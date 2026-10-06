from dotenv import load_dotenv
import sys
import logging
import streamlit as st



from car_search_rag.car_search.chat_runtime import (
    prepare_reply, _is_conversation_download_request, _display_metadata,
)


# =========================================================
# App 설정과 표시 helper
# =========================================================
# 외부 설정과 공통 logging을 먼저 준비한다.
load_dotenv()


logging.basicConfig(
    level=logging.INFO,
    format="[%(name)s] %(message)s",
    stream=sys.stdout,
    force=True
)

logger = logging.getLogger("CarManual")


def _render_assistant_message(message, *, render_answer=True):
    """assistant message를 답변, 출처, 이미지 순서로 화면에 표시한다.

    `message`는 role/content와 선택적인 sources/images를 담은 dict다.
    `render_answer=False`이면 streaming에서 이미 출력한 답변은 건너뛰고
    저장된 출처와 이미지 metadata만 다시 표시한다.
    """
    # 답변이 아직 화면에 출력되지 않은 경우 Markdown으로 표시한다.
    if render_answer:
        st.markdown(message["content"])

    # 저장된 출처를 page/chunk 순서대로 화면에 표시한다.
    # region [Python 설명] dict.get() 기본값과 list 반복
    # `message.get("sources", [])`는 key가 없으면 빈 list를 돌려준다.
    # 각 source dict에서 page 번호와 chunk 번호를 꺼내 한 줄씩 표시한다.
    # endregion
    sources = message.get("sources", [])
    if sources:
        st.markdown("**출처 · 검색된 근거 chunk**")
        for source in sources:
            st.markdown(
                f"- 매뉴얼 p.{source['page_no']} · chunk {source['chunk_no']}"
            )

    # 관련 이미지와 원본 링크를 화면에 표시한다.
    # region [Python 설명] dict.get()의 기본값
    # `message.get("images", [])`는 image key가 없을 때 빈 list를 사용한다.
    # endregion
    images = message.get("images", [])
    if images:
        st.markdown("**관련 검색 결과 이미지**")

        # 이미지 수만큼 같은 줄에 배치 영역을 만든다.
        # region [Streamlit 설명] st.columns()
        # `st.columns(n)`은 같은 줄에 n개의 배치 영역을 만든다.
        # endregion
        columns = st.columns(len(images))

        # 각 column과 image를 같은 순번끼리 짝지어 표시한다.
        # region [Python 설명] zip()과 tuple unpacking
        # `zip(columns, images)`는 두 list의 같은 위치 값을 함께 순회한다.
        # `for column, image in ...`는 한 쌍의 두 값을 변수 두 개로 나누어 받는다.
        # `with column:` 블록의 Streamlit 요소는 해당 column 안에 배치된다.
        # endregion
        for column, image in zip(columns, images):
            with column:
                try:
                    # caption은 page 번호와 선택된 image description을 조합한다.
                    # region [Python 설명] 조건식과 truthy/falsy fallback
                    # `값 if 조건 else 다른 값`은 조건에 따라 caption을 고르는 Python 조건식이다.
                    # `.get()`은 description/page 값이 없을 때 기본 문구를 선택하는 데 쓰인다.
                    # endregion

                    # 이미지 비율을 유지하며 실제 콘텐츠 크기에 맞춰 표시한다.
                    # region [Streamlit 설명] st.image()의 width="content"
                    # `width="content"`는 이미지를 column 전체 폭으로 늘리지 않는다.
                    # 작은 아이콘과 도식이 과도하게 확대되는 것을 막기 위해 사용한다.
                    # endregion
                    st.image(
                        image["url"],
                        caption=(
                            f"검색 결과 이미지 · p.{image['page_no']}"
                            + (f" · {image['description']}" if image.get("description") else "")
                            if image.get("page_no") is not None
                            else (image.get("description") or "검색 결과 이미지")
                        ),
                        width="content",
                    )

                # 미리보기 실패 시 오류를 전파하지 않고 안내 문구를 표시한다.
                # region [Python 설명] try/except
                # 이 예외 처리는 image preview 호출을 감싸며, 실패 메시지를 caption으로 대체한다.
                # endregion
                except Exception:
                    st.caption("이미지 미리보기를 불러오지 못했습니다.")

                # image URL을 원본 링크로 별도 제공한다.
                st.markdown(f"[원본 이미지 열기]({image['url']})")


# =========================================================
# Streamlit 페이지와 Agent 준비
# =========================================================
# 페이지 기본 설정은 화면 요소를 그리기 전에 적용한다.
st.set_page_config(
    page_title="차량 매뉴얼 AI 챗봇",
    page_icon="🚗",
    layout="wide"
)

st.title("🚗 차량 매뉴얼 AI 챗봇")


# =========================================================
# 차량 선택
# =========================================================
# sidebar에서 선택된 차량 정보를 검색 호출에 사용할 변수로 준비한다.
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

    # 선택된 차량 dict를 화면 label로 바꾸는 callback을 전달한다.
    # region [Python 설명] lambda callback
    # `lambda car: ...`는 이름 없이 짧게 정의한 함수다.
    # selectbox가 각 차량 dict를 callback에 전달하고, 반환 문자열을 옵션 label로 표시한다.
    # endregion
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


# =========================================================
# Conversation history 출력
# =========================================================
# 첫 실행에는 대화 목록을 만들고 이후 rerun에서는 기존 값을 유지한다.
# region [Streamlit 설명] session_state와 script rerun
# Streamlit은 입력이나 위젯 상호작용이 발생하면 Python script를 위에서 아래로 재실행한다.
# 일반 지역 변수는 실행이 끝나면 다음 rerun에서 다시 만들어지므로 대화 기록이 유지되지 않는다.
# `st.session_state`에 저장한 messages는 같은 session의 다음 실행에서도 사용할 수 있다.
# endregion
if "messages" not in st.session_state:
    st.session_state["messages"] = []


# 이전에 저장된 대화를 role에 맞는 chat message로 다시 그린다.
# region [Python 설명] message dict 반복과 Streamlit chat container
# `messages`는 role/content 등을 담은 dict 여러 개의 list다.
# 각 dict를 순서대로 읽어 assistant는 답변/metadata helper로 보내고,
# user는 본문만 표시한다.
# endregion
for message in st.session_state["messages"]:

    # role에 맞는 chat bubble 안에 기존 메시지를 표시한다.
    # region [Streamlit 설명] st.chat_message()와 st.markdown()
    # `st.chat_message(role)`은 user 또는 assistant 메시지 영역을 연다.
    # `with` 블록 안에서 호출한 요소는 해당 chat message 안에 표시된다.
    # `st.markdown()`은 content의 Markdown 표기를 렌더링한다.
    # endregion
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            _render_assistant_message(message)
        else:
            st.markdown(message["content"])


# =========================================================
# 질문 입력과 답변 흐름
# =========================================================
# 사용자가 제출한 이번 실행의 질문을 받는다.
# region [Streamlit 설명] st.chat_input()과 rerun
# 이 설정에서는 `st.chat_input()`이 제출된 질문 문자열을 반환하고,
# 제출된 질문이 없으면 None을 반환한다.
# 사용자가 제출하면 script가 rerun되고, 이 실행에서 반환된 질문만 아래에서 처리한다.
# endregion
question = st.chat_input(
    "차량 매뉴얼에 대해 질문하세요"
)


# 질문이 제출된 경우에만 대화와 Agent 응답 흐름을 실행한다.
if question:

    # 전체 이력을 전달하며, 공용 실행 모듈이 Agent용 최근 6개와 다운로드용 전체 이력을 구분한다.
    # region [Python 설명] list slicing과 대화 snapshot
    # `.copy()`는 현재 이력의 복사본을 만들며, 최근 6개 선택은 chat_runtime에서 수행한다.
    # 아래에서 현재 user question을 session history에 추가해도 snapshot에는 포함되지 않아,
    # 현재 질문은 별도 `question` 인자로 한 번만 전달된다.
    # endregion
    conversation_history = st.session_state["messages"].copy()

    # 제출한 user 질문을 chat 영역에 표시한다.
    # region [Streamlit 설명] 새 user chat message
    # `st.chat_message("user")` context 안의 Markdown이 현재 질문 bubble에 들어간다.
    # endregion
    with st.chat_message("user"):
        st.markdown(question)

    # 다음 rerun에서도 현재 질문이 남도록 session history에 user message를 저장한다.
    # region [Python 설명] list.append()와 message dict
    # `messages`는 `{role, content}` dict를 담은 list다.
    # `.append()`는 새 dict를 list 끝에 추가한다.
    # endregion
    st.session_state["messages"].append(
            {
                "role": "user",
                "content": question
            }
        )


    # Agent의 streaming 답변을 assistant chat 영역에서 처리한다.
    with st.chat_message("assistant"):

        # 긴 답변 생성 중에도 진행 중 상태를 사용자에게 보여준다.
        # region [Streamlit 설명] st.spinner()
        # spinner context 안에서 Agent 호출과 streaming이 진행되는 동안 안내 문구를 표시한다.
        # endregion
        with st.spinner("답변을 생성하는 중..."):

            # Agent 결과, 출처, 이미지 표시 데이터를 준비한다.
            try:
                # 공통 챗봇과 동일한 실행 흐름을 호출하고 화면만 렌더링합니다.
                reply = prepare_reply(
                    question, conversation_history,
                    vehicle=(car_brand_eng_nm, car_eng_nm, car_model_yr),
                )
                answer_placeholder = st.empty()
                answer_placeholder.write_stream(reply.chunks)
                answer = reply.answer
                sources, images = reply.sources, reply.images
                answer_placeholder.markdown(answer)
                if reply.error is not None:
                    st.error('답변 생성 중 오류가 발생했습니다. 다시 시도해 주세요.')
                if reply.download_html:
                    st.download_button(
                        label='📥 대화 기록 HTML 다운로드', data=reply.download_html,
                        file_name='car_manual_history.html', mime='text/html',
                    )

            # 예외가 발생해도 assistant history에 저장할 오류 답변을 준비한다.
            # region [Python 설명] try/except와 오류 변수
            # `except Exception as e`는 처리 중 발생한 예외 객체를 `e`에 담는다.
            # 여기서는 오류를 답변 문자열로 바꾸고 출처/이미지는 빈 목록으로 둔다.
            # endregion
            except Exception as e:

                answer = f"오류가 발생했습니다.\n\n{e}"
                sources, images = [], []

        # 답변과 검색 metadata를 하나의 assistant message dict로 묶는다.
        # region [Python 설명] nested dict/list 데이터 구성
        # 이 dict는 화면 표시와 다음 rerun의 conversation history에 함께 사용된다.
        # streaming 중간 조각은 별도로 저장하지 않고, 완료된 answer와 sources/images를 보관한다.
        # endregion
        assistant_message = {
            "role": "assistant",
            "content": answer,
            "sources": sources,
            "images": images,
        }

        # 이미 streaming으로 답변을 그렸으므로 출처와 이미지만 추가 표시한다.
        _render_assistant_message(assistant_message, render_answer=False)


    # 완성된 assistant 답변과 출처/이미지를 다음 rerun을 위해 저장한다.
    st.session_state["messages"].append(assistant_message)
