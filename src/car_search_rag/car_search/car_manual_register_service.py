import logging
import math
import re
import unicodedata
from collections import Counter

from langchain_openai import OpenAIEmbeddings
import pymupdf

from car_search_rag.common.sql_session import SqlSession
from car_search_rag.car_search.car_manual_repository import CarManualRepository
from car_search_rag.common.document_reader import DocumentReader
from car_search_rag.common.storage_manager import StorageManager
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


EMBEDDING_MODEL = "text-embedding-3-small"
machine_logger = logging.getLogger("car_search_rag.car_manual")


class CarManualRegisterService:

    sql_session: SqlSession                    # PDF 등록 과정에서 사용하는 데이터베이스 세션
    repository: CarManualRepository            # 차량 및 매뉴얼 데이터를 저장하는 저장소
    embedding_model: OpenAIEmbeddings          # 매뉴얼 청크 임베딩 생성 모델
    storage_manager: StorageManager            # PDF에서 추출한 이미지를 저장하는 관리자
    document_reader: DocumentReader            # PDF 페이지별 텍스트를 읽는 문서 리더

    def __init__(self, sql_session):
        self.sql_session = sql_session                         # 전달받은 데이터베이스 세션
        self.repository = CarManualRepository(sql_session=self.sql_session)  # DB 작업 저장소
        self.embedding_model = OpenAIEmbeddings(model=EMBEDDING_MODEL)  # 청크 임베딩 모델
        self.storage_manager = StorageManager()                # 이미지 업로드 관리자

    # =========================================================
    # 차량 메뉴얼 PDF 처리 메인 파이프 라인
    # =========================================================
    def insert_pdf_docs(self, file_path, car_brand_nm, car_brand_eng_nm, car_nm, car_eng_nm, car_model_yr):
        """차량 정보부터 PDF 분석과 DB 등록까지 매뉴얼 등록 전체 흐름을 실행한다.

        처리 흐름:
        1. 차량 row를 등록하고 PDF chapter 정보를 읽는다.
        2. page text를 chunk로 나누고 embedding을 생성한다.
        3. PDF 이미지를 추출해 주변 문구 설명과 함께 storage에 올린다.
        4. chapter, chunk, image row를 DB transaction으로 등록한다.

        Returns:
            `(chunk 목록, image metadata 목록)` 형태의 tuple.
        """

        # 매뉴얼 데이터가 연결될 차량 row를 먼저 등록한다.
        car_id = self.insert_car(
            car_brand_nm=car_brand_nm,
            car_brand_eng_nm=car_brand_eng_nm,
            car_nm=car_nm,
            car_eng_nm=car_eng_nm,
            car_model_yr=car_model_yr
        )

        machine_logger.info(f"차량 ID 생성 완료 : {car_id}")

        # PDF 목차와 본문에서 chapter 및 text chunk를 준비한다.
        chapter_list = self._extract_pdf_chapters(file_path)

        chunks = self._extract_and_split_chunks(file_path)

        # 각 chunk의 embedding을 생성한다.
        embedding_list = self._create_chunk_embeddings(chunks=chunks)

        # PDF 이미지를 추출하고 주변 문구를 설명으로 붙여 storage에 업로드한다.
        image_list = self._extract_and_upload_images(file_path=file_path,brand=car_brand_eng_nm,model=car_eng_nm)

        # 이미지 설명 유무와 생성 근거를 집계해 등록 진단에 기록한다.
        description_count = sum(bool(image.get("image_desc")) for image in image_list)

        # 설명 누락 사유와 설명 생성 방식별 건수를 집계한다.
        # region [Python 설명] generator expression과 Counter
        # 괄호 안의 `for ... if ...`는 항목을 하나씩 만드는 generator expression이다.
        # `Counter`는 값을 직접 순회해 항목별 개수를 세므로 중간 list를 만들지 않는다.
        # endregion
        none_reasons = Counter(
            image.get("image_desc_none_reason") or "unspecified"
            for image in image_list
            if not image.get("image_desc")
        )
        source_counts = Counter(
            image.get("image_desc_source_type") or "unspecified"
            for image in image_list
            if image.get("image_desc")
        )

        # 집계 내용을 로그에 남긴다.
        machine_logger.info(
            "IMAGE_DESC summary total=%d described=%d none=%d source_types=%s none_reasons=%s",
            len(image_list), description_count, len(image_list) - description_count,
            dict(source_counts), dict(none_reasons),
        )

        # 준비한 chapter, chunk, embedding, image를 하나의 transaction으로 등록한다.
        self._insert_car_manual_data(
            car_id=car_id,
            chapter_list=chapter_list,
            chunks=chunks,
            embedding_list=embedding_list,
            image_list=image_list
        )

        # 등록 결과를 확인할 수 있도록 요약을 출력한다.
        self._print_summary(chunks, image_list)

        # 호출 측에서 후속 확인에 사용할 준비 결과를 반환한다.
        return chunks, image_list

    # =========================================================
    # PDF 텍스트 추출 및 LangChain Chunk 분할 전담
    # =========================================================
    def _extract_and_split_chunks(self, file_path):
        """PDF page text를 Document로 바꾸고 LangChain splitter로 chunk를 만든다."""

        # PDF page별 text와 metadata를 읽을 DocumentReader를 준비한다.
        self.document_reader = DocumentReader(file_path=file_path)
        self.document_reader.set_pdf_reader()
        self.document_reader.set_pdf_doc_list()

        machine_logger.info(f"PDF Text 읽기 완료 : {len(self.document_reader.doc_list)} 페이지")

        # 페이지별 dict를 LangChain Document 목록으로 변환한다.
        # region [LangChain 설명] Document와 list comprehension
        # `Document`는 본문 `page_content`와 검색/추적용 `metadata`를 함께 담는다.
        # list comprehension은 `doc_list`의 각 dict에서 text와 page 번호를 골라 새 목록을 만든다.
        # endregion
        documents = [
            Document(
                page_content=doc["text"],
                metadata={"page_no": doc["page_no"]}
            )
            for doc in self.document_reader.doc_list
        ]

        # 겹치는 문맥을 유지하도록 문서를 chunk로 나누고 순번을 기록한다.
        splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)
        chunks = splitter.split_documents(documents)

        for chunk_no, chunk in enumerate(chunks, start=1):
            chunk.metadata["chunk_no"] = chunk_no

        machine_logger.info(f"Chunk 분할 완료 : 전체 {len(chunks)}개")
        return chunks

    # =========================================================
    # PDF 내 이미지 추출 및 Supabase 업로드 전담
    # =========================================================
    def _extract_and_upload_images(self, file_path, brand, model):
        """PDF를 page별로 읽어 이미지를 추출하고 설명과 함께 storage에 업로드한다."""
        car_manual_image_list = []

        # PDF 문서를 열고 page별 이미지 위치와 주변 문구를 조사한다.
        # region [Python 설명] with와 context manager
        # `with`는 PDF처럼 사용이 끝난 자원을 정리하는 context manager를 사용한다.
        # 블록을 벗어날 때 문서가 닫히므로 중간에 예외가 발생해도 자원 정리가 보장된다.
        # endregion
        with pymupdf.open(file_path) as pdf_document:
            total_pages = len(pdf_document)
            machine_logger.info(f"이미지 추출 및 Storage 업로드 시작 : 전체 {total_pages} 페이지")

            # 모든 page를 순서대로 확인한다.
            for page_index in range(total_pages):
                page = pdf_document[page_index]
                page_no = page_index + 1
                page_image_list = page.get_images(full=True)

                # page 내 모든 이미지 배치 위치를 모은다.
                # region [Python 설명] 중첩 list comprehension과 enumerate
                # PyMuPDF의 `get_images(full=True)` 결과 각 tuple에서 첫 값은 image xref다.
                # 중첩 comprehension은 각 xref에 해당하는 배치 사각형을 한 list로 모은다.
                # `enumerate(..., start=1)`은 이미지 순번을 1부터 함께 제공한다.
                # endregion
                page_image_rects = [
                    rect
                    for page_image_info in page_image_list
                    for rect in page.get_image_rects(page_image_info[0])
                ]

                # 각 이미지를 설명 생성, 추출, 업로드 순으로 처리한다.
                for image_index, image_info in enumerate(page_image_list, start=1):
                    image_xref = image_info[0]
                    image_rects = page.get_image_rects(image_xref)
                    image_desc_info = self._generate_image_description(
                        page,
                        image_rects,
                        page_image_rects=page_image_rects,
                        page_no=page_no,
                        image_no=image_index,
                        return_details=True,
                    )
                    image_data = self._upload_single_image(
                        pdf_document, image_info, page_no, image_index, brand, model,
                        image_desc=image_desc_info["description"],
                        image_desc_info=image_desc_info,
                    )
                    if image_data:
                        car_manual_image_list.append(image_data)

        # 업로드에 성공한 image metadata 목록을 반환한다.
        return car_manual_image_list

    def _create_chunk_embeddings(self, chunks):
        """각 chunk 본문을 embedding API에 전달해 벡터 목록을 생성한다."""

        machine_logger.info(
            f"Chunk Embedding 생성 시작 : {len(chunks)}개"
        )

        # Document 객체에서 embedding 입력에 필요한 본문만 추린다.
        # region [Python 설명] list comprehension과 객체 attribute
        # comprehension이 `chunks`를 순회하며 각 객체의 `page_content`만 새 list에 담는다.
        # endregion
        chunk_text_list = [
            chunk.page_content
            for chunk in chunks
        ]

        # 본문 목록을 한 번에 embedding 모델에 전달한다.
        embedding_list = self.embedding_model.embed_documents(
            chunk_text_list
        )

        machine_logger.info(
            f"Chunk Embedding 생성 완료 : {len(embedding_list)}개"
        )

        return embedding_list

    # 이미지 설명 helper
    @staticmethod
    def _normalize_image_context_text(text):
        """PDF text span의 공백·장식 기호만 정리하고 실제 문구는 보존한다."""
        # None이나 빈 입력은 빈 문자열로 바꾸고 유니코드 표기를 정규화한다.
        # region [Python 설명] `(value or "")` fallback
        # Python에서 None과 빈 문자열은 falsy이므로 `text or ""`는 둘 다 빈 문자열로 처리한다.
        # endregion
        text = unicodedata.normalize("NFKC", text or "")
        text = re.sub(r"DN8_KO\.book\s+Page\s+\S+", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"^[\s•·▪■▶▷※\-–—]+", "", text).strip()
        # 인코딩이 깨져 한국어/영문 문구를 읽을 수 없는 span은 검색 metadata로 사용하지 않는다.
        if not re.search(r"[가-힣A-Za-z]", text):
            return ""
        return text

    @classmethod
    def _select_nearby_text_blocks(cls, page, image_rect, page_image_rects=()):
        """이미지 위쪽의 같은 열 텍스트를 기하 정보로 정렬해 반환한다.

        글자 크기나 문장 어미는 후보를 탈락시키는 데 쓰지 않는다. font size는
        로그와 동률 순위에만 사용하며, 보조 label도 PDF에 있는 그대로 남긴다.
        """
        if image_rect is None:
            return []

        # 이미지 좌표와 페이지 text block을 읽어 가까운 문구 후보를 찾는다.
        # region [Python 설명] tuple unpacking과 PyMuPDF dict
        # `tuple(image_rect)`의 네 좌표를 한 번에 변수에 나누어 담는 것이 unpacking이다.
        # `_`는 이 함수에서 사용하지 않는 마지막 좌표를 받는다.
        # PyMuPDF의 `get_text("dict")`는 blocks/lines/spans가 중첩된 dict 형태를 반환한다.
        # `.get(key, default)`로 값이 없는 block이나 line도 기본 빈 목록으로 처리한다.
        # generator expression은 `max(..., default=...)`에 값을 순서대로 전달하고,
        # set/list comprehension은 서체 이름과 span flags 목록을 만든다.
        # endregion
        ix0, iy0, ix1, _ = tuple(image_rect)
        image_center_x = (ix0 + ix1) / 2
        image_width = max(ix1 - ix0, 1)
        nearby = []
        text_dict = page.get_text("dict")

        # block/line/span 구조에서 정규화된 text와 bbox를 읽는다.
        for block_index, block in enumerate(text_dict.get("blocks", [])):
            if block.get("type") != 0:
                continue
            for line_index, line in enumerate(block.get("lines", [])):
                spans = line.get("spans", [])
                text = cls._normalize_image_context_text("".join(s.get("text", "") for s in spans))
                if not text:
                    continue
                x0, y0, x1, y1 = line.get("bbox", block.get("bbox", (0, 0, 0, 0)))
                # 이미지와 겹치거나 아래쪽에 있는 문구는 '이미지 앞의 text' 후보가 아니다.
                if y1 > iy0 + 0.5:
                    continue
                overlap = max(0, min(ix1, x1) - max(ix0, x0))
                overlap_ratio = overlap / max(min(ix1 - ix0, x1 - x0), 1)
                center_distance = abs((x0 + x1) / 2 - image_center_x)
                same_column = overlap_ratio >= 0.15 or center_distance <= max(18, image_width * 0.12)
                if not same_column:
                    continue

                # page의 다른 이미지가 더 가까운 문구는 이 이미지 후보에서 제외한다.
                vertical_distance = max(0.0, iy0 - y1)
                if vertical_distance > 140:
                    continue
                # 같은 페이지의 다른 이미지가 이 문구에 더 가까우면 그 이미지에 귀속된 문맥으로 본다.
                other_distances = []
                for other_rect in page_image_rects:
                    if tuple(other_rect) == tuple(image_rect):
                        continue
                    ox0, oy0, ox1, oy1 = tuple(other_rect)
                    other_horizontal_gap = max(x0 - ox1, ox0 - x1, 0)
                    other_vertical_gap = max(oy0 - y1, y0 - oy1, 0)
                    other_distances.append(other_vertical_gap + other_horizontal_gap * 1.8)
                if other_distances and min(other_distances) + 12 < vertical_distance:
                    continue
                # 후보 문구의 위치와 서체 정보를 모아 결과 dict로 보관한다.
                font_size = max((float(s.get("size", 0)) for s in spans), default=0.0)
                font_names = sorted({s.get("font", "") for s in spans if s.get("font")})
                flags = [int(s.get("flags", 0)) for s in spans]
                nearby.append({
                    "text": text,
                    "bbox": (x0, y0, x1, y1),
                    "distance": vertical_distance,
                    "font_size": font_size,
                    "font": " / ".join(font_names),
                    "flags": flags,
                    "same_column": same_column,
                    "horizontal_overlap": overlap_ratio,
                    "block_index": block_index,
                    "line_index": line_index,
                })

        # 가까운 문구를 먼저 두고, 동률이면 크기와 좌우 위치로 정렬한다.
        # 기존 기준은 작은 제목도 후보로 보존한다.
        nearby.sort(key=lambda item: (item["distance"], -item["font_size"], item["bbox"][0]))

        # 거리순 후보 목록을 caller에 반환한다.
        return nearby

    @classmethod
    def _describe_image_context(cls, image_rect, text_blocks):
        """가장 가까운 위쪽 문구와 인접한 상위 제목·label을 조합한다.

        Returns:
            `(설명, 선택 사유, 선택한 text block 목록)` 형태의 tuple.
        """
        if not text_blocks:
            return None, "no_text_above_in_same_column", []

        # 가장 가까운 문구를 기본 설명 후보로 선택한다.
        first = text_blocks[0]
        if re.fullmatch(r"목차를\s*활용하세요[.!?。！]?", first["text"]):
            return None, "table_of_contents_instruction", [first]

        # 짧은 label 바로 위에 상위 제목이 있으면 두 문구를 문서 순서로 묶는다.
        selected = [first]
        if len(first["text"]) <= 20 and len(text_blocks) > 1:
            parent = text_blocks[1]
            vertical_gap = max(0.0, first["bbox"][1] - parent["bbox"][3])
            if (
                parent["text"] != first["text"]
                and len(parent["text"]) <= 64
                and vertical_gap <= 24
            ):
                selected = [parent, first]

        # 선택한 PDF 원문만 연결하고 설명 길이에 저장 상한을 적용한다.
        # region [Python 설명] list comprehension과 순서 보존 중복 제거
        # comprehension은 선택된 block의 text만 새 list에 담는다.
        # `dict.fromkeys(parts)`는 같은 문구를 한 번만 남기면서 원래 순서를 보존한다.
        # `description or None`은 최종 문자열이 비었을 때 None을 반환한다.
        # endregion
        parts = [item["text"] for item in selected]
        description = " / ".join(dict.fromkeys(parts))[:160].rstrip(" /")

        # 설명과 선택 이유, 사용한 원문 block을 함께 반환한다.
        return description or None, ("heading+label" if len(selected) > 1 else "nearest_above_text"), selected

    @classmethod
    def _generate_image_description(
        cls, page, image_rects, page_image_rects=(), page_no=None, image_no=None,
        return_details=False,
    ):
        """이미지 배치별 주변 문구를 평가해 설명과 진단 metadata를 만든다.

        `return_details`가 참이면 설명 외에 선택 사유와 text/image 좌표를 dict로 반환한다.
        기본값에서는 이미지 설명 문자열만 반환한다.
        """
        if not image_rects:
            # 이미지 좌표가 없으면 빈 설명과 누락 사유를 결과 형식에 맞춰 돌려준다.
            result = {
                "description": None,
                "reason": "no_image_bbox",
                "source_text": None,
                "text_bbox": None,
                "image_bbox": None,
                "distance": None,
                "font_size": None,
                "source_type": None,
            }
            return result if return_details else None

        # 동일 이미지가 배치된 위치마다 주변 문구 후보와 거리를 계산한다.
        placements = []
        for image_rect in image_rects:
            candidates = cls._select_nearby_text_blocks(page, image_rect, page_image_rects)
            description, reason, selected = cls._describe_image_context(image_rect, candidates)
            distance = selected[0]["distance"] if selected else float("inf")
            placements.append((distance, tuple(image_rect), description, reason, selected))

        # 가장 가까운 문구가 있는 배치의 상세 값을 한 번에 꺼낸다.
        # region [Python 설명] tuple 비교와 unpacking
        # 각 `placements` 항목은 `(거리, bbox, 설명, 사유, 선택 문구)` tuple이다.
        # `min(..., key=...)`가 고른 tuple의 다섯 값을 왼쪽 변수들에 순서대로 unpacking한다.
        # `key=lambda item: ...`는 어떤 tuple을 먼저 볼지 계산하는 짧은 함수를 전달한다.
        # endregion
        distance, image_bbox, description, reason, selected = min(
            placements, key=lambda item: (item[0], item[1][1], item[1][0])
        )
        source_text = " / ".join(item["text"] for item in selected) if selected else None
        nearest = min(selected, key=lambda item: item["distance"]) if selected else None
        source_type = (
            "heading+label" if len(selected) > 1 else ("heading" if description and selected else None)
        )

        # 선택한 text block에서 로그와 DB metadata에 사용할 요약값을 구성한다.
        # region [Python 설명] generator expression과 조건식
        # `join(item["text"] for item in selected)`은 generator expression으로 text를 하나씩 전달한다.
        # `값 if 조건 else 다른 값`은 조건에 따라 결과를 고르는 Python 조건식이다.
        # 여기서는 description이나 선택 block이 없을 때 None을 사용한다.
        # endregion
        # 문구 유무에 맞춰 성공 또는 누락 진단을 로그에 남긴다.
        if selected and description:
            machine_logger.info(
                "IMAGE_DESC page=%s image=%s desc=%s source=%s text_bbox=%s image_bbox=%s font_size_pt=%s distance_pt=%.2f",
                page_no if page_no is not None else getattr(page, "number", -1) + 1,
                image_no,
                description,
                source_text,
                nearest["bbox"],
                image_bbox,
                nearest["font_size"],
                nearest["distance"],
            )
        else:
            machine_logger.info(
                "IMAGE_DESC page=%s image=%s desc=None reason=%s source=%s text_bbox=%s image_bbox=%s distance_pt=%s font_size_pt=%s",
                page_no if page_no is not None else getattr(page, "number", -1) + 1,
                image_no,
                reason,
                source_text,
                nearest["bbox"] if nearest else None,
                image_bbox,
                nearest["distance"] if nearest else None,
                nearest["font_size"] if nearest else None,
            )
        result = {
            "description": description,
            "reason": reason if description is None else None,
            "source_text": source_text,
            "text_bbox": selected[0]["bbox"] if selected else None,
            "image_bbox": image_bbox,
            "distance": nearest["distance"] if nearest else None,
            "font_size": nearest["font_size"] if nearest else None,
            "source_type": source_type,
        }

        # 호출 옵션에 따라 상세 dict 또는 설명 문자열을 반환한다.
        return result if return_details else description

    def _upload_single_image(
        self, pdf_document, image_info, page_no, image_index, brand, model,
        image_desc=None, image_desc_info=None,
    ):
        """PDF에서 이미지 byte를 추출해 storage에 올리고 DB용 metadata를 반환한다."""
        try:
            # PyMuPDF image tuple의 xref로 실제 이미지 byte와 확장자를 읽는다.
            xref = image_info[0]
            image_data = pdf_document.extract_image(xref)
            image_bytes = image_data["image"]
            image_ext = image_data["ext"]

            image_name = f"page_{page_no:04d}_image_{image_index:02d}.{image_ext}"

            machine_logger.info(
                f"이미지 업로드 시작 : {image_name} ({len(image_bytes):,} bytes)"
            )

            # 추출한 이미지와 차량 정보를 storage upload에 전달한다.
            image_url = self.storage_manager.upload_car_image_bytes(
                image_bytes=image_bytes,
                brand=brand,
                model=model,
                image_name=image_name
            )

            machine_logger.info(f"이미지 업로드 완료 : {image_name}")

            # 업로드 URL과 page/image 번호, 주변 문구 설명을 결과 dict로 묶는다.
            # region [Python 설명] `(value or {})`와 dict.get()
            # `image_desc_info or {}`는 상세 정보가 None이거나 비어 있으면 빈 dict를 사용한다.
            # 그 뒤 `.get()`으로 진단 key를 읽으므로 선택 metadata가 없어도 결과를 구성한다.
            # endregion
            return {
                "page_no": page_no,
                "image_no": image_index,
                "image_xref": xref,
                "image_name": image_name,
                "image_url": image_url,
                "image_desc": image_desc,
                # 아래 설명 근거는 등록 진단/집계용이며 Repository SQL에는 전달하지 않는다.
                "image_desc_source_type": (image_desc_info or {}).get("source_type"),
                "image_desc_none_reason": (image_desc_info or {}).get("reason"),
            }

        # 이미지 하나의 처리 실패는 기록하고 해당 이미지만 건너뛴다.
        except Exception as e:
            machine_logger.exception(
                f"이미지 업로드 실패 : 페이지 {page_no}, 이미지 {image_index} - {e}"
            )
            return None

    def _print_summary(self, chunks, car_manual_image_list):
        """결과 확인 및 디버깅용 출력"""
        for index, chunk in enumerate(chunks[:10]):
            print(f"===== CHUNK {index + 1} =====")
            print("페이지:", chunk.metadata.get("page_no"))
            print("청크 번호:", chunk.metadata.get("chunk_no"))
            print("길이:", len(chunk.page_content))
            print(chunk.page_content)
            print()

        print("전체 Chunk 수:", len(chunks))
        print("전체 이미지 수:", len(car_manual_image_list))

        for car_manual_image in car_manual_image_list[:10]:
            print(car_manual_image)

    # =========================================================
    # 차량 매뉴얼 Chapter / Chunk / Image DB 등록
    # =========================================================
    def _insert_car_manual_data(self,car_id,chapter_list,chunks,embedding_list,image_list):
        """chapter, chunk, image 행을 하나의 DB transaction으로 등록한다.

        chapter를 먼저 저장해 page-to-chapter map을 만든 뒤, 해당 map을 chunk/image
        batch insert에 전달한다. 세 등록 단계는 같은 transaction 안에서 실행된다.
        """

        # chapter, chunk, image 등록을 하나의 DB transaction 경계로 묶는다.
        # region [DB 설명] transaction context manager
        # `with self.sql_session.transaction()`은 transaction context를 연다.
        # 이 블록 안에서 세 등록 단계를 실행해 DB 작업을 같은 transaction 흐름으로 관리한다.
        # Python의 `with`는 블록을 나갈 때 context manager의 정리 동작을 호출한다.
        # endregion
        with self.sql_session.transaction():

            # Repository가 page 번호를 chapter ID에 연결할 수 있도록 map을 준비한다.
            # region [Python 설명] chapter map list/dict
            # `chapter_map`은 chapter 정보를 담은 dict 여러 개의 list다.
            # 각 항목의 start/end page로 검색 page가 속한 chapter를 찾는다.
            # endregion
            chapter_map = []

            # chapter row를 등록하고 page 범위 map을 채운다.
            for chapter_no, chapter in enumerate(chapter_list, start=1):

                chapter_id = self.repository.get_car_manual_chapter_id()

                self.repository.insert_car_manual_chapter(
                    car_id=car_id,
                    car_manual_chapter_id=chapter_id,
                    car_manual_chapter_no=chapter_no,
                    car_manual_chapter_nm=chapter["chapter_nm"],
                    car_manual_chapter_sort_no=chapter_no
                )
                machine_logger.info(
                    f"차량 매뉴얼 Chapter 등록 완료 : {chapter_id}"
                )

                # 생성된 ID와 PDF page 범위를 이후 batch insert에서 사용한다.
                chapter_map.append({
                        "chapter_id": chapter_id,
                        "chapter_nm": chapter["chapter_nm"],
                        "start_page": chapter["start_page"],
                        "end_page": chapter["end_page"]
                    })

                machine_logger.info(
                    f"차량 매뉴얼 Chapter 등록 완료 : "
                    f"{chapter_no}. {chapter['chapter_nm']}"
                )

            # chunk 본문과 embedding을 chapter map에 연결해 batch 등록한다.
            chunk_insert_count = self.repository.insert_car_manual_chunks(
                car_id=car_id,
                chapter_map=chapter_map,
                chunks=chunks,
                embedding_list=embedding_list
            )
            machine_logger.info(
                f"차량 매뉴얼 Chunk 등록 완료 : {chunk_insert_count}개"
            )

            # 업로드된 image metadata도 같은 chapter map에 연결해 등록한다.
            image_insert_count = self.repository.insert_car_manual_images(
                car_id=car_id,
                chapter_map=chapter_map,
                image_list=image_list
            )
            machine_logger.info(
                f"차량 매뉴얼 Image 등록 완료 : {image_insert_count}개"
            )
        # transaction이 끝난 뒤 등록 건수를 기록하고 caller에 반환한다.
        machine_logger.info(
            f"차량 매뉴얼 DB 등록 완료 : "
            f"Chunk {chunk_insert_count}개 / "
            f"Image {image_insert_count}개"
        )

        # Python은 쉼표로 나열한 두 값을 하나의 tuple로 반환한다.
        # region [Python 설명] 여러 값 반환
        # caller는 `(chunk_insert_count, image_insert_count)` tuple을 받을 수 있다.
        # 변수 두 개로 받으면 tuple unpacking으로 각 건수가 나뉜다.
        # endregion
        return chunk_insert_count, image_insert_count

    def get_car_manual_chapter_id(self):
        """차량 매뉴얼 Chapter ID 생성"""
        return self.repository.get_car_manual_chapter_id()

    def insert_car(self,car_brand_nm,car_brand_eng_nm,car_nm,car_eng_nm,car_model_yr):
        car_id = self.repository.insert_car(
            car_brand_nm=car_brand_nm,
            car_brand_eng_nm=car_brand_eng_nm,
            car_nm=car_nm,
            car_eng_nm=car_eng_nm,
            car_model_yr=car_model_yr
        )
        machine_logger.info(f"차량 등록 완료 : {car_id}")
        return car_id

    def insert_car_manual_chapter(self,car_id,car_manual_chapter_id,  car_manual_chapter_no,car_manual_chapter_nm,car_manual_chapter_sort_no):
        self.repository.insert_car_manual_chapter(
            car_id=car_id,
            car_manual_chapter_id=car_manual_chapter_id,
            car_manual_chapter_no=car_manual_chapter_no,
            car_manual_chapter_nm=car_manual_chapter_nm,
            car_manual_chapter_sort_no=car_manual_chapter_sort_no
        )
        machine_logger.info(
            f"차량 매뉴얼 Chapter 등록 완료 : {car_manual_chapter_id}"
        )

    def insert_car_manual_chunks(self,car_id,chapter_map,chunks,embedding_list):
        insert_count = self.repository.insert_car_manual_chunks(
            car_id=car_id,
            chapter_map=chapter_map,
            chunks=chunks,
            embedding_list=embedding_list
        )
        machine_logger.info(
            f"차량 매뉴얼 Chunk 등록 완료 : {insert_count}개"
        )
        return insert_count

    def insert_car_manual_images(self,car_id,chapter_map,image_list):
        """차량 매뉴얼 이미지 정보 DB 등록"""
        insert_count = self.repository.insert_car_manual_images(
            car_id=car_id,
            chapter_map=chapter_map,
            image_list=image_list
        )
        machine_logger.info(
            f"차량 매뉴얼 Image 등록 완료 : {insert_count}개"
        )
        return insert_count

    def _extract_pdf_chapters(self, file_path):
        """PDF 목차의 1레벨 항목을 서로 겹치지 않는 page 범위 chapter로 만든다."""
        chapter_list = []

        # PDF를 열어 목차와 전체 page 수를 읽는다.
        # region [Python 설명] with와 PDF context manager
        # `pymupdf.open()`이 연 PDF document는 context manager로 관리한다.
        # `with` 블록이 끝나면 파일 자원이 정리된다.
        # endregion
        with pymupdf.open(file_path) as pdf_document:

            total_pages = len(pdf_document)

            # PyMuPDF TOC의 `(level, title, page_no)` 중 1레벨 항목만 모은다.
            # region [Python 설명] list comprehension과 tuple unpacking
            # TOC 각 항목은 세 값을 가진 tuple이고 반복문에서 이름 세 개로 나누어 받는다.
            # comprehension은 `level == 1`인 항목만 `(title, page_no)` tuple로 만든다.
            # endregion
            toc_list = [
                (title, page_no)
                for level, title, page_no
                in pdf_document.get_toc(simple=True)
                if level == 1
            ]

            # 각 chapter의 시작 page와 다음 chapter 직전 page를 연결한다.
            # region [Python 설명] enumerate와 tuple unpacking
            # `enumerate(toc_list)`는 index와 현재 tuple을 함께 돌려준다.
            # `(title, start_page)`가 현재 tuple의 두 값을 각각 받는다.
            # endregion
            for index, (title, start_page) in enumerate(toc_list):

                if index + 1 < len(toc_list):
                    end_page = toc_list[index + 1][1] - 1
                else:
                    end_page = total_pages

                chapter_list.append({
                    "chapter_nm": title,
                    "start_page": start_page,
                    "end_page": end_page
                })

        # page 범위가 지정된 chapter 목록을 반환한다.
        return chapter_list
