from typing import Any

from pathlib import Path
import sys

#=========================================================
# 문서 파일 읽기 및 전처리 관리
#=========================================================
class DocumentReader:
    """
    문서 파일 읽기 및 전처리 관리
    """

    file_path :str          # 파일경로
    doc_list : list[Any]    # 문서 리스트
    reader : Any            # 문서 리더 객체

    #=========================================================
    # 생성자 읽을 파일 설정
    #=========================================================
    def __init__(self, file_path):
        """
        현재 파일 기준으로 상위 1단계 폴더를 기준 경로로 사용하여
        file_path에 지정된 PDF 파일을 읽는다.
        """
        self.file_path = Path(file_path)
        self.reader = None
        self.doc_list = []


    #=========================================================
    # pdf 읽어서 설정
    #=========================================================
    def set_pdf_reader(self):
        """
        pdf 읽어서 설정
        """
        from pypdf import PdfReader

        self.reader = PdfReader(self.file_path)

    #=========================================================
    # csv 읽어서 설정
    #=========================================================
    def set_csv_reader(self):
        """
        csv 읽어서 설정
        """
        import pandas as pd

        self.reader = pd.read_csv(self.file_path)


    #=========================================================
    # 읽은 pdf 내용 doc_list 로 설정
    #=========================================================
    def set_pdf_doc_list(self):
        """
        읽은 pdf 내용 doc_list 로 설정
        """
        
        for i, page in enumerate(self.reader.pages):
            text = page.extract_text()

            self.doc_list.append({              # 현재 페이지 번호와 추출 텍스트를 하나의 딕셔너리로 목록에 추가
                "page_no": i + 1,               # 사용자에게 보이는 실제 페이지 순서처럼 1부터 시작하도록 페이지 번호 저장
                "text": text                    # 현재 페이지에서 추출된 전체 텍스트 저장
            })

    #=========================================================
    # doc_list 청크 설정후 재저장
    #=========================================================
    def set_pdf_chunk_doc_list(selft):
        """
        doc_list 청크 설정후 재저장
        """
        print("구현 예정")        


