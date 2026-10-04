import logging
import json
import os
import re
import time
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
machine_logger = logging.getLogger("car_search_rag.car_manual")

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
        """Run unchanged vector retrieval, then optionally rerank its exact rows."""
        query_vector = self.embedding_model.embed_query(question)
        vector_results = self.repository.search_manual(
            car_brand_eng_nm=car_brand_eng_nm,
            car_eng_nm=car_eng_nm,
            car_model_yr=car_model_yr,
            embedding=query_vector,
            limit=limit
        )
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
            return list(vector_results or ()), metadata

        return self.rerank_search_results(question, vector_results)

    def rerank_search_results(self, question, candidates):
        """Rerank ten retrieved rows, returning original rows and safe metadata.

        Any request, parse, or validation failure returns the original Vector
        order. Candidate IDs sent to the model are stable C01-C10 labels and are
        mapped back through a separate dictionary without modifying source rows.
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

        if len(vector_rows) != 10:
            metadata["fallback_reason"] = f"expected 10 vector candidates; got {len(vector_rows)}"
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
            metadata.setdefault("candidate_mapping", []).append({
                "candidate_id": candidate_id,
                "page_no": page_no,
                "chunk_id": chunk_id,
            })
            prompt_candidates.append({
                "candidate_id": candidate_id,
                "page_no": page_no,
                "chunk_id": chunk_id,
                "text": row.get("carManualChunkTxt", row.get("car_manual_chunk_txt", "")),
            })

        payload = {"question": question, "candidates": prompt_candidates}
        expected_ids = {f"C{i:02d}" for i in range(1, 11)}
        total_started = perf_counter()
        last_error = None

        for attempt in range(RERANKER_MAX_RETRIES + 1):
            metadata["request_count"] += 1
            try:
                response = self.reranker_model.invoke([
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
                if len(ids) != 10 or set(ids) != expected_ids or len(set(ids)) != 10:
                    raise ValueError("ranking must include C01-C10 exactly once")
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
    def generate_manual_answer(self,question,search_docs,conversation_history=None):
        
        if not search_docs:
            return "관련된 차량 매뉴얼 내용을 찾지 못했습니다."

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
        answer = self.manual_answer_chain.invoke(
            {
                "history": history_text,
                "question": question,
                "context": context
            }
        )

        return answer


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

    def ask_manual_with_sources(self, car_brand_eng_nm, car_eng_nm, car_model_yr, question, conversation_history=None, limit=5):
        """기존 검색/답변 경로를 실행하고 해당 호출의 검색 row를 함께 반환한다."""

        # =========================================================
        # 이전 대화 기반 검색 질문 재작성
        # =========================================================
        search_question = self.rewrite_search_question(
            question=question,
            conversation_history=conversation_history
        )


        # =========================================================
        # 차량 매뉴얼 검색
        # =========================================================
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
        answer = self.generate_manual_answer(
            question=question,
            search_docs=search_docs,
            conversation_history=conversation_history
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
