import logging
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from time import perf_counter

from langchain_openai import OpenAIEmbeddings, ChatOpenAI

from car_search_rag.common.sql_session import SqlSession
from car_search_rag.car_search.car_manual_repository import CarManualRepository
from car_search_rag.car_search.image_relevance import select_relevant_images
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536
RERANKER_MODEL = "gpt-5.6-luna"
RERANKER_TIMEOUT_SECONDS = 15
RERANKER_MAX_RETRIES = 1
RERANKER_BACKOFF_SECONDS = 0.5
HYBRID_TOP_K = 10
HYBRID_MAX_CANDIDATES = 20
HYBRID_RERANK_COMPLETION_TOKENS = 1200
machine_logger = logging.getLogger("car_search_rag.car_manual")

KEYWORD_EXTRACTION_PROMPT = """Extract search phrases and individual terms from a Korean vehicle-manual question.
Return only a JSON object in this shape: {\"phrases\":[\"핵심 구문\"],\"terms\":[\"핵심어1\",\"핵심어2\"]}.
- phrases: 1 to 2 short, important compound words or phrases from the question.
- terms: 2 to 4 meaningful single core words from the question. Split important compounds into their component words when useful.
- Do not return only long compound search queries.
- Exclude generic words such as 차량, 방법, 경우, 사용, 것, and exclude particles and question endings.
- Do not add answer information that is not in the question. Use synonyms only when necessary and minimally.
- Preserve meaningful technical names and abbreviations."""

_GENERIC_KEYWORD_TERMS = frozenset({
    "차량", "방법", "경우", "사용", "것", "무엇", "어떤", "어느", "어디", "어떻게", "수",
})
_QUESTION_ENDINGS = (
    "인가요?", "이나요?", "하나요?", "인가요", "이나요", "하나요", "나요", "까요", "습니까", "인가",
)
def _clean_keyword_group(values, *, group_name, minimum, maximum, allow_phrases):
    if not isinstance(values, list):
        raise ValueError(f"Keyword extraction response must contain a {group_name} array")

    cleaned = []
    for value in values:
        if not isinstance(value, str):
            continue
        keyword = re.sub(r"\s+", " ", value).strip()
        keyword = keyword.strip("\"'“”‘’.,!?;:")
        for ending in _QUESTION_ENDINGS:
            if keyword.endswith(ending):
                keyword = keyword[:-len(ending)].rstrip()
                break
        if not keyword or keyword in _GENERIC_KEYWORD_TERMS:
            continue
        if not allow_phrases and any(char.isspace() for char in keyword):
            continue
        if keyword not in cleaned:
            cleaned.append(keyword)

    if not minimum <= len(cleaned) <= maximum:
        raise ValueError(
            f"Expected {minimum}-{maximum} distinct {group_name}, got {len(cleaned)}"
        )
    return cleaned

RERANKER_SYSTEM_PROMPT = """You are a retrieval reranker.
질문과 제공된 문서 청크만 비교해, 질문에 답하는 근거로 직접 관련된 순서대로 정렬하세요.
질문에 직접 답하는 내용, 같은 부품·기능·작업에 대한 구체적인 절차·조건·경고를 우선하고, 단어만 비슷하거나 일반적인 문서는 낮게 평가하세요.
답변을 작성하거나 후보 text를 고치거나 후보를 추가하지 마세요. 모든 후보 ID를 정확히 한 번씩 반환하세요.
JSON object만 반환하세요. 형식: {"ranking":[{"candidate_id":"C01","relevance_score":0}]}
점수는 0~100 정수이며 ranking은 relevance_score 내림차순입니다."""


def _message_text(message) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(item.get("text", "") for item in content if isinstance(item, dict))
    return str(content)


def _message_token_usage(message) -> tuple[int, int]:
    usage = getattr(message, "usage_metadata", None) or {}
    response_usage = (getattr(message, "response_metadata", None) or {}).get("token_usage", {})
    return (
        int(usage.get("input_tokens", response_usage.get("prompt_tokens", 0)) or 0),
        int(usage.get("output_tokens", response_usage.get("completion_tokens", 0)) or 0),
    )


@dataclass(frozen=True)
class ManualSearchAnswer:
    """기존 답변 텍스트와 현재 검색 호출의 원본 row를 묶는 결과 객체."""

    answer: str
    search_results: tuple

# =========================================================
# 차량 매뉴얼 검색 Service
# =========================================================
class CarManualSearchService:

    # =========================================================
    # 인스턴스 변수
    # =========================================================

    sql_session: SqlSession                         # 데이터베이스 세션
    repository: CarManualRepository                 # 매뉴얼 문서 검색 저장소
    embedding_model: OpenAIEmbeddings               # 검색 질의 임베딩 생성 모델
    chat_model: ChatOpenAI                          # 검색 질의 재작성과 답변 생성 모델
    rewrite_search_prompt: ChatPromptTemplate        # 대화 문맥 기반 검색어 재작성 프롬프트
    rewrite_search_chain: object                     # 검색어 재작성 프롬프트와 LLM 체인
    manual_answer_prompt: ChatPromptTemplate         # 검색 결과 기반 답변 생성 프롬프트
    manual_answer_chain: object                      # 매뉴얼 답변 생성 프롬프트와 LLM 체인

    # =========================================================
    # 생성자
    # =========================================================
    def __init__(self,sql_session):
        self.sql_session = sql_session                              # 전달받은 데이터베이스 세션
        self.repository = CarManualRepository(sql_session=self.sql_session)  # 문서 검색 저장소

        self.reranking_enabled = os.getenv("ENABLE_LLM_RERANKING", "true").strip().lower() in {"1", "true", "yes", "on"}
        self.hybrid_search_enabled = os.getenv("ENABLE_HYBRID_SEARCH", "true").strip().lower() in {"1", "true", "yes", "on"}

        self.embedding_model = OpenAIEmbeddings(                     # 질의 임베딩 모델
            model=EMBEDDING_MODEL
        )

        self.chat_model = ChatOpenAI(                                 # 검색·답변 생성에 사용할 LLM
                model="gpt-6-luna"
            )

        self.reranker_model = (
            ChatOpenAI(
                model=RERANKER_MODEL,
                max_completion_tokens=400,
                timeout=RERANKER_TIMEOUT_SECONDS,
                max_retries=0,
            ).bind(response_format={"type": "json_object"})
            if self.reranking_enabled
            else None
        )


        # =========================================================
        # 검색 질문 재작성 Chain
        # =========================================================
        self.rewrite_search_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
    너는 차량 매뉴얼 검색용 질문을 만드는 역할이다.

    이전 대화를 참고해서 현재 질문을
    혼자 읽어도 의미가 통하는 검색 문장으로 다시 작성해라.

    차량 매뉴얼 검색에 도움이 되는 관련 용어나 동의어가 있으면 포함해라.

    설명하지 말고 검색 문장 하나만 반환해라.
    """
                ),
                (
                    "human",
                    """
    [이전 대화]
    {history}

    [현재 질문]
    {question}
    """
                )
            ]
        )

        self.rewrite_search_chain = (
            self.rewrite_search_prompt
            | self.chat_model
            | StrOutputParser()
        )

        # =========================================================
        # 차량 매뉴얼 답변 생성 Chain
        # =========================================================
        self.manual_answer_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
        너는 차량 사용 설명서를 안내하는 AI 어시스턴트다.

        이전 대화와 차량 매뉴얼 검색 결과를 참고해서
        현재 사용자의 질문에 자연스럽게 답변해라.

        규칙:
        - 이전 대화의 맥락을 유지한다.
        - 매뉴얼 내용에 근거해서 답변한다.
        - 매뉴얼에 없는 내용은 추측하지 않는다.
        - 관련 페이지 번호를 함께 알려준다.
        - 관련 이미지 URL이 있으면 함께 알려준다.
        """
                ),
                (
                    "human",
                    """
        [이전 대화]
        {history}

        [현재 질문]
        {question}

        [차량 매뉴얼]
        {context}
        """
                )
            ]
        )

        self.manual_answer_chain = (
            self.manual_answer_prompt
            | self.chat_model
            | StrOutputParser()
        )






    # =========================================================
    # 차량 매뉴얼 AI 검색
    # =========================================================
    def search_manual(self,car_brand_eng_nm,car_eng_nm,car_model_yr,question,limit=5):
        """Return the current vector candidates, reranked when enabled."""
        results, _metadata = self.search_manual_with_metadata(
            car_brand_eng_nm=car_brand_eng_nm,
            car_eng_nm=car_eng_nm,
            car_model_yr=car_model_yr,
            question=question,
            limit=limit,
        )
        return results

    def search_manual_with_metadata(
        self,
        car_brand_eng_nm,
        car_eng_nm,
        car_model_yr,
        question,
        limit=5,
        *,
        enable_reranking=None,
    ):
        """Run parallel Vector/LIKE retrieval, then rerank merged candidates.

        Set ``ENABLE_HYBRID_SEARCH=false`` to use the original Vector-only path.
        """
        if getattr(self, "hybrid_search_enabled", False):
            return self._search_manual_hybrid(
                car_brand_eng_nm, car_eng_nm, car_model_yr, question, limit,
                enable_reranking=enable_reranking,
            )

        total_started = perf_counter()
        vector_started = perf_counter()
        query_vector = self.embedding_model.embed_query(question)
        vector_results = self.repository.search_manual(
            car_brand_eng_nm=car_brand_eng_nm,
            car_eng_nm=car_eng_nm,
            car_model_yr=car_model_yr,
            embedding=query_vector,
            limit=limit
        )
        vector_latency = perf_counter() - vector_started
        should_rerank = self.reranking_enabled if enable_reranking is None else bool(enable_reranking)
        if not should_rerank:
            metadata = {
                "success": False,
                "model": RERANKER_MODEL,
                "latency_seconds": 0.0,
                "input_tokens": 0,
                "output_tokens": 0,
                "fallback_reason": "reranking disabled",
                "candidate_count": len(vector_results or ()),
                "request_count": 0,
                "retry_count": 0,
            }
            machine_logger.info(
                "LLM rerank disabled candidates=%d reason=%s",
                metadata["candidate_count"], metadata["fallback_reason"],
            )
            metadata.update({
                "hybrid_enabled": False,
                "vector_branch_latency_seconds": vector_latency,
                "keyword_branch_latency_seconds": 0.0,
                "parallel_retrieval_latency_seconds": vector_latency,
                "reranking_latency_seconds": 0.0,
                "total_search_latency_seconds": perf_counter() - total_started,
            })
            return list(vector_results or ()), metadata

        ranked, metadata = self.rerank_search_results(question, vector_results)
        metadata.update({
            "hybrid_enabled": False,
            "vector_branch_latency_seconds": vector_latency,
            "keyword_branch_latency_seconds": 0.0,
            "parallel_retrieval_latency_seconds": vector_latency,
            "reranking_latency_seconds": metadata.get("latency_seconds", 0.0),
            "total_search_latency_seconds": perf_counter() - total_started,
        })
        return ranked, metadata

    @staticmethod
    def _chunk_identity(row):
        chunk_id = row.get("carManualChunkId", row.get("car_manual_chunk_id"))
        if chunk_id is not None:
            return ("chunk", str(chunk_id))
        return (
            row.get("carId", row.get("car_id")),
            row.get("carManualChapterId", row.get("car_manual_chapter_id")),
            row.get("carManualChunkPageNo", row.get("car_manual_chunk_page_no")),
            row.get("carManualChunkNo", row.get("car_manual_chunk_no")),
        )

    def _vector_branch(self, car_brand_eng_nm, car_eng_nm, car_model_yr, question):
        started = perf_counter()
        query_vector = self.embedding_model.embed_query(question)
        # Each branch owns a SqlSession; its SELECT checks out its own pool connection.
        branch_session = SqlSession(
            database_manager=self.sql_session.database_manager,
            sql_log_mode="none",
        )
        repository = CarManualRepository(branch_session)
        rows = repository.search_manual(
            car_brand_eng_nm=car_brand_eng_nm,
            car_eng_nm=car_eng_nm,
            car_model_yr=car_model_yr,
            embedding=query_vector,
            limit=HYBRID_TOP_K,
        )
        return {"rows": list(rows or ()), "latency": perf_counter() - started}

    def _keyword_branch(self, car_brand_eng_nm, car_eng_nm, car_model_yr, question):
        started = perf_counter()
        extraction_started = perf_counter()
        try:
            response = self.chat_model.invoke([
                ("system", KEYWORD_EXTRACTION_PROMPT),
                ("human", question),
            ])
            raw = _message_text(response).strip()
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE)
            parsed = json.loads(raw)
            phrases = _clean_keyword_group(
                parsed.get("phrases") if isinstance(parsed, dict) else None,
                group_name="phrases", minimum=1, maximum=2, allow_phrases=True,
            )
            terms = _clean_keyword_group(
                parsed.get("terms") if isinstance(parsed, dict) else None,
                group_name="terms", minimum=2, maximum=4, allow_phrases=False,
            )
            extraction_latency = perf_counter() - extraction_started

            branch_session = SqlSession(
                database_manager=self.sql_session.database_manager,
                sql_log_mode="none",
            )
            repository = CarManualRepository(branch_session)
            car_lookup_started = perf_counter()
            car_id = repository.find_car_id(car_brand_eng_nm, car_eng_nm, car_model_yr)
            car_lookup_latency = perf_counter() - car_lookup_started
            like_started = perf_counter()
            rows = repository.search_manual_by_keywords(car_id, phrases, terms, HYBRID_TOP_K)
            like_latency = perf_counter() - like_started
            return {
                "rows": list(rows or ()), "phrases": phrases, "terms": terms,
                "extraction_latency": extraction_latency,
                "car_lookup_latency": car_lookup_latency,
                "like_latency": like_latency,
                "latency": perf_counter() - started,
                "error": None,
            }
        except Exception as exc:
            return {
                "rows": [], "phrases": [], "terms": [],
                "extraction_latency": perf_counter() - extraction_started,
                "car_lookup_latency": 0.0, "like_latency": 0.0,
                "latency": perf_counter() - started,
                "error": f"{type(exc).__name__}: {str(exc)[:240]}",
            }

    def _search_manual_hybrid(
        self, car_brand_eng_nm, car_eng_nm, car_model_yr, question, limit,
        *, enable_reranking=None,
    ):
        total_started = perf_counter()
        retrieval_started = perf_counter()
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="car-search") as executor:
            vector_future = executor.submit(
                self._vector_branch,
                car_brand_eng_nm, car_eng_nm, car_model_yr, question,
            )
            keyword_future = executor.submit(
                self._keyword_branch,
                car_brand_eng_nm, car_eng_nm, car_model_yr, question,
            )
            # Preserve the existing Vector failure policy: its exception propagates.
            vector_result = vector_future.result()
            keyword_result = keyword_future.result()
        parallel_latency = perf_counter() - retrieval_started
        vector_rows = vector_result["rows"]

        if keyword_result["error"]:
            machine_logger.warning(
                "Hybrid keyword branch failed; falling back to Vector candidates reason=%s",
                keyword_result["error"],
            )
        candidates = []
        rank_metadata = {}
        for rank, row in enumerate(vector_rows, 1):
            key = self._chunk_identity(row)
            rank_metadata.setdefault(key, {})["vector_rank"] = rank
            if not any(self._chunk_identity(existing) == key for existing in candidates):
                candidates.append(row)
        if not keyword_result["error"]:
            for rank, row in enumerate(keyword_result["rows"], 1):
                key = self._chunk_identity(row)
                rank_metadata.setdefault(key, {})["keyword_rank"] = rank
                rank_metadata[key]["keyword_score"] = row.get("keywordScore", row.get("keyword_score"))
                if not any(self._chunk_identity(existing) == key for existing in candidates):
                    candidates.append(row)
        if len(candidates) > HYBRID_MAX_CANDIDATES:
            raise AssertionError(f"Hybrid candidate count exceeded {HYBRID_MAX_CANDIDATES}")

        should_rerank = self.reranking_enabled if enable_reranking is None else bool(enable_reranking)
        rerank_started = perf_counter()
        if should_rerank and len(candidates) >= HYBRID_TOP_K:
            ranked, rerank_metadata = self.rerank_search_results(
                question, candidates, candidate_metadata=rank_metadata,
            )
        elif should_rerank and candidates:
            # Keep the legacy behavior for fewer than ten candidates.
            ranked, rerank_metadata = self.rerank_search_results(
                question, candidates, candidate_metadata=rank_metadata,
            )
        else:
            ranked = candidates
            rerank_metadata = {
                "success": False, "model": RERANKER_MODEL, "latency_seconds": 0.0,
                "input_tokens": 0, "output_tokens": 0,
                "fallback_reason": "reranking disabled" if not should_rerank else "no candidates",
                "candidate_count": len(candidates), "request_count": 0, "retry_count": 0,
                "candidate_mapping": [],
            }
        rerank_elapsed = perf_counter() - rerank_started
        metadata = dict(rerank_metadata)
        metadata.update({
            "hybrid_enabled": True,
            "keyword_phrases": keyword_result["phrases"],
            "keyword_terms": keyword_result["terms"],
            "keyword_branch_failed": bool(keyword_result["error"]),
            "keyword_fallback_reason": keyword_result["error"],
            "vector_candidate_count": len(vector_rows),
            "keyword_candidate_count": len(keyword_result["rows"]),
            "merged_candidate_count": len(candidates),
            "vector_branch_latency_seconds": vector_result["latency"],
            "keyword_extraction_latency_seconds": keyword_result["extraction_latency"],
            "keyword_car_lookup_latency_seconds": keyword_result["car_lookup_latency"],
            "keyword_like_latency_seconds": keyword_result["like_latency"],
            "keyword_branch_latency_seconds": keyword_result["latency"],
            "parallel_retrieval_latency_seconds": parallel_latency,
            "reranking_latency_seconds": rerank_metadata.get("latency_seconds", rerank_elapsed),
            "total_search_latency_seconds": perf_counter() - total_started,
        })
        machine_logger.info(
            "Hybrid search enabled=%s vector_n=%d keyword_n=%d merged_n=%d phrases=%s terms=%s "
            "vector_branch_ms=%.1f keyword_extract_ms=%.1f keyword_car_lookup_ms=%.1f "
            "keyword_like_ms=%.1f keyword_branch_ms=%.1f parallel_retrieval_ms=%.1f "
            "rerank_ms=%.1f total_ms=%.1f keyword_failed=%s",
            True, len(vector_rows), len(keyword_result["rows"]), len(candidates),
            keyword_result["phrases"], keyword_result["terms"], vector_result["latency"] * 1000,
            keyword_result["extraction_latency"] * 1000,
            keyword_result["car_lookup_latency"] * 1000,
            keyword_result["like_latency"] * 1000, keyword_result["latency"] * 1000,
            parallel_latency * 1000, metadata["reranking_latency_seconds"] * 1000,
            metadata["total_search_latency_seconds"] * 1000, bool(keyword_result["error"]),
        )
        return list(ranked[:limit]), metadata

    def rerank_search_results(self, question, candidates, *, candidate_metadata=None):
        """Rerank 10-20 retrieved rows, returning originals and safe metadata.

        Any request, parse, or validation failure returns the original Vector
        order. Candidate IDs are stable C01-C20 labels and map back without
        modifying source rows. The legacy 10-candidate request keeps its existing
        model token limit; larger sets use the validated experiment's larger cap.
        """
        vector_rows = list(candidates or ())
        metadata = {
            "success": False,
            "model": RERANKER_MODEL,
            "latency_seconds": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "fallback_reason": None,
            "candidate_count": len(vector_rows),
            "request_count": 0,
            "retry_count": 0,
        }

        if len(vector_rows) < 10 or len(vector_rows) > HYBRID_MAX_CANDIDATES:
            metadata["fallback_reason"] = (
                f"expected 10 vector candidates; got {len(vector_rows)}"
                if len(vector_rows) < 10
                else f"expected at most {HYBRID_MAX_CANDIDATES} candidates; got {len(vector_rows)}"
            )
            machine_logger.warning(
                "LLM rerank fallback model=%s candidates=%d reason=%s",
                RERANKER_MODEL, len(vector_rows), metadata["fallback_reason"],
            )
            return vector_rows, metadata
        if self.reranker_model is None:
            metadata["fallback_reason"] = "reranker model unavailable"
            machine_logger.warning("LLM rerank fallback model=%s reason=%s", RERANKER_MODEL, metadata["fallback_reason"])
            return vector_rows, metadata

        # Avoid object spread/merge here: the model label cannot be overwritten
        # by the source page/chunk identity.
        candidate_rows = {}
        prompt_candidates = []
        for index, row in enumerate(vector_rows, start=1):
            candidate_id = f"C{index:02d}"
            candidate_rows[candidate_id] = row
            page_no = row.get("carManualChunkPageNo", row.get("car_manual_chunk_page_no"))
            chunk_id = row.get("carManualChunkNo", row.get("car_manual_chunk_no"))
            database_chunk_id = row.get("carManualChunkId", row.get("car_manual_chunk_id"))
            candidate_rank = (candidate_metadata or {}).get(self._chunk_identity(row), {})
            mapping = {
                "candidate_id": candidate_id,
                "page_no": page_no,
                "chunk_id": chunk_id,
            }
            if database_chunk_id is not None:
                mapping["database_chunk_id"] = database_chunk_id
            mapping.update(candidate_rank)
            metadata.setdefault("candidate_mapping", []).append(mapping)
            prompt_candidates.append({
                "candidate_id": candidate_id,
                "page_no": page_no,
                "chunk_id": chunk_id,
                "text": row.get("carManualChunkTxt", row.get("car_manual_chunk_txt", "")),
            })

        payload = {"question": question, "candidates": prompt_candidates}
        expected_ids = {f"C{i:02d}" for i in range(1, len(vector_rows) + 1)}
        total_started = perf_counter()
        last_error = None
        reranker = self.reranker_model
        if len(vector_rows) > 10:
            # More ranking entries need a larger completion budget. The model
            # and response format remain the production configuration.
            base_model = getattr(self.reranker_model, "bound", None)
            if base_model is not None:
                reranker = base_model.bind(
                    max_completion_tokens=HYBRID_RERANK_COMPLETION_TOKENS
                ).bind(response_format={"type": "json_object"})

        for attempt in range(RERANKER_MAX_RETRIES + 1):
            metadata["request_count"] += 1
            try:
                response = reranker.invoke([
                    ("system", RERANKER_SYSTEM_PROMPT),
                    ("human", json.dumps(payload, ensure_ascii=False)),
                ])
                input_tokens, output_tokens = _message_token_usage(response)
                metadata["input_tokens"] += input_tokens
                metadata["output_tokens"] += output_tokens
                raw = _message_text(response).strip()
                raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE)
                result = json.loads(raw)
                ranking = result.get("ranking")
                if not isinstance(ranking, list):
                    raise ValueError("JSON must contain ranking array")
                ids = [item.get("candidate_id") for item in ranking]
                expected_count = len(vector_rows)
                if len(ids) != expected_count or set(ids) != expected_ids or len(set(ids)) != expected_count:
                    raise ValueError(f"ranking must include C01-C{expected_count:02d} exactly once")
                for item in ranking:
                    score = item.get("relevance_score")
                    if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 100:
                        raise ValueError(f"invalid relevance_score for {item['candidate_id']}")
                scores = [item["relevance_score"] for item in ranking]
                if any(left < right for left, right in zip(scores, scores[1:])):
                    raise ValueError("ranking must be sorted by descending relevance_score")

                reordered = [candidate_rows[item["candidate_id"]] for item in ranking]
                metadata["success"] = True
                metadata["latency_seconds"] = perf_counter() - total_started
                machine_logger.info(
                    "LLM rerank success model=%s candidates=%d latency_ms=%.1f input_tokens=%d output_tokens=%d retries=%d",
                    RERANKER_MODEL, len(vector_rows), metadata["latency_seconds"] * 1000,
                    metadata["input_tokens"], metadata["output_tokens"], metadata["retry_count"],
                )
                return reordered, metadata
            except Exception as exc:
                last_error = (
                    f"{type(exc).__name__}: "
                    f"{getattr(exc, 'code', None) or getattr(exc, 'status_code', None) or str(exc)[:240]}"
                )
                if attempt < RERANKER_MAX_RETRIES:
                    metadata["retry_count"] += 1
                    time.sleep(RERANKER_BACKOFF_SECONDS)

        metadata["latency_seconds"] = perf_counter() - total_started
        metadata["fallback_reason"] = last_error or "reranking failed"
        machine_logger.warning(
            "LLM rerank fallback model=%s candidates=%d latency_ms=%.1f input_tokens=%d output_tokens=%d retries=%d reason=%s",
            RERANKER_MODEL, len(vector_rows), metadata["latency_seconds"] * 1000,
            metadata["input_tokens"], metadata["output_tokens"], metadata["retry_count"],
            metadata["fallback_reason"],
        )
        return vector_rows, metadata



    def select_relevant_images(self, question, search_results, limit=3):
        """Select display images only from pages in current chunk search results."""
        rows = tuple(search_results or ())
        car_ids = {row.get("carId", row.get("car_id")) for row in rows if row.get("carId", row.get("car_id"))}
        if len(car_ids) != 1:
            return []
        pages = {row.get("carManualChunkPageNo", row.get("car_manual_chunk_page_no")) for row in rows if row.get("carManualChunkPageNo", row.get("car_manual_chunk_page_no")) is not None}
        candidates = self.repository.search_images_by_pages(next(iter(car_ids)), pages)
        return select_relevant_images(question, rows, candidates, limit=limit)

    # =========================================================
    # 차량 매뉴얼 LLM 답변 생성
    # =========================================================
    def generate_manual_answer(
        self,
        question,
        search_docs,
        conversation_history=None,
        *,
        stream_writer=None,
        stream_timing=None,
    ):
        
        if not search_docs:
            answer = "관련된 차량 매뉴얼 내용을 찾지 못했습니다."
            if stream_writer is not None:
                stream_writer({"type": "answer_token", "text": answer})
            return answer

        context_list = []

        for index, doc in enumerate(search_docs, start=1):

            context_list.append(
                f"""
    [검색 문서 {index}]

    페이지:
    {doc.get("carManualChunkPageNo")}

    내용:
    {doc.get("carManualChunkTxt")}

    이미지 URL:
    {doc.get("carManualImageUrl") or "없음"}
    """
            )

        context = "\n".join(context_list)

        # =========================================================
        # 이전 대화 문자열 생성
        # =========================================================
        if conversation_history:

            recent_messages = conversation_history

            history_text = "\n".join(
                [
                    f"{message['role']}: {message['content']}"
                    for message in recent_messages
                ]
            )

        else:
            history_text = "없음"

        # =========================================================
        # LangChain 실행
        # =========================================================
        inputs = {
            "history": history_text,
            "question": question,
            "context": context,
        }
        if stream_writer is not None:
            return self._stream_manual_answer(inputs, stream_writer, stream_timing)

        answer = self.manual_answer_chain.invoke(inputs)

        return answer

    def _stream_manual_answer(self, inputs, stream_writer, stream_timing):
        stream_timing = stream_timing or {}
        total_started = stream_timing.get("total_started", perf_counter())
        retrieval_rerank_ms = stream_timing.get("retrieval_rerank_ms", 0.0)
        generation_started = perf_counter()
        first_token_at = None
        answer_chunks = []
        machine_logger.info(
            "answer_generation_start retrieval_rerank_ms=%.1f",
            retrieval_rerank_ms,
        )

        try:
            for chunk in self.manual_answer_chain.stream(inputs):
                if not chunk:
                    continue
                text = chunk if isinstance(chunk, str) else str(chunk)
                if first_token_at is None:
                    first_token_at = perf_counter()
                    machine_logger.info(
                        "answer_first_token ttft_ms=%.1f",
                        (first_token_at - generation_started) * 1000,
                    )
                answer_chunks.append(text)
                stream_writer({"type": "answer_token", "text": text})
        except Exception:
            machine_logger.exception("manual answer streaming failed")
            raise
        finally:
            finished = perf_counter()
            ttft_ms = (
                (first_token_at - generation_started) * 1000
                if first_token_at is not None
                else None
            )
            machine_logger.info(
                "answer_generation_complete retrieval_rerank_ms=%.1f generation_ms=%.1f ttft_ms=%s total_ms=%.1f",
                retrieval_rerank_ms,
                (finished - generation_started) * 1000,
                f"{ttft_ms:.1f}" if ttft_ms is not None else "unavailable",
                (finished - total_started) * 1000,
            )
        return "".join(answer_chunks)


    # =========================================================
    # 차량 매뉴얼 AI 질의
    # =========================================================
    def ask_manual(self, car_brand_eng_nm, car_eng_nm, car_model_yr, question, conversation_history=None, limit=5):
        """기존 호출부 호환을 위해 답변 문자열만 반환한다."""
        return self.ask_manual_with_sources(
            car_brand_eng_nm=car_brand_eng_nm,
            car_eng_nm=car_eng_nm,
            car_model_yr=car_model_yr,
            question=question,
            conversation_history=conversation_history,
            limit=limit,
        ).answer

    def ask_manual_with_sources(
        self,
        car_brand_eng_nm,
        car_eng_nm,
        car_model_yr,
        question,
        conversation_history=None,
        limit=5,
        stream_writer=None,
    ):
        """기존 검색/답변 경로를 실행하고 해당 호출의 검색 row를 함께 반환한다."""

        # =========================================================
        # 이전 대화 기반 검색 질문 재작성
        # =========================================================
        total_started = perf_counter()
        search_question = self.rewrite_search_question(
            question=question,
            conversation_history=conversation_history
        )


        # =========================================================
        # 차량 매뉴얼 검색
        # =========================================================
        retrieval_started = perf_counter()
        search_docs = self.search_manual(
            car_brand_eng_nm=car_brand_eng_nm,
            car_eng_nm=car_eng_nm,
            car_model_yr=car_model_yr,
            question=search_question,
            limit=limit
        )

        # =========================================================
        # LLM 답변 생성
        # =========================================================
        retrieval_rerank_ms = (perf_counter() - retrieval_started) * 1000
        if stream_writer is not None:
            machine_logger.info(
                "retrieval_rerank_complete elapsed_ms=%.1f",
                retrieval_rerank_ms,
            )
        stream_timing = {
            "total_started": total_started,
            "retrieval_rerank_ms": retrieval_rerank_ms,
        }
        answer = self.generate_manual_answer(
            question=question,
            search_docs=search_docs,
            conversation_history=conversation_history,
            stream_writer=stream_writer,
            stream_timing=stream_timing,
        )

        return ManualSearchAnswer(
            answer=answer,
            search_results=tuple(search_docs or ()),
        )


    # =========================================================
    # 이전 대화 기반 검색 질문 재작성
    # =========================================================
    def rewrite_search_question(self, question, conversation_history=None ):
        """이전 대화를 참고하여 검색용 질문을 독립적인 문장으로 재작성"""

        # 이전 대화가 없으면 현재 질문 그대로 사용
        machine_logger.info(
            "rewrite_search_question input - question=%r, conversation_history=%r",
            question,
            conversation_history,
        )
        if not conversation_history:
            return question


        recent_messages = conversation_history              # 메시지 누적


        history_text = "\n".join(
            [
                f"{message['role']}: {message['content']}"
                for message in recent_messages
            ]
        )


        # =========================================================
        # LangChain 실행
        # =========================================================
        search_question = self.rewrite_search_chain.invoke(
            {
                "history": history_text,
                "question": question
            }
        )

        return search_question.strip()
