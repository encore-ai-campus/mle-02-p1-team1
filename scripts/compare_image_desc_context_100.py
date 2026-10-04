"""Compare original and expanded PDF text context for the fixed Sonata 100 sample.

This experiment reads the local PDF and prior evaluation artifacts only. It does
not connect to PostgreSQL, Supabase, or production registration code paths.
"""

from __future__ import annotations

import json
import os
import re
import statistics
import sys
import time
import unicodedata
from pathlib import Path

import pymupdf
from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from car_search_rag.car_search.car_manual_register_service import CarManualRegisterService as RegisterService

DOCS = ROOT / "src/car_search_rag/car_search/docs"
INPUT_JSON = DOCS / "IMAGE_DESC_TEXT_LLM_100_GPT56_TERRA.json"
BASELINE_JSON = DOCS / "IMAGE_DESC_TEXT_LLM_100_GPT56_TERRA.json"
OUTPUT_JSON = DOCS / "IMAGE_DESC_CONTEXT_DIAGNOSTIC_100.json"
OUTPUT_MD = DOCS / "IMAGE_DESC_CONTEXT_DIAGNOSTIC_100.md"
PDF_PATH = ROOT / "data/DN8_2026_ko_KR.pdf"
MODEL = "gpt-5.6-terra"
BATCH_SIZE = 10
MAX_CONTEXT_CHARS = 600
MAX_EXPANDED_BLOCKS = 10
EXPANDED_VERTICAL_GAP = 240.0

EXPANDED_SYSTEM_PROMPT = """너는 차량 매뉴얼 이미지 검색용 한국어 metadata를 정리한다.
각 description은 짧은 명사구 또는 짧은 문장으로 작성한다.
rule_candidate가 이미지 문맥에서 잘린 문구라면 nearby_source_text에 명시된 내용으로 자연스럽게 완성할 수 있다.
새로운 사실은 rule_candidate 또는 nearby_source_text에 분명히 적힌 내용만 사용한다.
이미지 자체의 모양, 색상, 위치, 부품, 규격, 수치를 추측하지 않는다.
주변 원문은 근거로만 사용하며 페이지 전체의 다른 주제를 섞지 않는다.
원문에서 검색에 유용한 핵심 대상을 유지하고, 불필요한 설명은 추가하지 않는다.
응답은 입력 id별 description을 담은 JSON object 하나만 반환한다.
형식: {\"items\":[{\"id\":\"...\",\"description\":\"...\"}]}"""

TOKEN_RE = re.compile(r"[가-힣]+|[A-Za-z0-9]+(?:[-/][A-Za-z0-9]+)*")
PARTICLES = (
    "으로부터", "에게서", "으로는", "에서는", "에게는", "으로", "에서", "에게",
    "까지", "부터", "처럼", "보다", "에는", "이나", "라도", "하고", "이며",
    "은", "는", "이", "가", "을", "를", "에", "로", "와", "과", "도", "만", "의",
)


def normalized_tokens(text: str) -> set[str]:
    return {t.casefold() for t in TOKEN_RE.findall(unicodedata.normalize("NFKC", text or ""))}


def support_form(token: str) -> str:
    for suffix in PARTICLES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 2:
            return token[: -len(suffix)]
    return token


def source_grounded(candidate: str, context: str, output: str) -> tuple[bool, list[str]]:
    allowed = normalized_tokens(candidate) | normalized_tokens(context)
    missing = []
    for token in normalized_tokens(output):
        if token in allowed:
            continue
        stem = support_form(token)
        if stem in allowed:
            continue
        # Permit a compound split by PDF line wrapping, but only if the exact
        # compound can be formed from adjacent source tokens in reading order.
        compact_source = re.sub(r"\s+", "", unicodedata.normalize("NFKC", candidate + " " + context).casefold())
        if token in compact_source:
            continue
        missing.append(token)
    return not missing, missing


def rect_gap(a, b):
    ax0, ay0, ax1, ay1 = tuple(a)
    bx0, by0, bx1, by1 = tuple(b)
    hg = max(ax0 - bx1, bx0 - ax1, 0)
    vg = max(ay0 - by1, by0 - ay1, 0)
    return hg, vg, vg + hg * 1.8


def heading_like(text: str) -> bool:
    value = re.sub(r"\s+", " ", text).strip()
    if not value or len(value) > 70:
        return False
    if re.search(r"(?:하십시오|하세요|합니다|됩니다|있습니다|바랍니다|수 있습니다)[.!。]?$", value):
        return False
    return True


def get_raw_text_blocks(page):
    result = []
    for idx, block in enumerate(page.get_text("blocks")):
        if len(block) < 5 or not isinstance(block[4], str) or (len(block) > 6 and block[6] != 0):
            continue
        text = RegisterService._normalize_image_context_text(block[4])
        if not text:
            continue
        result.append({
            "block_id": idx,
            "bbox": [round(float(v), 2) for v in block[:4]],
            "raw_text": block[4].strip(),
            "text": text,
        })
    return result


def enrich_blocks(page, target_rects, all_image_rects):
    enriched = []
    for block in get_raw_text_blocks(page):
        x0, y0, x1, y1 = block["bbox"]
        block_rect = pymupdf.Rect(x0, y0, x1, y1)
        metrics = []
        for rect in target_rects:
            hg, vg, distance = rect_gap(block_rect, rect)
            ix0, _, ix1, _ = tuple(rect)
            overlap = max(0.0, min(ix1, x1) - max(ix0, x0))
            center = abs((x0 + x1) / 2 - (ix0 + ix1) / 2)
            width = max(ix1 - ix0, 1)
            same_column = overlap > 0 or center <= max(28, width * .18, page.rect.width * .045)
            metrics.append({"rect": rect, "hgap": hg, "vgap": vg, "distance": distance,
                            "same_column": same_column, "center_distance": center})
        best = min(metrics, key=lambda m: m["distance"])
        target_distance = min(rect_gap(block_rect, rect)[2] for rect in target_rects)
        target_rect_keys = {tuple(round(float(v), 2) for v in rect) for rect in target_rects}
        other_distances = [
            rect_gap(block_rect, rect)[2] for rect in all_image_rects
            if tuple(round(float(v), 2) for v in rect) not in target_rect_keys
        ]
        nearest_other = min(other_distances, default=float("inf"))
        owned_by_target = nearest_other + 12 >= target_distance
        best["owned_by_target"] = owned_by_target
        best["inside_current_range"] = best["same_column"] and best["vgap"] <= 80 and owned_by_target
        best["inside_expanded_range"] = best["same_column"] and best["vgap"] <= EXPANDED_VERTICAL_GAP and owned_by_target
        block.update({k: v for k, v in best.items() if k != "rect"})
        block["selected_current"] = False
        block["selected_expanded"] = False
        if best["same_column"] and best["vgap"] <= EXPANDED_VERTICAL_GAP:
            block["exclusion_reason"] = None if owned_by_target else "다른 이미지에 더 가까움"
        elif not best["same_column"]:
            block["exclusion_reason"] = "다른 column"
        else:
            block["exclusion_reason"] = "수직 거리 범위 초과"
        enriched.append(block)
    return enriched


def build_row(row, pdf):
    page = pdf[row["page_no"] - 1]
    image_infos = page.get_images(full=True)
    if row["image_no"] < 1 or row["image_no"] > len(image_infos):
        raise ValueError(f"image index mismatch p{row['page_no']}/i{row['image_no']}")
    xref = image_infos[row["image_no"] - 1][0]
    target_rects = page.get_image_rects(xref)
    if not target_rects:
        target_rects = [pymupdf.Rect(row["bbox"])]
    target_rect = target_rects[0]
    all_rects = [r for info in image_infos for r in page.get_image_rects(info[0])]
    all_blocks = enrich_blocks(page, target_rects, all_rects)

    current = []
    raw_lookup = {(tuple(b["bbox"]), b["text"]): b["raw_text"] for b in all_blocks}
    for rect in target_rects:
        for item in RegisterService._select_nearby_text_blocks(page, rect, page_image_rects=all_rects):
            key = (tuple(round(float(x), 2) for x in item["bbox"]), item["text"])
            if not any((tuple(b["bbox"]), b["text"]) == key for b in current):
                current.append({**item, "bbox": list(item["bbox"]), "raw_text": raw_lookup.get(key, item["text"])})
    current.sort(key=lambda b: (b["distance"], b["bbox"][1]))
    current_keys = {(tuple(b["bbox"]), b["text"]) for b in current}
    for block in all_blocks:
        block["selected_current"] = (tuple(block["bbox"]), block["text"]) in current_keys

    candidates = [b for b in all_blocks if b["inside_expanded_range"]]
    # Reserve the nearest same-column block above and below, then the nearest
    # heading-like line and fill by geometric distance. This prevents the cap
    # from dropping a useful title while limiting adjacent-page noise.
    chosen = []
    def add(block):
        if block and block not in chosen and len(chosen) < MAX_EXPANDED_BLOCKS:
            chosen.append(block)
    above = [b for b in candidates if b["bbox"][3] <= tuple(target_rect)[1]]
    below = [b for b in candidates if b["bbox"][1] >= tuple(target_rect)[3]]
    add(min(above, key=lambda b: b["distance"]) if above else None)
    add(min(below, key=lambda b: b["distance"]) if below else None)
    headings = [b for b in candidates if heading_like(b["text"])]
    add(min(headings, key=lambda b: b["distance"]) if headings else None)
    for block in sorted(candidates, key=lambda b: (b["distance"], b["bbox"][1])):
        add(block)
    chosen.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))

    pieces = []
    used_chars = 0
    for block in chosen:
        text = block["text"].replace("\n", " ").strip()
        if not text:
            continue
        remaining = MAX_CONTEXT_CHARS - used_chars
        if remaining <= 0:
            break
        if len(text) > remaining:
            text = text[:remaining].rstrip()
            block["truncated_for_context_cap"] = True
        else:
            block["truncated_for_context_cap"] = False
        pieces.append(text)
        used_chars += len(text) + 1
        block["selected_expanded"] = True
    expanded_context = "\n".join(pieces)

    # Store exact user-item text for the original Terra request and a faithful
    # reconstruction of the payload context values.
    current_context = row.get("selected_text", [])
    llm_id = f"p{row['page_no']}-i{row['image_no']}"
    return {
        **row,
        "llm_id": llm_id,
        "image_bbox": [round(float(v), 2) for v in tuple(target_rect)],
        "current_context_blocks": current,
        "current_context_text": "\n".join(current_context),
        "current_context_payload": current_context,
        "current_context_chars": len("\n".join(current_context)),
        "expanded_context_blocks": [b for b in chosen if b["selected_expanded"]],
        "expanded_context_text": expanded_context,
        "expanded_request_item": {"id": llm_id, "page_no": row["page_no"], "image_no": row["image_no"],
                                  "bbox_pt": [round(float(v), 2) for v in tuple(target_rect)],
                                  "rule_candidate": row["description"], "nearby_source_text": expanded_context},
        "expanded_context_chars": len(expanded_context),
        "all_nearby_text_blocks": sorted(all_blocks, key=lambda b: (b["distance"], b["bbox"][1])),
    }


def load_base():
    data = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    return data


def run_expanded_llm(rows):
    load_dotenv(ROOT / ".env")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured; value not displayed")
    client = OpenAI(api_key=api_key, max_retries=0, timeout=60.0)
    responses = {}
    records = []
    start = time.perf_counter()
    eligible = [r for r in rows if r.get("description")]
    for offset in range(0, len(eligible), BATCH_SIZE):
        batch = eligible[offset:offset + BATCH_SIZE]
        items = [{
            "id": r["llm_id"],
            "page_no": r["page_no"],
            "image_no": r["image_no"],
            "bbox_pt": r["image_bbox"],
            "rule_candidate": r["description"],
            "nearby_source_text": r["expanded_context_text"],
        } for r in batch]
        rec = {"batch": len(records) + 1, "items": len(items), "input_tokens": 0,
               "output_tokens": 0, "status": "ok"}
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": EXPANDED_SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps({"items": items}, ensure_ascii=False)},
                ],
                response_format={"type": "json_object"},
                max_completion_tokens=1200,
            )
            if response.usage:
                rec["input_tokens"] = response.usage.prompt_tokens
                rec["output_tokens"] = response.usage.completion_tokens
            payload = json.loads(response.choices[0].message.content or "{}")
            for item in payload.get("items", []):
                if isinstance(item, dict) and isinstance(item.get("id"), str):
                    responses[item["id"]] = item.get("description")
        except Exception as exc:
            body = getattr(exc, "body", None)
            error = body.get("error", body) if isinstance(body, dict) else {}
            if not isinstance(error, dict):
                error = {}
            rec.update({"status": "error:" + type(exc).__name__, "error": {
                "http_status": getattr(exc, "status_code", None),
                "message": error.get("message", str(exc)),
                "type": error.get("type", getattr(exc, "type", None)),
                "code": error.get("code", getattr(exc, "code", None)),
                "param": error.get("param", getattr(exc, "param", None)),
            }})
        records.append(rec)
    return responses, records, round(time.perf_counter() - start, 3)


def classify_validation(candidate, source, proposed):
    if not proposed or not proposed.strip():
        return False, "empty", []
    value = proposed.strip().strip("`\"' ")
    if value.casefold() == "none":
        return False, "none", []
    if len(value) > 100:
        return False, "too_long", []
    if not re.search(r"[가-힣]", value):
        return False, "not_korean", []
    grounded, unsupported = source_grounded(candidate, source, value)
    return grounded, "source_supported" if grounded else "outside_candidate_and_source:" + ",".join(unsupported), unsupported


def build_report(payload):
    rows = payload["rows"]
    changed = [r for r in rows if r.get("description") and r.get("final_expanded_description") != r.get("description")]
    groups = {
        "A. Terra가 실제로 문구를 변경한 기존 9건": [r for r in rows if r.get("terra_disposition") == "llm_accepted" and r.get("terra_final") != r.get("description")],
        "B. 기존 candidate 밖 어휘로 거부된 18건": [r for r in rows if str(r.get("terra_validation", "")).startswith("new_tokens:")],
        "C. 후보와 동일하게 반환한 대표 사례 10건": [r for r in rows if r.get("terra_disposition") == "llm_accepted" and r.get("terra_final") == r.get("description")],
    }
    identical = groups["C. 후보와 동일하게 반환한 대표 사례 10건"]
    if len(identical) > 10:
        step = (len(identical) - 1) / 9
        groups[list(groups)[2]] = [identical[round(i * step)] for i in range(10)]
    lines = [
        "# Sonata image_desc 입력 문맥 진단 및 확대 실험", "",
        f"- 표본: seed 20261004, 100개 중 description 후보가 있는 {sum(bool(r.get('description')) for r in rows)}개만 비교 대상으로 삼음.",
        f"- 모델: `{MODEL}`; A는 기존 실행 결과, B는 확대 문맥 실험. DB/Storage/production 경로는 호출하지 않음.",
        f"- PDF text block 길이 분포(57개 대상 페이지): p50={payload['block_length_stats']['p50']}, p90={payload['block_length_stats']['p90']}, p95={payload['block_length_stats']['p95']}자.",
        f"- B 문맥 상한: {MAX_CONTEXT_CHARS}자 / 이미지당 최대 {MAX_EXPANDED_BLOCKS} blocks / 동일 column 최대 수직 간격 {EXPANDED_VERTICAL_GAP:.0f}pt. 문장 전체를 무제한 포함하지 않고 한 페이지 인접 문맥의 p95를 넘지 않도록 제한.",
        "- 확장 선택 순서: 같은 열의 바로 위/아래, 가까운 제목 후보, 이후 거리순. 다른 이미지 쪽 block은 제외.", "",
        "## A/B 요약", "",
        "| 지표 | A 기존 context + validator | B 확장 context + source-grounded validator |", "|---|---:|---:|",
    ]
    stats = payload["comparison"]
    for label, a, b in stats:
        lines.append(f"| {label} | {a} | {b} |")
    lines += ["", "## 기존 Terra 입력 상세 그룹", ""]
    for title, selected_rows in groups.items():
        lines += [f"### {title}", ""]
        for r in selected_rows:
            lines += [f"#### p.{r['page_no']} / image {r['image_no']}", "",
                      f"- image bbox: `{r['image_bbox']}`; candidate: `{r.get('description') or 'None'}`",
                      f"- 기존 실제 전달 context 필드: {r['current_context_payload']!r}",
                      f"- Terra 원응답: {r.get('terra_raw_output')!r}; 최종값: {r.get('terra_final')!r}; disposition: {r.get('terra_disposition')} / {r.get('terra_validation')}",
                      "- 선택된 text blocks:"]
            for block in r["current_context_blocks"]:
                lines.append(f"  - bbox `{block['bbox']}`, distance={block['distance']:.1f}pt, hgap={block['horizontal_gap']:.1f}pt, vgap={block['vertical_gap']:.1f}pt, same_column={block['same_column']}: {block['raw_text']!r}")
            lines.append("- 확장 context blocks:")
            for block in r["expanded_context_blocks"]:
                lines.append(f"  - bbox `{block['bbox']}`, distance={block['distance']:.1f}pt, hgap={block['hgap']:.1f}pt, vgap={block['vgap']:.1f}pt, same_column={block['same_column']}: {block['raw_text']!r}")
            if r.get("expanded_llm_output") is not None:
                lines += [f"- 확대 문맥 원응답: {r['expanded_llm_output']!r}",
                          f"- 검증 결과: {r.get('expanded_validation')}; 채택값: {r.get('final_expanded_description')!r}"]
            lines.append("")
    lines += ["## 57건 전체 상세 block 로그", ""]
    for r in rows:
        lines += [f"### p.{r['page_no']} / image {r['image_no']}", "",
                  f"- image bbox: `{r['image_bbox']}`; candidate: {r.get('description') or 'None'}",
                  f"- A LLM 전달 context 필드: {r['current_context_payload']!r}",
                  f"- B LLM 전달 text ({r['expanded_context_chars']}자): {r['expanded_context_text']!r}",
                  f"- A 결과: {r.get('terra_raw_output')!r} → {r.get('terra_final')!r} ({r.get('terra_disposition')} / {r.get('terra_validation')})",
                  f"- B 결과: {r.get('expanded_llm_output')!r} → {r.get('final_expanded_description')!r} ({r.get('expanded_validation')})",
                  "- blocks (current/expanded/excluded):"]
        for b in r["all_nearby_text_blocks"]:
            if b["selected_current"] or b["selected_expanded"] or (
                b["vgap"] <= EXPANDED_VERTICAL_GAP and (b["same_column"] or b["hgap"] <= 80)
            ):
                state = "current+expanded" if b["selected_current"] and b["selected_expanded"] else "current" if b["selected_current"] else "expanded" if b["selected_expanded"] else "excluded-nearby"
                lines.append(f"  - {state}; bbox `{b['bbox']}`; distance={b['distance']:.1f}pt; vgap={b['vgap']:.1f}pt; same_column={b['same_column']}; owner={b['owned_by_target']}; reason={b['exclusion_reason']}; raw={b['raw_text']!r}")
        lines.append("")
    lines += ["## 대표 사례 평가", "",
              "사람 검토는 생성 description과 candidate/source 원문을 대조한 표본 수준 판정이다. 자동 source-grounded 검사는 어휘 근거를 확인하며 단어 간 관계나 이미지 내용의 진실성을 완전히 증명하지 않는다.", ""]
    return "\n".join(lines) + "\n"


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    source = load_base()
    terra = json.loads(BASELINE_JSON.read_text(encoding="utf-8"))
    terra_by_id = {f"p{r['page_no']}-i{r['image_no']}": r for r in terra["rows"]}
    with pymupdf.open(PDF_PATH) as pdf:
        all_rows = [build_row(r, pdf) for r in source["rows"] if r.get("description")]
        all_page_block_lengths = []
        for page_no in sorted({r['page_no'] for r in all_rows}):
            all_page_block_lengths.extend(len(b['text']) for b in get_raw_text_blocks(pdf[page_no - 1]))
    ordered = sorted(all_page_block_lengths)
    def percentile(p):
        return ordered[min(round((len(ordered) - 1) * p), len(ordered) - 1)] if ordered else 0
    payload = {
        "sample_seed": 20261004, "sample_size": 100, "llm_target_count": len(all_rows),
        "none_skipped": 43, "model": MODEL,
        "block_length_stats": {"block_count": len(ordered), "mean": round(statistics.mean(ordered), 1),
                               "p50": percentile(.5), "p90": percentile(.9), "p95": percentile(.95), "max": max(ordered, default=0)},
        "context_cap_chars": MAX_CONTEXT_CHARS,
        "rows": all_rows,
    }
    # First save the reviewable context log before making any API requests.
    for r in all_rows:
        old = terra_by_id[r["llm_id"]]
        r.update({"terra_raw_output": old.get("llm_description"), "terra_final": old.get("final_description"),
                  "terra_disposition": old.get("disposition"), "terra_validation": old.get("validation")})

    expanded_outputs, requests, elapsed = run_expanded_llm(all_rows)
    errors = sum(rec["status"] != "ok" for rec in requests)
    for r in all_rows:
        proposed = expanded_outputs.get(r["llm_id"])
        valid, reason, unsupported = classify_validation(r["description"], r["expanded_context_text"], proposed or "")
        r["expanded_llm_output"] = proposed
        r["expanded_validation"] = reason
        r["expanded_unsupported_tokens"] = unsupported
        r["expanded_accepted"] = valid
        r["final_expanded_description"] = (proposed or "").strip() if valid else r["description"]

    accepted = [r for r in all_rows if r["expanded_accepted"]]
    changed = [r for r in accepted if r["final_expanded_description"].strip() != r["description"].strip()]
    same = [r for r in accepted if r["final_expanded_description"].strip() == r["description"].strip()]
    baseline_accepted = sum(r.get("terra_disposition") == "llm_accepted" for r in all_rows)
    payload["expanded_api"] = {"requests": requests, "request_count": len(requests),
                                "input_tokens": sum(x["input_tokens"] for x in requests),
                                "output_tokens": sum(x["output_tokens"] for x in requests),
                                "elapsed_seconds": elapsed, "errors": errors, "retries": 0}
    payload["comparison"] = [
        ("None skip", "43", "43"),
        ("LLM 대상", "57", "57"),
        ("평균 context 글자수", f"{statistics.mean(r['current_context_chars'] for r in all_rows):.1f}", f"{statistics.mean(r['expanded_context_chars'] for r in all_rows):.1f}"),
        ("평균 API input tokens/대상 (context+prompt+JSON)", f"{11096 / 57:.1f}", f"{payload['expanded_api']['input_tokens'] / 57:.1f}"),
        ("정적 검사 통과", str(baseline_accepted), str(len(accepted))),
        ("fallback", str(57 - baseline_accepted), str(57 - len(accepted))),
        ("candidate와 동일", "30", str(len(same))),
        ("실제 문구 변경", "9", str(len(changed))),
        ("명확한 개선", "3 (이전 수동 판정)", "수동 검토 필요"),
        ("의미 없는 변경", "6 (이전 수동 판정)", "수동 검토 필요"),
        ("잘못된 설명", "미측정; 추가 어휘 18건은 fallback", f"{sum(bool(r['expanded_unsupported_tokens']) for r in all_rows)} source/candidate 어휘 미지지 → fallback"),
        ("source context에 근거한 새로운 표현", "해당 없음(기존 검증은 candidate 전용)", "수동 판정 필요"),
        ("source context에도 없는 hallucination", "해당 없음", f"{sum(bool(r['expanded_unsupported_tokens']) for r in all_rows)} 어휘 수준 미지지 제안"),
        ("input/output tokens", "11,096 / 1,324", f"{payload['expanded_api']['input_tokens']} / {payload['expanded_api']['output_tokens']}"),
        ("실행 시간", "14.907초", f"{elapsed:.3f}초"),
    ]
    payload["candidate_comparison"] = {"accepted": len(accepted), "fallback": 57-len(accepted),
        "accepted_identical": len(same), "accepted_changed": len(changed),
        "source_unsupported_proposals": sum(bool(r['expanded_unsupported_tokens']) for r in all_rows)}
    OUTPUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    OUTPUT_MD.write_text(build_report(payload), encoding="utf-8")
    print(json.dumps({"model": MODEL, "sample_size": 100, "llm_target_count": 57, "none_skipped": 43,
                      "context_cap": MAX_CONTEXT_CHARS, "block_length_stats": payload["block_length_stats"],
                      "current_avg_chars": round(statistics.mean(r['current_context_chars'] for r in all_rows), 1),
                      "expanded_avg_chars": round(statistics.mean(r['expanded_context_chars'] for r in all_rows), 1),
                      "expanded_api": payload["expanded_api"], "accepted": len(accepted), "fallback": 57-len(accepted),
                      "changed": len(changed), "identical": len(same), "unsupported": payload['candidate_comparison']['source_unsupported_proposals'],
                      "report": str(OUTPUT_MD.relative_to(ROOT)), "json": str(OUTPUT_JSON.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
