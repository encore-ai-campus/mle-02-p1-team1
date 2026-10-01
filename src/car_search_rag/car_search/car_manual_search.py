from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

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
        self.document_reader = DocumentReader(file_path=file_path)

        self.documentReader.set_pdf_reader()
        self.documentReader.set_pdf_doc_list()

        doc_list = self.document_reader.doc_list
        for doc in doc_list:
            print(doc["page_no"])
            print(doc["text"])




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

# file_path = (Path(__file__).resolve().)




