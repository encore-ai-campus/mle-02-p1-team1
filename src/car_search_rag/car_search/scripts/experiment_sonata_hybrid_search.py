"""Read-only LIKE hybrid-search experiment on the frozen Sonata U50 holdout."""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv  # noqa: E402
from car_search_rag.car_search.car_manual_search_service import (  # noqa: E402
    CarManualSearchService,
    RERANKER_SYSTEM_PROMPT,
    _message_text,
)
from car_search_rag.common.sql_session import SqlSession  # noqa: E402


QUESTION_SET = Path(__file__).resolve().parents[1] / "docs" / "UNSEEN_50_QUESTION_SET_20261004.json"
TOP_K = 10

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

KEYWORD_SYSTEM = """Extract 3 to 6 concise Korean search terms for searching a vehicle manual.
Return only a JSON object: {\"keywords\":[\"term1\",...]}.
Prefer nouns and essential actions from the question. Remove particles and question phrasing.
You may add a directly equivalent manual term only when it does not change the question.
Do not infer an answer or add facts. Preserve useful technical abbreviations."""


def value(row: dict, camel: str, snake: str):
    return row.get(camel, row.get(snake))


def evidence_id(row: dict) -> tuple[int, int]:
    return (
        int(value(row, "carManualChunkPageNo", "car_manual_chunk_page_no")),
        int(value(row, "carManualChunkNo", "car_manual_chunk_no")),
    )


def rank_for(rows: list[dict], acceptable: set[tuple[int, int]]) -> int | None:
    return next((i for i, row in enumerate(rows, 1) if evidence_id(row) in acceptable), None)


def metric_summary(records: list[dict], key: str) -> dict:
    result = {}
    for k in (1, 3, 5, 10):
        hits = sum(row[key] is not None and row[key] <= k for row in records)
        result[f"hit@{k}"] = {"hits": hits, "total": len(records), "rate": hits / len(records)}
    for k in (5, 10):
        result[f"mrr@{k}"] = sum(
            1 / row[key] if row[key] is not None and row[key] <= k else 0 for row in records
        ) / len(records)
    return result


def extract_keywords(model, question: str) -> tuple[list[str], float]:
    started = perf_counter()
    response = model.invoke([("system", KEYWORD_SYSTEM), ("human", question)])
    raw = _message_text(response).strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE)
    parsed = json.loads(raw)
    terms = parsed.get("keywords") if isinstance(parsed, dict) else None
    if not isinstance(terms, list):
        raise ValueError(f"Keyword model did not return a keywords array: {raw[:300]}")
    clean = []
    for term in terms:
        if not isinstance(term, str):
            continue
        term = term.strip()
        if term and term not in clean:
            clean.append(term)
    if not 3 <= len(clean) <= 6:
        raise ValueError(f"Expected 3-6 distinct keywords, got {len(clean)}: {clean}")
    return clean, perf_counter() - started


def keyword_search(connection, car_id: str, keywords: list[str]) -> tuple[list[dict], float]:
    # All SQL identifiers are fixed; all variable values are bound parameters.
    score = " + ".join("CASE WHEN D.CAR_MANUAL_CHUNK_TXT LIKE %s THEN 1 ELSE 0 END" for _ in keywords)
    matches = " OR ".join("D.CAR_MANUAL_CHUNK_TXT LIKE %s" for _ in keywords)
    sql = f"""
        SELECT D.CAR_ID, D.CAR_MANUAL_CHAPTER_ID, H.CAR_MANUAL_CHAPTER_NO,
               H.CAR_MANUAL_CHAPTER_NM, D.CAR_MANUAL_CHUNK_PAGE_NO,
               D.CAR_MANUAL_CHUNK_NO, D.CAR_MANUAL_CHUNK_TXT,
               ({score}) AS KEYWORD_SCORE
          FROM CAR_MANUAL_CHUNK D
          JOIN CAR_MANUAL_CHAPTER H
            ON H.CAR_ID = D.CAR_ID
           AND H.CAR_MANUAL_CHAPTER_ID = D.CAR_MANUAL_CHAPTER_ID
         WHERE D.CAR_ID = %s
           AND ({matches})
         ORDER BY KEYWORD_SCORE DESC, D.CAR_MANUAL_CHUNK_PAGE_NO,
                  D.CAR_MANUAL_CHUNK_NO
         LIMIT %s
    """
    params = [f"%{term}%" for term in keywords] + [car_id] + [f"%{term}%" for term in keywords] + [TOP_K]
    started = perf_counter()
    rows = connection.execute(sql, params).fetchall()
    return list(rows), perf_counter() - started


def rerank_hybrid(service, question: str, candidates: list[dict]) -> tuple[list[dict], float, dict]:
    """Use the production reranker model/prompt with dynamic candidate IDs (up to 20)."""
    if len(candidates) == TOP_K:
        started = perf_counter()
        ranked, metadata = service.rerank_search_results(question, candidates)
        return ranked, perf_counter() - started, metadata
    if not candidates or len(candidates) > 2 * TOP_K:
        raise ValueError(f"Hybrid candidate count must be in 1..20, got {len(candidates)}")
    ids = [f"C{i:02d}" for i in range(1, len(candidates) + 1)]
    payload = {
        "question": question,
        "candidates": [
            {
                "candidate_id": cid,
                "page_no": value(row, "carManualChunkPageNo", "car_manual_chunk_page_no"),
                "chunk_id": value(row, "carManualChunkNo", "car_manual_chunk_no"),
                "text": value(row, "carManualChunkTxt", "car_manual_chunk_txt") or "",
            }
            for cid, row in zip(ids, candidates)
        ],
    }
    started = perf_counter()
    # The production model and settings are reused. Only raise its response
    # budget for the longer (up to 20-item) ranking payload in this experiment.
    hybrid_reranker = service.reranker_model.bound.bind(max_completion_tokens=1200).bind(
        response_format={"type": "json_object"}
    )
    last_error = None
    response = None
    ranking = None
    for attempt in range(2):
        try:
            response = hybrid_reranker.invoke([
                ("system", RERANKER_SYSTEM_PROMPT),
                ("human", json.dumps(payload, ensure_ascii=False)),
            ])
            raw = _message_text(response).strip()
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE)
            result = json.loads(raw)
            ranking = result.get("ranking")
            got = [item.get("candidate_id") for item in ranking] if isinstance(ranking, list) else ranking
            if not isinstance(ranking, list) or len(got) != len(ids) or set(got) != set(ids) or len(set(got)) != len(ids):
                raise ValueError(f"invalid candidate permutation: {got}")
            scores = [item.get("relevance_score") for item in ranking]
            if any(isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 100 for score in scores):
                raise ValueError(f"invalid relevance scores: {scores}")
            if any(left < right for left, right in zip(scores, scores[1:])):
                raise ValueError("scores are not sorted in descending order")
            break
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {str(exc)[:240]}"
            if attempt == 0:
                time.sleep(0.5)
    elapsed = perf_counter() - started
    if ranking is None or last_error is not None and (
        not isinstance(ranking, list)
        or len(ranking) != len(ids)
        or {item.get("candidate_id") for item in ranking} != set(ids)
        or any(isinstance(item.get("relevance_score"), bool) or not isinstance(item.get("relevance_score"), int) or not 0 <= item["relevance_score"] <= 100 for item in ranking)
        or any(a["relevance_score"] < b["relevance_score"] for a, b in zip(ranking, ranking[1:]))
    ):
        return candidates, elapsed, {
            "success": False, "latency_seconds": elapsed, "input_tokens": 0,
            "output_tokens": 0, "candidate_count": len(candidates),
            "model": None, "fallback_reason": last_error,
        }
    ranked = [candidates[ids.index(item["candidate_id"])] for item in ranking]
    return ranked, elapsed, {
        "success": True,
        "latency_seconds": elapsed,
        "input_tokens": int((getattr(response, "usage_metadata", None) or {}).get("input_tokens", 0) or 0),
        "output_tokens": int((getattr(response, "usage_metadata", None) or {}).get("output_tokens", 0) or 0),
        "candidate_count": len(candidates),
        "model": getattr(service.reranker_model, "model_name", None),
        "fallback_reason": None,
    }


def main() -> None:
    question_bytes = QUESTION_SET.read_bytes()
    question_set = json.loads(question_bytes.decode("utf-8"))
    questions = question_set.get("questions", [])
    if len(questions) != 50:
        raise ValueError(f"Expected 50 frozen questions, found {len(questions)}")

    load_dotenv(ROOT / ".env")
    sql_session = SqlSession(sql_log_mode="none")
    service = CarManualSearchService(sql_session)
    if not service.reranking_enabled or service.reranker_model is None:
        raise RuntimeError("Production reranker is disabled; cannot run the requested comparison")

    records = []
    try:
        with sql_session.database_manager.connect(camel_case_keys=True) as connection:
            car = connection.execute(
                "SELECT CAR_ID FROM CAR WHERE CAR_BRAND_ENG_NM = %s AND CAR_ENG_NM = %s AND CAR_MODEL_YR = %s",
                ("hyundai", "sonata", 2026),
            ).fetchall()
            if len(car) != 1:
                raise RuntimeError(f"Expected one current Sonata car row, found {len(car)}")
            car_id = str(car[0]["carId"])
            frozen_car_id = str(question_set.get("current_car_id_at_sampling"))
            if car_id != frozen_car_id:
                raise RuntimeError(
                    f"Current Sonata car_id {car_id} differs from holdout source car_id {frozen_car_id}; refusing mismatched evaluation"
                )

            for question in questions:
                q = question["question"]
                query_started = perf_counter()
                query_vector = service.embedding_model.embed_query(q)
                vector_rows = service.repository.search_manual(
                    "hyundai", "sonata", 2026, query_vector, TOP_K
                )
                vector_latency = perf_counter() - query_started
                if len(vector_rows) != TOP_K:
                    raise RuntimeError(f"{question['question_id']}: expected 10 Vector rows, got {len(vector_rows)}")

                baseline_ranked, baseline_meta = service.rerank_search_results(q, vector_rows)
                keywords, keyword_extract_latency = extract_keywords(service.chat_model, q)
                keyword_rows, like_latency = keyword_search(connection, car_id, keywords)

                candidates = []
                seen = set()
                vector_ranks = {}
                keyword_ranks = {}
                keyword_scores = {}
                for rank, row in enumerate(vector_rows, 1):
                    key = evidence_id(row)
                    if key not in seen:
                        candidates.append(row)
                        seen.add(key)
                        vector_ranks[key] = rank
                for rank, row in enumerate(keyword_rows, 1):
                    key = evidence_id(row)
                    keyword_ranks[key] = rank
                    keyword_scores[key] = row.get("keywordScore", row.get("keyword_score", row.get("KEYWORD_SCORE")))
                    if key not in seen:
                        candidates.append(row)
                        seen.add(key)
                if len(candidates) > 20:
                    raise AssertionError(f"Hybrid produced more than 20 candidates: {len(candidates)}")

                hybrid_ranked, hybrid_rerank_latency, hybrid_meta = rerank_hybrid(service, q, candidates)
                acceptable = {(int(item["page"]), int(item["chunk"])) for item in question["acceptable_evidence"]}
                v_rank = rank_for(vector_rows, acceptable)
                base_rank = rank_for(baseline_ranked, acceptable)
                hybrid_candidate_rank = rank_for(candidates, acceptable)
                hybrid_rank = rank_for(hybrid_ranked, acceptable)
                matched_gold = next((evidence_id(row) for row in candidates if evidence_id(row) in acceptable), None)
                records.append({
                    "question_id": question["question_id"],
                    "question": q,
                    "acceptable_evidence": sorted(acceptable),
                    "keywords": keywords,
                    "vector_rank": v_rank,
                    "baseline_rank": base_rank,
                    "keyword_gold_rank": keyword_ranks.get(matched_gold) if matched_gold else None,
                    "hybrid_candidate_rank": hybrid_candidate_rank,
                    "hybrid_rank": hybrid_rank,
                    "vector_ranks": {f"{p}:{c}": r for (p, c), r in vector_ranks.items()},
                    "keyword_ranks": {f"{p}:{c}": r for (p, c), r in keyword_ranks.items()},
                    "keyword_scores": {f"{p}:{c}": keyword_scores.get((p, c)) for p, c in keyword_ranks},
                    "candidate_count": len(candidates),
                    "baseline_rerank_latency": baseline_meta.get("latency_seconds", 0.0),
                    "hybrid_rerank_latency": hybrid_rerank_latency,
                    "keyword_extract_latency": keyword_extract_latency,
                    "keyword_search_latency": like_latency,
                    "vector_latency": vector_latency,
                    "hybrid_rerank_success": hybrid_meta["success"],
                })
                print(json.dumps({
                    "question_id": question["question_id"],
                    "vector_rank": v_rank,
                    "keyword_rank": records[-1]["keyword_gold_rank"],
                    "hybrid_candidate_rank": hybrid_candidate_rank,
                    "baseline_reranked_rank": base_rank,
                    "hybrid_reranked_rank": hybrid_rank,
                    "keywords": keywords,
                    "candidate_count": len(candidates),
                    "vector_candidates": [
                        {"rank": rank, "page": evidence_id(row)[0], "chunk": evidence_id(row)[1]}
                        for rank, row in enumerate(vector_rows, 1)
                    ],
                    "keyword_candidates": [
                        {
                            "rank": rank,
                            "page": evidence_id(row)[0],
                            "chunk": evidence_id(row)[1],
                            "keyword_score": value(row, "keywordScore", "keyword_score"),
                        }
                        for rank, row in enumerate(keyword_rows, 1)
                    ],
                }, ensure_ascii=False), flush=True)
    finally:
        sql_session.database_manager.close()

    before = metric_summary(records, "baseline_rank")
    after = metric_summary(records, "hybrid_rank")
    vector_misses = [row for row in records if row["vector_rank"] is None]
    recovered = sum(row["hybrid_candidate_rank"] is not None for row in vector_misses)
    mean_keyword = sum(row["keyword_search_latency"] for row in records) / len(records)
    mean_extract = sum(row["keyword_extract_latency"] for row in records) / len(records)
    mean_vector = sum(row["vector_latency"] for row in records) / len(records)
    mean_base_rerank = sum(row["baseline_rerank_latency"] for row in records) / len(records)
    mean_hybrid_rerank = sum(row["hybrid_rerank_latency"] for row in records) / len(records)
    mean_hybrid_total = mean_extract + mean_keyword + mean_vector + mean_hybrid_rerank
    mean_baseline_total = mean_vector + mean_base_rerank

    def show_metrics(title: str, metrics: dict) -> None:
        print(f"\n{title}")
        for k in (1, 3, 5, 10):
            m = metrics[f"hit@{k}"]
            print(f"Hit@{k}: {m['hits']}/{m['total']} ({m['rate']:.1%})")
        print(f"MRR@5: {metrics['mrr@5']:.4f}")
        print(f"MRR@10: {metrics['mrr@10']:.4f}")

    print(f"\nQuestion set SHA-256: {hashlib.sha256(question_bytes).hexdigest()}")
    print(f"Current car_id: {car_id}")
    show_metrics("A. Vector Top-10 + production LLM reranking", before)
    show_metrics("B. Vector + LIKE Top-10 + production LLM reranking", after)
    print(f"\nVector Top-10 misses: {len(vector_misses)}; Hybrid Candidate recovered: {recovered}/{len(vector_misses)}")
    print(f"Mean keyword extraction: {mean_extract:.3f}s")
    print(f"Mean Vector embedding + search: {mean_vector:.3f}s")
    print(f"Mean LIKE search: {mean_keyword:.3f}s")
    print(f"Mean baseline reranking: {mean_base_rerank:.3f}s")
    print(f"Mean hybrid reranking: {mean_hybrid_rerank:.3f}s")
    print(f"Mean baseline total: {mean_baseline_total:.3f}s")
    print(f"Mean hybrid total: {mean_hybrid_total:.3f}s ({mean_hybrid_total - mean_baseline_total:+.3f}s, {(mean_hybrid_total / mean_baseline_total - 1):+.1%})")
    print("\nVector miss details")
    print("question_id | question | gold_evidence | vector_rank | keyword_rank | hybrid_included | reranked_rank")
    for row in vector_misses:
        print(json.dumps({
            "question_id": row["question_id"],
            "question": row["question"],
            "gold_evidence": row["acceptable_evidence"],
            "vector_rank": row["vector_rank"],
            "keyword_rank": row["keyword_gold_rank"],
            "hybrid_candidate_included": row["hybrid_candidate_rank"] is not None,
            "hybrid_candidate_rank": row["hybrid_candidate_rank"],
            "reranked_rank": row["hybrid_rank"],
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
