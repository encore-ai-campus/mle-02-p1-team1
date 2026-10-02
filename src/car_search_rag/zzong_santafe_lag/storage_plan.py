"""전체 자료의 저장 범위와 추가 검토 목록을 집계합니다. DB에 쓰지 않습니다."""

# [프로젝트 추가] 자동 초안을 검토 완료로 바꾸지 않고 현재 상태를 집계합니다.
# 그림 키 목록만 비교하며 전체 그림을 추출·업로드하거나 임베딩하지 않습니다.

import json
from collections import Counter

from .config import ManualConfig, SAMPLE_RUN_ID
from .database import ManualRepository, PersonalSqlSession
from .db_rows import file_sha256
from .manual_service import ManualService


FLAG_LABELS = {
    "heading_not_confirmed": "제목 경계 확인 필요",
    "footer_not_confirmed": "인쇄 쪽수·꼬리말 확인 필요",
    "ambiguous_footer_candidate_needs_review": "쪽수 후보가 모호함",
    "detached_number_or_letter_labels_needs_review": "따로 추출된 번호·문자 확인 필요",
    "long_topic_boundary_needs_review": "긴 주제의 분할 경계 확인 필요",
    "thin_topic_needs_review": "검색 글이 짧음",
    "table_or_navigation_structure_needs_review": "표·안내 목록의 행과 열 확인 필요",
    "font_symbol_needs_review": "깨진 글꼴 기호 확인 필요",
    "warning_boundary_needs_review": "경고와 설명의 연결 경계 확인 필요",
    "page_level_image_linkage_needs_review": "그림과 주제가 페이지 수준으로만 연결됨",
}


def image_identity(part, service, name_cache):
    """쪽수와 PDF 내부 키로 그림을 구별합니다. 이름만 있는 예제는 해당 쪽에서 대조합니다."""
    number = part["pdf_page_number"]
    key = part.get("pdf_image_key")
    if key is None:
        # [프로젝트 적용] 이미 확인한 예제 몇 쪽만 이름→키를 대조합니다.
        # 자동 초안은 내부 키가 있으므로 864개 그림의 픽셀을 전부 읽지 않습니다.
        if number not in name_cache:
            page_images = service.inventory["reader"].pages[number - 1].images
            mapping = {}
            for candidate in page_images.keys():
                mapping.setdefault(page_images[candidate].name, []).append(candidate)
            name_cache[number] = mapping
        candidates = name_cache[number].get(part.get("name"), [])
        if len(candidates) != 1:
            raise ValueError("예제 그림의 이름과 PDF 내부 키를 대조해야 합니다.")
        key = candidates[0]
    # 중첩 키인 튜플과 DB JSON 목록을 같은 표현으로 비교합니다.
    return number, json.dumps(key, ensure_ascii=False, separators=(",", ":"))


def build_storage_plan(progress=print):
    """현재 PDF·개인 DB를 읽고 저장 제안과 검토 후보 목록을 반환합니다. 저장은 하지 않습니다."""
    repository = ManualRepository(PersonalSqlSession(read_only=True))
    with repository.session.transaction():
        run = repository.session.select_one("manual_store.get_run", {"run_id": SAMPLE_RUN_ID})
        if run is None or run["status"] != "ready":
            raise ValueError("완료한 개인 DB 표본을 먼저 확인하세요.")
        document = repository.session.select_one("manual_store.get_document", {"document_id": run["document_id"]})
        db_parents = repository.session.select_list("manual_store.get_run_parents", {"run_id": SAMPLE_RUN_ID})
        db_images = repository.session.select_list("manual_store.get_run_images", {"run_id": SAMPLE_RUN_ID})
        counts = repository.session.select_list("manual_store.personal_table_counts")
        sizes = repository.session.select_list("manual_store.personal_table_sizes")
        connection = repository.session.select_one("manual_store.connection_info")
    if document is None or connection["read_only"] != "on":
        raise ValueError("개인 PDF 정보와 읽기 전용 연결 상태를 확인하세요.")
    config = ManualConfig(model_name=run["model_name"], model_revision=run["model_revision"])
    if file_sha256(config.pdf_path) != document["file_sha256"]:
        raise ValueError("현재 PDF가 저장했던 원본과 다릅니다. 저장 범위를 다시 검토하세요.")
    service = ManualService(config).prepare(progress=progress)
    if (service.token_counter.model_revision != run["model_revision"]
            or service.token_counter.budget != run["token_budget"]
            or run["embedding_dimension"] != 768 or not run["normalized"]):
        raise ValueError("전체 자료와 표본의 모델·토큰 한도·차원을 확인하세요.")
    lookup = {record["metadata"]["record_id"]: record for record in service.parents}
    for row in db_parents:
        current = lookup.get(row["record_id"])
        if current is None or any(current[field] != row[field] for field in ("content", "raw_text")):
            raise ValueError("전체 자료의 표본 원문이 이미 저장한 글과 다릅니다.")

    # [프로젝트 추가] 그림 파일 수와 주제↔그림 연결 수는 다릅니다.
    # 같은 그림이 두 주제에 연결돼도 고유 그림은 한 개로 셉니다.
    name_cache, image_ids, links = {}, set(), set()
    links_with_description, links_without_description = 0, 0
    flags, statuses, page_roles = Counter(), Counter(), Counter()
    chunk_counts = Counter(chunk["metadata"]["parent_record_id"] for chunk in service.chunks)
    review_items = []
    for record in service.parents:
        meta = record["metadata"]
        record_id = meta["record_id"]
        statuses[meta["verification_status"]] += 1
        flags.update(set(meta.get("review_flags", [])))
        for part in record["image_parts"]:
            identity = image_identity(part, service, name_cache)
            image_ids.add(identity)
            link = (record_id, identity)
            if link in links:
                raise ValueError("같은 주제와 그림 연결이 중복되었습니다.")
            links.add(link)
            if part.get("description") and part["description"].strip():
                links_with_description += 1
            else:
                links_without_description += 1
        if meta["verification_status"] == "auto_draft_needs_review":
            # [프로젝트 추가] 검토 순서 제안용 규칙입니다. 검색 점수나 오류 판정이 아닙니다.
            # 표 구조·기호·경고 경계·긴 구간을 먼저 살펴보도록 가중치를 둡니다.
            weights = {"table_or_navigation_structure_needs_review": 5, "font_symbol_needs_review": 5,
                       "warning_boundary_needs_review": 5, "long_topic_boundary_needs_review": 3,
                       "heading_not_confirmed": 2, "ambiguous_footer_candidate_needs_review": 2,
                       "detached_number_or_letter_labels_needs_review": 1}
            priority = sum(weights.get(flag, 0) for flag in set(meta.get("review_flags", [])))
            review_items.append({"record_id": record_id, "title": meta["title"],
                "source_pages": meta["source_pages"], "manual_page_number": meta["manual_page_number"],
                "content_chars": len(record["content"]), "chunks": chunk_counts[record_id],
                "image_links": len(record["image_parts"]), "review_flags": meta.get("review_flags", []),
                "review_reasons": [FLAG_LABELS.get(flag, flag) for flag in meta.get("review_flags", [])],
                "review_priority": priority})
    inventory_ids = {image_identity(part, service, name_cache) for part in service.inventory["image_manifest"]}
    if not image_ids <= inventory_ids:
        raise ValueError("원문에 연결한 그림 키가 PDF 목록에 없습니다.")
    for page in service.inventory["page_inventory"].values():
        page_roles[page["role"]] += 1
    review_items.sort(key=lambda item: (-item["review_priority"], -item["content_chars"], item["source_pages"][0]))
    existing_image_ids = {(row["pdf_page_number"], json.dumps(row["pdf_image_key"], ensure_ascii=False,
                          separators=(",", ":"))) for row in db_images}
    if not existing_image_ids <= image_ids:
        raise ValueError("저장된 표본 그림이 전체 자료의 연결 목록에 없습니다.")
    summary = service.summary()
    return {
        "pdf_file_sha256": document["file_sha256"], "model_name": config.model_name,
        "model_revision": service.token_counter.model_revision, "summary": summary,
        "page_roles": dict(page_roles), "review_flag_counts": dict(flags),
        "review_items": review_items, "review_priority_method": "manual_rule_proposal_not_error_score",
        "images": {"pdf_image_elements": len(inventory_ids), "linked_unique_images": len(image_ids),
            "unlinked_pdf_image_elements": len(inventory_ids - image_ids), "parent_image_links": len(links),
            "links_with_description": links_with_description, "links_without_description": links_without_description,
            "existing_sample_images": len(db_images),
            "existing_uploaded_sample_images": sum(row["upload_status"] == "uploaded" for row in db_images),
            "additional_image_metadata_if_all_linked_stored": len(image_ids - existing_image_ids),
            "full_storage_bytes": None},
        "db_snapshot": {"read_only": connection["read_only"],
            "table_counts": {row["table_name"]: row["row_count"] for row in counts},
            "allocated_bytes": sum(row["bytes"] for row in sizes)},
        "vector_payload_bytes_if_all_embedded": len(service.chunks) * (4 * 768 + 8),
        "proposed_scope": "all_text_vectors_and_linked_image_metadata_keep_review_status",
        "proposed_new_run": True, "proposed_reuse_document_and_existing_images": True,
        "proposed_additional_image_uploads_now": 0, "ready_for_full_save": False,
        "embedding_computed": False, "db_written": False, "storage_uploaded": False,
        "note": "전체 저장 전 조사입니다. 자동 초안과 그림 연결은 추가 검토가 필요하며 저장 서비스·임베딩·새 저장 작업은 아직입니다.",
    }


def print_storage_plan(plan, limit=10):
    """전체 글·그림·검토 상태와 첫 검토 후보를 짧게 표시합니다."""
    summary, images = plan["summary"], plan["images"]
    print("\n전체 부모·청크:", summary["parent_records"], summary["search_chunks"])
    print("검토 상태:", summary["verification_status"])
    print("고유 그림·주제 연결:", images["linked_unique_images"], images["parent_image_links"])
    print("설명 있음/없음 (연결 기준):", images["links_with_description"], images["links_without_description"])
    print("본문에 연결되지 않은 PDF 그림 요소:", images["unlinked_pdf_image_elements"])
    print("현재 개인 DB:", plan["db_snapshot"])
    print("전체 벡터 내용 예상:", plan["vector_payload_bytes_if_all_embedded"], "바이트 — DB 전체 용량 아님")
    print("\n먼저 검토할 자동 초안 (규칙으로 정한 제안 순서):")
    for item in plan["review_items"][:limit]:
        print(f'{item["record_id"]} | PDF {item["source_pages"]} | {item["title"]}')
        print("  이유:", ", ".join(item["review_reasons"]) or "자동 초안 원본 대조 필요")
    print("\n제안: 전체 글·벡터·그림 참조는 새 작업 버전으로, 검토 상태는 그대로 저장.")
    print("그림 파일은 기존 3개를 재사용하고 추가 업로드는 다음 검토 후 결정합니다.")
    print(plan["note"])
