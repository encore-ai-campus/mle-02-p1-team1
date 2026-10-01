"""노트북에서 정한 30개 질문과 기대 출처로 검색 방식만 비교합니다."""

# [프로젝트 추가] 06·11·12번의 고정 질문과 기대 출처로 같은 조건의 검색 순위를 비교합니다.
# 기대 출처는 평가에서만 쓰며 retrieval.py의 순위 계산에는 전달하지 않습니다.

# 정답 출처는 검색 점수를 만들 때 사용하지 않고, 검색이 끝난 뒤에만 비교합니다.
BASELINE_QUESTIONS = [
    [
        "실외 미러를 접는 버튼은 차량 내부 안내도의 어디에 있나요?",
        "overview_33"
    ],
    [
        "후드 열림 레버의 위치를 보여주는 안내도를 찾아줘.",
        "overview_33"
    ],
    [
        "지문 인증 시스템은 차량 내부 안내도에서 몇 번인가요?",
        "overview_33"
    ],
    [
        "유리창 잠금 버튼과 전자식 차일드 락 버튼 위치를 알려줘.",
        "overview_33"
    ],
    [
        "시동 버튼 위치를 보여주는 안내도가 필요해.",
        "overview_34"
    ],
    [
        "스마트폰 무선 충전 표시등은 내부 안내도의 어느 항목인가요?",
        "overview_34"
    ],
    [
        "글로브 박스와 동승석 트레이의 위치를 찾아줘.",
        "overview_34"
    ],
    [
        "주차 안전 버튼과 주차 뷰 버튼 위치가 나오는 안내도를 보여줘.",
        "overview_34"
    ],
    [
        "와이퍼와 워셔 스위치는 내부 안내도 몇 번인가요?",
        "overview_35"
    ],
    [
        "블루투스 핸즈프리 버튼과 음성 인식 버튼은 어디에 있나요?",
        "overview_35"
    ],
    [
        "패들 쉬프트 위치를 보여주는 내부 안내도를 찾아줘.",
        "overview_35"
    ],
    [
        "차간거리 버튼과 차로 주행 보조 버튼 위치를 찾아줘.",
        "overview_35"
    ],
    [
        "1.6 T-GDi HEV에 표시된 엔진 오일 SAE 점도는 무엇인가요?",
        "table_44"
    ],
    [
        "0W-20이 표시된 엔진 오일 점도 표를 보여줘.",
        "table_44"
    ],
    [
        "엔진 오일 SAE 점도 표의 온도 눈금은 어디부터 어디까지인가요?",
        "table_44"
    ],
    [
        "안전벨트를 착용할 때 골반띠는 어디를 지나야 하나요?",
        "seatbelt_54"
    ],
    [
        "안전벨트 버클을 얼마나 밀어 넣어야 하나요?",
        "seatbelt_54"
    ],
    [
        "안전벨트 스토퍼를 쓰면 어떤 문제가 생기나요?",
        "seatbelt_54"
    ],
    [
        "차단 클립을 버클에 꽂으면 경고등과 경고음은 어떻게 되나요?",
        "seatbelt_54"
    ],
    [
        "뒷좌석 놀이방 매트는 왜 안전벨트 사용에 문제가 되나요?",
        "seatbelt_54"
    ]
]


# [프로젝트 추가] 기존 20문항과 새 10문항의 기대 출처를 같은 평가 버전으로 유지합니다.
# PDF 110쪽의 다른 버클 근거는 source_review.md에 기록하고 기존 정답을 결과에 맞춰 바꾸지 않았습니다.
def make_cases(parents):
    """기존 20개 질문과 원본에서 확인한 10개 질문의 기대 출처를 만듭니다."""
    def find_id(title, page):
        """제목과 시작 페이지가 일치하는 유일한 원문 ID를 찾습니다."""
        matches = [p["metadata"]["record_id"] for p in parents
                   if p["metadata"]["title"] == title and p["metadata"]["pdf_page_number"] == page]
        if len(matches) != 1:
            raise ValueError(f"평가 출처를 확인해야 합니다: {title}, PDF {page}쪽")
        return matches[0]

    oil_table_id = find_id("추천 오일 및 용량", 43)
    oil_notes_id = find_id("추천 오일 및 용량 — 각주 및 주의사항", 43)
    paddle_id = find_id("패들 쉬프트 (수동 변속 모드)", 397)
    table_398_id = find_id("드라이브 모드 별 패들 쉬프트 레버 기능", 398)
    table_402_id = find_id("주행 모드별 패들 쉬프트의 기능", 402)
    limit_402_id = find_id("회생 제동 시스템 사용 제한", 402)
    cases = [{"question": question, "expected_ids": [expected_id], "group": "기존 확인 질문"}
             for question, expected_id in BASELINE_QUESTIONS] + [
        {"question": "엔진 오일의 용량과 추천 사양을 알려줘.", "expected_ids": [oil_table_id]},
        {"question": "자동 변속기 오일 용량과 추천 사양은?", "expected_ids": [oil_table_id]},
        {"question": "리어 디퍼런셜 오일과 트랜스퍼 케이스 오일 용량은?", "expected_ids": [oil_table_id]},
        {"question": "브레이크액의 추천 규격과 관련 각주를 찾아줘.", "expected_ids": [oil_table_id, oil_notes_id]},
        {"question": "엔진 오일 4.8리터는 일반적인 교체 시 주입량인가요?", "expected_ids": [oil_notes_id]},
        {"question": "엔진 오일 첨가제를 사용하면 안 되는 이유는?", "expected_ids": [oil_notes_id]},
        {"question": "ECO 모드에서 패들 쉬프트 플러스 레버를 당기면?", "expected_ids": [table_398_id, table_402_id]},
        {"question": "SPORT 모드에서 패들 쉬프트 레버는 어떤 기능인가요?", "expected_ids": [table_398_id, table_402_id, paddle_id]},
        {"question": "패들 쉬프트를 동시에 당기면 변속되나요?", "expected_ids": [paddle_id]},
        {"question": "패들 쉬프트로 회생 제동량을 변경할 수 없는 상황은?", "expected_ids": [limit_402_id]},
    ]
    known_ids = {p["metadata"]["record_id"] for p in parents}
    for case in cases:
        case.setdefault("group", "이번 원본 확인 질문")
        if not set(case["expected_ids"]) <= known_ids:
            raise ValueError("평가 질문의 기대 출처가 현재 자료에 없습니다.")
    return cases


# [프로젝트 추가] 첫 후보·상위 3개에 기대 출처가 있는지 비교합니다.
# 계획의 Hit@5·MRR이나 생성 답변 정확도는 이 함수가 측정하지 않습니다.
def compare_search(engine, progress=print):
    """동일한 질문 벡터로 세 검색 방식의 출처 순위를 비교하며 결과를 메모리에 둡니다."""
    cases = make_cases(engine.parents)
    if any(engine.token_counter.count(c["question"]) > engine.token_counter.budget for c in cases):
        raise ValueError("평가 질문이 모델 입력 한도를 넘었습니다.")
    vectors = engine.model.encode(
        [c["question"] for c in cases], batch_size=16, convert_to_numpy=True,
        normalize_embeddings=True, show_progress_bar=False,
    )
    results = []
    for case, vector in zip(cases, vectors):
        expected = set(case["expected_ids"])
        row = dict(case)
        methods = {
            "baseline": engine.baseline_rank(case["question"], vector),
            "chunk": engine.rank(case["question"], vector, use_routing=False),
            "routed": engine.rank(case["question"], vector, use_routing=True),
        }
        for name, hits in methods.items():
            ids = [h["parent_record"]["metadata"]["record_id"] for h in hits]
            row[name + "_ids"] = ids
            row[name + "_top1"] = ids[0] in expected
            row[name + "_top3"] = bool(expected.intersection(ids))
        results.append(row)
    if progress:
        for name in ["baseline", "chunk", "routed"]:
            progress(f'{name}: 첫 후보 {sum(r[name + "_top1"] for r in results)}/30 | '
                     f'상위 세 후보 {sum(r[name + "_top3"] for r in results)}/30')
        for row in results:
            if not row["routed_top3"]:
                progress(f'기대 출처가 상위 3개에 없는 질문: {row["question"]}')
    return results
