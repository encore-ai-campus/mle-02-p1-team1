"""M7: 같은 DB 자료·질문 벡터로 구체 표현 점수의 적용 전후를 비교합니다."""

# [프로젝트 적용] 기존 SQL Mapper로 개인 전체 작업만 읽고 저장된 문서 벡터를 재사용합니다.
# [프로젝트 추가] 속도 비교가 아닌 순위 비교입니다. DB 자료를 한 번 읽어 메모리에서 두 방식을 비교합니다.
# 기본 서비스처럼 제목만 있는 기록을 제외하고 각주 묶음을 중복 제거합니다.
# 새 모델·청킹·정답 ID·DB 자료·그림 업로드를 변경하지 않습니다.

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter

import numpy as np

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from car_search_rag.zzong_santafe_lag.db_evaluation_service import DbRetrievalEvaluationService, score_candidates
from car_search_rag.zzong_santafe_lag.db_search_service import DbFullSearchService
from car_search_rag.zzong_santafe_lag.retrieval import SearchEngine
from car_search_rag.zzong_santafe_lag.specific_terms import SPECIFIC_BONUS_WEIGHT


def snapshot_candidates(engine, question, vector, parents, use_specific_terms):
    """DB 검색과 같은 원문·각주 묶음 중복 제거 후 상위 다섯 후보를 만듭니다."""
    ranked = engine.rank(question, vector, top_k=len(engine.parents), use_specific_terms=use_specific_terms)
    candidates, identities = [], set()
    for hit in ranked:
        record_id = hit["parent_record"]["metadata"]["record_id"]
        context = DbFullSearchService.read_context(record_id, parents)
        identity = tuple(sorted(row["record_id"] for row in context))
        if identity in identities:
            continue
        identities.add(identity)
        candidates.append({
            "title": hit["parent_record"]["metadata"]["title"], "parent_record_id": record_id,
            "context_records": context,
            "pending_review_record_ids": [row["record_id"] for row in context
                                          if row["verification_status"] == "auto_draft_needs_review"],
            "ranking_score": hit["score"], "specific_bonus": hit["specific_bonus"],
            "specific_terms": hit["specific_terms"],
        })
        if len(candidates) == 5:
            break
    return {"question": question, "candidates": candidates}


def run_comparison(run_id, progress=print):
    """읽기 전용 DB의 같은 자료로 기존 30문항을 비교하고 결과를 반환합니다."""
    started = perf_counter()
    evaluator = DbRetrievalEvaluationService(run_id)
    cases = evaluator.prepare_cases()
    service = evaluator.search_service.prepare(progress=progress)
    with service.repository.session.transaction():
        params = {"run_id": service.run_id}
        rows = service.repository.session.select_list("manual_store.get_run_parents", params)
        chunks = service.repository.session.select_list("manual_store.get_run_chunks", params)
    usable = [row for row in rows if re.sub(r"\s+", "", row["content"]) != re.sub(r"\s+", "", row["title"])]
    usable_ids = {row["record_id"] for row in usable}
    chunks = [row for row in chunks if row["metadata"]["parent_record_id"] in usable_ids]
    parents = [{"content": row["content"], "raw_text": row["raw_text"],
                "metadata": row["metadata"], "image_parts": []} for row in usable]
    records = [{"content": row["content"], "metadata": row["metadata"]} for row in chunks]
    vectors = np.stack([row["embedding"] for row in chunks]).astype(np.float32)
    if vectors.shape != (len(chunks), 768) or not np.isfinite(vectors).all():
        raise ValueError("저장된 벡터의 개수·숫자를 확인하세요.")
    # [프로젝트 추가] 같은 자료에서 비교했다는 식별값만 남기고 벡터 전체는 파일에 저장하지 않습니다.
    digest = hashlib.sha256()
    digest.update(json.dumps([(row["record_id"], row["content_sha256"]) for row in chunks], separators=(",", ":")).encode())
    digest.update(vectors.tobytes())
    engine = SearchEngine(parents, records, vectors, service.embedder.model, service.token_counter)
    by_id = {row["record_id"]: row for row in rows}
    results = {"before": [], "after": []}
    for index, case in enumerate(cases, start=1):
        if progress:
            progress(f"{index}/{len(cases)} | {case['case_id']} | {case['question']}", flush=True)
        # 두 방식에 같은 질문 벡터를 전달하며 문서 벡터를 다시 계산하지 않습니다.
        vector = service.embedder.embed_question(case["question"])
        for name, use_specific in (("before", False), ("after", True)):
            result = snapshot_candidates(engine, case["question"], vector, by_id, use_specific)
            scored = score_candidates(case, result, top_k=5)
            for output, hit in zip(scored["candidates"], result["candidates"]):
                output.update({key: hit[key] for key in ("ranking_score", "specific_bonus", "specific_terms")})
            results[name].append(scored)
        if progress:
            progress(f"  기대 근거 첫 순위: {results['before'][-1]['first_relevant_rank']} → {results['after'][-1]['first_relevant_rank']}", flush=True)
    metrics = {}
    for name, answers in results.items():
        metrics[name] = {
            "Hit@5": sum(row["hit_at_k"] for row in answers) / len(answers),
            "MRR@5": sum(row["reciprocal_rank_at_k"] for row in answers) / len(answers),
            "top1_count": sum(row["first_relevant_rank"] == 1 for row in answers),
        }
    changes = [{"case_id": before["case_id"], "question": before["question"],
                "before_rank": before["first_relevant_rank"], "after_rank": after["first_relevant_rank"]}
               for before, after in zip(results["before"], results["after"])
               if before["first_relevant_rank"] != after["first_relevant_rank"]]
    return {
        "phase": "completed", "created_at": datetime.now(timezone(timedelta(hours=9))).isoformat(),
        "run_id": str(service.run_id), "dataset_sha256": evaluator.dataset_sha256,
        "corpus_vector_sha256": digest.hexdigest(), "question_count": len(cases), "top_k": 5,
        "model_name": service.embedder.model_name, "model_revision": service.embedder.model_revision,
        "change": "rare_query_expression_bonus", "specific_bonus_weight": SPECIFIC_BONUS_WEIGHT,
        "excluded_heading_records": len(rows) - len(usable), "metrics": metrics,
        "changed_questions": changes, "results": results,
        "before_matches_user_reported_ranks": [row["first_relevant_rank"] for row in results["before"]]
            == [3 if index in (16, 17) else 4 if index == 19 else 1 for index in range(1, 31)],
        "db_written": False, "storage_uploaded": False, "document_embeddings_recomputed": False,
        "elapsed_seconds": perf_counter() - started,
        "limitations": ["기존 개선에 사용한 30문항이며 독립된 새 질문 평가가 아닙니다.",
                       "DB 자료를 한 번 읽어 순위를 비교하며 실제 DB 검색 시간을 측정하지 않습니다.",
                       "MRR@5·근거 검색 평가이며 답변·이미지 이해 정확도를 측정하지 않습니다."],
    }


def main():
    """실행 번호를 받아 비교하고 개인 reports 폴더에 결과만 저장합니다."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="M7 검색 순위 변경 전후 비교")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    folder = Path(__file__).resolve().parents[3] / "data/zzong_santafe_lag/reports"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone(timedelta(hours=9))).strftime("%Y%m%d_%H%M%S")
    status_path = folder / f"m7_specific_terms_{stamp}.json"
    status_path.write_text(json.dumps({"phase": "running", "pid": os.getpid(), "run_id": args.run_id}, indent=2), encoding="utf-8")
    print(f"PID: {os.getpid()} | 진행·결과 기록: {status_path}", flush=True)
    try:
        result = run_comparison(args.run_id)
    except Exception as error:
        # DB 비밀번호 등이 섞일 수 있는 전체 예외 메시지는 저장·출력하지 않습니다.
        status_path.write_text(json.dumps({"phase": "failed", "error_type": type(error).__name__}, indent=2), encoding="utf-8")
        print(f"평가 중단: {type(error).__name__}. 개인 연결·기록을 확인하세요.", flush=True)
        return 1
    status_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"metrics": result["metrics"], "changed_questions": result["changed_questions"],
                      "result_path": str(status_path)}, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
