"""아이오닉: 코사인 10개 + AI 키워드 LIKE 10개 → LLM 재정렬 → 5개.

DB 접근은 아이오닉 백엔드가 제공하는 함수만 사용합니다. 검색 중간 결과는
호출마다 따로 반환하여 여러 대화가 동시에 진행돼도 서로 섞이지 않습니다.
"""
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from dataclasses import dataclass
from hashlib import sha256
import json
import re
from threading import RLock
from time import perf_counter

from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from car_search_rag.anna_rag.chatbot.ioniq5_search_policy import (
    IoniqReranker, KEYWORD_EXTRACTION_PROMPT, RERANKER_SYSTEM_PROMPT, RERANKER_MODEL,
    RERANKER_TIMEOUT_SECONDS, HYBRID_RERANK_COMPLETION_TOKENS,
    _clean_keyword_group, _message_text,
)


@dataclass(frozen=True)
class SearchHit:
    document: Document
    cosine_distance: float | None
    cosine_rank: int | None
    keyword_rank: int | None
    keyword_score: int | None


@dataclass(frozen=True)
class SearchResult:
    hits: list[SearchHit]
    vector: list[float]
    metadata: dict


class IoniqKeywordRerankSearch:
    def __init__(self, load_ids, vector_search, keyword_search, *, keyword_model=None,
                 reranker_model=None):
        self.load_ids = load_ids
        self.vector_search = vector_search
        self.keyword_search = keyword_search
        self.keyword_model = keyword_model if keyword_model is not None else ChatOpenAI(
            model='gpt-6-luna', timeout=30, max_retries=0)
        if reranker_model is None:
            reranker_model = ChatOpenAI(model=RERANKER_MODEL,
                max_completion_tokens=HYBRID_RERANK_COMPLETION_TOKENS,
                timeout=RERANKER_TIMEOUT_SECONDS, max_retries=0
            ).bind(response_format={'type': 'json_object'})
        self.reranker = IoniqReranker(reranker_model)
        self._ordinals = None
        self._lock = RLock()

    def warmup(self):
        # 평가 때처럼 청크 ID 순서로 표시 번호를 부여합니다. 본문/대화는 저장하지 않습니다.
        with self._lock:
            if self._ordinals is None:
                self._ordinals = {cid: i for i, cid in enumerate(sorted(self.load_ids()), 1)}

    def configuration(self):
        return dict(method='cosine_keyword_llm_rerank', top_k=5, candidate_k=10,
            max_candidates=20, keyword_model='gpt-6-luna', reranker_model=RERANKER_MODEL,
            keyword_phrase_weight=3, keyword_term_weight=1,
            keyword_tie_break='first PDF page, chunk_id ascending',
            keyword_failure='vector candidates', rerank_failure='original candidate order',
            keyword_timeout_seconds=30, rerank_timeout_seconds=RERANKER_TIMEOUT_SECONDS,
            rerank_max_retries=1, rerank_completion_tokens=HYBRID_RERANK_COMPLETION_TOKENS,
            prompt_hash=sha256(json.dumps([KEYWORD_EXTRACTION_PROMPT, RERANKER_SYSTEM_PROMPT],
                                         ensure_ascii=False).encode()).hexdigest(),
            policy_version='sonata-transfer-f2c5976246f5')

    def _keywords(self, question):
        start = perf_counter()
        try:
            response = self.keyword_model.invoke([
                ('system', KEYWORD_EXTRACTION_PROMPT), ('human', question)])
            raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', _message_text(response).strip(), flags=re.I)
            parsed = json.loads(raw)
            phrases = _clean_keyword_group(
                parsed.get('phrases') if isinstance(parsed, dict) else None,
                group_name='phrases', minimum=0, maximum=2, allow_phrases=True)
            terms = _clean_keyword_group(
                parsed.get('terms') if isinstance(parsed, dict) else None,
                group_name='terms', minimum=0, maximum=4, allow_phrases=False)
            if not phrases and not terms:
                raise ValueError('Empty search keywords')
            extracted = perf_counter() - start
            rows = self.keyword_search(phrases, terms, 10)
            return rows, dict(keyword_phrases=phrases, keyword_terms=terms,
                keyword_branch_failed=False, keyword_fallback_reason=None,
                keyword_extraction_latency_seconds=extracted,
                keyword_branch_latency_seconds=perf_counter() - start)
        except Exception as error:
            # 접속 정보나 외부 응답 전문을 대화 기록에 남기지 않습니다.
            return [], dict(keyword_phrases=[], keyword_terms=[],
                keyword_branch_failed=True, keyword_fallback_reason=type(error).__name__,
                keyword_extraction_latency_seconds=perf_counter() - start,
                keyword_branch_latency_seconds=perf_counter() - start)

    def search(self, question, vector=None):
        started = perf_counter()
        self.warmup()
        # 질문 임베딩+벡터 검색과 키워드 AI+LIKE 검색은 동시에 진행합니다.
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix='ioniq-retrieval') as worker:
            dense_future = worker.submit(copy_context().run, self.vector_search, question, 10, vector)
            keyword_future = worker.submit(copy_context().run, self._keywords, question)
            query_vector, dense = dense_future.result()
            lexical, keyword_meta = keyword_future.result()
        parallel_elapsed = perf_counter() - started
        documents, ranks, distances, candidates = {}, {}, {}, []
        for rank, (doc, distance) in enumerate(dense, 1):
            documents[doc.id] = doc
            distances[doc.id] = float(distance)
            ranks.setdefault(doc.id, {})['vector_rank'] = rank
            if doc.id not in candidates:
                candidates.append(doc.id)
        for rank, (doc, score) in enumerate(lexical, 1):
            documents.setdefault(doc.id, doc)
            ranks.setdefault(doc.id, {}).update(keyword_rank=rank, keyword_score=int(score))
            if doc.id not in candidates:
                candidates.append(doc.id)
        if len(candidates) > 20:
            raise ValueError('Search candidate limit exceeded')
        with self._lock:
            if any(cid not in self._ordinals for cid in candidates):
                self._ordinals = None
                self.warmup()
            ordinals = dict(self._ordinals)
        # 소나타 평가와 같은 후보 payload(원문 전체, 페이지, 청크 번호)를 전달합니다.
        rows = [dict(carManualChunkId=cid, carManualChunkNo=ordinals[cid],
                     carManualChunkPageNo=min(documents[cid].metadata['pdf_pages']),
                     carManualChunkTxt=documents[cid].page_content) for cid in candidates]
        rank_metadata = {('chunk', cid): ranks[cid] for cid in candidates}
        ranked, rerank_meta = self.reranker.rerank_search_results(
            question, rows, candidate_metadata=rank_metadata)
        hits = [SearchHit(document=documents[row['carManualChunkId']],
                   cosine_distance=distances.get(row['carManualChunkId']),
                   cosine_rank=ranks[row['carManualChunkId']].get('vector_rank'),
                   keyword_rank=ranks[row['carManualChunkId']].get('keyword_rank'),
                   keyword_score=ranks[row['carManualChunkId']].get('keyword_score'))
                for row in ranked[:5]]
        return SearchResult(hits=hits, vector=query_vector, metadata={**self.configuration(),
            **keyword_meta, 'rerank': rerank_meta,
            'vector_candidate_count': len(dense), 'keyword_candidate_count': len(lexical),
            'merged_candidate_count': len(candidates),
            'parallel_retrieval_latency_seconds': parallel_elapsed,
            'total_search_latency_seconds': perf_counter() - started})
