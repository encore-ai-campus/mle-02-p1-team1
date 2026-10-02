from pathlib import Path
import sys

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



