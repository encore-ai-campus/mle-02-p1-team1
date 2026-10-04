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

    # =========================================================
    # 인스턴스 변수
    # =========================================================

    sql_session: SqlSession                    # PDF 등록 과정에서 사용하는 데이터베이스 세션
    repository: CarManualRepository            # 차량 및 매뉴얼 데이터를 저장하는 저장소
    embedding_model: OpenAIEmbeddings          # 매뉴얼 청크 임베딩 생성 모델
    storage_manager: StorageManager            # PDF에서 추출한 이미지를 저장하는 관리자
    document_reader: DocumentReader            # PDF 페이지별 텍스트를 읽는 문서 리더

    # =========================================================
    # 생성자
    # =========================================================

    def __init__(self, sql_session):
        self.sql_session = sql_session                         # 전달받은 데이터베이스 세션
        self.repository = CarManualRepository(sql_session=self.sql_session)  # DB 작업 저장소
        self.embedding_model = OpenAIEmbeddings(model=EMBEDDING_MODEL)  # 청크 임베딩 모델
        self.storage_manager = StorageManager()                # 이미지 업로드 관리자

    # =========================================================
    # 차량 메뉴얼 PDF 처리 메인 파이프 라인
    # =========================================================
    def insert_pdf_docs(self, file_path, car_brand_nm, car_brand_eng_nm, car_nm, car_eng_nm, car_model_yr):
        """차량 매뉴얼 PDF 처리 메인 파이프라인"""

        # =========================================================
        # 1. 차량 정보 등록
        # =========================================================
        car_id = self.insert_car(
            car_brand_nm=car_brand_nm,
            car_brand_eng_nm=car_brand_eng_nm,
            car_nm=car_nm,
            car_eng_nm=car_eng_nm,
            car_model_yr=car_model_yr
        )

        machine_logger.info(f"차량 ID 생성 완료 : {car_id}")

        chapter_list = self._extract_pdf_chapters(file_path)


        chunks = self._extract_and_split_chunks(file_path)      # 2. 텍스트 추출 및 청크 생성

        embedding_list = self._create_chunk_embeddings(chunks=chunks)  # 3. 청크 임베딩

        image_list = self._extract_and_upload_images(file_path=file_path,brand=car_brand_eng_nm,model=car_eng_nm)  # 4. 이미지 추출 및 스토리지 업로드
        description_count = sum(bool(image.get("image_desc")) for image in image_list)
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
        machine_logger.info(
            "IMAGE_DESC summary total=%d described=%d none=%d source_types=%s none_reasons=%s",
            len(image_list), description_count, len(image_list) - description_count,
            dict(source_counts), dict(none_reasons),
        )

        # =========================================================
        # 5. Chapter / Chunk / Image DB 등록
        # =========================================================
        self._insert_car_manual_data(
            car_id=car_id,
            chapter_list=chapter_list,
            chunks=chunks,
            embedding_list=embedding_list,
            image_list=image_list
        )

        # 6. 디버깅 출력 (필요 시 별도 디버그 함수로 추출 가능)
        self._print_summary(chunks, image_list)
        
        return chunks, image_list


    # =========================================================
    # PDF 텍스트 추출 및 LangChain Chunk 분할 전담
    # =========================================================
    def _extract_and_split_chunks(self, file_path):
        """PDF 텍스트 추출 및 LangChain Chunk 분할 전담"""
        self.document_reader = DocumentReader(file_path=file_path)
        self.document_reader.set_pdf_reader()
        self.document_reader.set_pdf_doc_list()
        
        machine_logger.info(f"PDF Text 읽기 완료 : {len(self.document_reader.doc_list)} 페이지")

        documents = [
            Document(
                page_content=doc["text"],
                metadata={"page_no": doc["page_no"]}
            )
            for doc in self.document_reader.doc_list
        ]

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
        """PDF 내 이미지 추출 및 Supabase 업로드 전담"""
        car_manual_image_list = []
        
        with pymupdf.open(file_path) as pdf_document:
            total_pages = len(pdf_document)
            machine_logger.info(f"이미지 추출 및 Storage 업로드 시작 : 전체 {total_pages} 페이지")

            for page_index in range(total_pages):
                page = pdf_document[page_index]
                page_no = page_index + 1
                page_image_list = page.get_images(full=True)
                page_image_rects = [
                    rect
                    for page_image_info in page_image_list
                    for rect in page.get_image_rects(page_image_info[0])
                ]

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

        return car_manual_image_list



    # =========================================================
    # 차량 매뉴얼 Chunk Embedding 생성
    # =========================================================
    def _create_chunk_embeddings(self, chunks):
        """차량 매뉴얼 Chunk 텍스트 Embedding 생성"""

        machine_logger.info(
            f"Chunk Embedding 생성 시작 : {len(chunks)}개"
        )

        chunk_text_list = [
            chunk.page_content
            for chunk in chunks
        ]

        embedding_list = self.embedding_model.embed_documents(
            chunk_text_list
        )

        machine_logger.info(
            f"Chunk Embedding 생성 완료 : {len(embedding_list)}개"
        )

        return embedding_list



    # =========================================================
    # PDF 내 이미지 추출 및 Supabase 업로드 전담
    # =========================================================
    @staticmethod
    def _normalize_image_context_text(text):
        """PDF text span의 공백·장식 기호만 정리하고 실제 문구는 보존한다."""
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

        ix0, iy0, ix1, _ = tuple(image_rect)
        image_center_x = (ix0 + ix1) / 2
        image_width = max(ix1 - ix0, 1)
        nearby = []
        text_dict = page.get_text("dict")
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

        # 지면 위치가 같을 때만 더 큰 활자를 먼저 두어도, 9pt 제목은 후보로 보존된다.
        nearby.sort(key=lambda item: (item["distance"], -item["font_size"], item["bbox"][0]))
        return nearby


    @classmethod
    def _describe_image_context(cls, image_rect, text_blocks):
        """가장 가까운 위쪽 문구를 사용하고 가까운 상위 제목·label은 함께 묶는다."""
        if not text_blocks:
            return None, "no_text_above_in_same_column", []

        first = text_blocks[0]
        if re.fullmatch(r"목차를\s*활용하세요[.!?。！]?", first["text"]):
            return None, "table_of_contents_instruction", [first]

        # 직전 문구가 짧은 label이고 바로 위에 짧은 상위 문구가 있을 때만 문서 순서대로 조합한다.
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

        # PDF에 추출된 원문만 연결한다. 긴 한 줄은 저장 상한만 적용한다.
        parts = [item["text"] for item in selected]
        description = " / ".join(dict.fromkeys(parts))[:160].rstrip(" /")
        return description or None, ("heading+label" if len(selected) > 1 else "nearest_above_text"), selected


    @classmethod
    def _generate_image_description(
        cls, page, image_rects, page_image_rects=(), page_no=None, image_no=None,
        return_details=False,
    ):
        """각 배치에서 위쪽 텍스트를 찾고 가장 가까운 문서 연결을 image_desc로 반환한다."""
        if not image_rects:
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

        placements = []
        for image_rect in image_rects:
            candidates = cls._select_nearby_text_blocks(page, image_rect, page_image_rects)
            description, reason, selected = cls._describe_image_context(image_rect, candidates)
            distance = selected[0]["distance"] if selected else float("inf")
            placements.append((distance, tuple(image_rect), description, reason, selected))

        # 같은 xref가 여러 위치에 그려졌다면 가장 가까운 위쪽 문구를 가진 배치를 일관되게 선택한다.
        distance, image_bbox, description, reason, selected = min(
            placements, key=lambda item: (item[0], item[1][1], item[1][0])
        )
        source_text = " / ".join(item["text"] for item in selected) if selected else None
        nearest = min(selected, key=lambda item: item["distance"]) if selected else None
        source_type = (
            "heading+label" if len(selected) > 1 else ("heading" if description and selected else None)
        )
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
        return result if return_details else description


    def _upload_single_image(
        self, pdf_document, image_info, page_no, image_index, brand, model,
        image_desc=None, image_desc_info=None,
    ):
        """단일 이미지 추출 및 업로드 처리"""
        try:
            xref = image_info[0]
            image_data = pdf_document.extract_image(xref)
            image_bytes = image_data["image"]
            image_ext = image_data["ext"]

            image_name = f"page_{page_no:04d}_image_{image_index:02d}.{image_ext}"

            machine_logger.info(
                f"이미지 업로드 시작 : {image_name} ({len(image_bytes):,} bytes)"
            )

            image_url = self.storage_manager.upload_car_image_bytes(
                image_bytes=image_bytes,
                brand=brand,
                model=model,
                image_name=image_name
            )

            machine_logger.info(f"이미지 업로드 완료 : {image_name}")

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

        except Exception as e:
            machine_logger.exception(
                f"이미지 업로드 실패 : 페이지 {page_no}, 이미지 {image_index} - {e}"
            )
            return None




    # =========================================================
    # 결과 확인 및 디버깅용 출력
    # =========================================================
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
        """차량 매뉴얼 Chapter / Chunk / Image DB 등록"""

        with self.sql_session.transaction():

            chapter_map = []

            # =========================================================
            # 1. Chapter 등록
            # =========================================================
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



            # =========================================================
            # 2. Chunk 등록
            # =========================================================
            chunk_insert_count = self.repository.insert_car_manual_chunks(
                car_id=car_id,
                chapter_map=chapter_map,
                chunks=chunks,
                embedding_list=embedding_list
            )
            machine_logger.info(
                f"차량 매뉴얼 Chunk 등록 완료 : {chunk_insert_count}개"
            )


            # =========================================================
            # 3. Image 등록
            # =========================================================
            image_insert_count = self.repository.insert_car_manual_images(
                car_id=car_id,
                chapter_map=chapter_map,
                image_list=image_list
            )
            machine_logger.info(
                f"차량 매뉴얼 Image 등록 완료 : {image_insert_count}개"
            )


        machine_logger.info(
            f"차량 매뉴얼 DB 등록 완료 : "
            f"Chunk {chunk_insert_count}개 / "
            f"Image {image_insert_count}개"
        )

        return chunk_insert_count, image_insert_count    


    # =========================================================
    # 차량 매뉴얼 Chapter ID 생성
    # =========================================================
    def get_car_manual_chapter_id(self):
        """차량 매뉴얼 Chapter ID 생성"""
        return self.repository.get_car_manual_chapter_id()


    # =========================================================
    # 차량 등록
    # =========================================================
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


    # =========================================================
    # 차량 매뉴얼 Chapter 등록
    # =========================================================
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


    # =========================================================
    # 차량 매뉴얼 Chunk 등록
    # =========================================================
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


    # =========================================================
    # 차량 매뉴얼 Image 등록
    # =========================================================
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




    # =========================================================
    # PDF 1레벨 목차 추출
    # =========================================================
    def _extract_pdf_chapters(self, file_path):

        chapter_list = []

        with pymupdf.open(file_path) as pdf_document:

            total_pages = len(pdf_document)

            toc_list = [
                (title, page_no)
                for level, title, page_no
                in pdf_document.get_toc(simple=True)
                if level == 1
            ]

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

        return chapter_list
