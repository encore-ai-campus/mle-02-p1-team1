"""검토한 싼타페 자료를 팀 공통 네 테이블에 추가합니다. 다른 차량은 수정하지 않습니다."""

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote, urlparse

import numpy as np
from dotenv import dotenv_values
from pgvector.utils import Vector
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

from .config import ManualConfig
from .database import PersonalSqlSession
from .openai_embedding import MODEL, DIMENSION, RECIPE
from .openai_migration import write_json
from .openai_search_service import active_embedding_run
from .review_revision import load_active, combine, text_sha
from .source_profile import FULL_SOURCE

# [프로젝트 추가] 공통 구조에는 검토 상태가 없어 확인한 자료만 내보냅니다.
# 현재 PDF에서 확인한 장별 목차 시작 쪽입니다. 다른 PDF에는 재사용하지 않습니다.
CHAPTERS = [(7, 0, "하이브리드 자동차 시작하기"), (29, 1, "안내 및 차량 정보"),
            (49, 2, "안전 및 주의 사항"), (63, 3, "시트 및 안전 장치"),
            (147, 4, "클러스터"), (183, 5, "편의 장치"), (379, 6, "시동 및 주행"),
            (461, 7, "운전자 보조"), (659, 8, "비상시 응급 조치"), (693, 9, "정기 점검")]
ACTOR = "zzong_santafe_lag"
TABLES = ("car", "car_manual_chapter", "car_manual_chunk", "car_manual_image")
REPORT_FOLDER = ManualConfig().project_folder / "data/zzong_santafe_lag/team_exports"


def root_settings():
    """사용자가 지정한 루트 .env의 DB_URL만 읽습니다. 비밀값은 출력하지 않습니다."""
    values = dotenv_values(ManualConfig().project_folder / ".env")
    dsn = values.get("DB_URL")
    if not dsn:
        raise ValueError("프로젝트 루트 .env에 DB_URL을 설정하세요.")
    # 기존 개인 DB와 같은 대상일 때만 원격 원문과 Storage 주소를 직접 재사용합니다.
    personal = PersonalSqlSession(read_only=True).database_manager._dsn
    if not personal or conninfo_to_dict(dsn) != conninfo_to_dict(personal):
        raise ValueError("팀 DB와 개인 DB 연결이 다릅니다. 별도 원문 이관 계획이 필요합니다.")
    combined = dict(values)
    combined.update(dotenv_values(Path(__file__).resolve().parent / ".env"))
    address = combined.get("SUPABASE_URL", "").rstrip("/")
    info = conninfo_to_dict(dsn)
    parsed = urlparse(address)
    ref = (parsed.hostname or "").split(".")[0]
    if (parsed.scheme != "https" or not (parsed.hostname or "").endswith(".supabase.co")
            or not (info.get("host") == f"db.{ref}.supabase.co" or info.get("user", "").endswith("." + ref))):
        raise ValueError("재사용할 Storage와 DB의 프로젝트가 다릅니다.")
    return dsn, address


def chapter_for(parent):
    """현재 PDF의 장 번호를 결정하고, 기존 원문 메타데이터와 대조합니다."""
    pages = parent["source_pages"]
    matches = [max((r for r in CHAPTERS if r[0] <= page), default=None) for page in pages]
    if not matches or any(r is None for r in matches) or len({r[1] for r in matches}) != 1:
        raise ValueError("하나의 장으로 분류할 수 없는 주제입니다.")
    _, number, name = matches[0]
    recorded = parent["metadata"].get("chapter_id")
    if recorded is not None and recorded != number:
        raise ValueError("장 번호가 원문 메타데이터와 다릅니다.")
    return str(number), f"{number}. {name}"


def prepare(session, address, year):
    """저장 완료된 같은 글·1536차원 벡터·검토 그림을 읽어 추가할 목록을 만듭니다."""
    embedding_id = active_embedding_run()
    if embedding_id is None:
        raise ValueError("활성 OpenAI 임베딩 저장 버전이 없습니다.")
    params = {"run_id": FULL_SOURCE.run_id}
    run = session.select_one("manual_store.get_run", params)
    embed_run = session.select_one("openai_vectors.get_run", {"embedding_run_id": embedding_id})
    document = session.select_one("manual_store.get_document", {"document_id": run["document_id"]}) if run else None
    if (not run or run["status"] != "ready" or not document
            or document["file_sha256"] != FULL_SOURCE.pdf_sha256
            or document["total_pages"] != FULL_SOURCE.page_count
            or run["settings"].get("input_manifest_sha256") != FULL_SOURCE.input_manifest_sha256):
        raise ValueError("승인한 PDF 원문 저장 버전이 아닙니다.")
    if (not embed_run or embed_run["status"] != "ready" or embed_run["source_run_id"] != FULL_SOURCE.run_id
            or embed_run["model_name"] != MODEL or embed_run["embedding_dimension"] != DIMENSION
            or embed_run["recipe"] != RECIPE or embed_run["settings"].get("normalized") is not True):
        raise ValueError("승인한 OpenAI 벡터 버전이 아닙니다.")
    parents = session.select_list("manual_store.get_run_parents", params)
    chunks = session.select_list("openai_vectors.get_vectors", {"embedding_run_id": embedding_id})
    images = session.select_list("manual_store.get_run_image_details", params)
    if len(parents) != FULL_SOURCE.parent_count or len(chunks) != FULL_SOURCE.chunk_count:
        raise ValueError("원문 또는 임베딩 개수가 다릅니다.")
    if any(c["input_sha256"] != c["content_sha256"] or text_sha(c["content"]) != c["input_sha256"] for c in chunks):
        raise ValueError("임베딩 입력 글이 저장 당시와 다릅니다.")
    revision = load_active(session)
    parents, chunks, images = combine(revision, parents, chunks, images, "openai")
    approved = {p["record_id"]: p for p in parents
                if p["verification_status"] in {"sample_verified", "visually_reviewed_source"}}
    if not approved:
        raise ValueError("검토 완료 자료가 없습니다.")
    for p in approved.values():
        if any(identity not in approved for identity in p["metadata"].get("required_context_record_ids", [])):
            raise ValueError("필수 각주·주의사항이 검토 범위에 없습니다.")
    chapters = dict(chapter_for(p) for p in approved.values())
    selected = []
    for c in chunks:
        parent_id = c["metadata"]["parent_record_id"]
        if parent_id not in approved:
            continue
        vector = np.asarray(c["embedding"], dtype=np.float32)
        if vector.shape != (DIMENSION,) or not np.isfinite(vector).all() or not np.isclose(np.linalg.norm(vector), 1, atol=1e-5):
            raise ValueError("벡터 크기·숫자·정규화가 잘못되었습니다.")
        number, _ = chapter_for(approved[parent_id])
        selected.append({"source_record_id": c["record_id"], "parent_record_id": parent_id,
                         "chunk_index": c["metadata"]["chunk_index"],
                         "chapter_no": number, "pdf_page": c["metadata"]["pdf_page_number"],
                         "source_pages": c["metadata"]["source_pages"], "content": c["content"],
                         "embedding": vector, "vector_sha256": hashlib.sha256(vector.tobytes()).hexdigest()})
    # 같은 장에서 같은 파일은 한 번만 등록하고, 주제별 대응 정보는 별도 대응표에 유지합니다.
    selected_images = {}
    for image in images:
        pid = image["parent_record_id"]
        if pid not in approved or image["linkage_status"] not in {"sample_linked", "visually_verified"}:
            continue
        prefix = f"cars/hyundai/santafe_hev/zzong_santafe_lag/{FULL_SOURCE.pdf_sha256}/"
        if (image["upload_status"] != "uploaded" or image["storage_bucket"] != "images"
                or not image["storage_path"].startswith(prefix) or not image["description"]):
            raise ValueError("검토 그림의 업로드 상태·개인 경로·설명을 확인하세요.")
        number, _ = chapter_for(approved[pid])
        key = (number, str(image["id"]))
        item = selected_images.setdefault(key, {"source_image_id": str(image["id"]), "chapter_no": number,
            "pdf_page": image["pdf_page_number"], "url": address + "/storage/v1/object/public/images/" + quote(image["storage_path"], safe="/"),
            "descriptions": [], "parent_record_ids": []})
        if image["description"] not in item["descriptions"]:
            item["descriptions"].append(image["description"])
        if pid not in item["parent_record_ids"]:
            item["parent_record_ids"].append(pid)
    # 10번을 2번 앞에 놓는 문자열 정렬을 피하고 원래 자식 청크의 숫자 순서를 유지합니다.
    selected.sort(key=lambda c: (int(c["chapter_no"]), c["pdf_page"], c["parent_record_id"], c["chunk_index"]))
    image_list = sorted(selected_images.values(), key=lambda i: (int(i["chapter_no"]), i["pdf_page"], i["source_image_id"]))
    for items in (selected, image_list):
        counters = defaultdict(int)
        for item in items:
            counters[item["chapter_no"]] += 1
            item["order"] = counters[item["chapter_no"]]
    plan = {"car_model_yr": year, "year_basis": "사용자 확인: 2024년 이후 생산형의 기준 연도; 정확한 모델 연식 별도 확인",
            "source_run_id": str(FULL_SOURCE.run_id), "pdf_sha256": FULL_SOURCE.pdf_sha256,
            "embedding_run_id": str(embedding_id), "review_revision_id": revision["revision_id"] if revision else None,
            "model": MODEL, "dimension": DIMENSION, "scope": "reviewed_only", "parent_count": len(approved),
            "pending_parent_count": len(parents) - len(approved), "chapters": chapters,
            "parents": [{"record_id": p["record_id"], "source_pages": p["source_pages"],
                         "required_context_record_ids": p["metadata"].get("required_context_record_ids", [])} for p in approved.values()],
            "chunks": [{k: v for k, v in c.items() if k != "embedding"} for c in selected], "images": image_list}
    plan["plan_sha256"] = text_sha(json.dumps(plan, ensure_ascii=False, sort_keys=True))
    return plan, selected, image_list


def fingerprint_other_rows(connection):
    """다른 작성자의 공통 행을 읽기만 하고, 변경 감지용 식별값과 건수를 계산합니다."""
    result = {}
    for table in TABLES:
        result[table] = connection.execute(sql.SQL(
            "SELECT count(*) AS count, md5(coalesce(string_agg(row_to_json(t)::text, '' ORDER BY row_to_json(t)::text), '')) AS digest "
            "FROM public.{} t WHERE create_user_id IS DISTINCT FROM %s"
        ).format(sql.Identifier(table)), (ACTOR,)).fetchone()
    return result


def readback(connection, car_id, plan, chunks, images):
    """자기 차량의 행만 다시 읽어 본문·벡터·URL·장 연결을 모두 대조합니다."""
    car = connection.execute("SELECT * FROM public.car WHERE car_id=%s", (car_id,)).fetchone()
    if not car or any(car[k] != v for k, v in {"car_brand_nm": "현대", "car_brand_eng_nm": "hyundai",
            "car_nm": "싼타페 HEV", "car_eng_nm": "santafe_hev", "car_model_yr": plan["car_model_yr"],
            "create_user_id": ACTOR, "update_user_id": ACTOR}.items()):
        raise ValueError("차량 또는 소유자가 저장 계획과 다릅니다.")
    chapters = connection.execute("SELECT * FROM public.car_manual_chapter WHERE car_id=%s", (car_id,)).fetchall()
    lookup = {r["car_manual_chapter_no"]: r for r in chapters}
    if len(chapters) != len(plan["chapters"]) or set(lookup) != set(plan["chapters"]):
        raise ValueError("장 목록이 저장 계획과 다릅니다.")
    for number, r in lookup.items():
        if r["car_manual_chapter_nm"] != plan["chapters"][number] or r["car_manual_chapter_sort_no"] != int(number) or r["create_user_id"] != ACTOR or r["update_user_id"] != ACTOR:
            raise ValueError("목차 내용·소유자가 다릅니다.")
    chunk_rows = connection.execute("SELECT * FROM public.car_manual_chunk WHERE car_id=%s", (car_id,)).fetchall()
    image_rows = connection.execute("SELECT * FROM public.car_manual_image WHERE car_id=%s", (car_id,)).fetchall()
    mappings = {}
    for rows, expected, prefix in ((chunk_rows, chunks, "chunk"), (image_rows, images, "image")):
        if len(rows) != len(expected):
            raise ValueError("저장한 청크 또는 그림 개수가 다릅니다. 기존 자료는 변경하지 않습니다.")
        indexed = {(r["car_manual_chapter_id"], r[f"car_manual_{prefix}_no"]): r for r in rows}
        for item in expected:
            r = indexed.get((lookup[item["chapter_no"]]["car_manual_chapter_id"], item["order"]))
            if not r or r["create_user_id"] != ACTOR or r["update_user_id"] != ACTOR or r[f"car_manual_{prefix}_page_no"] != item["pdf_page"]:
                raise ValueError("쪽수·순번·소유자가 다릅니다.")
            if prefix == "chunk":
                if r["car_manual_chunk_txt"] != item["content"] or not np.array_equal(r["car_manual_chunk_embed_vec"], item["embedding"]):
                    raise ValueError("본문 또는 임베딩 벡터가 다릅니다.")
                identity = item["source_record_id"]
            else:
                if r["car_manual_image_url"] != item["url"] or r["car_manual_image_desc"] != "\n".join(item["descriptions"]):
                    raise ValueError("그림 주소 또는 설명이 다릅니다.")
                identity = item["chapter_no"] + ":" + item["source_image_id"]
            mappings[identity] = r[f"car_manual_{prefix}_id"]
    return {"chapter_ids": {n: r["car_manual_chapter_id"] for n, r in lookup.items()}, "item_ids": mappings,
            "counts": {"car": 1, "car_manual_chapter": len(chapters), "car_manual_chunk": len(chunk_rows), "car_manual_image": len(image_rows)}}


def save(session, plan, chunks, images):
    """같은 차량의 중복 실행만 잠그고 INSERT만 수행합니다. UPDATE·DELETE·DDL은 없습니다."""
    connection = session.database_manager.connection
    connection.execute("SET LOCAL search_path TO pg_catalog, public")
    connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"{ACTOR}:santafe_hev:{plan['car_model_yr']}",))
    before = fingerprint_other_rows(connection)
    existing = connection.execute("SELECT car_id,create_user_id FROM public.car WHERE car_brand_eng_nm='hyundai' AND car_eng_nm='santafe_hev' AND car_model_yr=%s", (plan["car_model_yr"],)).fetchall()
    if existing:
        if len(existing) != 1 or existing[0]["create_user_id"] != ACTOR:
            raise ValueError("같은 차량에 다른 작성자의 자료가 있습니다. 덮어쓰지 않고 중단합니다.")
        car_id, mode = existing[0]["car_id"], "existing_verified"
        mapping = readback(connection, car_id, plan, chunks, images)
    else:
        car_id = connection.execute("INSERT INTO public.car (car_id,car_brand_nm,car_brand_eng_nm,car_nm,car_eng_nm,car_model_yr,create_user_id,update_user_id) VALUES(public.fn_get_biz_id('car'),'현대','hyundai','싼타페 HEV','santafe_hev',%s,%s,%s) RETURNING car_id", (plan["car_model_yr"],ACTOR,ACTOR)).fetchone()["car_id"]
        chapter_ids = {}
        for number, name in sorted(plan["chapters"].items(), key=lambda kv: int(kv[0])):
            chapter_ids[number] = connection.execute("INSERT INTO public.car_manual_chapter (car_id,car_manual_chapter_id,car_manual_chapter_no,car_manual_chapter_nm,car_manual_chapter_sort_no,create_user_id,update_user_id) VALUES(%s,public.fn_get_biz_id('car_manual_chapter'),%s,%s,%s,%s,%s) RETURNING car_manual_chapter_id", (car_id,number,name,int(number),ACTOR,ACTOR)).fetchone()["car_manual_chapter_id"]
        with connection.cursor() as cursor:
            cursor.executemany("INSERT INTO public.car_manual_chunk (car_id,car_manual_chapter_id,car_manual_chunk_id,car_manual_chunk_page_no,car_manual_chunk_no,car_manual_chunk_txt,car_manual_chunk_embed_vec,create_user_id,update_user_id) VALUES(%s,%s,public.fn_get_biz_id('car_manual_chunk'),%s,%s,%s,%s,%s,%s)", [(car_id,chapter_ids[c["chapter_no"]],c["pdf_page"],c["order"],c["content"],Vector(c["embedding"]),ACTOR,ACTOR) for c in chunks])
            cursor.executemany("INSERT INTO public.car_manual_image (car_id,car_manual_chapter_id,car_manual_image_id,car_manual_image_page_no,car_manual_image_no,car_manual_image_url,car_manual_image_desc,create_user_id,update_user_id) VALUES(%s,%s,public.fn_get_biz_id('car_manual_image'),%s,%s,%s,%s,%s,%s)", [(car_id,chapter_ids[i["chapter_no"]],i["pdf_page"],i["order"],i["url"],"\n".join(i["descriptions"]),ACTOR,ACTOR) for i in images])
        mapping, mode = readback(connection, car_id, plan, chunks, images), "inserted"
    after = fingerprint_other_rows(connection)
    if after != before:
        raise ValueError("다른 작성자 행의 변경이 감지되어 이번 거래를 취소합니다. 동시 작업 여부를 확인하세요.")
    # 공통 테이블 전체 크기는 팀원 자료를 포함하므로 내 행의 논리 크기만 합산합니다.
    sizes = {}
    for table in TABLES:
        columns = connection.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position", (table,)).fetchall()
        # TOAST에 따로 저장된 벡터도 포함하려고 행 포인터 대신 각 칼럼 값을 합칩니다.
        terms = sql.SQL(" + ").join(sql.SQL("coalesce(pg_column_size(t.{}),0)").format(sql.Identifier(c["column_name"])) for c in columns)
        sizes[table] = connection.execute(sql.SQL("SELECT coalesce(sum({}),0)::bigint AS bytes FROM public.{} t WHERE car_id=%s").format(terms, sql.Identifier(table)), (car_id,)).fetchone()["bytes"]
    return {"car_id": car_id, "mode": mode, **mapping, "other_authors_unchanged": True,
            "other_authors_fingerprint": after, "logical_row_bytes": sizes,
            "logical_total_bytes": sum(sizes.values()), "storage_uploaded_files": 0,
            "size_scope": "내 칼럼 값의 저장 크기 합계(TOAST 값 포함); 행 헤더·인덱스·페이지 여유·WAL 제외. Storage 파일 재사용"}


def main():
    """plan은 읽기·계획 저장, save는 승인한 자기 자료 추가·별도 연결 재조회를 실행합니다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "save"))
    parser.add_argument("--year", type=int, required=True)
    args = parser.parse_args()
    if not 2000 <= args.year <= 2100:
        raise ValueError("연식 숫자를 확인하세요.")
    dsn, address = root_settings()
    reader = PersonalSqlSession(dsn, read_only=True)
    with reader.transaction():
        plan, chunks, images = prepare(reader, address, args.year)
    target = REPORT_FOLDER / f"santafe_hev_{args.year}_{plan['plan_sha256'][:12]}"
    write_json(target.with_suffix(".plan.json"), plan)
    summary = {"parent_count": plan["parent_count"], "chapter_count": len(plan["chapters"]),
               "chunk_count": len(chunks), "image_count": len(images), "plan_file": str(target.with_suffix(".plan.json"))}
    print(json.dumps(summary, ensure_ascii=False))
    if args.action == "plan":
        return
    writer = PersonalSqlSession(dsn)
    with writer.transaction():
        result = save(writer, plan, chunks, images)
    # [프로젝트 추가] COMMIT 후 새 읽기 전용 연결에서 실제 저장 결과를 재확인합니다.
    with reader.transaction():
        checked = readback(reader.database_manager.connection, result["car_id"], plan, chunks, images)
    if checked["counts"] != result["counts"] or checked["item_ids"] != result["item_ids"]:
        raise ValueError("저장 후 별도 연결의 조회 결과가 다릅니다.")
    result.update(plan_sha256=plan["plan_sha256"], source_run_id=plan["source_run_id"],
                  review_revision_id=plan["review_revision_id"], model=MODEL, dimension=DIMENSION,
                  scope=plan["scope"], parent_count=plan["parent_count"], commit_readback_verified=True)
    write_json(target.with_suffix(".result.json"), result)
    print(json.dumps({k: v for k, v in result.items() if k not in {"item_ids", "other_authors_fingerprint"}}, ensure_ascii=False))
    print("저장 결과 파일:", target.with_suffix(".result.json"))


if __name__ == "__main__":
    main()
