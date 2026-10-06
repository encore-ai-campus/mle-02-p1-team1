"""저장된 발표 내용과 수업 근거를 개인 챗봇에서 읽어 보여줍니다."""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

FOLDER = Path(__file__).resolve().parent
PRESENTATION = FOLDER / "presentation"


def load_content():
    """모델이나 DB를 준비하지 않고 발표 JSON만 읽습니다."""
    return json.loads((PRESENTATION / "content.json").read_text(encoding="utf-8"))


def render_milestones():
    """M0~M9의 구현 근거와 완료 범위를 보여줍니다."""
    content = load_content()
    st.subheader("M0~M9 구현과 검증")
    st.write(content["thesis"])
    st.caption("2026-10-07 정리 · 데이터·평가는 저장 당시 스냅샷 기준입니다.")
    st.dataframe(pd.DataFrame([
        {"단계": row["stage"], "주제": row["name"], "실제 구현": row["implementation"],
         "현재 상태와 한계": row["status"]} for row in content["milestones"]
    ]), hide_index=True, use_container_width=True)
    st.subheader("싼타페의 검색 구조")
    st.write("의미 검색 점수와 TF-IDF 키워드 점수를 각각 0.5 비중으로 합칩니다. "
             "질문 목적과 구체 표현을 추가로 반영하는 하이브리드 검색 기반 RAG입니다.")
    st.code(content["architecture"], language=None, wrap_lines=True)
    st.caption("현재 기본 경로는 DB에서 읽은 저장 벡터를 정렬합니다. "
               "BM25·RRF·CrossEncoder·LLM 재정렬은 이 싼타페 경로에 연결하지 않았습니다.")


def render_saved_comparisons():
    """기존 실험 결과만 표시해 검색 지표와 응답 판정을 혼동하지 않도록 합니다."""
    root = FOLDER.parents[2]
    files = [root / "data/zzong_santafe_lag/reports/m7_specific_terms_20261002_142212.json",
             root / "data/zzong_santafe_lag/openai_embeddings/comparison_summary.json"]
    st.subheader("기존 30문항 검색 비교")
    rows = []
    if files[0].exists():
        metrics = json.loads(files[0].read_text(encoding="utf-8"))["metrics"]
        for key, label in [("before", "구체 표현 보너스 전"), ("after", "구체 표현 보너스 후")]:
            rows.append({"비교": "구체 표현 실험", "조건": label, **metrics[key]})
    if files[1].exists():
        metrics = json.loads(files[1].read_text(encoding="utf-8"))["metrics"]
        for key, label in [("local", "로컬 임베딩"), ("openai", "OpenAI 임베딩")]:
            rows.append({"비교": "동일 청크 모델 비교", "조건": label,
                         "Hit@5": metrics[key]["Hit@5"], "MRR@5": metrics[key]["MRR@5"]})
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    else:
        st.info("로컬 비교 결과 파일이 없는 환경입니다. 작업 Document의 저장된 발표 기록을 참고하세요.")
    st.info("기존 개선에 재사용한 30문항의 기대 출처 검색 평가입니다. "
            "새 질문 정확도·생성 답변 정확도·전체 관련성 Precision을 뜻하지 않습니다.")
    st.write("Hit@5는 상위 5개 안에 기대 근거가 포함된 질문 비율입니다. "
             "MRR@5는 첫 기대 근거 순위의 역수 평균이며 상위 5개 밖은 0점입니다.")


def render_work_document():
    """수업 근거·모델 이유·슬라이드 대본·시연을 기존 대화 상태 변경 없이 표시합니다."""
    content = load_content()
    st.title("싼타페 작업 Document")
    st.write(content["thesis"])
    flow, lessons, models, story = st.tabs(["M0~M9", "수업 근거", "모델과 추가 설계", "발표와 시연"])
    with flow:
        render_milestones()
        render_saved_comparisons()
        for row in content["milestones"]:
            with st.expander(f"{row['stage']} {row['name']} 구현 파일"):
                st.write(row["lesson"])
                st.code(row["evidence"], language=None, wrap_lines=True)
    with lessons:
        st.write("수업 개념은 현재 컴퓨터에 있는 노트북의 실제 셀과 대조했습니다. "
                 "M0~M9는 기존 합의 프로젝트 순서이며 최신 Notion 수업 순서와의 대조 결과는 아닙니다.")
        path = PRESENTATION / "lesson_evidence.json"
        if path.exists():
            audit = json.loads(path.read_text(encoding="utf-8"))
            st.caption(f"확인일 {audit['checked_date']} · 셀 번호는 노트북 전체 셀 순서, 1부터 시작")
            for row in audit["lessons"]:
                with st.expander(row["concept"]):
                    st.code(row["path"], language=None, wrap_lines=True)
                    for hit in row["matches"][:8]:
                        st.caption(f"셀 {hit['cell']}")
                        st.code(hit["excerpt"], language="python", wrap_lines=True)
            st.caption(f"NLP·LLM·RAG·DB 수업 {audit['additional_model_scan']['notebook_count']}개에서 "
                       "jhgan/ko-sroberta-multitask-mrl과 gpt-6-luna 사용을 찾지 못했습니다. "
                       "수업 전체에 전혀 없다는 뜻으로 확대하지 않습니다.")
            st.download_button("수업 근거 JSON", path.read_bytes(), file_name=path.name,
                               mime="application/json", on_click="ignore")
        st.write("수업의 TF-IDF는 명사 토큰을 사용했습니다. 글자 n-gram과 결합 가중치는 프로젝트 설계입니다. "
                 "수업의 상관 개념을 적용했으며 현재 Spearman 선택은 프로젝트 구현입니다.")
    with models:
        for row in content["models"]:
            with st.expander(row["name"], expanded=True):
                st.caption(row["category"])
                st.write("역할: " + row["role"])
                st.write("선택 이유: " + row["why"])
                st.write("목적: " + row["purpose"])
                st.write("해석 범위: " + row["limit"])
                st.code(row["evidence"], language=None, wrap_lines=True)
        st.subheader("프로젝트에서 추가한 처리")
        for row in content["extensions"]:
            with st.expander(row["item"]):
                st.write("이유: " + row["why"])
                st.write("목적: " + row["purpose"])
                st.write(row["boundary"])
                st.code(row["code"], language=None, wrap_lines=True)
    with story:
        st.write("약 12~15분 발표용 16장 구성. 문제 정의부터 실제 구현, 비교 실험, 실패와 다음 검증으로 이어집니다.")
        for index, slide in enumerate(content["slides"], 1):
            with st.expander(f"{index:02d}. {slide['title'].replace(chr(10), ' ')}"):
                for line in slide["body"]:
                    st.write("- " + line)
                st.write(slide["notes"])
                st.caption("근거: " + ", ".join(slide["sources"]))
        st.subheader("시연 순서")
        for row in content["demo"]:
            st.markdown(f"**{row['step']}. {row['question']}**")
            st.write(row["show"] + " — " + row["message"])
        st.subheader("예상 질문")
        for row in content["qa"]:
            with st.expander(row["q"]):
                st.write(row["a"])
    for filename, label, mime in [
        ("output/santafe_presentation_final.pptx", "발표 PPT 다운로드", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        ("storyline.md", "발표 대본과 근거 다운로드", "text/markdown"),
    ]:
        path = PRESENTATION / filename
        if path.exists():
            st.download_button(label, path.read_bytes(), file_name=path.name, mime=mime, on_click="ignore")
