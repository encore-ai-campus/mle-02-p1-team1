"""검색 범위와 답변 선택이 같은 한국어 질문 목적을 사용하도록 합니다."""

import re


def evidence_intent(question):
    """그림의 번호·위치와 동작/허용/조절 시점 질문을 구별합니다. 범용 의미 분석은 아닙니다."""
    text = re.sub(r"\s+", "", question)
    # [프로젝트 추가] 조절할 시점을 물으면 '위치'라는 말이 있어도 조작 지침을 찾습니다.
    timing_action = (any(word in text for word in ("출발전", "출발하기전", "주행중", "운전중"))
                     and any(word in text for word in ("조절", "조정", "맞추", "맞춰", "조작")))
    selection_action = ("무엇" in text and "선택" in text
                        and any(word in text for word in ("스위치", "버튼", "모드")))
    action_request = timing_action or selection_action or any(word in text for word in (
        "방법", "해도", "열어도", "사용해도", "조작해도", "조절해도", "어떻게", "해야", "하면", "했을때"))
    if action_request:
        return "procedure"
    # [프로젝트 추가] 부품의 그림 번호 요청을 기능 사용 질문과 구별합니다. 평가 정답 ID는 쓰지 않습니다.
    diagram_number = "번호" in text and any(word in text for word in ("그림", "도안", "안내도", "표시", "붙은"))
    if diagram_number or any(word in text for word in ("위치", "어디", "몇번", "안내도")):
        return "location"
    return "fact"
