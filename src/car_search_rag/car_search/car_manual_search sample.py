from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pathlib import Path
import sys
import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import logging
from car_search_rag.common.sql_session import SqlSession
from car_search_rag.common.document_reader import DocumentReader
from car_search_rag.common.storage_manager import StorageManager

#=========================================================
# 커피 머신 및 캐슐 검색 메인 프로그램
#=========================================================
class CarManualSearch:
    """
    자동차 메뉴얼 검색 조회
    """

    document_reader: DocumentReader


    #=========================================================
    # 생성시 pdf 설정
    #=========================================================
    def __init__(self,file_path):
        """
        생성시 PDF 설정
        """
        self.document_reader = DocumentReader(file_path=file_path)      # 파일 경로 설정

        self.document_reader.set_pdf_reader()                           # pdf reader 설정
        self.document_reader.set_pdf_doc_list()                         # pdf 파일 doc 설정

        # doc_list = self.document_reader.doc_list
        # for doc in doc_list:
        #     print(doc["page_no"])
        #     print(doc["text"])


#=========================================================
# 함수 선언부 시작
#=========================================================


#=========================================================
# 카 메뉴얼 등록
#=========================================================
def car_manual_register(carManualSearchService,filepath):
    """
    카 메뉴얼 등록
    """
    carManualSearch = CarManualSearch(file_path=filepath)



#=========================================================
# 함수 선언부 끝
#=========================================================



#=========================================================
# 실행 공통 부분 시작
#=========================================================
logging.basicConfig(
    level=logging.INFO,                      # INFO 이상 수준의 로그를 출력
    format="[%(name)s] %(message)s",         # [로그 이름] 로그내용 형식으로 출력
    stream=sys.stdout,                       # 로그를 터미널의 일반 출력(stdout)으로 표시
)

logger = logging.getLogger("CarManual")      # 차량 매뉴얼 처리용 Logger

session = SqlSession(result_log=True)        # session 생성 db 연결
#=========================================================
# 실행 공통 부분 끝
#=========================================================



#=========================================================
# 소나타 메뉴얼 PDF 읽기
#=========================================================

#=========================================================
# 차량 메뉴얼 정보 등록 호출 시작
#=========================================================

# Supabase Storage 업로드를 담당하는 공통 클래스 생성
storage_manager = StorageManager()

#=========================================================
# 차량 매뉴얼 PDF 설정
#=========================================================

file_path = (Path(__file__).resolve().parents[3] / "data" / "DN8_2026_ko_KR.pdf")       # 차량 매뉴얼 PDF 경로

logger.info(f"차량 매뉴얼 처리 시작 : {file_path.name}")

#=========================================================
# 차량 매뉴얼 Text 읽기
#=========================================================

carManualSearch = CarManualSearch(file_path=file_path)                                # 서비스 객체 생성
car_manual_doc_list = carManualSearch.document_reader.doc_list                        # 차량 매뉴얼 페이지별 텍스트 목록

logger.info(f"PDF Text 읽기 완료 : {len(car_manual_doc_list)} 페이지")

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

logger.info(f"Document 생성 완료 : {len(documents)}개")


#=========================================================
# 차량 매뉴얼 Chunk 생성
#=========================================================

logger.info("Chunk 분할 시작")


splitter = RecursiveCharacterTextSplitter(
    chunk_size=400,                                                                   # 청크 하나의 최대 문자 길이
    chunk_overlap=80                                                                  # 앞/뒤 청크가 80자 정도 겹치도록 설정
)

chunks = splitter.split_documents(documents)                                          # Document들을 작은 청크로 분할

for chunk_no, chunk in enumerate(chunks, start=1):
    chunk.metadata["chunk_no"] = chunk_no                                             # 전체 청크 순번 저장


logger.info(f"Chunk 분할 완료 : 전체 {len(chunks)}개")

#=========================================================
# PDF 이미지 추출 → Supabase Storage 직접 업로드
#=========================================================

car_manual_image_list = []                                                            # Supabase에 업로드한 이미지 정보 저장 리스트
pdf_document = pymupdf.open(file_path)                                                   # PyMuPDF로 PDF 파일 열기

total_pages = len(pdf_document)                                                       # PDF 전체 페이지 수

logger.info(f"이미지 추출 및 Storage 업로드 시작 : 전체 {total_pages} 페이지")


for page_index in range(len(pdf_document)):                                           # PDF 페이지를 처음부터 끝까지 반복
    page = pdf_document[page_index]                                                   # 현재 페이지
    page_no = page_index + 1                                                          # 페이지 번호
    page_image_list = page.get_images(full=True)                                      # 현재 페이지의 이미지 목록 추출

    logger.info(
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

            logger.info(
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

            logger.info(
                f"이미지 업로드 완료 : {image_name} "
                f"- 누적 {len(car_manual_image_list)}개"
            )

        except Exception as e:
            logger.exception(
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