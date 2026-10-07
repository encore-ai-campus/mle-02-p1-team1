"""IONIQ 5 검색 품질을 사람이 검수한 질문으로 즉시 확인합니다."""
import json
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st


HERE = Path(__file__).resolve().parents[1]
DATASET = HERE / 'evaluation' / 'm6_baseline_v1' / 'dataset_snapshot.json'
METHODS = ('키워드 + LLM 재정렬 (운영)', '벡터 검색', '벡터 검색 + MMR')
K = 5
FETCH_K = 50
MMR_LAMBDA = 0.25


@st.cache_data(show_spinner=False)
def _load_questions():
    data = json.loads(DATASET.read_text(encoding='utf-8'))
    return [q for q in data['questions']
            if q.get('retrieval_eligible') and q.get('relevant_chunk_ids')]


def _ranked_hits(backend, question):
    vector = backend.embeddings.embed_query(question)
    scope = {'document_id': backend.document_id,
             'embedding_model': backend.embedding_model,
             'embedding_dimension': backend.embedding_dimension}

    hybrid = backend.manual_search.search(question, vector=vector).hits
    dense = backend.store.similarity_search_with_score_by_vector(
        vector, k=K, filter=scope)
    mmr = backend.store.max_marginal_relevance_search_with_score_by_vector(
        vector, k=K, fetch_k=FETCH_K, lambda_mult=MMR_LAMBDA, filter=scope)

    def serialize(items, score_name):
        rows = []
        for rank, item in enumerate(items, 1):
            if score_name == 'hybrid':
                doc = item.document
                rows.append({
                    '순위': rank, '청크 ID': doc.id,
                    '목차': ' › '.join(doc.metadata.get('section_path', [])) or doc.metadata.get('section_id', ''),
                    '유형': doc.metadata.get('chunk_type', ''),
                    'PDF 페이지': ', '.join(map(str, doc.metadata.get('pdf_pages', []))),
                    '코사인 유사도': (1 - item.cosine_distance) if item.cosine_distance is not None else None,
                    '키워드 검색 점수': item.keyword_score,
                    '벡터 후보 순위': item.cosine_rank,
                    '키워드 후보 순위': item.keyword_rank,
                    '본문': doc.page_content,
                })
            else:
                doc, distance = item
                rows.append({
                    '순위': rank, '청크 ID': doc.id,
                    '목차': ' › '.join(doc.metadata.get('section_path', [])) or doc.metadata.get('section_id', ''),
                    '유형': doc.metadata.get('chunk_type', ''),
                    'PDF 페이지': ', '.join(map(str, doc.metadata.get('pdf_pages', []))),
                    '코사인 유사도': 1 - float(distance),
                    '본문': doc.page_content,
                })
        return rows

    return {
        METHODS[0]: serialize(hybrid, 'hybrid'),
        METHODS[1]: serialize(dense, 'dense'),
        METHODS[2]: serialize(mmr, 'mmr'),
    }


def _metric(rows, relevant_ids):
    gold = set(relevant_ids)
    rank = next((row['순위'] for row in rows if row['청크 ID'] in gold), None)
    return {'Hit@5': int(rank is not None), 'MRR@5': 1 / rank if rank else 0.0,
            '첫 정답 순위': f'{rank}위' if rank else '상위 5개 밖'}


def render_quality_dashboard(backend):
    st.title('IONIQ 5 검색 품질 대시보드')
    st.caption('검수된 질문은 Hit@5·MRR@5를 계산하고, 새 질문은 검색 결과를 살펴봅니다. 답변 생성은 실행하지 않습니다.')
    st.caption('비교: 운영 키워드+LLM 재정렬(각 10개 → 최종 5개) · 벡터 검색 · 벡터 후보 50개에서 MMR 재정렬(λ=0.25, 최종 5개).')

    questions = _load_questions()
    with st.expander('전체 기준 질문의 종합 점수', expanded=False):
        st.caption('G01–G24를 현재 검색기에 다시 실행해 방식별 평균을 계산합니다. 문항마다 질문 임베딩·키워드 추출·리랭크 API와 읽기 전용 검색을 사용하며, 결과는 이 화면에만 표시됩니다.')
        if st.button('G01–G24 전체 평가', key='ioniq_quality_run_all'):
            progress = st.progress(0, text='평가 준비 중…')
            aggregate = []
            try:
                for index, item in enumerate(questions, 1):
                    ranked = _ranked_hits(backend, item['question'])
                    aggregate.append({
                        'ID': item['id'], '질문': item['question'],
                        **{f'{method} Hit@5': _metric(ranked[method], item['relevant_chunk_ids'])['Hit@5']
                           for method in METHODS},
                        **{f'{method} MRR@5': _metric(ranked[method], item['relevant_chunk_ids'])['MRR@5']
                           for method in METHODS},
                    })
                    st.session_state.ioniq_quality_batch_result = aggregate
                    progress.progress(index / len(questions), text=f'{index}/{len(questions)}문항 평가 중')
                progress.empty()
            except Exception as error:
                progress.empty()
                st.error('전체 평가가 중단됐어요. 완료된 문항 결과는 아래에 남아 있습니다.')
                st.caption(f'오류 유형: {type(error).__name__}')
        aggregate = st.session_state.get('ioniq_quality_batch_result', [])
        if aggregate:
            frame = pd.DataFrame(aggregate)
            metric_cols = st.columns(len(METHODS))
            for col, method in zip(metric_cols, METHODS):
                hit = frame[f'{method} Hit@5'].mean()
                mrr = frame[f'{method} MRR@5'].mean()
                col.metric(f'{method} · Hit@5', f'{hit:.3f}',
                           delta='목표 달성' if hit >= 0.7 else '목표 미달')
                col.metric('MRR@5', f'{mrr:.3f}',
                           delta='목표 달성' if mrr >= 0.5 else '목표 미달')
                col.caption(f"{len(frame)}/{len(questions)}문항 완료")
            detail_cols = ['ID', '질문'] + [f'{m} Hit@5' for m in METHODS] + [f'{m} MRR@5' for m in METHODS]
            st.dataframe(frame[detail_cols], hide_index=True, use_container_width=True)

    mode = st.radio('평가 방식', ['검수 질문 평가', '새 질문 탐색'], horizontal=True,
                    key='ioniq_quality_mode')
    question = ''
    selected = None
    if mode == '검수 질문 평가':
        by_id = {q['id']: q for q in questions}
        question_id = st.selectbox(
            '정답 근거가 검수된 질문', list(by_id),
            format_func=lambda qid: f"{qid} · {by_id[qid].get('category', '')} · {by_id[qid]['question']}",
            key='ioniq_quality_question_id')
        selected = by_id[question_id]
        question = selected['question']
        pages = ', '.join(map(str, selected.get('evidence_pdf_pages', [])))
        st.markdown(
            '<div class="quality-question">'
            '<div class="quality-question-label">선택한 평가 질문</div>'
            f'<div class="quality-question-text">{escape(question)}</div>'
            f'<div class="quality-question-meta">정답 근거 {len(selected["relevant_chunk_ids"])}개 · PDF {escape(pages)}쪽</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        question = st.text_input('새 질문', max_chars=1000, key='ioniq_quality_custom_question')
        st.caption('새 질문에는 검수된 정답 라벨이 없어 점수를 계산하지 않습니다. 검색 순위와 근거를 확인할 수 있어요.')

    if st.button('검색하고 품질 확인', type='primary', disabled=not question.strip(),
                 key='ioniq_quality_run'):
        try:
            with st.spinner('설명서 검색 중…'):
                result = _ranked_hits(backend, question.strip())
            st.session_state.ioniq_quality_result = {
                'question': question.strip(), 'question_id': selected['id'] if selected else None,
                'gold_ids': selected['relevant_chunk_ids'] if selected else [],
                'methods': result,
            }
        except Exception as error:
            st.session_state.pop('ioniq_quality_result', None)
            st.error('검색을 완료하지 못했어요. 잠시 후 다시 시도해 주세요.')
            st.caption(f'오류 유형: {type(error).__name__}')

    result = st.session_state.get('ioniq_quality_result')
    if result and any(method not in result.get('methods', {}) for method in METHODS):
        # 검색 방식이 바뀌기 전 화면 결과를 현재 방식의 점수로 잘못 표시하지 않습니다.
        st.session_state.pop('ioniq_quality_result', None)
        result = None
    if not result:
        st.markdown('질문을 선택하거나 입력한 뒤 **검색하고 품질 확인**을 눌러주세요.')
        return
    if result.get('question') != question.strip():
        return
    if selected and result.get('question_id') != selected['id']:
        return
    if mode == '새 질문 탐색' and result.get('question_id') is not None:
        return

    st.subheader('검색 방식별 결과')
    if result['gold_ids']:
        metric_cols = st.columns(len(METHODS))
        for col, method in zip(metric_cols, METHODS):
            score = _metric(result['methods'][method], result['gold_ids'])
            col.metric(f'{method} · Hit@5', score['Hit@5'])
            col.metric('MRR@5', f"{score['MRR@5']:.3f}")
            col.caption(f"첫 정답 {score['첫 정답 순위']}")
        st.caption('정답 청크가 상위 5개에 하나라도 있으면 Hit@5=1입니다. MRR@5는 첫 정답 순위의 역수입니다. MMR은 재정렬 방법이며, MMR 자체의 점수를 정답률로 해석하지 않습니다.')
    else:
        st.warning('정답 근거가 지정되지 않아 Hit@5와 MRR@5는 표시하지 않습니다.')

    tabs = st.tabs(list(METHODS))
    for tab, method in zip(tabs, METHODS):
        rows = result['methods'][method]
        with tab:
            if result['gold_ids']:
                score = _metric(rows, result['gold_ids'])
                st.caption(f"{score['첫 정답 순위']} · 정답 청크는 ✅로 표시")
            if rows:
                frame = pd.DataFrame(rows)
                if result['gold_ids']:
                    frame.insert(1, '정답', frame['청크 ID'].isin(result['gold_ids']).map({True: '✅', False: ''}))
                st.dataframe(frame.drop(columns=['본문']), hide_index=True, use_container_width=True)
                for row in rows:
                    gold = row['청크 ID'] in result['gold_ids'] if result['gold_ids'] else False
                    title = f"{'✅ 정답 · ' if gold else ''}{row['순위']}위 · {row['목차']} · PDF {row['PDF 페이지']}쪽"
                    with st.expander(title):
                        st.code(row['청크 ID'], language=None)
                        st.write(row['본문'])
            else:
                st.info('검색 결과가 없습니다.')
