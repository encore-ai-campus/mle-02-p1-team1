"""추가 30문항의 저장 결과만 읽어 주제별 검색과 응답 판정을 표시합니다."""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

OUTPUT=Path(__file__).resolve().parent/'evaluation_30_results'
LABELS={'A':'상위 주제 키워드','B':'같은 기능의 구체 질문','C':'여러 의미 맥락 결합'}


def render_additional_evaluation():
    """평가를 다시 실행하지 않고 현재 저장된 별도 30문항 결과를 읽습니다."""
    st.subheader('추가 30문항 평가')
    files=[OUTPUT/'summary.json',OUTPUT/'graded_results.json']
    if not all(path.exists() for path in files):
        st.info('추가 평가 결과 정리가 아직 완료되지 않았습니다.')
        return
    summary,rows=[json.loads(path.read_text(encoding='utf-8')) for path in files]
    st.info('현재 버전의 자동 실행 결과를 Codex가 원본과 대조한 잠정 판정입니다. 사용자 직접 실행 50문항 및 확정 골든셋 점수와 구분합니다.')
    cols=st.columns(4)
    for col,label,value in zip(cols,['실행 완료','최종 응답 통과','부분 충족','최종 응답 실패'],
                               [summary['completed'],*[summary['counts'].get(k,0) for k in ['통과','부분','실패']]]):
        col.metric(label,f'{value}문항')
    st.caption(f"검색 {summary['search_calls']}회 · 생성 동작 요청 {summary['generation_attempts']}회 · 생성 답변 {summary['generated_answers']}개 · 원문 복귀 {summary['generation_fallbacks']}개 · 실행 예외 {summary['failure_count']}건")
    st.write(summary['rubric_note'])
    comparison=[]
    for g in 'ABC':
        c=summary['groups'][g];m=summary['provisional_search_metrics'][g]
        comparison.append({'유형':LABELS[g],'통과':c.get('통과',0),'부분':c.get('부분',0),'실패':c.get('실패',0),
                           '잠정 Hit@5':m['hit5'],'잠정 MRR@5':m['mrr5']})
    st.dataframe(pd.DataFrame(comparison),hide_index=True,use_container_width=True)
    st.caption(summary['metrics_note'])
    st.warning('검색 후보에 정답 근거가 있어도 화면에서 무관한 검토 자료를 선택하거나, 미검토 상태로 답변을 보류하는 사례가 있습니다. 검색 후보와 최종 응답을 별도로 확인하세요.')
    group=st.selectbox('추가 평가 유형',['전체','A','B','C'],format_func=lambda g:LABELS.get(g,g),key='extra30_group')
    frame=pd.DataFrame(rows)
    selected=frame if group=='전체' else frame[frame['group']==group]
    display=selected.copy()
    display['semantic_contexts']=display['semantic_contexts'].map(lambda values:' + '.join(values))
    mapping={'case_id':'번호','question':'질문','semantic_contexts':'의미 맥락','first_relevant_rank':'첫 관련 후보 순위',
             'displayed_source_grade':'표시 근거','overall':'최종 응답','note':'판정·보완'}
    st.dataframe(display[list(mapping)].rename(columns=mapping),hide_index=True,use_container_width=True)
    cid=st.selectbox('추가 평가 상세 문항',selected['case_id'].tolist(),key='extra30_case')
    row=next(r for r in rows if r['case_id']==cid)
    st.markdown('**'+row['question']+'**')
    st.write('결합한 의미 맥락: '+' + '.join(row['semantic_contexts']))
    st.write('기대 근거: '+row['expected'])
    st.write('판정·보완: '+row['note'])
    with st.expander('검색 상위 5개 후보'):
        st.dataframe(pd.DataFrame(row['top5']),hide_index=True)
    with st.expander('실제 초기 응답'):
        st.markdown(row['initial_text'])
    with st.expander('실제 최종 응답',expanded=True):
        st.markdown(row['final_text'])
        st.caption(f"최종 상태: {row['final_status']} · 생성 검증: {row.get('generation_diagnostic') or '별도 실패 표시 없음'}")
    for filename,label,mime in [('evaluation_30.csv','추가 30문항 결과 CSV','text/csv'),('report.md','추가 평가 보고서','text/markdown')]:
        path=OUTPUT/filename
        if path.exists():
            st.download_button(label,path.read_bytes(),file_name=filename,mime=mime,on_click='ignore')
