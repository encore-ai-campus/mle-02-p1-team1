"""개인 싼타페 PDF 검색·답변·출처·그림을 보여주는 로컬 Streamlit 화면입니다."""

import json
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import streamlit as st


# [프로젝트 추가] 어디에서 실행해도 기존 개인 서비스의 import 경로를 찾습니다.
# 화면의 입력·출력만 담당하며 PDF 처리·검색·생성 규칙은 서비스에서 재사용합니다.
SRC_FOLDER = Path(__file__).resolve().parents[2]
if str(SRC_FOLDER) not in sys.path:
    sys.path.insert(0, str(SRC_FOLDER))

# [프로젝트 적용] 이미 저장한 개인 전체 처리 작업입니다. 팀원 자료와 섞지 않습니다.
FULL_RUN_ID = "ca9d2721-3d48-42a8-8748-3935e78515e5"
MAX_HISTORY = 10
EXAMPLE_QUESTIONS = {
    "차대번호 위치": "차대번호가 새겨진 위치를 그림으로 보여줘.",
    "엔진 오일": "엔진 오일 교체 시 주입량과 추천 SAE 점도와 점도 표의 온도 눈금을 각각 알려줘.",
    "안전벨트": "안전벨트 버클을 밀어 넣는 기준과 안전벨트 차단 클립 사용 시 문제와 안전벨트 스토퍼 사용 시 문제를 각각 알려줘.",
    "미러 버튼 위치": "실외 미러 접이 버튼 위치를 그림으로 보여줘.",
}


def initialize_state():
    """이 브라우저의 서비스·최근 질문·입력칸을 처음 한 번 준비합니다."""
    # [프로젝트 추가] 화면 버튼을 누르면 파일 전체가 다시 실행됩니다.
    # session_state에 결과를 보관해 화면 조작만으로 검색·API가 반복되지 않게 합니다.
    defaults = {
        "zzong_service": None,
        "zzong_history": [],
        "zzong_question": "",
        "zzong_history_selection": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def fill_question(question):
    """예시 버튼이 질문 입력칸만 채웁니다. 검색이나 생성은 실행하지 않습니다."""
    # 콜백은 화면을 다시 그리기 전에 실행되므로 입력칸 값을 안전하게 바꿀 수 있습니다.
    st.session_state.zzong_question = question


def clear_history():
    """현재 화면의 질문·답변 기록만 지웁니다. DB·파일과 준비된 모델은 유지합니다."""
    st.session_state.zzong_history = []
    st.session_state.zzong_history_selection = None
    st.session_state.zzong_question = ""


def get_service():
    """첫 질문 제출 때 서비스를 만들고 같은 브라우저의 다음 질문에 재사용합니다."""
    # [프로젝트 적용] 시작 화면만 열었을 때는 DB 조회·모델 준비·OpenAI 호출을 하지 않습니다.
    # 무거운 검색 라이브러리도 첫 검색 때 불러옵니다. 키는 기존 개인 설정에서 읽습니다.
    if st.session_state.zzong_service is None:
        from car_search_rag.zzong_santafe_lag.llm_answer_service import LlmManualAnswerService

        st.session_state.zzong_service = LlmManualAnswerService(FULL_RUN_ID)
    return st.session_state.zzong_service


def search_question(question):
    """질문만 임베딩하고 개인 DB의 확인 근거를 찾아 화면 기록에 추가합니다."""
    question = question.strip()
    if not question:
        st.warning("질문을 입력해 주세요.")
        return
    # 새 검색이 실패했을 때 이전 답변을 새 질문의 결과로 오해하지 않게 선택을 비웁니다.
    st.session_state.zzong_history_selection = None
    try:
        with st.spinner("설명서에서 찾고 있습니다. 첫 검색은 준비 시간이 더 걸릴 수 있습니다."):
            evidence = get_service().prepare_evidence(question, top_k=5)
    except Exception as error:
        # 인증·연결 문자열이 오류에 들어 있을 수 있어 내용 대신 오류 종류만 표시합니다.
        st.error(f"설명서 검색을 완료하지 못했습니다. 연결 설정을 확인해 주세요. ({type(error).__name__})")
        return

    entry = {
        "id": uuid4().hex,
        "question": question,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "evidence": evidence,
        "generated": None,
        "generation_requested": False,
        "generation_error": None,
    }
    st.session_state.zzong_history.append(entry)
    # [프로젝트 추가] 부모 원문도 보관하므로 화면 기록을 최근 10개로 제한합니다.
    st.session_state.zzong_history = st.session_state.zzong_history[-MAX_HISTORY:]
    st.session_state.zzong_history_selection = entry["id"]


def select_history():
    """검색 후 최근 질문 목록을 그리고 사용자가 선택한 기록을 반환합니다."""
    history = st.session_state.zzong_history
    if not history:
        return None
    by_id = {entry["id"]: entry for entry in history}
    with st.sidebar:
        st.subheader("최근 질문")
        selected = st.selectbox(
            "확인할 질문",
            options=[None, *reversed(list(by_id))],
            key="zzong_history_selection",
            format_func=lambda identity: "질문을 선택해 주세요" if identity is None
            else by_id[identity]["question"][:70],
        )
        st.caption("최근 10개를 이 브라우저에서만 보관합니다. 새로고침하면 초기화될 수 있습니다.")
    return by_id.get(selected)


def generate_answer(entry, service, preview):
    """사용자가 생성 버튼을 눌렀을 때만 기존 근거로 한 번 답변을 정리합니다."""
    configured = service.settings()["api_key_configured"]
    disabled = not preview["ready_for_generation"] or not configured or entry["generation_requested"]
    if not preview["ready_for_generation"]:
        st.info(preview["reason"])
    elif not configured:
        st.info("답변 생성용 API 키 설정이 없습니다. 설명서 발췌와 출처는 확인할 수 있습니다.")
    elif not entry["generation_requested"]:
        st.caption("PDF 근거를 확인한 뒤 누르세요. OpenAI 호출 비용이 발생하며 질문과 선택한 근거 글을 전송합니다.")

    if st.button("답변 정리하기", key=f"generate_{entry['id']}", disabled=disabled, type="primary"):
        # [프로젝트 추가] 호출 전에 표시를 남겨 화면 재실행·버튼 중복으로 재생성하지 않습니다.
        # 실패해도 자동 재시도하지 않습니다. 다시 시도하려면 질문을 새로 제출합니다.
        entry["generation_requested"] = True
        try:
            with st.spinner("확인한 PDF 근거로 답변을 정리하고 있습니다."):
                entry["generated"] = service.generate(entry["evidence"])
        except Exception as error:
            entry["generation_error"] = type(error).__name__
        st.rerun()


def show_sources(result):
    """답변 번호와 대응하는 PDF 쪽수·검색용 글·보존 원문을 보여줍니다."""
    sources = result.get("sources", [])
    if not sources:
        st.info("확정 답변에 사용할 출처가 없습니다.")
    for source in sources:
        title = f"{source['label']} · {source['title']}"
        with st.expander(title):
            st.caption("답변의 [번호]와 같은 출처입니다. PDF 쪽수와 책에 인쇄된 매뉴얼 쪽수는 다를 수 있습니다.")
            st.markdown("**확인한 PDF 근거**")
            # 원문을 Markdown 지시나 HTML로 실행하지 않고 글자 그대로 보여줍니다.
            st.text(source["quote"])
            st.markdown("**전처리 전 보존 원문**")
            st.text(source.get("raw_text", ""))


def show_images(result):
    """준비된 그림만 표시하고 파일·설명 연결 확인이 남은 그림은 별도 안내합니다."""
    # [프로젝트 적용] 서비스가 검토한 설명과 공개 주소를 모두 확인해 images에 넣은 결과만 씁니다.
    # pending_image_references에서 주소나 로컬 파일을 추측해 표시하지 않습니다.
    images = result.get("images", [])
    for image in images:
        descriptions = list(dict.fromkeys(
            row["description"] for row in image.get("descriptions", []) if row.get("description")
        ))
        if not image.get("public_url") or not descriptions:
            st.info("그림 파일 또는 설명 연결 확인이 남아 있습니다.")
            continue
        caption = f"PDF {image['pdf_page_number']}쪽 · " + " / ".join(descriptions)
        try:
            st.image(image["public_url"], caption=caption, width="stretch")
        except Exception:
            st.warning("그림을 불러오지 못했습니다. 해당 출처의 설명과 PDF 원문을 확인해 주세요.")
        # 공개 주소 반환은 실제 브라우저 이미지 로드 성공을 보증하지 않습니다.
        st.link_button(f"PDF {image['pdf_page_number']}쪽 그림 열기", image["public_url"])

    pending = result.get("pending_image_references", [])
    if pending:
        pages = ", ".join(str(page) for page in sorted({image["pdf_page_number"] for image in pending}))
        st.info(f"PDF {pages}쪽의 그림 {len(pending)}개는 파일 업로드 또는 설명 연결 확인이 남아 있어 표시를 보류했습니다.")
    if not images and not pending:
        st.caption("이번 답변에 연결된 그림이 없습니다.")


def show_result(entry):
    """선택한 질문의 발췌·생성 답변·출처·그림·파일 내려받기를 한곳에 배치합니다."""
    st.subheader("확인 중인 질문")
    st.write(entry["question"])
    service = get_service()
    preview = service.preview(entry["evidence"])
    generate_answer(entry, service, preview)

    result = entry["generated"] or entry["evidence"]
    if entry["generation_error"]:
        st.warning(f"생성을 완료하지 못해 설명서 발췌를 유지합니다. ({entry['generation_error']})")
    if result.get("generation_notice"):
        st.info(result["generation_notice"])

    answer_tab, source_tab, image_tab = st.tabs(["답변", "출처와 원문", "관련 그림"])
    with answer_tab:
        if result["status"] == "generated_answer":
            st.caption("PDF 근거로 정리한 답변입니다. 출처에서 수치·조건·주의사항을 함께 확인하세요.")
        elif result["status"] in {"evidence_excerpt", "partial_evidence"}:
            st.caption("설명서에서 확인한 글을 발췌했습니다.")
        else:
            st.caption("현재 자료로 답변할 수 있는지 확인한 결과입니다.")
        st.markdown(result["answer"])
        if result.get("reason"):
            st.info(result["reason"])
        usage = result.get("token_usage")
        if usage:
            st.caption(f"이번 생성 사용량: 입력 {usage.get('input_tokens', 0):,} · 출력 {usage.get('output_tokens', 0):,} · 합계 {usage.get('total_tokens', 0):,}토큰")
    with source_tab:
        show_sources(result)
    with image_tab:
        show_images(result)

    # [프로젝트 추가] 사용자가 눌러 자신의 PC로 내려받습니다. DB·서버 보고서에 자동 저장하지 않습니다.
    export = {"created_at": entry["created_at"], "evidence": entry["evidence"], "answer_result": result}
    st.download_button(
        "답변과 출처 저장",
        data=json.dumps(export, ensure_ascii=False, indent=2),
        file_name=f"santafe_answer_{entry['id'][:12]}.json",
        mime="application/json",
        key=f"download_{entry['id']}",
    )
    if entry["generation_requested"]:
        st.caption("이 질문은 답변 정리를 한 번 시도했습니다. 다시 시도하려면 질문을 새로 제출하세요.")


def main():
    """시작 화면을 그리고 명시적 질문 제출·생성 버튼에만 작업을 연결합니다."""
    st.set_page_config(page_title="싼타페 HEV 설명서 도우미", page_icon="🚙", layout="wide")
    initialize_state()
    st.title("싼타페 HEV 설명서 도우미")
    st.caption("제공된 설명서에서 근거를 찾고, 답변과 페이지·그림을 함께 확인합니다.")

    with st.sidebar:
        st.header("예시 질문")
        for label, question in EXAMPLE_QUESTIONS.items():
            st.button(label, key=f"example_{label}", on_click=fill_question, args=(question,))
        st.divider()
        st.info("설명서에 없는 최신 리콜·실제 차량 진단은 확인할 수 없습니다. 검토가 남은 자료는 답변을 보류합니다.")
        st.button("화면 기록 지우기", on_click=clear_history)

    # [프로젝트 추가] 글자를 입력할 때마다 검색하지 않고 폼 제출 때만 조회합니다.
    with st.form("zzong_question_form"):
        question = st.text_area("궁금한 내용을 입력하세요", key="zzong_question", height=110, max_chars=2000)
        submitted = st.form_submit_button("PDF에서 찾기", type="primary")
    st.caption("질문은 각각 독립적으로 검색합니다. 예시 선택만으로는 검색하거나 답변을 생성하지 않습니다.")
    if submitted:
        search_question(question)

    # 검색 처리 후 선택 위젯을 만들므로 새 질문을 바로 선택해도 위젯 상태 충돌이 없습니다.
    entry = select_history()
    if entry is None:
        st.info("질문을 입력하고 'PDF에서 찾기'를 눌러 주세요.")
    else:
        show_result(entry)


if __name__ == "__main__":
    main()
