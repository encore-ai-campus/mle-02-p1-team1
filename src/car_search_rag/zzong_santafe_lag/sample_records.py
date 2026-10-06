"""수업 실험에서 확인한 안내도·표·본문 예제를 같은 형식으로 만듭니다."""

# [프로젝트 추가] 확인한 싼타페 안내도·표·본문을 같은 네 항목으로 만듭니다.
# content(검색용 글), raw_text(원문), metadata(출처), image_parts(그림 참조)를 사용합니다.

import re
from .chunking import prepare_text


def before_heading(text, heading):
    """확인한 다음 제목 앞까지만 원문을 가져옵니다."""
    marker = "\n" + heading + "\n"
    if marker not in text:
        raise ValueError(f"다음 제목을 찾지 못했습니다: {heading}")
    return text.split(marker, 1)[0]

def from_heading(text, heading):
    """확인한 제목부터 원문을 가져옵니다."""
    position = text.find(heading + "\n")
    if position < 0:
        raise ValueError(f"제목을 찾지 못했습니다: {heading}")
    return text[position:]

# [프로젝트 추가] 그림은 페이지·이름을 함께 식별하고 파일이 있을 때만 경로를 기록합니다.
# description은 원본을 보고 확인한 설명입니다. 별도 이미지 분석 모델이 만든 설명은 아닙니다.
def collect_image_parts(reader, project_folder, number, descriptions=None):
    """페이지와 이미지 이름을 함께 기록합니다. 모르는 그림은 설명을 만들지 않습니다."""
    descriptions = descriptions or {}
    parts = []
    for image in reader.pages[number - 1].images:
        path = project_folder / "data" / "zzong_santafe_lag" / "images" / f"pdf_page_{number}" / image.name
        parts.append({
            "name": image.name,
            "pdf_page_number": number,
            "size": image.image.size,
            "local_path": path.relative_to(project_folder).as_posix() if path.exists() else None,
            "description": descriptions.get(image.name),
        })
    return parts

def build_type_samples(reader, project_folder):
    """확인한 내부 안내도 세 개와 오일 점도 표·안전벨트 기록을 만듭니다."""
    page_texts = {n: reader.pages[n - 1].extract_text() or "" for n in [33, 34, 35, 36, 44, 54]}
    # 앞서 실제 PDF의 번호 순서와 항목 수를 확인한 세 안내도만 처리합니다.
    # [프로젝트 추가] 다음 페이지로 이어지는 안내도 설명은 다음 그림 제목 앞에서 경계를 끊습니다.
    # 번호·부품 이름·참조 쪽수는 앞서 확인한 순서로 연결합니다.
    overview_specs = [
        ("차량 내부 I", 33, 28, [33, 34], 18,
         page_texts[33] + "\n" + before_heading(page_texts[34], "차량 내부 II")),
        ("차량 내부 II", 34, 29, [34, 35], 24,
         from_heading(page_texts[34], "차량 내부 II") + "\n" + before_heading(page_texts[35], "차량 내부 III")),
        ("차량 내부 III", 35, 30, [35, 36], 10,
         from_heading(page_texts[35], "차량 내부 III") + "\n" + page_texts[36]),
    ]
    parent_records = []

    for title, image_page, manual_page, pages, expected_count, raw_text in overview_specs:
        # '부품 이름 ... 참조 쪽수' 형태인 줄만 찾습니다.
        rows = re.findall(r"^([^\n]+?)\.{3,}\s*(\d+(?:\s*,\s*\d+)*)\s*$", raw_text, flags=re.MULTILINE)
        if len(rows) != expected_count:
            raise ValueError(f"{title}: 예상한 {expected_count}개 항목과 추출 결과가 다릅니다.")

        items = [
            {"number": i, "name": name.strip(), "target_manual_pages": [int(n) for n in pages_text.split(",")]}
            for i, (name, pages_text) in enumerate(rows, start=1)
        ]
        content_lines = [title, "본 도안은 적용된 사양에 따라 실제 차량과 다를 수 있습니다."]
        content_lines += [
            f'{item["number"]}: {item["name"]} — 매뉴얼 ' +
            ", ".join(str(n) + "쪽" for n in item["target_manual_pages"])
            for item in items
        ]
        parent_records.append({
            "content": "\n".join(content_lines),
            "raw_text": raw_text,
            "metadata": {
                "record_id": f"overview_{image_page}",
                "title": title,
                "pdf_page_number": image_page,
                "manual_page_number": manual_page,
                "source_pages": pages,
                "content_type": "vehicle_overview_navigation",
                "navigation_items": items,
                "number_mapping": "previously_confirmed_order",
            },
            "image_parts": collect_image_parts(reader, project_folder, image_page, {"I1.jpg": title + "의 주요 부품 위치를 번호로 표시한 안내도."}),
        })

    # 44쪽은 확인한 꼬리말만 검색 글에서 제외하며 raw_text에는 그대로 남깁니다.
    table_raw = page_texts[44]
    table_footer = "\n안내 및 차량 정보\n39"
    if table_footer not in table_raw:
        raise ValueError("44쪽 표의 꼬리말을 다시 확인해야 합니다.")
    # [프로젝트 추가] PDF 44쪽 이미지 조각의 온도 눈금과 0W-20을 사람이 확인한 글로 보완합니다.
    # 이 설명은 표 정보를 검색하기 위한 문장이며 자동 OCR 결과는 아닙니다.
    table_descriptions = {
        "I1.jpg": "온도 눈금은 -30도부터 50도까지 표시되어 있다.",
        "I2.jpg": "1.6 T-GDi HEV 행에 0W-20이 표시되어 있다.",
    }
    parent_records.append({
        "content": table_raw.split(table_footer, 1)[0] + "\n[그림 설명] " + " ".join(table_descriptions.values()),
        "raw_text": table_raw,
        "metadata": {
            "record_id": "table_44",
            "title": "온도에 따른 엔진 오일 SAE 점도 분류표",
            "pdf_page_number": 44,
            "manual_page_number": 39,
            "source_pages": [44],
            "content_type": "table_with_images",
        },
        "image_parts": collect_image_parts(reader, project_folder, 44, table_descriptions),
    })

    long_raw = page_texts[54]
    long_footer = "\n안전 및 주의 사항\n49"
    if long_footer not in long_raw:
        raise ValueError("54쪽의 꼬리말을 다시 확인해야 합니다.")
    parent_records.append({
        "content": prepare_text(long_raw.split(long_footer, 1)[0]),
        "raw_text": long_raw,
        "metadata": {
            "record_id": "seatbelt_54",
            "title": "안전벨트 착용",
            "pdf_page_number": 54,
            "manual_page_number": 49,
            "source_pages": [54],
            "content_type": "figure_with_text",
            "image_linkage_status": "page_level_needs_review",
        },
        "image_parts": collect_image_parts(reader, project_folder, 54),
    })

    return parent_records

# [프로젝트 추가] 확인한 여섯 제목으로 PDF 52~53쪽을 나누고 다음 페이지의 이어지는 문장을 연결합니다.
def build_topic_samples(reader, project_folder):
    """52~53쪽의 확인한 여섯 주제를 원문 구간과 함께 만듭니다."""
    manual_page_numbers = {52: 47, 53: 48}
    page_texts = {n: reader.pages[n - 1].extract_text() or "" for n in [52, 53]}
    topic_titles = [
        "엔진룸 점검",
        "규격 타이어 장착 및 타이어 공기압 수시 점검",
        "클러스터 및 페달류 점검",
        "올바른 운전 자세",
        "좌석, 스티어링 휠, 미러 조정",
        "운전석 주변 점검",
    ]

    # 끝부분에 확인한 장 이름·쪽수와 글머리표만 있을 때 꼬리말로 처리합니다.
    footer_patterns = {
        52: r"\n안전 및 주의 사항\n47\n(?:[•\s])*\Z",
        53: r"\n2\n48\n(?:[•\s])*\Z",
    }
    page_bodies = {}
    for number, text in page_texts.items():
        footer = re.search(footer_patterns[number], text)
        if footer is None:
            raise ValueError(f"PDF {number}쪽 꼬리말 모양이 바뀌었습니다. 원문을 먼저 확인하세요.")
        page_bodies[number] = text[:footer.start()]

    def collect_topics(page_bodies, titles):
        """확인한 제목으로 원문을 나누고, 다음 페이지의 이어지는 글도 같은 주제로 묶습니다."""
        title_pattern = re.compile(r"^(?:" + "|".join(re.escape(title) for title in titles) + r")$", re.MULTILINE)
        topics = []
        active_topic = None

        def append_segment(topic, number, text, start, end):
            """원문의 해당 구간과 위치를 기록합니다. start와 end는 글자 위치입니다."""
            if end > start:
                topic["segments"].append({
                    "pdf_page_number": number,
                    "start": start,
                    "end": end,
                    "text": text[start:end],
                })

        for number, text in page_bodies.items():
            matches = list(title_pattern.finditer(text))
            first_title_start = matches[0].start() if matches else len(text)

            # 다음 페이지 첫 제목 앞의 글은 이전 페이지에서 시작한 주제에 붙입니다.
            if first_title_start > 0:
                if active_topic is None:
                    raise ValueError(f"PDF {number}쪽 첫 부분의 주제를 확인해야 합니다.")
                append_segment(active_topic, number, text, 0, first_title_start)

            for index, match in enumerate(matches):
                if active_topic is not None:
                    topics.append(active_topic)
                active_topic = {"title": match.group(), "segments": []}
                end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
                append_segment(active_topic, number, text, match.start(), end)

        if active_topic is not None:
            topics.append(active_topic)
        return topics

    topic_groups = collect_topics(page_bodies, topic_titles)
    def prepare_search_text(raw_text):
        """원문 문장은 유지하고, 확인한 기호와 불필요한 이미지 코드만 정리합니다."""
        text = raw_text
        for old, new in {"҃Ҋ": "[경고]", "઱੄": "[주의]", "ӝ": "[참고]"}.items():
            text = text.replace(old, new)

        # 이미지 내부 코드는 한 줄 전체가 코드일 때만 제외합니다.
        text = re.sub(r"^[12]C_[A-Za-z0-9_]+\s*$", "", text, flags=re.MULTILINE)
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
        return "\n".join(line for line in lines if line)

    # 이름만 같은 다른 페이지의 그림을 연결하지 않도록 페이지와 이름을 함께 확인합니다.
    engine_image = next((image for image in reader.pages[51].images if image.name == "I2.jpg"), None)
    if engine_image is None:
        raise ValueError("PDF 52쪽의 I2.jpg 그림을 찾지 못했습니다.")
    image_path = project_folder / "data" / "zzong_santafe_lag" / "images" / "pdf_page_52" / engine_image.name
    engine_image_part = {
        "name": engine_image.name,
        "size": engine_image.image.size,
        "pdf_page_number": 52,
        "local_path": image_path.relative_to(project_folder).as_posix() if image_path.exists() else None,
        "description": "증기가 올라오는 용기 위로 손이 향해 있고 X 표시가 있다. 냉각수가 뜨거울 때 보조 탱크 캡을 열지 말라는 주의사항을 보여준다.",
    }

    topic_records = []
    for topic in topic_groups:
        segments = topic["segments"]
        raw_text = "\n".join(segment["text"] for segment in segments)
        content = prepare_search_text(raw_text)
        image_parts = [dict(engine_image_part)] if topic["title"] == "엔진룸 점검" else []

        # 확인한 그림 설명은 그 그림에 해당하는 주제에만 붙입니다.
        if image_parts:
            content += "\n[그림 설명] " + image_parts[0]["description"]

        source_pages = list(dict.fromkeys(segment["pdf_page_number"] for segment in segments))
        metadata = {
            "title": topic["title"],
            "pdf_page_number": source_pages[0],
            "manual_page_number": manual_page_numbers[source_pages[0]],
            "source_pages": source_pages,
            "content_type": "figure_with_text" if image_parts else "instruction_text",
            "chunking_method": "confirmed_topic_titles",
            "source_spans": [
                {
                    "pdf_page_number": segment["pdf_page_number"],
                    "manual_page_number": manual_page_numbers[segment["pdf_page_number"]],
                    "start": segment["start"],
                    "end": segment["end"],
                } for segment in segments
            ],
        }
        if len(source_pages) > 1:
            metadata["continued_on_pdf_page"] = source_pages[1]
            metadata["continuation_manual_page_number"] = manual_page_numbers[source_pages[1]]

        topic_records.append({
            "content": content,
            "raw_text": raw_text,
            "metadata": metadata,
            "image_parts": image_parts,
        })


    return topic_records

# [프로젝트 추가] sample_verified는 확인한 예제라는 뜻입니다.
# 페이지 수준으로 연결한 그림은 개별 주제와의 대응을 더 살펴봐야 합니다.
def build_confirmed_samples(inventory, project_folder):
    """앞서 확인한 14개 예제와 자동 처리에서 제외할 페이지를 돌려줍니다."""
    reader = inventory["reader"]
    raw_pages = inventory["raw_pages"]
    page_inventory = inventory["page_inventory"]
    row_pattern = inventory["row_pattern"]
    verified_parents = []
    for original in build_type_samples(reader, project_folder):
        record = {
            "content": original["content"], "raw_text": original["raw_text"],
            "metadata": dict(original["metadata"]), "image_parts": original["image_parts"],
        }
        record["metadata"]["verification_status"] = "sample_verified"
        verified_parents.append(record)

    for index, original in enumerate(build_topic_samples(reader, project_folder)):
        record = {
            "content": original["content"], "raw_text": original["raw_text"],
            "metadata": dict(original["metadata"]), "image_parts": original["image_parts"],
        }
        record["metadata"].update({
            "record_id": f"sample_topic_{index}",
            "verification_status": "sample_verified",
        })
        verified_parents.append(record)

    for number, title, expected_count, manual_number in [
        (30, "차량 외부 I", 9, 25), (31, "차량 외부 II", 10, 26),
    ]:
        rows = row_pattern.findall(raw_pages[number])
        assert len(rows) == expected_count
        items = [
            {"number": index, "name": name.strip(),
             "target_manual_pages": [int(n) for n in pages.split(",")]}
            for index, (name, pages) in enumerate(rows, start=1)
        ]
        content = title + "\n이 그림은 실제 차량과 다를 수 있습니다.\n"
        content += "\n".join(
            f'{item["number"]}: {item["name"]} — 매뉴얼 ' +
            ", ".join(str(n) + "쪽" for n in item["target_manual_pages"])
            for item in items
        )
        verified_parents.append({
            "content": content, "raw_text": raw_pages[number],
            "metadata": {
                "record_id": f"overview_{number}", "title": title,
                "pdf_page_number": number, "manual_page_number": manual_number,
                "source_pages": [number], "content_type": "vehicle_overview_navigation",
                "navigation_items": items, "verification_status": "sample_verified",
            },
            "image_parts": collect_image_parts(reader, project_folder, number, {"I1.jpg": title + "의 주요 부품 위치를 번호로 표시한 안내도."}),
        })

    vin_description = "그림의 화살표는 엔진과 차량 실내 사이 차체 패널에 있는 차대번호 타각 위치를 가리킨다."
    verified_parents.append({
        "content": prepare_text(page_inventory[45]["body_text"]) + "\n[그림 설명] " + vin_description,
        "raw_text": raw_pages[45],
        "metadata": {
            "record_id": "vin_45", "title": "차대번호 (VIN)",
            "pdf_page_number": 45, "manual_page_number": 40, "source_pages": [45],
            "content_type": "figure_with_text", "verification_status": "sample_verified",
        },
        "image_parts": collect_image_parts(reader, project_folder, 45, {"I1.jpg": vin_description}),
    })
    override_pages = {number for record in verified_parents for number in record["metadata"]["source_pages"]}

    return verified_parents, override_pages
