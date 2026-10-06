"""실제 평가 기록으로부터 차트 값을 계산합니다. 서버 연결은 하지 않습니다."""
from collections import Counter

COLORS = {"충족": "#168269", "부분 충족": "#d0932b", "미충족": "#c65a57"}
OUTCOMES = {"pass": "충족", "partial": "부분 충족", "fail": "미충족"}
CATEGORIES = {"Positive": "정상 질문", "Negative": "답할 수 없는 질문", "Edge": "경계 사례"}


def evaluation_groups(dataset, results):
    """개수와 비율은 판정 결과에서 다시 계산하여 저장된 요약과 분리합니다."""
    by_id = {r["test_id"]: r for r in results["results"]}
    values = []
    for category, title in CATEGORIES.items():
        group = [by_id[c["test_id"]] for c in dataset["cases"] if c["category"] == category]
        counts = Counter(r["review"]["overall_result"] for r in group)
        for order, (status, label) in enumerate(OUTCOMES.items()):
            count = counts[status]
            values.append({"group": title, "category": category, "total": len(group),
                           "outcome": label, "count": count, "percent": count / len(group) * 100,
                           "order": order, "label": f"{count}개"})
    return values


def retrieval_groups(results):
    groups = [
        ("근거 확보 · 답변 충족", "#168269", "필요한 근거를 찾고, 답변도 기준을 충족했습니다."),
        ("근거 확보 · 답변 보완 필요", "#d0932b", "근거는 있었지만 원문의 조건을 바꾸거나 내용을 빠뜨렸습니다."),
        ("필수 근거 미확보", "#c65a57", "관련 글은 검색됐지만 정답에 필요한 근거가 상위 5개에 없었습니다."),
    ]
    buckets = {name: [] for name, _, _ in groups}
    excluded = []
    for r in results["results"]:
        hit = r["review"]["retrieval_hit_at_5"]
        if hit is None:
            excluded.append(r["test_id"])
        else:
            name = groups[2][0] if not hit else groups[0][0] if r["review"]["overall_result"] == "pass" else groups[1][0]
            buckets[name].append(r["test_id"])
    total = sum(len(ids) for ids in buckets.values())
    return [{"group": name, "count": len(buckets[name]), "percent": len(buckets[name]) / total * 100,
             "color": color, "description": desc, "ids": " · ".join(buckets[name]),
             "label": f"{len(buckets[name])}개 · {len(buckets[name]) / total * 100:.1f}%"}
            for name, color, desc in groups], excluded


def base_spec(values, height=230):
    return {"$schema": "https://vega.github.io/schema/vega-lite/v5.json", "data": {"values": values},
            "height": height, "config": {"view": {"stroke": None}, "background": "transparent",
            "font": "Malgun Gothic, sans-serif", "axis": {"labelFontSize": 12, "titleFontSize": 12,
            "labelColor": "#52626b", "titleColor": "#52626b", "gridColor": "#edf1f2", "domain": False,
            "tickSize": 0, "labelPadding": 12}, "legend": {"labelFontSize": 12, "title": None,
            "orient": "bottom", "symbolType": "circle", "symbolSize": 140}}}


def category_spec(values, percentages=False):
    spec = base_spec(values)
    field = "percent" if percentages else "count"
    x = {"field": field, "type": "quantitative", "stack": "zero", "title": "비율 (%)" if percentages else "질문 수 (개)",
         "axis": {"tickCount": 5, "format": ".0f"}, "scale": {"domain": [0, 100 if percentages else 18]}}
    y = {"field": "group", "type": "nominal", "sort": list(CATEGORIES.values()), "title": None,
         "axis": {"labelLimit": 170}}
    color = {"field": "outcome", "type": "nominal", "scale": {"domain": list(COLORS), "range": list(COLORS.values())}}
    tooltip = [{"field": "group", "title": "질문 구분"}, {"field": "outcome", "title": "판정"},
               {"field": "count", "title": "질문 수"}, {"field": "total", "title": "구분 전체"},
               {"field": "percent", "title": "구분 안의 비율 (%)", "format": ".1f"}]
    spec["encoding"] = {"x": x, "y": y, "order": {"field": "order", "type": "quantitative"}, "tooltip": tooltip}
    spec["layer"] = [{"mark": {"type": "bar", "height": 40, "cornerRadius": 3}, "encoding": {"color": color}},
                     {"transform": [{"filter": "datum.count > 0"}], "mark": {"type": "text", "color": "white", "fontSize": 13,
                       "fontWeight": "bold"}, "encoding": {"text": {"field": "label"}, "x": {**x, "bandPosition": 0.5}}}]
    # 정량 스택의 중앙 위치는 별도 누적 계산으로 지정합니다.
    spec["layer"][1]["transform"] = [{"stack": field, "groupby": ["group"], "sort": [{"field": "order"}],
                                    "as": ["start", "end"]}, {"calculate": "(datum.start + datum.end) / 2", "as": "center"},
                                    {"filter": "datum.count > 0"}]
    spec["layer"][1]["encoding"]["x"] = {"field": "center", "type": "quantitative", "title": x["title"],
                                                     "scale": x["scale"], "axis": x["axis"]}
    return spec


def retrieval_spec(values):
    spec = base_spec(values, 230)
    order = [v["group"] for v in values]
    spec["encoding"] = {"y": {"field": "group", "type": "nominal", "sort": order, "title": None,
                               "axis": {"labelLimit": 210}},
                        "x": {"field": "count", "type": "quantitative", "title": "질문 수 (개)",
                              "scale": {"domain": [0, 23]}, "axis": {"tickCount": 5, "format": ".0f"}},
                        "tooltip": [{"field": "group", "title": "검색과 답변"}, {"field": "count", "title": "질문 수"},
                                    {"field": "percent", "title": "23개 안의 비율 (%)", "format": ".1f"},
                                    {"field": "description", "title": "의미"}, {"field": "ids", "title": "질문 번호"}]}
    spec["layer"] = [{"mark": {"type": "bar", "height": 40, "cornerRadiusEnd": 4},
                      "encoding": {"color": {"field": "color", "type": "nominal", "scale": None, "legend": None}}},
                     {"mark": {"type": "text", "align": "left", "dx": 9, "fontSize": 13, "color": "#24383b"},
                      "encoding": {"text": {"field": "label"}}}]
    return spec
