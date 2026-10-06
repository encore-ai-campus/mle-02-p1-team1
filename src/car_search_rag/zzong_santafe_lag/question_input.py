"""원래 질문을 보존하고 명확한 용어만 정리하거나 확인 질문을 만듭니다."""

import re


# [프로젝트 추가] 대응이 분명한 용어만 등록합니다. 부품 번호·정답·쪽수는 넣지 않습니다.
# 숫자·단위·부정·주행 조건·사용자의 말투는 지우지 않습니다. 자동 오타 추측은 하지 않습니다.
ALIASES = (
    (r"(?<![가-힣A-Za-z0-9])사이드\s*미러", "실외 미러"),
    (r"(?<![가-힣A-Za-z0-9])엔진오일", "엔진 오일"),
    (r"(?<![가-힣A-Za-z0-9])안전\s+벨트", "안전벨트"),
    (r"(?<![가-힣A-Za-z0-9])테일\s+게이트", "테일게이트"),
)


def prepare_question(question):
    """검색용 질문·적용한 용어 변경·확인 안내를 반환합니다. DB·모델 호출은 없습니다."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError("질문을 입력해 주세요.")
    original = question.strip()
    search = re.sub(r"\s+", " ", original)
    changes = []
    for pattern, replacement in ALIASES:
        found = list(dict.fromkeys(re.findall(pattern, search)))
        for term in found:
            if term != replacement:
                changes.append({"original": term, "search_term": replacement})
        search = re.sub(pattern, replacement, search)

    # [프로젝트 추가] '빽미러'는 실외/실내 중 어느 미러인지 추측하지 않습니다.
    # 정확한 부품명이 함께 있으면 그 질문을 그대로 검색합니다.
    clarification = ""
    if (re.search(r"(?:빽|백)\s*미러", search)
            and not re.search(r"실외\s*미러|실내\s*미러|룸\s*미러", search)):
        clarification = (
            "어느 미러를 말씀하시나요?\n\n"
            "- 차 바깥 양쪽의 미러: ‘실외 미러 접는 방법’처럼 입력해주세요.\n"
            "- 차 안에서 뒤를 보는 미러: ‘실내 미러 조절 방법’처럼 입력해주세요."
        )
    # 대상 없는 짧은 요청만 확인합니다. '미러가 안 돼'처럼 대상을 포함하면 막지 않습니다.
    compact = re.sub(r"[\s?!？！.,。~]", "", search)
    # [프로젝트 추가] 특정 증상을 말하지 않은 차량 작동 중단 표현만 확인합니다.
    # 과거/가정/부정 표현이나 이미 부품·증상을 밝힌 문장을 일반 고장으로 바꾸지 않습니다.
    unclear_vehicle_symptom = re.fullmatch(
        r"(?:내)?(?:차|차량|자동차)(?:가|이|는)?(?:갑자기|방금|지금)?"
        r"(?:퍼졌어|퍼졌어요|퍼졌는데|먹통이야|먹통이에요|멈췄어|멈췄어요)", compact,
    )
    if not clarification and unclear_vehicle_symptom:
        clarification = (
            "차가 작동하지 않는 상황을 조금 더 알려주세요. 어떤 상태인가요?\n\n"
            "- 주행 중 시동이 꺼졌나요?\n"
            "- 시동이 걸리지 않나요?\n"
            "- 시동은 켜져 있는데 가속이 안 되나요?\n\n"
            "현재 주행 중인지, 정차한 상태인지도 알려주세요. "
            "알려주신 상황으로 설명서의 관련 내용을 찾겠습니다. 실제 고장 원인은 이 설명서만으로 확정하지 않습니다."
        )
    vague = re.fullmatch(
        r"(?:(?:이거|이게|그거|그게|저거|저게|이것|그것)(?:는|가|도)?)?"
        r"(?:안돼|안돼요|안됩니다|안되는데|작동안돼|작동이안돼|왜안돼|왜안돼요|"
        r"왜이래|왜이래요|어떻게해|어떻게해요|어떻게하나요|어디야|어디있어|알려줘|알려주세요)",
        compact,
    )
    if not clarification and vague:
        clarification = (
            "어떤 부품이나 기능에 대해 궁금하신가요?\n\n"
            "이름과 상황을 함께 적어주세요. 예: ‘실외 미러가 접히지 않아요’ 또는 "
            "‘스마트 테일게이트 설정 방법을 알려줘.’\n\n"
            "부품 이름을 모르시면 위치나 모양을 설명해주세요."
        )
    return {"rule_version": "conservative_terms_v1", "original_question": original,
            "search_question": search, "term_changes": changes,
            "clarification_message": clarification}


def has_starting_symptom(question):
    """명시적 시동 불가 표현을 구별합니다. 계기판 상태가 추가돼도 같은 증상으로 유지합니다."""
    compact = re.sub(r"[\s?!？！.,。~]", "", question)
    return bool(re.search(r"시동(?:이|은)?(?:잘)?(?:안걸|걸리지않|불가)", compact)
                and not any(word in compact for word in ("경우", "가정", "예시", "방법", "절차", "아니"))
                and not re.search(r"안걸리면|안걸릴때|걸리지않으면|걸리지않을때", compact))


def engine_symptom_kind(question):
    """명시적 시동 불가와 주행 중 시동 꺼짐을 구별합니다. 다른 증상은 추측하지 않습니다."""
    compact = re.sub(r"[\s?!？！.,。~]", "", question)
    no_start = has_starting_symptom(question)
    stopped = (bool(re.search(r"(?:주행|운전)중.*시동(?:이|은)?(?:갑자기)?꺼", compact))
               and not any(word in compact for word in ("아니", "가정", "예시", "경우", "꺼지면", "꺼질때")))
    # 두 상태를 함께 설명한 경우 한 상태로 덮어쓰지 않습니다.
    if no_start and stopped:
        return "mixed"
    return "no_start" if no_start else "driving_stall" if stopped else None


def symptom_candidate_fits(question, title):
    """질문과 다른 시동 상황의 후보 제목을 제외합니다. 자료 본문·주의사항은 변경하지 않습니다."""
    kind = engine_symptom_kind(question)
    text = re.sub(r"\s+", "", title)
    compact = re.sub(r"\s+", "", question)
    if kind == "no_start":
        # 정차 여부를 생략해도 '안 걸림'을 '주행 중 꺼짐'으로 해석하지 않습니다.
        if re.search(r"(?:주행|운전)중.*시동.*꺼", text):
            return False
        # 일반 시동 불가에 원격 시동 설정을 추가하지 않습니다. 사용자가 원격을 명시하면 유지합니다.
        if "원격" in text and "원격" not in compact:
            return False
    elif kind == "driving_stall":
        return bool(re.search(r"(?:주행|운전)중.*시동.*꺼", text))
    return True


def starting_symptom_prompt(question):
    """명시적인 시동 불가 증상에만 계기판 상태를 묻습니다. 원인·조치·진단은 만들지 않습니다."""
    # [프로젝트 추가] 고정 확인 질문입니다. 계기판을 이미 언급하면 재질문하지 않습니다.
    if not has_starting_symptom(question) or "계기판" in question:
        return ""
    return (
        "증상을 조금 더 알려주세요. **시동 버튼을 누르면 계기판이 켜지나요?**\n\n"
        "예: ‘시동이 안 걸리고 계기판은 켜져요’ 또는 ‘시동이 안 걸리고 계기판도 안 켜져요’처럼 알려주세요."
    )


def clarification_result(prepared):
    """대상이 모호할 때 검색·생성 대신 보여줄 결과입니다. 출처를 임의로 붙이지 않습니다."""
    return {"question": prepared["original_question"], "status": "needs_clarification",
            "answer_mode": "clarification", "answer": prepared["clarification_message"],
            "reason": "", "sources": [], "images": [], "pending_image_references": [],
            "review_candidates": [], "run_id": None, "query_embedding_api_called": False,
            "retrieval_performed": False, "llm_called": False,
            "db_written": False, "storage_uploaded": False, "input_processing": prepared}
