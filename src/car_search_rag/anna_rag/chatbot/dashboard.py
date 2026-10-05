"""9번 대시보드 초안의 기록 조회를 Streamlit 화면으로 제공합니다."""
from datetime import datetime, timedelta, time
from pathlib import Path
from zoneinfo import ZoneInfo
import logging
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from car_search_rag.common.database_manager import DatabaseManager

KST = ZoneInfo('Asia/Seoul')
ERRORS = {'error', 'agent_error', 'intent_error', 'invalid_citations', 'missing_tool', 'tool_limit'}


def read_rows(sql, params=()):
    # 요청마다 별도 연결을 열며, 대시보드에서는 DB를 변경하지 않습니다.
    load_dotenv(Path(__file__).resolve().parents[4] / '.env', override=False)
    with DatabaseManager().connect(camel_case_keys=False) as conn:
        conn.execute('SET TRANSACTION READ ONLY')
        return conn.execute(sql, params).fetchall()


def render_dashboard():
    st.title('품질 대시보드')
    st.caption('IONIQ 5 · 저장된 대화와 검색 근거를 확인합니다. 답변 완료율은 정답률이 아닙니다.')
    today = datetime.now(KST).date()
    left, middle, right = st.columns(3)
    start = left.date_input('시작일', today - timedelta(days=30))
    end = middle.date_input('종료일', today)
    mode = right.selectbox('기록 구분', ['실습 기록', '전체', '서비스 기록'])
    if start > end:
        st.warning('시작일을 종료일 이전으로 선택해 주세요.')
        return
    test = None if mode == '전체' else mode == '실습 기록'
    st.button('새로고침', key='refresh_dashboard')
    try:
        rows = read_rows('''SELECT r.request_id, r.session_id, r.created_at, r.completed_at,
            r.status, r.duration_ms, r.llm_usage, u.content AS question,
            r.config->>'pipeline_version' AS pipeline_version
            FROM anna_rag.rag_runs r JOIN anna_rag.chat_sessions s USING(session_id)
            JOIN anna_rag.chat_messages u ON u.message_id=r.user_message_id AND u.session_id=r.session_id
            WHERE r.created_at >= %s AND r.created_at < %s
              AND (%s::boolean IS NULL OR s.is_test=%s)
            ORDER BY r.created_at DESC''',
            (datetime.combine(start, time.min, KST),
             datetime.combine(end + timedelta(days=1), time.min, KST), test, test))
        if not rows:
            st.info('선택한 기간에 저장된 기록이 없습니다.')
            return
        df = pd.DataFrame(rows)
        version = st.selectbox('실행 버전', ['전체'] + sorted(df.pipeline_version.dropna().unique().tolist()))
        if version != '전체':
            df = df[df.pipeline_version.eq(version)]
        done = df[df.completed_at.notna()]
        n = len(done)
        times = pd.to_numeric(done.duration_ms, errors='coerce').dropna() / 1000
        cols = st.columns(4)
        cols[0].metric('전체 요청', len(df))
        cols[1].metric('답변 완료율', f'{done.status.eq("answered").mean()*100:.1f}%' if n else '자료 없음')
        cols[2].metric('오류율', f'{done.status.isin(ERRORS).mean()*100:.1f}%' if n else '자료 없음')
        cols[3].metric('평균 처리 시간', f'{times.mean():.2f}초' if len(times) else '자료 없음')
        st.caption(f'완료 요청 {n}건 · 미완료 요청 {len(df)-n}건 · 비율은 완료 요청 기준입니다. 처리 시간은 DB 기록 기준입니다.')
        st.subheader('처리 상태')
        st.bar_chart(df.status.fillna('미기록').value_counts(), color='#5b43e8')
        st.subheader('요청 기록')
        # 전체 기간으로 집계하고, 표시 목록만 최근 100개로 제한합니다.
        st.caption('아래 목록과 상세 선택에는 최근 100건을 표시합니다.')
        recent = df.head(100).copy()
        recent['created_at'] = pd.to_datetime(recent.created_at, utc=True).dt.tz_convert(KST)
        st.dataframe(recent[['created_at', 'question', 'status', 'duration_ms', 'pipeline_version']],
                     hide_index=True, use_container_width=True)
        options = {str(r.request_id): f'{r.question[:55]} · {r.status}' for r in recent.itertuples()}
        selected = st.selectbox('자세히 볼 요청', list(options), format_func=options.get)
        detail = read_rows('''SELECT r.snapshot, r.search_question, a.content AS answer_text,
            u.content AS question FROM anna_rag.rag_runs r
            JOIN anna_rag.chat_messages u ON u.message_id=r.user_message_id AND u.session_id=r.session_id
            LEFT JOIN anna_rag.chat_messages a ON a.message_id=r.assistant_message_id AND a.session_id=r.session_id
            WHERE r.request_id=%s''', (selected,))
        if not detail:
            st.info('해당 기록이 없습니다.')
            return
        row = detail[0]
        snapshot = row['snapshot'] or {}
        st.subheader('질문과 답변')
        st.text(row['question'])
        st.markdown(row['answer_text'] or '아직 답변이 저장되지 않았습니다.')
        with st.expander('검색 질문과 근거 확인'):
            st.text(row['search_question'] or '검색 기록 없음')
            st.write('검색 청크')
            st.text(snapshot.get('evidence') or '기록 없음')
            st.write('부모 본문')
            st.text(snapshot.get('parent_context') or '기록 없음')
            st.write('출처')
            st.json(snapshot.get('sources', []))
        with st.expander('도구 실행과 관련 이미지 기록'):
            st.json(snapshot.get('tool_calls', []))
            st.json(snapshot.get('image_candidates', []))
    except Exception as error:
        logging.warning('Dashboard read failed: %s', type(error).__name__)
        st.error('기록을 불러오지 못했어요. DB 연결 상태를 확인한 뒤 다시 시도해 주세요.')
