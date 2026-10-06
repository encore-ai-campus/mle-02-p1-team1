"""산출물 핵심 요약. 모든 자료는 앱과 함께 배포되는 파일에서 읽습니다."""
import csv
import json
from collections import Counter
from pathlib import Path

import streamlit as st

from portal_charts import COLORS, OUTCOMES, CATEGORIES, base_spec, category_spec, evaluation_groups, retrieval_groups, retrieval_spec
from portal_theme import hero, note, steps

ASSETS = Path(__file__).resolve().parent / "project_assets"
PAGES = ["프로젝트 한눈에", "매뉴얼 질문하기", "01 데이터·전처리", "02 데이터 분석", "03 검색·답변 구조", "04 검색 품질 평가"]


@st.cache_data(show_spinner=False)
def _json_file(name, modified):
    return json.loads((ASSETS / name).read_text(encoding="utf-8"))


def data(name):
    path = ASSETS / name
    return _json_file(name, path.stat().st_mtime_ns)


@st.cache_data(show_spinner=False)
def _csv_file(name, modified):
    with (ASSETS / name).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def table(name):
    path = ASSETS / name
    return _csv_file(name, path.stat().st_mtime_ns)


@st.cache_data(show_spinner=False)
def _bytes_file(name, modified):
    return (ASSETS / name).read_bytes()


def download(name, label, mime="application/zip", key=None):
    path = ASSETS / name
    st.download_button(label, _bytes_file(name, path.stat().st_mtime_ns), file_name=path.name,
                       mime=mime, key=key or "download_" + name, width="stretch")


def metrics(items):
    for column, (title, value, help_text) in zip(st.columns(len(items)), items):
        column.metric(title, value, help=help_text)


def chart(spec, key):
    st.vega_lite_chart(spec=spec, theme=None, width="stretch", key=key)


def render_overview():
    hero("PROJECT NOTEBOOK", "매뉴얼이 답변이 되기까지", "매뉴얼을 검색 가능한 데이터로 만들고, 실제 질문으로 답변 품질을 확인한 과정을 네 단계로 정리했습니다.")
    metrics([("매뉴얼 조각", "1,874개", "질문과 관련 있는 본문을 찾기 위해 나눈 단위입니다."),
             ("분석한 장", "11개", "원본 매뉴얼의 장 구성입니다."),
             ("실제 평가", "30개", "2026년 10월 2일에 완료한 초기 평가 기록입니다.")])
    st.subheader("처음 보신다면, 이 순서로 읽어보세요")
    steps([("01 · 데이터·전처리", "PDF에서 글과 목차를 읽고, 검색에 필요한 크기로 나누었습니다."),
           ("02 · 데이터 분석", "데이터의 길이·중복·특징 단어를 살펴보았습니다."),
           ("03 · 검색·답변 구조", "질문에 가까운 글을 팀 DB에서 찾고, 그 글을 근거로 답합니다."),
           ("04 · 검색 품질 평가", "30개 질문의 실제 답변을 기준과 비교해 개선할 지점을 찾았습니다.")])
    left, right = st.columns(2)
    with left, st.container(border=True):
        st.markdown("### 앱이 하는 일")
        st.write("질문과 관련 있는 매뉴얼 내용을 찾고, 출처 번호를 붙여 설명합니다. 답변의 번호를 검색 근거와 비교할 수 있습니다.")
    with right, st.container(border=True):
        st.markdown("### 자료를 읽는 방법")
        st.write("화면에는 핵심 결과를 먼저 보여줍니다. 세부 기준과 기록은 펼쳐 보고, 전체 제출 자료는 각 단계에서 내려받으세요.")
    note("이 프로젝트는 매뉴얼 텍스트를 검색합니다. 개별 차량의 실시간 진단이나 주변 충전소의 현재 빈자리를 확인하는 서비스는 아닙니다.")


def render_stage1():
    profile = data("dataset_profile.json")
    hero("01 / DATA & PREPROCESSING", "긴 매뉴얼을 작은 검색 단위로", "청크는 검색을 위해 나눈 글 조각입니다. 본문과 함께 제목·페이지 정보를 남겨, 답변의 출처를 찾을 수 있게 했습니다.")
    metrics([("전체 청크", f"{profile['rows']:,}개", "본문을 저장한 행 수입니다."),
             ("청크 길이 목표", "450토큰", "토큰은 모델이 글을 처리하는 작은 단위입니다. 단어 수와 같지는 않습니다."),
             ("이웃 청크의 겹침", "약 80토큰", "경계에서 내용이 끊기는 영향을 줄이기 위해 앞뒤 조각이 일부 내용을 공유합니다.")])
    st.subheader("어떻게 만들었나요?")
    steps([("PDF의 글과 목차를 읽습니다", "페이지의 텍스트와 장·절·소제목의 위치를 가져옵니다."),
           ("공백과 줄바꿈을 정리합니다", "과도한 공백과 빈 줄을 줄입니다. 원문을 새로 쓰거나 의미를 바꾸는 작업은 아닙니다."),
           ("목차 범위별로 글을 나눕니다", "장·절·하위 항목을 각각 처리하고, 긴 글은 길이 목표에 맞춰 분할합니다."),
           ("출처 정보를 붙입니다", "청크 ID, 제목, 목차, 페이지 범위를 함께 보관합니다."),
           ("검색용 입력을 준비합니다", "본문에 목차 정보를 더하고 passage:를 붙입니다. 최종 입력은 510토큰 기준으로 제한합니다.")])
    note("페이지 범위는 청크를 만든 목차 항목의 범위입니다. 청크 한 조각의 정확한 출처 페이지를 뜻하지는 않습니다.")
    with st.expander("데이터 한 행은 어떻게 생겼나요?"):
        sample = profile["samples"][0]
        st.caption(f"{sample['chunk_id']} · {sample['source_title']} · PDF {sample['page_start']}~{sample['page_end']}쪽")
        st.write(sample["chunk_text"])
        st.caption("예시 본문은 일부만 표시합니다. 전체 내용은 데이터셋 다운로드에 있습니다.")
    with st.expander("컬럼·자료형·빈칸을 확인하고 싶어요"):
        st.dataframe(profile["columns"], hide_index=True, width="stretch")
        st.write("절(section)과 하위 항목(subsection)의 빈칸에는 해당 목차가 없는 경우가 포함됩니다. 임의의 제목으로 채우지 않았습니다.")
        st.caption("분석 CSV는 14컬럼입니다. DB 본문 테이블은 검색 입력용 3컬럼을 제외한 11컬럼입니다.")
    with st.expander("청킹에서 알아둘 점"):
        st.write("상위 목차와 하위 목차의 원문 범위가 겹칠 수 있습니다. 일부 같은 본문이 다른 제목·출처 정보를 가진 청크로 만들어졌습니다.")
        st.write("450토큰은 목표값입니다. 실제 저장값은 최대 452토큰이며, 450을 넘는 행이 36개 있습니다. 이미지 추출·이미지 검색은 포함하지 않았습니다.")
    st.subheader("전체 자료")
    download("downloads/stage1_data_preprocessing.zip", "데이터셋·데이터 명세·전처리 설명 내려받기")


def render_stage2():
    profile = data("dataset_profile.json")
    hero("02 / DATA EXPLORATION", "무엇이 많이 들어 있고, 어디를 살펴봐야 할까요?", "EDA는 데이터를 먼저 살펴보는 작업입니다. 여기서는 장별 분량, 글의 길이, 반복된 본문과 특징 단어를 확인했습니다.")
    metrics([("서로 다른 본문", "1,542개", "완전히 같은 글은 한 번만 센 값입니다."),
             ("중복 추가 행", "332개", "1,874행 중 동일 본문이 추가로 등장한 행입니다. 중복 그룹에 속한 전체 행은 553개입니다."),
             ("본문 길이 중앙값", "444토큰", "길이를 순서대로 놓았을 때 가운데 값입니다.")])
    with st.container(border=True):
        st.subheader("어느 장에서 청크가 많이 만들어졌나요?")
        values = [{"장": r["chapter"], "청크 수": int(r["chunks"]), "목차 항목": int(r["source_units"])} for r in table("analysis/chapter_statistics.csv")]
        spec = base_spec(values, 350)
        spec.update(mark={"type": "bar", "color": "#168269", "cornerRadiusEnd": 3}, encoding={
            "y": {"field": "장", "type": "nominal", "sort": "-x", "title": None, "axis": {"labelLimit": 180}},
            "x": {"field": "청크 수", "type": "quantitative", "title": "청크 수 (개)"},
            "tooltip": [{"field": "장"}, {"field": "청크 수"}, {"field": "목차 항목"}]})
        chart(spec, "chapter_chart")
        st.caption("편의 장치 411개, 운전자 보조 394개가 많습니다. 청크 수가 많다는 것이 사용자 질문이나 중요도가 더 높다는 뜻은 아닙니다.")
    with st.container(border=True):
        st.subheader("청크 길이는 어느 정도인가요?")
        spec = base_spec(profile["length_histogram"], 200)
        spec.update(mark={"type": "bar", "color": "#71a99a", "cornerRadiusTopLeft": 2, "cornerRadiusTopRight": 2},
                    encoding={"x": {"field": "start", "type": "quantitative", "title": "본문 길이 (토큰)", "bin": "binned"},
                              "x2": {"field": "end"}, "y": {"field": "count", "type": "quantitative", "title": "청크 수 (개)"},
                              "tooltip": [{"field": "start", "title": "구간 시작"}, {"field": "end", "title": "구간 끝 (미만)"}, {"field": "count", "title": "청크 수"}]})
        chart(spec, "length_chart")
        st.caption("많은 청크가 길이 목표에 가깝습니다. 저장된 토큰 수를 사용한 분석이며 모델을 다시 실행한 결과는 아닙니다.")
    with st.container(border=True):
        st.subheader("반복된 글은 바로 삭제하면 될까요?")
        st.write("같은 글에도 목차 정보가 다르게 붙을 수 있습니다. 본문이 같다는 이유만으로 삭제하기 전에, 실제 검색에서 같은 내용이 반복해서 나오는지 확인해야 합니다.")
        note("중복을 줄이면 검색이 반드시 좋아진다는 결론은 아직 없습니다. EDA의 관찰은 다음 검색 실험의 출발점입니다.")
    with st.expander("통계 검정 결과를 쉽게 읽어보기"):
        st.markdown("**장별 길이 차이**: 장에 따라 길이 분포가 다른 신호가 있지만 효과크기는 0.0348로 작습니다. 어느 두 장이 다른지는 이 검정만으로 정하지 않았습니다.")
        st.markdown("**페이지 범위와 청크 수**: 넓은 목차 범위에서 청크가 많이 만들어지는 경향이 있었습니다. 순위상관은 0.7496입니다. 검색이 더 정확하다는 뜻은 아닙니다.")
        st.caption("506개 목차 항목을 분석했습니다. 원문 범위가 겹칠 수 있어 확정적 결론보다 탐색적 진단으로 읽어야 합니다.")
        st.dataframe(table("analysis/statistical_tests.csv"), hide_index=True, width="stretch")
    with st.expander("TF-IDF: 각 장을 특징짓는 단어"):
        keywords = table("analysis/tfidf_chapter_keywords.csv")
        chapter = st.selectbox("살펴볼 장", list(dict.fromkeys(r["chapter"] for r in keywords)), key="tfidf_chapter")
        selected = [{"단어": r["term"], "평균 TF-IDF": round(float(r["mean_tfidf"]), 4)} for r in keywords if r["chapter"] == chapter][:10]
        st.write("자주 등장하면서 다른 글과 구별되는 단어를 찾아보는 방법입니다. 단어 점수는 정답률이 아닙니다.")
        st.dataframe(selected, hide_index=True, width="stretch")
    st.subheader("전체 자료")
    download("downloads/stage2_analysis.zip", "실행된 노트북·분석 보고서·상세 표 내려받기")


def render_stage3():
    audit = data("logs/dump_audit.json")
    hero("03 / RETRIEVAL & ANSWERING", "질문에 가까운 글을 찾아, 근거로 답합니다", "검색은 필요한 글을 고르는 일이고, 답변 생성은 그 글을 읽고 설명하는 일입니다. 두 역할을 연결한 것이 이 앱의 RAG 파이프라인입니다.")
    metrics([("저장된 본문", f"{audit['chunk_rows']:,}개", "제공된 덤프 파일을 확인한 값입니다."),
             ("저장된 임베딩", f"{audit['embedding_rows']:,}개", "본문과 같은 ID로 연결되는 숫자 벡터입니다."),
             ("벡터 길이", "768개 숫자", "문서와 질문을 같은 모델로 바꿔 의미를 비교합니다.")])
    store, ask = st.tabs(["먼저 데이터를 저장합니다", "사용자가 질문하면"])
    with store:
        steps([("청크에 검색용 목차 정보를 더합니다", "제목과 본문을 묶어 passage:로 시작하는 입력을 만듭니다."),
               ("E5 모델로 숫자 벡터를 만듭니다", "문서의 의미를 비교할 수 있도록 768개의 숫자로 바꿉니다."),
               ("본문과 벡터를 따로 저장합니다", "casper_manual_chunks와 casper_manual_embeddings를 같은 chunk_id로 연결합니다."),
               ("개인 DB에서 팀 DB로 옮겼습니다", "기존 본문과 이미 만든 벡터를 함께 이관했습니다. 이관을 위해 임베딩을 다시 만들지는 않았습니다.")])
    with ask:
        steps([("질문을 같은 모델로 바꿉니다", "query:를 붙인 질문도 768개의 숫자로 표현합니다."),
               ("팀 DB에서 가까운 벡터를 찾습니다", "검색 함수 match_manual_chunks가 같은 모델·버전의 벡터를 비교합니다."),
               ("관련 본문과 출처를 가져옵니다", "기본 설정은 상위 5개입니다. 유사도는 정답 확률이 아닙니다."),
               ("LLM이 근거를 읽고 설명합니다", "근거 번호를 표시하고, 근거가 부족하면 확인할 수 없다고 답하도록 안내합니다.")])
    with st.expander("적재와 이관 기록은 어디까지 확인했나요?"):
        st.write("이전 노트북에는 개인 DB의 본문·임베딩 적재가 각각 1,874/1,874까지 진행된 출력이 남아 있습니다.")
        st.write("제공된 개인·팀 덤프 파일의 본문과 벡터 내용은 서로 일치했습니다. 본문과 벡터 사이에 연결되지 않은 행은 0개였습니다.")
        st.write("팀 DB 복원 완료와 연결 변경은 사용자가 확인한 기록입니다. 덤프 검사는 로컬 파일 검사이며 현재 DB 상태를 실시간으로 조회한 값은 아닙니다.")
        st.dataframe([{"확인 항목": "본문 행 수", "결과": str(audit['chunk_rows'])},
                      {"확인 항목": "임베딩 행 수", "결과": str(audit['embedding_rows'])},
                      {"확인 항목": "연결되지 않은 행", "결과": "0"},
                      {"확인 항목": "개인·팀 데이터 내용 일치", "결과": "일치"}], hide_index=True, width="stretch")
    with st.expander("검색 함수와 코드가 궁금해요"):
        st.write("코사인 거리로 가까운 순서대로 청크를 찾습니다. 현재 흐름은 검색 한 번과 답변 생성 한 번이며, ReAct나 질문 분해를 적용한 구조는 아닙니다.")
        sql_path = ASSETS / "code/match_manual_chunks.sql"
        st.code(sql_path.read_text(encoding="utf-8"), language="sql")
    st.subheader("전체 자료")
    download("downloads/stage3_code_logs.zip", "인덱싱·RAG 코드·SQL·적재 기록 내려받기")


def render_stage4():
    dataset, results = data("evaluation_dataset.json"), data("evaluation_results.json")
    rows = results["results"]
    counts = Counter(r["review"]["overall_result"] for r in rows)
    scored = [r for r in rows if r["review"]["retrieval_hit_at_5"] is not None]
    hits = sum(r["review"]["retrieval_hit_at_5"] for r in scored)
    hero("04 / QUALITY REVIEW · 2026.10.02", "잘 답한 질문과, 더 살펴볼 질문", "앱에 30개 질문을 실제로 입력했습니다. 필요한 근거를 찾았는지와, 답변이 기준을 충족했는지를 나누어 확인했습니다.")
    metrics([("실제 실행", f"{len(rows)}개", "각 질문을 한 번씩 실행한 초기 평가입니다."),
             ("답변 기준 충족", f"{counts['pass']} / {len(rows)}", "부분 충족 5개와 미충족 1개는 포함하지 않습니다."),
             ("정답 근거 확보", f"{hits} / {len(scored)}", "답할 수 있는 질문 23개 중, 정답 근거를 하나 이상 찾은 질문입니다.")])
    with st.container(border=True):
        st.subheader("질문 유형에 따라 답변 결과가 달랐나요?")
        st.write("정상 질문은 매뉴얼에 답이 있는 질문, 답할 수 없는 질문은 실시간·개인 정보 등을 요구한 질문입니다. 경계 사례는 오타·모호함·비슷한 기능처럼 헷갈리기 쉬운 질문입니다.")
        mode = st.radio("그래프 표시", ["질문 수", "유형 안의 비율"], horizontal=True, key="evaluation_chart_mode")
        chart(category_spec(evaluation_groups(dataset, results), mode != "질문 수"), "evaluation_by_category")
        st.caption("정상 질문 18개 · 답할 수 없는 질문 6개 · 경계 사례 6개. 서로 다른 개수의 그룹을 비교할 때는 비율도 함께 보세요.")
        note("답할 수 없는 질문 6개는 모두 정보를 지어내지 않았습니다. 여기서의 ‘충족’은 답변 거절 또는 확인 불가 안내가 적절했다는 뜻입니다.")
    with st.container(border=True):
        st.subheader("검색을 못 했나요, 답변에서 빠뜨렸나요?")
        values, excluded = retrieval_groups(results)
        chart(retrieval_spec(values), "retrieval_vs_answer")
        st.caption("매뉴얼 근거가 있는 23개만 비교합니다. 답할 수 없는 질문 6개와 모호한 Q028은 이 그래프에서 제외했습니다.")
        st.write("필수 근거가 없었던 Q005·Q018·Q027은 검색 개선이 필요합니다. 근거가 있었던 Q003·Q012는 답변의 조건과 누락을 먼저 살펴볼 사례입니다.")
        st.caption("근거 확보는 필수 내용의 근거를 하나 이상 찾았다는 뜻입니다. 모든 근거의 완전성을 뜻하지는 않습니다. 이번 20개는 필수 내용도 모두 확보했습니다.")
    st.subheader("확인된 결과에서 무엇을 배웠나요?")
    steps([("질문 표현이 검색 결과에 영향을 줍니다", "Q007은 CR2032를 답했지만, 오타·구어체의 Q027은 규격을 찾지 못했습니다."),
           ("여러 질문이라고 반드시 실패하지는 않습니다", "Q013·Q025·Q030은 여러 항목을 함께 물어도 답했습니다. Q005 실패의 원인을 질문 개수 하나로 단정할 수 없습니다."),
           ("근거가 있어도 조건이 바뀌거나 설명이 빠질 수 있습니다", "Q003의 점검 조건 표현이 달라졌습니다. Q012는 고정 정답 기준의 D 기어 조건이 빠졌습니다."),
           ("모호한 상황은 먼저 확인해야 합니다", "Q028은 일반 확인 방법을 안내했지만 사용자에게 상황을 추가로 묻지 않았습니다.")])
    st.caption("Q012의 속도 범위 답변은 정확했습니다. 부분 충족은 질문보다 넓게 설정된 정답 기준에 D 조건이 포함된 데 따른 판정입니다.")
    st.subheader("실제 답변을 직접 확인해 보세요")
    a, b = st.columns(2)
    with a:
        category = st.selectbox("질문 유형", ["전체"] + list(CATEGORIES.values()), key="case_category")
    with b:
        outcome = st.selectbox("답변 판정", ["전체"] + list(OUTCOMES.values()), key="case_outcome")
    cases = {c["test_id"]: c for c in dataset["cases"]}
    filtered = [r for r in rows if (category == "전체" or CATEGORIES[cases[r['test_id']]['category']] == category)
                and (outcome == "전체" or OUTCOMES[r['review']['overall_result']] == outcome)]
    if not filtered:
        st.info("이 조건에 해당하는 질문이 없습니다.")
    else:
        ids = [r["test_id"] for r in filtered]
        index = ids.index("Q005") if "Q005" in ids else 0
        selected = st.selectbox("살펴볼 질문", ids, index=index,
                                format_func=lambda id: f"{id} · {cases[id]['question']}", key="selected_evaluation_case")
        r = next(r for r in filtered if r["test_id"] == selected)
        with st.container(border=True):
            st.caption(f"{selected} · {OUTCOMES[r['review']['overall_result']]} · 앱 표시 처리 시간 {r['elapsed_seconds']:.1f}초")
            st.markdown(f"**{r['question']}**")
            st.markdown(r["answer"])
            st.info(r["review"]["notes"])
        with st.expander("사전에 정한 답변 기준"):
            c = cases[selected]
            for f in c["required_facts"]:
                st.markdown(f"- {f['criterion']}")
            if not c["required_facts"]:
                st.write(c["expected_behavior"])
        with st.expander("실제로 검색된 근거 5개"):
            for source in r["retrieved_sources"]:
                st.markdown(f"**[{source['rank']}] {source['source_title']}**")
                st.caption(f"PDF {source['page_start']}~{source['page_end']}쪽 · 유사도 {source['similarity']:.4f}")
                st.write(source["chunk_text"])
                st.divider()
        with st.expander("전체 질문과 판정을 표로 보기"):
            st.dataframe([{"번호": x["test_id"], "질문": x["question"], "판정": OUTCOMES[x["review"]["overall_result"]]} for x in filtered],
                         hide_index=True, width="stretch")
    with st.expander("이 평가의 범위와 주의점"):
        st.write("30개는 선정한 초기 테스트 사례입니다. 전체 사용자 질문에 대한 성공률이나 대규모 검증 결과로 일반화하지 않습니다.")
        st.write("팀 DB와 gpt-6-luna 사용은 사용자 확인 정보입니다. 배포 서버의 실제 설정과 코드 커밋을 별도로 조회하지 않았습니다.")
        st.write("판정은 작성자의 초기 검토입니다. 독립 전문가 채점, 같은 질문의 반복 실행, 동시 사용자 부하 검증은 수행하지 않았습니다.")
        st.write("Q005를 짧게 바꿨을 때 성공한 사용자 추가 확인은 별도 기록으로 남겼습니다. 원래 Q005와 전체 통계는 바꾸지 않았습니다.")
        st.caption("그래프는 현재 앱에 다시 질문한 결과가 아닌, 2026.10.02에 수집한 고정 평가 기록입니다.")
    st.subheader("전체 자료와 그래프")
    a, b = st.columns(2)
    with a:
        download("downloads/stage4_evaluation.zip", "평가 질문·실행 결과·리포트 내려받기")
    with b:
        download("charts/evaluation_charts.html", "그래프 2개를 HTML로 내려받기", "text/html")


def render_project_page(page):
    {"프로젝트 한눈에": render_overview, "01 데이터·전처리": render_stage1,
     "02 데이터 분석": render_stage2, "03 검색·답변 구조": render_stage3,
     "04 검색 품질 평가": render_stage4}[page]()
