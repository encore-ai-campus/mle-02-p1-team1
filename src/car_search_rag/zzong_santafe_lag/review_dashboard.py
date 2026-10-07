"""저장된 2차 검토 결과를 보여줍니다. DB나 생성 모델을 호출하지 않습니다."""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

FOLDER = Path(__file__).resolve().parent / 'source_reviews/20261007_batch2'


def render_review_results():
    """8개 원문 보완과 동일 질문 재평가 결과·남은 문제를 표시합니다."""
    file = FOLDER / 'review_summary.json'
    st.subheader('원문 8개 보완 · 2026-10-07')
    if not file.exists():
        st.info('2차 검토 결과를 정리 중입니다.')
        return
    summary = json.loads(file.read_text(encoding='utf-8'))
    st.write(summary['description'])
    for label, value in summary['metrics'].items():
        st.write(f'{label}: {value}')
    st.dataframe(pd.DataFrame(summary['questions']), hide_index=True, use_container_width=True)
    for limitation in summary['limitations']:
        st.caption(limitation)
    report = FOLDER / 'report.md'
    if report.exists():
        with st.expander('검토 상세 보고서'):
            st.markdown(report.read_text(encoding='utf-8'))
        st.download_button('8개 검토 보고서 다운로드', report.read_bytes(),
                           file_name='santafe_review_batch2.md', mime='text/markdown', on_click='ignore')
