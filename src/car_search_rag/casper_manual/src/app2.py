"""Streamlit 실습: 앱 시작 시 모델을 준비하고 질문 UI를 표시합니다."""

from time import perf_counter

import streamlit as st

from rag import download_model_weights, get_rag, DEFAULT_TOP_K
from portal_theme import apply_theme, hero, footer
from project_portal import PAGES, render_project_page


st.set_page_config(
    page_title="CASPER | 매뉴얼과 프로젝트",
    page_icon="🚙",
    layout="wide",
)

EXAMPLES = {
    "🔌 충전": "충전 커넥터가 빠지지 않을 때 어떻게 해야 해?",
    "🕒 예약 충전": "예약 충전을 설정했는데 지금 바로 충전하려면 어떻게 해?",
    "🚗 주행 보조": "차로 유지 보조가 제대로 작동하지 않을 수 있는 상황은 뭐야?",
}


def initialize_state():
    defaults = {
        "practice_history": [],
        "practice_selected": None,
        "practice_question": "",
        "practice_top_k": DEFAULT_TOP_K,
        "rag_ready": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def fill_question(question):
    st.session_state.practice_question = question


def select_history(index):
    st.session_state.practice_selected = index


def clear_history():
    st.session_state.practice_history = []
    st.session_state.practice_selected = None
    st.session_state.practice_question = ""


@st.cache_resource
def prepare_rag():
    return get_rag()


def ensure_rag_ready():
    """질문 폼을 그리기 전에 모델 가중치를 받고 RAG를 초기화합니다."""
    if st.session_state.rag_ready:
        return

    st.subheader("매뉴얼 검색 모델 준비 중")
    st.caption("처음에는 약 1.1GB 모델 파일을 내려받고 로드합니다.")
    download_bar = st.progress(0.0, text="모델 가중치 파일 확인 중…")
    stage = st.empty()

    def update_download(done, total):
        if total:
            fraction = min(done / total, 1.0)
            size_text = f"{done / 1_000_000_000:.2f} / {total / 1_000_000_000:.2f} GB"
            download_bar.progress(fraction, text=f"모델 파일 다운로드 · {size_text}")
        else:
            download_bar.progress(0.0, text=f"모델 파일 다운로드 · {done / 1_000_000:.0f} MB")

    try:
        _, was_cached = download_model_weights(update_download)
        if was_cached:
            download_bar.progress(1.0, text="캐시에 있는 모델 가중치를 확인했습니다")
        else:
            download_bar.progress(1.0, text="모델 파일 다운로드 완료")
        stage.info("임베딩 모델을 메모리에 올리는 중입니다. 잠시 기다려 주세요.")
        prepare_rag()
        stage.success("모델 준비가 완료됐습니다. 이제 질문할 수 있어요.")
        st.session_state.rag_ready = True
    except Exception:
        st.error("모델 준비에 실패했습니다. 잠시 후 다시 시도하거나 앱 로그를 확인해 주세요.")
        st.stop()


def render_header():
    hero("CASPER ELECTRIC / MANUAL SEARCH", "내 차가 궁금할 때, 매뉴얼에서 찾아보세요", "질문에 가까운 설명을 찾아 답합니다. 답변을 읽고 같은 번호의 매뉴얼 근거를 함께 확인하세요.")


def render_sidebar():
    with st.sidebar:
        st.subheader("검색 설정")
        st.slider(
            "검색할 매뉴얼 조각 수",
            min_value=1,
            max_value=10,
            key="practice_top_k",
            help="다음 질문부터 적용됩니다. 기본값은 5개입니다.",
        )

        st.subheader("예시 질문")
        for label, question in EXAMPLES.items():
            st.button(
                label,
                key=f"example_{label}",
                on_click=fill_question,
                args=(question,),
                use_container_width=True,
            )
        st.caption("예시를 누른 뒤 질문 폼에서 제출하세요.")
        st.divider()

        history = st.session_state.practice_history
        st.subheader(f"질문 기록 · {len(history)}")
        for index in range(len(history) - 1, -1, -1):
            question = history[index]["question"]
            label = question[:24] + ("…" if len(question) > 24 else "")
            st.button(
                f"{index + 1}. {label}",
                key=f"history_{index}",
                help=question,
                on_click=select_history,
                args=(index,),
                use_container_width=True,
            )

        st.button(
            "기록 지우기",
            on_click=clear_history,
            disabled=not history,
            use_container_width=True,
        )
        st.caption("기록은 현재 브라우저 세션에서만 유지됩니다.")


def render_question_form():
    st.caption("01 · ASK")
    st.subheader("어떤 점이 궁금한가요?")

    with st.form("question_form"):
        question = st.text_area(
            "질문",
            key="practice_question",
            placeholder="대상과 상황을 구체적으로 적어 주세요.",
            height=160,
        )
        submitted = st.form_submit_button(
            "매뉴얼에서 답변 찾기",
            type="primary",
            use_container_width=True,
        )

    st.caption("각 질문은 독립적으로 검색합니다.")
    if not submitted:
        return

    question = question.strip()
    if not question:
        st.warning("질문을 입력해 주세요.")
        return

    try:
        started = perf_counter()
        with st.spinner("매뉴얼을 검색하고 답변을 작성하고 있습니다…"):
            result = prepare_rag().ask_manual(
                question,
                top_k=st.session_state.practice_top_k,
            )
        result = {**result, "elapsed_seconds": perf_counter() - started}
    except Exception:
        st.error("답변을 가져오지 못했습니다. 연결과 Secrets 설정을 확인하세요.")
        return

    st.session_state.practice_history.append(result)
    st.session_state.practice_selected = len(st.session_state.practice_history) - 1
    st.rerun()


def render_result():
    st.caption("02 · CHECK")
    st.subheader("답변과 검색 근거")
    history = st.session_state.practice_history
    selected = st.session_state.practice_selected

    if selected is None or not history:
        with st.container(border=True):
            st.markdown("### 📖 매뉴얼에서 답변을 찾아보세요")
            st.write("왼쪽 질문 폼을 제출하면 이곳에 답변이 표시됩니다.")
        return

    result = history[selected]
    with st.container(border=True):
        st.markdown("**선택한 질문**")
        st.write(result["question"])
        count_column, time_column = st.columns(2)
        count_column.metric("검색 근거", f"{len(result['sources'])}개")
        time_column.metric("처리 시간", f"{result['elapsed_seconds']:.1f}초")
        answer_tab, sources_tab = st.tabs(["💬 답변", "📚 검색 근거"])
        with answer_tab:
            st.markdown(result["answer"])
            st.caption("답변의 [번호]를 검색 근거의 같은 번호와 비교하세요.")
        with sources_tab:
            if not result["sources"]:
                st.info("표시할 검색 근거가 없습니다.")
            for source in result["sources"]:
                title = f"[{source['citation_id']}] {source['source_title']}"
                with st.expander(title):
                    st.caption(
                        f"PDF {source['page_start']}~{source['page_end']}쪽"
                        f" · 유사도 {source['similarity']:.4f}"
                    )
                    st.text(source["chunk_text"])
            st.caption("검색 유사도는 정답 확률이 아닙니다.")


def main():
    initialize_state()
    apply_theme()
    with st.sidebar:
        st.header("CASPER")
        st.caption("매뉴얼에서 답을 찾고, 만든 과정을 살펴보세요.")
        page = st.radio("화면 선택", PAGES, key="project_page", label_visibility="collapsed")
        st.divider()
    if page == "매뉴얼 질문하기":
        render_sidebar()
        render_header()
        ensure_rag_ready()
        question_column, result_column = st.columns([4, 6], gap="large")
        with question_column:
            render_question_form()
        with result_column:
            render_result()
    else:
        render_project_page(page)
    footer()


if __name__ == "__main__":
    main()
