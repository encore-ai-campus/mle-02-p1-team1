"""정리한 검색 코드의 새 질문·원문 검토 자료를 별도 보관합니다. 원격 자료는 변경하지 않습니다."""

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from .answer_service import ManualAnswerService
from .config import ManualConfig
from .database import PersonalSqlSession
from .db_search_service import DbFullSearchService
from .openai_migration import digest, write_json
from .openai_search_service import OpenAIManualSearchService, active_embedding_run
from .source_profile import FULL_SOURCE


FOLDER = ManualConfig().project_folder / "data/zzong_santafe_lag/reports/sequence_20261005_172146"
# [프로젝트 추가] 새 표현 10개를 검색 전에 고정합니다. 기대 제목은 평가에만 사용합니다.
# 이미 확인한 일부 주제의 합성 질문이며 독립 사용자 평가·사람 판정 완료로 표시하지 않습니다.
CASES = [
    ("S01", "차대번호를 차체에서 찾으려면 어느 패널을 봐야 하나요?", "차대번호 (VIN)"),
    ("S02", "설명서의 엔진 오일 점도 도표는 온도 눈금이 -30℃에서 시작하나요?", "온도에 따른 엔진 오일 SAE 점도 분류표"),
    ("S03", "차량 내부 I 그림에서 지문 인증 기능에 붙은 번호를 알려줘.", "차량 내부 I"),
    ("S04", "클러스터 점검에서는 어떤 정보와 연료 상태를 확인하나요?", "클러스터 및 페달류 점검"),
    ("S05", "페달 아래로 빈 깡통이 굴러 들어가지 않게 해야 하는 이유가 뭐야?", "운전석 주변 점검"),
    ("S06", "안전벨트를 두 사람이 하나로 같이 써도 되는지 설명서에서 찾아줘.", "안전벨트 착용"),
    ("S07", "스티어링 휠과 미러 위치는 출발 전에 맞추는 건가요?", "좌석, 스티어링 휠, 미러 조정"),
    ("S08", "오일 첨가제가 엔진에 일으킬 수 있는 문제는 무엇인가요?", "추천 오일 및 용량 — 각주 및 주의사항"),
    ("S09", "타이어 공기압이 낮을 때 고속 주행하면 차량이 전복될 수도 있나요?", "규격 타이어 장착 및 타이어 공기압 수시 점검"),
    ("S10", "올바른 운전 자세에서는 브레이크를 끝까지 밟았을 때 무릎이 어떻게 되나요?", "올바른 운전 자세"),
]


def code_version():
    """검색·선택·설정의 파일별 식별값을 보관합니다. 키나 서버 모델 버전은 아닙니다."""
    root = Path(__file__).resolve().parent
    names = ("source_profile.py", "search_support.py", "retrieval.py", "specific_terms.py",
             "db_search_service.py", "openai_search_service.py", "answer_service.py", "llm_answer_service.py")
    return {name: digest((root / name).read_text(encoding="utf-8")) for name in names}


def prepare():
    """읽기 전용으로 원문 검토 후보와 새 평가 기준을 저장합니다. 임베딩·생성 API 호출은 없습니다."""
    plan_path = FOLDER / "dataset.json"
    if plan_path.exists():
        return {"folder": str(FOLDER), "already_prepared": True}
    session = PersonalSqlSession(read_only=True)
    params = {"run_id": FULL_SOURCE.run_id}
    with session.transaction():
        run = session.select_one("manual_store.get_run", params)
        if run is None:
            raise ValueError("승인한 저장 작업이 없습니다.")
        document = session.select_one("manual_store.get_document", {"document_id": run["document_id"]})
        counts = session.select_one("manual_store.get_run_search_counts", params)
        DbFullSearchService(FULL_SOURCE.run_id).validate_source(run, document, counts)
        if document["file_sha256"] != FULL_SOURCE.pdf_sha256:
            raise ValueError("원문 PDF 식별값이 다릅니다.")
        parents = session.select_list("manual_store.get_run_parents", params)
        images = session.select_list("manual_store.get_run_image_details", params)
    candidates = [row for row in parents if row["verification_status"] == "auto_draft_needs_review"
                  and ("스마트 테일게이트" in row["title"] or row["title"] == "실외 미러")]
    ids = {row["record_id"] for row in candidates}
    write_json(FOLDER / "review_sources.json", {
        "source_run_id": str(FULL_SOURCE.run_id), "pdf_sha256": FULL_SOURCE.pdf_sha256,
        "parent_status_counts": dict(Counter(row["verification_status"] for row in parents)),
        "records": candidates, "images": [row for row in images if row["parent_record_id"] in ids],
        "scope": "빈도가 높은 두 주제의 원문 검토 자료. 검토 결과 기록 전이며 DB 상태 승격 없음.",
        "db_written": False, "storage_uploaded": False})
    cases = []
    for case_id, question, title in CASES:
        matches = [row for row in parents if row["title"] == title
                   and row["verification_status"] != "auto_draft_needs_review"]
        if len(matches) != 1:
            raise ValueError("새 질문의 기대 근거를 하나로 고정하지 못했습니다.")
        anchor = matches[0]
        cases.append({"case_id": case_id, "question": question, "anchor": {
            key: anchor[key] for key in ("record_id", "title", "content", "raw_text", "source_pages")}})
    plan = {"cases": cases, "dataset_sha256": digest(cases), "top_k": 5,
            "source_run_id": str(FULL_SOURCE.run_id), "embedding_run_id": str(active_embedding_run()),
            "code_version": code_version(), "frozen_at": datetime.now(timezone.utc).isoformat(),
            "rubric": "질문의 요구를 직접 뒷받침하는 문장이 있으면 관련. 주제만 유사한 설명·참조는 비관련. 일부 직접 근거도 관련으로 셈.",
            "human_confirmed": False, "db_written": False, "storage_uploaded": False}
    write_json(plan_path, plan)
    return {"folder": str(FOLDER), "question_count": len(cases),
            "review_candidates": [{"title": r["title"], "pages": r["source_pages"]} for r in candidates]}


def collect():
    """고정한 10문항의 기본 OpenAI 검색과 로컬 3문항을 실행합니다. 생성 API 호출은 없습니다."""
    plan = json.loads((FOLDER / "dataset.json").read_text(encoding="utf-8"))
    if digest(plan["cases"]) != plan["dataset_sha256"] or code_version() != plan["code_version"]:
        raise ValueError("고정한 질문이나 검색 코드가 바뀌었습니다.")
    if str(active_embedding_run()) != plan["embedding_run_id"]:
        raise ValueError("평가 중 벡터 작업이 바뀌었습니다.")
    path = FOLDER / "retrieval.json"
    report = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
        "dataset_sha256": plan["dataset_sha256"], "code_version": plan["code_version"],
        "pid": os.getpid(), "results": [], "failures": [], "complete": False,
        "query_embedding_attempts": 0, "query_embedding_calls": 0,
        "generation_calls": 0, "db_written": False, "storage_uploaded": False}
    if report["failures"] or any(row["state"] != "completed" for row in report["results"]):
        raise ValueError("실패 또는 미완료 시작 기록이 있습니다. 자동 재호출하지 않습니다.")
    services = {"openai": OpenAIManualSearchService(plan["embedding_run_id"]),
                "local": DbFullSearchService(FULL_SOURCE.run_id, method="purpose_specific")}
    started = perf_counter()
    for backend, service in services.items():
        cases = plan["cases"] if backend == "openai" else plan["cases"][:3]
        for case in cases:
            if any(r["case_id"] == case["case_id"] and r["backend"] == backend for r in report["results"]):
                continue
            row = {"case_id": case["case_id"], "backend": backend, "state": "started"}
            report["results"].append(row)
            if backend == "openai":
                report["query_embedding_attempts"] += 1
            write_json(path, report)
            try:
                search = service.search(case["question"], top_k=5)
                if backend == "openai":
                    report["query_embedding_calls"] += 1
                evidence = ManualAnswerService.from_search_result(search)
                rank = next((index+1 for index, hit in enumerate(search["candidates"])
                    if any(r["record_id"] == case["anchor"]["record_id"] for r in hit["context_records"])), None)
                row.update(state="completed", search=search, evidence=evidence, expected_rank=rank)
            except Exception as error:
                # 외부 오류에는 인증 정보가 섞일 수 있어 종류만 기록합니다. 시작 기록은 보존합니다.
                row.update(state="failed", error_type=type(error).__name__)
                report["failures"].append({"case_id": case["case_id"], "backend": backend, "error_type": type(error).__name__})
                write_json(path, report)
                raise ValueError("검색 확인이 중단됐습니다. 실패 보고서를 확인하세요.") from None
            report["elapsed_seconds"] = perf_counter() - started
            write_json(path, report)
            print(f"{len(report['results'])}/13 {backend} {case['case_id']} | 기대 근거 순위 {rank} | {evidence['status']}", flush=True)
    report.update(complete=True)
    write_json(path, report)
    return {"path": str(path), "complete": True, "result_count": len(report["results"]),
            "query_embedding_calls": report["query_embedding_calls"], "generation_calls": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="개인 코드 정리 후 원문·새 질문 확인")
    parser.add_argument("action", choices=("prepare", "collect"))
    action = parser.parse_args().action
    try:
        print(json.dumps({"prepare": prepare, "collect": collect}[action](), ensure_ascii=False, indent=2))
    except Exception as error:
        print(f"확인 중단: {type(error).__name__}. 외부 오류 전문은 출력하지 않습니다.", flush=True)
        raise SystemExit(1) from None
