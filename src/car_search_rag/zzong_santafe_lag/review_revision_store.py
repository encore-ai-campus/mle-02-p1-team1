"""원문 검토 수정안의 준비·소량 임베딩·승인된 개인 DB 저장을 분리합니다."""

import argparse
import json
from copy import deepcopy
from pathlib import Path
from uuid import UUID, uuid5, NAMESPACE_URL

import numpy as np

from .chunking import TokenCounter, split_record
from .config import ManualConfig
from .database import PersonalSqlSession, PersonalDatabaseManager
from .embedding import LocalEmbedder
from .openai_embedding import OpenAIEmbedder, OpenAITokenCounter, MODEL, RECIPE
from .review_revision import FOLDER, ACTIVE_FILE, RECORD_IDS, sha, text_sha, validate_bundle
from .sample_store import APPROVED_REVISION
from .source_profile import FULL_SOURCE


DRAFT_FOLDER = ManualConfig().project_folder / "data/zzong_santafe_lag/reports/sequence_20261005_172146"
BUNDLE_FILE = FOLDER / "review_20261006_v1.json"


def write_new(path, value):
    """새 체크포인트만 보관해 성공한 유료 요청을 재실행하지 않도록 합니다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, default=str)


def prepare():
    """확인한 부모 5개를 재청킹하고 두 모델 벡터를 만듭니다. DB·Storage에는 쓰지 않습니다."""
    if BUNDLE_FILE.exists():
        return validate_bundle(json.loads(BUNDLE_FILE.read_text(encoding="utf-8")))
    # 시작 파일이 있으면 자동 재호출하지 않습니다. API 성공 후 파일 저장 실패도 중복 청구할 수 있습니다.
    started = FOLDER / "prepare_started.json"
    if started.exists():
        raise ValueError("미완료 준비 기록이 있습니다. 성공 배치 파일을 확인한 후 재개 방법을 정하세요.")
    draft = json.loads((DRAFT_FOLDER / "review_drafts.json").read_text(encoding="utf-8"))
    source = json.loads((DRAFT_FOLDER / "review_scope_expanded.json").read_text(encoding="utf-8"))
    if draft["pdf_sha256"] != FULL_SOURCE.pdf_sha256 or not draft["raw_text_preserved"]:
        raise ValueError("원문 대조 수정안이 아닙니다.")
    config = ManualConfig(model_revision=APPROVED_REVISION)
    counter = TokenCounter(config.model_name, revision=APPROVED_REVISION)
    rows = deepcopy(draft["draft_records"])
    if {row["record_id"] for row in rows} != RECORD_IDS:
        raise ValueError("부모 범위가 다릅니다.")
    image_lookup = {(str(row["id"]), row["parent_record_id"]): row for row in source["images"]}
    images = []
    for link in draft["draft_image_links"]:
        row = deepcopy(image_lookup[(link["image_id"], link["parent_record_id"])])
        row.update(description=link["description"], linkage_status="visually_verified")
        images.append(row)
    children = []
    for row in rows:
        descriptions = [image["description"] for image in images if image["parent_record_id"] == row["record_id"]]
        if descriptions:
            row["content"] += "\n[그림 설명] " + " ".join(descriptions)
        row["verification_status"] = "visually_reviewed_source"
        row["review_flags"] = []
        row["metadata"].update(verification_status="visually_reviewed_source", review_flags=[],
                               review_method="Codex PDF 원본 화면 대조", human_confirmed=False,
                               reviewed_on="2026-10-06")
        row["metadata"]["required_context_record_ids"] = list(dict.fromkeys(
            row["metadata"].get("required_context_record_ids", [])
            + draft["required_context_proposal"].get(row["record_id"], [])))
        # 원문 전체와 경고 문장은 유지합니다. 새 그림 설명만 검색용 글에 덧붙입니다.
        children.extend(split_record({"content": row["content"], "raw_text": row["raw_text"],
                                      "metadata": row["metadata"]}, counter))
    inputs = [{"record_id": c["metadata"]["record_id"], "input_sha256": text_sha(c["content"]),
               "metadata": c["metadata"]} for c in children]
    payload = {"source_run_id": str(FULL_SOURCE.run_id), "pdf_sha256": FULL_SOURCE.pdf_sha256,
               "base_manifest_sha256": FULL_SOURCE.input_manifest_sha256,
               "base_content_sha256": {r["record_id"]: text_sha(r["content"]) for r in source["records"]},
               "parents": rows, "images": images, "chunk_inputs": inputs,
               "local_model": config.model_name, "local_revision": APPROVED_REVISION,
               "openai_model": MODEL, "openai_recipe": RECIPE, "reviewer": "Codex PDF 화면 대조",
               "human_confirmed": False, "removed_image_links": draft["removed_links"]}
    payload_hash = sha(payload)
    revision_id = str(uuid5(NAMESPACE_URL, "zzong_santafe_lag:review:" + payload_hash))
    oa_counter = OpenAITokenCounter()
    token_count = sum(oa_counter.count(c["content"]) for c in children)
    write_new(started, {"revision_id": revision_id, "payload_sha256": payload_hash,
                        "parent_count": len(rows), "chunk_count": len(children),
                        "openai_input_tokens": token_count, "db_written": False})
    print(f"준비: 부모 {len(rows)}개, 새 청크 {len(children)}개, OpenAI 입력 {token_count}토큰", flush=True)
    local = LocalEmbedder(config, counter).embed_chunks(children)
    write_new(FOLDER / "local_vectors.json", local.tolist())
    oa = OpenAIEmbedder(oa_counter)
    vectors = []
    for start in range(0, len(children), 64):
        batch = oa.embed_texts([c["content"] for c in children[start:start+64]])
        write_new(FOLDER / f"openai_batch_{start:04d}.json", batch.tolist())
        vectors.extend(batch.tolist())
        print(f"OpenAI 청크 {len(vectors)}/{len(children)} 완료", flush=True)
    bundle = {"revision_id": revision_id, "payload": payload, "payload_sha256": payload_hash,
              "openai_input_tokens": token_count, "document_api_batches": (len(children)+63)//64,
              "chunks": [{"record_id": c["metadata"]["record_id"], "content": c["content"],
                          "input_sha256": text_sha(c["content"]), "metadata": c["metadata"],
                          "local_embedding": local[i].tolist(), "openai_embedding": vectors[i]}
                         for i, c in enumerate(children)]}
    validate_bundle(bundle)
    write_new(BUNDLE_FILE, bundle)
    return bundle


def legacy_fingerprint(connection):
    """이번 저장 대상이 아닌 개인 기존 여덟 테이블의 내용 식별값과 행 개수를 읽습니다."""
    from psycopg import sql
    names = ("documents", "processing_runs", "parent_records", "chunks", "images", "record_images",
             "openai_embedding_runs", "openai_chunk_vectors")
    result = {}
    for name in names:
        query = sql.SQL("SELECT count(*) AS count, md5(string_agg(row_to_json(t)::text,'' ORDER BY row_to_json(t)::text)) AS hash FROM {} t").format(
            sql.Identifier("zzong_santafe_lag", name))
        result[name] = connection.execute(query).fetchone()
    return result


def store():
    """준비한 수정 버전만 원자적으로 저장하고 새 연결에서 대조한 뒤 활성화합니다."""
    from psycopg.types.json import Jsonb
    from pgvector.utils import Vector
    bundle = validate_bundle(json.loads(BUNDLE_FILE.read_text(encoding="utf-8")))
    preflight = json.loads((FOLDER / "preflight_20261006_v2.json").read_text(encoding="utf-8"))
    if not preflight["all_passed"] or preflight["revision_id"] != bundle["revision_id"]:
        raise ValueError("같은 수정 버전의 저장 전 확인을 통과하지 못했습니다.")
    revision_id = UUID(bundle["revision_id"])
    # [프로젝트 적용] 기존 SQL Mapper를 사용합니다. CREATE 대상도 개인 스키마의 새 두 테이블뿐입니다.
    manager = PersonalDatabaseManager()
    with manager.connect() as connection:
        before = legacy_fingerprint(connection)
        originals = connection.execute("SELECT record_id,content,raw_text FROM zzong_santafe_lag.parent_records WHERE run_id=%s AND record_id=ANY(%s)",
                                       (FULL_SOURCE.run_id, list(RECORD_IDS))).fetchall()
        original_by_id = {r["record_id"]: r for r in originals}
        replaced_count = connection.execute("SELECT count(*) AS count FROM zzong_santafe_lag.chunks c JOIN zzong_santafe_lag.parent_records p ON p.id=c.parent_id WHERE p.run_id=%s AND p.record_id=ANY(%s)",
                                            (FULL_SOURCE.run_id, list(RECORD_IDS))).fetchone()["count"]
        for r in bundle["payload"]["parents"]:
            old_parent = original_by_id[r["record_id"]]
            if (text_sha(old_parent["content"]) != bundle["payload"]["base_content_sha256"][r["record_id"]]
                    or old_parent["raw_text"] != r["raw_text"]):
                raise ValueError("수정안의 원래 부모·보존 원문이 현재 DB와 다릅니다.")
        connection.execute((Path(__file__).resolve().parent / "db/08_review_revisions.sql.txt").read_text(encoding="utf-8"))
    session = PersonalSqlSession()
    with session.transaction():
        old = session.select_one("review_revisions.get_revision", {"revision_id": revision_id})
        if old is not None:
            if old["status"] != "ready" or old["payload_sha256"] != bundle["payload_sha256"]:
                raise ValueError("기존 미완료/다른 저장 버전이 있습니다.")
        else:
            session.execute("review_revisions.insert_revision", {
                "id": revision_id, "source_run_id": FULL_SOURCE.run_id,
                "payload_sha256": bundle["payload_sha256"], "payload": Jsonb(bundle["payload"]),
                "chunk_count": len(bundle["chunks"])})
            parameters = [{"revision_id": revision_id, "record_id": c["record_id"], "content": c["content"],
                           "input_sha256": c["input_sha256"], "metadata": Jsonb(c["metadata"]),
                           "local_embedding": Vector(c["local_embedding"]), "openai_embedding": Vector(c["openai_embedding"])}
                          for c in bundle["chunks"]]
            session.execute_many("review_revisions.insert_chunk", parameters)
            session.execute("review_revisions.ready", {"revision_id": revision_id})
    read_session = PersonalSqlSession(read_only=True)
    with read_session.transaction():
        header = read_session.select_one("review_revisions.get_revision", {"revision_id": revision_id})
        chunks = read_session.select_list("review_revisions.get_chunks", {"revision_id": revision_id})
        sizes = read_session.select_list("review_revisions.sizes")
    saved = validate_bundle({"revision_id": str(revision_id), "payload": header["payload"],
                             "payload_sha256": header["payload_sha256"], "chunks": chunks})
    by_id = {c["record_id"]: c for c in bundle["chunks"]}
    for c in saved["chunks"]:
        for field in ("local_embedding", "openai_embedding"):
            if not np.array_equal(np.asarray(c[field], dtype=np.float32), np.asarray(by_id[c["record_id"]][field], dtype=np.float32)):
                raise ValueError("새 연결에서 읽은 벡터 값이 준비한 값과 다릅니다.")
    with PersonalDatabaseManager(read_only=True).connect() as connection:
        after = legacy_fingerprint(connection)
    if before != after or header["status"] != "ready":
        raise ValueError("기존 테이블의 값 또는 저장 완료 상태를 확인하세요. 활성화하지 않습니다.")
    result = {"revision_id": str(revision_id), "payload_sha256": bundle["payload_sha256"],
              "parents": len(bundle["payload"]["parents"]), "chunks": len(chunks), "image_links": len(bundle["payload"]["images"]),
              "replaced_base_chunks": replaced_count, "effective_chunk_count": FULL_SOURCE.chunk_count - replaced_count + len(chunks),
              "legacy_tables_unchanged": before == after, "vector_readback_equal": True,
              "new_table_bytes": sum(r["bytes"] for r in sizes if r["table_name"] in {"review_revisions", "review_revision_chunks"}),
              "personal_db_bytes": sum(r["bytes"] for r in sizes), "table_sizes": sizes,
              "db_written": True, "storage_uploaded": False}
    report = FOLDER / "db_saved_20261006.json"
    if not report.exists():
        write_new(report, result)
    # 새 DB 대조 성공 후에만 선택 파일을 바꿉니다. 임베딩 모델과 원본 run은 그대로입니다.
    pointer = {"revision_id": str(revision_id), "payload_sha256": bundle["payload_sha256"]}
    if ACTIVE_FILE.exists() and json.loads(ACTIVE_FILE.read_text(encoding="utf-8")) != pointer:
        raise ValueError("다른 활성 수정 버전이 있습니다. 임의로 대체하지 않습니다.")
    if not ACTIVE_FILE.exists():
        write_new(ACTIVE_FILE, pointer)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="개인 원문 검토 버전 준비/저장")
    parser.add_argument("action", choices=("prepare", "store"))
    args = parser.parse_args()
    try:
        value = prepare() if args.action == "prepare" else store()
        # 비밀키·벡터 전체는 표시하지 않습니다.
        print(json.dumps({k: value[k] for k in ("revision_id", "payload_sha256")}
                         if args.action == "prepare" else value, ensure_ascii=False, indent=2))
    except Exception as error:
        print(f"검토 버전 처리 중단: {type(error).__name__}. 인증 정보가 있을 수 있어 오류 전문은 숨깁니다.", flush=True)
        raise SystemExit(1) from None
