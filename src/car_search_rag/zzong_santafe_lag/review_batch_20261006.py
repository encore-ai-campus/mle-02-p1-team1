"""우선 8개 자료의 원문·그림 연결을 읽기 전용으로 조회하고 화면 대조용 이미지를 만듭니다."""

import hashlib
import json
from pathlib import Path

import pymupdf

from .database import PersonalSqlSession
from .source_profile import FULL_SOURCE

FOLDER = Path(__file__).resolve().parent / "source_reviews/20261006_batch2"
ROOT = Path(__file__).resolve().parents[3]
IDS = {"auto_topic_135", "auto_topic_139", "auto_topic_149", "auto_topic_160",
       "auto_topic_274", "auto_topic_276", "auto_topic_420", "auto_topic_73"}


def main():
    """개인 DB에서 8개 자료를 읽고 본문·경계를 원본 화면에서 대조할 기록을 남깁니다."""
    pdf = ROOT / "data/santafe_hev_manual.pdf"
    if hashlib.sha256(pdf.read_bytes()).hexdigest() != FULL_SOURCE.pdf_sha256:
        raise ValueError("원본 PDF의 식별값이 다릅니다.")
    session = PersonalSqlSession(read_only=True)
    with session.transaction():
        parents = session.select_list("manual_store.get_run_parents", {"run_id":FULL_SOURCE.run_id})
        images = session.select_list("manual_store.get_run_image_details", {"run_id":FULL_SOURCE.run_id})
    rows = [r for r in parents if r["record_id"] in IDS]
    assert {r["record_id"] for r in rows} == IDS
    selected = [r for r in images if r["parent_record_id"] in IDS]
    FOLDER.mkdir(parents=True,exist_ok=True)
    payload = {"source_run_id":str(FULL_SOURCE.run_id),"pdf_sha256":FULL_SOURCE.pdf_sha256,
               "records":rows,"images":selected,"db_written":False,"activated":False}
    (FOLDER/"source_snapshot.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    document = pymupdf.open(pdf)
    pages = sorted({p for r in rows for p in r["source_pages"]} | {230,232,238,250,262,265,382,388,660,662,104,113})
    # 개별 그림만으로는 경고나 다음 제목의 경계를 확인할 수 없어 페이지 전체를 렌더링합니다.
    for page in pages:
        document[page-1].get_pixmap(matrix=pymupdf.Matrix(1.8,1.8)).save(FOLDER/f"page_{page}.png")
    print(json.dumps({"records":len(rows),"image_links":len(selected),"rendered_pages":pages,
                      "path":str(FOLDER),"db_written":False,"activated":False},ensure_ascii=False))


if __name__ == "__main__":
    main()
