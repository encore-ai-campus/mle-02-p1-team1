"""로컬/OpenAI 검색에서 같은 방식으로 사용하던 프로젝트 확인·저장 벡터 정렬을 묶습니다."""

import os
import re
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
from dotenv import dotenv_values
from psycopg.conninfo import conninfo_to_dict

from .database import PersonalDatabaseManager


def checked_storage_url(config):
    """공개 그림 주소와 개인 DB의 프로젝트가 같은지 확인합니다. DB 연결이나 다운로드는 없습니다."""
    values = dict(dotenv_values(config.project_folder / ".env"))
    values.update(dotenv_values(Path(__file__).resolve().parent / ".env"))
    storage_url = os.environ.get("SUPABASE_URL") or values.get("SUPABASE_URL")
    if not storage_url:
        return storage_url
    parsed = urlparse(storage_url)
    host = parsed.hostname or ""
    project_ref = host.split(".")[0] if host.endswith(".supabase.co") else ""
    info = conninfo_to_dict(PersonalDatabaseManager(read_only=True)._dsn)
    same_project = project_ref and (info.get("host") == f"db.{project_ref}.supabase.co"
                                   or info.get("user", "").endswith("." + project_ref))
    if parsed.scheme != "https" or not same_project:
        raise ValueError("그림 주소와 개인 DB의 Supabase 프로젝트가 다릅니다.")
    return f"https://{host}"


def rank_stored_rows(question, vector, rows, chunks, embedder, counter, method, *, require_normalized=False):
    """읽어 둔 같은 모델의 벡터를 정렬해 검색 후보와 제외한 제목 개수를 반환합니다. 모델 호출은 없습니다."""
    from .retrieval import SearchEngine

    # [프로젝트 추가] 양쪽 검색의 기존 순서·점수·타입을 유지하며 같은 변환 코드를 공유합니다.
    usable = rows if method == "semantic" else [row for row in rows if
        re.sub(r"\s+", "", row["content"]) != re.sub(r"\s+", "", row["title"])]
    parent_ids = {row["record_id"] for row in usable}
    chunks = [row for row in chunks if row["metadata"]["parent_record_id"] in parent_ids]
    vectors = np.stack([row["embedding"] for row in chunks]).astype(np.float32)
    if vectors.shape != (len(chunks), embedder.dimension) or not np.isfinite(vectors).all():
        raise ValueError("저장한 벡터의 개수·차원·숫자가 올바르지 않습니다.")
    if require_normalized and not np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-5):
        raise ValueError("OpenAI 저장 벡터의 정규화가 다릅니다.")

    if method == "semantic":
        # OpenAI의 의미 검색은 기존처럼 부모당 최고 점수와 청크 ID 동점 순서를 유지합니다.
        best = {}
        titles = {row["record_id"]: row["title"] for row in rows}
        for chunk, score in zip(chunks, vectors @ vector):
            parent_id = chunk["metadata"]["parent_record_id"]
            hit = {"title": titles[parent_id], "parent_record_id": parent_id,
                   "chunk_record_id": chunk["record_id"], "chunk_content": chunk["content"], "similarity": float(score)}
            if parent_id not in best or score > best[parent_id]["similarity"]:
                best[parent_id] = hit
        return sorted(best.values(), key=lambda row: (-row["similarity"], row["chunk_record_id"])), len(rows) - len(usable)

    parents = [{"content": row["content"], "raw_text": row["raw_text"],
                "metadata": row["metadata"], "image_parts": []} for row in usable]
    records = [{"content": row["content"], "metadata": row["metadata"]} for row in chunks]
    engine = SearchEngine(parents, records, vectors, embedder.model, counter)
    ranked = engine.rank(question, vector, top_k=len(parents), use_specific_terms=method == "purpose_specific")
    vector_by_id = {row["record_id"]: vectors[index] for index, row in enumerate(chunks)}
    hits = []
    for hit in ranked:
        parent, chunk = hit["parent_record"]["metadata"], hit["matched_chunk"]
        chunk_id = chunk["metadata"]["record_id"]
        hits.append({"title": parent["title"], "parent_record_id": parent["record_id"],
                     "chunk_record_id": chunk_id, "chunk_content": chunk["content"],
                     "similarity": float(vector_by_id[chunk_id] @ vector), "ranking_score": hit["score"],
                     "routing": hit["routing"], "specific_bonus": hit["specific_bonus"], "specific_terms": hit["specific_terms"],
                     "used_fallback": hit["used_fallback"] and (
                         hit["preferred_candidate_count"] == len(parents) or len(hits) >= hit["preferred_candidate_count"])})
    return hits, len(rows) - len(usable)
