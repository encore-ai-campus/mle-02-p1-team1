"""이미 실행한 화면·검색 결과를 요약합니다. 모델·DB를 부르지 않는 보고서 작성 도구입니다."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PERSONAL = Path(__file__).resolve().parent
REPORTS = ROOT / "data/zzong_santafe_lag/reports"
FOLDER = REPORTS / "sequence_20261005_172146"

# [프로젝트 추가] 검색을 끝낸 뒤 내용으로 판정한 평가 자료입니다.
# 운영 검색이나 답변 함수에는 가져오지 않습니다. 정답 사전이 아닙니다.
# None은 사람이 다시 판정할 경계 사례입니다. 모든 판정은 사람 교차 검토 전입니다.
RELATED = {
    "S01": {1: "차대번호가 타각된 차체 패널을 명시한다."},
    "S02": {1: "점도 표의 온도 눈금 -30~50도를 명시한다."},
    "S03": {},
    "S04": {1: "클러스터 정보의 이상 유무와 충분한 연료량 점검을 명시한다."},
    "S05": {1: "빈 깡통이 페달 조작을 불가능하게 하므로 위험하다고 명시한다."},
    "S06": {1: "벨트 하나를 두 사람 이상이 착용하지 말라고 명시한다.",
            2: "두 사람 이상이 안전벨트 하나를 함께 착용하지 말라고 명시한다."},
    "S07": {},
    "S08": {1: "첨가제가 오일 특성을 바꾸고 심각한 엔진 고장을 유발할 수 있다고 명시한다.",
            2: "연결 각주·주의사항에 첨가제의 특성 변화와 엔진 고장 경고가 있다.",
            3: "정기 점검 표의 각주에도 같은 첨가제 경고가 있다."},
    "S09": {5: "공기압 부족·고속 주행·파열·차량 전복의 연결을 명시한다."},
    "S10": {1: "브레이크를 끝까지 밟았을 때 무릎이 약간 굽혀지는 자세를 명시한다."},
}
NEGATIVE_REASONS = {
    "S01": "부품 위치·번호판등·ESC·디지털 키 설명이며 차대번호 타각 패널의 직접 근거가 없다.",
    "S02": "오일 사양/점검 또는 다른 표·계측기이며 엔진 오일 점도 도표의 온도 시작 눈금을 말하지 않는다.",
    "S03": "지문 기능 설명 또는 다른 번호이며 차량 내부 I 안내도의 지문 항목 번호를 말하지 않는다.",
    "S04": "부품 참조 쪽수나 다른 점검 설명이며 클러스터 정보·연료 점검 지침의 직접 근거가 아니다.",
    "S05": "다른 이물질·액체·안전벨트 설명이며 페달 밑 깡통의 위험을 직접 뒷받침하지 않는다.",
    "S06": "안전벨트 관리·어린이·임산부·착용 의무이며 하나를 두 사람이 함께 쓰는 금지 근거가 없다.",
    "S07": "안내도 부품 이름·참조 쪽수이며 출발 전 조절 또는 주행 중 조절 금지를 말하지 않는다.",
    "S08": "오일의 역할/과열 설명이며 오일 첨가제의 특성 변화와 엔진 고장 경고가 없다.",
    "S09": "공기압 표시·규격·점검 설명이며 공기압 부족 고속 주행으로 전복될 수 있다는 직접 근거가 없다.",
    "S10": "다른 운전/제동/좌석 경고이며 질문에서 요구한 무릎의 굽힘 상태를 말하지 않는다.",
}


def read_json(path):
    """비밀 설정이 아닌 지정한 결과 파일만 읽습니다."""
    return json.loads(path.read_text(encoding="utf-8"))


def file_hash(path):
    """읽은 보고서의 바이트 식별값으로 다른 실행과 혼동하지 않도록 합니다."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_new(path, value):
    """과거 결과를 덮어쓰지 않고 새 결과만 씁니다."""
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def summarize_ui():
    """화면의 다섯 질문과 다운로드한 실제 결과를 대조합니다. 전체 답변 정확도는 아닙니다."""
    expected = {
        "vin": ("generated_answer", ["vin_45"], ["차체 패널", "관련 그림"], 1),
        "oil": ("generated_answer", ["auto_topic_33", "reviewed_oil_notes_43", "table_44"], ["4.8", "0W-20", "F"], 2),
        "prohibition": ("generated_answer", ["sample_topic_4"], ["출발", "절대로"], 0),
        "recall": ("outside_pdf_scope", [], [], 0),
        "review": ("needs_review", [], [], 0),
    }
    cases = []
    for name, (status, source_ids, phrases, images) in expected.items():
        path = REPORTS / f"sequence_ui_{name}_20261005.json"
        wrapped = read_json(path)
        evidence = wrapped["evidence"]
        answer = wrapped["answer_result"] or evidence
        ids = [row["record_id"] for row in answer["sources"]]
        checks = {"status": answer["status"] == status,
                  "sources": sorted(ids) == sorted(source_ids),
                  "answer_phrases": all(word in answer["answer"] for word in phrases),
                  "image_references": len(answer["images"]) == images,
                  "generation_called": bool(answer.get("llm_called")) == (status == "generated_answer")}
        cases.append({"name": name, "question": answer["question"], "status": answer["status"],
                      "checks": checks, "passed": all(checks.values()), "source_record_ids": ids,
                      "image_reference_count": len(answer["images"]),
                      "llm_called": bool(answer.get("llm_called")), "token_usage": answer.get("token_usage"),
                      "query_embedding_calls": (len(evidence.get("subquestions") or [evidence["question"]])
                                                 if evidence.get("query_embedding_api_called") else 0),
                      "file": str(path.relative_to(ROOT)), "file_sha256": file_hash(path)})
    return {"cases": cases, "passed": sum(row["passed"] for row in cases), "total": len(cases),
            "generation_calls": sum(row["llm_called"] for row in cases),
            "total_generation_tokens": sum((row["token_usage"] or {}).get("total_tokens", 0) for row in cases),
            "query_embedding_calls": sum(row["query_embedding_calls"] for row in cases),
            "vin_image_visually_loaded": True,
            "scope": "브라우저 실제 동작 5조건 및 Codex의 답변 대조. 모든 이미지·전체 답변 정확도 평가가 아님.",
            "screenshots": ["data/zzong_santafe_lag/reports/sequence_ui_vin_20261005.png",
                            "data/zzong_santafe_lag/reports/sequence_ui_prohibition_20261005.png"]}


def summarize_search(plan, retrieval):
    """후보 내용 판정과 미리 지정한 기대 ID의 점수를 구별해 집계합니다."""
    if not retrieval["complete"] or retrieval["failures"] or len(retrieval["results"]) != 13:
        raise ValueError("검색 13건의 완료 기록을 먼저 확인하세요.")
    if retrieval["dataset_sha256"] != plan["dataset_sha256"]:
        raise ValueError("질문 목록이 다릅니다.")
    cases, labels = [], []
    for row in retrieval["results"]:
        case_id, backend = row["case_id"], row["backend"]
        candidates = row["search"]["candidates"]
        if len(candidates) != 5:
            raise ValueError("모든 질문에 후보 5개가 있어야 이 지표를 적용할 수 있습니다.")
        relevant_ranks = []
        uncertain_ranks = []
        for rank, candidate in enumerate(candidates, 1):
            related = rank in RELATED[case_id]
            reason = RELATED[case_id].get(rank, NEGATIVE_REASONS[case_id])
            if backend == "openai" and case_id == "S04" and rank == 5:
                related = None
                uncertain_ranks.append(rank)
                reason = "통상 조건 표에 일일 연료량 점검이 있으나 클러스터 점검이라는 질문 범위를 충족하는지 사람 판정 필요."
            elif related:
                relevant_ranks.append(rank)
            labels.append({"backend": backend, "case_id": case_id, "rank": rank,
                           "parent_record_id": candidate["parent_record_id"], "title": candidate["title"],
                           "context_record_ids": [r["record_id"] for r in candidate["context_records"]],
                           "codex_related": related, "reason": reason, "human_related": None,
                           "context_sha256": hashlib.sha256(json.dumps(candidate["context_records"],
                               ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()})
        # 선택 결과의 직접 근거는 후보 내용과 별도로 대조했습니다. S03/S07은 실제 실패입니다.
        selected_has_direct_support = case_id not in {"S03", "S07"}
        cases.append({"backend": backend, "case_id": case_id, "question": row["search"]["question"],
                      "expected_id_rank": row["expected_rank"], "related_ranks": relevant_ranks,
                      "uncertain_ranks": uncertain_ranks, "first_related_rank": min(relevant_ranks, default=None),
                      "evidence_status": row["evidence"]["status"],
                      "selected_record_ids": [r["record_id"] for r in row["evidence"]["sources"]],
                      "selected_has_direct_support": selected_has_direct_support})
    metrics = {}
    for backend in ("openai", "local"):
        group = [row for row in cases if row["backend"] == backend]
        count = len(group)
        positives = sum(len(row["related_ranks"]) for row in group)
        uncertain = sum(len(row["uncertain_ranks"]) for row in group)
        metrics[backend] = {"question_count": count, "candidate_occurrences": count * 5,
                            "relevant_occurrences": positives, "uncertain_occurrences": uncertain,
                            "precision_at_5_lower": positives / (count * 5),
                            "precision_at_5_upper": (positives + uncertain) / (count * 5),
                            "content_hit_at_5": sum(bool(r["related_ranks"]) for r in group) / count,
                            "content_mrr_at_5": sum(1 / r["first_related_rank"] if r["first_related_rank"] else 0
                                                    for r in group) / count,
                            "expected_id_hit_at_5": sum(r["expected_id_rank"] is not None for r in group) / count,
                            "expected_id_mrr_at_5": sum(1 / r["expected_id_rank"] if r["expected_id_rank"] else 0
                                                       for r in group) / count,
                            "selected_direct_support_count": sum(r["selected_has_direct_support"] for r in group)}
    return {"cases": cases, "labels": labels, "metrics": metrics,
            "human_confirmed": False, "judge_api_calls": 0,
            "rubric": plan["rubric"], "dataset_sha256": plan["dataset_sha256"],
            "scope": "이미 검토한 주제의 새 표현. Codex 잠정 판정. 로컬 3문항은 진단용이며 모델 우위 비교가 아님."}


def main():
    """이전 실행과 이번 실행을 구별하고 새 로컬 결과를 저장합니다."""
    plan = read_json(FOLDER / "dataset.json")
    retrieval = read_json(FOLDER / "retrieval.json")
    drafts = read_json(FOLDER / "review_drafts.json")
    ui = summarize_ui()
    search = summarize_search(plan, retrieval)
    summary = {"evaluation_date": "2026-10-05", "summary_date": "2026-10-06", "report_folder": str(FOLDER.relative_to(ROOT)),
               "dataset_sha256": plan["dataset_sha256"], "code_version": plan["code_version"],
               "source_run_id": plan["source_run_id"], "embedding_run_id": plan["embedding_run_id"],
               "ui": ui, "search": {key: value for key, value in search.items() if key != "labels"},
               "source_review": {"parent_drafts": len(drafts["draft_records"]),
                                 "image_links": len(drafts["draft_image_links"]),
                                 "removed_links": len(drafts["removed_links"]), "applied": drafts["applied"],
                                 "raw_text_preserved": drafts["raw_text_preserved"], "human_confirmed": False},
               "query_embedding_calls": ui["query_embedding_calls"] + retrieval["query_embedding_calls"],
               "generation_calls": ui["generation_calls"], "generation_tokens": ui["total_generation_tokens"],
               "retrieval_elapsed_seconds": retrieval["elapsed_seconds"],
               "db_written": False, "storage_uploaded": False, "document_embeddings_changed": False,
               "failure_scope": "검색 처리 예외 0건. S03/S07 직접 근거 선택은 부적절. 새 10문항의 생성 API는 미실행."}
    # 먼저 모든 출력 경로를 확인해 기존 판정을 재실행으로 덮어쓰지 않도록 합니다.
    outputs = {FOLDER / "ui_checks.json": ui, FOLDER / "relevance_review.json": search,
               PERSONAL / "sequence_summary_20261005.json": summary}
    if any(path.exists() for path in outputs):
        raise FileExistsError("既存の結果があります。変更案は別バージョンで記録してください。")
    for path, value in outputs.items():
        save_new(path, value)
    print(json.dumps({"ui": f"{ui['passed']}/{ui['total']}", "metrics": search["metrics"],
                      "generation_tokens": summary["generation_tokens"], "source_drafts_applied": False},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
