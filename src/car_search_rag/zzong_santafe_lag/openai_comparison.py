"""동일한 30문항·청킹·검색 규칙에서 로컬/OpenAI 임베딩만 비교합니다."""

import argparse
from time import perf_counter

from .db_evaluation_service import DbRetrievalEvaluationService, score_candidates
from .openai_migration import SOURCE_RUN_ID, OUTPUT_FOLDER, load_plan, write_json, digest
from .openai_search_service import OpenAIManualSearchService, active_embedding_run


def compare(progress=print):
    """검색·출처 순위를 비교합니다. 답변 생성 API·DB 쓰기·그림 업로드는 하지 않습니다."""
    run_id = active_embedding_run()
    if run_id is None:
        raise ValueError("새 벡터 저장을 먼저 마무리하세요.")
    baseline = DbRetrievalEvaluationService(SOURCE_RUN_ID, method="purpose_specific")
    cases = baseline.prepare_cases()
    new_service = OpenAIManualSearchService(run_id)
    started = perf_counter()
    results = []
    plan, folder = load_plan()
    for index, case in enumerate(cases, start=1):
        row = {"case_id": case["case_id"], "question": case["question"]}
        for label, service in (("local", baseline.search_service), ("openai", new_service)):
            result = service.search(case["question"], top_k=5)
            scored = score_candidates(case, result, top_k=5)
            # [프로젝트 추가] 5개 후보 중 등록된 기대 ID가 포함된 후보 수를 5로 나눕니다.
            # PDF 110쪽 버클처럼 다른 유효한 근거가 정답 목록에 없으므로 완전한 관련성 Precision이 아닙니다.
            # 같은 고정 목록을 두 모델에 적용하고 보조값 이름으로 한계를 명시합니다.
            scored["Precision@5_expected_ids"] = sum(bool(hit["matched_expected_ids"]) for hit in scored["candidates"]) / 5
            row[label] = scored
        results.append(row)
        write_json(folder / "comparison_progress.json", {"completed": index, "total": len(cases),
                   "dataset_sha256": baseline.dataset_sha256, "results": results})
        if progress:
            progress(f"검색 비교 {index}/{len(cases)} | {case['case_id']} | 첫 기대 출처: "
                     f"로컬 {row['local']['first_relevant_rank']} / OpenAI {row['openai']['first_relevant_rank']}")
    metrics = {}
    for label in ("local", "openai"):
        metrics[label] = {
            "Hit@5": sum(row[label]["hit_at_k"] for row in results) / len(results),
            "MRR@5": sum(row[label]["reciprocal_rank_at_k"] for row in results) / len(results),
            "Precision@5_expected_ids": sum(row[label]["Precision@5_expected_ids"] for row in results) / len(results),
        }
    report = {"source_run_id": str(SOURCE_RUN_ID), "embedding_run_id": str(run_id),
              "dataset_sha256": baseline.dataset_sha256, "question_count": len(cases),
              "search_rule": "purpose_specific; same chunks, same TF-IDF/purpose/specific term rules",
              "metrics": metrics, "elapsed_seconds": perf_counter() - started,
              "openai_query_embedding_calls": len(cases), "generation_api_calls": 0,
              "db_written": False, "images_uploaded": False,
              "limitations": ["검색 개선에 재사용한 30문항이며 새 질문에 대한 독립 평가가 아닙니다.",
                  "Precision@5_expected_ids는 기존 정답 ID 목록 기준의 보조값입니다. 전체 관련성 검토 Precision@5는 미완료입니다.",
                  "한 후보는 부모 원문과 필수 각주 묶음이며, 그 안에 기대 ID가 있으면 일치로 셉니다.",
                  "높은 검색 점수는 답변 정확도·미검토 원문의 승인·그림 픽셀 이해를 보장하지 않습니다."],
              "results": results}
    write_json(folder / "comparison_result.json", report)
    write_json(OUTPUT_FOLDER / "comparison_summary.json", {key: value for key, value in report.items() if key != "results"})
    return report


def verify_answers(progress=print):
    """기존 10문항으로 출처·보류·그림 연결 조건을 확인합니다. 유료 답변 생성은 실행하지 않습니다."""
    from .answer_checks import case_manifest, inspect_answer
    from .answer_service import ManualAnswerService
    from .llm_answer_service import LlmManualAnswerService

    run_id = active_embedding_run()
    if run_id is None:
        raise ValueError("새 임베딩 저장을 먼저 완료하세요.")
    search_service = OpenAIManualSearchService(run_id)
    service = LlmManualAnswerService(SOURCE_RUN_ID,
        evidence_service=ManualAnswerService(SOURCE_RUN_ID, search_service=search_service),
        image_display_location="관련 그림 탭")
    cases, manifest = case_manifest()
    _, folder = load_plan()
    rows = []
    for index, case in enumerate(cases, start=1):
        evidence = service.prepare_evidence(case["question"], top_k=5)
        row = inspect_answer(case, evidence)
        preview = service.preview(evidence)
        row["generation_ready"] = preview["ready_for_generation"]
        # [프로젝트 추가] PDF 밖·미검토는 생성 준비도 False인지 확인합니다. 실제 generate는 호출하지 않습니다.
        expected_ready = case["expected_status"] == "evidence_excerpt"
        row["checks"]["generation_gate"] = row["generation_ready"] == expected_ready
        row["failed_checks"] = [key for key, passed in row["checks"].items() if not passed]
        row["expectation_checks_passed"] = not row["failed_checks"]
        rows.append(row)
        write_json(folder / "answer_checks_progress.json", {"completed": index, "total": len(cases), "results": rows})
        if progress:
            progress(f"근거·보류 확인 {index}/{len(cases)} | {case['case_id']} | 조건 일치: {row['expectation_checks_passed']}")
    report = {"question_count": len(cases), "question_manifest_sha256": manifest,
              "embedding_run_id": str(run_id), "expectation_match_count": sum(row["expectation_checks_passed"] for row in rows),
              "generation_api_calls": 0, "db_written": False, "storage_uploaded": False,
              "limitation": "기존 고정 조건의 회귀 확인이며 생성 답변 정확도·그림 픽셀 의미 판정이 아닙니다.", "results": rows}
    write_json(folder / "answer_checks_result.json", report)
    return report


def record_post_upload_checks():
    """이미 저장한 동일 답변을 업로드 완료 후의 별도 기대 조건으로 다시 채점합니다. API 호출은 없습니다."""
    import json
    from .answer_checks import case_manifest, inspect_answer
    from .config import ManualConfig

    _, folder = load_plan()
    original = json.loads((folder / "answer_checks_result.json").read_text(encoding="utf-8"))
    upload = json.loads((ManualConfig().project_folder /
        "data/zzong_santafe_lag/reports/full_images_upload_summary_20261003.json").read_text(encoding="utf-8"))["result"]
    if upload["verified_public_images"] != 864 or upload["failure_count"] != 0:
        raise ValueError("기대 조건 변경 근거인 기존 전체 업로드 완료 보고서를 확인하세요.")
    cases, original_manifest = case_manifest()
    case = next(row for row in cases if row["case_id"] == "A10")
    # [프로젝트 추가] 기존 A10은 그림 미업로드 시점의 조건입니다. 10월 3일 완료 보고서에 맞춘 새 평가 버전을 만듭니다.
    # 기존 결과·질문 목록은 그대로 보관하며 새 버전의 변경 항목과 이유를 명시합니다.
    case.pop("pending_image_pages")
    case["display_image_pages"] = [33]
    case["min_display_images"] = 1
    rows = []
    by_id = {row["case_id"]: row for row in original["results"]}
    for case in cases:
        previous = by_id[case["case_id"]]
        row = inspect_answer(case, previous["answer"])
        row["generation_ready"] = previous["generation_ready"]
        row["checks"]["generation_gate"] = previous["checks"]["generation_gate"]
        row["failed_checks"] = [key for key, passed in row["checks"].items() if not passed]
        row["expectation_checks_passed"] = not row["failed_checks"]
        rows.append(row)
    report = {"question_count": len(rows), "original_question_manifest_sha256": original_manifest,
              "question_manifest_sha256": digest(cases), "evaluation_version": "post_full_image_upload_v2",
              "expectation_match_count": sum(row["expectation_checks_passed"] for row in rows),
              "original_expectation_match_count": original["expectation_match_count"],
              "changed_cases": ["A10"], "change_reason": "PDF 33쪽 그림이 2026-10-03 전체 업로드 완료되어 표시 가능 조건을 적용",
              "same_saved_answers_rescored": True, "new_api_calls": 0, "db_written": False,
              "limitation": original["limitation"], "results": rows}
    write_json(folder / "answer_checks_post_upload_result.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OpenAI 전환 검색·근거 연결 확인")
    parser.add_argument("action", choices=["compare", "answers", "post_upload_checks"], nargs="?", default="compare")
    action = parser.parse_args().action
    try:
        actions = {"compare": compare, "answers": verify_answers, "post_upload_checks": record_post_upload_checks}
        report = actions[action]()
        print(report.get("metrics", {"expectation_match_count": report.get("expectation_match_count")}))
    except Exception as error:
        print(f"비교 중단: {type(error).__name__}. 완료 표시를 하지 않고 기존 결과를 유지합니다.")
        raise SystemExit(1) from None
