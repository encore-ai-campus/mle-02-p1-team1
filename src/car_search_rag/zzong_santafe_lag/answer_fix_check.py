"""저장 검색을 재사용해 승인받은 답변 선택·생성 검사 보완을 비교합니다."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .answer_service import ManualAnswerService, citation_requirements
from .answer_checks import case_manifest, inspect_answer
from .fresh_evaluation import current_plan, pool_key
from .llm_answer_service import LlmManualAnswerService
from .openai_migration import SOURCE_RUN_ID, digest, write_json, load_plan
from .openai_search_service import OpenAIManualSearchService


def inputs():
    """기존 고정 질문과 검색 전문을 읽습니다. 검색·DB·API를 다시 실행하지 않습니다."""
    plan, folder = current_plan()
    searches = json.loads((folder / "retrieval.json").read_text(encoding="utf-8"))
    if not searches["complete"] or searches["failures"]:
        raise ValueError("완료된 동일 검색 결과가 필요합니다.")
    return plan, folder, searches


def code_version():
    """답변 선택·프롬프트·검사 코드의 현재 식별값을 남깁니다. 모델 서버 버전은 아닙니다."""
    root = Path(__file__).resolve().parent
    return {name: digest((root / name).read_text(encoding="utf-8"))
            for name in ("answer_service.py", "llm_answer_service.py")}


def replay():
    """같은 20개 검색 결과에서 선택만 다시 확인하고 직접 근거 판정과 비교합니다."""
    plan, folder, searches = inputs()
    labels = json.loads((folder / "relevance_labels.json").read_text(encoding="utf-8"))["labels"]
    rows = []
    for row in searches["results"]:
        after = ManualAnswerService.from_search_result(row["search"])
        chosen = next((c for c in row["search"]["candidates"]
                       if c["matched_chunk_record_id"] == after.get("matched_chunk_record_id")), None)
        relevant = labels[pool_key(row["case_id"], chosen)]["relevant"] if chosen else False
        rows.append({"case_id": row["case_id"], "backend": row["backend"],
                     "before": row["evidence"], "after": after, "selected_has_direct_support": relevant})
    report = {"dataset_sha256": plan["dataset_sha256"], "code_version": code_version(), "results": rows,
              "human_confirmed": False, "db_written": False, "storage_uploaded": False,
              "new_query_embedding_calls": 0, "generation_calls": 0,
              "limitation": "원래 검색 후보·순위를 재사용한 근거 선택 비교입니다. 새 검색 성능 점수가 아닙니다."}
    # [프로젝트 추가] 코드가 바뀌면 파일명도 달라져 수정 전후 비교를 덮어쓰지 않습니다.
    path = folder / ("answer_selection_" + digest(report["code_version"])[:12] + ".json")
    write_json(path, report)
    return {"path": str(path), "direct_support": {backend: sum(
        r["selected_has_direct_support"] for r in rows if r["backend"] == backend) for backend in ("local", "openai")}}


def generate(phase):
    """진단은 N05/N08, 최종 확인은 N01/N05/N08만 각 1회 생성하고 시작 기록을 보존합니다."""
    plan, folder, searches = inputs()
    cases = ("N05", "N08") if phase == "diagnose" else ("N01", "N05", "N08")
    path = folder / ("answer_fix_" + phase + ".json")
    report = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
        "dataset_sha256": plan["dataset_sha256"], "phase": phase, "results": [], "attempted_calls": 0,
        "db_written": False, "storage_uploaded": False, "new_query_embedding_calls": 0}
    service = LlmManualAnswerService(SOURCE_RUN_ID, image_display_location="관련 그림 탭")
    for case_id in cases:
        # [프로젝트 추가] 같은 단계의 시작 기록이 있으면 호출하지 않습니다. 실패 재시도도 명시적 새 단계가 필요합니다.
        if any(row["case_id"] == case_id for row in report["results"]):
            continue
        original = next(row for row in searches["results"] if row["backend"] == "openai" and row["case_id"] == case_id)
        evidence = ManualAnswerService.from_search_result(original["search"])
        pending = {"case_id": case_id, "state": "started", "code_version": code_version(),
                   "started_at": datetime.now(timezone.utc).isoformat(), "evidence": evidence,
                   "preview": service.preview(evidence)}
        report["results"].append(pending)
        write_json(path, report)
        answer = service.generate(evidence)
        pending.update(state="completed", answer=answer)
        report["attempted_calls"] += int(answer.get("llm_called", False))
        write_json(path, report)
        diagnostic = answer.get("generation_diagnostics", {})
        print(f"{phase} {case_id} | {answer['status']} | 검사: {diagnostic.get('code', '통과')} | "
              f"입력/출력 사용량: {answer.get('token_usage')}", flush=True)
    return {"path": str(path), "attempted_calls": report["attempted_calls"]}


def regression():
    """기존 업로드 후 10문항 조건을 유지한 새 실행을 별도 보관합니다. 생성 API는 호출하지 않습니다."""
    plan, folder, _ = inputs()
    _, migration_folder = load_plan()
    before = json.loads((migration_folder / "answer_checks_post_upload_result.json").read_text(encoding="utf-8"))
    cases, _ = case_manifest()
    for case in cases:
        if case["case_id"] == "A10":
            # 업로드 완료 뒤 이미 고정한 v2 조건을 그대로 재사용합니다. 이번 결과에 맞춰 기대를 바꾸지 않습니다.
            case.pop("pending_image_pages")
            case.update(display_image_pages=[33], min_display_images=1)
    if digest(cases) != before["question_manifest_sha256"]:
        raise ValueError("이전 업로드 후 조건과 다른 평가입니다.")
    path = folder / ("answer_fix_regression_" + digest(code_version())[:12] + ".json")
    report = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
        "question_manifest_sha256": digest(cases), "code_version": code_version(), "results": [],
        "complete": False, "query_embedding_calls": 0, "generation_calls": 0, "db_written": False, "storage_uploaded": False}
    service = LlmManualAnswerService(SOURCE_RUN_ID, evidence_service=ManualAnswerService(SOURCE_RUN_ID,
        search_service=OpenAIManualSearchService(plan["embedding_run_id"])), image_display_location="관련 그림 탭")
    for case in cases:
        if any(row["case_id"] == case["case_id"] for row in report["results"]):
            continue
        evidence = service.prepare_evidence(case["question"], top_k=5)
        row = inspect_answer(case, evidence)
        row["checks"]["generation_gate"] = service.preview(evidence)["ready_for_generation"] == (case["expected_status"] == "evidence_excerpt")
        row["failed_checks"] = [name for name, passed in row["checks"].items() if not passed]
        row["expectation_checks_passed"] = not row["failed_checks"]
        report["results"].append(row)
        # 복합 요청은 각 항목의 질문 임베딩을 별도 호출합니다. PDF 밖 2문항은 검색하지 않습니다.
        report["query_embedding_calls"] += len(evidence.get("subquestions", [case["question"]])) if evidence.get("retrieval_performed") else 0
        write_json(path, report)
        print(f"기존 조건 {case['case_id']} | 일치: {row['expectation_checks_passed']} | 실패 항목: {row['failed_checks']}", flush=True)
    report.update(complete=True, expectation_match_count=sum(r["expectation_checks_passed"] for r in report["results"]))
    write_json(path, report)
    return {"path": str(path), "expectation_match_count": report["expectation_match_count"],
            "query_embedding_calls": report["query_embedding_calls"]}


def policy_inspection():
    """저장 표의 각주 필수 조건과 출처 검사를 직접 확인합니다. 새 검색·API 호출은 없습니다."""
    _, folder, searches = inputs()
    original = next(r for r in searches["results"] if r["case_id"] == "N08" and r["backend"] == "openai")
    candidate = original["search"]["candidates"][0]
    checks = []
    for question, required in (("연료 용량", False), ("엔진 오일 용량", True), ("브레이크액 용량", True),
                               ("전체 표의 용량", True), ("연료 사용 주의사항", True), ("연료와 엔진 오일 용량", True)):
        actual = citation_requirements(question, candidate)
        primary = candidate["parent_record_id"]
        auxiliary = [x["required"] for key, x in actual.items() if key != primary]
        checks.append({"question": question, "check": "표 항목·필수 각주 유지", "passed": bool(auxiliary) and all(x == required for x in auxiliary),
                       "actual": actual, "scope": "같은 저장 표로 인용 규칙만 확인. 이 질문의 새 검색은 실행하지 않음"})
    # [프로젝트 추가] 불필요한 참고 인용만 선택으로 바꿨는지 확인합니다. 없는 출처·필수 각주 누락은 여전히 차단합니다.
    from .llm_answer_service import AnswerValidationError
    from copy import deepcopy
    evidence = ManualAnswerService.from_search_result(original["search"])
    text = json.dumps({"items": [{"text": "연료 67 ℓ, 무연 휘발유", "citation_ids": [1]}], "unanswered": []}, ensure_ascii=False)
    LlmManualAnswerService.parse_items(text, evidence["sources"])
    checks.append({"check": "선택적 참고 출처를 인용하지 않은 연료 문장 허용", "passed": True})
    legacy = deepcopy(evidence["sources"])
    for source in legacy:
        source.pop("citation_required", None)
    for name, output, sources, expected_code in (
            ("필수 여부 없는 기존 근거는 모두 필수", text, legacy, "missing_required_citation"),
            ("전달하지 않은 출처 차단", text.replace('"citation_ids": [1]', '"citation_ids": [999]'), evidence["sources"], "unknown_citation")):
        try:
            LlmManualAnswerService.parse_items(output, sources)
            actual = "허용됨"
        except AnswerValidationError as error:
            actual = error.diagnostic["code"]
        checks.append({"check": name, "passed": actual == expected_code, "actual": actual})
    report = {"checks": checks, "all_passed": all(c["passed"] for c in checks), "code_version": code_version(),
              "query_embedding_calls": 0, "generation_calls": 0, "db_written": False}
    path = folder / ("answer_fix_policy_" + digest(code_version())[:12] + ".json")
    write_json(path, report)
    return {"path": str(path), "all_passed": report["all_passed"], "check_count": len(checks)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="승인한 답변 선택·검사 보완의 저장 자료 비교")
    parser.add_argument("action", choices=("replay", "diagnose", "final", "regression", "policy"))
    action = parser.parse_args().action
    try:
        result = {"replay": replay, "regression": regression, "policy": policy_inspection}.get(action)
        result = result() if result else generate(action)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as error:
        print(f"확인 중단: {type(error).__name__}. 외부 오류 문장은 저장하거나 출력하지 않습니다.", flush=True)
        raise SystemExit(1) from None
