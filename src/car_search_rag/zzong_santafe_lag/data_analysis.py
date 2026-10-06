"""싼타페 저장 자료를 읽기 전용으로 분석하고 재현 가능한 요약을 만듭니다."""

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .answer_service import REVIEWED_STATUSES
from .database import PersonalSqlSession
from .db_search_service import DbFullSearchService
from .review_revision import load_active, combine
from .source_profile import FULL_SOURCE

OUTPUT = Path(__file__).resolve().parent / "analysis_results"


def collect_summary():
    """개인 저장 버전과 활성 검토 자료를 읽습니다. 임베딩·검색·생성·DB 쓰기는 없습니다."""
    session = PersonalSqlSession(read_only=True)
    with session.transaction():
        params = {"run_id": FULL_SOURCE.run_id}
        run = session.select_one("manual_store.get_run", params)
        if not run:
            raise ValueError("분석할 개인 저장 버전이 없습니다.")
        document = session.select_one("manual_store.get_document", {"document_id": run["document_id"]})
        counts = session.select_one("manual_store.get_run_search_counts", params)
        DbFullSearchService(FULL_SOURCE.run_id).validate_source(run, document, counts)
        parents = session.select_list("manual_store.get_run_parents", params)
        chunks = session.select_list("manual_store.get_run_chunks", params)
        images = session.select_list("manual_store.get_run_image_details", params)
        bundle = load_active(session)
    # 검색과 같은 활성 검토 버전을 적용합니다. 읽은 벡터·원문 전체는 결과 파일에 저장하지 않습니다.
    parents, chunks, images = combine(bundle, parents, chunks, images, "local")
    parent_ids = {row["record_id"] for row in parents}
    chunk_counts = Counter(row["metadata"].get("parent_record_id") for row in chunks)
    rows = [{"record_id": row["record_id"], "title": row["title"],
             "content_type": row["content_type"], "verification_status": row["verification_status"],
             "characters": len(row["content"]), "chunks": chunk_counts[row["record_id"]],
             "source_pages": row.get("source_pages", [])} for row in parents]
    frame = pd.DataFrame(rows)
    pages = [page for row in rows for page in set(row["source_pages"])
             if type(page) is int and 1 <= page <= FULL_SOURCE.page_count]
    exact = Counter(hashlib.sha256(row["content"].encode("utf-8")).hexdigest() for row in parents)
    quality = {
        "empty_content": sum(not row["content"].strip() for row in parents),
        "empty_title": sum(not row["title"].strip() for row in parents),
        "missing_pages": sum(not row["source_pages"] for row in rows),
        "invalid_pages": sum(type(page) is not int or not 1 <= page <= FULL_SOURCE.page_count
                             for row in rows for page in row["source_pages"]),
        "duplicate_record_ids": len(rows) - len(parent_ids),
        "exact_duplicate_content_excess": sum(n - 1 for n in exact.values() if n > 1),
        "orphan_chunks": sum(row["metadata"].get("parent_record_id") not in parent_ids for row in chunks),
        "parents_without_chunks": sum(row["chunks"] == 0 for row in rows),
    }
    reviewed = sum(row["verification_status"] in REVIEWED_STATUSES for row in rows)
    correlation = frame["characters"].rank().corr(frame["chunks"].rank())
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(), "source_run_id": str(FULL_SOURCE.run_id),
        "pdf_sha256": document["file_sha256"], "review_revision_id": bundle["revision_id"] if bundle else None,
        "counts": {"pdf_pages": FULL_SOURCE.page_count, "base_parents": counts["parent_count"],
                   "base_chunks": counts["chunk_count"], "effective_parents": len(rows),
                   "effective_chunks": len(chunks), "linked_unique_images": len({str(row["id"]) for row in images}),
                   "image_links": len(images), "reviewed_parents": reviewed,
                   "unreviewed_parents": len(rows) - reviewed, "parent_referenced_pages": len(set(pages))},
        "type_counts": dict(Counter(row["content_type"] for row in rows)),
        "review_counts": dict(Counter(row["verification_status"] for row in rows)),
        "length_statistics": frame[["characters", "chunks"]].describe().round(2).to_dict(),
        "length_chunk_rank_correlation": round(float(correlation), 4) if pd.notna(correlation) else None,
        "quality_checks": quality, "parents": rows,
        "db_written": False, "embedding_calls": 0, "generation_calls": 0,
        "limitations": ["단일 설명서의 저장 자료 분석이며 차량 이용자의 행동 통계가 아닙니다.",
                        "검토된 부모 비율은 답변 정확도나 전체 PDF 검토 완료율이 아닙니다.",
                        "쪽수 집계는 부모 자료가 참조한 페이지이며 추출 성공률이 아닙니다.",
                        "문자 수와 청크 수의 순위 상관은 인과관계나 검색 품질을 입증하지 않습니다.",
                        "같은 글 중복은 정상 반복 경고일 수 있어 자동으로 삭제하지 않습니다.",
                        "단일 설명서 전체 저장 목록의 기술 통계입니다. 모집단 추론용 가설 검정은 하지 않았습니다."]}
    return summary


def report_text(summary):
    """실측 건수와 한계를 함께 적은 간단한 분석 보고서를 만듭니다."""
    c = summary["counts"]
    reviewed_rate = 100 * c["reviewed_parents"] / c["effective_parents"]
    lines = ["# 싼타페 HEV 설명서 데이터 분석", "", f"조회 시각(UTC): {summary['created_at']}",
             f"원문 버전: `{summary['source_run_id']}` · 검토 버전: `{summary['review_revision_id']}`", "",
             "## 수집·분석 범위", "", "개인 DB의 저장 자료와 활성 검토 버전을 읽기 전용으로 집계했습니다.", "",
             "| 항목 | 실측 건수 |", "|---|---:|"]
    labels = {"base_parents":"기본 부모", "base_chunks":"기본 청크", "effective_parents":"현재 부모",
              "effective_chunks":"현재 청크", "linked_unique_images":"연결된 고유 그림", "image_links":"그림 연결",
              "reviewed_parents":"검토된 부모", "unreviewed_parents":"미검토 부모"}
    lines += [f"| {label} | {c[key]} |" for key, label in labels.items()]
    lines += ["", "## 데이터 특징 및 다음 작업", "",
              f"- 검토된 부모는 {c['reviewed_parents']}/{c['effective_parents']}개({reviewed_rate:.1f}%)입니다. 미검토 자료는 답변 보류 및 원문 제공 대상으로 관리합니다.",
              f"- 부모 본문 문자 수 중앙값은 {summary['length_statistics']['characters']['50%']}자입니다. 긴 본문은 짧은 검색 청크와 전체 연결 문맥을 함께 사용하는 이유가 됩니다.",
              f"- 본문 길이와 청크 수의 순위 상관계수는 {summary['length_chunk_rank_correlation']}입니다. 검색 성능 개선 여부는 별도 평가가 필요합니다.",
              "", "## 자료 유형", "", "| 유형 | 개수 |", "|---|---:|"]
    lines += [f"| {kind} | {count} |" for kind, count in summary["type_counts"].items()]
    lines += ["", "## 기술 통계", "", pd.DataFrame(summary["length_statistics"]).to_string(),
              "", "## 품질 점검", "", "아래 숫자는 해당 문제 또는 점검 대상의 건수입니다.", ""]
    lines += [f"- {key}: {value}" for key, value in summary["quality_checks"].items()]
    lines += ["", "## 한계", ""] + [f"- {text}" for text in summary["limitations"]]
    lines += ["", "## 재현", "", "프로젝트 루트에서 `python -m car_search_rag.zzong_santafe_lag.data_analysis` 실행(PYTHONPATH=src).",
              "결과 JSON을 읽는 대시보드·노트북에서는 DB·모델 호출이 없습니다.", ""]
    return "\n".join(lines)


def main():
    """요약 JSON·분석 보고서만 개인 폴더에 저장합니다. DB 연결 오류의 상세 정보는 출력하지 않습니다."""
    try:
        summary = collect_summary()
    except Exception as error:
        print(f"분석 조회 실패: {type(error).__name__}")
        raise SystemExit(1) from None
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT / "report.md").write_text(report_text(summary), encoding="utf-8")
    print(json.dumps({"counts": summary["counts"], "quality_checks": summary["quality_checks"],
                      "db_written": False, "embedding_calls": 0, "generation_calls": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
