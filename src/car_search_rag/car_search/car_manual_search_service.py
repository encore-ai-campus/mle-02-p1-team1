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

    def insert_pdf_docs(
        self,
        file_path,
        brand,
        model
    ):

        #=========================================================
        # PDF Text 읽기
        #=========================================================
        car_manual_doc_list = self.document_reader.doc_list                                  # 차량 매뉴얼 페이지별 텍스트 목록

        machine_logger.info(f"PDF Text 읽기 완료 : {len(car_manual_doc_list)} 페이지")

        #=========================================================
        # LangChain Document 생성
        #=========================================================

        documents = []                                                                        # LangChain Document 객체 저장 리스트

        for car_manual_doc in car_manual_doc_list:                                            # 차량 매뉴얼 데이터를 하나씩 반복
            documents.append(
                Document(
                    page_content=car_manual_doc["text"],                                      # 실제 매뉴얼 내용
                    metadata={"page_no": car_manual_doc["page_no"]}                           # 원본 페이지 번호 저장
                )
            )

        machine_logger.info(f"Document 생성 완료 : {len(documents)}개")


        #=========================================================
        # 차량 매뉴얼 Chunk 생성
        #=========================================================

        machine_logger.info("Chunk 분할 시작")


        splitter = RecursiveCharacterTextSplitter(
            chunk_size=400,                                                                   # 청크 하나의 최대 문자 길이
            chunk_overlap=80                                                                  # 앞/뒤 청크가 80자 정도 겹치도록 설정
        )

        chunks = splitter.split_documents(documents)                                          # Document들을 작은 청크로 분할

        for chunk_no, chunk in enumerate(chunks, start=1):
            chunk.metadata["chunk_no"] = chunk_no                                             # 전체 청크 순번 저장


        machine_logger.info(f"Chunk 분할 완료 : 전체 {len(chunks)}개")

        #=========================================================
        # PDF 이미지 추출 → Supabase Storage 직접 업로드
        #=========================================================

        car_manual_image_list = []                                                            # Supabase에 업로드한 이미지 정보 저장 리스트
        pdf_document = pymupdf.open(file_path)                                                # PyMuPDF로 PDF 파일 열기

        self.document_reader.set_pdf_reader()                                                 # pdf reader 설정
        self.document_reader.set_pdf_doc_list()                                               # pdf 파일 doc 설정

        total_pages = len(pdf_document)                                                       # PDF 전체 페이지 수

        machine_logger.info(f"이미지 추출 및 Storage 업로드 시작 : 전체 {total_pages} 페이지")


        for page_index in range(len(pdf_document)):                                           # PDF 페이지를 처음부터 끝까지 반복
            page = pdf_document[page_index]                                                   # 현재 페이지
            page_no = page_index + 1                                                          # 페이지 번호
            page_image_list = page.get_images(full=True)                                      # 현재 페이지의 이미지 목록 추출

            machine_logger.info(
                f"페이지 처리 : {page_no}/{total_pages} "
                f"- 이미지 {len(page_image_list)}개"
            )


            for image_index, image_info in enumerate(page_image_list, start=1):               # 페이지의 이미지를 하나씩 반복

                try:
                
                    xref = image_info[0]                                                          # PDF 내부 이미지 객체 번호
                    image_data = pdf_document.extract_image(xref)                                 # 이미지 데이터 추출
                    image_bytes = image_data["image"]                                             # 실제 이미지 바이너리 데이터
                    image_ext = image_data["ext"]                                                 # 이미지 확장자

                    image_name = f"page_{page_no:04d}_image_{image_index:02d}.{image_ext}"         # Storage에 저장할 이미지 파일명

                    machine_logger.info(
                        f"이미지 업로드 시작 : {image_name} "
                        f"({len(image_bytes):,} bytes)"
                    )


                    image_url = storage_manager.upload_car_image_bytes(                           # 로컬 저장 없이 Supabase Storage에 바로 업로드
                        image_bytes=image_bytes,
                        brand="hyundai",
                        model="sonata",
                        image_name=image_name
                    )

                    car_manual_image_list.append({
                        "page_no": page_no,                                                       # 이미지가 위치한 페이지 번호
                        "image_no": image_index,                                                  # 페이지 내 이미지 순번
                        "image_xref": xref,                                                       # PDF 내부 이미지 객체 번호
                        "image_name": image_name,                                                 # Storage 이미지 파일명
                        "image_url": image_url                                                    # Supabase Storage Public URL
                    })

                    machine_logger.info(
                        f"이미지 업로드 완료 : {image_name} "
                        f"- 누적 {len(car_manual_image_list)}개"
                    )

                except Exception as e:
                    machine_logger.exception(
                        f"이미지 업로드 실패 : "
                        f"페이지 {page_no}, 이미지 {image_index} - {e}"
                    )


        pdf_document.close()                                                                  # PDF 파일 닫기


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