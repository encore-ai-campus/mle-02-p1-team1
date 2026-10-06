"""전체 글·벡터·그림 참조의 미리보기, 임베딩, 승인 후 저장 순서를 관리합니다."""

# [프로젝트 적용] 기존 PDF 처리·로컬 모델·SQL Mapper·트랜잭션을 재사용합니다.
# [프로젝트 추가] 기존 PDF·그림은 재사용하고 전체 자료는 새 run_id로 구분합니다.
# prepare는 읽기 전용, embed는 메모리 계산, save는 승인 식별값을 확인한 뒤 DB에 씁니다.
# 그림 파일 업로드·테이블 생성·기존 원문 변경은 이 서비스에 포함하지 않습니다.

import json
from copy import deepcopy
from time import perf_counter
from uuid import uuid4

import numpy as np

from .config import ManualConfig
from .database import ManualRepository, PersonalSqlSession
from .db_rows import RowPreview, file_sha256, sha256_text
from .embedding import LocalEmbedder
from .manual_service import ManualService
from .sample_embedding import validate_sample_rows
from .sample_store import APPROVED_REVISION, json_value, load_sample_bundle
from .storage_plan import image_identity


from .source_profile import PIPELINE_VERSION
IMAGE_FIELDS = ("pdf_page_number", "pdf_image_key", "image_key_sha256", "file_name", "width", "height",
                "local_path", "storage_bucket", "storage_path", "upload_status")


def validate_full_rows(preview, service, require_vectors=False):
    """기존 행 검증에 전체 누락·컬럼 일치·그림 키·개인 경로 검사를 추가합니다."""
    # [프로젝트 적용] 표본 때 사용한 검증도 PDF/작업 1개를 전제로 전체 목록에 재사용할 수 있습니다.
    validate_sample_rows(preview, service, require_vectors=require_vectors)
    tables = preview.tables
    source_parents = {row["metadata"]["record_id"]: row for row in service.parents}
    source_chunks = {row["metadata"]["record_id"]: row for row in service.chunks}
    if (len(tables["parent_records"]) != len(source_parents)
            or {row["record_id"] for row in tables["parent_records"]} != set(source_parents)
            or len(tables["chunks"]) != len(source_chunks)
            or {row["record_id"] for row in tables["chunks"]} != set(source_chunks)):
        raise ValueError("전체 원문 또는 청크가 누락됐습니다.")
    parents = {row["id"]: row for row in tables["parent_records"]}
    for row in parents.values():
        meta = source_parents[row["record_id"]]["metadata"]
        for field in ("title", "pdf_page_number", "manual_page_number", "source_pages", "content_type", "verification_status"):
            if row[field] != meta[field]:
                raise ValueError("부모 컬럼과 원래 출처 정보가 다릅니다.")
        if row["review_flags"] != meta.get("review_flags", []):
            raise ValueError("원래 검토 표시가 바뀌었습니다.")
    for row in tables["chunks"]:
        original = source_chunks[row["record_id"]]
        if (row["content"] != original["content"] or row["metadata"] != original["metadata"]
                or parents[row["parent_id"]]["record_id"] != original["metadata"]["parent_record_id"]):
            raise ValueError("전체 청크가 원래 글·출처·부모 연결과 다릅니다.")
    image_keys = set()
    document_sha = tables["documents"][0]["file_sha256"]
    image_root = (service.config.project_folder / "data/zzong_santafe_lag/images").resolve()
    for row in tables["images"]:
        key_text = json.dumps(row["pdf_image_key"], ensure_ascii=False, separators=(",", ":"))
        identity = row["pdf_page_number"], row["image_key_sha256"]
        if sha256_text(key_text) != row["image_key_sha256"] or identity in image_keys:
            raise ValueError("전체 그림 내부 키가 변경되거나 중복됐습니다.")
        image_keys.add(identity)
        if row["local_path"]:
            path = (service.config.project_folder / row["local_path"]).resolve()
            if not path.is_relative_to(image_root) or not path.is_file():
                raise ValueError("기존 로컬 그림이 개인 이미지 경로에 없습니다.")
        if row["upload_status"] == "uploaded":
            path = row["storage_path"] or ""
            prefix = f"cars/hyundai/santafe_hev/zzong_santafe_lag/{document_sha}/"
            if row["storage_bucket"] != "images" or not path.startswith(prefix) or ".." in path.split("/"):
                raise ValueError("재사용할 그림 주소가 개인 PDF 경로가 아닙니다.")


def input_manifest(tables):
    """UUID·계산 시간을 제외한 원문·청크·그림 연결 전체의 내용 식별값을 만듭니다."""
    # [프로젝트 추가] 승인 범위는 청크 글뿐 아니라 각주·그림 설명·검토 상태도 포함합니다.
    parents = {row["id"]: row["record_id"] for row in tables["parent_records"]}
    images = {row["id"]: (row["pdf_page_number"], row["image_key_sha256"]) for row in tables["images"]}
    run = tables["processing_runs"][0]
    payload = {
        "pdf_sha256": tables["documents"][0]["file_sha256"],
        "pipeline_version": run["pipeline_version"],
        "model": [run["model_name"], run["model_revision"], run["embedding_dimension"], run["token_budget"], run["normalized"]],
        "parents": [{key: value for key, value in row.items() if key not in {"id", "run_id", "document_id"}}
                    for row in sorted(tables["parent_records"], key=lambda row: row["record_id"])],
        "chunks": [{key: row[key] for key in ("record_id", "chunk_index", "content", "content_sha256", "token_count",
                    "parent_content_start", "parent_content_end", "metadata")}
                   for row in sorted(tables["chunks"], key=lambda row: row["record_id"])],
        "images": [{key: row[key] for key in IMAGE_FIELDS} for row in sorted(tables["images"],
                    key=lambda row: (row["pdf_page_number"], row["image_key_sha256"]))],
        "links": [{"parent": parents[row["parent_id"]], "image": images[row["image_id"]],
                   "description": row["description"], "linkage_status": row["linkage_status"], "metadata": row["metadata"]}
                  for row in sorted(tables["record_images"], key=lambda row: (parents[row["parent_id"]], images[row["image_id"]]))],
    }
    return sha256_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def compare_full_bundle(preview, stored, require_ready=False):
    """DB에서 읽은 모든 입력 필드·벡터를 비교합니다. 재실행의 새 UUID는 실제 번호에 대응합니다."""
    expected = preview.tables
    if {name: len(rows) for name, rows in stored.items()} != {name: len(rows) for name, rows in expected.items()}:
        raise ValueError("전체 저장 건수가 준비한 범위와 다릅니다.")
    replacements = {expected["documents"][0]["id"]: stored["documents"][0]["id"],
                    expected["processing_runs"][0]["id"]: stored["processing_runs"][0]["id"]}
    for table in ("parent_records", "chunks", "images"):
        def identity(row):
            """UUID 대신 해당 목록 안에서 고유한 논리 식별자를 사용합니다."""
            return (row["pdf_page_number"], row["image_key_sha256"]) if table == "images" else row["record_id"]
        actual_by_key = {identity(row): row for row in stored[table]}
        if len(actual_by_key) != len(stored[table]):
            raise ValueError("저장된 기록 식별자가 중복되었습니다.")
        for row in expected[table]:
            target = actual_by_key.get(identity(row))
            if target is None:
                raise ValueError("저장된 기록 식별자가 다릅니다.")
            replacements[row["id"]] = target["id"]
    for table, rows in expected.items():
        actual_by_id = {((row["parent_id"], row["image_id"]) if table == "record_images" else row["id"]): row
                        for row in stored[table]}
        for row in rows:
            values = {key: replacements[value] if key in {"id", "document_id", "run_id", "parent_id", "image_id"}
                      else value for key, value in row.items()}
            identity = (values["parent_id"], values["image_id"]) if table == "record_images" else values["id"]
            actual = actual_by_id.get(identity)
            if actual is None:
                raise ValueError("저장된 행의 연결 번호가 다릅니다.")
            for key, value in values.items():
                if key == "embedding":
                    if not np.array_equal(np.asarray(value, dtype=np.float32), actual[key]):
                        raise ValueError("저장된 전체 벡터가 계산한 값과 다릅니다.")
                elif key == "settings":
                    for setting, setting_value in value.items():
                        if setting != "embedding_validation" and json_value(actual[key].get(setting)) != json_value(setting_value):
                            raise ValueError("저장된 전체 처리 설정이 다릅니다.")
                elif json_value(actual[key]) != json_value(value):
                    raise ValueError(f"저장된 전체 입력 필드가 다릅니다: {table}.{key}")
    if require_ready and stored["processing_runs"][0]["status"] != "ready":
        raise ValueError("전체 저장 완료 상태가 아닙니다.")
    return {"all_fields_match": True, "vectors_exact_match": True,
            "run_id": str(stored["processing_runs"][0]["id"])}


class FullManualStoreService:
    """전체 자료를 새 작업으로 준비하고, 승인된 내용만 개인 DB에 저장하는 서비스입니다."""

    def __init__(self):
        """설정만 준비합니다. 생성만으로 PDF·모델·DB를 읽거나 저장하지 않습니다."""
        self.service = ManualService(ManualConfig(model_revision=APPROVED_REVISION))
        self.preview = None
        self.existing_image_ids = set()
        self.db_snapshot = None

    def prepare(self, progress=print):
        """전체 행을 메모리에 만듭니다. 기존 PDF·그림을 조회하며 새 벡터는 None으로 둡니다."""
        if self.preview is not None:
            return self
        self.service.prepare(progress=progress)
        reader = ManualRepository(PersonalSqlSession(read_only=True))
        with reader.session.transaction():
            document = reader.session.select_one("manual_store.find_document", {
                "file_sha256": file_sha256(self.service.config.pdf_path)})
            if document is None:
                raise ValueError("전체 저장은 이미 등록한 개인 PDF 정보를 재사용하는 범위입니다.")
            existing = reader.session.select_list("manual_store.get_document_images", {"document_id": document["id"]})
            self.db_snapshot = {row["table_name"]: row["row_count"] for row in
                                reader.session.select_list("manual_store.personal_table_counts")}
        if document["total_pages"] != len(self.service.inventory["reader"].pages):
            raise ValueError("저장된 PDF 쪽수가 다릅니다.")
        tables = {name: [] for name in ("documents", "processing_runs", "parent_records", "chunks", "images", "record_images")}
        tables["documents"] = [{key: document[key] for key in ("id", "file_name", "file_sha256", "total_pages",
                                                              "local_path", "storage_bucket", "storage_path")}]
        run_id, document_id = uuid4(), document["id"]
        tables["processing_runs"] = [{"id": run_id, "document_id": document_id, "pipeline_version": PIPELINE_VERSION,
            "model_name": self.service.config.model_name, "model_revision": self.service.token_counter.model_revision,
            "embedding_dimension": 768, "token_budget": self.service.token_counter.budget, "normalized": True,
            "settings": {"scope": "full_manual", "embedding_state": "not_computed",
                         "additional_image_uploads": 0, "review_status_preserved": True,
                         "batch_size": self.service.config.batch_size, "cpu_threads": self.service.config.cpu_threads}}]
        parent_ids = {record["metadata"]["record_id"]: uuid4() for record in self.service.parents}
        existing_by_key = {(row["pdf_page_number"], row["image_key_sha256"]): row for row in existing}
        image_rows, links, name_cache = {}, [], {}
        for record in self.service.parents:
            meta = record["metadata"]
            parent_id = parent_ids[meta["record_id"]]
            tables["parent_records"].append({"id": parent_id, "run_id": run_id, "document_id": document_id,
                "record_id": meta["record_id"], "title": meta["title"], "raw_text": record["raw_text"],
                "content": record["content"], "pdf_page_number": meta["pdf_page_number"],
                "manual_page_number": meta["manual_page_number"], "source_pages": deepcopy(meta["source_pages"]),
                "content_type": meta["content_type"], "verification_status": meta["verification_status"],
                "review_flags": deepcopy(meta.get("review_flags", [])), "metadata": deepcopy(meta)})
            for part in record["image_parts"]:
                number, key_text = image_identity(part, self.service, name_cache)
                key_hash = sha256_text(key_text)
                identity = number, key_hash
                size = part.get("size")
                candidate = {"pdf_page_number": number, "pdf_image_key": json.loads(key_text),
                    "image_key_sha256": key_hash, "file_name": part.get("name"),
                    "width": size[0] if size else None, "height": size[1] if size else None,
                    "local_path": part.get("local_path"), "storage_bucket": None, "storage_path": None,
                    "upload_status": "local_available" if part.get("local_path") else "reference_only"}
                if identity not in image_rows:
                    actual = existing_by_key.get(identity)
                    image_rows[identity] = {"id": actual["id"] if actual else uuid4(), "document_id": document_id,
                        **({field: actual[field] for field in IMAGE_FIELDS} if actual else candidate)}
                    if actual:
                        self.existing_image_ids.add(actual["id"])
                target = image_rows[identity]
                # [프로젝트 추가] 이름·크기를 알고 있는 참조끼리 충돌하면 추측하거나 덮어쓰지 않습니다.
                for field in ("file_name", "width", "height", "local_path"):
                    if candidate[field] is not None:
                        if target[field] is not None and target[field] != candidate[field]:
                            raise ValueError("같은 그림의 이름·크기·경로가 서로 다릅니다.")
                        if target["id"] not in self.existing_image_ids:
                            target[field] = candidate[field]
                description = part.get("description")
                # [프로젝트 추가] 설명이 있어도 자동 주제와 그림의 대응을 검토 완료로 올리지 않습니다.
                status = "unreviewed_page_reference"
                if description and meta["verification_status"] == "sample_verified":
                    status = "sample_linked"
                elif description and meta["verification_status"] == "visually_reviewed_source":
                    status = "visually_verified"
                links.append({"document_id": document_id, "parent_id": parent_id, "image_id": target["id"],
                    "description": description, "linkage_status": status,
                    "metadata": {"source_image_part": deepcopy(part), "key_resolution": "matched_current_pdf"}})
        tables["images"], tables["record_images"] = list(image_rows.values()), links
        for chunk in self.service.chunks:
            meta = chunk["metadata"]
            tables["chunks"].append({"id": uuid4(), "run_id": run_id, "parent_id": parent_ids[meta["parent_record_id"]],
                "record_id": meta["record_id"], "chunk_index": meta["chunk_index"], "content": chunk["content"],
                "content_sha256": sha256_text(chunk["content"]), "token_count": meta["token_count"],
                "parent_content_start": meta["parent_content_start"], "parent_content_end": meta["parent_content_end"],
                "embedding": None, "metadata": deepcopy(meta)})
        preview = RowPreview(tables, {record_id: "전체 PDF 주제" for record_id in parent_ids})
        validate_full_rows(preview, self.service)
        tables["processing_runs"][0]["settings"]["input_manifest_sha256"] = input_manifest(tables)
        self.preview = preview
        return self

    def summary(self):
        """화면에는 개수·식별값·74쪽 보완만 표시하고 전체 벡터는 출력하지 않습니다."""
        if self.preview is None:
            raise ValueError("먼저 prepare()를 실행하세요.")
        tables = self.preview.tables
        seat = [row for row in tables["parent_records"] if row["metadata"].get("image_description_updates")]
        return {"row_counts": {name: len(rows) for name, rows in tables.items()},
            "additional_rows_if_new_run": {"documents": 0, "processing_runs": 1,
                "parent_records": len(tables["parent_records"]), "chunks": len(tables["chunks"]),
                "images": len(tables["images"]) - len(self.existing_image_ids), "record_images": len(tables["record_images"])},
            "reuse_images": len(self.existing_image_ids), "db_snapshot": self.db_snapshot,
            "image_links_with_description": sum(bool(row["description"]) for row in tables["record_images"]),
            "image_links_without_description": sum(not row["description"] for row in tables["record_images"]),
            "input_manifest_sha256": tables["processing_runs"][0]["settings"]["input_manifest_sha256"],
            "pipeline_version": PIPELINE_VERSION, "summary": self.service.summary(),
            "seat74_updates": [{"record_id": row["record_id"], "source_pages": row["source_pages"],
                "verification_status": row["verification_status"], "content_tail": row["content"][-250:]} for row in seat],
            "embedding_complete": self.preview.embedding_report is not None,
            "db_written": bool(self.preview.embedding_report and self.preview.embedding_report.get("db_written")),
            "additional_storage_uploads": 0}

    def embed(self, progress=print):
        """전체 청크를 메모리에 임베딩합니다. 실제 저장은 별도 승인된 save에서만 합니다."""
        self.prepare(progress=progress)
        if self.preview.embedding_report is not None:
            return self
        validate_full_rows(self.preview, self.service)
        rows = self.preview.tables["chunks"]
        run = self.preview.tables["processing_runs"][0]
        manifest = run["settings"]["input_manifest_sha256"]
        started = perf_counter()
        embedder = LocalEmbedder(self.service.config, self.service.token_counter)
        vectors = embedder.embed_chunks(rows, progress=progress)
        try:
            for row, vector in zip(rows, vectors, strict=True):
                row["embedding"] = vector.tolist()
            validate_full_rows(self.preview, self.service, require_vectors=True)
            if input_manifest(self.preview.tables) != manifest:
                raise ValueError("임베딩 도중 전체 입력이 바뀌었습니다.")
        except Exception:
            for row in rows:
                row["embedding"] = None
            raise
        # [프로젝트 추가] 개수뿐 아니라 실제 숫자의 유효성·길이도 결과에 남깁니다.
        # 벡터 전체는 파일에 쓰지 않고, DB에 저장한 뒤 같은 숫자인지 다시 비교합니다.
        norms = np.linalg.norm(vectors, axis=1)
        self.preview.embedding_report = {"shape": list(vectors.shape), "dtype": str(vectors.dtype),
            "norm_min": float(norms.min()), "norm_max": float(norms.max()),
            "failed_chunks": 0, "vector_bytes": int(vectors.nbytes),
            "largest_chunk_tokens": max(row["token_count"] for row in rows), "model_name": embedder.model_name,
            "model_revision": embedder.model_revision, "elapsed_seconds": round(perf_counter() - started, 3),
            "finite": True, "normalized": True, "input_manifest_sha256": manifest,
            "db_written": False, "storage_uploaded": False}
        run["settings"]["embedding_state"] = "computed_in_memory"
        return self

    def save(self, *, approved_manifest, progress=print):
        """승인한 입력만 새 작업으로 저장합니다. 기존 파일·작업·그림을 수정하지 않습니다."""
        if self.preview is None or self.preview.embedding_report is None:
            raise ValueError("전체 미리보기와 임베딩을 먼저 완료하세요.")
        validate_full_rows(self.preview, self.service, require_vectors=True)
        tables = self.preview.tables
        manifest = input_manifest(tables)
        if manifest != approved_manifest or manifest != tables["processing_runs"][0]["settings"]["input_manifest_sha256"]:
            raise ValueError("승인한 전체 입력 식별값이 다릅니다. 새 미리보기를 검토하세요.")
        run = tables["processing_runs"][0]
        run["settings"].update(embedding_state="stored_after_validation",
                               embedding_validation=deepcopy(self.preview.embedding_report))
        writer = ManualRepository(PersonalSqlSession())
        reused = False
        with writer.session.transaction():
            document = writer.session.select_one("manual_store.lock_full_document", {"document_id": run["document_id"]})
            if document is None or any(document[key] != value for key, value in tables["documents"][0].items()):
                raise ValueError("재사용할 PDF 정보가 미리보기 이후 바뀌었습니다.")
            matches = writer.session.select_list("manual_store.find_full_run", {"document_id": run["document_id"],
                "pipeline_version": PIPELINE_VERSION, "model_name": run["model_name"],
                "model_revision": run["model_revision"], "input_manifest_sha256": manifest})
            if matches:
                if len(matches) != 1 or matches[0]["status"] != "ready":
                    raise ValueError("같은 입력의 기존 작업 상태를 먼저 확인하세요.")
                run_id = matches[0]["id"]
                compare_full_bundle(self.preview, load_sample_bundle(writer, run_id), require_ready=True)
                reused = True
            else:
                existing = writer.session.select_list("manual_store.lock_document_images", {"document_id": run["document_id"]})
                existing_by_key = {(row["pdf_page_number"], row["image_key_sha256"]): row for row in existing}
                replacements, new_images = {}, []
                for row in tables["images"]:
                    actual = existing_by_key.get((row["pdf_page_number"], row["image_key_sha256"]))
                    if actual:
                        if any(json_value(row[field]) != json_value(actual[field]) for field in IMAGE_FIELDS):
                            raise ValueError("재사용할 그림 정보가 미리보기 이후 바뀌었습니다.")
                        replacements[row["id"]] = actual["id"]
                    else:
                        if row["id"] in self.existing_image_ids:
                            raise ValueError("재사용할 그림 행이 없습니다.")
                        new_images.append(row)
                # 같은 키가 준비 이후 등록됐다면 이미 있는 행에 연결합니다. 기존 값을 덮어쓰지 않습니다.
                for row in tables["images"]:
                    row["id"] = replacements.get(row["id"], row["id"])
                for row in tables["record_images"]:
                    row["image_id"] = replacements.get(row["image_id"], row["image_id"])
                run_id = run["id"]
                for table, rows in (("processing_runs", [run]), ("images", new_images),
                                    ("parent_records", tables["parent_records"]), ("chunks", tables["chunks"]),
                                    ("record_images", tables["record_images"])):
                    # [수업 개념] 하나의 트랜잭션: 실패하면 이번 새 작업의 모든 INSERT를 되돌립니다.
                    for start in range(0, len(rows), 256):
                        batch = rows[start:start + 256]
                        if writer.insert_rows(table, batch) != len(batch):
                            raise ValueError("일괄 저장 건수가 준비한 행과 다릅니다.")
                    if progress:
                        progress(f"개인 {table}: {len(rows)}행 저장 준비 — 아직 트랜잭션 확정 전")
                compare_full_bundle(self.preview, load_sample_bundle(writer, run_id))
                if writer.session.execute("manual_store.mark_run_ready", {"run_id": run_id}) != 1:
                    raise ValueError("전체 저장 완료 상태 변경 건수가 다릅니다.")
                compare_full_bundle(self.preview, load_sample_bundle(writer, run_id), require_ready=True)
        # 확정 후 새 읽기 전용 연결에서도 대조합니다. 실패를 자동 재삽입으로 처리하지 않습니다.
        reader = ManualRepository(PersonalSqlSession(read_only=True))
        with reader.session.transaction():
            result = compare_full_bundle(self.preview, load_sample_bundle(reader, run_id), require_ready=True)
            counts = reader.session.select_list("manual_store.personal_table_counts")
            sizes = reader.session.select_list("manual_store.personal_table_sizes")
        self.preview.embedding_report["db_written"] = True
        return {**result, "reused_existing_run": reused, "schema_counts": counts,
                "allocated_bytes": sum(row["bytes"] for row in sizes), "additional_storage_uploads": 0}
