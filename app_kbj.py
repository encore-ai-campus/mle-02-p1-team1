from dotenv import load_dotenv
import sys
import logging
import streamlit as st



from car_search_rag.car_search.car_manual import CarManual


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


def _is_conversation_download_request(question):
    """대화 기록과 다운로드 의도가 함께 있는 질문을 판별한다."""
    normalized = " ".join((question or "").casefold().split())
    history_terms = (
        "대화", "채팅", "기록", "내역", "히스토리", "history", "conversation", "chat"
    )
    download_terms = ("다운로드", "내려받", "내보내", "download", "export")
    return (
        any(term in normalized for term in history_terms)
        and any(term in normalized for term in download_terms)
    )


def _display_metadata(search_results, question=None, image_selector=None, answer=None):
    """검색 row에서 출처와 화면에 표시할 이미지를 분리해 만든다.

    출처는 chunk 순서를 유지하며 최대 5개까지 모은다. image selector가 있으면
    질문 관련도로 이미지를 고르고, 없으면 검색 row의 URL에서 최대 3개를 가져온다.

    Returns:
        `(출처 목록, 이미지 metadata 목록)` 형태의 tuple.
    """
    # 검색 row 순서대로 중복 없는 출처 목록을 만든다.
    # region [Python 설명] list, set, tuple key와 dict.get()
    # `sources`는 출처 dict를 담는 list이고 `seen_sources`는 중복 검사 set이다.
    # row의 key는 camelCase 또는 snake_case일 수 있어 중첩 `.get()`으로 둘 다 확인한다.
    # `(page_no, chunk_no)` tuple은 출처 한 건을 구별하는 set key로 사용한다.
    # `search_results or ()`는 결과가 None 또는 비어 있으면 빈 tuple로 순회한다.
    # endregion
    sources = []
    seen_sources = set()

    for result in search_results or ():
        page_no = result.get("carManualChunkPageNo", result.get("car_manual_chunk_page_no"))
        chunk_no = result.get("carManualChunkNo", result.get("car_manual_chunk_no"))
        source_key = (page_no, chunk_no)
        if page_no is not None and chunk_no is not None and source_key not in seen_sources:
            sources.append({"page_no": page_no, "chunk_no": chunk_no})
            seen_sources.add(source_key)

        if len(sources) >= 5:
            break

    # image selector가 있으면 질문을 전달해 관련 이미지를 선택한다.
    # region [Python 설명] callback 함수와 truthy 검사
    # `image_selector`는 호출자가 함수로 전달한 callback이다.
    # 질문과 검색 row를 넘겨 실행하고 이미지 표시용 metadata 목록을 받는다.
    # `question and image_selector`는 두 값이 모두 있을 때만 이 경로를 선택한다.
    # endregion
    if question and image_selector:
        images = image_selector(question, search_results, limit=3, answer=answer)
    else:
        # selector가 없으면 검색 row에 붙은 image URL에서 순서대로 모은다.
        images = []
        seen_images = set()

        # URL이 문자열이고 유효하며 이미 쓰이지 않았는지 확인한다.
        # region [Python 설명] isinstance()와 set membership
        # `isinstance(image_url, str)`는 URL 값이 문자열인지 확인한다.
        # `.strip()`은 앞뒤 공백을 제거하고, set membership은 이미 본 URL을 건너뛴다.
        # endregion
        for result in search_results or ():
            image_url = result.get("carManualImageUrl", result.get("car_manual_image_url"))
            page_no = result.get("carManualChunkPageNo", result.get("car_manual_chunk_page_no"))
            if isinstance(image_url, str) and image_url.strip() and image_url.strip() not in seen_images:
                images.append({"url": image_url.strip(), "page_no": page_no})
                seen_images.add(image_url.strip())

            if len(images) >= 3:
                break

    # 출처와 이미지 목록을 tuple로 반환한다.
    # region [Python 설명] 여러 값 반환
    # `return a, b`는 `(a, b)` tuple을 반환한다.
    # 호출 측은 `sources, images = ...`처럼 두 변수로 나누어 받을 수 있다.
    # endregion
    return sources[:5], images


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


# 반복 실행에서도 재사용할 차량 매뉴얼 Agent를 준비한다.
# region [Streamlit 설명] st.cache_resource
# Streamlit은 사용자 입력 등으로 script를 위에서 아래로 다시 실행한다.
# `st.cache_resource`는 이 함수가 반환한 Agent 같은 resource를 실행 사이에 재사용한다.
# 따라서 매 rerun마다 LLM/DB 연결 객체를 새로 만들지 않고 기존 resource를 쓴다.
# endregion
@st.cache_resource
def get_car_manual():
    """Agent와 검색 service를 한 번 만들고 첫 검색 전 DB 연결을 준비한다."""
    car_manual = CarManual()
    # cache_resource 함수는 resource 최초 생성 때만 실행되므로 첫 검색 전에 최소 DB connection을 준비한다.
    sql_session = car_manual.service.sql_session
    sql_session.database_manager.warmup(camel_case_keys=sql_session.camel_case_keys)
    return car_manual


car_manual = get_car_manual()


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

    # Agent에는 이번 질문을 추가하기 전 대화 중 최근 6개 message만 전달한다.
    # region [Python 설명] list slicing과 대화 snapshot
    # `[-6:]`은 messages의 마지막 6개 message를 새 list로 만든다.
    # 아래에서 현재 user question을 session history에 추가해도 snapshot에는 포함되지 않아,
    # 현재 질문은 별도 `question` 인자로 한 번만 전달된다.
    # endregion
    conversation_history = st.session_state["messages"][-6:]

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
                if _is_conversation_download_request(question):
                    # UI session에 저장된 전체 대화로 HTML을 만들고 성공 여부를 확인한다.
                    logger.info("Conversation history download request detected")
                    sources, images = [], []
                    try:
                        download_html = car_manual.prepare_history_html(
                            st.session_state["messages"]
                        )
                    except Exception:
                        logger.exception("Conversation history HTML preparation failed")
                        download_html = None

                    if download_html:
                        try:
                            # HTML 준비 후 버튼 렌더링까지 성공한 경우에만 완료를 알린다.
                            st.download_button(
                                label="📥 대화 기록 HTML 다운로드",
                                data=download_html,
                                file_name="car_manual_history.html",
                                mime="text/html",
                            )
                        except Exception:
                            logger.exception(
                                "Conversation history download button rendering failed"
                            )
                            answer = "다운로드 버튼을 표시하지 못했습니다. 다시 시도해 주세요."
                            st.error(answer)
                        else:
                            answer = "대화 기록 HTML 다운로드를 준비했습니다."
                            st.markdown(answer)
                            logger.info(
                                "Conversation history download button displayed export_messages=%d",
                                len(st.session_state["messages"]),
                            )
                    else:
                        answer = "대화 기록 HTML을 만들지 못했습니다. 다시 시도해 주세요."
                        st.error(answer)
                else:
                    # 일반 질문은 기존 Agent streaming 경로로 처리한다.
                    answer_result = car_manual.ask_with_sources_stream(
                        car_brand_eng_nm=car_brand_eng_nm,
                        car_eng_nm=car_eng_nm,
                        car_model_yr=car_model_yr,
                        question=question,
                        limit=10,
                        conversation_history=conversation_history,
                    )

                    # streaming output을 넣고 최종 Markdown으로 갱신할 placeholder를 만든다.
                    # region [Streamlit 설명] st.empty() placeholder
                    # `st.empty()`는 나중에 내용을 채우거나 바꿀 수 있는 화면 위치를 만든다.
                    # 같은 placeholder에 streaming text를 먼저 표시하고 최종 답변 Markdown을 다시 쓴다.
                    # endregion
                    answer_placeholder = st.empty()

                    # Agent가 보내는 답변 조각을 화면에 순서대로 출력한다.
                    # region [Streamlit 설명] st.write_stream()
                    # `write_stream()`은 iterator/generator의 값을 하나씩 화면에 출력한다.
                    # 문자열만 stream하면 완료 후 전체 문자열도 반환하므로 최종 답변 복원에 쓸 수 있다.
                    # endregion
                    streamed_answer = answer_placeholder.write_stream(answer_result.chunks)

                    # service가 저장한 전체 답변을 우선하고, 없으면 UI stream 반환값을 사용한다.
                    # region [Python 설명] `or` fallback
                    # 빈 문자열은 falsy이므로 `answer_result.answer`가 비어 있으면 `streamed_answer`가 선택된다.
                    # endregion
                    answer = answer_result.answer or streamed_answer

                    # placeholder에 완성 답변 전체를 Markdown으로 표시한다.
                    answer_placeholder.markdown(answer)

                    # streaming 중 수집된 오류가 있으면 답변과 함께 사용자에게 알린다.
                    if answer_result.error is not None:
                        st.error(f"답변 생성 중 오류가 발생했습니다: {answer_result.error}")

                    # 답변 생성이 끝난 뒤 검색 출처와 관련 이미지를 선택한다.
                    # region [Python 설명] 여러 값 unpacking과 callback 전달
                    # `_display_metadata()`는 `(sources, images)` tuple을 반환한다.
                    # 검색 service의 image selector 함수를 callback으로 전달해 질문 관련 이미지를 고른다.
                    # endregion
                    sources, images = _display_metadata(
                        answer_result.search_results,
                        question=question,
                        answer=answer,
                        image_selector=car_manual.service.select_relevant_images,
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
