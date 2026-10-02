import logging
import re
from pathlib import Path

from langchain_openai import OpenAIEmbeddings
from pgvector.utils import Vector
from pypdf import PdfReader

from car_search_rag.common.sql_session import SqlSession
from car_search_rag.common import document_reader

SYSTEM_USER_ID = "SYSTEM"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536
machine_logger = logging.getLogger("car_search_rag.machine")

#=========================================================
# 검색 서비스
#=========================================================
class CoffeeSearchService:

    sql_session : SqlSession

    def __init__(self, sql_session):
        self.sql_session = sql_session

        self.embedding_model = OpenAIEmbeddings(
            model=EMBEDDING_MODEL
        )


    def pdf_filter(self, pdf_docs):                                                               # 전체 PDF 페이지 중 KR 표시 뒤의 한국어 구간만 추출하는 함수

        pdf_filter_docs = []                                                                           # 한국어가 정상 추출된 페이지만 저장할 결과 목록 생성

        other_languages = (                                                                            # KR 구간의 끝을 판단하기 위해 뒤에 나올 수 있는 다른 언어 코드 패턴 정의
            r"EN|FR|ES-LATAM|DE|IT|ES|PT|CS|SK|PL|HU|RU|EL|NL|BR|"                                     # 설명서에 등장할 수 있는 첫 번째 언어 코드 묶음
            r"DA|NO|SV|FI|RO|TR|CN|HK|TW|MS|ID|TH|AR|IL|AU|US\s*/\s*CA|CA"                             # 설명서에 등장할 수 있는 나머지 언어 코드와 US / CA 변형 패턴
        )

        for pdf_doc in pdf_docs:                                                                       # PDF에서 읽은 페이지 정보를 앞에서부터 한 페이지씩 순회

            page_no = pdf_doc["page_no"]                                                               # 현재 페이지의 페이지 번호를 별도 변수에 저장
            text = pdf_doc["text"]                                                                     # 현재 페이지에서 추출한 전체 텍스트를 별도 변수에 저장

            #---------------------------------------------------------
            # 텍스트가 없는 페이지 제외
            #---------------------------------------------------------
            if text is None:                                                                           # PDF 텍스트 추출 결과가 아예 없는 페이지인지 확인
                continue                                                                               # 텍스트가 없으면 현재 페이지 처리를 중단하고 다음 페이지로 이동

            #---------------------------------------------------------
            # KR 표시가 없는 페이지 제외
            #---------------------------------------------------------
            if "KR" not in text:                                                                       # 현재 페이지 전체 텍스트에 한국어 구간 시작 표시인 KR이 있는지 확인
                continue                                                                               # KR 표시가 없으면 한국어 추출 대상이 아니므로 다음 페이지로 이동

            #---------------------------------------------------------
            # 현재 페이지에서 KR부터 다음 언어 코드 직전까지 찾기
            #---------------------------------------------------------
            matches = re.finditer(                                                                     # 현재 페이지 안의 모든 KR 구간을 순서대로 찾는 정규식 iterator 생성
                rf"\bKR\b(.*?)(?=\s+(?:{other_languages})\b|[\u0590-\u05FF]|\Z)",                      # KR 뒤부터 다음 언어 코드·히브리 문자·문서 끝 직전까지 최소 범위로 캡처
                text,                                                                                  # 정규식을 적용할 현재 페이지의 전체 추출 텍스트
                re.DOTALL                                                                              # 점(.)이 줄바꿈 문자까지 포함하여 여러 줄의 KR 영역을 잡도록 설정
            )

            #---------------------------------------------------------
            # 현재 페이지의 KR 구간 합치기
            #---------------------------------------------------------
            korean_text = ""                                                                           # 한 페이지에서 발견된 여러 KR 텍스트 구간을 합칠 빈 문자열 생성

            for match in matches:                                                                      # 정규식으로 찾은 KR 구간을 발견 순서대로 하나씩 순회
                korean_text += match.group(1).strip() + "\n\n"                                         # KR 표시 자체를 제외한 캡처 내용을 정리하여 두 줄 간격으로 누적

            #---------------------------------------------------------
            # 실제 추출된 내용이 있는 경우에만 저장
            #---------------------------------------------------------
            korean_text = korean_text.strip()                                                           # 앞뒤에 남은 불필요한 공백과 마지막 줄바꿈을 제거

            if korean_text:                                                                             # 공백 제거 후 실제 한국어 텍스트가 남아 있는지 확인
                pdf_filter_docs.append({                                                                # 정상 추출된 페이지 번호와 한국어 텍스트를 결과 목록에 추가
                    "page_no": page_no,                                                                 # 원본 PDF의 페이지 번호를 그대로 저장
                    "text": korean_text                                                                 # 해당 페이지에서 추출한 KR 영역의 텍스트만 저장
                })

        return pdf_filter_docs                                                                          # 한국어 영역이 추출된 페이지 목록 반환    


    #=========================================================
    # 커피 머신 매뉴얼 등록
    #=========================================================
    def insert_pdf_docs(
        self,
        brand,
        machine_name,
        pdf_filter_docs
    ):

        #=====================================================
        # 1. 임베딩할 text 목록
        #=====================================================
        texts = []

        for pdf_doc in pdf_filter_docs:
            texts.append(pdf_doc["text"])


        #=====================================================
        # 2. 임베딩 한번에 호출
        #=====================================================
        vectors = self.embedding_model.embed_documents(texts)


        #=====================================================
        # 3. DB Transaction
        #=====================================================
        with self.sql_session.transaction():

            # 머신 조회
            machine = self.sql_session.select_one(
                "coffee_search.select_machine",
                {
                    "BRAND": brand,
                    "MACHINE_NAME": machine_name
                }
            )


            #=================================================
            # 머신 없으면 등록
            #=================================================
            if machine is None:

                machine_id_row = self.sql_session.select_one(
                    "coffee_search.generate_biz_id",
                    {
                        "TABLE_NAME": "CFF_MACH"
                    }
                )

                cff_mach_id = machine_id_row["id"]

                self.sql_session.execute(
                    "coffee_search.insert_machine",
                    {
                        "CFF_MACH_ID": cff_mach_id,
                        "BRAND": brand,
                        "MACHINE_NAME": machine_name,
                        "USER_ID": SYSTEM_USER_ID
                    }
                )

            else:

                cff_mach_id = machine["id"]


            #=================================================
            # 기존 상세 삭제
            #=================================================
            self.sql_session.execute(
                "coffee_search.delete_machine_details",
                {
                    "CFF_MACH_ID": cff_mach_id
                }
            )


            #=================================================
            # 상세 Batch 등록
            #=================================================
            insert_count = self.insert_machine_details(
                cff_mach_id,
                pdf_filter_docs,
                vectors
            )


        return insert_count


    #=========================================================
    # 커피 머신 매뉴얼 상세 Batch 등록
    #=========================================================
    def insert_machine_details(
        self,
        cff_mach_id,
        pdf_filter_docs,
        vectors
    ):

        #=====================================================
        # Batch 등록 데이터 목록
        #=====================================================
        batch_params = []


        #=====================================================
        # PDF 문서와 임베딩 Vector를 1:1로 처리
        #=====================================================
        for pdf_doc, vector in zip(
            pdf_filter_docs,
            vectors,
            strict=True
        ):

            #=================================================
            # Batch 등록 데이터 추가
            #=================================================
            batch_params.append({
                "CFF_MACH_ID": cff_mach_id,
                "PAGE_NO": str(pdf_doc["page_no"]),
                "TEXT": pdf_doc["text"],
                "EMBEDDING": Vector(vector),
                "USER_ID": SYSTEM_USER_ID
            })


        #=====================================================
        # 상세 데이터 한번에 등록
        #=====================================================
        if batch_params:

            self.sql_session.execute_many(
                "coffee_search.insert_machine_detail",
                batch_params
            )


        return len(batch_params)



    #=========================================================
    # 커피 머신 매뉴얼 AI 검색
    #=========================================================
    def search_machine_manual(
        self,
        brand,
        machine_name,
        question,
        limit=5
    ):

        #=====================================================
        # 질문 임베딩
        #=====================================================
        query_vector = self.embedding_model.embed_query(question)


        #=====================================================
        # 질문과 유사한 PDF 내용 검색
        #=====================================================
        search_docs = self.sql_session.select_list(
            "coffee_search.search_machine_manual",
            {
                "BRAND": brand,
                "MACHINE_NAME": machine_name,
                "EMBEDDING": Vector(query_vector),
                "LIMIT": limit
            }
        )

        return search_docs



    #=========================================================
    # 차량 매뉴얼 LLM 답변 생성
    #=========================================================
    def generate_manual_answer(
        self,
        question,
        search_docs
    ):
        if not search_docs:
            return "관련된 차량 매뉴얼 내용을 찾지 못했습니다."

        context_list = []

        for index, doc in enumerate(search_docs, start=1):

            context_list.append(
                f"""
                [검색 문서 {index}]

                페이지:
                {doc.get("carManualChunkPageNo")}

                내용:
                {doc.get("carManualChunkTxt")}

                이미지 URL:
                {doc.get("carManualImageUrl") or "없음"}
                """
            )

        context = "\n".join(context_list)

        prompt = f"""
            너는 차량 사용 설명서를 안내하는 AI 어시스턴트다.

            아래 차량 매뉴얼 검색 결과를 기반으로 질문에 답변해라.

            규칙:
            - 매뉴얼 내용에 근거해서 답변한다.
            - 매뉴얼에 없는 내용은 추측하지 않는다.
            - 관련 페이지 번호를 함께 알려준다.
            - 관련 이미지 URL이 있으면 함께 알려준다.

            [질문]
            {question}

            [차량 매뉴얼]
            {context}
            """

        response = self.chat_model.invoke(prompt)

        return response.content


    #=========================================================
    # 차량 매뉴얼 AI 질의
    #=========================================================
    def ask_manual(
        self,
        car_brand_eng_nm,
        car_eng_nm,
        car_model_yr,
        question,
        limit=5
    ):

        search_docs = self.search_manual(
            car_brand_eng_nm=car_brand_eng_nm,
            car_eng_nm=car_eng_nm,
            car_model_yr=car_model_yr,
            question=question,
            limit=limit
        )

        answer = self.generate_manual_answer(
            question=question,
            search_docs=search_docs
        )

        return answer
