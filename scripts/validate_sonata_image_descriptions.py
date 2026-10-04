"""Run a non-destructive 4-image Vision sample against the Sonata manual.

This script reads the source PDF, makes read-only DB/Storage snapshots, and
calls the OpenAI Responses API for only the explicitly selected images. It
never calls repository insert methods or Storage upload/delete methods.
"""

from __future__ import annotations

import base64
import argparse
import hashlib
import mimetypes
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI
import pymupdf
from pypdf import PdfReader
from supabase import create_client


ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / "data" / "DN8_2026_ko_KR.pdf"
CAR_ID = "20261004_000015"
VISION_MODEL = "gpt-4.1-mini"
IMAGE_SAMPLES = (
    # Oil level gauge: maintenance/engine diagram.
    {
        "page_no": 463,
        "image_no": 1,
        "label": "엔진 오일 점검 그림",
        "keywords": ("엔진 오일", "오일량"),
        "previous_desc": "현대 쏘나타 2026년형 엔진룸 내 엔진 오일 레벨 게이지 위치 및 오일량 확인 모습",
    },
    # The second image on the USB page depicts the rear console ports.
    {
        "page_no": 236,
        "image_no": 2,
        "label": "USB 단자 위치 그림",
        "keywords": ("USB 충전 단자", "뒷좌석"),
        "previous_desc": "현대 쏘나타 2026년형 뒷좌석 센터 콘솔 하단에 위치한 듀얼 USB-C 충전 포트.",
    },
    # Tire tread wear indicator: safety/maintenance diagram.
    {
        "page_no": 479,
        "image_no": 1,
        "label": "타이어 마모 표시 그림",
        "keywords": ("타이어 교체", "마모한도"),
        "previous_desc": "타이어 트레드 중앙에 위치한 마모한도 표시밴드[A] 모습.",
    },
    # Compact warning pictogram is an abstention/low-detail control sample.
    {
        "page_no": 468,
        "image_no": 1,
        "label": "안전 경고 pictogram",
        "keywords": ("냉각팬", "경고"),
        "previous_desc": "냉각팬 작동 시 손을 대지 말라는 경고 표시와 주의 안내 아이콘.",
    },
    # A repeated, tiny chevron that is not independently meaningful.
    {
        "page_no": 386,
        "image_no": 3,
        "label": "저정보 작은 화살표 fragment",
        "keywords": ("후방 주차 가이드", "가이드라인"),
        "previous_desc": None,
        "use_page_context": False,
    },
)


def _load_configuration() -> None:
    load_dotenv(dotenv_path=ROOT / ".env")
    required = ("DB_URL", "SUPABASE_URL", "SUPABASE_SECRET_KEY", "OPENAI_API_KEY")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError("필요한 환경변수가 설정되지 않았습니다: " + ", ".join(missing))


def _extract_page_text(page_no: int) -> str:
    # DocumentReader.set_pdf_doc_list()와 동일하게 pypdf page.extract_text() 사용.
    page = PdfReader(PDF_PATH).pages[page_no - 1]
    return page.extract_text() or ""


def _context_excerpt(text: str, keywords: tuple[str, ...], limit: int = 280) -> str:
    flattened = re.sub(r"\s+", " ", text).strip()
    lowered = flattened.lower()
    for keyword in keywords:
        position = lowered.find(keyword.lower())
        if position >= 0:
            start = max(0, position - 90)
            return flattened[start : start + limit]
    return flattened[:limit]


def _describe_image(
    client: OpenAI,
    *,
    image_bytes: bytes,
    image_ext: str,
    page_text: str,
    page_no: int,
    image_no: int,
) -> str | None:
    mime_type = mimetypes.types_map.get(f".{image_ext.lower()}") or "image/png"
    data_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
    prompt = f"""너는 차량 매뉴얼 이미지의 검색용 캡션을 작성한다.
차량: Hyundai Sonata 2026
PDF 물리 페이지: {page_no}
페이지 본문(용어 확인용 문맥이며, 이미지에 보이지 않는 정보를 주장하지 말 것):
{page_text}

이미지와 페이지 본문에서 명확히 확인되는 사실만 짧은 한국어 한 문장으로 설명하라.
페이지 본문은 이미지에서 실제로 보이는 대상의 용어를 확인하는 데만 참고하라. 본문만으로 알 수 있고 이미지에서는 확인되지 않는 절차, 기능, 위험 원인, 수치, 규격은 설명에 넣지 말라.
이미지와 본문이 충돌하면 이미지에서 실제로 보이는 내용만 사용하라.
차량명과 연식은 반복하지 말라. 규격, 수치, 부품명, 위치를 모양만 보고 추측하지 말라.
본문이 단순히 'USB'라고 하면 'USB-C' 등 구체 규격으로 확대 해석하지 말라.
확신할 수 없는 세부 사항은 생략하고 일반적인 표현을 사용하라.
장식, 로고, 의미 없는 선/배경, 매우 작은 fragment처럼 검색에 도움이 되지 않거나 문맥 없이 독립적으로 식별할 수 없는 이미지는 정확히 NONE만 출력하라.
작은 fragment는 페이지 문맥이 있다고 해서 의미 있는 장면으로 승격하지 말라. 이미지 자체에서 대상이나 기능을 알아볼 수 없으면 NONE을 출력하라.
이미지 자체가 일반적인 방향 화살표, 단순 선, UI 표식 하나뿐이고 차량 부품/기능/안전 pictogram을 식별할 수 없다면 그 표식의 페이지상 역할을 추론하지 말고 NONE을 출력하라.
단, 경고 pictogram처럼 식별 가능한 안전 의미가 있는 아이콘은 그 의미를 간결하게 설명하라."""
    response = client.responses.create(
        model=VISION_MODEL,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": data_url, "detail": "high"},
                ],
            }
        ],
        max_output_tokens=120,
    )
    description = (response.output_text or "").strip()
    if not description or description == "NONE":
        return None
    return description


def _db_snapshot() -> dict[str, Any]:
    # DatabaseManager uses the project's configured pool; the transaction is
    # explicitly read-only before any SELECT is issued.
    from car_search_rag.common.database_manager import DatabaseManager

    manager = DatabaseManager()
    try:
        with manager.connect(camel_case_keys=False) as connection:
            with connection.transaction():
                connection.execute("SET TRANSACTION READ ONLY")
                rows = {}
                for name, table in (
                    ("car", "public.car"),
                    ("chapter", "public.car_manual_chapter"),
                    ("chunk", "public.car_manual_chunk"),
                    ("image", "public.car_manual_image"),
                ):
                    rows[name] = connection.execute(
                        f"SELECT count(*) AS n FROM {table} WHERE car_id = %s", (CAR_ID,)
                    ).fetchone()["n"]
                vector = connection.execute(
                    """SELECT count(*) FILTER (WHERE car_manual_chunk_embed_vec IS NOT NULL) AS embedding,
                              count(*) FILTER (WHERE car_manual_chunk_embed_vec IS NULL) AS embedding_null,
                              min(vector_dims(car_manual_chunk_embed_vec)) AS dimension_min,
                              max(vector_dims(car_manual_chunk_embed_vec)) AS dimension_max
                       FROM public.car_manual_chunk WHERE car_id = %s""",
                    (CAR_ID,),
                ).fetchone()
                rows.update(
                    embedding=vector["embedding"],
                    embedding_null=vector["embedding_null"],
                    dimension_min=vector["dimension_min"],
                    dimension_max=vector["dimension_max"],
                )
        return rows
    finally:
        manager.close()


def _storage_object_count() -> int:
    client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])
    bucket = client.storage.from_("images")
    prefix = "cars/hyundai/sonata"
    offset = 0
    limit = 1000
    total = 0
    while True:
        page = bucket.list(prefix, {"limit": limit, "offset": offset})
        object_count = sum(
            1 for item in page
            if item.get("id") is not None or item.get("metadata") is not None
        )
        total += object_count
        if len(page) < limit:
            return total
        offset += limit


def _pdf_image_hashes() -> tuple[int, int, int]:
    counts: Counter[str] = Counter()
    total = 0
    with pymupdf.open(PDF_PATH) as document:
        for page in document:
            for image_info in page.get_images(full=True):
                extracted = document.extract_image(image_info[0])
                image_hash = hashlib.sha256(extracted["image"]).hexdigest()
                counts[image_hash] += 1
                total += 1
    unique = len(counts)
    return total, unique, total - unique


def _selected_samples(sample_keys: set[tuple[int, int]] | None = None) -> list[dict[str, Any]]:
    samples = []
    reader = PdfReader(PDF_PATH)
    with pymupdf.open(PDF_PATH) as document:
        for selected in IMAGE_SAMPLES:
            page_no = selected["page_no"]
            image_no = selected["image_no"]
            if sample_keys is not None and (page_no, image_no) not in sample_keys:
                continue
            page = document[page_no - 1]
            image_refs = page.get_images(full=True)
            if len(image_refs) < image_no:
                raise RuntimeError(f"샘플 이미지 없음: page={page_no}, image_no={image_no}")
            image_info = image_refs[image_no - 1]
            extracted = document.extract_image(image_info[0])
            image_bytes = extracted["image"]
            page_text = reader.pages[page_no - 1].extract_text() or ""
            samples.append(
                {
                    **selected,
                    "image_bytes": image_bytes,
                    "image_ext": extracted["ext"],
                    "width": extracted.get("width"),
                    "height": extracted.get("height"),
                    "sha256": hashlib.sha256(image_bytes).hexdigest(),
                    "page_text": page_text,
                    "excerpt": _context_excerpt(page_text, selected["keywords"]),
                }
            )
    return samples


def main() -> int:
    # Windows console 기본 cp949는 모델 설명의 일부 Unicode 문자를 출력하지 못할 수 있다.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _load_configuration()
    if not PDF_PATH.is_file():
        raise FileNotFoundError(PDF_PATH)

    parser = argparse.ArgumentParser(description="비파괴 Sonata 이미지 설명 샘플 검증")
    parser.add_argument(
        "--sample",
        nargs=2,
        action="append",
        type=int,
        metavar=("PAGE_NO", "IMAGE_NO"),
        help="이 페이지만 재검증. 생략하면 정의된 5개 샘플을 모두 실행합니다.",
    )
    args = parser.parse_args()
    selected_keys = {(page_no, image_no) for page_no, image_no in args.sample} if args.sample else None

    before_db = _db_snapshot()
    before_storage = _storage_object_count()
    if before_db["car"] != 1 or before_db["chapter"] != 10 or before_db["chunk"] != 947 or before_db["image"] != 955:
        raise RuntimeError(f"DB 사전 상태가 예상과 다릅니다: {before_db}")
    if before_storage != 955:
        raise RuntimeError(f"Storage 사전 object 수가 예상과 다릅니다: {before_storage}")

    total_images, unique_hashes, duplicate_images = _pdf_image_hashes()
    samples = _selected_samples(selected_keys)
    client = OpenAI()
    cache: dict[str, str | None] = {}

    print(f"Vision API: OpenAI Responses API / {VISION_MODEL}")
    print("Read-only DB baseline:", before_db)
    print("Read-only Storage baseline objects:", before_storage)
    for index, sample in enumerate(samples, start=1):
        key = sample["sha256"]
        error = None
        if key in cache:
            description = cache[key]
            print(f"\n[Sample {index}] hash cache hit; API 호출 생략")
        else:
            try:
                description = _describe_image(
                    client,
                    image_bytes=sample["image_bytes"],
                    image_ext=sample["image_ext"],
                    page_text=(sample["page_text"] if sample.get("use_page_context", True) else ""),
                    page_no=sample["page_no"],
                    image_no=sample["image_no"],
                )
                cache[key] = description
            except Exception as exc:  # continue other samples on API failure
                description = None
                safe_message = str(exc).replace(os.environ["OPENAI_API_KEY"], "[redacted]")
                error = f"{type(exc).__name__}: {safe_message}"
                cache[key] = None

        print(f"\n[Sample {index}] {sample['label']}")
        print(f"page={sample['page_no']} image_no={sample['image_no']}")
        print(f"size={sample['width']}x{sample['height']} {len(sample['image_bytes'])} bytes; sha256={sample['sha256']}")
        print("page excerpt:", sample["excerpt"])
        print("previous_desc:", repr(sample.get("previous_desc")))
        print("image_desc:", repr(description))
        print("is_none:", description is None)
        if error:
            # Keep diagnostics useful without including request headers/secrets.
            print("API error:", error[:300])

    after_db = _db_snapshot()
    after_storage = _storage_object_count()
    print("\nPDF image references:", total_images)
    print("Unique image hashes:", unique_hashes)
    print("Duplicate image references:", duplicate_images)
    print("Read-only DB after:", after_db)
    print("Read-only Storage after objects:", after_storage)
    print("DB unchanged:", before_db == after_db)
    print("Storage count unchanged:", before_storage == after_storage)
    return 0 if before_db == after_db and before_storage == after_storage else 2


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "src"))
    raise SystemExit(main())
