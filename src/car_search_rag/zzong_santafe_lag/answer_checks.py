"""새 표현·복합 질문·자료 범위·그림 요청의 사전 기대 조건을 확인합니다."""

# [프로젝트 적용] 기존 ManualAnswerService와 같은 개인 DB·로컬 임베딩 모델을 사용합니다.
# [프로젝트 추가] 실행 전에 고정한 10문항의 상태·출처·문구·그림 연결을 비교합니다.
# 이번 질문은 30문항과 표현이 다르지만 기존에 살펴본 주제가 포함되어 있습니다.
# 자동 조건 일치는 사람의 답변 정확도 판정이나 독립적인 전체 성능 지표가 아닙니다.

import argparse
import hashlib
import json
import os
import re
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from car_search_rag.zzong_santafe_lag.answer_service import ManualAnswerService


# [프로젝트 추가] 기대 페이지는 검사할 때만 사용하며 검색·답변 선택에 전달하지 않습니다.
# 한 페이지 그룹은 대체 가능한 출처이고, 그룹이 여러 개면 각 그룹의 근거가 모두 필요합니다.
ANSWER_CASES = [
    {"case_id": "A01", "group": "표현 바꾸기", "question": "차대번호 찍힌 곳 어디야?",
     "expected_status": "evidence_excerpt", "required_page_groups": [[45]],
     "required_text_groups": [["엔진"], ["차체 패널"]]},
    {"case_id": "A02", "group": "표현 바꾸기", "question": "0W-20 표에 있는 온도 눈금은 몇 도부터 몇 도까지야?",
     "expected_status": "evidence_excerpt", "required_page_groups": [[44]],
     "required_text_groups": [["0W-20"], ["-30"], ["50"]]},
    {"case_id": "A03", "group": "표현 바꾸기", "question": "안전벨트 버클은 어느 정도까지 밀어 넣어?",
     "expected_status": "evidence_excerpt", "required_page_groups": [[54, 110]],
     "required_text_groups": [["찰칵"]]},
    {"case_id": "A04", "group": "복합 질문", "question": "엔진 오일 교체 시 주입량과 SAE 점도 표의 온도 눈금을 함께 알려줘.",
     "expected_status": "evidence_excerpt", "required_page_groups": [[43], [44]],
     "required_text_groups": [["4.8"], ["0W-20"], ["-30"], ["50"]]},
    {"case_id": "A05", "group": "복합 질문", "question": "차대번호 위치와 실외 미러 접이 버튼 위치를 함께 알려줘.",
     "expected_status": "evidence_excerpt", "required_page_groups": [[45], [33]],
     "required_text_groups": [["차대번호"], ["실외 미러 접이 버튼"]]},
    {"case_id": "A06", "group": "PDF 밖 질문", "question": "지금 내 차가 리콜 대상이야?",
     "expected_status": "outside_pdf_scope", "no_retrieval_expected": True},
    {"case_id": "A07", "group": "PDF 밖 질문", "question": "내 차 엔진 경고등이 켜졌는데 실제 고장이 난 거야?",
     "expected_status": "outside_pdf_scope", "no_retrieval_expected": True},
    {"case_id": "A08", "group": "미검토 자료", "question": "스마트 테일게이트 설정 방법을 설명해줘.",
     "expected_status": "needs_review"},
    {"case_id": "A09", "group": "그림 요청", "question": "차대번호가 새겨진 위치를 그림으로 보여줘.",
     "expected_status": "evidence_excerpt", "required_page_groups": [[45]],
     "required_text_groups": [["차대번호"]], "display_image_pages": [45], "min_display_images": 1},
    {"case_id": "A10", "group": "그림 요청", "question": "실외 미러 접이 버튼 위치를 그림으로 보여줘.",
     "expected_status": "evidence_excerpt", "required_page_groups": [[33]],
     "required_text_groups": [["실외 미러 접이 버튼"]], "pending_image_pages": [33]},
]


def case_manifest():
    """사전 질문·기대 조건을 복사하고 조건 변경 여부를 비교할 식별값을 만듭니다."""
    cases = deepcopy(ANSWER_CASES)
    payload = json.dumps(cases, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return cases, hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalize_text(text):
    """조건 문구 비교에서 공백·대소문자 차이만 줄입니다."""
    return re.sub(r"\s+", "", text).lower()


def inspect_answer(case, answer):
    """답변의 상태·출처·문구·그림 참조를 검사하되 의미 정확도를 자동 확정하지 않습니다."""
    # 안내 문구가 아닌 실제 발췌 quote만 문구 검사 대상으로 삼습니다.
    quote = normalize_text(" ".join(source["quote"] for source in answer["sources"]))
    pages = {page for source in answer["sources"] for page in source["source_pages"]}
    checks = {"expected_status": answer["status"] == case["expected_status"],
              "no_db_write": answer["db_written"] is False,
              "no_storage_upload": answer["storage_uploaded"] is False,
              "no_llm_call": answer["llm_called"] is False}
    for index, group in enumerate(case.get("required_page_groups", []), start=1):
        checks[f"required_source_group_{index}"] = bool(pages.intersection(group))
    for index, group in enumerate(case.get("required_text_groups", []), start=1):
        checks[f"required_text_group_{index}"] = any(normalize_text(term) in quote for term in group)
    if case.get("no_retrieval_expected"):
        checks["no_retrieval"] = answer["retrieval_performed"] is False
    if case["expected_status"] in {"outside_pdf_scope", "needs_review"}:
        checks["no_unverified_quote"] = not answer["sources"] and not answer["images"]
    if "display_image_pages" in case:
        valid_images = [image for image in answer["images"]
                        if image["pdf_page_number"] in case["display_image_pages"]
                        and image["public_url"] and image["descriptions"]]
        checks["displayed_image_reference"] = len(valid_images) >= case["min_display_images"]
    if "pending_image_pages" in case:
        checks["pending_image_reference"] = any(image["pdf_page_number"] in case["pending_image_pages"]
                                                for image in answer["pending_image_references"])
        checks["no_unavailable_image_display"] = not answer["images"]
    return {"case_id": case["case_id"], "group": case["group"], "question": case["question"],
            "expected": case, "checks": checks, "expectation_checks_passed": all(checks.values()),
            "failed_checks": [name for name, passed in checks.items() if not passed],
            "actual_status": answer["status"], "actual_source_pages": sorted(pages),
            "displayed_image_count": len(answer["images"]),
            "pending_image_count": len(answer["pending_image_references"]),
            # 실제 발췌를 저장하여 자동 조건이 통과해도 사람이 본문·경고를 다시 읽을 수 있게 합니다.
            "answer": answer}


def run_checks(run_id, progress=print, checkpoint=None):
    """같은 서비스로 10문항을 순서대로 확인하고 중간 결과와 완료 보고서를 반환합니다."""
    cases, manifest = case_manifest()
    service = ManualAnswerService(run_id)
    started = perf_counter()
    report = {"phase": "running", "pid": os.getpid(), "run_id": str(run_id),
              "started_at": datetime.now(timezone(timedelta(hours=9))).isoformat(),
              "question_manifest_sha256": manifest, "question_count": len(cases), "completed_count": 0,
              "search_method": "purpose_specific", "top_k": 5, "operational_error_count": 0,
              "rules_modified": False, "results": [], "failures": [],
              "limitations": ["기존 확인 주제를 포함한 새 표현이며 독립된 전체 성능 평가가 아닙니다.",
                             "상태·출처·문구·그림 참조의 자동 조건으로 답변의 의미 정확도를 보장하지 않습니다.",
                             "그림의 공개 주소·관련 페이지 반환을 확인하며 그림 픽셀의 의미를 채점하지 않습니다."]}
    if checkpoint:
        checkpoint(report)
    for index, case in enumerate(cases, start=1):
        if progress:
            progress(f"{index}/{len(cases)} | {case['case_id']} | {case['question']}")
        try:
            answer = service.answer(case["question"], top_k=5)
            row = inspect_answer(case, answer)
        except Exception as error:
            # 연결 정보가 포함될 수 있어 실행 오류의 종류만 별도 목록에 기록합니다.
            failure = {"case_id": case["case_id"], "error_type": type(error).__name__}
            report["failures"].append(failure)
            report["operational_error_count"] += 1
            row = {"case_id": case["case_id"], "group": case["group"], "question": case["question"],
                   "expectation_checks_passed": False, "failed_checks": ["operational_error"], **failure}
        report["results"].append(row)
        report["completed_count"] = index
        report["elapsed_seconds"] = perf_counter() - started
        if checkpoint:
            checkpoint(report)
        if progress:
            progress(f"  상태: {row.get('actual_status', '실행 오류')} | 기대 조건 일치: {row['expectation_checks_passed']}")
    report["phase"] = "completed" if not report["operational_error_count"] else "completed_with_errors"
    report["expectation_match_count"] = sum(row["expectation_checks_passed"] for row in report["results"])
    report["expectation_mismatch_count"] = len(cases) - report["expectation_match_count"]
    report["finished_at"] = datetime.now(timezone(timedelta(hours=9))).isoformat()
    report["db_written"] = False
    report["storage_uploaded"] = False
    report["document_embeddings_recomputed"] = False
    if service.search_service.embedder:
        report["model_name"] = service.search_service.embedder.model_name
        report["model_revision"] = service.search_service.embedder.model_revision
    if checkpoint:
        checkpoint(report)
    return report


def main():
    """승인한 확인 작업을 실행하고 개인 reports에 진행 상태·결과·실행 오류를 기록합니다."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="새 10문항의 발췌 답변·근거·그림 참조 확인")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    folder = Path(__file__).resolve().parents[3] / "data/zzong_santafe_lag/reports"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone(timedelta(hours=9))).strftime("%Y%m%d_%H%M%S")
    path = folder / f"answer_checks_10_{stamp}.json"
    failures_path = folder / f"answer_checks_10_{stamp}_failures.json"

    def write_checkpoint(report):
        """최근 완료 건수와 결과를 기록합니다. 실행 오류는 별도 파일에 남깁니다."""
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        failures_path.write_text(json.dumps(report["failures"], ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"PID: {os.getpid()} | 진행·결과 기록: {path}", flush=True)
    result = run_checks(args.run_id, progress=lambda text: print(text, flush=True), checkpoint=write_checkpoint)
    print(json.dumps({key: result[key] for key in ("phase", "completed_count", "expectation_match_count",
                                                 "expectation_mismatch_count", "operational_error_count")}, ensure_ascii=False), flush=True)
    return 0 if not result["operational_error_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
