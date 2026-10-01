"""원본 화면에서 대조한 패들 쉬프트와 오일 표의 보완을 적용합니다."""

# [프로젝트 추가] PDF 원본 화면을 대조한 구간에만 표·기호·그림 보완을 적용합니다.
# 10번(패들 쉬프트)·11번(오일 표) 노트북의 확인 기록을 옮겼습니다.

import re
from copy import deepcopy
from .chunking import prepare_text


def apply_paddle_review(parents, inventory):
    """397·398·402쪽의 확인한 기호·표·그림을 보완하고 403쪽은 초안으로 남깁니다."""
    reviewed_parent_records = deepcopy(parents)
    page_inventory = inventory["page_inventory"]
    reader = inventory["reader"]
    def find_parent(title, first_page):
        """제목과 시작 PDF 쪽수가 일치하는 원문 묶음 한 개를 찾습니다."""
        matches = [
            parent for parent in reviewed_parent_records
            if parent["metadata"]["title"] == title
            and parent["metadata"]["pdf_page_number"] == first_page
        ]
        if len(matches) != 1:
            raise ValueError(f"{title}: 원문 묶음이 달라졌으므로 경계를 다시 확인하세요.")
        return matches[0]


    # [프로젝트 추가] 검토한 구간과 미검토 구간을 나누되 원문 위치를 보존합니다.
    def select_page_spans(parent, numbers, record_id):
        """선택한 페이지 구간만 복사하고, 원문 위치와 출처를 함께 유지합니다."""
        spans = [
            deepcopy(span) for span in parent["metadata"]["source_spans"]
            if span["pdf_page_number"] in numbers
        ]
        if not spans:
            raise ValueError("선택할 원문 구간이 없습니다.")
        pages = list(dict.fromkeys(span["pdf_page_number"] for span in spans))
        raw = "\n".join(
            page_inventory[span["pdf_page_number"]]["body_text"][span["start"]:span["end"]]
            for span in spans
        )
        record = {
            "content": prepare_text(raw), "raw_text": raw,
            "metadata": deepcopy(parent["metadata"]),
            "image_parts": [
                deepcopy(part) for part in parent["image_parts"]
                if part["pdf_page_number"] in pages
            ],
        }
        record["metadata"].update({
            "record_id": record_id, "source_pages": pages, "source_spans": spans,
            "pdf_page_number": pages[0],
            "manual_page_number": page_inventory[pages[0]]["manual_page_number"],
        })
        return record


    paddle_draft = find_parent("패들 쉬프트 (수동 변속 모드)", 397)
    mode_table_draft = find_parent("주행 모드별 패들 쉬프트의 기능", 402)
    limit_draft = find_parent("회생 제동 시스템 사용 제한", 402)

    paddle_record = select_page_spans(paddle_draft, {397}, paddle_draft["metadata"]["record_id"])
    table_398_record = select_page_spans(paddle_draft, {398}, "reviewed_paddle_table_398")
    table_398_record["metadata"]["title"] = "드라이브 모드 별 패들 쉬프트 레버 기능"
    table_402_record = deepcopy(mode_table_draft)
    limit_402_record = select_page_spans(limit_draft, {402}, limit_draft["metadata"]["record_id"])
    limit_403_draft = select_page_spans(limit_draft, {403}, "unreviewed_paddle_limit_403")
    limit_403_draft["metadata"]["title"] = "시스템 제한 경고"
    limit_403_draft["metadata"]["verification_status"] = "auto_draft_needs_review"

    # 목차 경계가 실제 화면의 제목 경계와 일치하는지 확인합니다.
    assert paddle_record["raw_text"].startswith("패들 쉬프트 (수동 변속 모드)")
    assert "올바른 운전 요령" not in table_398_record["raw_text"]
    assert "회생 제동 시스템 사용 제한" not in table_402_record["raw_text"]
    assert limit_402_record["raw_text"].startswith("회생 제동 시스템 사용 제한")
    assert [page_inventory[n]["manual_page_number"] for n in [397, 398, 402]] == [392, 393, 397]
    # 전역 치환을 하면 다른 페이지의 기호까지 잘못 바꿀 수 있어 확인한 구간만 고칩니다.
    # [프로젝트 추가] î/ï를 +/−로 해석한 근거는 PDF 397쪽 화면입니다. 확인한 구간에만 적용합니다.
    symbol_corrections = {"î": "+", "ï": "-"}
    corrected_raw = paddle_record["raw_text"]
    for broken, corrected in symbol_corrections.items():
        corrected_raw = corrected_raw.replace(broken, corrected)
    paddle_record["content"] = prepare_text(corrected_raw)

    # 개별 이미지로 확인한 그림 하나만 선택합니다. 실제 이미지 파일은 저장하지 않습니다.
    # [프로젝트 추가] 같은 페이지의 경고 그림과 조작 그림을 구별해 확인한 /I2만 연결합니다.
    paddle_parts = [
        part for part in paddle_record["image_parts"] if part["pdf_image_key"] == "/I2"
    ]
    if len(paddle_parts) != 1:
        raise ValueError("패들 쉬프트 이미지 키가 달라졌습니다.")
    paddle_image = reader.pages[396].images["/I2"]
    paddle_part = deepcopy(paddle_parts[0])
    paddle_part.update({
        "name": paddle_image.name, "size": tuple(paddle_image.image.size),
        "description": "스티어링 휠 뒤쪽의 패들 쉬프트 레버와 당기는 방향을 보여준다.",
        "linkage_status": "visually_verified",
    })
    paddle_record["image_parts"] = [paddle_part]
    paddle_record["content"] += "\n[그림 설명] " + paddle_part["description"]
    paddle_record["metadata"]["image_linkage_status"] = "visually_verified"
    paddle_record["metadata"]["symbol_corrections"] = symbol_corrections

    # 표는 열 머리글과 셀의 관계를 확인한 후 행으로 옮깁니다.
    # [프로젝트 추가] 모드·레버 기호·기능을 한 행에 옮깁니다. 값은 원본 화면에서 대조한 내용입니다.
    table_rows = [
        {"drive_mode": "ECO", "lever": "+", "function": "회생 제동 단계 감소"},
        {"drive_mode": "ECO", "lever": "-", "function": "회생 제동 단계 증가"},
        {"drive_mode": "SPORT", "lever": "+", "function": "수동 변속 +"},
        {"drive_mode": "SPORT", "lever": "-", "function": "수동 변속 -"},
    ]


    def normalize_mode_table(record):
        """확인한 네 표 행을 옮기고 표 앞 설명과 뒤 참고 문장을 유지합니다."""
        raw = record["raw_text"]
        start = raw.index("드라이브 모드 패들 쉬프트 레버 조작 패들 쉬프트 레버 기능")
        last_row = "- 수동 변속 -"
        end = raw.index(last_row, start) + len(last_row)
        extracted_rows = raw[start:end]
        # 같은 PDF가 바뀌면 예전에 확인한 표를 그대로 적용하지 않습니다.
        expected_rows = [
            "ECO", "+ 회생 제동 단계 감소", "- 회생 제동 단계 증가",
            "SPORT", "+ 수동 변속 +", "- 수동 변속 -",
        ]
        actual_rows = [line.strip() for line in extracted_rows.splitlines()[1:] if line.strip()]
        if actual_rows != expected_rows:
            raise ValueError("표 내용이 바뀌었습니다. 원본 화면부터 확인하세요.")

        row_lines = [
            f'드라이브 모드: {row["drive_mode"]} | 패들 쉬프트 레버 조작: {row["lever"]} | 기능: {row["function"]}'
            for row in table_rows
        ]
        record["content"] = "\n".join([
            prepare_text(raw[:start]), "[표: 드라이브 모드별 패들 쉬프트 레버 기능]",
            *row_lines, prepare_text(raw[end:]),
        ])
        record["metadata"].update({
            "content_type": "structured_table",
            "table_rows": deepcopy(table_rows),
            "duplicate_group_id": "paddle_mode_function_table",
            "table_structure_status": "visually_verified",
        })
        return record


    table_398_record = normalize_mode_table(table_398_record)
    table_402_record = normalize_mode_table(table_402_record)
    limit_402_record["metadata"]["content_type"] = "instruction_text"

    reviewed_records = [paddle_record, table_398_record, table_402_record, limit_402_record]
    for record in reviewed_records:
        record["metadata"].update({
            "verification_status": "visually_reviewed_source",
            "review_method": "원본 페이지 전체 화면 및 표 행·기호 대조",
            "review_flags": [],
        })

    # 연결은 검색 결과를 답변 근거로 읽을 때 함께 불러와야 할 원문 ID입니다.
    # 이 표시만으로 기존 답변 코드가 자동으로 읽는 것은 아니므로 이후 검색 코드에 반영합니다.
    paddle_id = paddle_record["metadata"]["record_id"]
    table_398_id = table_398_record["metadata"]["record_id"]
    table_402_id = table_402_record["metadata"]["record_id"]
    limit_402_id = limit_402_record["metadata"]["record_id"]
    # [프로젝트 추가] 검색된 표와 함께 읽을 조작 설명·제한 조건을 ID로 연결합니다.
    # 403쪽의 미검토 경고는 별도로 표시합니다.
    paddle_record["metadata"]["required_context_record_ids"] = [table_398_id]
    table_398_record["metadata"]["required_context_record_ids"] = [paddle_id, limit_402_id]
    table_402_record["metadata"]["required_context_record_ids"] = [paddle_id, limit_402_id]
    limit_402_record["metadata"]["required_context_record_ids"] = [table_402_id]
    limit_402_record["metadata"]["unreviewed_continuation_record_ids"] = [
        limit_403_draft["metadata"]["record_id"]
    ]

    # 해당하는 세 초안만 대체하고 나머지 기록은 그대로 남깁니다.
    replacements = {
        paddle_draft["metadata"]["record_id"]: [paddle_record, table_398_record],
        mode_table_draft["metadata"]["record_id"]: [table_402_record],
        limit_draft["metadata"]["record_id"]: [limit_402_record, limit_403_draft],
    }
    reviewed_parent_records = [
        replacement
        for parent in reviewed_parent_records
        for replacement in replacements.get(parent["metadata"]["record_id"], [parent])
    ]

    return reviewed_parent_records

def apply_oil_review(parents, inventory):
    """43쪽의 표 행·공유 셀·각주·주의사항을 보존해 두 기록으로 나눕니다."""
    full_parent_records = deepcopy(parents)
    page_inventory = inventory["page_inventory"]
    oil_matches = [
        p for p in full_parent_records
        if p["metadata"]["title"] == "추천 오일 및 용량"
        and p["metadata"]["pdf_page_number"] == 43
    ]
    if len(oil_matches) != 1:
        raise ValueError("43쪽 원문 묶음의 경계를 다시 확인하세요.")
    oil_original = oil_matches[0]
    assert oil_original["metadata"]["source_pages"] == [43]
    assert oil_original["metadata"]["manual_page_number"] == 38
    assert len(oil_original["metadata"]["source_spans"]) == 1
    original_span = oil_original["metadata"]["source_spans"][0]
    body = page_inventory[43]["body_text"]
    footnote_start = body.index("엔진 오일 용량은 일반적인 오일 교체 시 주입되는 용량 기준입니다.")
    table_raw = body[original_span["start"]:footnote_start]
    notes_raw = body[footnote_start:original_span["end"]]

    # [프로젝트 추가] 두 오일 항목에 걸친 사양 셀을 각 행에 옮기고 원래 공유 관계도 기록합니다.
    shared_specification = "하이포이드 기어 오일 API GL-5, SAE 75W/85(SK HCT-5 기어 오일 75W/85 or 상당품)"
    oil_rows = [
        {"kind": "연료", "capacity": "67 ℓ", "specification": "무연 휘발유", "footnote_ids": []},
        {"kind": "엔진 오일", "capacity": "4.8 ℓ",
         "specification": "SAE 0W-20 API SN PLUS/SP 또는 ILSAC GF-6", "footnote_ids": ["*1", "*2"]},
        {"kind": "자동 변속기 오일", "capacity": "6.0 ℓ",
         "specification": "SK ATF SP4M-1, MICHANG ATF SP4M-1, S-OIL ATF SP4M-1, Hyundai Genuine ATF SP4M-1",
         "footnote_ids": []},
        {"kind": "엔진 냉각수", "capacity": "8.9 ℓ",
         "specification": "알루미늄 라디에이터용 인산염계 에틸렌 글리콜 부동액과 물 혼합액",
         "footnote_ids": []},
        {"kind": "브레이크액", "capacity": "필요량", "specification": "DOT-4", "footnote_ids": ["*3"]},
        {"kind": "리어 디퍼런셜 오일 (HTRAC)", "capacity": "0.53 ~ 0.63 ℓ",
         "specification": shared_specification, "footnote_ids": ["*4"], "shared_specification_cell": "htrac_gears"},
        {"kind": "트랜스퍼 케이스 오일 (HTRAC)", "capacity": "0.62 ~ 0.68 ℓ",
         "specification": shared_specification, "footnote_ids": ["*4"], "shared_specification_cell": "htrac_gears"},
    ]

    # 표 셀 안에서 줄이 바뀐 영문명도 화면에서 같은 문구임을 확인했습니다.
    compact_raw = re.sub(r"\s+", "", table_raw)
    for row in oil_rows:
        for field in ["kind", "capacity", "specification"]:
            assert re.sub(r"\s+", "", row[field]) in compact_raw

    # [프로젝트 추가] 오일 종류·용량과 함께 읽어야 할 각주·주의사항을 별도 기록으로 연결합니다.
    note_markers = [
        ("*1", "엔진 오일 용량은 일반적인"),
        ("*2", "API SN PLUS(또는 그 이상)"),
        ("*3", "차량의 제동 성능 및 ABS/ESC"),
        ("*4", "교체 주기와는 별도로"),
    ]
    caution_start = notes_raw.index("઱੄")
    footnotes = {}
    for index, (note_id, marker) in enumerate(note_markers):
        start = notes_raw.index(marker)
        end = notes_raw.index(note_markers[index + 1][1]) if index + 1 < len(note_markers) else caution_start
        footnotes[note_id] = prepare_text(notes_raw[start:end])
    caution_text = prepare_text(notes_raw[caution_start:])

    oil_table_id = oil_original["metadata"]["record_id"]
    oil_notes_id = "reviewed_oil_notes_43"
    table_content = "\n".join([
        "추천 오일 및 용량",
        *[
            row["kind"] + " | 용량: " + row["capacity"] + " | 추천 사양: " + row["specification"]
            + (" | 각주: " + ", ".join(row["footnote_ids"]) if row["footnote_ids"] else "")
            for row in oil_rows
        ],
    ])
    oil_table_record = {
        "content": table_content, "raw_text": table_raw, "image_parts": [],
        "metadata": deepcopy(oil_original["metadata"]),
    }
    oil_table_record["metadata"].update({
        "content_type": "structured_table", "table_rows": oil_rows,
        "source_spans": [{"pdf_page_number": 43, "start": original_span["start"], "end": footnote_start}],
        "verification_status": "visually_reviewed_source", "review_flags": [],
        "table_structure_status": "visually_verified",
        "review_method": "43쪽 전체 화면의 표 셀·공유 사양·각주 번호 대조",
        "required_context_record_ids": [oil_notes_id],
    })
    oil_notes_record = {
        "content": "추천 오일 및 용량 — 각주 및 주의사항\n"
            + "\n".join(note_id + ": " + text for note_id, text in footnotes.items())
            + "\n" + caution_text,
        "raw_text": notes_raw, "image_parts": [],
        "metadata": {
            "record_id": oil_notes_id, "title": "추천 오일 및 용량 — 각주 및 주의사항",
            "pdf_page_number": 43, "manual_page_number": 38, "source_pages": [43],
            "chapter_id": oil_original["metadata"].get("chapter_id"),
            "content_type": "instruction_text",
            "source_spans": [{"pdf_page_number": 43, "start": footnote_start, "end": original_span["end"]}],
            "verification_status": "visually_reviewed_source", "review_flags": [],
            "review_method": "43쪽 전체 화면의 각주·주의사항 대조",
            "footnotes": footnotes, "required_context_record_ids": [oil_table_id],
        },
    }
    assert table_raw + notes_raw == oil_original["raw_text"]
    assert "[주의]" in oil_notes_record["content"]
    assert "엔진 오일 첨가제를 사용하지 마십시오." in oil_notes_record["content"]
    assert "'F' 선 이상 주입하지" in oil_notes_record["content"]
    full_parent_records = [
        record for parent in full_parent_records
        for record in ([oil_table_record, oil_notes_record]
            if parent["metadata"]["record_id"] == oil_table_id else [parent])
    ]

    return full_parent_records
