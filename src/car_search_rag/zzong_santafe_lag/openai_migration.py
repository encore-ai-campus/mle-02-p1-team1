"""준비 → 소량 임베딩 → 전체 임베딩 → 별도 DB 저장을 명시적으로 실행합니다."""

import argparse
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter
from uuid import UUID, uuid4

import numpy as np
from pgvector.utils import Vector
from psycopg.types.json import Jsonb

from .config import ManualConfig
from .database import PersonalSqlSession, PersonalDatabaseManager
from .db_search_service import DbFullSearchService
from .openai_embedding import MODEL, DIMENSION, RECIPE, OpenAIEmbedder, OpenAITokenCounter
from .source_profile import FULL_SOURCE

# 이전 실행 파일·노트북의 import 이름은 유지하고 실제 값은 한곳에서 읽습니다.
SOURCE_RUN_ID = FULL_SOURCE.run_id
PRIVATE_FOLDER = Path(__file__).resolve().parent
OUTPUT_FOLDER = ManualConfig().project_folder / "data/zzong_santafe_lag/openai_embeddings"


def json_default(value):
    """UUID·일시·벡터를 비밀 연결 정보 없이 JSON으로 변환합니다."""
    if isinstance(value, np.ndarray):
        return value.tolist()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def digest(value):
    """순서와 글 내용이 같을 때 같은 식별값을 만드는 함수입니다."""
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=json_default)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_json(path, value):
    """완성한 파일만 교체해 중단 중 반쪽 JSON이 남지 않게 합니다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=json_default), encoding="utf-8")
    os.replace(temporary, path)


def read_source(session):
    """승인한 기존 전체 작업을 읽고 원문·기존 벡터·그림의 상태 식별값을 계산합니다."""
    params = {"run_id": SOURCE_RUN_ID}
    run = session.select_one("manual_store.get_run", params)
    if run is None:
        raise ValueError("기존 전체 저장 작업을 찾지 못했습니다.")
    document = session.select_one("manual_store.get_document", {"document_id": run["document_id"]})
    counts = session.select_one("manual_store.get_run_search_counts", params)
    DbFullSearchService(SOURCE_RUN_ID).validate_source(run, document, counts)
    inputs = session.select_list("openai_vectors.get_inputs", params)
    # [프로젝트 추가] 실제 저장된 모델 입력 글을 그대로 재사용합니다. 제목을 다시 붙이지 않습니다.
    if any(hashlib.sha256(row["content"].encode("utf-8")).hexdigest() != row["content_sha256"] for row in inputs):
        raise ValueError("저장된 청크의 글과 SHA-256이 다릅니다.")
    state = {"document": document, "run": run}
    for name in ("parents", "chunks", "images", "image_links"):
        state[name] = session.select_list("manual_store.get_run_" + name, params)
    # 이미지 조회 SQL에는 정렬이 없으므로 행을 ID로 정렬한 뒤 비교합니다.
    for name in ("images", "image_links"):
        state[name].sort(key=lambda row: digest(row))
    return inputs, digest(state)


def make_manifest(inputs, counter):
    """모델·차원·처리 규칙과 청크별 입력을 고정합니다. 토큰 초과는 자동 축약하지 않습니다."""
    rows = [{"chunk_id": str(row["id"]), "record_id": row["record_id"],
             "input_sha256": row["content_sha256"], "token_count": counter.count(row["content"])} for row in inputs]
    if len(rows) != FULL_SOURCE.chunk_count or any(not 1 <= row["token_count"] <= counter.budget for row in rows):
        raise ValueError("2213개 청크 또는 OpenAI 입력 한도를 확인하세요.")
    return {"source_run_id": str(SOURCE_RUN_ID), "model_name": MODEL, "dimension": DIMENSION,
            "recipe": RECIPE, "token_encoding": "cl100k_base", "rows": rows}


def prepare():
    """DB를 읽기만 하고 비용·입력 수·저장 위치를 준비합니다. 임베딩 API 호출은 없습니다."""
    counter = OpenAITokenCounter()
    session = PersonalSqlSession(read_only=True)
    with session.transaction():
        inputs, state_hash = read_source(session)
    manifest = make_manifest(inputs, counter)
    manifest_hash = digest(manifest)
    folder = OUTPUT_FOLDER / manifest_hash
    path = folder / "plan.json"
    if path.exists():
        plan = json.loads(path.read_text(encoding="utf-8"))
        if plan["manifest"] != manifest or plan["source_state_sha256"] != state_hash:
            raise ValueError("기존 준비 이후 원문 또는 연결 정보가 바뀌었습니다. 먼저 차이를 확인하세요.")
    else:
        tokens = sum(row["token_count"] for row in manifest["rows"])
        plan = {"manifest": manifest, "manifest_sha256": manifest_hash,
                "embedding_run_id": str(uuid4()), "source_state_sha256": state_hash,
                "estimated_input_tokens": tokens, "estimated_document_cost_usd": tokens * 0.02 / 1000000,
                "price_note": "일반 API 입력 $0.02/백만 토큰 기준 추정; 실제 청구·질문 비용은 별도",
                "input_recipe": "기존 chunks.content 전체를 수정 없이 사용", "db_written": False}
        write_json(path, plan)
    write_json(OUTPUT_FOLDER / "prepared_plan.json", {"manifest_sha256": manifest_hash})
    return {"plan_path": str(path), "chunk_count": len(inputs), "dimension": DIMENSION,
            "model": MODEL, "max_input_tokens": max(row["token_count"] for row in manifest["rows"]),
            "estimated_input_tokens": plan["estimated_input_tokens"],
            "estimated_document_cost_usd": plan["estimated_document_cost_usd"],
            "api_called": False, "db_written": False}


def load_plan():
    """개인 준비 파일을 읽고 경로·입력 식별값이 올바른지 확인합니다."""
    pointer = json.loads((OUTPUT_FOLDER / "prepared_plan.json").read_text(encoding="utf-8"))
    manifest_hash = pointer["manifest_sha256"]
    if len(manifest_hash) != 64 or any(c not in "0123456789abcdef" for c in manifest_hash):
        raise ValueError("준비한 입력 식별값이 올바르지 않습니다.")
    folder = OUTPUT_FOLDER / manifest_hash
    plan = json.loads((folder / "plan.json").read_text(encoding="utf-8"))
    if digest(plan["manifest"]) != manifest_hash or plan["manifest_sha256"] != manifest_hash:
        raise ValueError("준비한 입력 목록이 변경되었습니다.")
    return plan, folder


def load_batches(plan, folder):
    """성공한 구간만 읽어 순서·청크 ID·정규화를 확인합니다. 실패 구간은 완료로 세지 않습니다."""
    vectors, completed = [], 0
    rows = plan["manifest"]["rows"]
    for path in sorted(folder.glob("batch_*.npz")):
        with np.load(path, allow_pickle=False) as saved:
            start, end = int(saved["start"]), int(saved["end"])
            batch = saved["vectors"]
            if (start != completed or not start < end <= len(rows)
                    or str(saved["manifest"]) != plan["manifest_sha256"]
                    or list(saved["chunk_ids"]) != [row["chunk_id"] for row in rows[start:end]]
                    or batch.shape != (end - start, DIMENSION) or not np.isfinite(batch).all()
                    or not np.allclose(np.linalg.norm(batch, axis=1), 1.0, atol=1e-5)):
                raise ValueError("중간 저장의 구간·청크 순서·벡터가 다릅니다.")
            vectors.append(batch.copy())
            completed = end
    return np.concatenate(vectors) if vectors else np.empty((0, DIMENSION), dtype=np.float32)


def embed(*, sample=False, progress=print):
    """소량 16개 또는 나머지 전체를 API로 처리합니다. 성공 구간을 저장해 재실행 때 재사용합니다."""
    plan, folder = load_plan()
    session = PersonalSqlSession(read_only=True)
    with session.transaction():
        inputs, state_hash = read_source(session)
    counter = OpenAITokenCounter()
    if make_manifest(inputs, counter) != plan["manifest"] or state_hash != plan["source_state_sha256"]:
        raise ValueError("준비 이후 기존 자료가 변경되었습니다.")
    saved = load_batches(plan, folder)
    target = 16 if sample else len(inputs)
    completed = len(saved)
    if not sample and completed < 16:
        raise ValueError("먼저 sample 단계로 16개 결과를 확인하세요.")
    embedder = OpenAIEmbedder(counter) if completed < target else None
    started = perf_counter()
    while completed < target:
        end = min(completed + 64, target)
        try:
            batch = embedder.embed_texts([row["content"] for row in inputs[completed:end]])
            temporary = folder / "batch.tmp"
            with temporary.open("wb") as stream:
                np.savez_compressed(stream, start=completed, end=end, vectors=batch,
                                    chunk_ids=[str(row["id"]) for row in inputs[completed:end]],
                                    manifest=plan["manifest_sha256"])
            os.replace(temporary, folder / f"batch_{completed:05d}_{end:05d}.npz")
        except Exception as error:
            # 오류 내용에는 키·연결 주소가 섞일 수 있어 종류만 기록합니다. 무조건 자동 재시도하지 않습니다.
            write_json(folder / "last_failure.json", {"start": completed, "end": end,
                       "error_type": type(error).__name__, "api_outcome_may_be_unknown": True})
            raise RuntimeError(f"임베딩 {completed}~{end} 구간 실패: {type(error).__name__}") from None
        completed = end
        write_json(folder / "progress.json", {"completed": completed, "total": len(inputs),
                   "elapsed_seconds_this_execution": perf_counter() - started, "failure_count_this_execution": 0})
        if progress:
            progress(f"OpenAI 임베딩 {completed}/{len(inputs)} | 이번 실행 {perf_counter()-started:.1f}초")
    return {"completed": completed, "total": len(inputs), "dimension": DIMENSION,
            "elapsed_seconds_this_execution": perf_counter() - started, "checkpoint_folder": str(folder),
            "db_written": False, "sample": sample}


def save():
    """완료한 새 벡터만 개인 DB에 추가하고 실제 조회 결과를 대조한 뒤 ready로 표시합니다."""
    plan, folder = load_plan()
    vectors = load_batches(plan, folder)
    if vectors.shape != (FULL_SOURCE.chunk_count, DIMENSION):
        raise ValueError("전체 임베딩을 먼저 마무리하세요.")
    manager = PersonalDatabaseManager()
    connection = manager.connect()
    try:
        connection.execute((PRIVATE_FOLDER / "db/06_openai_vectors.sql.txt").read_text(encoding="utf-8"))
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()
    session = PersonalSqlSession()
    run_id = UUID(plan["embedding_run_id"])
    with session.transaction():
        inputs, before = read_source(session)
        if before != plan["source_state_sha256"]:
            raise ValueError("기존 자료가 바뀌어 저장을 중단합니다.")
        existing = session.select_one("openai_vectors.find_run", {
            "source_run_id": SOURCE_RUN_ID, "manifest": plan["manifest_sha256"]})
        if existing:
            run_id = existing["id"]
            if existing["status"] != "ready":
                raise ValueError("동일 입력의 미완료 DB 작업을 먼저 확인하세요.")
        else:
            session.execute("openai_vectors.insert_run", {
                "id": run_id, "source_run_id": SOURCE_RUN_ID, "model_name": MODEL,
                "embedding_dimension": DIMENSION, "recipe": RECIPE, "manifest": plan["manifest_sha256"],
                "chunk_count": len(inputs), "settings": Jsonb({"normalized": True, "token_encoding": "cl100k_base",
                    "token_budget": 8191, "estimated_input_tokens": plan["estimated_input_tokens"],
                    "source_state_sha256": before, "chunking_changed": False, "image_pixels_embedded": False})})
            params = [{"embedding_run_id": run_id, "chunk_id": UUID(row["chunk_id"]),
                       "input_sha256": row["input_sha256"], "token_count": row["token_count"],
                       "embedding": Vector(vectors[index])} for index, row in enumerate(plan["manifest"]["rows"])]
            session.execute_many("openai_vectors.insert_vector", params)
        stored = session.select_list("openai_vectors.get_vectors", {"embedding_run_id": run_id})
        if (len(stored) != len(inputs) or [str(row["id"]) for row in stored] != [str(row["id"]) for row in inputs]
                or any(row["input_sha256"] != row["content_sha256"] for row in stored)
                or not np.array_equal(np.stack([row["embedding"] for row in stored]), vectors)):
            raise ValueError("DB에서 읽은 벡터·입력·순서가 중간 저장과 다릅니다. 추가 저장을 취소합니다.")
        if read_source(session)[1] != before:
            raise ValueError("기존 원문·로컬 벡터·그림 상태가 변경되었습니다.")
        if not existing:
            session.execute("openai_vectors.mark_ready", {"embedding_run_id": run_id})
        final_run = session.select_one("openai_vectors.get_run", {"embedding_run_id": run_id})
        if final_run["status"] != "ready":
            raise ValueError("검색 준비 완료 상태가 아닙니다.")
        sizes = session.select_list("openai_vectors.sizes")
    result = {"source_run_id": str(SOURCE_RUN_ID), "embedding_run_id": str(run_id),
              "model": MODEL, "dimension": DIMENSION, "vector_count": len(stored),
              "source_unchanged": True, "images_reuploaded": False, "tables": sizes}
    write_json(folder / "db_save_result.json", result)
    # [프로젝트 추가] 확인한 버전만 화면의 기본 검색으로 선택합니다. 기존 버전은 삭제하지 않습니다.
    write_json(OUTPUT_FOLDER / "active_run.json", {"source_run_id": str(SOURCE_RUN_ID),
               "embedding_run_id": str(run_id), "model": MODEL, "dimension": DIMENSION})
    return result


def main():
    """사용자가 선택한 단계 하나만 실행합니다. import만으로 유료 처리가 시작되지 않습니다."""
    parser = argparse.ArgumentParser(description="개인 OpenAI 임베딩 전환")
    parser.add_argument("step", choices=["prepare", "sample", "embed", "save"])
    args = parser.parse_args()
    actions = {"prepare": prepare, "sample": lambda: embed(sample=True), "embed": embed, "save": save}
    try:
        print(json.dumps(actions[args.step](), ensure_ascii=False, indent=2, default=json_default))
    except Exception as error:
        print(f"단계 중단: {type(error).__name__}. 설정·네트워크·개인 실패 기록을 확인하세요.")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
