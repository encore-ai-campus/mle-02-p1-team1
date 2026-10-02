"""표본 청크만 로컬 임베딩하고 저장 전에 글·벡터·연결을 확인합니다."""

# [프로젝트 추가] 전체 2,213개 대신 승인된 표본의 11개만 계산합니다.
# 원문과 그림 설명의 텍스트 임베딩이며 그림 픽셀을 임베딩하는 기능은 아닙니다.
# DB·Storage·벡터 파일 저장은 없습니다. 결과는 전달받은 preview의 메모리에 남습니다.

import json
import time

import numpy as np

from .db_rows import file_sha256, sha256_text
from .embedding import LocalEmbedder


def validate_sample_rows(preview, service, *, require_vectors=False):
    """원문·청크·그림의 연결과 실제 모델 입력을 확인하고 벡터 배열을 돌려줍니다."""
    tables = preview.tables
    if len(tables["documents"]) != 1 or len(tables["processing_runs"]) != 1:
        raise ValueError("표본은 PDF와 처리 작업 각각 한 건이어야 합니다.")
    document, run = tables["documents"][0], tables["processing_runs"][0]
    if document["file_sha256"] != file_sha256(service.config.pdf_path):
        raise ValueError("PDF 파일이 준비한 내용과 달라졌습니다.")
    if run["document_id"] != document["id"]:
        raise ValueError("PDF와 처리 작업 연결이 다릅니다.")
    if (run["model_name"], run["model_revision"]) != (
            service.token_counter.model_name, service.token_counter.model_revision):
        raise ValueError("모델 이름·버전과 청킹 토크나이저가 다릅니다.")
    if run["embedding_dimension"] != 768 or run["token_budget"] != service.token_counter.budget or not run["normalized"]:
        raise ValueError("현재 모델의 차원·입력 한도·정규화 설정이 다릅니다.")
    parents = {row["id"]: row for row in tables["parent_records"]}
    source = {record["metadata"]["record_id"]: record for record in service.parents}
    parent_record_ids = {row["record_id"] for row in parents.values()}
    if len(parents) != len(tables["parent_records"]) or len(parent_record_ids) != len(parents):
        raise ValueError("부모 연결 번호 또는 기록 ID가 중복되었습니다.")
    for row in parents.values():
        if row["run_id"] != run["id"] or row["document_id"] != document["id"]:
            raise ValueError("부모의 PDF·처리 작업 연결이 다릅니다.")
        original = source.get(row["record_id"])
        if original is None or any(row[field] != original[field] for field in ("content", "raw_text", "metadata")):
            raise ValueError("부모 원문·검색 글·출처가 준비한 기록과 다릅니다.")
        for field in ("required_context_record_ids", "unreviewed_continuation_record_ids"):
            if not set(row["metadata"].get(field, [])) <= parent_record_ids:
                raise ValueError("표본에서 함께 읽어야 하는 기록이 누락됐습니다.")
    images = {row["id"]: row for row in tables["images"]}
    if len(images) != len(tables["images"]) or any(row["document_id"] != document["id"] for row in images.values()):
        raise ValueError("그림의 PDF 연결 또는 식별 번호가 다릅니다.")
    seen_links = set()
    for link in tables["record_images"]:
        parent, image = parents.get(link["parent_id"]), images.get(link["image_id"])
        key = (link["parent_id"], link["image_id"])
        if parent is None or image is None or link["document_id"] != document["id"] or key in seen_links:
            raise ValueError("부모와 그림 연결이 누락되거나 중복되었습니다.")
        if image["pdf_page_number"] not in parent["source_pages"]:
            raise ValueError("그림 쪽수가 부모 출처에 없습니다.")
        seen_links.add(key)
    seen_chunks = set()
    seen_positions = set()
    vectors = []
    for row in tables["chunks"]:
        parent = parents.get(row["parent_id"])
        position = (row["parent_id"], row["chunk_index"])
        if parent is None or row["run_id"] != run["id"] or row["record_id"] in seen_chunks or position in seen_positions:
            raise ValueError("청크의 부모·처리 버전 연결 또는 번호를 확인해야 합니다.")
        start, end = row["parent_content_start"], row["parent_content_end"]
        expected = "주제: " + parent["title"] + "\n" + parent["content"][start:end].strip()
        if not 0 <= start < end <= len(parent["content"]) or expected != row["content"]:
            raise ValueError("청크 입력 글과 부모 원문 구간이 일치하지 않습니다.")
        if sha256_text(row["content"]) != row["content_sha256"]:
            raise ValueError("청크 글이 변경돼 다시 임베딩해야 합니다.")
        count = service.token_counter.count(row["content"])
        if count != row["token_count"] or not 1 <= count <= run["token_budget"]:
            raise ValueError("청크 토큰 수와 모델 한도가 다릅니다.")
        seen_chunks.add(row["record_id"])
        seen_positions.add(position)
        if require_vectors:
            vector = np.asarray(row["embedding"], dtype=np.float32)
            if vector.shape != (768,) or not np.isfinite(vector).all():
                raise ValueError("청크 벡터가 없거나 차원·숫자가 잘못됐습니다.")
            if not np.isclose(np.linalg.norm(vector), 1.0, atol=1e-5):
                raise ValueError("청크 벡터가 정규화되지 않았습니다.")
            vectors.append(vector)
    if not seen_chunks or {row["parent_id"] for row in tables["chunks"]} != set(parents):
        raise ValueError("검색 청크가 없는 부모가 있습니다.")
    return np.asarray(vectors, dtype=np.float32) if require_vectors else None


def embed_sample_rows(preview, service, progress=print):
    """선정한 행의 글을 같은 로컬 모델 버전으로 임베딩해 메모리에 연결합니다."""
    validate_sample_rows(preview, service)
    rows = preview.tables["chunks"]
    if preview.embedding_report is not None or any(row["embedding"] is not None for row in rows):
        raise ValueError("이미 계산한 표본입니다. 새 미리보기를 준비하거나 기존 결과를 사용하세요.")
    # [프로젝트 추가] 모델 입력의 순서·글 식별값을 먼저 기록해 다른 청크의 벡터가 섞이지 않게 합니다.
    manifest = [{"record_id": row["record_id"], "content_sha256": row["content_sha256"]} for row in rows]
    inputs = [{"content": row["content"]} for row in rows]
    started = time.perf_counter()
    if progress:
        progress(f"표본 {len(rows)}개 임베딩 시작 | 로컬 CPU | 같은 스냅샷 버전 사용")
    embedder = LocalEmbedder(service.config, service.token_counter)
    vectors = embedder.embed_chunks(inputs, progress=progress)
    if manifest != [{"record_id": row["record_id"], "content_sha256": sha256_text(row["content"])} for row in rows]:
        raise ValueError("임베딩 도중 청크 글 또는 순서가 바뀌었습니다.")
    try:
        for row, vector in zip(rows, vectors, strict=True):
            row["embedding"] = vector.tolist()
        validate_sample_rows(preview, service, require_vectors=True)
    except Exception:
        # 실패한 묶음을 계산 완료로 남기지 않습니다. DB에는 아직 쓰지 않았습니다.
        for row in rows:
            row["embedding"] = None
        raise
    norms = np.linalg.norm(vectors, axis=1)
    run = preview.tables["processing_runs"][0]
    run["pipeline_version"] = "db_sample_embedding_v1"
    run["settings"].update({"embedding_state": "computed_in_memory", "model_revision_state": "pinned_local_snapshot"})
    preview.embedding_report = {
        "model_name": embedder.model_name, "model_revision": embedder.model_revision,
        "shape": list(vectors.shape), "elapsed_seconds": round(time.perf_counter() - started, 3),
        "dtype": str(vectors.dtype), "finite": bool(np.isfinite(vectors).all()),
        "norm_min": float(norms.min()), "norm_max": float(norms.max()),
        "input_manifest_sha256": sha256_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))),
        "vector_payload_bytes": len(rows) * (4 * 768 + 8),
        "db_written": False, "storage_uploaded": False,
    }
    return preview
