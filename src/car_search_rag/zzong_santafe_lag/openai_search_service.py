"""새 OpenAI 벡터를 검색하되 기존 부모 문맥·출처·그림 검토 규칙은 재사용합니다."""

import json
import hashlib
from time import perf_counter
from uuid import UUID

from .config import ManualConfig
from .db_search_service import DbFullSearchService
from .openai_embedding import MODEL, DIMENSION, RECIPE, OpenAIEmbedder, OpenAITokenCounter
from .openai_migration import SOURCE_RUN_ID, OUTPUT_FOLDER
from .search_support import checked_storage_url, rank_stored_rows
from .source_profile import FULL_SOURCE


def active_embedding_run():
    """개인 기본 선택 파일을 읽습니다. API·DB 호출은 하지 않으며 잘못된 값은 조용히 대체하지 않습니다."""
    path = OUTPUT_FOLDER / "active_run.json"
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if (value["source_run_id"] != str(SOURCE_RUN_ID) or value["model"] != MODEL
            or value["dimension"] != DIMENSION):
        raise ValueError("기본 선택 파일의 문서·모델·차원을 확인하세요.")
    return UUID(value["embedding_run_id"])


class OpenAIManualSearchService(DbFullSearchService):
    """문서·질문 모두 같은 OpenAI 모델의 1536차원으로 비교합니다."""

    def __init__(self, embedding_run_id, method="purpose_specific"):
        """기존 원문 작업과 새 벡터 작업을 별도로 고정합니다. 생성만으로 API를 부르지 않습니다."""
        super().__init__(SOURCE_RUN_ID, method=method)
        self.embedding_run_id = UUID(str(embedding_run_id))
        self.search_method = "openai_1536_" + method

    def check_embedding_run(self, row):
        """API 모델 이름·차원·처리 설정·완료 상태가 모두 일치하는지 확인합니다."""
        if (row is None or row["status"] != "ready" or row["source_run_id"] != self.run_id
                or row["model_name"] != MODEL or row["embedding_dimension"] != DIMENSION
                or row["recipe"] != RECIPE or row["chunk_count"] != FULL_SOURCE.chunk_count
                or row["settings"].get("normalized") is not True):
            raise ValueError("동일한 OpenAI 임베딩 버전의 저장 완료 상태가 아닙니다.")

    def prepare(self, progress=None):
        """새 벡터 버전을 읽고 API 연결만 준비합니다. 로컬 모델 다운로드·문서 재임베딩은 없습니다."""
        if self.embedder is not None:
            return self
        started = perf_counter()
        session = self.repository.session
        with session.transaction():
            run = session.select_one("manual_store.get_run", {"run_id": self.run_id})
            counts = session.select_one("manual_store.get_run_search_counts", {"run_id": self.run_id})
            if run is None:
                raise ValueError("원문 작업이 없습니다.")
            document = session.select_one("manual_store.get_document", {"document_id": run["document_id"]})
            self.validate_source(run, document, counts)
            embedding_run = session.select_one("openai_vectors.get_run", {"embedding_run_id": self.embedding_run_id})
            self.check_embedding_run(embedding_run)
        # [프로젝트 적용] 기존 그림 URL 검사와 같은 방식으로 개인 DB와 Storage 프로젝트가 같은지 확인합니다.
        config = ManualConfig()
        storage_url = checked_storage_url(config)
        self.token_counter = OpenAITokenCounter()
        self.embedder = OpenAIEmbedder(self.token_counter)
        self.config, self.run, self.document, self.counts = config, run, document, counts
        self.storage_url = storage_url
        self.model_prepare_seconds = perf_counter() - started
        if progress:
            progress("OpenAI 벡터 저장 버전 확인 완료 → 질문만 API로 임베딩")
        return self

    def query_rows(self, question, vector):
        """원문은 기존 테이블, 벡터는 새 테이블에서 읽고 동일한 검색 규칙을 적용합니다."""
        session = self.repository.session
        params = {"run_id": self.run_id}
        embedding_params = {"embedding_run_id": self.embedding_run_id}
        self.check_embedding_run(session.select_one("openai_vectors.get_run", embedding_params))
        rows = session.select_list("manual_store.get_run_parents", params)
        chunks = session.select_list("openai_vectors.get_vectors", embedding_params)
        images = session.select_list("manual_store.get_run_image_details", params)
        if len(chunks) != FULL_SOURCE.chunk_count or any(
                row["input_sha256"] != row["content_sha256"]
                or hashlib.sha256(row["content"].encode("utf-8")).hexdigest() != row["input_sha256"]
                for row in chunks):
            raise ValueError("새 벡터의 입력 글 또는 개수가 저장 당시와 다릅니다.")
        from .review_revision import load_active, combine
        bundle = getattr(self, "review_bundle", None) or load_active(session)
        rows, chunks, images = combine(bundle, rows, chunks, images, "openai")
        self.review_revision_id = bundle["revision_id"] if bundle else None
        self.effective_chunk_count = len(chunks)
        self.effective_pending_count = sum(row["verification_status"] == "auto_draft_needs_review" for row in rows)
        # [프로젝트 추가] 로컬/OpenAI의 공통 정렬 흐름을 사용하고 OpenAI 벡터의 정규화도 확인합니다.
        hits, self.excluded_heading_records = rank_stored_rows(
            question, vector, rows, chunks, self.embedder, self.token_counter, self.method,
            require_normalized=True)
        return hits, rows, images

    def search(self, question, top_k=3, progress=None):
        """기존 출처·그림 연결을 유지하면서 결과에 새 벡터 버전을 기록합니다."""
        result = super().search(question, top_k=top_k, progress=progress)
        result.update(embedding_run_id=str(self.embedding_run_id), query_embedding_api_called=True,
                      model_revision_kind="application_recipe_not_server_snapshot",
                      review_revision_id=getattr(self, "review_revision_id", None),
                      effective_chunk_count=getattr(self, "effective_chunk_count", FULL_SOURCE.chunk_count))
        return result

    def coverage_notice(self):
        """검색 범위와 미검토 자료의 상태를 구별합니다."""
        return (f"기존 부모 {FULL_SOURCE.parent_count:,}개·청크 {FULL_SOURCE.chunk_count:,}개를 OpenAI 벡터로 검색합니다. "
                f"기본 자료와 별도 검토 버전을 대조하며 자동 초안 {getattr(self, 'effective_pending_count', 507)}개는 원본 대조가 필요합니다.")
