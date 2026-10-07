"""실제 평가 기록으로부터 차트 값을 계산합니다. 서버 연결은 하지 않습니다."""
from collections import Counter

COLORS = {"충족": "#138878", "부분 충족": "#d49a36", "미충족": "#c36a78"}
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
        ("근거 확보 · 답변 충족", "#138878", "필요한 근거를 찾고, 답변도 기준을 충족했습니다."),
        ("근거 확보 · 답변 보완 필요", "#d49a36", "근거는 있었지만 원문의 조건을 바꾸거나 내용을 빠뜨렸습니다."),
        ("필수 근거 미확보", "#c36a78", "관련 글은 검색됐지만 정답에 필요한 근거가 상위 5개에 없었습니다."),
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
    return {"$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "data": {"values": values}, "height": height,
            "padding": {"left": 4, "right": 24, "top": 16, "bottom": 8},
            "config": {"view": {"stroke": None}, "background": "transparent",
                       "font": "Malgun Gothic, sans-serif",
                       "axis": {"labelFontSize": 12, "titleFontSize": 12, "titleFontWeight": "normal",
                                "labelColor": "#657789", "titleColor": "#657789", "titlePadding": 18,
                                "gridColor": "#e9eef3", "gridDash": [3, 4], "domain": False,
                                "tickSize": 0, "labelPadding": 10},
                       "axisY": {"grid": False},
                       "legend": {"labelFontSize": 12, "labelColor": "#526477", "title": None,
                                  "orient": "bottom", "symbolType": "circle", "symbolSize": 110,
                                  "padding": 14, "columnPadding": 22},
                       "bar": {"binSpacing": 3}}}


def chapter_spec(values):
    total = sum(r["청크 수"] for r in values)
    rows = [{**r, "비중": r["청크 수"] / total * 100 if total else 0} for r in values]
    spec = base_spec(rows, 380)
    spec["encoding"] = {
        "y": {"field": "장", "type": "nominal", "sort": "-x", "title": None,
              "axis": {"labelLimit": 180}},
        "x": {"field": "청크 수", "type": "quantitative", "title": "청크 수 (개)",
              "scale": {"domain": [0, max((r["청크 수"] for r in rows), default=1) * 1.18]}},
        "tooltip": [{"field": "장"}, {"field": "청크 수", "type": "quantitative"},
                    {"field": "비중", "type": "quantitative", "title": "전체 비중 (%)", "format": ".1f"},
                    {"field": "목차 항목", "type": "quantitative"}]}
    spec["layer"] = [
        {"mark": {"type": "bar", "height": 19, "cornerRadiusEnd": 6}, "encoding": {
            "color": {"condition": {"test": "datum['청크 수'] >= 390", "value": "#138878"},
                      "value": "#9ac8c2"}}},
        {"mark": {"type": "text", "align": "left", "dx": 8, "color": "#33485c", "fontSize": 12},
         "encoding": {"text": {"field": "청크 수", "type": "quantitative", "format": ","}}}]
    return spec


def length_spec(bins):
    peak = max((r["청크 수"] for r in bins), default=0)
    spec = base_spec(bins, 280)
    spec["encoding"] = {
        "x": {"field": "구간", "type": "ordinal", "sort": [r["구간"] for r in bins],
              "title": "본문 길이 (토큰)", "axis": {"labelAngle": -50, "labelLimit": 120}},
        "y": {"field": "청크 수", "type": "quantitative", "title": "청크 수 (개)",
              "scale": {"domain": [0, max(peak * 1.15, 1)]}},
        "tooltip": [{"field": "구간"}, {"field": "청크 수", "type": "quantitative"}]}
    spec["layer"] = [
        {"mark": {"type": "bar", "cornerRadiusTopLeft": 4, "cornerRadiusTopRight": 4},
         "encoding": {"color": {"condition": {"test": f"datum['청크 수'] == {peak}", "value": "#138878"},
                                "value": "#9ac8c2"}}},
        {"transform": [{"filter": f"datum['청크 수'] == {peak} && datum['청크 수'] > 0"}],
         "mark": {"type": "text", "dy": -12, "color": "#138878", "fontWeight": "bold", "fontSize": 13},
         "encoding": {"text": {"field": "청크 수", "type": "quantitative", "format": ","}}}]
    return spec


def version_spec(versions):
    rows = []
    labels = [v["label"] for v in versions]
    for version in versions:
        start = 0
        for status, title in OUTCOMES.items():
            count = version["summary"]["overall_counts"].get(status, 0)
            rows.append({"버전": version["label"], "판정": title, "질문 수": count,
                         "start": start, "end": start + count, "center": start + count / 2,
                         "표시": f"{count}개"})
            start += count
    spec = base_spec(rows, 220)
    axis = {"type": "quantitative", "title": "질문 수 (개)", "scale": {"domain": [0, 30]},
            "axis": {"values": [0, 5, 10, 15, 20, 25, 30]}}
    spec["encoding"] = {"y": {"field": "버전", "type": "nominal", "sort": labels, "title": None},
                        "tooltip": [{"field": "버전"}, {"field": "판정"},
                                    {"field": "질문 수", "type": "quantitative"}]}
    spec["layer"] = [
        {"mark": {"type": "bar", "height": 38}, "encoding": {
            "x": {**axis, "field": "start"}, "x2": {"field": "end"},
            "color": {"field": "판정", "type": "nominal", "scale": {
                "domain": list(COLORS), "range": list(COLORS.values())}}}},
        {"transform": [{"filter": "datum['질문 수'] > 0"}],
         "mark": {"type": "text", "color": "white", "fontSize": 13, "fontWeight": "bold"},
         "encoding": {"x": {**axis, "field": "center"}, "text": {"field": "표시"}}}]
    return spec


def category_spec(values, percentages=False):
    # 누적 위치를 직접 계산해 막대와 숫자에 같은 좌표를 사용합니다.
    field = "percent" if percentages else "count"
    prepared = []
    for title in CATEGORIES.values():
        start = 0
        for row in sorted((v for v in values if v["group"] == title), key=lambda v: v["order"]):
            end = start + row[field]
            prepared.append({**row, "segment_start": start, "segment_end": end,
                             "segment_center": (start + end) / 2,
                             "display_label": f"{row['percent']:.1f}%" if percentages else f"{row['count']}개"})
            start = end
    maximum = 100 if percentages else max((r["total"] for r in values), default=1)
    spec = base_spec(prepared, 240)
    x = {"field": "segment_start", "type": "quantitative", "title": "비율 (%)" if percentages else "질문 수 (개)",
         "scale": {"domain": [0, maximum]}, "axis": {"tickCount": 5, "format": ".0f"}}
    spec["encoding"] = {
        "y": {"field": "group", "type": "nominal", "sort": list(CATEGORIES.values()), "title": None,
              "axis": {"labelLimit": 170}},
        "tooltip": [{"field": "group", "title": "질문 유형"}, {"field": "outcome", "title": "판정"},
                    {"field": "count", "type": "quantitative", "title": "질문 수"},
                    {"field": "total", "type": "quantitative", "title": "유형 전체"},
                    {"field": "percent", "type": "quantitative", "title": "유형 안의 비율 (%)", "format": ".1f"}]}
    spec["layer"] = [
        {"mark": {"type": "bar", "height": 40}, "encoding": {
            "x": x, "x2": {"field": "segment_end"},
            "color": {"field": "outcome", "type": "nominal", "scale": {
                "domain": list(COLORS), "range": list(COLORS.values())}}}},
        {"transform": [{"filter": "datum.count > 0"}],
         "mark": {"type": "text", "color": "white", "fontSize": 13, "fontWeight": "bold"},
         "encoding": {"x": {**x, "field": "segment_center"},
                      "text": {"field": "display_label", "type": "nominal"}}}]
    return spec


def retrieval_spec(values):
    spec = base_spec(values, 240)
    order = [v["group"] for v in values]
    spec["encoding"] = {"y": {"field": "group", "type": "nominal", "sort": order, "title": None,
                               "axis": {"labelLimit": 210}},
                        "x": {"field": "count", "type": "quantitative", "title": "질문 수 (개)",
                              "scale": {"domain": [0, max(sum(v["count"] for v in values) * 1.3, 1)]}, "axis": {"values": [0, 5, 10, 15, 20]}},
                        "tooltip": [{"field": "group", "title": "검색과 답변"}, {"field": "count", "title": "질문 수"},
                                    {"field": "percent", "title": "23개 안의 비율 (%)", "format": ".1f"},
                                    {"field": "description", "title": "의미"}, {"field": "ids", "title": "질문 번호"}]}
    spec["layer"] = [{"mark": {"type": "bar", "height": 26, "cornerRadiusEnd": 6},
                      "encoding": {"color": {"field": "color", "type": "nominal", "scale": None, "legend": None}}},
                     {"mark": {"type": "text", "align": "left", "dx": 9, "fontSize": 13, "color": "#24383b"},
                      "encoding": {"text": {"field": "label"}}}]
    return spec


def progress_spec(versions, metric):
    definitions = {
        "answers": ("답변", "답변 충족", lambda s: s["overall_counts"]["pass"], lambda s: s["executed"]),
        "hits": ("근거", "정답 근거 확보", lambda s: s["retrieval_hit_count"], lambda s: s["retrieval_scored_cases"]),
        "facts": ("내용", "필수 내용 근거 확보", lambda s: s["covered_facts"], lambda s: s["total_facts"]),
    }
    _, title, numerator, denominator = definitions[metric]
    rows = []
    for index, version in enumerate(versions):
        summary = version["summary"]
        n, d = numerator(summary), denominator(summary)
        rows.append({"버전": ["초기", "1차", "2차"][index], "비율": n / d * 100 if d else 0,
                     "개수": f"{n}/{d}", "상세": version["label"]})
    spec = base_spec(rows, 240)
    spec["encoding"] = {
        "x": {"field": "버전", "type": "ordinal", "sort": [r["버전"] for r in rows], "title": None,
              "axis": {"labelAngle": 0}},
        "y": {"field": "비율", "type": "quantitative", "title": "비율 (%)",
              "scale": {"domain": [0, 100]}, "axis": {"values": [0, 25, 50, 75, 100]}},
        "tooltip": [{"field": "상세", "title": "버전"}, {"field": "개수", "title": title},
                    {"field": "비율", "type": "quantitative", "format": ".1f", "title": "비율 (%)"}]}
    spec["layer"] = [
        {"mark": {"type": "bar", "size": 36, "cornerRadiusTopLeft": 5, "cornerRadiusTopRight": 5},
         "encoding": {"color": {"condition": {"test": "datum['버전'] == '2차'", "value": "#138878"},
                                "value": "#b5cfda"}}},
        {"mark": {"type": "text", "dy": -12, "color": "#33485c", "fontSize": 13, "fontWeight": "bold"},
         "encoding": {"text": {"field": "개수"}}}]
    return spec


def timing_spec(versions):
    rows = [{"버전": v["label"], "초": v["summary"]["mean_app_elapsed_seconds"],
             "표시": f"{v['summary']['mean_app_elapsed_seconds']:.2f}초"} for v in versions]
    spec = base_spec(rows, 180)
    spec["encoding"] = {
        "y": {"field": "버전", "type": "nominal", "sort": [r["버전"] for r in rows], "title": None},
        "x": {"field": "초", "type": "quantitative", "title": "평균 앱 처리 시간 (초)",
              "scale": {"domain": [0, max(r["초"] for r in rows) * 1.25]}},
        "tooltip": [{"field": "버전"}, {"field": "초", "type": "quantitative", "format": ".2f"}]}
    spec["layer"] = [
        {"mark": {"type": "bar", "height": 24, "cornerRadiusEnd": 5, "color": "#7b95af"}},
        {"mark": {"type": "text", "align": "left", "dx": 8, "color": "#33485c", "fontSize": 12},
         "encoding": {"text": {"field": "표시"}}}]
    return spec
