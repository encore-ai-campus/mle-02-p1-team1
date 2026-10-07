"""검토한 부분의 별도 버전을 읽어 기존 검색 자료와 결합합니다. 이 파일은 DB에 쓰지 않습니다."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from uuid import UUID

import numpy as np

from .source_profile import FULL_SOURCE
from .config import ManualConfig


FOLDER = ManualConfig().project_folder / "data/zzong_santafe_lag/review_revisions"
ACTIVE_FILE = FOLDER / "active.json"
# [프로젝트 추가] Git으로 공유하는 선택 정보에는 버전 ID와 내용 식별값만 넣습니다.
# 개인 선택 파일이 있으면 우선하며, DB에 없는 버전은 검증 오류로 중단합니다.
SHARED_SELECTION = Path(__file__).resolve().parent / "review_revision_selection.json"
RECORD_IDS = {"auto_topic_150", "auto_topic_171", "auto_topic_172", "auto_topic_173", "auto_topic_174"}
# 2차 원본 대조 8개는 기존 5개를 보존한 누적 버전으로만 허용합니다.
BATCH2_RECORD_IDS = {"auto_topic_135", "auto_topic_139", "auto_topic_149", "auto_topic_160",
                     "auto_topic_274", "auto_topic_276", "auto_topic_420", "auto_topic_73"}


def selection_file():
    """개인 선택을 우선하고, 없으면 공유된 정확한 검토 버전 선택 파일을 반환합니다."""
    if ACTIVE_FILE.exists():
        return ACTIVE_FILE
    return SHARED_SELECTION if SHARED_SELECTION.exists() else None


def sha(value):
    """UUID·튜플의 JSON 표현을 통일해 수정 버전의 내용 식별값을 계산합니다."""
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def text_sha(value):
    """임베딩에 사용한 글의 실제 UTF-8 바이트 식별값입니다."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def validate_bundle(bundle):
    """부모·청크·그림 연결과 두 벡터 공간의 일치 여부를 확인합니다."""
    from .openai_embedding import MODEL, DIMENSION, RECIPE
    from .sample_store import APPROVED_REVISION
    payload, chunks = bundle["payload"], bundle["chunks"]
    if (sha(payload) != bundle["payload_sha256"] or payload["source_run_id"] != str(FULL_SOURCE.run_id)
            or payload["pdf_sha256"] != FULL_SOURCE.pdf_sha256
            or payload["base_manifest_sha256"] != FULL_SOURCE.input_manifest_sha256
            or payload["local_model"] != ManualConfig().model_name
            or payload["local_revision"] != APPROVED_REVISION
            or payload["openai_model"] != MODEL or payload["openai_recipe"] != RECIPE):
        raise ValueError("검토 버전의 원문·모델·내용 식별값이 다릅니다.")
    parents = {row["record_id"]: row for row in payload["parents"]}
    if (set(parents) not in (RECORD_IDS, RECORD_IDS | BATCH2_RECORD_IDS)
            or len(parents) != len(payload['parents']) or len(chunks) != len(payload["chunk_inputs"])):
        raise ValueError("승인된 검토 부모 범위 또는 청크 개수가 다릅니다.")
    expected = {row["record_id"]: row for row in payload["chunk_inputs"]}
    if len(expected) != len(chunks) or {row["record_id"] for row in chunks} != set(expected):
        raise ValueError("청크 ID가 누락·중복되었습니다.")
    for row in chunks:
        meta = row["metadata"]
        identity = row["record_id"]
        parent = parents[meta["parent_record_id"]]
        start, end = meta["parent_content_start"], meta["parent_content_end"]
        reconstructed = "주제: " + parent["title"] + "\n" + parent["content"][start:end].strip()
        if (row["content"] != reconstructed or row["input_sha256"] != text_sha(row["content"])
                or row["input_sha256"] != expected[identity]["input_sha256"]
                or meta != expected[identity]["metadata"]):
            raise ValueError("청크가 보완한 부모 구간·임베딩 입력과 다릅니다.")
        for field, dimension in (("local_embedding", 768), ("openai_embedding", DIMENSION)):
            vector = np.asarray(row[field], dtype=np.float32)
            if vector.shape != (dimension,) or not np.isfinite(vector).all() or not np.isclose(np.linalg.norm(vector), 1, atol=1e-5):
                raise ValueError("수정 청크의 벡터 크기·숫자·정규화를 확인하세요.")
    for row in payload["images"]:
        if row["parent_record_id"] not in parents or row["linkage_status"] != "visually_verified":
            raise ValueError("검토하지 않은 그림 연결이 섞였습니다.")
    return bundle


def load_active(session):
    """활성 선택 파일의 정확한 버전만 DB에서 읽습니다. 최신 버전을 임의로 선택하지 않습니다."""
    selected_file = selection_file()
    if selected_file is None:
        return None
    pointer = json.loads(selected_file.read_text(encoding="utf-8"))
    revision_id = UUID(pointer["revision_id"])
    header = session.select_one("review_revisions.get_revision", {"revision_id": revision_id})
    if (not header or header["status"] != "ready" or str(header["source_run_id"]) != str(FULL_SOURCE.run_id)
            or header["payload_sha256"] != pointer["payload_sha256"]):
        raise ValueError("선택한 검토 버전이 DB에 완전히 저장되지 않았습니다.")
    chunks = session.select_list("review_revisions.get_chunks", {"revision_id": revision_id})
    bundle = {"revision_id": str(revision_id), "payload": header["payload"],
              "payload_sha256": header["payload_sha256"], "chunks": chunks}
    if len(chunks) != header["chunk_count"]:
        raise ValueError("저장한 검토 청크 개수가 다릅니다.")
    return validate_bundle(bundle)


def combine(bundle, rows, chunks, images, backend):
    """수정된 부모의 옛 청크만 검색 목록에서 대체합니다. 원격 자료는 변경하지 않습니다."""
    if bundle is None:
        return rows, chunks, images
    validate_bundle(bundle)
    payload = bundle["payload"]
    replaced_ids = {row['record_id'] for row in payload['parents']}
    original = {row["record_id"]: row for row in rows}
    for identity, expected in payload["base_content_sha256"].items():
        if text_sha(original[identity]["content"]) != expected:
            raise ValueError("수정 버전이 참조한 원래 부모 내용이 바뀌었습니다.")
    # [프로젝트 추가] 그림 파일의 기존 ID·쪽수·내부 키·경로를 대조하고 설명·연결만 보완합니다.
    original_images = {str(row["id"]): row for row in images}
    for row in payload["images"]:
        old = original_images[str(row["id"])]
        if any(row[key] != old[key] for key in ("pdf_page_number", "pdf_image_key", "storage_path", "image_key_sha256")):
            raise ValueError("보완 그림이 기존 업로드한 파일과 다릅니다.")
    new_rows = [deepcopy(row) for row in rows if row["record_id"] not in replaced_ids] + deepcopy(payload["parents"])
    new_chunks = [row for row in chunks if row["metadata"]["parent_record_id"] not in replaced_ids]
    for row in bundle["chunks"]:
        field = "openai_embedding" if backend == "openai" else "local_embedding"
        new_chunks.append({"record_id": row["record_id"], "content": row["content"],
                           "metadata": row["metadata"], "embedding": np.asarray(row[field], dtype=np.float32)})
    new_images = [row for row in images if row["parent_record_id"] not in replaced_ids] + deepcopy(payload["images"])
    return new_rows, sorted(new_chunks, key=lambda row: row["record_id"]), new_images
