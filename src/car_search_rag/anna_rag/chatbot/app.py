"""공통 차종 선택 화면 → 선택한 차종의 대화 화면."""
from pathlib import Path
import sys
from uuid import uuid4
import logging
import base64
import time
from concurrent.futures import ThreadPoolExecutor
from queue import Queue, Empty
from html import escape

import streamlit as st

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT / 'src') not in sys.path:
    sys.path.insert(0, str(ROOT / 'src'))

from car_search_rag.anna_rag.chatbot.registry import VEHICLES, load_backend
from car_search_rag.anna_rag.chatbot.navigation import (
    detach_chat, request_chat_exit, EXIT_TRANSITION, RETURN_TRANSITION,
)
from car_search_rag.anna_rag.chatbot.answer_view import (
    render_answer, format_answer, verified_answer_images,
)
from car_search_rag.anna_rag.chatbot.casper_image_view import render_casper_images

BOT_AVATAR = str(Path(__file__).parent / 'assets' / 'hyundai-logo.webp')

st.set_page_config(page_title='자동차 사용설명서 챗봇', page_icon='🚘', layout='wide', initial_sidebar_state='expanded')
# 폰트를 앱에 포함해 외부 CDN 연결 없이도 동일한 글꼴을 표시합니다.
@st.cache_data
def pretendard_data():
    return base64.b64encode((Path(__file__).parent / 'assets' / 'PretendardVariable.woff2').read_bytes()).decode('ascii')

st.markdown(f"""<style>
@font-face {{font-family:'Pretendard Variable';font-style:normal;font-weight:45 920;
font-display:swap;src:url('data:font/woff2;base64,{pretendard_data()}') format('woff2');}}
</style>""", unsafe_allow_html=True)

st.markdown("""<style>
/* Pretendard를 텍스트에만 적용하여 아이콘용 폰트는 보존합니다. */
.stApp, .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp h4,
.stApp h5, .stApp h6, .stApp li, .stApp button, .stApp textarea,
.stApp input, .stApp label, .stApp summary, .stApp table,
[data-testid="stCaptionContainer"], [data-testid="stMarkdownContainer"] {
 font-family:"Pretendard Variable", Pretendard, -apple-system, BlinkMacSystemFont, system-ui, sans-serif!important;
}
.stApp {background:#f6f5fa;color:#21212b;}
.block-container {max-width:980px;padding:2.8rem 2rem 2rem;}
[data-testid="stHeader"] {background:transparent;pointer-events:none;}
[data-testid="stToolbar"] {display:none;}
/* 사이드바는 고정 표시하며 접기/펼치기 컨트롤을 모든 화면에서 제거합니다. */
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="stExpandSidebarButton"],
[data-testid="stSidebarResizeHandle"] {display:none!important;}

[data-testid="stChatMessageAvatarAssistant"] {background:#5b43e8;color:white;}
[data-testid="stChatMessageAvatarUser"] {background:#e5dffe;color:#4d3db0;}
h1 {font-size:2rem!important;letter-spacing:-.06em;word-break:keep-all;}
h2,h3 {letter-spacing:-.04em;}
[data-testid="stChatMessage"] {background:#f8f8fc;border:1px solid #eeedf6;border-radius:18px;margin-bottom:1rem;}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {background:#5b43e8;border-color:#5b43e8;}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stMarkdownContainer"] {color:white;}
/* 사용자 말풍선은 텍스트만 표시합니다. 정렬용 DOM은 유지합니다. */
[data-testid="stChatMessageAvatarUser"] {display:none;}
[data-testid="stChatInput"] {border-radius:18px;border:1px solid #dcd8ec;background:#fff;}
.stButton button {border-radius:12px;min-height:44px;}
.stButton button[kind="primary"] {background:#5b43e8;border-color:#5b43e8;color:white;}
[data-testid="stExpander"] {border-radius:12px;}
[data-testid="stChatMessage"] p {line-height:1.85;margin-bottom:1rem;}
[data-testid="stChatMessage"] li {line-height:1.8;margin-bottom:.65rem;}
[data-testid="stChatMessage"] h4 {font-size:1.08rem;margin-top:0;padding-bottom:.35rem;}
[data-testid="stChatMessage"] [data-testid="stVerticalBlockBorderWrapper"] {background:white;border-radius:12px;margin:10px 0;}

.brand-mark {width:40px;height:40px;border-radius:12px;background:#5b43e8;color:white;display:flex;align-items:center;justify-content:center;font-size:24px;margin-bottom:14px;}
.eyebrow {color:#736f85;font-size:11px;font-weight:700;letter-spacing:.16em;margin-bottom:8px;}
.welcome {padding:24px 0 12px;font-size:34px;line-height:1.35;font-weight:750;letter-spacing:-.055em;}
@media(max-width:640px) {.block-container {padding:3rem 1rem;} h1 {font-size:1.5rem!important;} .welcome {font-size:27px;}}

/* 첫 화면은 사이드바 없이 인사말과 네 개의 차량 카드만 보여줍니다. */
.landing-title {font-size:32px!important;line-height:1.35!important;margin:45px 0 80px!important;font-weight:750!important;}
.st-key-vehicle_cards {margin-bottom:36px;}
.st-key-vehicle_cards button {width:100%;aspect-ratio:1;min-height:150px;background:#f7f7fa;border:1px solid #eeedf3;border-radius:16px;color:#484356;font-size:22px;}
.st-key-vehicle_cards button p {font-size:22px;font-weight:650;}
.st-key-vehicle_cards button:disabled {background:#f7f7fa;border-color:#eeedf3;color:#484356;opacity:1;}
.st-key-vehicle_cards button:hover:enabled {background:#f0edff;color:#5139d4;border-color:#5b43e8;box-shadow:0 4px 18px #5b43e815;}
.st-key-vehicle_cards [data-testid="stCaptionContainer"] {text-align:center;}
[data-testid="stChatInput"] {border-radius:18px;min-height:64px;background:#fff;border:1px solid #e7e4f0;box-shadow:0 3px 20px #24203906;}
[data-testid="stChatInput"]:focus-within {border-color:#a292f5;box-shadow:0 0 0 3px #5b43e810;}
[data-testid="stChatInputSubmitButton"] {background:#5b43e8;color:#fff;border-radius:12px;}
[data-testid="stChatInputSubmitButton"]:disabled {background:#ece8fb;color:#aa9ecf;}
/* 기본 카드 배경은 동일하며, 보라색은 호버/키보드 포커스에서만 사용합니다. */
.st-key-vehicle_cards button:focus-visible {outline:3px solid #5b43e8;outline-offset:3px;}
@media(max-width:640px) {
 .landing-title {font-size:25px!important;margin:22px 0 38px!important;}
 .st-key-vehicle_cards [data-testid="stHorizontalBlock"] {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;}
 .st-key-vehicle_cards [data-testid="stColumn"] {width:100%!important;min-width:0!important;}
 .st-key-vehicle_cards button {min-height:120px;}
}

/* 말풍선은 내용 길이에 맞추고 양쪽을 구분합니다. */
[data-testid="stChatMessage"] {width:fit-content;max-width:86%;background:#fff;border:1px solid #eeecf4;border-radius:6px 22px 22px 22px;padding:20px;box-shadow:0 5px 24px #28204405;}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {margin-left:auto;max-width:72%;border-radius:22px 6px 22px 22px;flex-direction:row-reverse;padding:14px 20px;}
[data-testid="stChatMessage"] p:last-child {margin-bottom:0;}
/* Markdown의 기본 음수 여백이 여러 줄 본문 높이를 줄이지 않도록 합니다. */
[data-testid="stChatMessageContent"] [data-testid="stMarkdown"],
[data-testid="stChatMessageContent"] [data-testid="stMarkdown"] > div,
[data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] {margin-block:0!important;display:flow-root;}
[data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] > :last-child {margin-bottom:0!important;}
/* 재실행 중 남아 있는 이전 출력은 반투명 잔상으로 표시하지 않습니다. */
[data-testid="stChatMessage"] [data-stale="true"] {display:none!important;}

[data-testid="stChatMessageContent"] {min-width:0;overflow-wrap:anywhere;}
[data-testid="stBottomBlockContainer"] {max-width:980px;margin:0 auto;padding-left:2rem;padding-right:2rem;background:#f6f5fa;}
[data-testid="stBottom"], [data-testid="stBottom"] > div {background:#f6f5fa!important;}
[data-testid="stChatInput"] textarea {background:white;}
.stButton button,[data-testid="stChatInput"] {transition:transform .2s ease,box-shadow .2s ease,background .2s ease;}
.stButton button:hover:enabled {transform:translateY(-3px);}
.stButton button:active:enabled {transform:scale(.97);}
[class*="st-key-message_"] {animation:message-in .55s cubic-bezier(.16,1,.3,1) both;}
@keyframes message-in {from {opacity:0;transform:translateY(30px);} to {opacity:1;transform:translateY(0) scale(1);}}
.thinking {display:flex;align-items:center;gap:7px;color:#827796;font-size:13px;height:32px;padding:0;}
.thinking i {width:6px;height:6px;background:#8d79ec;border-radius:50%;animation:thinking 1.2s infinite ease-in-out;}
.thinking i:nth-child(2) {animation-delay:.16s;}.thinking i:nth-child(3) {animation-delay:.32s;}
.thinking span {margin-left:8px;}
@keyframes thinking {0%,70%,100% {transform:translateY(0);opacity:.35;} 35% {transform:translateY(-5px);opacity:1;}}
@media(max-width:640px) {[data-testid="stChatMessage"] {max-width:95%;padding:14px;} [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {max-width:88%;}}
@media(prefers-reduced-motion:reduce) {*,*::before,*::after {animation:none!important;transition:none!important;scroll-behavior:auto!important;}}

/* Figma의 넓은 작성 영역 + 오른쪽 아래 전송 버튼. 실제 Streamlit 입력 기능은 유지합니다. */
[data-testid="stChatInput"] {
 position:relative;min-height:58px;border-radius:20px!important;
 border:1px solid #dce3f0!important;background:#fff!important;
 box-shadow:0 8px 20px #26324d0b;padding:0!important;overflow:hidden;
}
[data-testid="stChatInput"] > div,
[data-testid="stChatInput"] > div > div {background:transparent!important;border:0!important;box-shadow:none!important;}
[data-testid="stChatInput"] textarea {
 min-height:42px!important;max-height:140px!important;
 padding:8px 56px 8px 14px!important;background:transparent!important;
 color:#29354a!important;font-size:17px;line-height:1.6;resize:none;
}
[data-testid="stChatInput"] textarea::placeholder {color:#77839a;opacity:1;}
[data-testid="stChatInput"]:focus-within {border-color:#aaa0f4!important;box-shadow:0 0 0 3px #5b43e80a,0 8px 20px #26324d0b;}
[data-testid="stChatInputSubmitButton"] {
 position:absolute!important;right:10px;bottom:9px;
 width:38px!important;height:38px!important;min-width:38px;padding:0;
 border-radius:999px!important;background:#5543eb!important;color:#fff!important;
 display:flex;align-items:center;justify-content:center;gap:10px;
 transition:transform .18s ease,background .18s ease;
}
[data-testid="stChatInputSubmitButton"]::before {content:none;}
[data-testid="stChatInputSubmitButton"] svg {display:none;}
[data-testid="stChatInputSubmitButton"]::after {
 content:"";width:23px;height:23px;background:currentColor;
 mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M3 3l18 9-18 9 4-9-4-9zm4 9h14' fill='none' stroke='black' stroke-width='1.8' stroke-linejoin='round'/%3E%3C/svg%3E") center/contain no-repeat;
}
[data-testid="stChatInputSubmitButton"]:hover:enabled {background:#4733d9!important;transform:translateY(-2px);}
[data-testid="stChatInputSubmitButton"]:active:enabled {transform:scale(.96);}
[data-testid="stChatInputSubmitButton"]:disabled {background:#e9e5fa!important;color:#a599cc!important;}
[data-testid="stBottomBlockContainer"] {padding-top:12px;padding-bottom:20px;}
/* 고정 입력창 뒤로 마지막 답변이 가려지지 않게 여백을 확보합니다. */
.block-container {padding-bottom:125px;}
@media(max-width:640px) {
 [data-testid="stBottomBlockContainer"] {padding-left:12px;padding-right:12px;padding-bottom:12px;}
 [data-testid="stChatInput"] {min-height:56px;border-radius:18px!important;}
 [data-testid="stChatInput"] textarea {min-height:40px!important;padding:7px 52px 7px 10px!important;font-size:16px;}
 [data-testid="stChatInputSubmitButton"] {right:8px;bottom:8px;height:36px!important;width:36px!important;min-width:36px;}
}

/* 스타일 전용 요소가 만드는 빈 행/간격을 제거합니다. */
[data-testid="stElementContainer"]:has(style) {display:none;}
[data-testid="stChatInput"] > div {padding:6px 10px!important;}
/* 첫 진입은 상단부터 표시하고, 작성창은 별도 고정 영역으로 배치합니다. */
.block-container:has(.landing-title) {padding-top:84px!important;}
.landing-title {margin:0 0 58px!important;padding:0!important;}
/* 준비 중인 차종도 카드 호버는 동일하게 표시하되 클릭 비활성 상태는 유지합니다. */
.st-key-vehicle_cards [data-testid="stElementContainer"]:hover button {
 background:#f0edff;color:#5139d4;border-color:#5b43e8;
 box-shadow:0 4px 18px #5b43e815;transform:translateY(-4px) scale(1.025);
}
@media(max-width:640px) {
 .landing-title {margin-bottom:36px!important;}
}
/* 제공된 현대 로고의 흰색은 유지하고 어두운 바탕을 UI 보라색과 합성합니다. */
[data-testid="stChatMessage"] {align-items:flex-start;gap:12px;}
[data-testid="stChatMessage"] > img {
 width:32px;height:32px;min-width:32px;object-fit:cover;border-radius:10px;
 background:#5b43e8;mix-blend-mode:normal;
}
[data-testid="stChatMessage"] [data-testid="stChatMessageContent"] {padding-top:0;margin:0!important;min-height:32px;}
[data-testid="stChatMessage"] [data-testid="stChatMessageContent"] > div {gap:12px;}
[data-testid="stChatMessageContent"] [data-testid="stElementContainer"]:has([data-testid="stEmpty"]) {display:none;}
</style>""", unsafe_allow_html=True)  # 고정된 스타일만 HTML로 사용합니다.


# 실제 차량 이미지는 카드 버튼 안에 넣어 그림을 눌러도 같은 버튼이 동작합니다.
# AVIF는 브라우저 호환성을 위해 PNG로 변환해 로컬 자산으로 보관했습니다.
logo_image_data = base64.b64encode(Path(BOT_AVATAR).read_bytes()).decode('ascii')
st.markdown(f"""<style>
/* 첫 인사는 아이콘과 문장을 같은 행의 세로 중앙에 맞춥니다. */
.welcome-bubble {{display:flex;align-items:center;gap:12px;width:fit-content;max-width:86%;
 box-sizing:border-box;padding:20px;background:#fff;border:1px solid #eeecf4;
 border-radius:6px 22px 22px 22px;box-shadow:0 5px 24px #28204405;margin-bottom:16px;}}
.welcome-logo {{display:block;flex:0 0 32px;width:32px;height:32px;border-radius:10px;
 background:#5b43e8 url("data:image/webp;base64,{logo_image_data}") center/cover no-repeat;
 background-blend-mode:lighten;}}
.welcome-text {{display:block;margin:0!important;padding:0!important;font-size:16px;line-height:1.5;}}
@media(max-width:640px) {{.welcome-bubble {{max-width:95%;padding:14px;}}}}
/* 원본 파일은 그대로 두고 CSS 배경 합성으로 보라색 로고 타일을 만듭니다. */
[data-testid="stChatMessage"] > img[alt="assistant avatar"] {{
 object-position:-9999px;flex-shrink:0;margin-top:-1px;
 background-color:#5b43e8;
 background-image:url("data:image/webp;base64,{logo_image_data}");
 background-size:cover;background-position:center;background-blend-mode:lighten;
}}
</style>""", unsafe_allow_html=True)

# 각 카드에 같은 이미지/확대 스타일을 적용합니다. 연결 준비 중인 차종도 미리 볼 수 있습니다.
for car_id in ('ioniq5', 'santafe', 'sonata', 'casper'):
    asset = Path(__file__).parent / 'assets' / f'{car_id}.png'
    data = base64.b64encode(asset.read_bytes()).decode('ascii')
    # 캐스퍼 이미지는 원본 여백이 적어 다른 이미지보다 작게 배치합니다.
    image_size = '64%' if car_id == 'casper' else '80%'
    # 원본 투명 여백이 비대칭인 두 이미지는 시각적 중심을 보정합니다.
    image_position = '65% center' if car_id in ('santafe', 'sonata') else '50% center'
    st.markdown(f"""<style>
.st-key-car_{car_id} button {{position:relative;overflow:visible;}}
.st-key-car_{car_id}:hover, .st-key-car_{car_id}:focus-within {{position:relative;z-index:2;}}
.st-key-car_{car_id} button::before {{content:"";position:absolute;inset:0% -25% 27%;
 background-image:url("data:image/png;base64,{data}");
 background-size:{image_size} auto;background-repeat:no-repeat;background-position:{image_position};
 pointer-events:none;transform-origin:center 60%;transition:transform .45s cubic-bezier(.2,.8,.2,1);}}
.st-key-car_{car_id}:hover button::before,
.st-key-car_{car_id} button:focus-visible::before {{transform:scale(1.45) translateY(-3px);}}
.st-key-car_{car_id} button p {{position:absolute;bottom:16px;left:0;right:0;margin:0;font-size:19px;}}
</style>""", unsafe_allow_html=True)


# 원본 설명서는 차종별로 지정합니다. 다운로드는 대화를 다시 실행하지 않습니다.
MANUAL_FILES = {'ioniq5': 'NE1_2027_ko_KR.pdf', 'casper': 'AXEV_2027_ko_KR.pdf'}

@st.cache_data(show_spinner=False)
def manual_bytes(path, modified_at):
    # 수정 시간이 바뀌면 캐시도 갱신합니다.
    return Path(path).read_bytes()


def backend_for(vehicle_id):
    # 화면은 차종별 구현을 생성하고, 현재 접속에서 재사용하기만 합니다.
    key = f'vehicle_backend_{vehicle_id}'
    if key not in st.session_state:
        st.session_state[key] = load_backend(vehicle_id)
    return st.session_state[key]


def init_state():
    defaults = {'active_vehicle': None, 'conversation_id': None, 'messages': [],
                'pending': None, 'request_error': False, 'session_notice': None}
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def leave_chat():
    detach_chat(st.session_state)


def _merge_packet_images(selected_images, verified_images):
    """선택 이미지와 답변 링크 이미지를 합치고 URL 중복을 제거합니다."""
    display_images = []
    seen_image_urls = set()
    for image in selected_images or ():
        image_url = image.get('data')
        if isinstance(image_url, str):
            if image_url in seen_image_urls:
                continue
            seen_image_urls.add(image_url)
        display_images.append(image)
    for image in verified_images or ():
        image_url = image['url']
        if image_url in seen_image_urls:
            continue
        seen_image_urls.add(image_url)
        display_images.append({
            'data': image_url,
            'pdf_page': image.get('page_no'),
            'caption': image.get('caption', ''),
        })
    return display_images


def return_to_vehicles():
    request_chat_exit(st.session_state)


@st.dialog('차량 선택으로 돌아갈까요?', dismissible=False)
def confirm_chat_exit():
    st.write('돌아가면 현재 대화가 화면에서 사라지고, 차량을 다시 선택하면 새 대화가 시작됩니다.')
    st.caption('답변을 생성 중이라면 진행 중인 답변도 이 화면에서 이어서 볼 수 없어요.')
    stay, leave = st.columns(2)
    if stay.button('대화 계속하기', use_container_width=True, key='keep_chat'):
        st.session_state.confirm_chat_exit = False
        st.rerun()
    if leave.button('돌아가기', type='primary', use_container_width=True, key='confirm_leave_chat'):
        st.session_state.confirm_chat_exit = False
        st.session_state.exiting_chat = True
        st.rerun()


def animate_chat_exit():
    # 현재 사이드바를 닫는 모션을 보여 준 다음, 대화 종료 작업은 백그라운드로 넘깁니다.
    st.markdown(EXIT_TRANSITION, unsafe_allow_html=True)
    time.sleep(.42)
    leave_chat()
    st.session_state.returning_to_vehicles = True
    st.rerun()


def show_packet(message, render_body=True):
    packet = message['packet']
    answer_text = packet['answer']['text']
    verified_images = verified_answer_images(answer_text, packet.get('verified_images', []))
    if render_body:
        render_answer(answer_text, verified_images=verified_images)

    if packet.get('vehicle_id') == 'casper':
        # 캐스퍼 원본 응답의 그림 번호를 유지하고 image_id로 중복을 제거합니다.
        render_casper_images(packet)
    else:
        # backend가 선택한 이미지와 답변의 검증된 링크 이미지를 URL 기준으로 합칩니다.
        display_images = _merge_packet_images(message.get('images'), verified_images)
        if display_images:
            st.caption('설명서의 연결된 그림입니다. 답변과 함께 원문을 확인하세요.')
            for image in display_images:
                page_caption = f"PDF {image['pdf_page']}페이지" if image.get('pdf_page') is not None else ''
                description = image.get('caption', '')
                caption = ' · '.join(part for part in (page_caption, description) if part)
                st.image(image['data'], caption=caption or None,
                         alt=description or '차량 사용설명서 이미지')

    # 모델이 만든 URL 대신 DB가 반환한 문서명/페이지 정보를 사용합니다.
    cited = set(packet['answer'].get('cited_labels', []))
    retrieved = packet.get('source_display') == 'retrieved'
    sources = [s for s in packet.get('sources', []) if retrieved or s.get('label') in cited]
    if sources:
        with st.expander('검색에 사용한 설명서' if retrieved else '설명서 출처 확인'):
            for s in sources:
                pages = ', '.join(map(str, s.get('pdf_pages', [])))
                st.write(f"[{s['label']}] {s['title']} · PDF {pages}페이지")
                st.caption(s.get('source_file', ''))
                if s.get('quote'):
                    st.text(s['quote'])
    if message.get('image_error'):
        st.caption('관련 그림을 불러오지 못했습니다. 답변과 출처는 확인할 수 있어요.')
    for notice in packet.get('notices', []):
        st.caption(notice)
    # 생성 여부·동작은 차종 구현이 결정하고, 화면은 전달된 버튼만 표시합니다.
    for action in packet.get('actions', []):
        if st.button(action['label'], key=f"action_{message['ui_id']}_{action['id']}"):
            try:
                selected_backend = backend_for(st.session_state.active_vehicle)
                with st.spinner(''):
                    updated = selected_backend.perform_action(
                        st.session_state.conversation_id, packet, action['id'])
                message['packet'] = updated
                message['images'] = selected_backend.get_related_images(updated)
                st.rerun()
            except Exception as error:
                logging.warning('Vehicle action failed: %s', type(error).__name__)
                st.info('처리하지 못했어요. 최근 질문인지 확인하고 다시 질문해 주세요.')
    if packet.get('download_html'):
        st.download_button('대화 기록 HTML 다운로드', data=packet['download_html'],
                           file_name='car_manual_history.html', mime='text/html',
                           key=f"history_download_{message['ui_id']}", on_click='ignore')


init_state()
returning_to_vehicles = st.session_state.pop('returning_to_vehicles', False)
# 대시보드 상태는 Sonata 화면에만 적용합니다.
if st.session_state.active_vehicle == 'sonata':
    st.session_state.setdefault('sonata_active_view', 'chat')

# 차량 선택 이후에 표시하는 공통 메뉴입니다.
st.markdown("""<style>
.st-key-vehicle_menu {position:fixed;top:20px;right:28px;z-index:1000;width:44px;}
.st-key-vehicle_menu [data-testid="stPopoverButton"] {
 width:44px;height:44px;min-height:44px;padding:0;border:0!important;
 background:transparent!important;color:#5b43e8!important;box-shadow:none!important;
 display:flex;align-items:center;justify-content:center;gap:0;
}
.st-key-vehicle_menu [data-testid="stPopoverButton"]:hover {
 color:#4932cf!important;
}
.st-key-vehicle_menu [data-testid="stPopoverButton"] > div {
 position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;
 clip:rect(0,0,0,0);white-space:nowrap;
}
/* 기본 메뉴·펼침 아이콘 대신 동일한 굵기의 보라색 세 줄만 표시합니다. */
.st-key-vehicle_menu [data-testid="stPopoverButton"] svg,
.st-key-vehicle_menu [data-testid="stPopoverButton"] [data-testid="stIconMaterial"] {display:none!important;}
.st-key-vehicle_menu [data-testid="stPopoverButton"]::before {
 content:"";display:block;flex:0 0 22px;width:22px;height:2px;border-radius:2px;
 background:currentColor;box-shadow:0 -7px 0 currentColor,0 7px 0 currentColor;
}
.st-key-vehicle_menu [data-testid="stPopoverButton"]:focus-visible {outline:2px solid #b9aff2;outline-offset:2px;}
.block-container:not(:has(.landing-title)) {padding-top:84px;}
@media(max-width:640px) {.st-key-vehicle_menu {top:16px;right:16px;}}
</style>""", unsafe_allow_html=True)
if st.session_state.active_vehicle is not None:
    with st.container(key='vehicle_menu'):
        with st.popover('메뉴', icon=':material/menu:', key='vehicle_menu_popover'):
            if st.session_state.active_vehicle == 'sonata':
                if st.button('데이터 대시보드', key='menu_data_dashboard', use_container_width=True):
                    st.session_state.sonata_active_view = 'dashboard'
                    st.rerun()
                st.link_button(
                    '작업 Document',
                    'https://app.notion.com/p/3dec53ef970481b49d25c56dcae99f16?pvs=204',
                    use_container_width=True,
                )
            else:
                st.button('데이터 대시보드', key='menu_data_dashboard', use_container_width=True)
                st.button('작업 Document', key='menu_work_document', use_container_width=True)
if st.session_state.session_notice:
    st.info(st.session_state.session_notice)
    st.session_state.session_notice = None

# 1. 공통 입구: 차종 선택 전에는 어떤 RAG도 호출하지 않습니다.
if st.session_state.active_vehicle is None:
    if returning_to_vehicles:
        st.markdown(RETURN_TRANSITION, unsafe_allow_html=True)
    st.markdown('<style>[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {display:none;}</style>', unsafe_allow_html=True)
    selected_car = None
    st.markdown('<h1 class="landing-title">안녕하세요!<br>보유하고 있는 자동차를 선택해주세요.</h1>', unsafe_allow_html=True)
    with st.container(key='vehicle_cards'):
        columns = st.columns(4, gap='medium')
        for column, (choice, vehicle) in zip(columns, VEHICLES.items()):
            with column:
                ready = vehicle.module is not None
                label = {'ioniq5': 'IONIQ 5', 'santafe': 'SANTA FE',
                         'sonata': 'SONATA', 'casper': 'CASPER'}.get(choice, vehicle.label)
                clicked = st.button(label, key=f'car_{choice}', disabled=not ready,
                                    use_container_width=True)
                if clicked:
                    selected_car = choice
    if selected_car:
        # 연결을 기다리지 않고 화면 전환부터 실행합니다.
        st.markdown("""<style>
.landing-title, .st-key-vehicle_cards {
 animation:landing-out .38s ease-in forwards;pointer-events:none;
}
@keyframes landing-out {to {opacity:0;translate:0 70px;}}
</style>""", unsafe_allow_html=True)
        time.sleep(.4)
        st.session_state.active_vehicle = selected_car
        st.session_state.conversation_id = None
        st.session_state.startup_error = False
        st.session_state.entering_chat = True
        st.rerun()
    st.stop()

# 2. 선택한 차종을 대화가 끝날 때까지 고정합니다.
vehicle_id = st.session_state.active_vehicle
# 사이드바는 차량 선택 이후에만 표시합니다.
entering_chat = st.session_state.pop('entering_chat', False)
st.markdown("""<style>
/* 대화 화면에서는 이전 화면의 숨김/자동 접힘 상태를 명시적으로 해제합니다. */
[data-testid="stSidebar"] {
 display:block!important;visibility:visible!important;opacity:1;
 position:relative!important;transform:none!important;margin-left:0!important;
 width:280px!important;min-width:280px!important;max-width:280px!important;
 background:#f0eef8;border-right:1px solid #e5e1f1;
}
[data-testid="stSidebarContent"] {display:block!important;visibility:visible!important;}
[data-testid="stSidebarCollapseButton"], [data-testid="stSidebarCollapsedControl"] {display:none!important;}
@media(max-width:640px) {
 [data-testid="stSidebar"] {width:160px!important;min-width:160px!important;max-width:160px!important;}
 [data-testid="stSidebarUserContent"] {padding:24px 10px!important;}
}
[data-testid="stSidebarUserContent"] {padding-top:48px;}
/* 보이는 것은 화살표만, 버튼 이름은 보조 기술에 그대로 제공합니다. */
.st-key-back_to_vehicles {position:absolute;top:18px;left:18px;width:40px;z-index:2;}
.st-key-back_to_vehicles button {width:40px;min-height:40px;padding:8px;border:0;background:transparent;color:#625775;}
.st-key-back_to_vehicles button [data-testid="stMarkdownContainer"] {position:absolute;width:1px;height:1px;padding:0;overflow:hidden;clip-path:inset(50%);white-space:nowrap;}
.st-key-back_to_vehicles button:hover {background:#e6e0f7;color:#5b43e8;}

.sidebar-car {text-align:center;padding:16px 0 28px;}
.sidebar-car img {width:100%;max-width:230px;height:135px;object-fit:contain;}
.sidebar-car h2 {font-size:23px;font-weight:700;letter-spacing:-.03em;margin:8px 0;color:#484356;}
.sidebar-car p {font-size:13px;color:#8b849e;margin:0;}
</style>""", unsafe_allow_html=True)
if entering_chat:
    st.markdown("""<style>
[data-testid="stSidebar"] {animation:sidebar-in .5s cubic-bezier(.2,.8,.2,1) both;}
.sidebar-car {animation:car-up .65s cubic-bezier(.2,.8,.2,1) both;}
.st-key-chat_welcome {animation:welcome-in .45s .25s ease-out both;}
@keyframes sidebar-in {from {translate:-100% 0;opacity:0;} to {translate:0 0;opacity:1;}}
@keyframes car-up {from {transform:translateY(110px) scale(1.18);opacity:0;} to {transform:translateY(0) scale(1);opacity:1;}}
@keyframes welcome-in {from {transform:translateY(22px);opacity:0;} to {transform:translateY(0);opacity:1;}}
</style>""", unsafe_allow_html=True)
with st.sidebar:
    st.button('차량 선택으로 돌아가기', icon=':material/arrow_back:',
              key='back_to_vehicles', on_click=return_to_vehicles)
    selected_label = {'ioniq5': 'IONIQ 5', 'santafe': 'SANTA FE',
                      'sonata': 'SONATA', 'casper': 'CASPER'}.get(vehicle_id, VEHICLES[vehicle_id].label)
    selected_image = base64.b64encode((Path(__file__).parent / 'assets' / f'{vehicle_id}.png').read_bytes()).decode('ascii')
    st.markdown(f'<div class="sidebar-car"><img src="data:image/png;base64,{selected_image}" alt="{escape(selected_label)}"><h2>{escape(selected_label)}</h2><p>자동차 사용설명서</p></div>', unsafe_allow_html=True)
    manual_name = MANUAL_FILES.get(vehicle_id)
    manual_path = Path(__file__).parent / 'manuals' / manual_name if manual_name else None
    if vehicle_id == 'sonata':
        manual_name = 'DN8_2026_ko_KR.pdf'
        manual_path = ROOT / 'data' / manual_name
    if vehicle_id == 'santafe':
        manual_name = 'santafe_hev_manual.pdf'
        manual_path = ROOT / 'data' / manual_name
    if manual_path and manual_path.is_file():
        st.download_button('PDF 사용설명서 다운로드',
                           data=manual_bytes(str(manual_path), manual_path.stat().st_mtime_ns),
                           file_name=manual_name, mime='application/pdf',
                           use_container_width=True, on_click='ignore', key='manual_download')
    else:
        st.caption('다운로드할 설명서가 아직 등록되지 않았습니다.')

# Sonata 대시보드는 공통 사이드바를 그린 뒤 채팅 시작/질문 처리 전에 표시합니다.
# 기존 conversation/session/backend 상태는 건드리지 않고 현재 화면만 전환합니다.
if vehicle_id == 'sonata' and st.session_state.sonata_active_view == 'dashboard':
    from app_kbj import _render_quality_dashboard

    st.title('📊 데이터 대시보드')
    _render_quality_dashboard()
    if st.button('← 챗봇으로 돌아가기', key='sonata_dashboard_back'):
        st.session_state.sonata_active_view = 'chat'
        st.rerun()
    st.stop()

# 사이드바와 대화 화면이 표시된 다음 연결을 시작합니다.
if st.session_state.conversation_id is None:
    if st.session_state.get('exiting_chat'):
        animate_chat_exit()
    st.chat_input('차량 사용법을 물어보세요', disabled=True, key='startup_input')
    with st.container(key='chat_welcome'):
        with st.chat_message('assistant', avatar=BOT_AVATAR):
            if st.session_state.get('startup_error', False):
                st.write('설명서를 준비하지 못했어요. 다시 시도해 주세요.')
                if st.button('설명서 다시 연결'):
                    st.session_state.startup_error = False
                    st.rerun()
                st.stop()
            st.markdown('<div class="thinking" role="status" aria-label="답변 준비 중"><i></i><i></i><i></i></div>', unsafe_allow_html=True)
            try:
                sid = backend_for(vehicle_id).start_session(is_test=True)
                st.session_state.conversation_id = sid
            except Exception as error:
                logging.warning('Chat startup failed: %s', type(error).__name__)
                st.session_state.startup_error = True
    st.rerun()

backend = backend_for(vehicle_id)

# 인사말·완료된 대화·생성 중 답변은 매번 같은 위치에 만듭니다.
# 조건에 따라 인사말 블록을 없애면 다음 메시지들이 이전 답변의 자리를 재사용합니다.
welcome_slot = st.empty()
history_container = st.container(key='chat_history')
pending_slot = st.empty()
if not st.session_state.messages:
    welcome_slot.markdown('<div class="welcome-bubble"><span class="welcome-logo" role="img" aria-label="현대 로고"></span><span class="welcome-text">안녕하세요! 차량을 사용하며 궁금했던 점을 물어보세요.</span></div>', unsafe_allow_html=True)
with history_container:
    for index, message in enumerate(st.session_state.messages):
        message.setdefault('ui_id', f'history_{index}')
        with st.container(key=f"message_{message['ui_id']}"):
            with st.chat_message(message['role'], avatar=BOT_AVATAR if message['role'] == 'assistant' else None):
                if message['role'] == 'user':
                    st.markdown(message['text'])
                else:
                    show_packet(message)

if st.session_state.get('exiting_chat'):
    animate_chat_exit()
if st.session_state.get('confirm_chat_exit'):
    confirm_chat_exit()
    st.chat_input('차량 사용법을 물어보세요', disabled=True, key='exit_confirmation_input')
    st.stop()

# 실패한 요청은 같은 request_id로 재시도하여 중복 저장을 방지합니다.
retry = False
if st.session_state.pending and st.session_state.request_error:
    st.warning('답변을 완료하지 못했어요. 다시 시도하거나 새 대화를 시작해 주세요.')
    retry = st.button('같은 질문 다시 시도')
resume_pending_reply = st.session_state.pending is not None
question = st.chat_input('차량 사용법을 물어보세요', max_chars=1000,
                         disabled=st.session_state.pending is not None, submit_mode='disable')
if question:
    # 네트워크/DB를 기다리지 않고 내 메시지를 화면에 먼저 추가합니다.
    st.session_state.pending = {'text': question, 'id': str(uuid4())}
    st.session_state.messages.append({'role': 'user', 'text': question,
                                      'ui_id': st.session_state.pending['id'] + '_user'})
    st.session_state.request_error = False
    welcome_slot.empty()
    with history_container:
        with st.container(key=f"message_{st.session_state.pending['id']}_user"):
            with st.chat_message('user'):
                st.markdown(question)
if st.session_state.pending and (not st.session_state.request_error or retry):
    if question:
        # 전송 메시지가 먼저 그려진 뒤 봇 로딩이 이어지도록 짧게 간격을 둡니다.
        time.sleep(.15)
    pending = st.session_state.pending
    try:
        # 작업 스레드는 모델/DB만 처리하고, 화면 변경은 메인 스레드에서 합니다.
        with pending_slot.container():
            with st.container(key=f"message_{pending['id']}_assistant"):
                with st.chat_message('assistant', avatar=BOT_AVATAR):
                    loading = st.empty()
                    draft = st.empty()
                    # 이전 답변의 이미지·출처를 새 답변을 기다리는 동안 남겨 두지 않습니다.
                    details = st.empty()
                    def show_loading(label):
                        loading.markdown('<div class="thinking" role="status" aria-label="답변 준비 중"><i></i><i></i><i></i></div>', unsafe_allow_html=True)
                    show_loading('질문을 확인하고 있어요')
                    # 대화가 유효한지는 선택된 차종의 로직에서 판단합니다.
                    try:
                        expired = not backend.is_session_active(st.session_state.conversation_id)
                        if expired:
                            leave_chat()
                            st.session_state.session_notice = '이전 대화가 종료됐어요. 차종을 선택해 새로 시작해 주세요.'
                            st.rerun()
                    except Exception as error:
                        logging.warning('Session check failed: %s', type(error).__name__)
                        st.session_state.request_error = True
                        st.rerun()
                    job = st.session_state.get('chat_job')
                    if job is None or job['id'] != pending['id']:
                        events = Queue()
                        def on_event(kind, value):
                            events.put((kind, value))
                        worker = ThreadPoolExecutor(max_workers=1)
                        future = worker.submit(backend.chat, st.session_state.conversation_id,
                                               pending['text'], request_id=pending['id'], on_event=on_event)
                        # 재실행/확인창이 답변 완료를 기다리며 막히지 않도록 합니다.
                        worker.shutdown(wait=False)
                        job = {'id': pending['id'], 'future': future, 'events': events,
                               'text': '', 'buffer': ''}
                        st.session_state.chat_job = job
                    future, events = job['future'], job['events']
                    if job['text']:
                        loading.empty()
                        draft.markdown(format_answer(job['text']))
                    while not future.done() or not events.empty() or job['buffer']:
                        # Streamlit가 뒤로가기 클릭을 처리할 수 있는 재실행 지점을 둡니다.
                        if st.session_state.pending is None:
                            st.stop()
                        while True:
                            try:
                                kind, value = events.get_nowait()
                            except Empty:
                                break
                            if kind == 'token':
                                job['buffer'] += value
                        if future.done() and future.result()['answer']['status'] != 'answered':
                            job['buffer'] = ''
                            break
                        if job['buffer']:
                            job['text'] += job['buffer'][:3]
                            job['buffer'] = job['buffer'][3:]
                            loading.empty()
                            draft.markdown(format_answer(job['text']))
                        time.sleep(.045)
                    packet = future.result()
                    loading.empty()
                    # 같은 출력 위치와 같은 서식으로 최종 문구만 확정합니다.
                    verified_images = verified_answer_images(
                        packet['answer']['text'], packet.get('verified_images', []))
                    draft.markdown(format_answer(
                        packet['answer']['text'], verified_images=verified_images))
                    message = {'role': 'assistant', 'packet': packet, 'images': [],
                               'ui_id': pending['id'] + '_assistant'}
                    try:
                        message['images'] = backend.get_related_images(packet)
                    except Exception as error:
                        message['image_error'] = True
                        logging.warning('Image fetch failed: %s', type(error).__name__)
                    with details.container():
                        show_packet(message, render_body=False)
        st.session_state.messages.append(message)
        st.session_state.pop('chat_job', None)
        st.session_state.pending = None
        st.session_state.request_error = False
        # 일반 전송은 재실행하지 않아 완성된 말풍선이 깜빡이지 않습니다.
        if retry or resume_pending_reply:
            st.rerun()
    except Exception as error:
        st.session_state.pop('chat_job', None)
        logging.warning('Chat request failed: %s', type(error).__name__)
        st.session_state.request_error = True
        st.rerun()
