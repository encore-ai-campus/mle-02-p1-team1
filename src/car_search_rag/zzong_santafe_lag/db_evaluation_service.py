"""저장된 전체 자료에서 기존 30문항의 기대 출처를 찾는지 평가합니다."""

# [프로젝트 적용] 11·12번에서 사용한 질문과 기대 출처를 그대로 재사용합니다.
# [프로젝트 추가] 문서 벡터 재계산 없이 DB 검색 결과에 Hit@5·MRR@5를 계산합니다.
# 이미 검색 개선에 사용한 질문이므로 새로운 질문에 대한 독립 평가가 아닙니다.
# 그림 자체의 이해·답변 정확도·복합 질문의 모든 조건 충족 여부는 측정하지 않습니다.

import hashlib
import json
from datetime import datetime, timedelta, timezone
from time import perf_counter

from .db_search_service import DbFullSearchService
from .evaluation import make_cases


def score_candidates(case, search_result, top_k=5):
    """상위 후보 묶음에 기대 원문 ID가 있는지 확인하고 첫 발견 순위를 계산합니다."""
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 10:
        raise ValueError("평가할 후보 수는 1~10 사이의 정수입니다.")
    if search_result["question"] != case["question"]:
        raise ValueError("평가 질문과 검색 결과의 질문이 다릅니다.")
    expected = set(case["expected_ids"])
    if not expected:
        raise ValueError("기대 출처가 없는 질문은 이 검색 평가에 사용할 수 없습니다.")
    ranks, primary_ranks, candidates = [], [], []
    for rank, hit in enumerate(search_result["candidates"][:top_k], start=1):
        # [프로젝트 추가] 현재 화면의 한 후보는 본문과 필수 각주를 함께 읽는 묶음입니다.
        # 페이지 번호만 겹친 다른 주제를 정답으로 세지 않도록 원문 ID로 비교합니다.
        context_ids = {record["record_id"] for record in hit["context_records"]}
        matched = sorted(expected.intersection(context_ids))
        primary_match = hit["parent_record_id"] in expected
        if matched:
            ranks.append(rank)
        if primary_match:
            primary_ranks.append(rank)
        candidates.append({
            "rank": rank, "title": hit["title"],
            "primary_record_id": hit["parent_record_id"],
            "context_record_ids": sorted(context_ids),
            "pdf_pages": sorted({page for record in hit["context_records"]
                                  for page in record["source_pages"]}),
            "matched_expected_ids": matched, "primary_match": primary_match,
            "pending_review_record_ids": hit["pending_review_record_ids"],
        })
    first_rank = ranks[0] if ranks else None
    primary_rank = primary_ranks[0] if primary_ranks else None
    return {
        "case_id": case["case_id"], "question": case["question"],
        "expected_ids": case["expected_ids"], "expected_sources": case["expected_sources"],
        "first_relevant_rank": first_rank,
        "hit_at_k": first_rank is not None,
        # [프로젝트 추가] 1위=1점, 2위=0.5점, 3위=약0.33점, 상위 k개에 없으면0점입니다.
        # 상위 k개 밖의 순위를 모르므로 전체 MRR이 아닌 MRR@k로 이름을 붙입니다.
        "reciprocal_rank_at_k": 1.0 / first_rank if first_rank is not None else 0.0,
        "primary_first_relevant_rank": primary_rank,
        "primary_hit_at_k": primary_rank is not None,
        "primary_reciprocal_rank_at_k": 1.0 / primary_rank if primary_rank is not None else 0.0,
        "candidates": candidates,
    }


class DbRetrievalEvaluationService:
    """개인 DB를 읽어 고정 질문을 준비하고 요청한 질문만 검색·채점합니다."""

    def __init__(self, run_id, method="purpose"):
        """저장 작업과 검색 방식을 고정합니다. 생성만으로 DB·모델을 실행하지 않습니다."""
        self.search_service = DbFullSearchService(run_id, method=method)
        self.cases = None
        self.dataset_sha256 = None

    def prepare_cases(self):
        """모델 없이 저장된 원문을 조회해 기존 질문과 정답 출처의 목록을 만듭니다."""
        if self.cases is not None:
            return self.cases
        service = self.search_service
        with service.repository.session.transaction():
            session = service.repository.session
            params = {"run_id": service.run_id}
            run = session.select_one("manual_store.get_run", params)
            if run is None:
                raise ValueError("평가할 전체 저장 작업을 찾지 못했습니다.")
            counts = session.select_one("manual_store.get_run_search_counts", params)
            document = session.select_one("manual_store.get_document", {"document_id": run["document_id"]})
            service.validate_source(run, document, counts)
            parents = session.select_list("manual_store.get_run_parents", params)
        # 기존 평가 함수가 사용한 딕셔너리 구조로 바꿉니다. PDF 재추출은 하지 않습니다.
        original_cases = make_cases([{"metadata": row["metadata"]} for row in parents])
        by_id = {row["record_id"]: row for row in parents}
        cases = []
        for index, original in enumerate(original_cases, start=1):
            expected_sources = [{
                "record_id": record_id, "title": by_id[record_id]["title"],
                "pdf_pages": by_id[record_id]["source_pages"],
                "manual_start_page": by_id[record_id]["manual_page_number"],
                "verification_status": by_id[record_id]["verification_status"],
            } for record_id in original["expected_ids"]]
            cases.append({**original, "case_id": f"Q{index:02d}", "expected_sources": expected_sources})
        # [프로젝트 추가] 질문과 기대 출처가 같은지 비교할 수 있도록 목록의 식별값을 남깁니다.
        # 이 식별값은 평가 결과를 본 뒤 질문·기대 출처를 바꾸었는지 확인할 때 사용합니다.
        payload = json.dumps(cases, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self.dataset_sha256 = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        self.cases = cases
        return self.cases

    def evaluate_case(self, case_id, top_k=5, progress=print):
        """지정한 질문 하나만 검색하고 기대 출처를 찾은 순위를 채점합니다."""
        cases = self.prepare_cases()
        matches = [case for case in cases if case["case_id"] == case_id]
        if len(matches) != 1:
            raise ValueError("질문 번호는 Q01~Q30 중에서 선택하세요.")
        case = matches[0]
        # [프로젝트 추가] 기대 ID는 검색에 전달하지 않고 검색이 끝난 뒤에만 비교합니다.
        result = self.search_service.search(case["question"], top_k=top_k, progress=progress)
        return score_candidates(case, result, top_k=top_k)

    def evaluate_all(self, top_k=5, progress=print):
        """동일한 30문항을 순서대로 검색하고 점수와 질문별 출처를 메모리에 반환합니다."""
        cases = self.prepare_cases()
        started = perf_counter()
        results = []
        for index, case in enumerate(cases, start=1):
            if progress:
                progress(f"{index}/{len(cases)} | {case['case_id']} | {case['question']}")
            # 실패한 질문을 분모에서 빼면 점수가 높아질 수 있어 오류 시 평가를 중단합니다.
            row = self.evaluate_case(case["case_id"], top_k=top_k, progress=None)
            results.append(row)
            if progress:
                progress(f"  기대 출처 첫 순위: {row['first_relevant_rank'] or '상위 후보에 없음'}")
        service = self.search_service
        hits = sum(row["hit_at_k"] for row in results)
        primary_hits = sum(row["primary_hit_at_k"] for row in results)
        return {
            "phase": "completed", "evaluation_scope": "reused_30_question_retrieval_regression",
            "created_at": datetime.now(timezone(timedelta(hours=9))).isoformat(),
            "run_id": str(service.run_id), "search_method": service.search_method,
            "model_name": service.embedder.model_name, "model_revision": service.embedder.model_revision,
            "dataset_sha256": self.dataset_sha256, "question_count": len(results), "top_k": top_k,
            "metrics": {
                f"Hit@{top_k}": hits / len(results),
                f"MRR@{top_k}": sum(row["reciprocal_rank_at_k"] for row in results) / len(results),
                "hit_question_count": hits,
                f"primary_Hit@{top_k}": primary_hits / len(results),
                f"primary_MRR@{top_k}": sum(row["primary_reciprocal_rank_at_k"] for row in results) / len(results),
            },
            "elapsed_seconds": perf_counter() - started,
            "db_written": False, "storage_uploaded": False, "document_embeddings_recomputed": False,
            "answer_accuracy_measured": False, "image_understanding_measured": False,
            "limitations": [
                "검색 개선에 사용한 기존 30문항이며 독립된 새 질문 평가는 아닙니다.",
                "주 지표는 본문·필수 각주 묶음에 기대 ID가 하나 이상 있는지 셉니다.",
                "primary 지표는 연결 각주를 제외하고 대표 원문의 ID만 비교합니다.",
                "여러 기대 ID 중 하나를 찾았다는 뜻이며 복합 질문 전체의 근거 완성을 뜻하지 않습니다.",
                "MRR@k는 상위 k개 밖의 정답을 0점으로 계산하며 전체 순위의 MRR과 다릅니다.",
                "정답 페이지의 모든 내용·그림·생성 답변의 정확도를 측정한 결과가 아닙니다.",
                "저장 원문과 이미지 참조의 검토 상태는 평가 점수와 별개로 유지합니다.",
            ],
            "results": results,
        }
