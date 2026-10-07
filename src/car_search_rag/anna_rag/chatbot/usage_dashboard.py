"""IONIQ 5 챗봇의 실제 요청 로그를 읽기 전용으로 요약합니다."""
from datetime import datetime, timedelta, time
from pathlib import Path
from zoneinfo import ZoneInfo
import logging

import pandas as pd
import streamlit as st
import altair as alt
from dotenv import load_dotenv
from car_search_rag.common.database_manager import DatabaseManager

KST = ZoneInfo('Asia/Seoul')
ERRORS = {'error', 'agent_error', 'intent_error', 'invalid_citations', 'missing_tool', 'tool_limit'}
TYPE_ORDER = ['설명서에서 답변', '질문을 되물음', '범위 재확인 안내', '설명서 밖 질문 안내',
              '근거를 찾지 못함', '인사', '처리 중 오류', '처리 중', '기타']
TYPE_HELP = {
    '설명서에서 답변': '설명서에서 관련 내용을 찾아 답했습니다.',
    '질문을 되물음': '질문이 모호해 필요한 정보를 다시 물었습니다.',
    '범위 재확인 안내': '질문 범위를 좁히기 어려워 구체적으로 다시 질문해 달라고 안내했습니다.',
    '설명서 밖 질문 안내': '차량 설명서에서 다루지 않는 질문이라고 안내했습니다.',
    '근거를 찾지 못함': '설명서에서 답변 근거를 찾지 못했다고 안내했습니다.',
    '인사': '인사말로 응답했습니다.',
    '처리 중 오류': '요청을 처리하는 중 오류가 발생했습니다.',
    '처리 중': '아직 답변이 완료되지 않았습니다.',
    '기타': '위 유형으로 분류되지 않은 응답입니다.',
}
STATUS_TYPE = {
    'answered':'설명서에서 답변', 'needs_clarification':'질문을 되물음',
    'needs_scope_review':'범위 재확인 안내', 'out_of_scope':'설명서 밖 질문 안내',
    'insufficient_evidence':'근거를 찾지 못함', 'greeting':'인사',
    **{status:'처리 중 오류' for status in ERRORS}, 'running':'처리 중',
}


def read_rows(sql, params=()):
    load_dotenv(Path(__file__).resolve().parents[4] / '.env', override=False)
    with DatabaseManager().connect(camel_case_keys=False) as conn:
        conn.execute('SET TRANSACTION READ ONLY')
        return conn.execute(sql, params).fetchall()


def _seconds(value):
    values = pd.to_numeric(value, errors='coerce').dropna() / 1000
    return values


def _render_type_chart(type_table):
    bars = alt.Chart(type_table).mark_bar(color='#5b43e8', cornerRadiusEnd=4).encode(
        x=alt.X('건수:Q', title='질문 수', scale=alt.Scale(domainMin=0), axis=alt.Axis(tickMinStep=1)),
        y=alt.Y('응답 유형:N', title=None, sort=TYPE_ORDER, axis=alt.Axis(labelLimit=220)),
        tooltip=[alt.Tooltip('응답 유형:N'), alt.Tooltip('건수:Q', format=',d')],
    )
    labels = alt.Chart(type_table).mark_text(align='left', dx=6, color='#34313d').encode(
        x='건수:Q', y=alt.Y('응답 유형:N', sort=TYPE_ORDER), text=alt.Text('건수:Q', format='d')
    )
    st.altair_chart((bars + labels).properties(height=300), use_container_width=True)


def _render_response_time_chart(done, overall_mean):
    timed = done.copy()
    timed['응답 유형'] = timed.status.fillna('running').map(lambda value: STATUS_TYPE.get(value, '기타'))
    timed['답변 시간(초)'] = pd.to_numeric(timed.duration_ms, errors='coerce') / 1000
    timed = timed[timed['답변 시간(초)'].notna() & (timed['답변 시간(초)'] >= 0)]
    by_type = timed.groupby('응답 유형', observed=False)['답변 시간(초)'].agg(
        질문수='count', 평균='mean', 중앙값='median'
    ).reindex(TYPE_ORDER)
    by_type_table = by_type.rename_axis('응답 유형').reset_index()
    by_type_table['질문 수'] = by_type_table['질문수'].fillna(0).astype(int)
    by_type_table['평균 답변 시간(초)'] = by_type_table['평균'].round(1)
    by_type_table['중앙값(초)'] = by_type_table['중앙값'].round(1)

    st.subheader('응답 시간')
    st.caption(f'전체 평균 **{overall_mean:.1f}초** · 유형별 평균을 비교합니다. 점선은 전체 평균입니다.')
    plot_data = by_type_table[by_type_table['평균 답변 시간(초)'].notna()]
    if plot_data.empty:
        st.info('응답 시간 기록이 없습니다.')
    else:
        bars = alt.Chart(plot_data).mark_bar(color='#5b43e8', cornerRadiusEnd=4).encode(
            x=alt.X('평균 답변 시간(초):Q', title='평균 답변 시간 (초)', scale=alt.Scale(domainMin=0)),
            y=alt.Y('응답 유형:N', title=None, sort=TYPE_ORDER, axis=alt.Axis(labelLimit=220)),
            tooltip=[alt.Tooltip('응답 유형:N'), alt.Tooltip('평균 답변 시간(초):Q', format='.1f'),
                     alt.Tooltip('중앙값(초):Q', format='.1f'), alt.Tooltip('질문 수:Q', format=',d')],
        )
        labels = alt.Chart(plot_data).mark_text(align='left', dx=6, color='#34313d').encode(
            x='평균 답변 시간(초):Q', y=alt.Y('응답 유형:N', sort=TYPE_ORDER),
            text=alt.Text('평균 답변 시간(초):Q', format='.1f'),
        )
        mean_rule = alt.Chart(pd.DataFrame({'전체 평균':[overall_mean]})).mark_rule(
            color='#dd6b20', strokeDash=[5, 4], strokeWidth=2
        ).encode(x='전체 평균:Q', tooltip=alt.Tooltip('전체 평균:Q', format='.1f'))
        st.altair_chart((bars + labels + mean_rule).properties(height=300), use_container_width=True)
    st.dataframe(by_type_table[['응답 유형','질문 수','평균 답변 시간(초)','중앙값(초)']],
                 hide_index=True, use_container_width=True)


def render_usage_dashboard():
    today = datetime.now(KST).date()
    title_col, date_col = st.columns([3, 1], vertical_alignment='center')
    with title_col:
        st.title('IONIQ 5 챗봇 사용 현황')
    with date_col:
        selected_day = st.date_input('날짜', today, key='usage_day', format='YYYY.MM.DD')
    start = end = selected_day
    try:
        rows = read_rows('''SELECT r.request_id, r.session_id, r.created_at, r.completed_at,
            r.status, r.duration_ms, u.content AS question,
            r.snapshot->'intent'->>'action' AS action,
            r.snapshot->>'clarification_count' AS clarification_count,
            r.config->>'pipeline_version' AS pipeline_version
            FROM anna_rag.rag_runs r
            JOIN anna_rag.chat_sessions s USING(session_id)
            JOIN anna_rag.chat_messages u ON u.message_id=r.user_message_id AND u.session_id=r.session_id
            WHERE r.created_at >= %s AND r.created_at < %s
            ORDER BY r.created_at DESC''',
            (datetime.combine(start, time.min, KST),
             datetime.combine(end + timedelta(days=1), time.min, KST)))
        if not rows:
            st.info('선택한 날짜에 저장된 대화가 없습니다.')
            empty = pd.DataFrame({'응답 유형': TYPE_ORDER,
                                  '설명': [TYPE_HELP[name] for name in TYPE_ORDER],
                                  '건수': [0] * len(TYPE_ORDER)})
            st.subheader('챗봇 응답 유형')
            _render_type_chart(empty)
            st.dataframe(empty, hide_index=True, use_container_width=True)
            st.subheader('응답 시간')
            st.info('응답 시간 기록이 없습니다.')
            return

        df = pd.DataFrame(rows)
        done = df[df.completed_at.notna()].copy()
        seconds = _seconds(done.duration_ms)
        status = done.status.fillna('running')
        response_types = status.map(lambda value: STATUS_TYPE.get(value, '기타'))
        total = len(df)
        clarifications = int(response_types.isin(['질문을 되물음', '범위 재확인 안내']).sum())
        out_of_scope = int(response_types.eq('설명서 밖 질문 안내').sum())
        error_count = int(response_types.eq('처리 중 오류').sum())

        st.subheader('오늘 한눈에 보기')
        c = st.columns(5)
        c[0].metric('받은 질문', f'{total:,}건', help='선택한 날짜에 사용자가 보낸 질문 수입니다.')
        c[1].metric('답변까지 걸린 시간', f'{seconds.mean():.1f}초' if len(seconds) else '자료 없음',
                    help='질문을 받은 뒤 답변을 저장할 때까지 걸린 시간의 평균입니다.')
        c[2].metric('되묻기·범위 확인', f'{clarifications:,}회',
                    help='챗봇이 질문을 되묻거나 범위를 다시 확인한 횟수입니다.')
        c[3].metric('설명서 밖 질문', f'{out_of_scope:,}건',
                    help='차량 설명서 범위 밖이라고 안내한 질문 수입니다.')
        c[4].metric('처리 중 오류', f'{error_count:,}건', help='챗봇 처리 중 오류가 기록된 요청 수입니다.')
        st.caption(f'답변 완료 {len(done):,}건 · 처리 중 {total-len(done):,}건')

        _render_response_time_chart(done, seconds.mean() if len(seconds) else 0)

        st.subheader('챗봇 응답 유형')
        st.caption('각 유형이 어떤 뜻인지와 해당 날짜의 건수를 보여줍니다. 기록이 없는 유형은 0건으로 표시합니다.')
        type_counts = response_types.value_counts().reindex(TYPE_ORDER, fill_value=0)
        type_table = pd.DataFrame({'응답 유형': TYPE_ORDER,
                                   '설명': [TYPE_HELP[name] for name in TYPE_ORDER],
                                   '건수': [int(type_counts[name]) for name in TYPE_ORDER]})
        _render_type_chart(type_table)
        st.dataframe(type_table, hide_index=True, use_container_width=True)

        st.subheader('사용자가 입력한 질문')
        recent = df.head(100).copy()
        recent['시각'] = pd.to_datetime(recent.created_at, utc=True).dt.tz_convert(KST).dt.strftime('%H:%M')
        recent['답변까지(초)'] = (pd.to_numeric(recent.duration_ms, errors='coerce') / 1000).round(1)
        recent['응답 유형'] = recent.status.fillna('running').map(lambda value: STATUS_TYPE.get(value, '기타'))
        recent = recent.rename(columns={'question':'질문'})
        st.dataframe(recent[['시각','질문','응답 유형','답변까지(초)']], hide_index=True, use_container_width=True)
    except Exception as error:
        logging.warning('Usage dashboard read failed: %s', type(error).__name__)
        st.error('대화 기록을 불러오지 못했어요. DB 연결 상태를 확인한 뒤 다시 시도해 주세요.')
