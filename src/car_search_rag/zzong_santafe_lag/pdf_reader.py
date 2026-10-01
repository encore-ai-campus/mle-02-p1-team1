"""PDF 페이지·목차·쪽수·이미지 키 목록을 읽습니다."""

# [프로젝트 추가] 싼타페 목차·색인·본문·꼬리말을 조사한 09번 노트북의 규칙입니다.
# 현재 PDF 구조에 맞춘 규칙이므로 다른 설명서에는 원본 대조 후 적용합니다.

import re
from collections import defaultdict
from pypdf import PdfReader


def inspect_pdf(pdf_path):
    """검토한 779쪽 PDF의 본문과 이미지 참조 목록을 만듭니다."""
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF를 찾을 수 없습니다: {pdf_path}")
    reader = PdfReader(str(pdf_path))
    if len(reader.pages) != 779:
        raise ValueError("검토한 779쪽 PDF와 다릅니다. 표·번호 보완 내용을 먼저 다시 확인하세요.")
    raw_pages = {number: page.extract_text() or "" for number, page in enumerate(reader.pages, start=1)}
    row_pattern = re.compile(r"^([^\n]+?)\.{3,}\s*(\d+(?:\s*,\s*\d+)*)\s*$", re.MULTILINE)
    known_overview_pages = {30, 31, 33, 34, 35, 36}
    toc_pages = []
    for number, text in raw_pages.items():
        rows = row_pattern.findall(text)
        line_count = max(1, sum(bool(line.strip()) for line in text.splitlines()))
        if (number < 765 and number not in known_overview_pages
                and len(rows) >= 2 and len(rows) / line_count > 0.4
                and len(reader.pages[number - 1].images) == 0):
            toc_pages.append(number)

    # 이번 PDF에서 확인한 목차 목록과 달라지면 자동 처리를 멈추고 다시 살펴봅니다.
    # [프로젝트 추가] 목차를 사용 설명 본문과 구별합니다. 확인한 목록과 다르면 PDF 구조를 다시 살펴봅니다.
    expected_toc_pages = [7, 29, 49, 50, 63, 147, 183, 184, 185, 186, 187, 379, 380, 461, 462, 463, 659, 693, 694]
    assert toc_pages == expected_toc_pages

    def normalize_title(text):
        """제목 비교에서는 공백 차이만 제거합니다. 내용이나 숫자는 바꾸지 않습니다."""
        return re.sub(r"\s+", "", text)

    chapter_names = {}
    for number in toc_pages:
        for chapter, name in re.findall(r"^([0-9])\.\s+([^\n]+)$", raw_pages[number], re.MULTILINE):
            chapter_names[normalize_title(name)] = int(chapter)

    # [프로젝트 추가] PDF 쪽수와 인쇄 쪽수를 따로 기록하고 꼬리말 후보가 모호하면 검토 표시를 남깁니다.
    def split_footer(raw_text):
        """끝부분의 꼬리말 후보를 찾고, 따로 추출된 번호·각주도 원문 목록에 남깁니다."""
        lines = []
        position = 0
        for line in raw_text.splitlines(keepends=True):
            if line.strip():
                lines.append({"text": line.strip(), "start": position})
            position += len(line)

        candidates = []
        marker_pattern = r"[•-]|\*?\d+:|[A-Z]:|\d+"
        for index in range(len(lines) - 1):
            section = normalize_title(lines[index]["text"])
            chapter = chapter_names.get(section)
            if re.fullmatch(r"[0-9]", section):
                chapter = int(section)
            manual_text = lines[index + 1]["text"]
            if chapter is None or not manual_text.isdigit():
                continue
            manual_number = int(manual_text)
            if not 0 < manual_number <= len(reader.pages):
                continue
            tail = [line["text"] for line in lines[index + 2:]]
            if all(re.fullmatch(marker_pattern, marker) for marker in tail):
                candidates.append({
                    "index": index, "chapter": chapter, "manual": manual_number,
                    "named_section": section in chapter_names, "tail": tail,
                })
        if candidates:
            # 장 이름 후보를 우선합니다. 숫자 후보가 여러 개면 검토 표시를 남깁니다.
            candidates.sort(key=lambda c: (c["named_section"], c["manual"]), reverse=True)
            chosen = candidates[0]
            index = chosen["index"]
            ambiguous = len(candidates) > 1 and not chosen["named_section"]
            return (raw_text[:lines[index]["start"]], chosen["manual"], chosen["chapter"],
                    True, ambiguous, chosen["tail"])
        return raw_text, None, None, False, False, []

    page_inventory = {}
    image_manifest = []
    for number, raw_text in raw_pages.items():
        body, manual_number, chapter, footer_found, footer_review, detached_markers = split_footer(raw_text)
        # 이미지 키 목록은 픽셀을 모두 디코딩하지 않고 읽을 수 있습니다.
        # [프로젝트 추가] 그림을 모두 저장하지 않고 페이지·PDF 내부 키를 먼저 기록합니다.
        # I1.jpg처럼 이름이 같아도 다른 페이지면 다른 그림이므로 이름만으로 연결하지 않습니다.
        parts = []
        for index, key in enumerate(reader.pages[number - 1].images.keys()):
            part = {
                "image_id": f"pdf_{number}_image_{index}",
                "pdf_page_number": number,
                "pdf_image_key": key,
                "name": None,
                "size": None,
                "local_path": None,
                "description": None,
            }
            parts.append(part)
            image_manifest.append(part)

        # [프로젝트 추가] 페이지의 용도를 나눠 원본 조사 목록과 본문 청킹 대상을 따로 관리합니다.
        divider = re.fullmatch(r"([0-9])\.\s*([^\n]+)\s*", raw_text.strip())
        is_divider = bool(divider and normalize_title(divider.group(2)) in chapter_names)
        if not raw_text.strip() and not parts:
            role = "empty"
        elif number >= 765:
            role = "index"
        elif number in toc_pages:
            role = "toc"
        elif is_divider or (footer_found and not body.strip()):
            role = "divider_or_empty_body"
        elif number <= 6:
            role = "frontmatter"
        else:
            role = "body"
        page_inventory[number] = {
            "raw_text": raw_text, "body_text": body,
            "manual_page_number": manual_number, "chapter_id": chapter,
            "footer_found": footer_found, "footer_review_required": footer_review,
            "detached_markers": detached_markers, "role": role, "image_parts": parts,
        }

    # 목차의 참조 쪽수와 본문 제목을 함께 비교할 색인을 만듭니다.
    # [프로젝트 추가] 목차의 제목과 인쇄 쪽수를 함께 사용해 본문 제목 경계를 찾습니다.
    toc_entries = defaultdict(list)
    for number in toc_pages:
        for title, pages in row_pattern.findall(raw_pages[number]):
            if "," in pages:
                continue
            toc_entries[(int(pages), normalize_title(title))].append({
                "title": re.sub(r"\s+", " ", title.strip()),
                "toc_pdf_page_number": number,
            })


    return {"reader": reader, "page_inventory": page_inventory, "image_manifest": image_manifest,
            "raw_pages": raw_pages, "row_pattern": row_pattern, "toc_entries": toc_entries,
            "normalize_title": normalize_title}
