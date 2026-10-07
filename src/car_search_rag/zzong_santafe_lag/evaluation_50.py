"""사용자가 확정한 50문항의 현재 화면 응답·검색 후보를 보존합니다. 자동 의미 채점은 없습니다."""

import csv
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from .app import create_answer_service, SantafeBackend
from .openai_search_service import active_embedding_run
from .source_profile import FULL_SOURCE
from .review_revision import selection_file

FOLDER = Path(__file__).resolve().parent
OUTPUT = FOLDER / "evaluation_50_results"


def write_json(path, value):
    """중단 시 기존 결과를 보호하도록 임시 파일을 완성한 뒤 교체합니다."""
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    temporary.replace(path)


def freeze_plan():
    """질문·기준·구현·저장 버전을 검색 전에 고정합니다. 정답은 검색에 전달하지 않습니다."""
    dataset = json.loads((FOLDER / "evaluation_50_questions.json").read_text(encoding="utf-8"))
    cases = [{"case_id": f"{group['group']}{n:02}", "group":group["group"], "question":question}
             for group in dataset["groups"] for n,question in enumerate(group["questions"],1)]
    assert len(cases) == 50 and [len(g["questions"]) for g in dataset["groups"]] == [10,20,20]
    digest = hashlib.sha256(json.dumps(dataset, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    files = ["app.py", "answer_service.py", "question_input.py", "question_intent.py", "retrieval.py",
             "source_navigation.py", "answer_display.py", "llm_answer_service.py", "specific_terms.py"]
    hashes = {name: hashlib.sha256((FOLDER/name).read_bytes()).hexdigest() for name in files}
    selected = selection_file()
    plan = {"dataset_sha256":digest, "cases":cases, "rubric":dataset["rubric"],
            "source_run_id":str(FULL_SOURCE.run_id), "embedding_run_id":str(active_embedding_run()),
            "review_selection":json.loads(selected.read_text(encoding="utf-8")) if selected else None,
            "code_hashes":hashes, "git_commit":subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),
            "gold_labels_human_confirmed":False, "independent_sessions":True, "generation_calls_planned":0}
    OUTPUT.mkdir(exist_ok=True)
    path = OUTPUT / "plan.json"
    if path.exists() and json.loads(path.read_text(encoding="utf-8")) != plan:
        raise ValueError("질문·구현·저장 버전이 기존 계획과 다릅니다. 별도 결과로 구분해주세요.")
    write_json(path, plan)
    return plan


def collect():
    """50문항을 독립 세션에서 실행하고 후보 전문과 응답을 체크포인트로 저장합니다."""
    plan = freeze_plan()
    path = OUTPUT / "results.json"
    saved = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
        "dataset_sha256":plan["dataset_sha256"], "results":[], "complete":False}
    if saved["dataset_sha256"] != plan["dataset_sha256"]:
        raise ValueError("질문 식별값이 다릅니다.")
    service = create_answer_service("OpenAI", "답변 아래 관련 그림 보기")
    search = service.evidence_service.search_service
    original_search = search.search
    captured = []

    def record_search(*args, **kwargs):
        """실제 검색을 한 번 호출하고 같은 반환 후보를 기록합니다. 평가용 중복 검색은 없습니다."""
        value = original_search(*args, **kwargs)
        captured.append(value)
        return value

    search.search = record_search
    backend = SantafeBackend(service)
    started = perf_counter()
    for case in plan["cases"]:
        if any(row["case_id"]==case["case_id"] for row in saved["results"]):
            continue
        captured.clear()
        session = backend.start_session(is_test=True)
        tick = perf_counter()
        try:
            packet = backend.chat(session, case["question"], request_id=case["case_id"])
            row = {**case, "packet":packet, "search_results":list(captured), "error_type":None,
                   "human_relevance_labels":None, "human_response_label":None}
        except Exception as error:
            row = {**case, "error_type":type(error).__name__, "search_results":list(captured),
                   "human_relevance_labels":None, "human_response_label":None}
        finally:
            # 종료 메서드는 서비스를 초기화하므로 독립 질문 기록만 지웁니다. 검색 준비 상태는 재사용합니다.
            backend.sessions.pop(session, None)
        row["seconds"] = round(perf_counter()-tick, 3)
        saved["results"].append(row)
        saved.update(completed=len(saved["results"]), total=50, pid=os.getpid(),
                     elapsed_seconds=round(perf_counter()-started,2), updated_at=datetime.now(timezone.utc).isoformat())
        write_json(path, saved)
        failures = [{"case_id":r["case_id"],"error_type":r["error_type"]} for r in saved["results"] if r["error_type"]]
        write_json(OUTPUT/"failures.json", failures)
        print(f"완료 {len(saved['results'])}/50 | {case['case_id']} | 실패 {len(failures)}",flush=True)
    saved["complete"] = len(saved["results"])==50
    write_json(path, saved)
    with (OUTPUT/"human_grading.csv").open("w",encoding="utf-8-sig",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=["case_id","group","question","native_status","search_count","displayed_titles","response_pass","gold_pages","notes"])
        writer.writeheader()
        for row in saved["results"]:
            packet=row.get("packet",{})
            writer.writerow({"case_id":row["case_id"],"group":row["group"],"question":row["question"],
                             "native_status":packet.get("native_status",row["error_type"]),
                             "search_count":len(row["search_results"]),
                             "displayed_titles":" | ".join(s["title"] for s in packet.get("sources",[]))})
    status={}
    for row in saved["results"]:
        value=row.get("packet",{}).get("native_status",row["error_type"])
        status[value]=status.get(value,0)+1
    write_json(OUTPUT/"summary.json", {"completed":len(saved["results"]),"failure_count":len(failures),
               "status_counts":status,"search_calls":sum(len(r["search_results"]) for r in saved["results"]),
               "generation_calls":0,"db_written":False,"human_confirmed":False,
               "quality_metrics":None,"note":"검색·화면 응답 수집 결과입니다. 사람의 정답·관련성 확인 전에는 정확도를 계산하지 않습니다."})
    print("결과 저장 완료. 의미 품질 채점은 사람 확인 대기입니다.",flush=True)


if __name__ == "__main__":
    collect()
