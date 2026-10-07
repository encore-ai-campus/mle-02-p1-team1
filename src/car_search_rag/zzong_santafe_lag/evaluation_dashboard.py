"""저장된 50문항 평가 결과를 표시합니다. 검색·생성·DB 쓰기를 실행하지 않습니다."""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

FOLDER = Path(__file__).resolve().parent
RESULTS = FOLDER / "evaluation_50_results"
GROUP_LABELS = {"A":"설명서 밖 질문", "B":"직접 키워드 질문", "C":"모호한 표현·증상 질문"}
STATUS_LABELS = {"needs_review":"미검토 자료 안내", "evidence_excerpt":"검토 자료 연결",
                 "needs_clarification":"확인 질문", "insufficient_evidence":"근거 부족 안내"}


def render_screenshot_evaluation():
    """사용자 실행 화면의 판정을 자동 초기 응답 결과와 별도로 표시합니다."""
    path = RESULTS / "screenshot_evaluation.json"
    if not path.exists():
        return
    recorded = json.loads(path.read_text(encoding="utf-8"))
    summary, rows = recorded["summary"], recorded["rows"]
    st.subheader("사용자 직접 실행 화면 평가")
    st.info("사용자가 실행한 캡처를 Codex가 판정한 기록입니다. 사용자 최종 판정 확정과는 구분합니다. 자동 평가는 초기 응답만, 직접 평가는 일부 생성 답변까지 확인하여 동일 조건의 전후 점수가 아닙니다.")
    cols = st.columns(4)
    for col, label, value in zip(cols, ["캡처 기록", "화면 대응 통과", "부분 충족", "화면 대응 실패"],
                                [summary["captured"], *[summary["counts"].get(k, 0) for k in ["통과", "부분", "실패"]]]):
        col.metric(label, f"{value}문항")
    st.caption(f"생성 답변 확인 {summary['generated_answers']}문항 · B04 추가 및 C07/C08 번호 정정 반영 · Hit@5·MRR 미산출")
    st.warning("B03·B04는 핵심 용량·규격 통과 판정을 유지했습니다. 일반 오일 게이지 F선 문구의 디퍼렌셜·트랜스퍼 케이스 적용 여부는 별도 검증이 필요합니다.")
    frame = pd.DataFrame(rows)
    group = st.selectbox("직접 평가 질문 유형", ["전체", "A", "B", "C"], key="santafe_screenshot_group")
    selected = frame if group == "전체" else frame[frame["group"] == group]
    labels = {"case_id":"번호", "question":"질문", "source_grade":"근거 판정", "overall":"직접 화면 판정",
              "generation_grade":"생성 평가", "automatic_overall":"자동 초기 응답 판정", "note":"보완 기록"}
    st.dataframe(selected[list(labels)].rename(columns=labels), hide_index=True, use_container_width=True)
    lookup = {row["case_id"]:row for row in rows}
    cid = st.selectbox("직접 평가 상세 문항", selected["case_id"].tolist(), key="santafe_screenshot_case")
    row = lookup[cid]
    with st.expander(f"{cid} · 직접 실행 화면 기록", expanded=True):
        st.write("질문: " + row["question"])
        st.write("표시된 자료: " + row["actual_sources"])
        st.write("캡처 응답 요약: " + row["response_summary"])
        st.write("판정·보완: " + row["note"])
        st.write("자동 평가 판정 이유: " + row["automatic_note"])
        st.caption("응답 요약은 전체 원문 전사가 아닙니다. C18은 질문이 캡처에 없어 평가지 문구로 대응시켰습니다.")
    csv = RESULTS / "screenshot_evaluation.csv"
    if csv.exists():
        st.download_button("직접·자동 평가 비교 CSV", csv.read_bytes(), file_name=csv.name, mime="text/csv", on_click="ignore")
    pdf = FOLDER.parents[2] / "output/pdf/santafe_evaluation_combined.pdf"
    if pdf.exists():
        st.download_button("통합 평가 PDF", pdf.read_bytes(), file_name=pdf.name, mime="application/pdf", on_click="ignore")
    st.divider()


def render_evaluation_dashboard():
    """AI 잠정 판정·실제 응답·실행 현황을 나눠 보여줍니다. 사람 판정은 임의로 채우지 않습니다."""
    render_screenshot_evaluation()
    st.subheader("기존 자동 50문항 검색·초기 응답 평가")
    files = [RESULTS / "summary.json", RESULTS / "graded_results.json", RESULTS / "results.json"]
    if not all(file.exists() for file in files):
        st.info("50문항 평가 결과가 아직 준비되지 않았습니다.")
        return
    # 화면을 열 때 로컬 결과를 다시 읽습니다. 대시보드 때문에 질문을 재실행하지 않습니다.
    summary, graded, raw = [json.loads(file.read_text(encoding="utf-8")) for file in files]
    st.info("AI 잠정 판정입니다. 직접 평가가 끝나기 전까지 확정 정답률로 사용하지 않습니다. 생성 답변과 Hit@5·MRR는 미평가입니다.")
    cols = st.columns(4)
    for col,label,value in zip(cols,["실행 완료", "잠정 통과", "부분 충족", "실패"],
                               [summary["completed"], *[summary["ai_provisional_counts"].get(k,0) for k in ["통과","부분","실패"]]]):
        col.metric(label,f"{value}문항")
    confirmed = sum(row.get("human_confirmed") is True for row in graded)
    st.caption(f"직접 판정 확인: {confirmed}/50문항 · 부분 충족은 통과에 포함하지 않음 · 원시 결과 기록(UTC): {raw.get('updated_at','미기록')}")
    st.write("아래 표는 보존된 자동 초기 응답 판정입니다. 직접 실행 화면 기록은 위에서 별도로 표시합니다.")
    frame = pd.DataFrame(graded)
    counts = pd.DataFrame([{"질문 유형":GROUP_LABELS[g],"판정":grade,"문항 수":summary["groups"][g].get(grade,0)}
                           for g in "ABC" for grade in ["통과","부분","실패"]])
    st.subheader("질문 유형별 잠정 판정")
    st.bar_chart(counts,x="질문 유형",y="문항 수",color="판정",stack=True)

    st.subheader("질문별 결과")
    left,right = st.columns(2)
    group = left.selectbox("질문 유형",["전체",*GROUP_LABELS],format_func=lambda v:GROUP_LABELS.get(v,v),key="santafe_eval_group")
    grade = right.selectbox("잠정 판정",["전체","통과","부분","실패"],key="santafe_eval_grade")
    selected = frame
    if group != "전체":
        selected = selected[selected["group"]==group]
    if grade != "전체":
        selected = selected[selected["overall"]==grade]
    labels = {"case_id":"번호","question":"질문","overall":"AI 잠정 판정","source_grade":"자료 연결",
              "response_grade":"초기 대응","expected":"기대 대응·근거","note":"판정 이유"}
    st.dataframe(selected[list(labels)].rename(columns=labels),hide_index=True,use_container_width=True)
    if not selected.empty:
        lookup = {row["case_id"]:row for row in graded}
        case_id = st.selectbox("상세히 볼 문항",selected["case_id"].tolist(),
                               format_func=lambda v:f"{v} · {lookup[v]['question']}",key="santafe_eval_case")
        row = lookup[case_id]
        st.markdown(f"**{row['case_id']} · {row['question']}**")
        st.write(f"AI 잠정 판정: {row['overall']} / 자료 연결: {row['source_grade']} / 초기 대응: {row['response_grade']}")
        st.write("기대 대응·근거: "+row["expected"])
        st.write("판정 이유: "+row["note"])
        with st.expander("실제로 나온 초기 응답",expanded=True):
            st.markdown(row["answer_text"])
        with st.expander("표시된 자료·페이지"):
            if not row["actual_sources"]:
                st.write("표시된 원문 없음. 확인 질문에는 자료 연결이 필요하지 않을 수 있습니다.")
            for source in row["actual_sources"]:
                st.write(f"{source['title']} · PDF {', '.join(map(str,source['pages']))}쪽")
            st.caption(f"이 문항의 검색: {row['search_count']}회 · 생성 답변: 미평가")
    else:
        st.caption("현재 조건에 해당하는 문항이 없습니다.")

    with st.expander("실행 현황과 평가 범위"):
        st.write(f"질문 실행 오류 {summary['failure_count']}건 · 검색 {summary['search_calls']}회 · 생성 호출 {summary['generation_calls']}회")
        st.dataframe(pd.DataFrame([{"처리 유형":STATUS_LABELS.get(k,k),"문항 수":v}
                                   for k,v in summary["status_counts"].items()]),hide_index=True)
        times = pd.DataFrame([{"번호":r["case_id"],"검색 여부":"검색 실행" if r["search_results"] else "확인 질문만",
                               "처리 시간(초)":r["seconds"]} for r in raw["results"]])
        st.dataframe(times.groupby("검색 여부")["처리 시간(초)"].agg(["count","median","min","max"]).round(2)
                     .rename(columns={"count":"문항 수","median":"중앙값","min":"최소","max":"최대"}))
        st.caption("처리 시간은 이번 실행 환경의 기록이며 첫 준비 시간 등을 포함합니다. 검색 없는 확인 질문과 검색 실행 문항을 구분했습니다.")
        st.write("질문마다 독립 대화로 실행했습니다. 생성 버튼·후속 대화·실제 화면 조작은 이번 자동 수집에 포함하지 않았습니다.")
        st.write("잠정 정답 기준은 수집 이후 AI가 작성했습니다. 검색 후보의 순위별 관련성 및 사용자 판정 확정 후 Hit@5·MRR를 계산해야 합니다.")
        if summary.get("finalization_recovered"):
            st.caption("마지막 파일 저장 접근 오류는 보존된 50개 결과로 복구했습니다. 질문 실행 오류와 구분합니다.")
    st.subheader("평가 자료 다운로드")
    csv = RESULTS / "human_grading.csv"
    if csv.exists():
        st.download_button("문항별 판정·실제 응답 CSV",csv.read_bytes(),file_name="santafe_evaluation_50.csv",mime="text/csv",on_click="ignore")
    pdf = FOLDER.parents[2] / "output/pdf/santafe_evaluation_50_graded.pdf"
    if pdf.exists():
        st.download_button("채점 PDF 다운로드",pdf.read_bytes(),file_name="santafe_evaluation_50_graded.pdf",mime="application/pdf",on_click="ignore")
