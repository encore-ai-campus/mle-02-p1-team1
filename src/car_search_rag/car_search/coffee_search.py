import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))    # 파일 경로 현재 위치 기준으로 상위 2단계 경로를 sys.path에 추가        

import logging
from car_search_rag.common.sql_session import SqlSession
from car_search_rag.car_search.coffee_search_service import CoffeeSearchService
import logging
import re
from pathlib import Path
# from langchain_openai import OpenAIEmbeddings
from pgvector.utils import Vector
from pypdf import PdfReader

from car_search_rag.car_search import coffee_search_service
from car_search_rag.common.document_reader import DocumentReader

#=========================================================
# 커피 머신 및 캐슐 검색 메인 프로그램
#=========================================================
class CoffeeSearch: 
    """
    커피 머신 및 캐슐 검색 메인 프로그램
    """

    document_reader : DocumentReader                                    # 문서 처리 클래스

    #=========================================================
    # 생성시 pdf 설정
    #=========================================================
    def __init__(self,file_path):
        """
        생성시 pdf 설정
        """
        self.document_reader = DocumentReader(file_path=file_path)   # 파일 설정

        self.document_reader.set_pdf_reader()                        # 파일 pdf 방식 읽기            
        self.document_reader.set_pdf_doc_list()                      # pdf to doc_list 설정

        # doc_list = self.document_reader.doc_list
        # for doc in doc_list:
        #     print(doc["page_no"])
        #     print(doc["text"])





#=========================================================
# 함수 선언부 시작
#=========================================================

#=========================================================
# 커피 머신 정보 등록
#=========================================================
def coffee_machine_register(coffeeSearchService,file_path, brand, machine_name):

    #=====================================================
    # CoffeeSearch 클래스 생성
    #=====================================================
    coffeeSearch = CoffeeSearch(file_path=file_path)          # pdf 설정    
    
    #=====================================================
    # PDF 필터
    #=====================================================
    pdf_filter_docs = coffeeSearchService.pdf_filter(coffeeSearch.document_reader.doc_list)    


    #=========================================================
    insert_count = coffeeSearchService.insert_pdf_docs(
        brand=brand,
        machine_name=machine_name,
        pdf_filter_docs=pdf_filter_docs
    )

    return insert_count

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

session = SqlSession(result_log=True)        # session 생성 db 연결
#=========================================================
# 실행 공통 부분 끝
#=========================================================



#=========================================================
# 커피 머신 정보 등록 호출 시작
#=========================================================

# file_path = (Path(__file__).resolve().parents[2]/ "data"/ "에센자미니_c30.pdf")       # 파일 위치 중심 경로  

# coffeeSearch = CoffeeSearch(file_path=file_path)                                    # pdf 설정
# coffeeSearchService = CoffeeSearchService(sql_session=session)                      # 서비스 생성  

# insert_count = coffee_machine_register(coffeeSearchService=coffeeSearchService,
#     file_path=file_path, brand="네스프레소",machine_name="에센자 미니")

# print("등록 완료 건수 :", insert_count)

#=========================================================
# 커피 머신 정보 등록 호출 끝
#=========================================================


#=========================================================
# 커피 머신 AI 검색 테스트
#=========================================================

question = "커피가 나오지 않을 때 어떻게 해야 하나요?"

coffeeSearchService = CoffeeSearchService(sql_session=session)                      # 서비스 생성  

search_docs = coffeeSearchService.search_machine_manual(
    brand="네스프레소",
    machine_name="에센자 미니",
    question=question,
    limit=5
)

print()
print("질문 :", question)
print()

#=========================================================
# 커피 머신 AI 검색 끝
#=========================================================    
