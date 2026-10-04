"""Reproducible 100-image local dry run; never connects to DB or Storage."""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from car_search_rag.car_search.car_manual_register_service import CarManualRegisterService

PDF_PATH = ROOT / "data" / "DN8_2026_ko_KR.pdf"
SEED = 20261004
SAMPLE_SIZE = 100


def page_quartile(page_no: int) -> int:
    return min((page_no - 1) // 127, 3)


def size_class(rect) -> str:
    area = max(0, rect.width) * max(0, rect.height)
    if area < 400:
        return "small"
    if area < 5000:
        return "medium"
    return "large"


def allocate_quotas(groups: dict, total: int) -> dict:
    group_sizes = {key: len(value) for key, value in groups.items()}
    exact = {key: total * count / sum(group_sizes.values()) for key, count in group_sizes.items()}
    quotas = {key: int(value) for key, value in exact.items()}
    remaining = total - sum(quotas.values())
    for key in sorted(groups, key=lambda item: (exact[item] - quotas[item], group_sizes[item]), reverse=True)[:remaining]:
        quotas[key] += 1
    return quotas


def collect_images(pdf):
    records = []
    for page_index in range(len(pdf)):
        page = pdf[page_index]
        image_info = page.get_images(full=True)
        all_rects = [rect for info in image_info for rect in page.get_image_rects(info[0])]
        for image_no, info in enumerate(image_info, start=1):
            xref = info[0]
            rects = page.get_image_rects(xref)
            if not rects:
                continue
            rect = rects[0]
            records.append({
                "page_no": page_index + 1,
                "image_no": image_no,
                "xref": xref,
                "rects": rects,
                "bbox": [round(value, 2) for value in tuple(rect)],
                "width_pt": round(rect.width, 2),
                "height_pt": round(rect.height, 2),
                "page_image_rects": all_rects,
                "page_image_count": len(image_info),
                "stratum": (page_quartile(page_index + 1), "single" if len(image_info) == 1 else "multiple", size_class(rect)),
            })
    return records


def stratified_sample(records):
    rng = random.Random(SEED)
    groups = defaultdict(list)
    for record in records:
        groups[record["stratum"]].append(record)
    for group in groups.values():
        rng.shuffle(group)
    quotas = allocate_quotas(groups, min(SAMPLE_SIZE, len(records)))
    chosen = [record for key, group in groups.items() for record in group[:quotas[key]]]
    return sorted(chosen, key=lambda item: (item["page_no"], item["image_no"])), quotas


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    with pymupdf.open(PDF_PATH) as pdf:
        records = collect_images(pdf)
        sample, quotas = stratified_sample(records)
        output = []
        for record in sample:
            page = pdf[record["page_no"] - 1]
            text_blocks = []
            for rect in record["rects"]:
                for block in CarManualRegisterService._select_nearby_text_blocks(
                    page, rect, page_image_rects=record["page_image_rects"]
                ):
                    if block not in text_blocks:
                        text_blocks.append(block)
            text_blocks.sort(key=lambda block: block["distance"])
            description = CarManualRegisterService._generate_image_description(
                page, record["rects"], page_image_rects=record["page_image_rects"]
            )
            output.append({
                "page_no": record["page_no"],
                "image_no": record["image_no"],
                "xref": record["xref"],
                "bbox": record["bbox"],
                "width_pt": record["width_pt"],
                "height_pt": record["height_pt"],
                "page_image_count": record["page_image_count"],
                "stratum": list(record["stratum"]),
                "selected_text": [block["text"] for block in text_blocks[:6]],
                "selected_text_bboxes": [list(block["bbox"]) for block in text_blocks[:6]],
                "description": description,
                "is_none": description is None,
            })

    counts = Counter(tuple(row["stratum"]) for row in output)
    payload = {
        "pdf": str(PDF_PATH.relative_to(ROOT)),
        "seed": SEED,
        "population": len(records),
        "sample_size": len(output),
        "stratum_quotas": {"/".join(map(str, key)): value for key, value in quotas.items()},
        "stratum_actual": {"/".join(map(str, key)): value for key, value in counts.items()},
        "rows": output,
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
        print(f"WROTE {args.output}")
        if args.report:
            lines = [
                "# image_desc 100건 Dry-run 검토 자료", "",
                f"- PDF: `{payload['pdf']}` / 추출 이미지 모집단: {len(records)}건",
                f"- 재현 seed: `{SEED}` / 층화 표본: {len(output)}건",
                "- DB/Storage 접근·변경, Vision/Text LLM 호출 없음.",
                "- ‘품질 메모’는 주변 텍스트와 결과 문자열의 정적 점검이며 이미지 의미의 사람 육안 검수 결과가 아님.",
                "- 현재 결과만으로 production 전체 재적재를 승인할 수 없음.", "",
                "| # | page/image | bbox (pt) | 선택 주변 텍스트 | image_desc | 품질 메모 |", "|---:|---|---|---|---|---|",
            ]
            incomplete = re.compile(r"(?:있|하|되|할|하게|하고|으며|어서|해서|하면|하여|으로|에서|의|은|는|이|가|을|를|및|\s[·/-])$")
            for index, row in enumerate(output, start=1):
                context = " / ".join(row["selected_text"]).replace("\n", " ")
                desc = row["description"]
                if desc is None:
                    note = "None (주변 근거 없음/캡션 후보 미추출; 정답 여부 미판정)"
                    desc_text = "—"
                elif len(desc) > 60 or incomplete.search(desc):
                    note = "부적절 의심: 문장 조각/미완성 끝맺음"
                    desc_text = desc
                else:
                    note = "제목형 후보 (이미지 의미와의 일치 육안 확인 필요)"
                    desc_text = desc
                lines.append(
                    f"| {index} | p.{row['page_no']}/i{row['image_no']} | `{row['bbox']}` | "
                    f"{context[:260].replace('|', '/')} | {desc_text.replace('|', '/')} | {note} |"
                )
            args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")
            print(f"WROTE {args.report}")
        if args.summary:
            print(json.dumps({key: payload[key] for key in ("population", "sample_size", "stratum_quotas", "stratum_actual")}, ensure_ascii=False))
            non_null = sum(row["description"] is not None for row in output)
            print(json.dumps({"description_count": non_null, "none_count": len(output) - non_null, "description_rate_percent": round(100 * non_null / len(output), 2)}, ensure_ascii=False))
            for row in output:
                print(json.dumps({
                    "page_no": row["page_no"], "image_no": row["image_no"],
                    "bbox": row["bbox"], "size_pt": [row["width_pt"], row["height_pt"]],
                    "description": row["description"],
                    "context": " | ".join(row["selected_text"])[:100],
                }, ensure_ascii=False))
    else:
        print(rendered)


if __name__ == "__main__":
    main()
