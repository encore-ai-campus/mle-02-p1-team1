"""Batch-refine existing rule-based image_desc candidates with text-only LLM.

Loads a prior dry-run JSON sample, skips None candidates, sends text only, and
never imports or calls the DB, Storage, PDF, or production registration paths.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
MODEL = "gpt-5.6-terra"
BATCH_SIZE = 10

SYSTEM_PROMPT = """너는 차량 매뉴얼 검색용 한국어 metadata 문구를 다듬는다.
각 항목의 description은 rule_candidate의 의미와 사실을 그대로 유지하면서 짧고 자연스럽게 정리한다.
page_no, image_no, context는 기존 후보의 문맥 확인용일 뿐이며 새로운 사실을 추가하는 근거로 사용하지 않는다.
부품명, 위치, 규격, 수치, 기능을 추측하거나 candidate에 없는 내용을 추가하지 않는다.
이미 간결하거나 자연스러우면 그대로 반환한다. 빈 값이나 NONE을 만들지 않는다.
출력은 JSON object 하나이며 형식은 {\"items\":[{\"id\":\"...\",\"description\":\"...\"}]} 이다.
입력 item의 id마다 정확히 한 개를 반환한다. 설명 외 문장은 쓰지 않는다."""


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[가-힣]+|[A-Za-z0-9]+(?:[-/][A-Za-z0-9]+)*", text.casefold()))


def validate(candidate: str, output: str) -> tuple[bool, str]:
    value = output.strip().strip("`\"' ")
    if not value:
        return False, "empty"
    if value.casefold() == "none":
        return False, "none"
    if len(value) > 60:
        return False, "too_long"
    if not re.search(r"[가-힣]", value):
        return False, "not_korean"
    extra = tokens(value) - tokens(candidate)
    if extra:
        return False, "new_tokens:" + ",".join(sorted(extra))
    return True, "accepted"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("sample_json", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "src/car_search_rag/car_search/docs/IMAGE_DESC_TEXT_LLM_100.md")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY가 설정되지 않았습니다. 값은 출력하지 않습니다.")

    sample = json.loads(args.sample_json.read_text(encoding="utf-8"))
    sample_seed = sample.get("sample_seed", sample.get("seed"))
    rows = sample["rows"]
    eligible = [row for row in rows if row.get("description")]
    skipped_none = len(rows) - len(eligible)
    client = OpenAI(api_key=api_key, max_retries=0, timeout=60.0)
    output_by_id: dict[str, dict] = {}
    request_records = []
    errors = 0
    start = time.perf_counter()

    for offset in range(0, len(eligible), BATCH_SIZE):
        batch = eligible[offset : offset + BATCH_SIZE]
        items = []
        for row in batch:
            items.append({
                "id": f"p{row['page_no']}-i{row['image_no']}",
                "page_no": row["page_no"],
                "image_no": row["image_no"],
                "bbox_pt": row["bbox"],
                "context": row["selected_text"],
                "rule_candidate": row["description"],
            })
        request_record = {"batch": len(request_records) + 1, "items": len(items), "input_tokens": 0, "output_tokens": 0, "status": "ok"}
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps({"items": items}, ensure_ascii=False)},
                ],
                response_format={"type": "json_object"},
                max_completion_tokens=1200,
            )
            if response.usage:
                request_record["input_tokens"] = response.usage.prompt_tokens
                request_record["output_tokens"] = response.usage.completion_tokens
            parsed = json.loads(response.choices[0].message.content or "{}")
            response_items = parsed.get("items", [])
            for item in response_items:
                if isinstance(item, dict) and isinstance(item.get("id"), str):
                    output_by_id[item["id"]] = item
        except Exception as exc:  # one batch failure must not trigger automatic retry
            errors += 1
            body = getattr(exc, "body", None)
            error_body = body.get("error", body) if isinstance(body, dict) else {}
            if not isinstance(error_body, dict):
                error_body = {}
            request_record["status"] = "error:" + type(exc).__name__
            request_record["error"] = {
                "http_status": getattr(exc, "status_code", None),
                "message": error_body.get("message", str(exc)),
                "type": error_body.get("type", getattr(exc, "type", None)),
                "code": error_body.get("code", getattr(exc, "code", None)),
                "param": error_body.get("param", getattr(exc, "param", None)),
            }
        request_records.append(request_record)

    elapsed = time.perf_counter() - start
    final_rows = []
    fallback_count = 0
    valid_llm_count = 0
    new_info_cases = 0
    meaning_preserved = 0
    quality_error_count = errors
    for row in rows:
        candidate = row.get("description")
        if not candidate:
            final_rows.append({**row, "llm_description": None, "final_description": None, "disposition": "skipped_none", "validation": "not_called"})
            continue
        item_id = f"p{row['page_no']}-i{row['image_no']}"
        answer = output_by_id.get(item_id)
        proposed = answer.get("description") if answer else None
        valid, reason = validate(candidate, proposed or "")
        if valid:
            final = proposed.strip()
            disposition = "llm_accepted"
            valid_llm_count += 1
            meaning_preserved += 1
        else:
            final = candidate
            disposition = "fallback_candidate"
            fallback_count += 1
            if reason.startswith("new_tokens:"):
                new_info_cases += 1
            if proposed:
                quality_error_count += 1
        final_rows.append({
            **row,
            "llm_description": proposed,
            "final_description": final,
            "disposition": disposition,
            "validation": reason,
        })

    input_tokens = sum(record["input_tokens"] for record in request_records)
    output_tokens = sum(record["output_tokens"] for record in request_records)
    result = {
        "model": MODEL,
        "sample_seed": sample_seed,
        "sample_size": len(rows),
        "llm_target_count": len(eligible),
        "skipped_none_count": skipped_none,
        "api_request_count": len(request_records),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "elapsed_seconds": round(elapsed, 3),
        "api_errors_or_retries": {"errors": errors, "retries": 0},
        "valid_llm_count": valid_llm_count,
        "meaning_preserved_count": meaning_preserved,
        "new_information_rejected_count": new_info_cases,
        "incorrect_or_invalid_response_count": quality_error_count,
        "fallback_count": fallback_count,
        "requests": request_records,
        "rows": final_rows,
    }
    report = [
        "# Sonata image_desc Text LLM 100건 샘플 처리", "",
        f"- 규칙 dry-run 표본: {len(rows)}건 (seed {sample_seed})",
        f"- 모델: `{MODEL}` / text-only Chat Completions / batch size {BATCH_SIZE}",
        "- 이미지 bytes·URL 미전송. DB/Storage/production 등록 코드 미호출.",
        "- API 재시도: 0 (SDK max_retries=0); 오류 시 원 후보로 fallback.", "",
        "## 실행량", "",
        f"- LLM 대상: {len(eligible)} / None skip: {skipped_none}",
        f"- API requests: {len(request_records)} / input tokens: {input_tokens} / output tokens: {output_tokens}",
        f"- API 구간 경과 시간: {elapsed:.3f}s / 오류: {errors} / 재시도: 0", "",
        "## 결과", "",
        f"- 유효 LLM 후처리: {valid_llm_count}; fallback: {fallback_count}; 후보 의미 유지로 승인된 LLM 결과: {meaning_preserved}",
        f"- 새 token 추가로 거부: {new_info_cases}; 유효성 검사 실패 또는 요청 오류: {quality_error_count}",
        "- ‘잘못된 의미’ 판정은 token subset 검사로 새로운 어휘 추가를 차단한 정적 기준이다. 최종 의미 적합성은 사람이 검토해야 한다.", "",
        "| # | page/image | 주변 텍스트 | 규칙 후보 | LLM 응답 | 최종 사용값 | 판정 |", "|---:|---|---|---|---|---|---|",
    ]
    for index, row in enumerate(final_rows, start=1):
        context = " / ".join(row.get("selected_text", [])).replace("\n", " ")
        cells = [context[:220], row.get("description") or "—", row.get("llm_description") or "—", row.get("final_description") or "—", row["disposition"] + " / " + row["validation"]]
        cells = [value.replace("|", "/") for value in cells]
        report.append(f"| {index} | p.{row['page_no']}/i{row['image_no']} | " + " | ".join(cells) + " |")
    args.output.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in (
        "model", "sample_size", "llm_target_count", "skipped_none_count", "api_request_count",
        "input_tokens", "output_tokens", "elapsed_seconds", "api_errors_or_retries",
        "valid_llm_count", "meaning_preserved_count", "new_information_rejected_count",
        "incorrect_or_invalid_response_count", "fallback_count",
    )}, ensure_ascii=False))
    print("REPORT", args.output)
    print("RESULT_JSON", args.output.with_suffix(".json"))
    args.output.with_suffix(".json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
