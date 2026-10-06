"""저장 전 수정안으로 실제 검색을 확인하고, 저장 후에는 DB에서 같은 버전을 대조합니다."""

import argparse
import json
import re
from pathlib import Path

from .answer_service import ManualAnswerService
from .db_search_service import DbFullSearchService
from .llm_answer_service import LlmManualAnswerService
from .openai_embedding import OpenAIEmbedder
from .openai_search_service import OpenAIManualSearchService, active_embedding_run
from .post_refactor_checks import FOLDER as OLD_FOLDER
from .review_revision import FOLDER, validate_bundle
from .review_revision_store import BUNDLE_FILE, write_new
from .source_profile import FULL_SOURCE


ADDITIONAL = [
    ("R01", "스마트 테일게이트를 켜는 설정 메뉴와 작동 조건은 무엇인가요?", "auto_topic_172", ["차량", "도어", "스마트 테일게이트", "15", "3"]),
    ("R02", "스마트 테일게이트의 뒤쪽 감지 범위는 몇 cm인가요?", "auto_topic_174", ["50", "100"]),
    ("R03", "스마트 테일게이트 감지 중 중지할 때 키의 번호별 버튼을 알려줘.", "auto_topic_173", ["1:", "2:", "3:", "4:"]),
    ("R04", "실외 미러 조절 스위치의 L과 R은 무엇을 선택하나요?", "auto_topic_150", ["L", "R"]),
    ("R05", "후진 시 실외 미러 자동 조절 기능은 모든 사양에 있나요?", "auto_topic_150", ["사양 적용 시"]),
    ("R06", "실외 미러는 주행 중 접거나 조절해도 되나요?", "auto_topic_150", ["주행 중", "조절", "접"]),
    ("R07", "지금 내 차가 리콜 대상이야?", None, []),
    ("R08", "에어클리너 필터 점검 및 교체 방법을 알려줘.", None, []),
]


def run_preflight(version="v1"):
    """기존 새 표현 10개와 추가 조건 8개를 확인합니다. 원문·벡터는 DB에 저장하지 않습니다."""
    suffix = "" if version == "v1" else "_v2"
    target = FOLDER / f"preflight_20261006{suffix}.json"
    if target.exists():
        return json.loads(target.read_text(encoding="utf-8"))
    started = FOLDER / f"preflight_started{suffix}.json"
    if started.exists():
        raise ValueError("미완료 평가 기록이 있습니다. 자동 API 재호출은 하지 않습니다.")
    bundle = validate_bundle(json.loads(BUNDLE_FILE.read_text(encoding="utf-8")))
    plan = json.loads((OLD_FOLDER / "dataset.json").read_text(encoding="utf-8"))
    cases = [{"id": c["case_id"], "question": c["question"], "record_id": c["anchor"]["record_id"], "phrases": []}
             for c in plan["cases"]]
    cases += [{"id": i, "question": q, "record_id": identity, "phrases": phrases}
              for i, q, identity, phrases in ADDITIONAL]
    write_new(started, {"revision_id": bundle["revision_id"], "cases": cases})
    # [프로젝트 추가] 평가에서만 질문을 한 배치로 임베딩해 왕복 요청 수를 줄입니다.
    # 운영 검색은 질문 하나를 임베딩합니다. 질문별 정답/출처 ID는 API 입력이나 순위에 넣지 않습니다.
    texts = [c["question"] for c in cases if c["id"] != "R07"]
    cache = FOLDER / "preflight_query_vectors.json"
    batches = 0
    if cache.exists():
        import numpy as np
        saved_vectors = json.loads(cache.read_text(encoding="utf-8"))
        if set(saved_vectors) != set(texts):
            raise ValueError("같은 질문 임베딩 체크포인트가 아닙니다.")
        query_vectors = {q: np.asarray(v, dtype=np.float32) for q, v in saved_vectors.items()}
        if any(v.shape != (1536,) or not np.isclose(np.linalg.norm(v), 1, atol=1e-5) for v in query_vectors.values()):
            raise ValueError("질문 벡터 체크포인트가 올바르지 않습니다.")
    else:
        vectors = OpenAIEmbedder().embed_texts(texts)
        query_vectors = dict(zip(texts, vectors))
        write_new(cache, {q: v.tolist() for q, v in query_vectors.items()})
        batches = 1
    search = OpenAIManualSearchService(active_embedding_run())
    search.review_bundle = bundle
    search.prepare()
    search.embedder.embed_question = lambda question: query_vectors[question]
    service = ManualAnswerService(FULL_SOURCE.run_id, search_service=search)
    rows = []
    for case in cases:
        evidence = service.answer(case["question"], top_k=5)
        content = " ".join(r["quote"] for r in evidence["sources"])
        normalized = re.sub(r"\s+", "", content)
        source_ids = [r["record_id"] for r in evidence["sources"]]
        if case["id"] == "R07":
            passed = evidence["status"] == "outside_pdf_scope" and not evidence["retrieval_performed"]
        elif case["id"] == "R08":
            passed = evidence["status"] == "needs_review" and not evidence["sources"]
        else:
            passed = (evidence["status"] == "evidence_excerpt" and case["record_id"] in source_ids
                      and all(re.sub(r"\s+", "", phrase) in normalized for phrase in case["phrases"]))
        rows.append({**case, "passed": passed, "evidence": evidence})
        print(f"{len(rows)}/18 {case['id']} | {evidence['status']} | 조건={passed}", flush=True)
    # 저장 전 이 지역 변수의 수정 버전으로 시험합니다. 화면·원격 DB의 활성 버전은 바꾸지 않습니다.
    local = DbFullSearchService(FULL_SOURCE.run_id, method="purpose_specific")
    local.review_bundle = bundle
    local_service = ManualAnswerService(FULL_SOURCE.run_id, search_service=local)
    local_rows = []
    for case in (cases[2], cases[6], cases[10]):
        evidence = local_service.answer(case["question"], top_k=5)
        passed = case["record_id"] in [r["record_id"] for r in evidence["sources"]]
        local_rows.append({**case, "passed": passed, "evidence": evidence})
        print(f"로컬 {case['id']} | 조건={passed}", flush=True)
    llm = LlmManualAnswerService(FULL_SOURCE.run_id, evidence_service=service, image_display_location="관련 그림 탭")
    generated = []
    generation_calls = 0
    previous = json.loads((FOLDER / "preflight_20261006.json").read_text(encoding="utf-8")) if version == "v2" else None
    # 고친 두 질문의 생성 결과만 확인합니다. 테스트 답을 운영 프롬프트에 추가하지 않습니다.
    for index in (2, 6):
        evidence = rows[index]["evidence"]
        if not rows[index]["passed"]:
            continue
        # 두 질문의 원문·프롬프트 입력이 같을 때만 이전 생성 결과를 재사용합니다.
        # 재사용 결과를 새 생성 호출의 성공·토큰으로 세지 않습니다.
        old = next((r["result"] for r in previous["generated"] if r["case_id"] == rows[index]["id"]), None) if previous else None
        reused = bool(old and old.get("evidence_excerpt") == evidence["answer"] and old["question"] == evidence["question"])
        if reused:
            answer = old
        else:
            answer = llm.generate(evidence)
            generation_calls += 1
        expected_word = "18" if index == 2 else "출발"
        generated.append({"case_id": rows[index]["id"], "result": answer,
                          "reused": reused,
                          "passed": answer["status"] == "generated_answer" and expected_word in answer["answer"]})
        print(f"생성 {rows[index]['id']} | {answer['status']}", flush=True)
    result = {"date": "2026-10-06", "revision_id": bundle["revision_id"], "openai": rows, "local": local_rows,
              "version": version, "generated": generated, "question_embedding_api_batches": batches,
              "question_embedding_inputs": len(texts) if batches else 0, "cached_question_vectors": len(texts) if not batches else 0,
              "generation_calls": generation_calls, "generation_tokens": sum((r["result"].get("token_usage") or {}).get("total_tokens", 0) for r in generated if not r["reused"]),
              "passed": sum(r["passed"] for r in rows), "total": len(rows),
              "local_passed": sum(r["passed"] for r in local_rows),
              "all_passed": all(r["passed"] for r in rows + local_rows + generated) and len(generated) == 2,
              "db_written": False, "storage_uploaded": False,
              "scope": "새 코드·수정안의 조건 회귀 확인. 사람의 의미 정확도 교차 평가나 전체 PDF 성능이 아님."}
    write_new(target, result)
    return result


def readback():
    """저장 후 앱과 같은 활성 DB 버전으로 검색합니다. 문서 재임베딩·DB 쓰기는 없습니다."""
    target = FOLDER / "readback_search_20261006.json"
    if target.exists():
        return json.loads(target.read_text(encoding="utf-8"))
    service = ManualAnswerService(FULL_SOURCE.run_id,
        search_service=OpenAIManualSearchService(active_embedding_run()))
    results = []
    for case_id, question in (("S03", "차량 내부 I 그림에서 지문 인증 기능에 붙은 번호를 알려줘."),
                             ("R01", ADDITIONAL[0][1]), ("R03", ADDITIONAL[2][1])):
        evidence = service.answer(question, top_k=5)
        results.append({"case_id": case_id, "evidence": evidence})
        print(case_id, evidence["status"], [r["title"] for r in evidence["sources"]], flush=True)
    result = {"results": results, "query_embedding_calls": 3, "db_written": False, "storage_uploaded": False}
    write_new(target, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="수정 버전 저장 전/후 확인")
    parser.add_argument("action", choices=("preflight", "preflight-v2", "readback"))
    args = parser.parse_args()
    try:
        result = (run_preflight("v2" if args.action == "preflight-v2" else "v1")
                  if args.action.startswith("preflight") else readback())
        print(json.dumps({k: result[k] for k in ("passed", "total", "local_passed", "all_passed", "generation_tokens") if k in result}, ensure_ascii=False))
    except Exception as error:
        print(f"확인 중단: {type(error).__name__}. 외부 오류 전문은 숨깁니다.", flush=True)
        raise SystemExit(1) from None
