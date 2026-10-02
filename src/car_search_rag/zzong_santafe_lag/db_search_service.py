"""질문 임베딩 → 저장된 청크 검색 → 원문·각주·그림 연결의 순서를 관리합니다."""

# [프로젝트 적용] 기존 로컬 모델과 SQL Mapper의 pgvector 코사인 검색을 재사용합니다.
# [프로젝트 추가] 표본 run_id로 범위를 제한하고 필수 문맥·그림 설명·공개 경로를 묶습니다.
# 표본은 의미 검색, 전체 검색은 의미 기준 또는 기존 TF-IDF·질문 목적 결합 검색을 사용합니다.
# 높은 점수도 정답 보장이 아닙니다. 답변 생성·근거 부족 판정은 이후 단계입니다.

import os
from pathlib import Path
from time import perf_counter
from urllib.parse import quote, urlparse

from dotenv import dotenv_values
from psycopg.conninfo import conninfo_to_dict

from .chunking import TokenCounter
from .config import ManualConfig, SAMPLE_RUN_ID, sample_image_storage_path
from .database import ManualRepository, PersonalDatabaseManager, PersonalSqlSession
from .embedding import LocalEmbedder
from .sample_store import APPROVED_MANIFEST, APPROVED_REVISION


class DbSampleSearchService:
    """저장된 부모 4개·청크 11개에서 근거를 찾는 읽기 전용 서비스입니다."""

    def __init__(self):
        """조회 세션만 준비합니다. 생성 시 모델·PDF·DB 자료를 읽거나 수정하지 않습니다."""
        self.repository = ManualRepository(PersonalSqlSession(read_only=True))
        self.run_id = SAMPLE_RUN_ID
        self.config = None
        self.run = None
        self.document = None
        self.counts = None
        self.token_counter = None
        self.embedder = None
        self.storage_url = None
        self.model_prepare_seconds = None
        self.max_results = 4
        self.best_per_parent = False
        self.search_method = "pgvector_cosine_only"
        self.excluded_heading_records = 0

    def validate_source(self, run, document, counts):
        """표본 범위와 저장 완료 여부를 확인합니다. 전체 검색은 별도 클래스가 확장합니다."""
        if document is None or run["status"] != "ready" or counts != {"parent_count": 4, "chunk_count": 11}:
            raise ValueError("이번 검색 대상은 저장 완료된 부모 4개·청크 11개의 표본입니다.")
        if run["settings"].get("input_manifest_sha256") != APPROVED_MANIFEST:
            raise ValueError("승인한 표본 입력과 다릅니다.")

    def coverage_notice(self):
        """현재 검색 범위를 설명합니다. 높은 점수를 근거 충분 판정으로 사용하지 않습니다."""
        return "현재는 PDF 43~45쪽의 일부 표본만 검색합니다. 높은 점수도 정답 보장이 아니며 근거 부족 판정은 아직 없습니다."

    def prepare(self, progress=None):
        """저장 버전을 확인하고 같은 로컬 모델을 한 번 준비합니다. 문서 임베딩은 하지 않습니다."""
        if self.embedder is not None:
            return self
        with self.repository.session.transaction():
            run = self.repository.session.select_one("manual_store.get_run", {"run_id": self.run_id})
            counts = self.repository.session.select_one("manual_store.get_run_search_counts", {"run_id": self.run_id})
            if run is None:
                raise ValueError("저장된 개인 표본 작업이 없습니다.")
            document = self.repository.session.select_one("manual_store.get_document", {"document_id": run["document_id"]})
        self.validate_source(run, document, counts)
        if (run["model_name"], run["model_revision"]) != (ManualConfig().model_name, APPROVED_REVISION):
            raise ValueError("현재 로컬 모델과 저장한 모델 버전이 다릅니다.")
        config = ManualConfig(model_name=run["model_name"], model_revision=run["model_revision"])
        started = perf_counter()
        if progress:
            progress("DB 검색 범위 확인 완료 → 저장 당시의 로컬 모델 준비")
        counter = TokenCounter(config.model_name, revision=config.model_revision)
        embedder = LocalEmbedder(config, counter)
        if run["token_budget"] != counter.budget or run["embedding_dimension"] != embedder.dimension or not run["normalized"]:
            raise ValueError("저장한 토큰 한도·차원·정규화 설정이 모델과 다릅니다.")
        # [프로젝트 추가] 그림 공개 URL에는 비밀키가 필요 없습니다. 같은 프로젝트 주소만 읽습니다.
        values = dict(dotenv_values(config.project_folder / ".env"))
        values.update(dotenv_values(Path(__file__).resolve().parent / ".env"))
        storage_url = os.environ.get("SUPABASE_URL") or values.get("SUPABASE_URL")
        if storage_url:
            parsed = urlparse(storage_url)
            host = parsed.hostname or ""
            project_ref = host.split(".")[0] if host.endswith(".supabase.co") else ""
            info = conninfo_to_dict(PersonalDatabaseManager(read_only=True)._dsn)
            same_project = project_ref and (info.get("host") == f"db.{project_ref}.supabase.co" or info.get("user", "").endswith("." + project_ref))
            if parsed.scheme != "https" or not same_project:
                raise ValueError("그림 주소와 개인 DB의 Supabase 프로젝트가 다릅니다.")
            storage_url = f"https://{host}"
        self.config, self.run, self.document, self.counts = config, run, document, counts
        self.token_counter, self.embedder, self.storage_url = counter, embedder, storage_url
        self.model_prepare_seconds = perf_counter() - started
        return self

    @staticmethod
    def read_context(parent_record_id, parents):
        """필수 각주·주의사항을 연결합니다. 서로 참조하는 기록도 한 번씩만 읽습니다."""
        records, visited = [], set()

        def visit(record_id):
            """방문한 기록을 기억하고 같은 작업의 필수 연결을 따라갑니다."""
            if record_id in visited:
                return
            parent = parents.get(record_id)
            if parent is None:
                raise ValueError("함께 읽어야 하는 원문이 저장된 표본에 없습니다.")
            visited.add(record_id)
            records.append(parent)
            for linked_id in parent["metadata"].get("required_context_record_ids", []):
                visit(linked_id)

        visit(parent_record_id)
        return records

    def image_details(self, context, images):
        """검색한 주제들의 그림을 설명과 연결합니다. 그림 파일을 다운로드·업로드하지 않습니다."""
        record_ids = {row["record_id"] for row in context}
        parts = {}
        for image in images:
            if image["parent_record_id"] not in record_ids:
                continue
            image_id = str(image["id"])
            if image_id not in parts:
                public_url = None
                if image["upload_status"] == "uploaded":
                    expected_path = sample_image_storage_path(self.document["file_sha256"],
                                                             image["pdf_page_number"], image["file_name"])
                    if image["storage_bucket"] != "images" or image["storage_path"] != expected_path:
                        raise ValueError("검색 결과의 그림이 개인 표본 Storage 경로와 다릅니다.")
                    if self.storage_url:
                        public_url = f'{self.storage_url}/storage/v1/object/public/images/{quote(expected_path, safe="/")}'
                parts[image_id] = {
                    "pdf_page_number": image["pdf_page_number"], "file_name": image["file_name"],
                    "pdf_image_key": image["pdf_image_key"], "image_key_sha256": image["image_key_sha256"],
                    "width": image["width"], "height": image["height"],
                    "local_path": image["local_path"], "storage_bucket": image["storage_bucket"],
                    "storage_path": image["storage_path"], "upload_status": image["upload_status"],
                    "public_url": public_url, "descriptions": [],
                }
            # 같은 그림이 여러 주제에 연결돼 있어도 각 설명·검토 상태는 보존합니다.
            parts[image_id]["descriptions"].append({"parent_record_id": image["parent_record_id"],
                "description": image["description"], "linkage_status": image["linkage_status"]})
        return list(parts.values())

    def query_rows(self, question, vector):
        """같은 작업의 검색 청크·전체 문맥·그림 연결을 읽습니다. 호출한 읽기 전용 거래 안에서 실행합니다."""
        hits = self.repository.search_chunks(self.run_id, vector,
            model_name=self.embedder.model_name, model_revision=self.embedder.model_revision,
            limit=self.counts["parent_count"] if self.best_per_parent else self.counts["chunk_count"],
            best_per_parent=self.best_per_parent)
        rows = self.repository.session.select_list("manual_store.get_run_parents", {"run_id": self.run_id})
        images = self.repository.session.select_list("manual_store.get_run_image_details", {"run_id": self.run_id})
        return hits, rows, images

    def search(self, question, top_k=3, progress=None):
        """질문만 임베딩해 DB 청크를 찾고 중복 원문·필수 문맥·그림을 묶어 반환합니다."""
        if not isinstance(question, str) or not question.strip():
            raise ValueError("검색할 질문을 입력하세요.")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= self.max_results:
            raise ValueError(f"결과 묶음 수는 1~{self.max_results} 사이로 입력하세요.")
        question = question.strip()
        self.prepare(progress=progress)
        started = perf_counter()
        vector = self.embedder.embed_question(question)
        if progress:
            progress("질문 임베딩 완료 → 저장된 청크에서 검색·원문 연결")
        with self.repository.session.transaction():
            # [프로젝트 적용] 같은 run_id·모델 버전의 벡터만 비교합니다. 조회 연결은 읽기 전용입니다.
            hits, rows, images = self.query_rows(question, vector)
        parents = {row["record_id"]: row for row in rows}
        candidates, seen_contexts = [], set()
        for hit in hits:
            context = self.read_context(hit["parent_record_id"], parents)
            identity = tuple(sorted(row["record_id"] for row in context))
            # [프로젝트 추가] 여러 청크가 같은 원문·각주 묶음을 가리키면 가장 높은 후보만 남깁니다.
            if identity in seen_contexts:
                continue
            seen_contexts.add(identity)
            pending = [row["record_id"] for row in context if row["verification_status"] == "auto_draft_needs_review"]
            continuations = sorted({name for row in context for name in row["metadata"].get("unreviewed_continuation_record_ids", [])})
            candidates.append({
                "rank": len(candidates) + 1, "title": hit["title"], "similarity": float(hit["similarity"]),
                "ranking_score": float(hit.get("ranking_score", hit["similarity"])),
                "routing": hit.get("routing"), "used_fallback": hit.get("used_fallback", False),
                "specific_bonus": float(hit.get("specific_bonus", 0.0)),
                "specific_terms": hit.get("specific_terms", []),
                "matched_chunk_record_id": hit["chunk_record_id"], "matched_chunk": hit["chunk_content"],
                "parent_record_id": hit["parent_record_id"],
                "context_records": [{key: row[key] for key in ("record_id", "title", "content", "raw_text",
                    "pdf_page_number", "manual_page_number", "source_pages", "content_type", "verification_status", "metadata")}
                    for row in context],
                "image_parts": self.image_details(context, images),
                "pending_review_record_ids": pending, "unreviewed_continuation_record_ids": continuations,
            })
            if len(candidates) >= top_k:
                break
        return {"question": question, "run_id": str(self.run_id), "read_only": True,
                "model_name": self.embedder.model_name, "model_revision": self.embedder.model_revision,
                "query_token_count": self.token_counter.count(question), "query_vector_shape": list(vector.shape),
                "document_embeddings_recomputed": False, "db_written": False, "storage_uploaded": False,
                "search_method": self.search_method, "source_counts": self.counts,
                "excluded_heading_records": self.excluded_heading_records,
                "model_prepare_seconds": self.model_prepare_seconds, "query_search_seconds": perf_counter() - started,
                "candidates": candidates, "answer_generation_status": "not_implemented",
                "coverage_notice": self.coverage_notice()}


class DbFullSearchService(DbSampleSearchService):
    """지정한 전체 저장 작업만 검색합니다. 표본과 다른 모델의 벡터는 섞지 않습니다."""

    def __init__(self, run_id, method="purpose"):
        """전체 저장 결과의 run_id를 받습니다. 최신 작업을 임의로 선택하지 않습니다."""
        from uuid import UUID
        super().__init__()
        self.run_id = UUID(str(run_id))
        self.max_results = 10
        self.best_per_parent = True
        if method not in {"semantic", "purpose", "purpose_specific"}:
            raise ValueError("검색 방식은 semantic, purpose 또는 purpose_specific입니다.")
        self.method = method
        self.search_method = "stored_vectors_keyword_purpose" if method == "purpose" else "pgvector_cosine_only"
        if method == "purpose_specific":
            self.search_method = "stored_vectors_keyword_purpose_specific_terms_v1"

    def query_rows(self, question, vector):
        """의미 검색을 기준으로 남기고, 기본값은 기존 글자·목적 검색을 저장 벡터에 적용합니다."""
        if self.method == "semantic":
            return super().query_rows(question, vector)
        import re
        import numpy as np
        from .retrieval import SearchEngine

        # [프로젝트 적용] 같은 읽기 전용 거래에서 저장된 글·벡터·연결을 함께 가져옵니다.
        # 부모/청크를 새로 만들거나 임베딩하지 않습니다. 기존 12번 실험의 검색 규칙을 재사용합니다.
        run = self.repository.session.select_one("manual_store.get_run", {"run_id": self.run_id})
        counts = self.repository.session.select_one("manual_store.get_run_search_counts", {"run_id": self.run_id})
        if run is None:
            raise ValueError("전체 저장 작업이 없습니다.")
        self.validate_source(run, self.document, counts)
        if (run["model_name"], run["model_revision"]) != (self.embedder.model_name, self.embedder.model_revision):
            raise ValueError("질문과 저장한 벡터의 모델 버전이 다릅니다.")
        rows = self.repository.session.select_list("manual_store.get_run_parents", {"run_id": self.run_id})
        chunks = self.repository.session.select_list("manual_store.get_run_chunks", {"run_id": self.run_id})
        images = self.repository.session.select_list("manual_store.get_run_image_details", {"run_id": self.run_id})

        # [프로젝트 추가] 본문이 제목과 완전히 같은 항목은 답변 근거 후보에서 제외합니다.
        # 저장 원문은 유지합니다. 긴 글을 짧다는 이유로 제거하거나 주의사항을 요약하지 않습니다.
        def normalize_space(text):
            """제목과 본문 비교에서 공백·줄바꿈 차이만 줄입니다."""
            return re.sub(r"\s+", "", text)
        usable = [row for row in rows if normalize_space(row["content"]) != normalize_space(row["title"])]
        self.excluded_heading_records = len(rows) - len(usable)
        parent_ids = {row["record_id"] for row in usable}
        chunks = [row for row in chunks if row["metadata"]["parent_record_id"] in parent_ids]
        parents = [{"content": row["content"], "raw_text": row["raw_text"],
                    "metadata": row["metadata"], "image_parts": []} for row in usable]
        records = [{"content": row["content"], "metadata": row["metadata"]} for row in chunks]
        vectors = np.stack([row["embedding"] for row in chunks]).astype(np.float32)
        if vectors.shape != (len(chunks), self.embedder.dimension) or not np.isfinite(vectors).all():
            raise ValueError("저장한 벡터의 개수·차원·숫자가 올바르지 않습니다.")
        engine = SearchEngine(parents, records, vectors, self.embedder.model, self.token_counter)
        # 전체 순위를 받아 기존 각주 문맥 중복 제거 후 요청한 개수만 반환합니다.
        ranked = engine.rank(question, vector, top_k=len(parents), use_specific_terms=self.method == "purpose_specific")
        vector_by_id = {row["record_id"]: vectors[index] for index, row in enumerate(chunks)}
        hits = []
        for hit in ranked:
            parent = hit["parent_record"]["metadata"]
            chunk = hit["matched_chunk"]
            chunk_id = chunk["metadata"]["record_id"]
            hits.append({"title": parent["title"], "parent_record_id": parent["record_id"],
                "chunk_record_id": chunk_id, "chunk_content": chunk["content"],
                "similarity": float(vector_by_id[chunk_id] @ vector), "ranking_score": hit["score"],
                "routing": hit["routing"],
                "specific_bonus": hit["specific_bonus"], "specific_terms": hit["specific_terms"],
                # 전체 순위의 뒤쪽 보충 후보 때문에 앞쪽 목적 일치 후보까지 보충으로 표시하지 않습니다.
                "used_fallback": hit["used_fallback"] and (
                    hit["preferred_candidate_count"] == len(parents)
                    or len(hits) >= hit["preferred_candidate_count"])})
        return hits, rows, images

    def validate_source(self, run, document, counts):
        """현재 승인한 전체 버전·개수·입력 식별값을 모두 확인한 뒤 모델을 준비합니다."""
        from .full_store_service import PIPELINE_VERSION
        expected_manifest = "893151d66a49fab8f21060ee95e7917054ebb12753dc62eb4ead26cd52798a1b"
        if (document is None or run["status"] != "ready"
                or counts != {"parent_count": 527, "chunk_count": 2213}
                or run["pipeline_version"] != PIPELINE_VERSION
                or run["settings"].get("scope") != "full_manual"
                or run["settings"].get("input_manifest_sha256") != expected_manifest):
            raise ValueError("승인한 전체 자료의 저장 완료 상태·버전·개수가 다릅니다.")

    def coverage_notice(self):
        """전체 글 검색과 그림 업로드·검토 범위를 구별해 안내합니다."""
        return ("전체 부모 527개·청크 2,213개를 검색합니다. 자동 초안 507개는 원본 대조가 필요합니다. "
                "그림은 참조를 연결하며 공개 파일은 기존 3개입니다. 답변 생성·근거 부족 판정은 아직 없습니다.")
