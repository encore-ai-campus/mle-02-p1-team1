"""Evaluate the live service retrieval method with LLM reranking enabled.

Run from repository root:
    python src/car_search_rag/car_search/scripts/evaluate_sonata_production_reranking.py

This uses the exact ``CarManualSearchService.search_manual_with_metadata``
method called by production ``search_manual``. It only reads the existing M6
questions/evidence and Sonata search rows; it does not generate answers or write
to PostgreSQL/Storage.
"""

from __future__ import annotations

import csv
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv  # noqa: E402
from car_search_rag.car_search.car_manual_search_service import CarManualSearchService  # noqa: E402
from car_search_rag.common.sql_session import SqlSession  # noqa: E402


SCRIPT_DIR = Path(__file__).resolve().parent
DOCS_DIR = SCRIPT_DIR.parent / "docs"
QUESTIONS_CSV = DOCS_DIR / "M6_RETRIEVAL_RESULTS.csv"
RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
OUT_JSON = DOCS_DIR / f"LLM_RERANKING_PRODUCTION_VALIDATION_{RUN_ID}.json"
OUT_CSV = DOCS_DIR / f"LLM_RERANKING_PRODUCTION_VALIDATION_{RUN_ID}.csv"
OUT_MD = DOCS_DIR / f"LLM_RERANKING_PRODUCTION_VALIDATION_{RUN_ID}.md"


def load_questions() -> list[dict]:
    with QUESTIONS_CSV.open(encoding="utf-8-sig", newline="") as file:
        source = list(csv.DictReader(file))
    result = []
    for row in source:
        acceptable = []
        for item in row["Acceptable page/chunk"].split(";"):
            item = item.strip()
            if item:
                page, chunk = item.split("/")
                acceptable.append(f"p{int(page.removeprefix('p'))}/c{int(chunk.removeprefix('c'))}")
        baseline_top10 = [token.split(":", 1)[1].strip() for token in row["Top-10 page/chunk"].split(";")]
        result.append({
            "question_id": row["ID"],
            "question": row["Question"],
            "expected": row["Expected page/chunk"],
            "acceptable": acceptable,
            "baseline_top10": baseline_top10,
            "baseline_expected_rank": int(row["First relevant rank"]),
        })
    if len(result) != 11:
        raise ValueError(f"Expected 11 M6 questions, found {len(result)}")
    return result


def evidence_id(row: dict) -> str:
    page = row.get("carManualChunkPageNo", row.get("car_manual_chunk_page_no"))
    chunk = row.get("carManualChunkNo", row.get("car_manual_chunk_no"))
    return f"p{page}/c{chunk}"


def find_rank(rows: list[dict], acceptable: set[str]) -> int | None:
    for rank, row in enumerate(rows, 1):
        if evidence_id(row) in acceptable:
            return rank
    return None


def metrics(records: list[dict], rank_key: str) -> dict:
    result = {}
    for k in (1, 3, 5, 10):
        hits = sum(row[rank_key] is not None and row[rank_key] <= k for row in records)
        result[f"hit@{k}"] = {"hits": hits, "total": len(records), "rate": hits / len(records)}
    for k in (5, 10):
        result[f"mrr@{k}"] = sum(
            1 / row[rank_key] if row[rank_key] is not None and row[rank_key] <= k else 0
            for row in records
        ) / len(records)
    return result


def main() -> None:
    for path in (OUT_JSON, OUT_CSV, OUT_MD):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite existing validation run: {path}")
    load_dotenv()
    questions = load_questions()
    service = CarManualSearchService(SqlSession(sql_log_mode="none"))
    if not service.reranking_enabled:
        raise RuntimeError("ENABLE_LLM_RERANKING is false; production reranking validation aborted")

    records = []
    run_started = perf_counter()
    for question in questions:
        search_started = perf_counter()
        ranked_rows, metadata = service.search_manual_with_metadata(
            "hyundai", "sonata", 2026, question["question"], limit=10,
        )
        total_search_latency = perf_counter() - search_started
        after_rank = find_rank(ranked_rows, set(question["acceptable"]))
        actual_vector_ids = [
            f"p{item['page_no']}/c{item['chunk_id']}"
            for item in metadata.get("candidate_mapping", [])
        ]
        records.append({
            **question,
            "vector_candidate_count": metadata["candidate_count"],
            "vector_candidate_mapping": metadata.get("candidate_mapping", []),
            "baseline_vector_candidate_set_matches": set(actual_vector_ids) == set(question["baseline_top10"]),
            "rerank_success": metadata["success"],
            "reranker_model": metadata["model"],
            "rerank_latency_seconds": metadata["latency_seconds"],
            "input_tokens": metadata["input_tokens"],
            "output_tokens": metadata["output_tokens"],
            "request_count": metadata["request_count"],
            "retry_count": metadata["retry_count"],
            "fallback_reason": metadata["fallback_reason"],
            "before_expected_rank": question["baseline_expected_rank"],
            "after_expected_rank": after_rank,
            "before_hit_at_5": question["baseline_expected_rank"] <= 5,
            "after_hit_at_5": after_rank is not None and after_rank <= 5,
            "rank_change": "상승" if after_rank is not None and after_rank < question["baseline_expected_rank"] else "하락" if after_rank is None or after_rank > question["baseline_expected_rank"] else "유지",
            "reranked_top10": [
                {"rank": rank, "page_no": row.get("carManualChunkPageNo"),
                 "chunk_id": row.get("carManualChunkNo"),
                 "similarity": row.get("similarity")}
                for rank, row in enumerate(ranked_rows, 1)
            ],
            "total_search_latency_seconds": total_search_latency,
        })
        print(
            f"{question['question_id']}: {question['baseline_expected_rank']} -> {after_rank}; "
            f"rerank_success={metadata['success']} total_ms={total_search_latency * 1000:.1f}",
            flush=True,
        )

    total_run_latency = perf_counter() - run_started
    before_metrics = metrics(records, "before_expected_rank")
    after_metrics = metrics(records, "after_expected_rank")
    summary = {
        "run_id": RUN_ID,
        "validation": "production CarManualSearchService.search_manual_with_metadata; retrieval only, no answer generation",
        "model": "gpt-5.6-luna",
        "reranking_enabled": service.reranking_enabled,
        "question_count": len(records),
        "vector_candidates_per_question": 10,
        "vector_candidate_set_matches_baseline_all_questions": all(r["baseline_vector_candidate_set_matches"] for r in records),
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "mean_rerank_latency_seconds": sum(r["rerank_latency_seconds"] for r in records) / len(records),
        "mean_total_search_latency_seconds": sum(r["total_search_latency_seconds"] for r in records) / len(records),
        "total_search_latency_seconds_all_questions": sum(r["total_search_latency_seconds"] for r in records),
        "mean_input_tokens": sum(r["input_tokens"] for r in records) / len(records),
        "mean_output_tokens": sum(r["output_tokens"] for r in records) / len(records),
        "input_tokens_total": sum(r["input_tokens"] for r in records),
        "output_tokens_total": sum(r["output_tokens"] for r in records),
        "api_request_count": sum(r["request_count"] for r in records),
        "api_retry_count": sum(r["retry_count"] for r in records),
        "fallback_count": sum(not r["rerank_success"] for r in records),
        "total_run_latency_seconds": total_run_latency,
        "records": records,
        "runtime": {"python": platform.python_version(), "platform": platform.platform()},
    }
    OUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as file:
        columns = ["question_id", "question", "expected", "before_expected_rank", "after_expected_rank", "before_hit_at_5", "after_hit_at_5", "rank_change", "rerank_success", "candidate_count", "candidate_set_matches_baseline", "rerank_latency_seconds", "total_search_latency_seconds", "input_tokens", "output_tokens", "request_count", "retry_count", "fallback_reason", "vector_candidate_mapping", "reranked_top10"]
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for row in records:
            writer.writerow({
                "question_id": row["question_id"], "question": row["question"], "expected": row["expected"],
                "before_expected_rank": row["before_expected_rank"], "after_expected_rank": row["after_expected_rank"],
                "before_hit_at_5": row["before_hit_at_5"], "after_hit_at_5": row["after_hit_at_5"],
                "rank_change": row["rank_change"], "rerank_success": row["rerank_success"],
                "candidate_count": row["vector_candidate_count"],
                "candidate_set_matches_baseline": row["baseline_vector_candidate_set_matches"],
                "rerank_latency_seconds": row["rerank_latency_seconds"],
                "total_search_latency_seconds": row["total_search_latency_seconds"],
                "input_tokens": row["input_tokens"], "output_tokens": row["output_tokens"],
                "request_count": row["request_count"], "retry_count": row["retry_count"],
                "fallback_reason": row["fallback_reason"],
                "vector_candidate_mapping": json.dumps(row["vector_candidate_mapping"], ensure_ascii=False),
                "reranked_top10": json.dumps(row["reranked_top10"], ensure_ascii=False),
            })

    def hit(metric):
        return f"{metric['hits']}/{metric['total']} ({metric['rate']:.1%})"
    report = f"""# Sonata LLM reranking: production-path validation

Run: `{RUN_ID}`. The run calls the production service search method, uses its unchanged Vector Top-10, and executes retrieval only (no answer generation).

| Metric | Vector-only M6 baseline | Production service after |
|---|---:|---:|
| Hit@1 | {hit(before_metrics['hit@1'])} | {hit(after_metrics['hit@1'])} |
| Hit@3 | {hit(before_metrics['hit@3'])} | {hit(after_metrics['hit@3'])} |
| Hit@5 | {hit(before_metrics['hit@5'])} | {hit(after_metrics['hit@5'])} |
| Hit@10 | {hit(before_metrics['hit@10'])} | {hit(after_metrics['hit@10'])} |
| MRR@5 | {before_metrics['mrr@5']:.4f} | {after_metrics['mrr@5']:.4f} |
| MRR@10 | {before_metrics['mrr@10']:.4f} | {after_metrics['mrr@10']:.4f} |

- Vector candidates per question: 10; candidate sets match M6 CSV on all questions: {summary['vector_candidate_set_matches_baseline_all_questions']}.
- Reranker: gpt-5.6-luna. Mean API rerank latency: {summary['mean_rerank_latency_seconds']:.3f}s; mean total search latency: {summary['mean_total_search_latency_seconds']:.3f}s.
- Mean input/output tokens: {summary['mean_input_tokens']:.1f}/{summary['mean_output_tokens']:.1f}; requests {summary['api_request_count']}; retries {summary['api_retry_count']}; fallbacks {summary['fallback_count']}.
- M6-05: {next(r['before_expected_rank'] for r in records if r['question_id']=='M6-05')} → {next(r['after_expected_rank'] for r in records if r['question_id']=='M6-05')}.
- M6-11: {next(r['before_expected_rank'] for r in records if r['question_id']=='M6-11')} → {next(r['after_expected_rank'] for r in records if r['question_id']=='M6-11')}.
- This 11-question set was used during development and does not establish accuracy on unseen questions.
"""
    OUT_MD.write_text(report, encoding="utf-8")
    print(f"Wrote {OUT_MD}\nWrote {OUT_CSV}\nWrote {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
