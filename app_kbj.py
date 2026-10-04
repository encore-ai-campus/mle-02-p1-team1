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


def _display_metadata(search_results):
    """검색 row에서 UI 출처와 이미지 URL만 검색 순서대로 추린다."""
    sources = []
    seen_sources = set()
    images = []
    seen_images = set()

    for result in search_results or ():
        page_no = result.get("carManualChunkPageNo", result.get("car_manual_chunk_page_no"))
        chunk_no = result.get("carManualChunkNo", result.get("car_manual_chunk_no"))
        source_key = (page_no, chunk_no)
        if page_no is not None and chunk_no is not None and source_key not in seen_sources:
            sources.append({"page_no": page_no, "chunk_no": chunk_no})
            seen_sources.add(source_key)

        image_url = result.get("carManualImageUrl", result.get("car_manual_image_url"))
        if isinstance(image_url, str):
            image_url = image_url.strip()
            if image_url and image_url not in seen_images and len(images) < 3:
                images.append({"url": image_url, "page_no": page_no})
                seen_images.add(image_url)

        if len(sources) >= 5 and len(images) >= 3:
            break

    return sources[:5], images


def _render_assistant_message(message):
    """답변 아래에 저장된 검색 근거와 관련 검색 결과 이미지를 표시한다."""
    st.markdown(message["content"])

    sources = message.get("sources", [])
    if sources:
        st.markdown("**출처 · 검색된 근거 chunk**")
        for source in sources:
            st.markdown(
                f"- 매뉴얼 p.{source['page_no']} · chunk {source['chunk_no']}"
            )

    images = message.get("images", [])
    if images:
        st.markdown("**관련 검색 결과 이미지**")
        columns = st.columns(len(images))
        for column, image in zip(columns, images):
            with column:
                try:
                    st.image(
                        image["url"],
                        caption=(
                            f"검색 결과 이미지 · p.{image['page_no']}"
                            if image.get("page_no") is not None
                            else "검색 결과 이미지"
                        ),
                        width="stretch",
                    )
                except Exception:
                    st.caption("이미지 미리보기를 불러오지 못했습니다.")
                st.markdown(f"[원본 이미지 열기]({image['url']})")


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
    car_manual = CarManual()
    # cache_resource 함수는 resource 최초 생성 때만 실행되므로 첫 검색 전에 최소 DB connection을 준비한다.
    sql_session = car_manual.service.sql_session
    sql_session.database_manager.warmup(camel_case_keys=sql_session.camel_case_keys)
    return car_manual


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
        if message["role"] == "assistant":
            _render_assistant_message(message)
        else:
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

                answer_result = car_manual.ask_with_sources(
                    car_brand_eng_nm=car_brand_eng_nm,
                    car_eng_nm=car_eng_nm,
                    car_model_yr=car_model_yr,
                    question=question,
                    limit=10,
                    conversation_history=conversation_history,
                )
                answer = answer_result.answer
                sources, images = _display_metadata(answer_result.search_results)

                if car_manual.download_html:
                    st.download_button(
                        label="📥 대화 기록 HTML 다운로드",
                        data=car_manual.download_html,
                        file_name="car_manual_history.html",
                        mime="text/html",
                    )

            except Exception as e:

                answer = f"오류가 발생했습니다.\n\n{e}"
                sources, images = [], []


        assistant_message = {
            "role": "assistant",
            "content": answer,
            "sources": sources,
            "images": images,
        }
        _render_assistant_message(assistant_message)


    #=====================================================
    # AI 답변 대화 내역 저장
    #=====================================================
    st.session_state["messages"].append(assistant_message)
