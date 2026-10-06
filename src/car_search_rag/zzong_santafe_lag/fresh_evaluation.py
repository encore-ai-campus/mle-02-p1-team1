"""새 질문의 후보 원문을 보존하고, 내용 판정표로 Precision@5를 계산합니다."""

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from .answer_service import ManualAnswerService
from .database import PersonalSqlSession
from .db_search_service import DbFullSearchService
from .llm_answer_service import LlmManualAnswerService
from .openai_migration import SOURCE_RUN_ID, OUTPUT_FOLDER, digest, write_json
from .openai_search_service import OpenAIManualSearchService, active_embedding_run


# [프로젝트 추가] 이전 30문항과 다른 질문을 검색 전에 고정합니다.
# 검토된 일부 주제에서 만든 소규모 합성 질문이며, 전체 PDF의 독립 사용자 평가가 아닙니다.
# 기대 원문 ID·정답 문장은 검색/생성 함수에 전달하지 않습니다.
FRESH_CASES = [
    ("N01", "냉각수 보조 탱크 캡을 엔진이 뜨거울 때 열어도 되나요?", "엔진룸 점검",
     "엔진이 차가울 때 점검. 수온이 높을 때 캡을 열면 냉각수가 분출되어 화상 위험.", True),
    ("N02", "타이어의 스탠딩 웨이브는 어떤 현상인가요?", "규격 타이어 장착 및 타이어 공기압 수시 점검",
     "공기압이 부족한 타이어로 고속 주행할 때 물결 같은 주름이 접힘. 계속되면 단시간에 파열.", False),
    ("N03", "페달의 간극이 평소보다 길거나 짧아졌을 때 어디에서 점검받아야 하나요?", "클러스터 및 페달류 점검",
     "즉시 당사 직영 하이테크센터나 블루핸즈에서 점검.", False),
    ("N04", "올바른 운전 자세에서 헤드레스트 중심은 귀의 어느 부분에 맞추나요?", "올바른 운전 자세",
     "높이 조절이 가능한 차량에서 운전자의 귀 상단이 헤드레스트 중심에 오도록 조절.", False),
    ("N05", "좌석과 스티어링 휠과 미러는 주행 중에 조절해도 되나요?", "좌석, 스티어링 휠, 미러 조정",
     "출발 전에 조절하고 주행 중에는 절대로 조작하지 않음.", True),
    ("N06", "운전석 바닥 매트는 어떤 조건을 갖춰야 하나요?", "운전석 주변 점검",
     "페달 움직임을 방해하지 않고, 너무 두껍지 않으며, 바닥에 고정되는 제품.", False),
    ("N07", "차체에 새겨진 차대번호와 차량 등록증의 차대번호는 같아야 하나요?", "차대번호 (VIN)",
     "차체에 타각된 차대번호와 차량 등록증에 기록된 차대번호는 일치해야 함.", False),
    ("N08", "추천 오일 및 용량 표에 기재된 연료 탱크 용량과 연료 종류는 무엇인가요?", "추천 오일 및 용량",
     "연료 67 ℓ, 무연 휘발유.", True),
    ("N09", "차량 외부 II 안내도에서 안테나는 몇 번으로 표시되어 있나요?", "차량 외부 II",
     "6번, 관련 설명은 매뉴얼 367쪽. 이 그림은 실제 차량과 다를 수 있음.", False),
    ("N10", "어린이를 무릎에 앉히고 팔로 안은 채 타도 되나요?", "안전벨트 착용",
     "어린이를 무릎에 앉히고 팔로 안지 않음. 충돌 시 놓쳐 위험. 3점식 안전벨트 착용 불가 어린이는 뒷좌석 보조 좌석 사용.", False),
]


def current_plan():
    """고정 질문과 새 벡터 버전의 식별값을 대조하고 결과 폴더를 반환합니다."""
    pointer = json.loads((OUTPUT_FOLDER / "fresh_active.json").read_text(encoding="utf-8"))
    folder = OUTPUT_FOLDER / ("fresh_" + pointer["dataset_sha256"])
    plan = json.loads((folder / "dataset.json").read_text(encoding="utf-8"))
    if digest(plan["cases"]) != pointer["dataset_sha256"]:
        raise ValueError("검색 전에 고정한 질문/기준이 바뀌었습니다.")
    if plan["embedding_run_id"] != str(active_embedding_run()):
        raise ValueError("평가 중 임베딩 버전이 바뀌었습니다.")
    return plan, folder


def prepare():
    """개인 원문을 읽고 정답 기준을 먼저 저장합니다. 모델/API 실행은 없습니다."""
    session = PersonalSqlSession(read_only=True)
    with session.transaction():
        parents = session.select_list("manual_store.get_run_parents", {"run_id": SOURCE_RUN_ID})
    cases = []
    for case_id, question, title, facts, generate in FRESH_CASES:
        matches = [row for row in parents if row["title"] == title
                   and row["verification_status"] != "auto_draft_needs_review"]
        if len(matches) != 1:
            raise ValueError("검색 전 기대 원문을 하나로 고정하지 못했습니다.")
        row = matches[0]
        cases.append({"case_id": case_id, "question": question, "required_facts": facts,
                      "generate_sample": generate,
                      "anchor": {key: row[key] for key in ("record_id", "title", "source_pages", "content", "raw_text")}})
    dataset_hash = digest(cases)
    folder = OUTPUT_FOLDER / ("fresh_" + dataset_hash)
    plan = {"dataset_sha256": dataset_hash, "source_run_id": str(SOURCE_RUN_ID),
            "embedding_run_id": str(active_embedding_run()), "cases": cases,
            "created_at": datetime.now(timezone.utc).isoformat(), "top_k": 5,
            "rubric": "1=질문의 요구 사실을 직접 뒷받침하는 원문 문장이 있음. 0=주제만 유사/목차·참조만 있음/다른 조작. 일부 요청의 직접 근거도 1. 미판정은 null.",
            "scope": "새 합성 질문 10개, 이미 확인한 일부 주제. 사람의 교차 검토 전 Codex 내용 판정."}
    path = folder / "dataset.json"
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8"))
        if previous["cases"] != cases or previous["embedding_run_id"] != plan["embedding_run_id"]:
            raise ValueError("기존 평가 기준 또는 모델 버전이 다릅니다.")
    else:
        write_json(path, plan)
    write_json(OUTPUT_FOLDER / "fresh_active.json", {"dataset_sha256": dataset_hash})
    return {"folder": str(folder), "question_count": len(cases), "dataset_sha256": dataset_hash,
            "api_called": False, "db_written": False}


def pool_key(case_id, candidate):
    """모델명·순위와 무관한 식별값을 만들어 같은 문맥을 한 번만 판정합니다."""
    records = [{key: row[key] for key in ("record_id", "content", "raw_text", "source_pages")}
               for row in candidate["context_records"]]
    return case_id + "_" + digest(sorted(records, key=lambda row: row["record_id"]))


def collect(progress=print):
    """두 모델을 같은 조건으로 검색하고 후보 전문과 발췌 선택을 보존합니다. DB 수정은 없습니다."""
    plan, folder = current_plan()
    services = {"local": DbFullSearchService(SOURCE_RUN_ID, method="purpose_specific"),
                "openai": OpenAIManualSearchService(plan["embedding_run_id"], method="purpose_specific")}
    path = folder / "retrieval.json"
    saved = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
        "dataset_sha256": plan["dataset_sha256"], "results": [], "failures": [], "complete": False}
    if saved["failures"]:
        raise ValueError("실패 기록부터 확인하세요. 자동 재시도하지 않습니다.")
    if saved["dataset_sha256"] != plan["dataset_sha256"]:
        raise ValueError("평가 질문의 식별값이 다릅니다.")
    started = perf_counter()
    for case in plan["cases"]:
        for backend, service in services.items():
            if any(row["case_id"] == case["case_id"] and row["backend"] == backend for row in saved["results"]):
                continue
            try:
                # [프로젝트 적용] 기대 정답은 전달하지 않습니다. 검색 결과로 발췌를 만들므로 중복 API 호출도 없습니다.
                search = service.search(case["question"], top_k=plan["top_k"])
                saved["results"].append({"case_id": case["case_id"], "backend": backend,
                                         "search": search, "evidence": ManualAnswerService.from_search_result(search)})
            except Exception as error:
                # [프로젝트 추가] 연결/인증 메시지 대신 종류만 저장해 키 유출을 피합니다. 실패를 분모에서 빼지 않습니다.
                saved["failures"].append({"case_id": case["case_id"], "backend": backend,
                                          "error_type": type(error).__name__})
                write_json(path, saved)
                write_json(folder / "failures.json", saved["failures"])
                raise
            saved.update(completed=len(saved["results"]), total=len(plan["cases"]) * 2,
                         recent_session_seconds=perf_counter() - started, pid=os.getpid())
            write_json(path, saved)
            progress(f"검색 완료 {saved['completed']}/{saved['total']} | {case['case_id']} | {backend}", flush=True)
    saved["complete"] = len(saved["results"]) == len(plan["cases"]) * 2
    write_json(path, saved)
    # [프로젝트 추가] 모델/순위를 숨긴 합집합 판정표를 만듭니다. 같은 후보를 두 모델에 다르게 채점하지 않습니다.
    pool = {}
    cases = {case["case_id"]: case for case in plan["cases"]}
    for row in saved["results"]:
        case = cases[row["case_id"]]
        for hit in row["search"]["candidates"]:
            key = pool_key(case["case_id"], hit)
            pool[key] = {"key": key, "case_id": case["case_id"], "question": case["question"],
                         "required_facts": case["required_facts"], "context_records": hit["context_records"]}
    write_json(folder / "review_queue.json", [pool[key] for key in sorted(pool)])
    return {"question_count": len(cases), "pooled_candidate_count": len(pool), "complete": saved["complete"],
            "failure_count": len(saved["failures"]), "new_generation_calls": 0, "folder": str(folder)}


def score():
    """후보 전문 판정이 모두 있을 때 Precision/Hit/MRR을 계산합니다. API 호출은 없습니다."""
    plan, folder = current_plan()
    saved = json.loads((folder / "retrieval.json").read_text(encoding="utf-8"))
    annotations = json.loads((folder / "relevance_labels.json").read_text(encoding="utf-8"))
    if not saved["complete"] or saved["failures"] or annotations["dataset_sha256"] != plan["dataset_sha256"]:
        raise ValueError("검색 완료 상태와 질문 식별값을 확인하세요.")
    rows = []
    for row in saved["results"]:
        ranked = []
        for rank, hit in enumerate(row["search"]["candidates"], start=1):
            key = pool_key(row["case_id"], hit)
            label = annotations["labels"].get(key)
            if label is None or type(label["relevant"]) is not bool or not label["reason"]:
                raise ValueError("미판정 후보가 있습니다. 임의로 0점을 넣지 않습니다.")
            ranked.append({"rank": rank, "key": key, "title": hit["title"],
                           "record_ids": [r["record_id"] for r in hit["context_records"]], **label})
        first = next((r["rank"] for r in ranked if r["relevant"]), None)
        # [프로젝트 추가] 분모는 요청한 5개입니다. 부족한 반환 수도 기록해 적은 반환 결과의 점수를 부풀리지 않습니다.
        rows.append({"case_id": row["case_id"], "backend": row["backend"], "candidates": ranked,
                     "returned_count": len(ranked), "Precision@5": sum(r["relevant"] for r in ranked) / 5,
                     "Hit@5": first is not None, "MRR@5": 1 / first if first else 0.0,
                     "answer_status": row["evidence"]["status"]})
    metrics = {}
    for backend in ("local", "openai"):
        subset = [row for row in rows if row["backend"] == backend]
        metrics[backend] = {name: sum(row[name] for row in subset) / len(subset)
                            for name in ("Precision@5", "Hit@5", "MRR@5")}
    report = {"dataset_sha256": plan["dataset_sha256"], "question_count": len(plan["cases"]),
              "source_run_id": plan["source_run_id"], "embedding_run_id": plan["embedding_run_id"],
              "metrics": metrics, "annotation_sha256": digest(annotations),
              "annotation_provenance": annotations["provenance"], "human_confirmed": False,
              "db_written": False, "storage_uploaded": False, "generation_accuracy_measured": False,
              "limitations": ["이미 확인한 주제 위주의 소규모 합성 질문으로 실제 사용자의 독립 평가는 아닙니다.",
                              "Precision은 후보의 직접 근거 여부이며 생성 정확도·경고 완전성·그림 이해와 다릅니다.",
                              "Codex의 원문 내용 판정입니다. 사람의 교차 검토 전 잠정값입니다."], "results": rows}
    write_json(folder / "metrics.json", report)
    return metrics


def import_labels():
    """읽고 작성한 내용 판정표를 후보 식별값에 연결하고 직접 인용문도 대조합니다."""
    plan, folder = current_plan()
    reviewed = json.loads(Path(__file__).with_name("fresh_relevance_review_20261005.json").read_text(encoding="utf-8"))
    if reviewed["dataset_sha256"] != plan["dataset_sha256"]:
        raise ValueError("내용 판정표의 질문 버전이 다릅니다.")
    queue = json.loads((folder / "review_queue.json").read_text(encoding="utf-8"))
    labels, used = {}, set()
    for row in queue:
        identity = ",".join(sorted(r["record_id"] for r in row["context_records"]))
        decision = reviewed["cases"][row["case_id"]].get(identity)
        if decision is None or type(decision[0]) is not bool:
            raise ValueError("판정표에 없는 후보가 있습니다. 새 후보를 임의로 채점하지 않습니다.")
        used.add((row["case_id"], identity))
        label = {"relevant": decision[0], "reason": decision[1], "human_confirmed": False}
        if decision[0]:
            # [프로젝트 추가] 관련 판정은 실제 원문 문장이 있어야 합니다. 안내도 번호는 기존 검토된 매핑을 사용합니다.
            kind = decision[3] if len(decision) > 3 else "stored_raw_text"
            field = "content" if kind == "verified_navigation_content" else "raw_text"
            body = " ".join(r[field] for r in row["context_records"])
            normalize = lambda text: re.sub(r"\s+", "", text)
            if normalize(decision[2]) not in normalize(body):
                raise ValueError("관련 판정의 직접 인용문이 저장 원문에서 일치하지 않습니다.")
            if kind == "verified_navigation_content" and any(
                    r["verification_status"] == "auto_draft_needs_review" for r in row["context_records"]):
                raise ValueError("안내도 번호의 원문 확인 상태를 먼저 검토하세요.")
            label.update(supporting_excerpt=decision[2], supporting_source=kind)
        labels[row["key"]] = label
    expected = {(case_id, identity) for case_id, decisions in reviewed["cases"].items() for identity in decisions}
    if used != expected:
        raise ValueError("후보 합집합과 판정표 항목 수가 다릅니다.")
    report = {"dataset_sha256": plan["dataset_sha256"], "provenance": reviewed["provenance"],
              "human_confirmed": False, "labels": labels, "reviewed_candidate_count": len(labels)}
    write_json(folder / "relevance_labels.json", report)
    return {"reviewed_candidate_count": len(labels), "human_confirmed": False, "api_called": False}


def generate_samples():
    """검색해 둔 OpenAI 근거로 사전 지정 3문항만 생성합니다. 완료·보류 건을 재생성하지 않습니다."""
    plan, folder = current_plan()
    searches = json.loads((folder / "retrieval.json").read_text(encoding="utf-8"))
    if not searches["complete"] or searches["failures"]:
        raise ValueError("검색 확인부터 완료하세요.")
    service = LlmManualAnswerService(SOURCE_RUN_ID, image_display_location="관련 그림 탭")
    path = folder / "generation.json"
    report = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"results": [], "attempted_calls": 0}
    for case in plan["cases"]:
        if not case["generate_sample"] or any(row["case_id"] == case["case_id"] for row in report["results"]):
            continue
        evidence = next(row["evidence"] for row in searches["results"]
                        if row["case_id"] == case["case_id"] and row["backend"] == "openai")
        # [프로젝트 추가] API 실행 전에 시도 기록을 남겨 중단 후 자동 재시도로 중복 호출하지 않습니다.
        pending = {"case_id": case["case_id"], "phase": "started", "required_facts": case["required_facts"]}
        report["results"].append(pending)
        write_json(path, report)
        result = service.generate(evidence)
        pending.update(phase="completed", answer=result)
        report["attempted_calls"] += int(result.get("llm_called", False))
        report["generation_settings"] = service.settings()
        write_json(path, report)
        print(f"생성 확인 {case['case_id']} | {result['status']} | API: {result.get('llm_called', False)}", flush=True)
    return {"sample_count": len(report["results"]), "attempted_calls": report["attempted_calls"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="새 질문·Precision@5 평가: 단계별 실행")
    parser.add_argument("action", choices=("prepare", "collect", "labels", "score", "generate"))
    action = parser.parse_args().action
    try:
        print(json.dumps({"prepare": prepare, "collect": collect, "labels": import_labels, "score": score,
                          "generate": generate_samples}[action](), ensure_ascii=False, indent=2))
    except Exception as error:
        print(f"평가 중단: {type(error).__name__}. 실패를 완료로 표시하거나 자동 재시도하지 않습니다.", flush=True)
        raise SystemExit(1) from None
