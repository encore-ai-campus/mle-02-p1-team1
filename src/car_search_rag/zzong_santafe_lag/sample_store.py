"""승인한 PDF 표본을 한 트랜잭션으로 저장하고 다시 읽어 비교합니다."""

# [프로젝트 적용] 기존 SQL Mapper의 insert_row와 transaction을 재사용합니다.
# [프로젝트 추가] 쓰기는 개인 스키마의 표본에 한정합니다. 파일 업로드·테이블 생성은 없습니다.

import json
from copy import deepcopy

import numpy as np

from .database import ManualRepository, PersonalSqlSession
from .sample_embedding import validate_sample_rows


APPROVED_REVISION = "3ec6ac494ac7ab802fbeed415a99d546c3a0503c"
APPROVED_MANIFEST = "a336a9c958344af7b2b21652041104764c0d67f90d51084aec3366b1f2d1f056"
APPROVED_COUNTS = {
    "documents": 1, "processing_runs": 1, "parent_records": 4,
    "chunks": 11, "images": 3, "record_images": 3,
}


def load_sample_bundle(repository, run_id):
    """같은 처리 버전의 PDF·원문·벡터·그림 연결을 여섯 목록으로 읽습니다."""
    session = repository.session
    run = session.select_one("manual_store.get_run", {"run_id": run_id})
    if run is None:
        raise ValueError("저장한 표본 처리 작업을 찾을 수 없습니다.")
    document = session.select_one("manual_store.get_document", {"document_id": run["document_id"]})
    tables = {"documents": [document] if document else [], "processing_runs": [run]}
    for table, query in (
        ("parent_records", "get_run_parents"), ("chunks", "get_run_chunks"),
        ("images", "get_run_images"), ("record_images", "get_run_image_links"),
    ):
        tables[table] = session.select_list("manual_store." + query, {"run_id": run_id})
    return tables


def json_value(value):
    """튜플이 JSONB 목록으로 바뀌는 차이를 정리해 원래 값과 비교합니다."""
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def compare_sample_bundle(preview, stored, *, require_ready=False):
    """전체 저장 필드와 벡터를 대조합니다. 새 UUID는 DB 번호에 맞춰 비교합니다."""
    expected = deepcopy(preview.tables)
    if {name: len(rows) for name, rows in stored.items()} != APPROVED_COUNTS:
        raise ValueError("저장한 표본 건수가 승인한 범위와 다릅니다.")
    # [프로젝트 추가] 재실행에서 새로 발급한 번호를 DB 번호로 연결해 중복 저장을 피합니다.
    replacements = {
        expected["documents"][0]["id"]: stored["documents"][0]["id"],
        expected["processing_runs"][0]["id"]: stored["processing_runs"][0]["id"],
    }
    parent_lookup = {row["record_id"]: row for row in stored["parent_records"]}
    image_lookup = {(row["pdf_page_number"], row["image_key_sha256"]): row for row in stored["images"]}
    chunk_lookup = {row["record_id"]: row for row in stored["chunks"]}
    for table, lookup in (("parent_records", parent_lookup), ("chunks", chunk_lookup)):
        for row in expected[table]:
            target = lookup.get(row["record_id"])
            if target is None:
                raise ValueError("저장한 원문 또는 청크 ID가 다릅니다.")
            replacements[row["id"]] = target["id"]
    for row in expected["images"]:
        target = image_lookup.get((row["pdf_page_number"], row["image_key_sha256"]))
        if target is None:
            raise ValueError("저장한 이미지 키가 다릅니다.")
        replacements[row["id"]] = target["id"]
    for table, rows in expected.items():
        for row in rows:
            for field in ("id", "document_id", "run_id", "parent_id", "image_id"):
                if field in row:
                    row[field] = replacements[row[field]]
            key = (row["parent_id"], row["image_id"]) if table == "record_images" else row["id"]
            actual = next((item for item in stored[table] if
                           ((item["parent_id"], item["image_id"]) if table == "record_images" else item["id"]) == key), None)
            if actual is None:
                raise ValueError("저장한 행의 연결 번호가 다릅니다.")
            for field, value in row.items():
                if field == "embedding":
                    if not np.array_equal(np.asarray(value, dtype=np.float32), actual[field]):
                        raise ValueError("DB에서 읽은 벡터와 계산한 벡터가 다릅니다.")
                elif field == "settings":
                    # 재실행의 계산 시간 차이로 기존 보고서를 덮어쓰지 않습니다.
                    for setting, expected_value in value.items():
                        if setting != "embedding_validation" and json_value(actual[field].get(setting)) != json_value(expected_value):
                            raise ValueError("DB에 저장한 처리 설정이 다릅니다.")
                elif json_value(actual[field]) != json_value(value):
                    raise ValueError(f"저장 값이 원래 행과 다릅니다: {table}.{field}")
    run = stored["processing_runs"][0]
    if require_ready and run["status"] != "ready":
        raise ValueError("표본 저장 완료 상태가 아닙니다.")
    return {"row_counts": APPROVED_COUNTS.copy(), "all_fields_match": True,
            "vectors_exact_match": True, "run_id": str(run["id"]), "run_status": run["status"]}


def save_sample_rows(preview, service):
    """승인 범위만 저장합니다. 기존 동일 표본은 읽고 비교하여 중복 삽입을 피합니다."""
    validate_sample_rows(preview, service, require_vectors=True)
    report = preview.embedding_report
    if not report or report["model_revision"] != APPROVED_REVISION or report["input_manifest_sha256"] != APPROVED_MANIFEST:
        raise ValueError("승인한 모델 버전 또는 표본 입력과 다릅니다. 새 범위를 먼저 검토하세요.")
    if {name: len(rows) for name, rows in preview.tables.items()} != APPROVED_COUNTS:
        raise ValueError("승인한 23개 행의 범위를 벗어났습니다.")
    run = preview.tables["processing_runs"][0]
    run["settings"].update({
        "input_manifest_sha256": report["input_manifest_sha256"],
        "embedding_state": "stored_after_validation",
        "embedding_validation": {key: value for key, value in report.items()
                                 if key not in {"db_written", "storage_uploaded"}},
    })
    repository = ManualRepository(PersonalSqlSession())
    reused = False
    # [수업 개념] 트랜잭션: 모두 성공하면 함께 확정하고 실패하면 함께 되돌립니다.
    with repository.session.transaction():
        document = repository.session.select_one("manual_store.find_document", {
            "file_sha256": preview.tables["documents"][0]["file_sha256"]})
        if document is not None:
            matches = repository.session.select_list("manual_store.find_sample_run", {
                "document_id": document["id"], "pipeline_version": run["pipeline_version"],
                "model_name": run["model_name"], "model_revision": run["model_revision"],
                "input_manifest_sha256": report["input_manifest_sha256"],
            })
            if len(matches) != 1 or matches[0]["status"] != "ready":
                raise ValueError("같은 PDF의 기존 작업이 있습니다. 기존 자료를 덮어쓰지 않고 중단합니다.")
            run_id = matches[0]["id"]
            compare_sample_bundle(preview, load_sample_bundle(repository, run_id), require_ready=True)
            reused = True
        else:
            run_id = run["id"]
            for table in APPROVED_COUNTS:
                for row in preview.tables[table]:
                    repository.insert_row(table, row)
            # 같은 트랜잭션에서 모든 필드·벡터를 비교한 다음에만 ready로 바꿉니다.
            compare_sample_bundle(preview, load_sample_bundle(repository, run_id))
            changed = repository.session.execute("manual_store.mark_run_ready", {"run_id": run_id})
            if changed != 1:
                raise ValueError("저장 완료 상태 변경 건수가 다릅니다.")
            compare_sample_bundle(preview, load_sample_bundle(repository, run_id), require_ready=True)
    # COMMIT 후에는 새 읽기 전용 연결로 다시 읽습니다. 실패했다고 자동 재삽입하지 않습니다.
    reader = ManualRepository(PersonalSqlSession(read_only=True))
    with reader.session.transaction():
        stored = load_sample_bundle(reader, run_id)
        result = compare_sample_bundle(preview, stored, require_ready=True)
        sizes = reader.session.select_list("manual_store.personal_table_sizes")
        total_counts = reader.session.select_list("manual_store.personal_table_counts")
    preview.embedding_report["db_written"] = True
    result.update({"reused_existing": reused, "schema": "zzong_santafe_lag", "storage_uploaded": False,
                   "total_table_bytes": sum(row["bytes"] for row in sizes),
                   "table_sizes": sizes, "schema_counts": total_counts})
    return result


def read_sample_report(run_id):
    """모델을 다시 실행하지 않고 저장한 원문·각주·그림 연결과 벡터 상태를 읽습니다."""
    reader = ManualRepository(PersonalSqlSession(read_only=True))
    with reader.session.transaction():
        tables = load_sample_bundle(reader, run_id)
        sizes = reader.session.select_list("manual_store.personal_table_sizes")
    run = tables["processing_runs"][0]
    vectors = np.asarray([row["embedding"] for row in tables["chunks"]], dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1) if len(vectors) else np.array([])
    parents = {row["id"]: row for row in tables["parent_records"]}
    images = {row["id"]: row for row in tables["images"]}
    return {
        "run_id": str(run["id"]), "run_status": run["status"],
        "model_name": run["model_name"], "model_revision": run["model_revision"],
        "row_counts": {name: len(rows) for name, rows in tables.items()},
        "vector_shape": list(vectors.shape), "finite": bool(np.isfinite(vectors).all()),
        "normalized": bool(len(norms) and np.allclose(norms, 1.0, atol=1e-5)),
        "parents": [{"record_id": row["record_id"], "title": row["title"],
                     "source_pages": row["source_pages"], "manual_page_number": row["manual_page_number"],
                     "raw_text_characters": len(row["raw_text"]), "content": row["content"],
                     "required_context_record_ids": row["metadata"].get("required_context_record_ids", [])}
                    for row in parents.values()],
        "image_links": [{"parent_record_id": parents[link["parent_id"]]["record_id"],
                         "description": link["description"], "linkage_status": link["linkage_status"],
                         "pdf_page_number": images[link["image_id"]]["pdf_page_number"],
                         "pdf_image_key": images[link["image_id"]]["pdf_image_key"],
                         "local_path": images[link["image_id"]]["local_path"]}
                        for link in tables["record_images"]],
        "total_table_bytes": sum(row["bytes"] for row in sizes),
    }
