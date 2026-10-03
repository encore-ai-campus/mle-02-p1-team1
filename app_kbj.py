from dotenv import load_dotenv
import sys
import logging
import streamlit as st



from car_search_rag.car_search.car_manual import CarManual


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
# 차량 매뉴얼 Agent 생성
#=========================================================
@st.cache_resource
def get_car_manual():
    return CarManual()


car_manual = get_car_manual()


#=========================================================
# 차량 선택
#=========================================================
with st.sidebar:

    st.header("차량 정보")

    cars = [
        {
            "car_nm": "소나타",
            "car_brand_nm": "현대",
            "car_brand_eng_nm": "hyundai",
            "car_eng_nm": "sonata",
            "car_model_yr": 2026,
        }
    ]

    selected_car = st.selectbox(
        "차량",
        cars,
        format_func=lambda car: (
            f"{car['car_nm']} ({car['car_brand_nm']} · "
            f"{car['car_model_yr']}년)"
        ),
    )

    car_brand_eng_nm = selected_car["car_brand_eng_nm"]
    car_eng_nm = selected_car["car_eng_nm"]
    car_model_yr = selected_car["car_model_yr"]


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
    # Agent 답변 생성
    #=====================================================
    with st.chat_message("assistant"):

        with st.spinner("답변을 생성하는 중..."):

            try:

                answer = car_manual.ask(
                    car_brand_eng_nm=car_brand_eng_nm,
                    car_eng_nm=car_eng_nm,
                    car_model_yr=car_model_yr,
                    question=question,
                    limit=10,
                    conversation_history=conversation_history,
                )

                if car_manual.download_html:
                    st.download_button(
                        label="📥 대화 기록 HTML 다운로드",
                        data=car_manual.download_html,
                        file_name="car_manual_history.html",
                        mime="text/html",
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
