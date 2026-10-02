import logging
import re
from pathlib import Path

from langchain_openai import OpenAIEmbeddings
from pgvector.utils import Vector
from pypdf import PdfReader
import pymupdf

from car_search_rag.common.sql_session import SqlSession
from car_search_rag.common import document_reader
from car_search_rag.common.document_reader import DocumentReader
from car_search_rag.common.storage_manager import StorageManager
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


SYSTEM_USER_ID = "SYSTEM"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536
machine_logger = logging.getLogger("car_search_rag.car_manual")

#=========================================================
# 차량 매뉴얼 검색 Service
#=========================================================
class CarManualSearchService:

    sql_session : SqlSession
    embedding_model : OpenAIEmbeddings
    storage_manager: StorageManager

    #=========================================================
    # 생성자
    #=========================================================
    def __init__(self,sql_session):
        self.sql_session = sql_session

        self.embedding_model = OpenAIEmbeddings(
            model=EMBEDDING_MODEL
        )

        self.storage_manager = StorageManager()


    #=========================================================
    # 차량 메뉴얼 PDF 처리 메인 파이프 라인
    #=========================================================
    def insert_pdf_docs(self, 
                        file_path, 
                        car_brand_nm, 
                        car_brand_eng_nm,
                        car_nm,
                        car_eng_nm,
                        car_model_yr
                        ):
        """차량 매뉴얼 PDF 처리 메인 파이프라인"""

        #=====================================================
        # 2. 차량 정보 등록
        #=====================================================
        car_id = self.insert_car(
            car_brand_nm=car_brand_nm,
            car_brand_eng_nm=car_brand_eng_nm,
            car_nm=car_nm,
            car_eng_nm=car_eng_nm,
            car_model_yr=car_model_yr
        )

        machine_logger.info(f"차량 ID 생성 완료 : {car_id}")

        return car_id
        
        # 1. 텍스트 추출 및 청크 생성
        chunks = self._extract_and_split_chunks(file_path)
        
        # 2. 이미지 추출 및 스토리지 업로드
        image_list = self._extract_and_upload_images(file_path, brand, model)
        
        # 3. 디버깅 출력 (필요 시 별도 디버그 함수로 추출 가능)
        self._print_summary(chunks, image_list)
        
        return chunks, image_list


    #=========================================================
    # PDF 텍스트 추출 및 LangChain Chunk 분할 전담
    #=========================================================
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

        splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=80)
        chunks = splitter.split_documents(documents)

        for chunk_no, chunk in enumerate(chunks, start=1):
            chunk.metadata["chunk_no"] = chunk_no

        machine_logger.info(f"Chunk 분할 완료 : 전체 {len(chunks)}개")
        return chunks


    #=========================================================
    # PDF 내 이미지 추출 및 Supabase 업로드 전담
    #=========================================================
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

                for image_index, image_info in enumerate(page_image_list, start=1):
                    image_data = self._upload_single_image(
                        pdf_document, image_info, page_no, image_index, brand, model
                    )
                    if image_data:
                        car_manual_image_list.append(image_data)

        return car_manual_image_list

    #=========================================================
    # PDF 내 이미지 추출 및 Supabase 업로드 전담
    #=========================================================
    def _upload_single_image(self, pdf_document, image_info, page_no, image_index, brand, model):
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
                "image_url": image_url
            }

        except Exception as e:
            machine_logger.exception(
                f"이미지 업로드 실패 : 페이지 {page_no}, 이미지 {image_index} - {e}"
            )
            return None

    #=========================================================
    # 결과 확인 및 디버깅용 출력
    #=========================================================
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


    #=========================================================
    # 차량 ID 생성
    #=========================================================
    def get_car_id(self):
        """ 차량 ID 생성 """    

        result = self.sql_session.select_one("car_manual_search.select_get_car_id")
        return result["carId"]

    #=========================================================
    # 차량 등록
    #=========================================================
    def insert_car(
        self,
        car_brand_nm,
        car_brand_eng_nm,
        car_nm,
        car_eng_nm,
        car_model_yr
    ):

        result = self.sql_session.execute(
        "car_manual_search.merge_car",
        {
            "CAR_BRAND_NM": car_brand_nm,
            "CAR_BRAND_ENG_NM": car_brand_eng_nm,
            "CAR_NM": car_nm,
            "CAR_ENG_NM": car_eng_nm,
            "CAR_MODEL_YR": car_model_yr,
            "USER_ID": SYSTEM_USER_ID
        }
        )

        car_id = result[0]["carId"]

        machine_logger.info(f"차량 등록 완료 : {car_id}")

        return car_id