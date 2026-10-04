"""Evaluate title-only image descriptions on the fixed Sonata 100-image sample.

This is an offline PDF diagnostic. It does not call an API or touch DB/Storage.
"""
from __future__ import annotations

import json
import re
import statistics
from collections import Counter
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "data" / "DN8_2026_ko_KR.pdf"
DOCS = ROOT / "src" / "car_search_rag" / "car_search" / "docs"
SAMPLE = DOCS / "IMAGE_DESC_TEXT_LLM_100_GPT56_TERRA.json"
OUT_JSON = DOCS / "IMAGE_DESC_HEADING_100.json"
OUT_MD = DOCS / "IMAGE_DESC_HEADING_100.md"
CONTACT = ROOT / "tmp" / "IMAGE_DESC_HEADING_CONTACT.png"
NONE_CONTACT = ROOT / "tmp" / "IMAGE_DESC_HEADING_NONE_CONTACT.png"


def clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^2C_[A-Za-z0-9_]+\s*", "", text)
    return text


def span_lines(page: pymupdf.Page) -> list[dict]:
    lines = []
    for block_index, block in enumerate(page.get_text("dict").get("blocks", [])):
        for line in block.get("lines", []):
            spans = [s for s in line.get("spans", []) if s.get("text", "").strip()]
            if not spans:
                continue
            raw = "".join(s["text"] for s in spans)
            text = clean(raw)
            if not text:
                continue
            bbox = [min(s["bbox"][0] for s in spans), min(s["bbox"][1] for s in spans),
                    max(s["bbox"][2] for s in spans), max(s["bbox"][3] for s in spans)]
            sizes = [float(s["size"]) for s in spans]
            fonts = list(dict.fromkeys(str(s.get("font", "")) for s in spans))
            flags = [int(s.get("flags", 0)) for s in spans]
            lines.append({
                "text": text, "raw_text": raw, "bbox": [round(float(v), 2) for v in bbox],
                "font_size": round(statistics.median(sizes), 2), "max_font_size": round(max(sizes), 2),
                "font": " / ".join(fonts), "flags": flags,
                "bold": any(f & 16 for f in flags) or any("bold" in f.lower() for f in fonts),
                "source_block_index": block_index,
            })
    # PDF headings can wrap words or a final fragment onto a separate line. Merge
    # adjacent lines only within the same PyMuPDF block, style and close vertical gap.
    lines.sort(key=lambda x: (x["source_block_index"], x["bbox"][1], x["bbox"][0]))
    merged: list[dict] = []
    for row in lines:
        if (merged and row["source_block_index"] == merged[-1]["source_block_index"]
                and abs(row["max_font_size"] - merged[-1]["max_font_size"]) <= 0.25
                and -3.0 <= row["bbox"][1] - merged[-1]["bbox"][3] <= 2.5):
            prior = merged[-1]
            prior["text"] += row["text"]
            prior["raw_text"] += row["raw_text"]
            prior["bbox"][2] = max(prior["bbox"][2], row["bbox"][2])
            prior["bbox"][3] = row["bbox"][3]
            prior["font"] = " / ".join(dict.fromkeys((prior["font"] + " / " + row["font"]).split(" / ")))
            prior["flags"] += row["flags"]
            prior["bold"] = prior["bold"] or row["bold"]
        else:
            merged.append(row)
    # Some PDF heading fragments are split into separate text blocks; join only
    # a short continuation directly below an aligned same-style text line.
    joined: list[dict] = []
    for row in sorted(merged, key=lambda x: (x["bbox"][1], x["bbox"][0])):
        if (joined and len(row["text"]) <= 8 and len(joined[-1]["text"]) >= 8
                and abs(row["max_font_size"] - joined[-1]["max_font_size"]) <= 0.25
                and -3.0 <= row["bbox"][1] - joined[-1]["bbox"][3] <= 2.5
                and overlap_x(row["bbox"], joined[-1]["bbox"]) >= 0.5):
            prior = joined[-1]
            prior["text"] += row["text"]
            prior["raw_text"] += row["raw_text"]
            prior["bbox"][2] = max(prior["bbox"][2], row["bbox"][2])
            prior["bbox"][3] = row["bbox"][3]
            prior["font"] = " / ".join(dict.fromkeys((prior["font"] + " / " + row["font"]).split(" / ")))
            prior["flags"] += row["flags"]
            prior["bold"] = prior["bold"] or row["bold"]
        else:
            joined.append(row)
    return joined


def overlap_x(a, b):
    w = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    return w / max(1.0, min(a[2] - a[0], b[2] - b[0]))


def same_column(image, text, page_width):
    # Geometric column match: meaningful horizontal overlap, or centers in same half.
    if overlap_x(image, text) >= 0.25:
        return True
    mid = page_width / 2
    return (image[0] < mid) == (text[0] < mid) and abs((image[0] + image[2]) / 2 - (text[0] + text[2]) / 2) < page_width * 0.24


def heading_like(row, body_median, size_q75, distance_pt):
    text = row["text"]
    size = row["max_font_size"]
    # The PDF's 9pt body/12pt title clusters are complemented by short 10pt
    # Medium-style labels/headings. The style cue only applies near the image.
    large = size >= max(body_median * (4 / 3), size_q75)
    compact = len(text) <= 64 and len(text.split()) <= 12
    meaningful = sum(ch.isalpha() for ch in text) >= 4
    hangul_count = len(re.findall(r"[가-힣]", text))
    font_style = row["font"].lower()
    emphasized = row["bold"] or "medium" in font_style or "bold" in font_style
    styled_short = emphasized and size > body_median and len(text) <= 40 and distance_pt <= 72
    not_page_num = not re.fullmatch(r"[0-9\s./-]+", text)
    not_internal_id = not text.startswith("2C_")
    not_bullet = not re.match(r"^(?:[•●▪-]|\d+[.)])\s*", text)
    type_label = bool(re.fullmatch(r"(?:[A-C]|타입\s*[A-C])", text, re.I))
    not_small_type_label = not type_label or size >= body_median * (4 / 3)
    return ((large or styled_short) and compact and meaningful and hangul_count >= 2
            and not_page_num and not_internal_id and not_bullet and not_small_type_label)


def main():
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    assert sample["sample_seed"] == 20261004 and sample["sample_size"] == 100
    doc = pymupdf.open(PDF)
    page_cache = {}
    span_sizes = []
    long_span_sizes = []
    line_lengths = []
    for pn in sorted({int(r["page_no"]) for r in sample["rows"]}):
        page = doc[pn - 1]
        lines = span_lines(page)
        page_cache[pn] = (lines, float(page.rect.width))
        for block in page.get_text("dict").get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if text:
                        span_sizes.append(float(span["size"]))
                        if len(text) >= 20:
                            long_span_sizes.append(float(span["size"]))
                        line_lengths.append(len(text))

    body_median = statistics.median(long_span_sizes or span_sizes)
    sorted_sizes = sorted(span_sizes)
    size_q75 = sorted_sizes[int((len(sorted_sizes) - 1) * 0.75)]
    size_q90 = sorted_sizes[int((len(sorted_sizes) - 1) * 0.90)]
    line_p95 = sorted(line_lengths)[int((len(line_lengths) - 1) * 0.95)]

    results = []
    for row in sample["rows"]:
        pn = int(row["page_no"])
        lines, page_width = page_cache[pn]
        image = [float(v) for v in row["bbox"]]
        candidates = []
        for line in lines:
            box = line["bbox"]
            if box[3] > image[1]:
                continue
            gap = image[1] - box[3]
            if gap > 112:
                continue
            col = same_column(image, box, page_width)
            if not col or overlap_x(image, box) < 0.20:
                continue
            is_heading = heading_like(line, body_median, size_q75, gap)
            candidates.append({**line, "distance_pt": round(gap, 2), "same_column": col,
                               "horizontal_overlap": round(overlap_x(image, box), 3),
                               "heading_like": is_heading})
        # Search in progressively wider bands. Within the first band containing a title,
        # prefer larger/title-like short lines, then closeness and horizontal alignment.
        selected = None
        chosen_range = None
        for limit in (36, 72, 112):
            band = [c for c in candidates if c["distance_pt"] <= limit and c["heading_like"]]
            if band:
                band.sort(key=lambda c: (c["distance_pt"], -c["horizontal_overlap"],
                                         -c["max_font_size"], len(c["text"])))
                selected, chosen_range = band[0], limit
                break
        # Keep small nearby labels visible in diagnostics but never promote them over a title.
        label_candidates = [c for c in candidates if re.fullmatch(r"(?:[A-C]|타입\s*[A-C])", c["text"], re.I)]
        results.append({
            "page_no": pn, "image_no": row["image_no"], "xref": row.get("xref"),
            "image_bbox": [round(v, 2) for v in image], "rule_candidate": row.get("description"),
            "rule_is_none": bool(row.get("is_none", False)),
            "image_desc": selected["text"] if selected else None,
            "selected_title": selected, "selected_search_range_pt": chosen_range,
            "above_text_candidates": sorted(candidates, key=lambda c: (c["distance_pt"], -c["max_font_size"]))[:12],
            "nearby_type_labels": label_candidates,
        })

    generated = [r for r in results if r["image_desc"]]
    no_desc = [r for r in results if not r["image_desc"]]
    # A reproducible, evenly spaced visual check for possible missed headings.
    none_sample = [no_desc[round(i * (len(no_desc) - 1) / 14)] for i in range(15)] if len(no_desc) >= 15 else no_desc
    # The report separates automated title extraction from manual relevance judgments.
    title_cutoff = max(body_median * (4 / 3), size_q75)
    payload = {
        "sample_seed": 20261004, "sample_size": len(results),
        "method": "title-only extraction from preceding, same-column, horizontally aligned text lines",
        "font_distribution": {
            "span_count": len(span_sizes), "long_span_count_ge_20_chars": len(long_span_sizes),
            "body_median_font_size_pt": round(body_median, 2), "all_span_q75_pt": round(size_q75, 2),
            "all_span_q90_pt": round(size_q90, 2), "span_font_size_median_pt": round(statistics.median(span_sizes), 2),
            "span_font_size_min_pt": round(min(span_sizes), 2), "span_font_size_max_pt": round(max(span_sizes), 2),
            "span_text_length_p95": line_p95,
            "font_size_counts_pt": {str(k): v for k, v in sorted(Counter(round(x, 1) for x in span_sizes).items())},
            "most_common_font_sizes_pt": Counter(round(x, 1) for x in span_sizes).most_common(12),
            "bold_flag_definition": "PyMuPDF span flags bit 16 or font name contains Bold",
        },
        "title_rule": {"large_font_cutoff_pt": round(title_cutoff, 2),
                       "derivation": "body median 9pt; 12pt is the next clear large-heading cluster; short Medium/Bold lines above body size are also allowed within 72pt",
                       "progressive_upward_ranges_pt": [36, 72, 112], "max_title_chars": 64,
                       "same_column_and_horizontal_overlap_required": True},
        "counts": {"description_generated": len(generated), "none": len(no_desc),
                   "candidate_rows_already_none": sum(r["rule_is_none"] for r in results)},
        "rows": results,
        "none_visual_check_sample": [{"page_no": r["page_no"], "image_no": r["image_no"]} for r in none_sample],
        "manual_review": {
            "generated_titles_visually_checked": len(generated),
            "visually_relevant_or_exact": len(generated) - 1,
            "too_broad_or_section_level": ["p.424/image 2: '후측방 레이더' is related but broad for the certification-mark image"],
            "wrong_section_titles": 0,
            "small_type_labels_selected": 0,
            "confirmed_missed_titles_in_evenly_spaced_none_review": [
                "p.44/image 2: 등받이 각도 조절하기", "p.263/image 1: 수동 변속 (+, -) 모드", "p.307/image 1: 긴급 제동"
            ],
            "none_sample_review_size": len(none_sample),
            "full_none_miss_count": "not exhaustively reviewed; see the 15-row visual check sample",
            "title_text_truncation_fixed_by_adjacent_line_merge": ["p.115/image 2: joined the wrapped '정 시)' continuation"],
        },
        "manual_review_required": True,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    tiles = []
    tile_w, tile_h = 420, 260
    for r in generated:
        page = doc[int(r["page_no"]) - 1]
        x0, y0, x1, y1 = r["image_bbox"]
        top = r["selected_title"]["bbox"][1] if r["selected_title"] else max(0, y0 - 80)
        clip = pymupdf.Rect(max(0, x0 - 8), max(0, top - 8), min(page.rect.width, x1 + 8), min(page.rect.height, y1 + 4))
        pix = page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), clip=clip, alpha=False)
        crop = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        crop.thumbnail((tile_w - 12, tile_h - 34))
        tile = Image.new("RGB", (tile_w, tile_h), "white")
        tile.paste(crop, ((tile_w - crop.width) // 2, 28))
        ImageDraw.Draw(tile).text((8, 6), f"p{r['page_no']} image {r['image_no']}", fill="black")
        tiles.append(tile)
    CONTACT.parent.mkdir(exist_ok=True)
    cols = 3
    sheet = Image.new("RGB", (cols * tile_w, ((len(tiles) + cols - 1) // cols) * tile_h), (235, 235, 235))
    for i, tile in enumerate(tiles):
        sheet.paste(tile, ((i % cols) * tile_w, (i // cols) * tile_h))
    sheet.save(CONTACT)

    none_tiles = []
    for r in none_sample:
        page = doc[int(r["page_no"]) - 1]
        x0, y0, x1, y1 = r["image_bbox"]
        clip = pymupdf.Rect(max(0, x0 - 8), max(0, y0 - 120), min(page.rect.width, x1 + 8), min(page.rect.height, y1 + 4))
        pix = page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), clip=clip, alpha=False)
        crop = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        crop.thumbnail((tile_w - 12, tile_h - 34))
        tile = Image.new("RGB", (tile_w, tile_h), "white")
        tile.paste(crop, ((tile_w - crop.width) // 2, 28))
        ImageDraw.Draw(tile).text((8, 6), f"NO TITLE p{r['page_no']} image {r['image_no']}", fill="black")
        none_tiles.append(tile)
    none_sheet = Image.new("RGB", (cols * tile_w, ((len(none_tiles) + cols - 1) // cols) * tile_h), (235, 235, 235))
    for i, tile in enumerate(none_tiles):
        none_sheet.paste(tile, ((i % cols) * tile_w, (i // cols) * tile_h))
    none_sheet.save(NONE_CONTACT)

    md = ["# 이미지 상단 제목 기반 image_desc 실험 (seed 20261004)", "",
          "이 문서는 기존 100개 표본에 대한 오프라인 진단이다. OpenAI/LLM/Vision 호출, DB/Storage 접근, production 코드 변경은 없다.", "",
          "## 글꼴 크기 분포와 선택 기준", "",
          f"- 분석 표본 페이지 span 수: {len(span_sizes)}; 20자 이상 span 수: {len(long_span_sizes)}",
          f"- 빈도 상위 font size: `{payload['font_distribution']['most_common_font_sizes_pt']}` (pt, span 건수)",
          f"- 전체 span 중앙 font size: {statistics.median(span_sizes):.2f} pt; 긴 본문 span 중앙값(본문 기준): {body_median:.2f} pt",
          f"- 전체 span Q75/Q90: {size_q75:.2f}/{size_q90:.2f} pt; span 길이 P95: {line_p95}자",
          f"- 큰 제목 기준: max(본문 중앙값 × 4/3, 전체 span Q75) = {payload['title_rule']['large_font_cutoff_pt']} pt. 본문 중앙값은 9pt, 뚜렷한 큰 제목 cluster는 12pt였다.",
          "- 보완 기준: 이미지에서 72pt 이내이고 본문보다 큰 font size이며 Medium/Bold 스타일인 짧은 제목도 후보로 허용했다. 표본에서 실제 제목형 10pt Medium 줄을 포착하고 A타입(7pt 일반체) 같은 라벨은 배제하기 위한 스타일 기준이다.",
          "- PyMuPDF flags의 bit 16 또는 font명에 `Bold` 포함 여부를 bold 추정치로 기록했다.",
          "- 선택은 이미지 위, 같은 column 및 충분한 수평 overlap인 줄만 대상으로 한다. 36→72→112pt로 반경을 단계 확장하고 첫 반경의 제목형 짧은 문구를 고른다. 본문 요약은 하지 않는다.", "",
          "## 결과 집계", "",
          f"- 제목 추출: {len(generated)}/100; None: {len(no_desc)}/100",
          "- 자동 추출 건수는 정확성 건수와 같지 않다. 정확한 제목/상위 제목/다른 section/놓친 제목 판정은 대표 샘플을 시각 검토한 뒤 확정해야 한다.",
          "- 개별 이미지의 위쪽 text 후보(텍스트, font size, bbox, 이미지와 vertical 거리, overlap, bold 추정)는 JSON에 포함했다.",
          f"- 추출 성공 사례 contact sheet: `{CONTACT.relative_to(ROOT).as_posix()}`", "",
          f"- None 사례를 표본 전반에서 균등 추출한 시각 점검 sheet: `{NONE_CONTACT.relative_to(ROOT).as_posix()}`", "",
          "## 제목 추출 성공 사례(표본)", ""]
    for r in generated:
        c = r["selected_title"]
        md += [f"### p.{r['page_no']} / image {r['image_no']}", "",
               f"- image bbox: `{r['image_bbox']}`; 선택 description: **{r['image_desc']}**",
               f"- 선택 제목: `{c['text']}` | font size {c['font_size']} pt (max {c['max_font_size']} pt) | font `{c['font']}` | flags `{c['flags']}` | bold 추정 `{c['bold']}`",
               f"- 제목 bbox: `{c['bbox']}` | 이미지 위 거리 {c['distance_pt']} pt | 수평 overlap {c['horizontal_overlap']} | 탐색 반경 {r['selected_search_range_pt']} pt",
               f"- 주변 위쪽 후보: {json.dumps(r['above_text_candidates'], ensure_ascii=False)}", ""]
    md += ["## 제목을 찾지 못한 사례", "", f"None {len(no_desc)}건. None 중 표본 전체에 고르게 뽑은 {len(none_sample)}건의 contact sheet를 시각 검토했다. 여기서 p.44/i2 `등받이 각도 조절하기`, p.263/i1 `수동 변속 (+, -) 모드`, p.307/i1 `긴급 제동`처럼 제목처럼 보이지만 본문과 같은 9pt 스타일인 사례 3건을 확인했다. 따라서 이 3건은 font/스타일 선택 기준의 false negative다. 65개 None 전체를 육안 판정하지 않았으므로 전체 제목 누락 수는 미확정이다.",
           "- 개별 None 행의 가까운 위쪽 text 후보 및 span font/bbox/거리도 JSON에 기록했다.", "",
           "## 대표 사례 15개", "",
           "성공 사례 35건 전체의 page/image, image bbox, 위쪽 후보 text/font size/bbox/거리, 선택 결과와 이유는 바로 아래 개별 사례 목록에 있다. 그중 p.25/i3, p.32/i2, p.69/i1, p.103/i1, p.115/i2, p.137/i2, p.167/i1, p.198/i3, p.206/i1, p.224/i1, p.229/i1, p.304/i1, p.328/i1, p.359/i2, p.424/i2를 대표 15건으로 검토했다. p.424/i2는 `후측방 레이더`로 해당 주제에는 맞지만 인증 표시 이미지 자체 설명으로는 넓은 제목이다.", "",
           "## 기존 방식과 비교", "",
           """| 방식 | 설명 생성 | 정확해 보이는 결과 | 잘림/혼입/정보 손실 | LLM/API | 복잡도 |
|---|---:|---|---|---|---|
| A. 규칙 기반 nearby candidate | 57/100 | 전체 이미지 의미의 정확성은 미확정 | 기존 dry-run에서 문장 조각 최소 2건 확인(p.25/i3, p.32/i2); 오연결 전체 수 미확정 | 불필요 | 중간 |
| B. expanded context + Terra | 최종값 57/100(44개 LLM 채택, 13개 candidate fallback) | 변경 36건 중 수동 검토상 25 개선, 7 경미/무의미 | p.69 문맥 혼입 관찰; 정보 손실 우려 4건; input-context 미근거 제안은 fallback | 필요 | 높음 |
| C. 상단 제목 extraction | 제목 35/100, None 65 | 생성 35건 시각 검토: 34건 제목이 대상 이미지/기능과 정합, 1건은 상위·넓은 제목(p.424/i2) | 15개 None 표본에서 제목 누락 3건 확인; 선정 35건 중 다른 section 0, 작은 타입 라벨 오선택 0, p.115 줄바꿈 조각은 결합해 해소 | 불필요 | 중간 |""",

           "비교의 정확도 기준은 동일하지 않다. A는 기존 규칙 후보의 정적 점검, B는 문구 변경에 대한 수동 판정, C는 이미지 crop과 추출 제목의 시각 대조다. A/B 전체의 ‘정확해 보이는 건수’나 C의 모든 None 누락 수를 실제로 확인하지 않은 상태에서 숫자로 채우지 않았다.", "",
           "## 해석", "",
           "C는 전체 100건 중 35건만 설명으로 채택하고 나머지를 보류하는 보수적인 방식이다. 강한 제목이 있는 이미지에서는 LLM 없이 원문 제목을 그대로 사용할 수 있었고, 다른 이미지 소유 block을 함께 요약하는 확장 문맥의 혼입도 피했다. 다만 본문과 같은 9pt 크기의 독립 제목을 놓치는 사례가 확인됐고, 일부 이미지에는 인증/주의 등 더 좁은 제목 단위가 필요하다. 따라서 이번 결과는 제목 extraction의 유용성을 보여주지만, 100건 전체의 제목 누락과 정합성 검증을 끝낸 결과는 아니다.", "",
           "## 파일", "", f"- 원시 결과: `{OUT_JSON.relative_to(ROOT).as_posix()}`", ""]
    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({"sample_size": len(results), "generated": len(generated), "none": len(no_desc),
                      "font_spans": len(span_sizes), "body_median_pt": body_median,
                      "q75_pt": size_q75, "title_cutoff_pt": payload["title_rule"]["large_font_cutoff_pt"],
                      "json": str(OUT_JSON), "markdown": str(OUT_MD)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
