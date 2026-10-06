"""개인 분석 요약만 표시합니다. 화면 표시 중 DB·검색·생성 호출은 없습니다."""

import json

import altair as alt
import pandas as pd
import streamlit as st

from .data_analysis import OUTPUT

TYPE_LABELS = {"instruction_text":"사용·주의 설명", "figure_with_text":"그림 포함 설명",
               "vehicle_overview_navigation":"위치 안내도", "structured_table":"구조화 표",
               "table_with_images":"그림 포함 표", "heading":"제목"}
QUALITY_LABELS = {"empty_content":"빈 본문", "empty_title":"빈 제목", "missing_pages":"쪽수 누락",
                  "invalid_pages":"유효하지 않은 쪽수", "duplicate_record_ids":"자료 ID 중복",
                  "exact_duplicate_content_excess":"동일 본문 반복", "orphan_chunks":"부모 없는 청크",
                  "parents_without_chunks":"검색 청크 없는 부모"}


def render_data_dashboard():
    """설명서 유형·길이·검토 상태·점검 결과와 한계를 표시합니다. 정답률은 표시하지 않습니다."""
    st.title("싼타페 설명서 데이터 분석")
    file = OUTPUT / "summary.json"
    if not file.exists():
        st.info("분석 결과가 아직 없습니다. 개인 데이터 분석 작업을 먼저 실행해주세요.")
        return
    summary = json.loads(file.read_text(encoding="utf-8"))
    c = summary["counts"]
    st.caption(f"저장 자료와 활성 검토 버전의 분석 · 조회 시각(UTC): {summary['created_at']}")
    st.info("설명서 자료의 분포와 점검 결과입니다. 검토 비율은 챗봇의 정답률이 아닙니다.")
    columns = st.columns(4)
    for col, label, number in zip(columns, ["설명서 페이지", "현재 부모 자료", "현재 검색 청크", "연결된 그림"],
                                   [c["pdf_pages"], c["effective_parents"], c["effective_chunks"], c["linked_unique_images"]]):
        col.metric(label, f"{number:,}")
    frame = pd.DataFrame(summary["parents"])
    left, right = st.columns(2)
    with left:
        st.subheader("자료 유형")
        counts = pd.DataFrame([{"유형":TYPE_LABELS.get(k,k), "자료 수":v} for k,v in summary["type_counts"].items()])
        st.bar_chart(counts, x="유형", y="자료 수", horizontal=True)
    with right:
        st.subheader("원문 검토 상태")
        st.bar_chart(pd.DataFrame({"상태":["검토됨", "미검토"],
                                 "자료 수":[c["reviewed_parents"],c["unreviewed_parents"]]}), x="상태", y="자료 수")
        st.caption("미검토 원문과 필수 문맥은 확정 답변 생성에 사용하지 않습니다.")
    st.subheader("본문 길이 분포")
    chart = alt.Chart(frame).mark_bar().encode(
        x=alt.X("characters:Q", bin=alt.Bin(maxbins=20), title="본문 문자 수"),
        y=alt.Y("count():Q", title="자료 수"), tooltip=[alt.Tooltip("count():Q",title="자료 수")])
    st.altair_chart(chart, use_container_width=True)
    st.subheader("본문 길이와 청크 수")
    st.scatter_chart(frame.rename(columns={"characters":"본문 문자 수", "chunks":"청크 수"}),
                     x="본문 문자 수", y="청크 수")
    st.caption(f"순위 상관계수: {summary['length_chunk_rank_correlation']} · 인과관계나 검색 정확도 지표가 아닙니다.")
    st.dataframe(pd.DataFrame(summary["length_statistics"]).rename(columns={"characters":"본문 문자 수","chunks":"청크 수"}), use_container_width=True)
    st.subheader("데이터 점검")
    st.dataframe(pd.DataFrame([{"점검 항목":QUALITY_LABELS[k],"대상 건수":v}
                               for k,v in summary["quality_checks"].items()]), hide_index=True)
    st.subheader("분석에서 확인한 점")
    ratio = c["reviewed_parents"] / c["effective_parents"] * 100
    st.write(f"검토된 부모는 {c['reviewed_parents']}개({ratio:.1f}%)입니다. 미검토 자료가 많아 원문 제공과 답변 보류 처리가 필요합니다.")
    st.write("본문 길이 차이가 있어 검색용 청크와 전체 원문 문맥을 함께 관리합니다. 검색 성능은 별도 평가로 확인해야 합니다.")
    with st.expander("자료 목록과 분석 범위"):
        st.dataframe(frame.rename(columns={"title":"자료 제목","characters":"문자 수","chunks":"청크 수"}), hide_index=True)
        for limitation in summary["limitations"]:
            st.write("- " + limitation)
        st.caption(f"기본 청크 {c['base_chunks']}개 → 활성 검토 반영 청크 {c['effective_chunks']}개")
        st.text(f"원문 버전: {summary['source_run_id']}\n검토 버전: {summary['review_revision_id']}")
    st.download_button("분석 보고서 다운로드", (OUTPUT / "report.md").read_text(encoding="utf-8"),
                       file_name="santafe_data_analysis.md", mime="text/markdown", on_click="ignore")
    st.download_button("분석 집계 JSON 다운로드", file.read_bytes(), file_name="santafe_analysis.json",
                       mime="application/json", on_click="ignore")


def render_distribution_dashboard():
    """기존 분석 스냅샷으로 페이지 분포·유형별 검토·자료 필터를 추가합니다."""
    file = OUTPUT / "summary.json"
    if not file.exists():
        st.info("분석 집계가 아직 없습니다.")
        return
    summary = json.loads(file.read_text(encoding="utf-8"))
    frame = pd.DataFrame(summary["parents"])
    st.subheader("페이지별 자료 분포")
    # 같은 부모가 한 페이지를 반복 참조해도 한 건만 집계합니다. 추출 성공률이 아닙니다.
    pages = pd.DataFrame([{"PDF 페이지":page,"부모 자료 수":1} for row in summary["parents"]
                          for page in set(row["source_pages"]) if type(page) is int and 1<=page<=summary["counts"]["pdf_pages"]])
    counts = pages.groupby("PDF 페이지")["부모 자료 수"].sum().reindex(range(1,summary["counts"]["pdf_pages"]+1),fill_value=0)
    st.line_chart(counts)
    c = summary["counts"]
    st.caption(f"부모 자료가 참조한 페이지 {c['parent_referenced_pages']}/{c['pdf_pages']}쪽. 0인 페이지는 이 저장 목록의 참조가 없는 페이지이며 추출 실패라고 단정할 수 없습니다.")
    st.subheader("유형별 검토 현황")
    frame["자료 유형"] = frame["content_type"].map(lambda v:TYPE_LABELS.get(v,v))
    frame["검토 상태"] = frame["verification_status"].map(
        lambda v:"검토됨" if v in {"sample_verified","visually_reviewed_source"} else "미검토")
    st.dataframe(pd.crosstab(frame["자료 유형"],frame["검토 상태"]),use_container_width=True)
    st.subheader("자료 찾아보기")
    left,right = st.columns(2)
    kind = left.selectbox("자료 유형",["전체",*sorted(frame["자료 유형"].unique())],key="santafe_data_type")
    state = right.selectbox("검토 상태",["전체","검토됨","미검토"],key="santafe_data_review")
    keyword = st.text_input("제목에서 찾을 말",key="santafe_data_keyword")
    selected=frame
    if kind!="전체":
        selected=selected[selected["자료 유형"]==kind]
    if state!="전체":
        selected=selected[selected["검토 상태"]==state]
    if keyword.strip():
        selected=selected[selected["title"].str.contains(keyword.strip(),case=False,regex=False,na=False)]
    st.caption(f"조건에 맞는 자료 {len(selected)}개 · 분석 기준 시각(UTC): {summary['created_at']}")
    st.dataframe(selected[["title","자료 유형","검토 상태","characters","chunks","source_pages"]]
                 .rename(columns={"title":"제목","characters":"문자 수","chunks":"청크 수","source_pages":"PDF 페이지"}),
                 hide_index=True,use_container_width=True)


def render_dashboard():
    """개인 싼타페 화면 안에서 분석·자료 분포·50문항 평가 탭을 표시합니다."""
    from .evaluation_dashboard import render_evaluation_dashboard
    from .evaluation_30_dashboard import render_additional_evaluation
    analysis,distribution,evaluation,additional=st.tabs(["설명서 분석","자료 분포·목록","50문항 평가","추가 30문항 평가"])
    with analysis:
        render_data_dashboard()
    with distribution:
        render_distribution_dashboard()
    with evaluation:
        render_evaluation_dashboard()
    with additional:
        render_additional_evaluation()
