"""목차 제목과 인쇄 쪽수로 전체 본문을 자동 초안으로 나눕니다."""

# [프로젝트 추가] 목차 제목·인쇄 쪽수·장 번호로 여러 페이지의 같은 주제를 모읍니다.
# 자동 결과는 검토할 초안입니다. 경계 실험은 09번 노트북에 있습니다.

import re
from .chunking import prepare_text


def build_auto_topics(inventory, override_pages):
    """원문 구간을 보존하며 검토가 필요한 자동 주제 기록을 만듭니다."""
    page_inventory = inventory["page_inventory"]
    toc_entries = inventory["toc_entries"]
    row_pattern = inventory["row_pattern"]
    normalize_title = inventory["normalize_title"]
    auto_topics = []
    active = None

    def add_segment(topic, number, start, end):
        """본문의 원문 구간과 글자 위치를 보존합니다. 숫자 위치는 본문 문자열 기준입니다."""
        if end > start:
            topic["segments"].append({
                "pdf_page_number": number, "start": start, "end": end,
                "raw_text": page_inventory[number]["body_text"][start:end],
            })

    def finish_active(topic):
        """완성된 임시 주제를 목록에 남깁니다."""
        if topic is not None and topic["segments"]:
            auto_topics.append(topic)

    # [프로젝트 추가] 직접 확인한 페이지는 예제 기록을 사용해 자동 주제와 중복하지 않습니다.
    for number, page in page_inventory.items():
        if number in override_pages or page["role"] not in {"body", "frontmatter"}:
            finish_active(active)
            active = None
            continue
        body = page["body_text"]
        if not body.strip():
            continue
        if active is not None and page["chapter_id"] != active["chapter_id"]:
            finish_active(active)
            active = None

        # [프로젝트 추가] 제목과 인쇄 쪽수 조합을 비교해 이름만 비슷한 다른 구간이 섞이지 않도록 합니다.
        matches = []
        offset = 0
        for line in body.splitlines(keepends=True):
            key = (page["manual_page_number"], normalize_title(line.strip()))
            if key in toc_entries:
                matches.append((offset, toc_entries[key][0]["title"]))
            offset += len(line)
        first_start = matches[0][0] if matches else len(body)

        # 새 페이지 제목 앞의 이어지는 설명은 같은 장의 앞 주제에 연결합니다.
        if first_start > 0:
            if active is None:
                active = {
                    "title": f"PDF {number}쪽 제목 미확인 구간",
                    "chapter_id": page["chapter_id"], "segments": [],
                    "boundary_source": "unmatched_prefix",
                }
            add_segment(active, number, 0, first_start)
        for index, (start, title) in enumerate(matches):
            finish_active(active)
            active = {
                "title": title, "chapter_id": page["chapter_id"], "segments": [],
                "boundary_source": "toc_title_and_printed_page",
            }
            end = matches[index + 1][0] if index + 1 < len(matches) else len(body)
            add_segment(active, number, start, end)
    finish_active(active)

    auto_parents = []
    for index, topic in enumerate(auto_topics):
        segments = topic["segments"]
        pages = list(dict.fromkeys(segment["pdf_page_number"] for segment in segments))
        raw_text = "\n".join(segment["raw_text"] for segment in segments)
        # 검색을 방해하는 긴 점선만 정리하고, 같은 줄의 항목 이름과 참조 숫자는 유지합니다.
        normalized_rows = row_pattern.sub(
            lambda match: match.group(1).strip() + " — 매뉴얼 " + match.group(2) + "쪽", raw_text
        )
        content = prepare_text(normalized_rows)
        # [프로젝트 추가] 제목·꼬리말·기호·표·그림 연결의 불확실성을 review_flags에 남깁니다.
        # 자동 추출 성공은 원본 대조 완료를 뜻하지 않습니다.
        flags = []
        if topic["boundary_source"] == "unmatched_prefix":
            flags.append("heading_not_confirmed")
        if any(not page_inventory[n]["footer_found"] for n in pages):
            flags.append("footer_not_confirmed")
        if any(page_inventory[n]["footer_review_required"] for n in pages):
            flags.append("ambiguous_footer_candidate_needs_review")
        if any(re.fullmatch(r"\*?\d+:|[A-Z]:|\d+", marker)
               for n in pages for marker in page_inventory[n]["detached_markers"]):
            flags.append("detached_number_or_letter_labels_needs_review")
        if len(pages) > 4:
            flags.append("long_topic_boundary_needs_review")
        if len(content) < 40:
            flags.append("thin_topic_needs_review")
        if row_pattern.search(raw_text) or re.search(r"종류\s+용량\s+추천 사양", raw_text):
            flags.append("table_or_navigation_structure_needs_review")
        # 실제 출력에서 확인한 표 제목과 깨진 방향 기호는 별도 검토 대상입니다.
        if topic["title"] == "주행 모드별 패들 쉬프트의 기능" and "table_or_navigation_structure_needs_review" not in flags:
            flags.append("table_or_navigation_structure_needs_review")
        if any(symbol in content for symbol in ["î", "ï"]):
            flags.append("font_symbol_needs_review")
        if any(re.search(r"(?:҃Ҋ|઱੄|ӝ)\s*$", segment["raw_text"]) for segment in segments):
            flags.append("warning_boundary_needs_review")

        # [프로젝트 추가] 미검토 그림은 페이지 수준으로 연결합니다. 주제별 정확한 대응은 추가 대조가 필요합니다.
        images = [part for n in pages for part in page_inventory[n]["image_parts"]]
        if images:
            flags.append("page_level_image_linkage_needs_review")
        auto_parents.append({
            "content": content,
            "raw_text": raw_text,
            "metadata": {
                "record_id": f"auto_topic_{index}",
                "title": topic["title"],
                "pdf_page_number": pages[0],
                "manual_page_number": page_inventory[pages[0]]["manual_page_number"],
                "source_pages": pages,
                "chapter_id": topic["chapter_id"],
                "content_type": "figure_with_text" if images else "instruction_text",
                "boundary_source": topic["boundary_source"],
                "source_spans": [
                    {k: segment[k] for k in ["pdf_page_number", "start", "end"]}
                    for segment in segments
                ],
                "verification_status": "auto_draft_needs_review",
                "review_flags": flags,
            },
            "image_parts": images,
        })

    return auto_parents
