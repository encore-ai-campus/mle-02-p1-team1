"""아이오닉 구축 문서. 정적 자료를 표시하며 DB/API를 호출하지 않습니다."""
import base64
from pathlib import Path

import streamlit as st


@st.cache_data(show_spinner=False)
def document_html(html_bytes: bytes, font_bytes: bytes) -> str:
    # HTML/폰트가 바뀌면 캐시 키도 바뀝니다. 외부 CDN 없이 열 수 있습니다.
    return html_bytes.decode('utf-8').replace(
        '__PRETENDARD_URL__',
        'data:font/woff2;base64,' + base64.b64encode(font_bytes).decode('ascii'),
    )


def render_work_document():
    assets = Path(__file__).parent / 'assets'
    html = document_html(
        (assets / 'ioniq5-work-document.html').read_bytes(),
        (assets / 'PretendardVariable.woff2').read_bytes(),
    )
    # 별도 URL의 전체 화면 문서입니다. 챗봇의 레이아웃/세션을 렌더링하지 않습니다.
    st.html('''<style>
    [data-testid="stHeader"], [data-testid="stToolbar"] {display:none!important;}
    iframe {position:fixed!important;inset:0!important;width:100vw!important;
            height:100dvh!important;border:0!important;z-index:9999;background:white;}
    [data-testid="stMain"] {overflow:hidden;}
    </style>''')
    st.iframe(html, height=980, tab_index=0, alt='전체 챗봇 구조와 아이오닉 M0–M8 작업 문서')
