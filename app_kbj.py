from dotenv import load_dotenv
import sys
import logging
import streamlit as st
from dotenv import load_dotenv



from car_search_rag.car_search.car_manual_search_service import (
    CarManualSearchService
)
from car_search_rag.common.sql_session import SqlSession


#=========================================================
# 환경 변수 로드
#=========================================================
load_dotenv()


#=========================================================
# 실행 공통 부분 시작
#=========================================================
logging.basicConfig(
    level=logging.INFO,
    format="[%(name)s] %(message)s",
    stream=sys.stdout,
    force=True
)

logger = logging.getLogger("CarManual")


#=========================================================
# Streamlit 페이지 설정
#=========================================================
st.set_page_config(
    page_title="차량 매뉴얼 AI 챗봇",
    page_icon="🚗",
    layout="wide"
)

st.title("🚗 차량 매뉴얼 AI 챗봇")


#=========================================================
# Service 생성
# DB / Embedding / LLM 객체 재사용
#=========================================================
@st.cache_resource
def get_service():

    sql_session = SqlSession(
        result_log=True
    )

    return CarManualSearchService(
        sql_session=sql_session
    )


service = get_service()


#=========================================================
# 차량 선택
#=========================================================
with st.sidebar:

    st.header("차량 정보")

    car_brand_eng_nm = st.selectbox(
        "제조사",
        ["hyundai"]
    )

    car_eng_nm = st.selectbox(
        "차량",
        ["sonata"]
    )

    car_model_yr = st.selectbox(
        "연식",
        [2026]
    )

    limit = st.selectbox(
        "검색 문서 수",
        [3, 5, 10],
        index=1
    )


#=========================================================
# 대화 내용 초기화
#=========================================================
if "messages" not in st.session_state:
    st.session_state["messages"] = []


#=========================================================
# 기존 대화 출력
#=========================================================
for message in st.session_state["messages"]:

    with st.chat_message(message["role"]):
        st.markdown(message["content"])


#=========================================================
# 사용자 질문 입력
#=========================================================
question = st.chat_input(
    "차량 매뉴얼에 대해 질문하세요"
)


#=========================================================
# 질문 처리
#=========================================================
if question:

    # 현재 질문을 제외한 과거 대화 복사
    conversation_history = st.session_state["messages"].copy()

    #=====================================================
    # 사용자 질문 화면 출력
    #=====================================================
    with st.chat_message("user"):
        st.markdown(question)


    st.session_state["messages"].append(
            {
                "role": "user",
                "content": question
            }
        )


    #=====================================================
    # 차량 매뉴얼 RAG 검색 + LLM 답변
    #=====================================================
    with st.chat_message("assistant"):

        with st.spinner("차량 매뉴얼을 검색하고 답변하는 중..."):

            try:

                answer = service.ask_manual(
                    car_brand_eng_nm=car_brand_eng_nm,
                    car_eng_nm=car_eng_nm,
                    car_model_yr=car_model_yr,
                    question=question,
                    conversation_history=conversation_history,
                    limit=limit
                )

            except Exception as e:

                answer = f"오류가 발생했습니다.\n\n{e}"


        st.markdown(answer)


    #=====================================================
    # AI 답변 대화 내역 저장
    #=====================================================
    st.session_state["messages"].append(
        {
            "role": "assistant",
            "content": answer
        }
    )