"""Compare Vector-only and production LLM reranking on a frozen 50-question set."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv  # noqa: E402
from car_search_rag.car_search.car_manual_search_service import CarManualSearchService  # noqa: E402
from car_search_rag.common.sql_session import SqlSession  # noqa: E402


DATE = "20261004"
DOCS = Path(__file__).resolve().parents[1] / "docs"
QUESTION_SET = DOCS / f"UNSEEN_50_QUESTION_SET_{DATE}.json"
OUT_JSON = DOCS / f"UNSEEN_50_RERANKING_RESULTS_{DATE}.json"
OUT_CSV = DOCS / f"UNSEEN_50_RERANKING_RESULTS_{DATE}.csv"
OUT_MD = DOCS / f"UNSEEN_50_RERANKING_EVALUATION_{DATE}.md"


def evidence_id(row: dict) -> tuple[int, int]:
    return (
        int(row.get("page_no", row.get("pageNo", row.get("carManualChunkPageNo")))),
        int(row.get("chunk_id", row.get("chunkNo", row.get("carManualChunkNo")))),
    )


def rank_for(items: list[dict], acceptable: set[tuple[int, int]]) -> int | None:
    for rank, item in enumerate(items, start=1):
        if evidence_id(item) in acceptable:
            return rank
    return None


def metric_summary(records: list[dict], rank_key: str) -> dict:
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


def group_metrics(records: list[dict], key_path: str) -> dict:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in records:
        groups[str(row[key_path])].append(row)
    result = {}
    for key, items in sorted(groups.items(), key=lambda item: item[0]):
        m = metric_summary(items, "before_rank")
        after = metric_summary(items, "after_rank")
        result[key] = {
            "question_count": len(items),
            "vector_hit@5": m["hit@5"],
            "vector_mrr@5": m["mrr@5"],
            "rerank_hit@5": after["hit@5"],
            "rerank_mrr@5": after["mrr@5"],
        }
    return result


def main() -> None:
    if not QUESTION_SET.exists():
        raise FileNotFoundError(f"Required frozen question set missing: {QUESTION_SET}")
    for path in (OUT_JSON, OUT_CSV, OUT_MD):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite an existing evaluation artifact: {path}")

    question_bytes = QUESTION_SET.read_bytes()
    question_hash = hashlib.sha256(question_bytes).hexdigest()
    question_set = json.loads(question_bytes.decode("utf-8"))
    questions = question_set.get("questions", [])
    if len(questions) != 50 or [q["question_id"] for q in questions] != [f"U50-{i:03d}" for i in range(1, 51)]:
        raise ValueError("Frozen question set must contain U50-001 through U50-050 exactly once and in order")

    load_dotenv(ROOT / ".env")
    service = CarManualSearchService(SqlSession(sql_log_mode="none"))
    if not service.reranking_enabled:
        raise RuntimeError("Production reranking feature flag is disabled; refusing this comparison")

    records = []
    run_started = perf_counter()
    try:
        for question in questions:
            started = perf_counter()
            reranked, meta = service.search_manual_with_metadata(
                "hyundai", "sonata", 2026, question["question"], limit=10,
            )
            total_latency = perf_counter() - started
            vector_candidates = meta.get("candidate_mapping", [])
            if len(vector_candidates) != 10:
                raise RuntimeError(f"{question['question_id']}: Vector candidate set size is {len(vector_candidates)}, expected 10")
            before_ids = [evidence_id(item) for item in vector_candidates]
            after_ids = [evidence_id(item) for item in reranked]
            if len(after_ids) != 10 or set(before_ids) != set(after_ids):
                raise RuntimeError(f"{question['question_id']}: reranking changed the Top-10 candidate set")
            acceptable = {
                (int(item["page"]), int(item["chunk"]))
                for item in question["acceptable_evidence"]
            }
            before_rank = rank_for(vector_candidates, acceptable)
            after_rank = rank_for(reranked, acceptable)
            if before_rank is not None and before_rank > 10:
                raise AssertionError("before rank cannot exceed Top-10")
            record = {
                "question_id": question["question_id"],
                "chapter_no": question["chapter"]["number"],
                "chapter_name": question["chapter"]["name"],
                "question_type": question["question_type"],
                "question": question["question"],
                "expected_page": question["expected_page"],
                "expected_chunk": question["expected_chunk"],
                "acceptable_evidence": question["acceptable_evidence"],
                "before_rank": before_rank,
                "after_rank": after_rank,
                "rank_delta": None if before_rank is None or after_rank is None else before_rank - after_rank,
                "candidate_miss": before_rank is None,
                "ranking_failure": before_rank is not None and (after_rank is None or after_rank > 5),
                "rerank_success": bool(meta["success"]),
                "rerank_fallback_reason": meta["fallback_reason"],
                "vector_candidates": vector_candidates,
                "reranked_top10": [
                    {"rank": rank, "page": item.get("carManualChunkPageNo"), "chunk": item.get("carManualChunkNo")}
                    for rank, item in enumerate(reranked, start=1)
                ],
                "candidate_set_identical": set(before_ids) == set(after_ids),
                "request_count": meta["request_count"],
                "retry_count": meta["retry_count"],
                "rerank_latency_seconds": meta["latency_seconds"],
                "total_search_latency_seconds": total_latency,
                "input_tokens": meta["input_tokens"],
                "output_tokens": meta["output_tokens"],
            }
            records.append(record)
            print(json.dumps({"question_id": record["question_id"], "before": before_rank, "after": after_rank,
                              "success": record["rerank_success"], "latency_s": round(record["rerank_latency_seconds"], 3)}, ensure_ascii=True), flush=True)
    finally:
        service.sql_session.database_manager.close()

    if len(records) != 50:
        raise RuntimeError(f"Expected 50 evaluation records, got {len(records)}")
    total_run = perf_counter() - run_started
    before_metrics = metric_summary(records, "before_rank")
    after_metrics = metric_summary(records, "after_rank")
    chapter_groups = group_metrics(records, "chapter_no")
    type_groups = group_metrics(records, "question_type")
    rerank_latencies = [row["rerank_latency_seconds"] for row in records]
    input_total = sum(row["input_tokens"] for row in records)
    output_total = sum(row["output_tokens"] for row in records)
    retries = sum(row["retry_count"] for row in records)
    requests = sum(row["request_count"] for row in records)
    fallbacks = sum(not row["rerank_success"] for row in records)
    candidate_misses = sum(row["candidate_miss"] for row in records)
    ranking_failures = sum(row["ranking_failure"] for row in records)
    summary = {
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "evaluation_type": "new synthetic holdout; separate from historical M6 development set",
        "question_set_path": str(QUESTION_SET),
        "question_set_sha256": question_hash,
        "question_set_frozen_at_utc": question_set["frozen_at_utc"],
        "vehicle": "Hyundai Sonata 2026",
        "question_count": len(records),
        "vector_candidates": 10,
        "model": "gpt-5.6-luna",
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "chapter_metrics": chapter_groups,
        "question_type_metrics": type_groups,
        "candidate_miss_count": candidate_misses,
        "ranking_failure_count": ranking_failures,
        "reranked_success_count": len(records) - ranking_failures - candidate_misses,
        "candidate_sets_identical_all": all(row["candidate_set_identical"] for row in records),
        "request_count": requests,
        "input_tokens_total": input_total,
        "output_tokens_total": output_total,
        "total_tokens": input_total + output_total,
        "mean_input_tokens": input_total / len(records),
        "mean_output_tokens": output_total / len(records),
        "mean_rerank_latency_seconds": sum(rerank_latencies) / len(rerank_latencies),
        "min_rerank_latency_seconds": min(rerank_latencies),
        "max_rerank_latency_seconds": max(rerank_latencies),
        "mean_total_search_latency_seconds": sum(row["total_search_latency_seconds"] for row in records) / len(records),
        "total_run_seconds": total_run,
        "retry_count": retries,
        "rerank_error_attempt_count": sum(max(0, row["request_count"] - (1 if row["rerank_success"] else 0)) for row in records),
        "fallback_count": fallbacks,
        "records": records,
    }
    OUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    columns = ["question_id", "chapter_no", "chapter_name", "question_type", "question", "expected_page", "expected_chunk", "acceptable_evidence", "before_rank", "after_rank", "rank_delta", "candidate_miss", "ranking_failure", "rerank_success", "rerank_fallback_reason", "vector_candidates", "reranked_top10", "candidate_set_identical", "request_count", "retry_count", "rerank_latency_seconds", "total_search_latency_seconds", "input_tokens", "output_tokens"]
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for row in records:
            writer.writerow({**row,
                "acceptable_evidence": json.dumps(row["acceptable_evidence"], ensure_ascii=False),
                "vector_candidates": json.dumps(row["vector_candidates"], ensure_ascii=False),
                "reranked_top10": json.dumps(row["reranked_top10"], ensure_ascii=False),
            })

    def hits(metric):
        return f"{metric['hits']}/{metric['total']} ({metric['rate']:.1%})"

    md = [
        "# Sonata synthetic holdout: Vector-only vs LLM reranking",
        "",
        f"- Run: `{summary['run_id']}`; question set frozen at `{question_set['frozen_at_utc']}`.",
        f"- Frozen set SHA-256: `{question_hash}`.",
        "- New synthetic holdout: 50 questions, stratified from the current Sonata 2026 chunk corpus. This is separate from the historical M6 development set.",
        "- Reranker: production `CarManualSearchService.search_manual_with_metadata`, model `gpt-5.6-luna`.",
        "- Candidate policy: each question uses one unchanged Vector Top-10; the reranker only permutes those candidates.",
        "",
        "## Overall results",
        "",
        "| Metric | Vector Only | LLM Rerank |",
        "|---|---:|---:|",
        *[f"| Hit@{k} | {hits(before_metrics[f'hit@{k}'])} | {hits(after_metrics[f'hit@{k}'])} |" for k in (1, 3, 5, 10)],
        f"| MRR@5 | {before_metrics['mrr@5']:.4f} | {after_metrics['mrr@5']:.4f} |",
        f"| MRR@10 | {before_metrics['mrr@10']:.4f} | {after_metrics['mrr@10']:.4f} |",
        "",
        "## Candidate and ranking outcomes",
        "",
        f"- Vector Top-10 candidate misses: {candidate_misses}.",
        f"- Ranking failures (candidate present but reranked below Top-5): {ranking_failures}.",
        f"- Successful Top-5 after reranking: {summary['reranked_success_count']}.",
        f"- All candidate sets identical before/after: {summary['candidate_sets_identical_all']}.",
        "",
        "## Largest rank movements",
        "",
        "| Question | Chapter | Before | After | Rank rise |",
        "|---|---:|---:|---:|---:|",
    ]
    ranked = [row for row in records if row["rank_delta"] is not None]
    for row in sorted(ranked, key=lambda r: (-r["rank_delta"], r["question_id"]))[:5]:
        md.append(f"| {row['question_id']} | {row['chapter_no']} | {row['before_rank']} | {row['after_rank']} | +{row['rank_delta']} |")
    md.extend(["", "| Question | Chapter | Before | After | Rank fall |", "|---|---:|---:|---:|---:|"])
    for row in sorted(ranked, key=lambda r: (r["rank_delta"], r["question_id"]))[:5]:
        md.append(f"| {row['question_id']} | {row['chapter_no']} | {row['before_rank']} | {row['after_rank']} | {row['rank_delta']} |")
    md.extend(["", "## Chapter metrics", "", "| Chapter | Questions | Vector Hit@5 | Vector MRR@5 | Rerank Hit@5 | Rerank MRR@5 |", "|---:|---:|---:|---:|---:|---:|"])
    for chapter, item in chapter_groups.items():
        md.append(f"| {chapter} | {item['question_count']} | {hits(item['vector_hit@5'])} | {item['vector_mrr@5']:.4f} | {hits(item['rerank_hit@5'])} | {item['rerank_mrr@5']:.4f} |")
    md.extend(["", "## Question-type metrics", "", "| Type | Questions | Vector Hit@5 | Vector MRR@5 | Rerank Hit@5 | Rerank MRR@5 |", "|---|---:|---:|---:|---:|---:|"])
    for kind, item in type_groups.items():
        md.append(f"| {kind} | {item['question_count']} | {hits(item['vector_hit@5'])} | {item['vector_mrr@5']:.4f} | {hits(item['rerank_hit@5'])} | {item['rerank_mrr@5']:.4f} |")
    md.extend([
        "", "## Latency and usage", "",
        f"- Requests: {requests}; input tokens: {input_total}; output tokens: {output_total}; total tokens: {input_total + output_total}.",
        f"- Mean input/output tokens per question: {summary['mean_input_tokens']:.1f}/{summary['mean_output_tokens']:.1f}.",
        f"- Mean/min/max rerank latency: {summary['mean_rerank_latency_seconds']:.3f}/{summary['min_rerank_latency_seconds']:.3f}/{summary['max_rerank_latency_seconds']:.3f}s.",
        f"- Mean total search latency: {summary['mean_total_search_latency_seconds']:.3f}s; total 50-question elapsed time: {total_run:.3f}s.",
        f"- Retry count: {retries}; rerank error attempts: {summary['rerank_error_attempt_count']}; fallbacks: {fallbacks}.",
        "",
        "## Comparison and interpretation",
        "",
        "Historical M6 development set (11 questions): Vector Hit@5 81.8%, MRR@5 0.5333; production LLM rerank Hit@5 100%, MRR@5 0.9091. These historical results remain separate and are not pooled with this holdout.",
        "This 50-question set is generated synthetically from sampled manual chunks; it is not equivalent to 50 real user questions and does not prove generalization to actual user traffic.",
        "",
    ])
    if after_metrics["hit@5"]["rate"] > before_metrics["hit@5"]["rate"] or after_metrics["mrr@5"] > before_metrics["mrr@5"] + 0.05:
        verdict = "A. unseen synthetic holdout에서도 명확한 개선"
    elif after_metrics["hit@5"]["rate"] > before_metrics["hit@5"]["rate"] or after_metrics["mrr@5"] > before_metrics["mrr@5"]:
        verdict = "B. 일부 개선"
    else:
        verdict = "C. 개발셋에서만 개선 폭이 컸음"
    md.extend([f"**Verdict: {verdict}.**", ""])
    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({"evaluation_written": True, "run_id": summary["run_id"], "question_set_sha256": question_hash,
                      "report": str(OUT_MD), "csv": str(OUT_CSV), "json": str(OUT_JSON)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
