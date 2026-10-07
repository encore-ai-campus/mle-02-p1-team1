"""아이오닉 전용 검색 정책: 검증한 소나타 프롬프트·재정렬 검사를 독립 보관합니다.

출처: sonata_transfer_v1/sonata_service_snapshot.py (SHA-256 f2c5976246f56041aab75a70b093978c38cfde83c8098af0bd2db36e0e0ed009).
팀원의 이후 수정과 분리하며, 정답지나 소나타 데이터는 실행 때 읽지 않습니다.
후보 ID를 빠뜨리거나 중복한 AI 응답은 재시도 후 원래 후보 순서로 복구합니다.
"""
import json
import logging
import re
import time
from time import perf_counter

machine_logger = logging.getLogger(__name__)

RERANKER_MODEL = 'gpt-5.6-luna'

RERANKER_TIMEOUT_SECONDS = 15

RERANKER_MAX_RETRIES = 1

RERANKER_BACKOFF_SECONDS = 0.5

HYBRID_MAX_CANDIDATES = 20

HYBRID_RERANK_COMPLETION_TOKENS = 1200

KEYWORD_EXTRACTION_PROMPT = 'Extract search phrases and individual terms from a Korean vehicle-manual question.\nReturn only a JSON object in this shape: {"phrases":["핵심 구문"],"terms":["핵심어1","핵심어2"]}.\n- phrases: 1 to 2 short, important compound words or phrases from the question.\n- terms: 2 to 4 meaningful single core words from the question. Split important compounds into their component words when useful.\n- Do not return only long compound search queries.\n- Exclude generic words such as 차량, 방법, 경우, 사용, 것, and exclude particles and question endings.\n- Do not add answer information that is not in the question. Use synonyms only when necessary and minimally.\n- Preserve meaningful technical names and abbreviations.'

_GENERIC_KEYWORD_TERMS = frozenset({'차량', '방법', '경우', '사용', '것', '무엇', '어떤', '어느', '어디', '어떻게', '수'})

_QUESTION_ENDINGS = ('인가요?', '이나요?', '하나요?', '인가요', '이나요', '하나요', '나요', '까요', '습니까', '인가')

def _clean_keyword_group(values, *, group_name, minimum, maximum, allow_phrases):
    """LLM에서 받은 검색어를 검증하고 중복 없이 정리한다."""
    if not isinstance(values, list):
        raise ValueError(f'Keyword extraction response must contain a {group_name} array')
    cleaned = []
    for value in values:
        if not isinstance(value, str):
            continue
        keyword = re.sub('\\s+', ' ', value).strip()
        keyword = keyword.strip('"\'“”‘’.,!?;:')
        for ending in _QUESTION_ENDINGS:
            if keyword.endswith(ending):
                keyword = keyword[:-len(ending)].rstrip()
                break
        if not keyword or keyword in _GENERIC_KEYWORD_TERMS:
            continue
        if not allow_phrases and any((char.isspace() for char in keyword)):
            continue
        if keyword not in cleaned:
            cleaned.append(keyword)
    if not minimum <= len(cleaned) <= maximum:
        raise ValueError(f'Expected {minimum}-{maximum} distinct {group_name}, got {len(cleaned)}')
    return cleaned

RERANKER_SYSTEM_PROMPT = 'You are a retrieval reranker.\n질문과 제공된 문서 청크만 비교해, 질문에 답하는 근거로 직접 관련된 순서대로 정렬하세요.\n질문에 직접 답하는 내용, 같은 부품·기능·작업에 대한 구체적인 절차·조건·경고를 우선하고, 단어만 비슷하거나 일반적인 문서는 낮게 평가하세요.\n답변을 작성하거나 후보 text를 고치거나 후보를 추가하지 마세요. 모든 후보 ID를 정확히 한 번씩 반환하세요.\nJSON object만 반환하세요. 형식: {"ranking":[{"candidate_id":"C01","relevance_score":0}]}\n점수는 0~100 정수이며 ranking은 relevance_score 내림차순입니다.'

def _message_text(message) -> str:
    """LangChain 응답의 content를 로그·파싱에 사용할 문자열로 변환한다."""
    content = getattr(message, 'content', '')
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return ''.join((item.get('text', '') for item in content if isinstance(item, dict)))
    return str(content)

def _message_token_usage(message) -> tuple[int, int]:
    """응답 metadata에서 입력·출력 token 수를 순서대로 반환한다."""
    usage = getattr(message, 'usage_metadata', None) or {}
    response_usage = (getattr(message, 'response_metadata', None) or {}).get('token_usage', {})
    return (int(usage.get('input_tokens', response_usage.get('prompt_tokens', 0)) or 0), int(usage.get('output_tokens', response_usage.get('completion_tokens', 0)) or 0))

class IoniqReranker:

    def __init__(self, model):
        self.reranker_model = model

    @staticmethod
    def _chunk_identity(row):
        """검색 row의 chunk ID를 중복 제거용 안정적인 key로 만든다."""
        chunk_id = row.get('carManualChunkId', row.get('car_manual_chunk_id'))
        if chunk_id is not None:
            return ('chunk', str(chunk_id))
        return (row.get('carId', row.get('car_id')), row.get('carManualChapterId', row.get('car_manual_chapter_id')), row.get('carManualChunkPageNo', row.get('car_manual_chunk_page_no')), row.get('carManualChunkNo', row.get('car_manual_chunk_no')))

    def rerank_search_results(self, question, candidates, *, candidate_metadata=None):
        """LLM 순위 응답을 검증해 원본 검색 row를 재배열한다.

        각 후보에 ID를 부여해 reranker에 전달하고, 반환된 ID가 원본 후보와 정확히
        일치하는지 확인한다. 응답이나 API 처리에 실패하면 입력 순서를 유지한다.
        """
        vector_rows = list(candidates or ())
        metadata = {'success': False, 'model': RERANKER_MODEL, 'latency_seconds': 0.0, 'input_tokens': 0, 'output_tokens': 0, 'fallback_reason': None, 'candidate_count': len(vector_rows), 'request_count': 0, 'retry_count': 0}
        if len(vector_rows) < 10 or len(vector_rows) > HYBRID_MAX_CANDIDATES:
            metadata['fallback_reason'] = f'expected 10 vector candidates; got {len(vector_rows)}' if len(vector_rows) < 10 else f'expected at most {HYBRID_MAX_CANDIDATES} candidates; got {len(vector_rows)}'
            machine_logger.warning('LLM rerank fallback model=%s candidates=%d reason=%s', RERANKER_MODEL, len(vector_rows), metadata['fallback_reason'])
            return (vector_rows, metadata)
        if self.reranker_model is None:
            metadata['fallback_reason'] = 'reranker model unavailable'
            machine_logger.warning('LLM rerank fallback model=%s reason=%s', RERANKER_MODEL, metadata['fallback_reason'])
            return (vector_rows, metadata)
        candidate_rows = {}
        prompt_candidates = []
        for (index, row) in enumerate(vector_rows, start=1):
            candidate_id = f'C{index:02d}'
            candidate_rows[candidate_id] = row
            page_no = row.get('carManualChunkPageNo', row.get('car_manual_chunk_page_no'))
            chunk_id = row.get('carManualChunkNo', row.get('car_manual_chunk_no'))
            database_chunk_id = row.get('carManualChunkId', row.get('car_manual_chunk_id'))
            candidate_rank = (candidate_metadata or {}).get(self._chunk_identity(row), {})
            mapping = {'candidate_id': candidate_id, 'page_no': page_no, 'chunk_id': chunk_id}
            if database_chunk_id is not None:
                mapping['database_chunk_id'] = database_chunk_id
            mapping.update(candidate_rank)
            metadata.setdefault('candidate_mapping', []).append(mapping)
            prompt_candidates.append({'candidate_id': candidate_id, 'page_no': page_no, 'chunk_id': chunk_id, 'text': row.get('carManualChunkTxt', row.get('car_manual_chunk_txt', ''))})
        payload = {'question': question, 'candidates': prompt_candidates}
        expected_ids = {f'C{i:02d}' for i in range(1, len(vector_rows) + 1)}
        total_started = perf_counter()
        last_error = None
        reranker = self.reranker_model
        if len(vector_rows) > 10:
            base_model = getattr(self.reranker_model, 'bound', None)
            if base_model is not None:
                reranker = base_model.bind(max_completion_tokens=HYBRID_RERANK_COMPLETION_TOKENS).bind(response_format={'type': 'json_object'})
        for attempt in range(RERANKER_MAX_RETRIES + 1):
            metadata['request_count'] += 1
            try:
                response = reranker.invoke([('system', RERANKER_SYSTEM_PROMPT), ('human', json.dumps(payload, ensure_ascii=False))])
                (input_tokens, output_tokens) = _message_token_usage(response)
                metadata['input_tokens'] += input_tokens
                metadata['output_tokens'] += output_tokens
                raw = _message_text(response).strip()
                raw = re.sub('^```(?:json)?\\s*|\\s*```$', '', raw, flags=re.IGNORECASE)
                result = json.loads(raw)
                ranking = result.get('ranking')
                if not isinstance(ranking, list):
                    raise ValueError('JSON must contain ranking array')
                ids = [item.get('candidate_id') for item in ranking]
                expected_count = len(vector_rows)
                if len(ids) != expected_count or set(ids) != expected_ids or len(set(ids)) != expected_count:
                    raise ValueError(f'ranking must include C01-C{expected_count:02d} exactly once')
                for item in ranking:
                    score = item.get('relevance_score')
                    if isinstance(score, bool) or not isinstance(score, int) or (not 0 <= score <= 100):
                        raise ValueError(f"invalid relevance_score for {item['candidate_id']}")
                scores = [item['relevance_score'] for item in ranking]
                if any((left < right for (left, right) in zip(scores, scores[1:]))):
                    raise ValueError('ranking must be sorted by descending relevance_score')
                reordered = [candidate_rows[item['candidate_id']] for item in ranking]
                metadata['success'] = True
                metadata['latency_seconds'] = perf_counter() - total_started
                machine_logger.info('LLM rerank success model=%s candidates=%d latency_ms=%.1f input_tokens=%d output_tokens=%d retries=%d', RERANKER_MODEL, len(vector_rows), metadata['latency_seconds'] * 1000, metadata['input_tokens'], metadata['output_tokens'], metadata['retry_count'])
                return (reordered, metadata)
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {getattr(exc, 'code', None) or getattr(exc, 'status_code', None) or str(exc)[:240]}"
                if attempt < RERANKER_MAX_RETRIES:
                    metadata['retry_count'] += 1
                    time.sleep(RERANKER_BACKOFF_SECONDS)
        metadata['latency_seconds'] = perf_counter() - total_started
        metadata['fallback_reason'] = last_error or 'reranking failed'
        machine_logger.warning('LLM rerank fallback model=%s candidates=%d latency_ms=%.1f input_tokens=%d output_tokens=%d retries=%d reason=%s', RERANKER_MODEL, len(vector_rows), metadata['latency_seconds'] * 1000, metadata['input_tokens'], metadata['output_tokens'], metadata['retry_count'], metadata['fallback_reason'])
        return (vector_rows, metadata)
