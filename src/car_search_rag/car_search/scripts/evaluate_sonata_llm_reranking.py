"""Evaluate text-only LLM reranking of the existing M6 Sonata vector Top-10.

Run from repository root:
    python src/car_search_rag/car_search/scripts/evaluate_sonata_llm_reranking.py

The script reads the existing M6 question/evidence CSV, executes only the
existing query embedding + search_car_manual SELECT path, then sends one request
per question with its ten retrieved chunk texts. It does not write to the DB.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
import os
import platform
import re
import sys
import time
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv  # noqa: E402
from langchain_openai import ChatOpenAI, OpenAIEmbeddings  # noqa: E402

from car_search_rag.car_search.car_manual_search_service import (  # noqa: E402
    CarManualSearchService,
)
from car_search_rag.common.sql_session import SqlSession  # noqa: E402


SCRIPT_DIR = Path(__file__).resolve().parent
DOCS_DIR = SCRIPT_DIR.parent / "docs"
BASELINE_CSV = DOCS_DIR / "M6_RETRIEVAL_RESULTS.csv"
RUN_ID = os.getenv("LLM_RERANKING_RUN_ID") or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
if not re.fullmatch(r"[A-Za-z0-9_-]+", RUN_ID):
    raise ValueError("LLM_RERANKING_RUN_ID may contain only letters, numbers, underscore, and hyphen")
RESULTS_JSON = DOCS_DIR / f"LLM_RERANKING_RESULTS_{RUN_ID}.json"
RESULTS_CSV = DOCS_DIR / f"LLM_RERANKING_RESULTS_{RUN_ID}.csv"
EVALUATION_MD = DOCS_DIR / f"LLM_RERANKING_EVALUATION_{RUN_ID}.md"
MODEL = "gpt-5.6-luna"
TOP_K = 10
MAX_RETRIES = 2

SYSTEM_PROMPT = """You are a retrieval reranker.

사용자 질문과 검색된 문서 청크 10개를 보고, 질문의 답변 근거로 얼마나 유용한지 평가해 가장 관련 높은 순서로 정렬하세요.
제공된 text만 근거로 판단하세요. 질문에 답하지 말고, 사실을 추가하지 말고, 문서를 고쳐 쓰지 마세요.
질문에 직접 답하는 정보, 절차, 조건, 경고, 설명을 우선하세요. 같은 부품·기능·작업에 관한 내용 중 직접성이 낮은 것은 그 다음, 단순히 같은 장에 있거나 단어만 비슷한 내용은 낮게 평가하세요.
모든 후보를 정확히 한 번씩 반환하세요. candidate_id와 text를 변경하거나 후보를 만들지 마세요.

JSON object만 반환하세요. 형식:
{"ranking":[{"candidate_id":"C01","relevance_score":0,"reason":"짧은 근거"}]}
relevance_score는 0~100 정수이고, ranking은 점수 내림차순이어야 합니다."""


def load_questions() -> list[dict]:
    with BASELINE_CSV.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    questions = []
    for row in rows:
        acceptable = []
        for token in row["Acceptable page/chunk"].split(";"):
            token = token.strip()
            if token:
                page, chunk = token.split("/")
                acceptable.append({"page": int(page.removeprefix("p")), "chunk": int(chunk.removeprefix("c"))})
        questions.append({
            "question_id": row["ID"],
            "question": row["Question"],
            "expected_page_chunk": row["Expected page/chunk"],
            "acceptable": acceptable,
        })
    if len(questions) != 11:
        raise ValueError(f"M6 baseline must contain 11 questions, found {len(questions)}")
    return questions


def canonical_id(row: dict) -> str:
    return f"p{row['carManualChunkPageNo']}/c{row['carManualChunkNo']}"


def find_rank(candidates: list[dict], expected_ids: set[str]) -> int | None:
    for rank, candidate in enumerate(candidates, 1):
        evidence_id = candidate.get("source_candidate_id", candidate["candidate_id"])
        if evidence_id in expected_ids:
            return rank
    return None


def calculate_metrics(records: list[dict], rank_key: str) -> dict:
    metrics = {}
    n = len(records)
    for k in (1, 3, 5, 10):
        hits = sum(r[rank_key] is not None and r[rank_key] <= k for r in records)
        metrics[f"hit@{k}"] = {"hits": hits, "total": n, "rate": hits / n}
    for k in (5, 10):
        metrics[f"mrr@{k}"] = sum(
            1 / r[rank_key] if r[rank_key] is not None and r[rank_key] <= k else 0
            for r in records
        ) / n
    return metrics


def token_usage(message) -> dict:
    usage = getattr(message, "usage_metadata", None) or {}
    response_usage = (getattr(message, "response_metadata", None) or {}).get("token_usage", {})
    return {
        "input_tokens": int(usage.get("input_tokens", response_usage.get("prompt_tokens", 0)) or 0),
        "output_tokens": int(usage.get("output_tokens", response_usage.get("completion_tokens", 0)) or 0),
        "total_tokens": int(usage.get("total_tokens", response_usage.get("total_tokens", 0)) or 0),
    }


def extract_text(message) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return str(content)


def validate_ranking(raw_text: str, expected_candidate_ids: set[str]) -> list[dict]:
    text = raw_text.strip()
    # Accept a fenced JSON object from the model while logging the unmodified raw response.
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    obj = json.loads(text)
    ranking = obj.get("ranking")
    if not isinstance(ranking, list):
        raise ValueError("JSON must contain ranking array")
    ids = [item.get("candidate_id") for item in ranking]
    if len(ids) != 10 or set(ids) != expected_candidate_ids or len(set(ids)) != 10:
        raise ValueError("ranking must include C01-C10 exactly once")
    for item in ranking:
        score = item.get("relevance_score")
        if not isinstance(score, (int, float)) or not 0 <= score <= 100:
            raise ValueError(f"invalid relevance_score for {item['candidate_id']}")
    scores = [item["relevance_score"] for item in ranking]
    if any(a < b for a, b in zip(scores, scores[1:])):
        raise ValueError("ranking must be sorted by descending relevance_score")
    return ranking


def atomic_write_json(path: Path, data: dict) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def write_csv(records: list[dict]) -> None:
    fields = [
        "question_id", "question", "expected_page_chunk", "acceptable_page_chunks",
        "vector_rank", "candidate_id", "source_candidate_id", "page_no", "chunk_id", "vector_distance",
        "vector_similarity", "reranker_score", "reason", "rerank_rank",
        "before_expected_rank", "after_expected_rank", "before_hit_at_5",
        "after_hit_at_5", "rank_change", "api_attempts", "retry_count",
        "api_input_tokens", "api_output_tokens", "api_total_tokens", "api_latency_seconds",
    ]
    with RESULTS_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for record in records:
            by_id = {item["source_candidate_id"]: item for item in record.get("reranked_top10", [])}
            for candidate in record["llm_input_candidates"]:
                source_id = candidate["source_candidate_id"]
                ranked = by_id.get(source_id, {})
                writer.writerow({
                    "question_id": record["question_id"], "question": record["question"],
                    "expected_page_chunk": record["expected_page_chunk"],
                    "acceptable_page_chunks": ";".join(record["acceptable_ids"]),
                    "vector_rank": candidate["vector_rank"], "candidate_id": candidate["candidate_id"],
                    "source_candidate_id": source_id,
                    "page_no": candidate["page_no"], "chunk_id": candidate["chunk_id"],
                    "vector_distance": f"{candidate['vector_distance']:.8f}",
                    "vector_similarity": f"{candidate['vector_similarity']:.8f}",
                    "reranker_score": ranked.get("relevance_score", ""), "reason": ranked.get("reason", ""),
                    "rerank_rank": ranked.get("rerank_rank", ""),
                    "before_expected_rank": record.get("before_expected_rank", ""),
                    "after_expected_rank": record.get("after_expected_rank", ""),
                    "before_hit_at_5": record.get("before_hit_at_5", ""),
                    "after_hit_at_5": record.get("after_hit_at_5", ""),
                    "rank_change": record.get("rank_change", ""),
                    "api_attempts": record.get("api_attempts", 0), "retry_count": record.get("retry_count", 0),
                    "api_input_tokens": record.get("api_input_tokens", 0),
                    "api_output_tokens": record.get("api_output_tokens", 0),
                    "api_total_tokens": record.get("api_total_tokens", 0),
                    "api_latency_seconds": record.get("api_latency_seconds", ""),
                })


def write_report(summary: dict) -> None:
    before, after = summary["before_metrics"], summary["after_metrics"]
    def hit(m, k):
        v = m[f"hit@{k}"]
        return f"{v['hits']}/{v['total']} ({v['rate']:.1%})"
    rows = []
    for r in summary["records"]:
        before_order = ", ".join(f"{x['vector_rank']}:{x['candidate_id']}" for x in r["vector_top10"])
        after_order = ", ".join(f"{x['rerank_rank']}:{x['candidate_id']}={x['source_candidate_id']}({x['relevance_score']})" for x in r.get("reranked_top10", []))
        rows.append(f"| {r['question_id']} | {r.get('before_expected_rank', '')} | {r.get('after_expected_rank', '')} | {r.get('rank_change', '오류')} | {before_order} | {after_order} |")
    report = f"""# Sonata M6 LLM Reranking 평가

## 지표

| 지표 | Vector Before | LLM Rerank After |
|---|---:|---:|
| Hit@1 | {hit(before, 1)} | {hit(after, 1)} |
| Hit@3 | {hit(before, 3)} | {hit(after, 3)} |
| Hit@5 | {hit(before, 5)} | {hit(after, 5)} |
| Hit@10 | {hit(before, 10)} | {hit(after, 10)} |
| MRR@5 | {before['mrr@5']:.4f} | {after['mrr@5']:.4f} |
| MRR@10 | {before['mrr@10']:.4f} | {after['mrr@10']:.4f} |

## 실험 조건

- 기존 M6 공식 CSV에서 11개 질문과 expected/acceptable page/chunk를 읽었다. 신규 질문·정답은 없다.
- 질문 embedding 및 Vector Top-10 후보는 기존 `CarManualSearchService.search_manual()`와 `search_car_manual` SELECT 결과를 그대로 사용했다. 결과 후보의 집합과 본문을 바꾸지 않고, 질문마다 후보 10개를 한 번의 text-only LLM 요청으로 보냈다.
- LLM: `{summary['model']}`. 요청 수 {summary['api_request_count']}회, API 오류 {summary['api_error_count']}회, 재시도 {summary['retry_count']}회. 총 input/output/total tokens: {summary['input_tokens_total']}/{summary['output_tokens_total']}/{summary['total_tokens_total']}.
- 전체 경과시간(기존 query embedding + SELECT + LLM 포함): {summary['total_elapsed_seconds']:.2f}s. 질문당 평균 전체시간 {summary['mean_elapsed_seconds_per_question']:.2f}s. LLM 요청시간 합계 {summary['api_latency_seconds_total']:.2f}s, 질문당 평균 API latency {summary['mean_api_latency_seconds']:.2f}s.
- 검색 대상은 existing Sonata 2026 filter이며 DB 접근은 SELECT 전용이었다. image URL/bytes와 image_desc는 LLM 입력에 포함하지 않았다. production 및 Streamlit 경로는 변경하지 않았다.
- baseline에서 expected 근거는 11/11 Top-10 안에 있다. 따라서 이 실험은 후보 recall이 아니라 후보 내 순위만 비교한다. MRR/Hit 판정은 기존 공식 평가의 acceptable adjacent evidence 정의를 따른다.

## 질문별 근거 순위

| ID | Before rank | After rank | 변화 | Before Vector Top-10 | After LLM Top-10 |
|---|---:|---:|---|---|---|
{"\n".join(rows)}

## M6-05 / M6-11

- M6-05: {next((r.get('before_expected_rank') for r in summary['records'] if r['question_id']=='M6-05'), '')} → {next((r.get('after_expected_rank') for r in summary['records'] if r['question_id']=='M6-05'), '')}
- M6-11: {next((r.get('before_expected_rank') for r in summary['records'] if r['question_id']=='M6-11'), '')} → {next((r.get('after_expected_rank') for r in summary['records'] if r['question_id']=='M6-11'), '')}

모델의 원문 응답, 프롬프트에 전달한 후보 전체, 각 후보 점수/짧은 reason, 순위 및 사용량은 JSON에 보존했다. 후보별 거리·유사도·점수는 CSV에도 있다.

## 해석

현재 11개 질문은 이미 개발·평가 과정에서 사용됐다. 이 결과로 unseen 질문에 대한 일반화 성능은 보장되지 않는다. 단일 11문항의 점수만으로 production 적용을 결론내리지 않는다.
"""
    EVALUATION_MD.write_text(report, encoding="utf-8")


def main() -> None:
    existing = [path for path in (RESULTS_JSON, RESULTS_CSV, EVALUATION_MD) if path.exists()]
    if existing:
        raise FileExistsError(f"Refusing to overwrite this run's existing outputs: {existing}")
    load_dotenv()
    questions = load_questions()
    sql_session = SqlSession(sql_log_mode="none")
    search_service = CarManualSearchService(sql_session)
    # Keep this experiment's candidate source vector-only even when production
    # reranking is enabled by the service's default feature flag.
    search_service.reranking_enabled = False
    # Preserve the exact embedding model while using bounded, observable
    # timeouts in this standalone experiment.
    search_service.embedding_model = OpenAIEmbeddings(
        model="text-embedding-3-small", request_timeout=45, max_retries=0,
    )

    started_all = perf_counter()
    retrieval_started = perf_counter()
    records = []
    print(f"Retrieving unchanged Vector Top-{TOP_K} candidates for {len(questions)} M6 questions...", flush=True)
    for question in questions:
        rows = search_service.search_manual("hyundai", "sonata", 2026, question["question"], limit=TOP_K)
        if len(rows) != TOP_K:
            raise RuntimeError(f"{question['question_id']}: expected 10 Vector candidates, got {len(rows)}")
        vector_top10 = []
        for rank, row in enumerate(rows, 1):
            similarity = float(row["similarity"])
            vector_top10.append({
                "candidate_id": canonical_id(row), "page_no": int(row["carManualChunkPageNo"]),
                "chunk_id": int(row["carManualChunkNo"]), "text": row["carManualChunkTxt"],
                "vector_rank": rank, "vector_similarity": similarity,
                "vector_distance": 1.0 - similarity,
            })
        acceptable_ids = {f"p{x['page']}/c{x['chunk']}" for x in question["acceptable"]}
        before_rank = find_rank(vector_top10, acceptable_ids)
        if before_rank is None:
            raise RuntimeError(f"{question['question_id']}: expected evidence missing from retrieved Top-10")
        llm_candidates = [
            {
                **candidate,
                "source_candidate_id": candidate["candidate_id"],
                "candidate_id": f"C{i:02d}",
            }
            for i, candidate in enumerate(vector_top10, 1)
        ]
        llm_input = {
            "question": question["question"],
            "candidates": [{
                "candidate_id": c["candidate_id"], "page_no": c["page_no"],
                "chunk_id": c["chunk_id"], "text": c["text"],
            } for c in llm_candidates],
        }
        records.append({
            **question,
            "expected_page_chunks": [f"p{x['page']}/c{x['chunk']}" for x in question["acceptable"]],
            "acceptable_ids": sorted(acceptable_ids), "vector_top10": vector_top10,
            "before_expected_rank": before_rank, "before_hit_at_5": before_rank <= 5,
            "llm_input": llm_input, "llm_input_candidates": llm_candidates,
            "raw_responses": [], "api_attempts": 0, "retry_count": 0,
            "api_input_tokens": 0, "api_output_tokens": 0, "api_total_tokens": 0,
            "api_latency_seconds": 0.0, "api_errors": [],
        })
        print(f"Retrieved {question['question_id']} Top-{TOP_K}; expected rank {before_rank}.", flush=True)
    retrieval_seconds = perf_counter() - retrieval_started

    # Keep ChatOpenAI use consistent with the existing project; no temperature,
    # max_tokens, custom client, or image content. LLM is asked for JSON only.
    model = ChatOpenAI(
        model=MODEL,
        max_completion_tokens=1800,
        timeout=90,
        max_retries=0,
    ).bind(response_format={"type": "json_object"})

    all_api_start = perf_counter()
    for record in records:
        valid_ranking = None
        last_error = None
        for attempt in range(MAX_RETRIES + 1):
            record["api_attempts"] += 1
            call_started = perf_counter()
            try:
                message = model.invoke([
                    ("system", SYSTEM_PROMPT),
                    ("human", json.dumps(record["llm_input"], ensure_ascii=False)),
                ])
                latency = perf_counter() - call_started
                record["api_latency_seconds"] += latency
                usage = token_usage(message)
                record["api_input_tokens"] += usage["input_tokens"]
                record["api_output_tokens"] += usage["output_tokens"]
                record["api_total_tokens"] += usage["total_tokens"]
                raw = extract_text(message)
                record["raw_responses"].append({
                    "attempt": attempt + 1, "raw_response": raw, "latency_seconds": latency,
                    **usage,
                })
                valid_ranking = validate_ranking(raw, {f"C{i:02d}" for i in range(1, 11)})
                break
            except Exception as exc:
                latency = perf_counter() - call_started
                record["api_latency_seconds"] += latency
                response = getattr(exc, "response", None)
                body = getattr(exc, "body", None)
                response_text = None
                if response is not None:
                    try:
                        response_text = response.text
                    except Exception:
                        response_text = None
                is_validation_error = isinstance(exc, (json.JSONDecodeError, ValueError))
                detail = {
                    "attempt": attempt + 1,
                    "category": "json_validation" if is_validation_error else "api_error",
                    "exception_class": type(exc).__name__,
                    "http_status": getattr(exc, "status_code", None),
                    "openai_error_type": body.get("type") if isinstance(body, dict) else None,
                    "openai_error_code": body.get("code") if isinstance(body, dict) else getattr(exc, "code", None),
                    "message": str(exc),
                    "raw_response": response_text if response_text is not None else body,
                    "validation_error": str(exc) if is_validation_error else None,
                    "latency_seconds": latency,
                }
                last_error = f"{detail['exception_class']}: {detail['message']}"
                record["api_errors"].append(detail)
                if attempt < MAX_RETRIES:
                    record["retry_count"] += 1
                    time.sleep(min(2 ** attempt, 4))
        if valid_ranking is None:
            record["final_error"] = last_error or "unknown error"
            print(f"LLM failed for {record['question_id']} after {record['api_attempts']} attempts.", flush=True)
            continue
        by_id = {candidate["candidate_id"]: candidate for candidate in record["llm_input_candidates"]}
        reranked = []
        for rank, item in enumerate(valid_ranking, 1):
            # Preserve the exact original candidate record/text; only attach model score/reason/rank.
            source_candidate = by_id[item["candidate_id"]]
            reranked.append({
                **source_candidate,
                "candidate_id": item["candidate_id"],
                "relevance_score": item["relevance_score"],
                "reason": str(item.get("reason", ""))[:240], "rerank_rank": rank,
            })
        record["reranked_top10"] = reranked
        record["after_expected_rank"] = find_rank(reranked, set(record["acceptable_ids"]))
        rank_before, rank_after = record["before_expected_rank"], record["after_expected_rank"]
        record["after_hit_at_5"] = rank_after is not None and rank_after <= 5
        record["rank_change"] = "상승" if rank_after is not None and rank_after < rank_before else "하락" if rank_after is None or rank_after > rank_before else "유지"
        print(f"Reranked {record['question_id']}: {rank_before} -> {rank_after}.", flush=True)
    api_wall_seconds = perf_counter() - all_api_start
    total_elapsed = perf_counter() - started_all

    complete = [r for r in records if "reranked_top10" in r]
    if len(complete) != len(records):
        before_metrics = calculate_metrics(records, "before_expected_rank")
        # Failed questions count as missed at all after cutoffs.
        for r in records:
            if "after_expected_rank" not in r:
                r["after_expected_rank"] = None
        after_metrics = calculate_metrics(records, "after_expected_rank")
    else:
        before_metrics = calculate_metrics(records, "before_expected_rank")
        after_metrics = calculate_metrics(records, "after_expected_rank")

    summary = {
        "experiment": "LLM reranking of the fixed existing M6 vector Top-10; evaluation only",
        "model": MODEL, "method": "one text-only Chat Completions request per question; JSON ranking",
        "question_count": len(records), "candidate_count_per_question": TOP_K,
        "external_api": True, "image_content_sent": False,
        "api_request_count": sum(r["api_attempts"] for r in records),
        "api_error_count": sum(e["category"] == "api_error" for r in records for e in r["api_errors"]),
        "validation_error_count": sum(e["category"] == "json_validation" for r in records for e in r["api_errors"]),
        "retry_count": sum(r["retry_count"] for r in records),
        "input_tokens_total": sum(r["api_input_tokens"] for r in records),
        "output_tokens_total": sum(r["api_output_tokens"] for r in records),
        "total_tokens_total": sum(r["api_total_tokens"] for r in records),
        "api_latency_seconds_total": sum(r["api_latency_seconds"] for r in records),
        "api_wall_seconds": api_wall_seconds,
        "mean_api_latency_seconds": sum(r["api_latency_seconds"] for r in records) / len(records),
        "total_elapsed_seconds": total_elapsed,
        "mean_elapsed_seconds_per_question": total_elapsed / len(records),
        "retrieval_embedding_seconds": retrieval_seconds,
        "before_metrics": before_metrics, "after_metrics": after_metrics,
        "records": records,
        "runtime": {"python": platform.python_version(), "platform": platform.platform()},
    }
    atomic_write_json(RESULTS_JSON, summary)
    write_csv(records)
    write_report(summary)
    print(json.dumps({k: summary[k] for k in (
        "model", "api_request_count", "api_error_count", "validation_error_count", "retry_count",
        "input_tokens_total", "output_tokens_total", "total_tokens_total",
        "total_elapsed_seconds", "mean_elapsed_seconds_per_question",
        "before_metrics", "after_metrics",
    )}, ensure_ascii=False, indent=2))
    print(f"Wrote: {EVALUATION_MD}\nWrote: {RESULTS_CSV}\nWrote: {RESULTS_JSON}")


if __name__ == "__main__":
    main()
