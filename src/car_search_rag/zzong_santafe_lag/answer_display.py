"""답변 내용은 유지하고 싼타페 화면의 문단·출처 표시만 정리합니다."""

import re


# [프로젝트 추가] 화면 제목만 고정합니다. 차량 수치·방법·경고 내용은 근거에서 생성합니다.
ANSWER_SECTIONS = (
    ("answer", "핵심 답변"),
    ("details", "추가 설명"),
    ("caution", "꼭 지킬 주의사항"),
)


def format_answer_items(items, item_formatter):
    """검사한 답변 항목을 종류별로 묶고 각 항목의 실제 출처 번호를 붙입니다."""
    blocks = []
    for section, title in ANSWER_SECTIONS:
        selected = [item for item in items if item.get("section", "answer") == section]
        if selected:
            # 근거 없는 빈 주의사항을 만들지 않으며, 같은 종류 안의 원래 순서는 유지합니다.
            body = "\n\n".join("- " + item_formatter(item) for item in selected)
            blocks.append("### " + title + "\n\n" + body)
    return "\n\n".join(blocks)


def sentence_breaks(text):
    """명확한 한국어 문장 끝에서 화면 줄바꿈만 추가합니다. 숫자·단위는 나누지 않습니다."""
    # [프로젝트 추가] Markdown은 줄바꿈 하나를 공백으로 표시하므로 명시적 줄바꿈을 씁니다.
    # 문장을 요약하거나 순서를 바꾸지 않습니다. 소수점이나 규격명은 문장 끝으로 취급하지 않습니다.
    return re.sub(
        r"((?:습니다|십시오|입니다|합니다|됩니다|하세요|해요|이다|된다)\.)[ \t]+(?![ \t]*\[\d+\])",
        r"\1  \n", text,
    )


def format_evidence_preview(result):
    """생성 전 자료 안내를 표시합니다. 자료 내용을 요약한 답변으로 만들지는 않습니다."""
    # [프로젝트 추가] 긴 원문을 여는 항목과 생성 버튼을 먼저 찾을 수 있게 합니다.
    # 미리보기는 생성 전 자료 안내입니다. 수치·조작·경고를 추출한 확정 답변은 만들지 않습니다.
    sources = result.get("sources", [])
    headings = ["- " + source["label"] + " · " + source["title"] for source in sources]
    return (
        "설명서에서 관련 자료를 찾았습니다.\n\n"
        + "\n\n".join(headings)
        + "\n\n아직 답변 정리 전입니다. ‘답변 정리하기’를 눌러 주세요. "
        + "원문·조건·주의사항은 아래 ‘검색에 사용한 설명서’에서 확인할 수 있습니다."
    )


def format_answer_for_display(result, *, evidence_preview=False):
    """검토된 결과의 화면용 글을 만듭니다. 원문·생성 답변·출처 데이터는 수정하지 않습니다."""
    # [프로젝트 추가] 답변 보류나 오류 안내는 기존 문구 그대로 표시합니다.
    status = result.get("status")
    original = result.get("answer", "")
    # [프로젝트 추가] 검색 실패를 '설명서 전체에 자료가 없음'으로 단정하지 않습니다.
    # 사용자에게 다음 입력 방법을 안내하며, 원래 상태·진단·후보는 결과 데이터에 보존합니다.
    if status == "insufficient_evidence":
        return (
            "현재 검색 결과에서 질문에 답할 근거를 찾지 못했습니다.\n\n"
            "부품 이름과 궁금한 내용을 함께 적어 다시 질문해주세요.\n\n"
            "- 예: ‘실외 미러 접는 방법을 알려줘.’\n"
            "- 이름을 모르시면 위치나 모양을 설명해주세요.\n\n"
            "설명서에 없는 내용은 추측해서 답하지 않습니다."
        )
    if status == "needs_review":
        return (
            "관련 자료는 찾았지만, 원본 설명서와의 확인이 남아 있어 답변을 보류합니다.\n\n"
            "자료 검토가 완료된 후 답변할 수 있습니다. 지금은 원본 PDF에서 해당 내용을 확인해주세요."
        )
    if evidence_preview and status == "evidence_excerpt" and result.get("sources"):
        return format_evidence_preview(result)
    if status not in {"evidence_excerpt", "partial_evidence", "generated_answer"}:
        return original

    sources = result.get("sources", [])
    headers = {source["label"] + " · " + source["title"] for source in sources}
    lines = []
    if status == "generated_answer" and not original.lstrip().startswith("### "):
        lines.append("### 답변")
    for raw_line in original.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line in headers:
            # 같은 실제 출처를 유지합니다. 발췌에서는 제목, 생성에서는 출처 목록입니다.
            lines.append(("- " if status == "generated_answer" else "### ") + line)
        elif line == "출처:":
            lines.append("### " + line)
        elif line in {"[주의]", "[경고]", "[참고]", "[그림 설명]"}:
            # 기존 표지에만 강조를 붙입니다. 문장 의미로 경고를 새로 분류하지 않습니다.
            lines.append("**" + line + "**")
        else:
            # 각주 *1 등이 Markdown의 기울임 표시로 해석되지 않게 시작 문자만 보호합니다.
            if status != "generated_answer" and re.match(r"^\*\d", line):
                line = "\\" + line
            lines.append(sentence_breaks(line))
    return "\n\n".join(lines)
