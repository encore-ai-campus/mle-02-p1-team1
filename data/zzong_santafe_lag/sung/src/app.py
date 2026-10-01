"""실행: uv run streamlit run src/app.py"""
import streamlit as st
from rag import get_rag

st.set_page_config(page_title="캐스퍼 매뉴얼 도우미", page_icon="🚙", layout="centered")


@st.cache_resource
def prepare_rag():
    return get_rag()


def show_result(result):
    st.markdown(result["answer"])
    if result["sources"]:
        with st.expander("매뉴얼 근거 확인"):
            for source in result["sources"]:
                st.markdown(f"**[{source['citation_id']}] {source['source_title']}**")
                st.caption(f"PDF {source['page_start']}~{source['page_end']} · "
                           f"{source['chunk_id']} · 검색 유사도 {source['similarity']:.4f}")
                st.text(source["chunk_text"])
                st.divider()


st.title("🚙 캐스퍼 매뉴얼 도우미")
st.write("캐스퍼 일렉트릭의 기능과 사용 방법을 물어보세요.")
st.caption("예: 충전 커넥터가 빠지지 않을 때 어떻게 해야 해?")
st.caption("질문마다 매뉴얼을 새로 검색합니다. 각 질문에 대상과 상황을 적어 주세요.")

if "manual_history" not in st.session_state:
    st.session_state.manual_history = []

if st.sidebar.button("대화 지우기"):
    st.session_state.manual_history = []

for item in st.session_state.manual_history:
    with st.chat_message("user"):
        st.write(item["question"])
    with st.chat_message("assistant"):
        show_result(item)

question = st.chat_input("매뉴얼에 대해 질문하세요")
if question and question.strip():
    with st.chat_message("user"):
        st.write(question)
    with st.chat_message("assistant"):
        try:
            with st.spinner("매뉴얼을 검색하고 답변을 작성하고 있습니다…"):
                result = prepare_rag().ask_manual(question, top_k=5)
            show_result(result)
            st.session_state.manual_history.append(result)
        except ValueError as error:
            st.error(str(error))
        except Exception:
            # 외부 API 오류에 포함될 수 있는 연결 정보는 화면에 출력하지 않습니다.
            st.error("답변을 가져오지 못했습니다. 연결과 API 설정을 확인한 뒤 다시 시도해 주세요.")
