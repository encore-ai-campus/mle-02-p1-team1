from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import logging
from car_search_rag.common.document_reader import DocumentReader


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
# 소나타 메뉴얼 PDF 읽기
#=========================================================

#=========================================================
# 커피 머신 정보 등록 호출 시작
#=========================================================

file_path = (Path(__file__).resolve().parents[3]/ "data"/ "DN8_2026_ko_KR.pdf")       # 파일 위치 중심 경로  

carManualSearch = CarManualSearch(file_path=file_path)                                # 서비스 객체 생성  

car_manual_doc_list = carManualSearch.document_reader.doc_list                        # 차 메뉴얼 doc list 설정  

for car_manual_doc in car_manual_doc_list:
    print(car_manual_doc["page_no"])
    print(car_manual_doc["text"])



# coffeeSearch = CoffeeSearch(file_path=file_path)                                    # pdf 설정
# coffeeSearchService = CoffeeSearchService(sql_session=session)                      # 서비스 생성  

# insert_count = coffee_machine_register(coffeeSearchService=coffeeSearchService,
#     file_path=file_path, brand="네스프레소",machine_name="에센자 미니")

# print("등록 완료 건수 :", insert_count)

#=========================================================
# 커피 머신 정보 등록 호출 끝
#=========================================================




