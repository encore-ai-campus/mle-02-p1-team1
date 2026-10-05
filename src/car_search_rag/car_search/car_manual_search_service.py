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
    """LLM에서 받은 검색어를 검증하고 중복 없이 정리한다."""
    if not isinstance(values, list):
        raise ValueError(f"Keyword extraction response must contain a {group_name} array")

    # 문자열 검색어만 정규화하고 허용되지 않는 항목은 제외한다.
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

    # 검색어 개수가 정책 범위를 벗어나면 호출 측에서 fallback하도록 오류를 낸다.
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
    """LangChain 응답의 content를 로그·파싱에 사용할 문자열로 변환한다."""
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # content가 여러 block이면 text가 있는 dict block만 이어 붙인다.
        return "".join(item.get("text", "") for item in content if isinstance(item, dict))
    return str(content)


def _message_token_usage(message) -> tuple[int, int]:
    """응답 metadata에서 입력·출력 token 수를 순서대로 반환한다."""
    usage = getattr(message, "usage_metadata", None) or {}
    response_usage = (getattr(message, "response_metadata", None) or {}).get("token_usage", {})
    # 최신·구형 응답 형식 중 값이 있는 쪽을 선택한다.
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
    # 검색 및 reranking
    # =========================================================
    def search_manual(self,car_brand_eng_nm,car_eng_nm,car_model_yr,question,limit=5):
        """차량 매뉴얼 후보를 검색하고 설정된 reranking 결과를 반환한다."""
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
        """검색과 reranking을 수행하고 결과 및 단계별 metadata를 반환한다.

        Hybrid Search가 켜져 있으면 Vector/Keyword 병렬 검색 경로를 사용한다.
        꺼져 있으면 기존 Vector Search 경로를 사용한다.
        반환값은 `(검색 원본 row 목록, 처리 metadata dict)` 형태다.
        """
        # 객체 생성 경로에 hybrid_search_enabled가 없으면 Vector 전용 경로를 선택한다.
        # region [Python 설명] getattr() 기본값
        # `getattr(object, "name", default)`는 attribute가 없어도 default를 반환한다.
        # 따라서 이전 방식으로 만든 service 객체도 이 설정 검사에서 오류가 나지 않는다.
        # endregion
        if getattr(self, "hybrid_search_enabled", False):
            return self._search_manual_hybrid(
                car_brand_eng_nm, car_eng_nm, car_model_yr, question, limit,
                enable_reranking=enable_reranking,
            )

        # Hybrid Search가 꺼진 경우 Vector Search부터 수행한다.
        total_started = perf_counter()
        vector_started = perf_counter()
        query_vector = self.embedding_model.embed_query(question)

        # 질의 embedding으로 매뉴얼 후보를 조회한다.
        vector_results = self.repository.search_manual(
            car_brand_eng_nm=car_brand_eng_nm,
            car_eng_nm=car_eng_nm,
            car_model_yr=car_model_yr,
            embedding=query_vector,
            limit=limit
        )
        vector_latency = perf_counter() - vector_started

        # 설정에 따라 reranking을 건너뛰거나 Vector 결과에 적용한다.
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

            # reranking 생략 사유와 검색 단계별 시간을 metadata에 기록한다.
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

        # reranker metadata에 Vector 전용 검색 시간을 덧붙인다.
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
        """검색 row의 chunk ID를 중복 제거용 안정적인 key로 만든다."""
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
        """Hybrid Search의 Vector branch를 실행하고 row와 소요 시간을 반환한다."""
        started = perf_counter()
        query_vector = self.embedding_model.embed_query(question)

        # 분기별 세션으로 Vector SELECT에 별도 pool connection을 사용한다.
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
        """질문에서 phrase/term을 추출하고 Keyword 후보와 분기 상태를 반환한다.

        LLM 검색어 추출부터 차량 조회, LIKE 검색까지의 시간과 오류를 결과 dict에 담는다.
        추출 또는 DB 조회에 실패하면 빈 후보와 오류 정보를 반환해 Hybrid fallback에 사용한다.
        """
        started = perf_counter()
        extraction_started = perf_counter()
        try:
            # 질문에서 검색에 사용할 phrase와 term을 추출한다.
            response = self.chat_model.invoke([
                ("system", KEYWORD_EXTRACTION_PROMPT),
                ("human", question),
            ])
            raw = _message_text(response).strip()
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE)
            parsed = json.loads(raw)

            # JSON 응답의 phrase/term 목록을 검색어 정책에 맞게 정리한다.
            # region [Python 설명] dict.get()과 isinstance()
            # JSON 최상위 값이 dict일 때만 `.get()`으로 각 key를 읽는다.
            # dict가 아니면 None을 넘겨 검색어 검증에서 오류 처리한다.
            # endregion
            phrases = _clean_keyword_group(
                parsed.get("phrases") if isinstance(parsed, dict) else None,
                group_name="phrases", minimum=1, maximum=2, allow_phrases=True,
            )
            terms = _clean_keyword_group(
                parsed.get("terms") if isinstance(parsed, dict) else None,
                group_name="terms", minimum=2, maximum=4, allow_phrases=False,
            )
            extraction_latency = perf_counter() - extraction_started

            # 해당 차량 ID를 찾고 phrase/term LIKE 검색을 실행한다.
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

            # 성공한 검색 결과와 각 하위 단계의 시간을 한 dict로 반환한다.
            return {
                "rows": list(rows or ()), "phrases": phrases, "terms": terms,
                "extraction_latency": extraction_latency,
                "car_lookup_latency": car_lookup_latency,
                "like_latency": like_latency,
                "latency": perf_counter() - started,
                "error": None,
            }
        # Keyword branch 실패는 빈 결과와 사유로 돌려 Hybrid Search가 Vector로 계속 진행하게 한다.
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
        """Vector/Keyword 후보를 병렬 검색, 병합, reranking하고 검색 metadata를 반환한다.

        Keyword branch가 실패하면 Vector 결과를 유지한다. 성공하면 chunk identity를 기준으로
        후보를 중복 제거하고, reranking 결과 순서로 원본 row를 반환한다.
        """
        total_started = perf_counter()
        retrieval_started = perf_counter()

        # Vector Search와 Keyword Search를 병렬로 실행한다.
        # region [Thread 설명] ThreadPoolExecutor와 Future
        # ThreadPoolExecutor는 여러 작업을 동시에 실행하는 thread pool이다.
        # `submit()`은 작업을 시작하고 완료 전 결과를 나타내는 Future를 돌려준다.
        # Future의 `.result()`는 해당 작업이 끝날 때까지 기다린 뒤 결과를 반환한다.
        # `with`를 벗어나면 executor가 정리된다. 기존 Vector 오류는 그대로 전달한다.
        # endregion
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="car-search") as executor:
            vector_future = executor.submit(
                self._vector_branch,
                car_brand_eng_nm, car_eng_nm, car_model_yr, question,
            )
            keyword_future = executor.submit(
                self._keyword_branch,
                car_brand_eng_nm, car_eng_nm, car_model_yr, question,
            )
            # 기존 Vector 예외 정책을 유지해 분기 오류를 그대로 전달한다.
            vector_result = vector_future.result()
            keyword_result = keyword_future.result()

        # 두 branch의 결과를 확인하고 keyword 실패 여부를 기록한다.
        parallel_latency = perf_counter() - retrieval_started
        vector_rows = vector_result["rows"]

        if keyword_result["error"]:
            machine_logger.warning(
                "Hybrid keyword branch failed; falling back to Vector candidates reason=%s",
                keyword_result["error"],
            )
        # Vector 순서를 먼저 보존하고 Keyword 후보를 뒤에 병합한다.
        # region [Python 설명] 후보 중복 제거와 metadata dict
        # `_chunk_identity(row)`가 row마다 같은 chunk를 가리키는 key를 만든다.
        # `rank_metadata`는 이 key로 Vector/Keyword 순위와 Keyword 점수를 보관한다.
        # `setdefault(key, {})`는 key가 처음이면 빈 dict를 만들고, 기존 dict가 있으면 재사용한다.
        # 후보 list에 같은 identity가 이미 있는지 확인해 원본 row를 한 번만 추가한다.
        # endregion
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

        # 병합된 후보를 reranking하고 선택된 순서와 검색 metadata를 구성한다.
        should_rerank = self.reranking_enabled if enable_reranking is None else bool(enable_reranking)
        rerank_started = perf_counter()
        if should_rerank and len(candidates) >= HYBRID_TOP_K:
            ranked, rerank_metadata = self.rerank_search_results(
                question, candidates, candidate_metadata=rank_metadata,
            )
        elif should_rerank and candidates:
            # 후보가 10개 미만일 때도 기존 reranker 호출 동작을 유지한다.
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

        # reranker 결과에 branch 순위, 검색어, 단계별 시간을 추가한다.
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
        """LLM 순위 응답을 검증해 원본 검색 row를 재배열한다.

        각 후보에 ID를 부여해 reranker에 전달하고, 반환된 ID가 원본 후보와 정확히
        일치하는지 확인한다. 응답이나 API 처리에 실패하면 입력 순서를 유지한다.
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

        # 모델이 사용할 후보 ID와 원본 row의 매핑을 만든다.
        # region [Python 설명] 후보 ID, dict mapping, metadata update
        # `enumerate(..., start=1)`은 후보마다 1부터 번호를 붙인다.
        # `candidate_rows`는 reranker가 돌려준 ID를 원본 DB row로 다시 찾는 dict다.
        # `candidate_metadata or {}`는 값이 없으면 빈 dict를 쓰며,
        # `.get(key, {})`는 순위 정보가 없을 때 빈 dict를 기본값으로 사용한다.
        # `mapping.update(...)`는 Vector/Keyword 순위 metadata를 기존 mapping에 합친다.
        # endregion
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

        # reranker 요청용 payload와 유효 후보 ID 집합을 만든다.
        payload = {"question": question, "candidates": prompt_candidates}
        expected_ids = {f"C{i:02d}" for i in range(1, len(vector_rows) + 1)}
        total_started = perf_counter()
        last_error = None
        reranker = self.reranker_model
        if len(vector_rows) > 10:
            # 후보가 10개를 넘으면 completion budget만 늘리고 모델과 응답 형식은 유지한다.
            base_model = getattr(self.reranker_model, "bound", None)
            if base_model is not None:
                reranker = base_model.bind(
                    max_completion_tokens=HYBRID_RERANK_COMPLETION_TOKENS
                ).bind(response_format={"type": "json_object"})

        # reranker 응답을 파싱하고 후보 ID·점수 순서를 검증한다.
        # region [Python 설명] list/set comprehension과 zip()
        # `[...]` comprehension은 ranking에서 ID와 점수를 각각 새 list로 만든다.
        # `{...}` comprehension은 예상 ID를 중복 없는 set으로 만든다.
        # `zip(scores, scores[1:])`는 이웃한 점수 쌍을 만들어 내림차순인지 확인한다.
        # endregion
        for attempt in range(RERANKER_MAX_RETRIES + 1):
            metadata["request_count"] += 1
            try:
                # 완성한 후보 payload를 reranker에 전달한다.
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

                # 순위 배열에 원본 후보 ID가 정확히 한 번씩 있는지 확인한다.
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

                # reranker가 정한 순서대로 원본 DB row를 다시 배치한다.
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
        """검색 결과의 차량과 page에 해당하는 이미지 중 관련도 높은 항목을 선택한다.

        검색 row에서 차량 ID와 page 번호를 모아 Repository로 이미지 후보를 조회한 뒤,
        image relevance 함수에 검색 결과와 함께 전달한다.
        """
        # row 목록을 안정적인 tuple로 만들고 조회 대상 차량/page를 모은다.
        # region [Python 설명] tuple·set comprehension과 dict.get()
        # `(search_results or ())`는 검색 결과가 없을 때 빈 tuple을 사용한다.
        # `{... for ... if ...}`는 중복을 제거하면서 조건에 맞는 차량 ID/page만 모은다.
        # 중첩 `.get()`은 DB row의 camelCase 또는 snake_case key를 순서대로 확인한다.
        # endregion
        rows = tuple(search_results or ())
        car_ids = {row.get("carId", row.get("car_id")) for row in rows if row.get("carId", row.get("car_id"))}
        if len(car_ids) != 1:
            return []
        pages = {row.get("carManualChunkPageNo", row.get("car_manual_chunk_page_no")) for row in rows if row.get("carManualChunkPageNo", row.get("car_manual_chunk_page_no")) is not None}

        # 최종 검색 page에 속한 이미지 후보를 조회한다.
        candidates = self.repository.search_images_by_pages(next(iter(car_ids)), pages)

        # 조회된 후보 중 질문과 관련된 이미지만 선택한다.
        return select_relevant_images(question, rows, candidates, limit=limit)

    # =========================================================
    # 이미지 선택 및 답변 생성
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
        """검색 chunk와 대화 이력으로 context를 만들고 최종 답변을 생성한다.

        검색 결과가 없으면 안내 답변을 반환한다. 결과가 있으면 chunk와 이전 대화를
        prompt 입력으로 구성한 뒤, stream writer가 있으면 답변 조각을 전달한다.
        """
        if not search_docs:
            # 검색 결과가 없으면 같은 답변을 반환하고 streaming 경로에도 전달한다.
            answer = "관련된 차량 매뉴얼 내용을 찾지 못했습니다."
            if stream_writer is not None:
                stream_writer({"type": "answer_token", "text": answer})
            return answer

        # 검색 row마다 prompt에 넣을 문서 context를 만든다.
        context_list = []

        for index, doc in enumerate(search_docs, start=1):

            # 원본 page/text와 선택된 이미지 URL을 context 한 항목으로 묶는다.
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

        # 여러 검색 문서를 줄바꿈으로 연결한다.
        context = "\n".join(context_list)

        # 이전 대화를 prompt에 전달할 문자열로 만든다.
        if conversation_history:
            recent_messages = conversation_history

            # role/content를 한 줄씩 연결해 대화 순서를 유지한다.
            # region [Python 설명] list comprehension과 truthy 검사
            # `if conversation_history`는 빈 list/None이면 거짓으로 평가된다.
            # comprehension은 각 message dict에서 role과 content를 골라 문자열 list를 만든다.
            # endregion
            history_text = "\n".join(
                [
                    f"{message['role']}: {message['content']}"
                    for message in recent_messages
                ]
            )

        else:
            history_text = "없음"

        # 질문·이력·검색 context를 prompt 입력 dict로 구성한다.
        inputs = {
            "history": history_text,
            "question": question,
            "context": context,
        }

        # stream writer가 있으면 답변 chunk 전달 경로를 사용한다.
        if stream_writer is not None:
            return self._stream_manual_answer(inputs, stream_writer, stream_timing)

        # 일반 호출에서는 완성된 답변 문자열을 한 번에 반환한다.
        answer = self.manual_answer_chain.invoke(inputs)

        return answer

    def _stream_manual_answer(self, inputs, stream_writer, stream_timing):
        """LangChain 답변 iterator를 소비해 chunk를 전달하고 전체 문자열을 반환한다.

        첫 chunk 시각으로 TTFT를 계산하고, 성공 또는 오류 여부와 관계없이 생성 시간을 기록한다.
        이미 보낸 chunk도 `answer_chunks`에 누적해 종료 후 완성 답변 문자열을 만든다.
        """
        # 호출 측에서 timing 정보가 없으면 빈 dict로 측정을 시작한다.
        # region [Python 설명] `(value or {})`와 dict.get()
        # `stream_timing or {}`는 None 또는 빈 dict일 때 새 빈 dict를 사용한다.
        # `.get(key, default)`는 선택 입력이 없을 때 기본 측정값을 돌려준다.
        # endregion
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

        # LangChain이 만든 답변 chunk를 받아 UI에 전달한다.
        # region [LangChain 설명] stream()과 iterator
        # `manual_answer_chain.stream(inputs)`는 답변이 만들어질 때마다 chunk를 순서대로 낸다.
        # `for`가 iterator를 하나씩 소비하므로 첫 chunk를 받은 즉시 stream writer에 보낼 수 있다.
        # 각 chunk는 전체 답변 복원을 위해 list에도 쌓는다.
        # endregion

        # 오류는 호출자에게 전파하고, 완료 시간은 성공/실패 모두 기록한다.
        # region [Python 설명] try/except/finally와 bare raise
        # `except`는 streaming 중 발생한 오류를 기록한다.
        # `raise`만 쓰면 현재 처리 중인 같은 예외를 호출자에게 다시 전달한다.
        # `finally`는 정상 종료와 예외 발생 모두에서 실행된다.
        # endregion
        try:
            for chunk in self.manual_answer_chain.stream(inputs):
                if not chunk:
                    continue
                text = chunk if isinstance(chunk, str) else str(chunk)

                # 처음 도착한 chunk만 기록해 generation 시작부터의 TTFT를 계산한다.
                if first_token_at is None:
                    first_token_at = perf_counter()
                    machine_logger.info(
                        "answer_first_token ttft_ms=%.1f",
                        (first_token_at - generation_started) * 1000,
                    )
                # chunk를 전체 답변에 누적하고 caller의 stream writer로 전달한다.
                answer_chunks.append(text)
                stream_writer({"type": "answer_token", "text": text})

        # streaming 오류는 기록한 뒤 호출 측으로 다시 전달한다.
        except Exception:
            machine_logger.exception("manual answer streaming failed")
            raise

        # 정상 종료와 예외 모두에서 생성 시간 및 TTFT를 기록한다.
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
        # 누적한 chunk를 하나의 답변 문자열로 반환한다.
        return "".join(answer_chunks)

    # =========================================================
    # 답변 API 및 검색 질문 재작성
    # =========================================================
    def ask_manual(self, car_brand_eng_nm, car_eng_nm, car_model_yr, question, conversation_history=None, limit=5):
        """기존 호출부와 호환되도록 매뉴얼 답변 문자열만 반환한다."""
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
        """질문 재작성부터 검색·답변 생성을 실행하고 원본 검색 row를 함께 반환한다.

        처리 흐름:
        1. 이전 대화를 참고해 독립적인 검색 질문을 만든다.
        2. Hybrid/Vector 검색과 설정된 reranking을 완료한다.
        3. 확정된 검색 결과로 답변을 생성하거나 stream writer에 전달한다.
        4. 답변 문자열과 검색 원본 row를 `ManualSearchAnswer`로 반환한다.
        """

        # 이전 대화 맥락을 반영해 검색에 사용할 질문을 준비한다.
        total_started = perf_counter()
        search_question = self.rewrite_search_question(
            question=question,
            conversation_history=conversation_history
        )

        # 재작성된 질문으로 검색과 reranking을 완료한다.
        retrieval_started = perf_counter()
        search_docs = self.search_manual(
            car_brand_eng_nm=car_brand_eng_nm,
            car_eng_nm=car_eng_nm,
            car_model_yr=car_model_yr,
            question=search_question,
            limit=limit
        )

        # retrieval/rerank 완료 시각을 기록한 뒤 최종 답변 생성을 시작한다.
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

        # 검색 결과와 대화 이력을 답변 생성 단계에 전달한다.
        answer = self.generate_manual_answer(
            question=question,
            search_docs=search_docs,
            conversation_history=conversation_history,
            stream_writer=stream_writer,
            stream_timing=stream_timing,
        )

        # 답변과 이번 검색에서 사용한 원본 row를 결과 객체로 묶는다.
        return ManualSearchAnswer(
            answer=answer,
            search_results=tuple(search_docs or ()),
        )

    def rewrite_search_question(self, question, conversation_history=None ):
        """이전 대화를 참고해 현재 질문을 독립적으로 이해할 검색 문장으로 바꾼다."""

        # 이전 대화가 없으면 재작성 없이 현재 질문을 사용한다.
        machine_logger.info(
            "rewrite_search_question input - question=%r, conversation_history=%r",
            question,
            conversation_history,
        )
        if not conversation_history:
            return question

        # 이전 대화의 role/content를 LLM 입력 문자열로 연결한다.
        recent_messages = conversation_history              # 메시지 누적

        # 각 dict의 role과 content를 대화 순서대로 한 줄씩 만든다.
        # region [Python 설명] list comprehension과 dict 접근
        # comprehension은 history의 각 dict에서 `role`, `content`를 읽어 문자열을 만든다.
        # 대괄호 key 접근은 key가 없는 경우 KeyError를 내므로 입력 메시지 형식을 전제로 한다.
        # endregion
        history_text = "\n".join(
            [
                f"{message['role']}: {message['content']}"
                for message in recent_messages
            ]
        )

        # 재작성 chain에 이전 대화와 현재 질문을 전달한다.
        search_question = self.rewrite_search_chain.invoke(
            {
                "history": history_text,
                "question": question
            }
        )

        # LLM 출력 앞뒤의 공백을 정리해 검색 질문으로 반환한다.
        return search_question.strip()
