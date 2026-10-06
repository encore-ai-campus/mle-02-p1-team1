"""화면 이탈과 차종별 종료 작업을 분리합니다. 대화 저장 정책은 변경하지 않습니다."""
import logging
from concurrent.futures import ThreadPoolExecutor

# 매번 executor를 with로 만들면 종료를 기다리므로 프로세스에서 재사용합니다.
_close_workers = ThreadPoolExecutor(max_workers=4, thread_name_prefix='chat-close')


def _finish_session(backend, session_id):
    try:
        backend.end_session(session_id)
    except Exception as error:
        logging.warning('Session close failed: %s', type(error).__name__)


def detach_chat(state):
    """이전 backend와 ID만 작업자에 넘기고 새 대화와 즉시 분리합니다."""
    vehicle_id = state.get('active_vehicle')
    session_id = state.get('conversation_id')
    backend = state.pop(f'vehicle_backend_{vehicle_id}', None)
    for key in ('active_vehicle', 'conversation_id', 'pending'):
        state[key] = None
    state['messages'] = []
    state['request_error'] = False
    state.pop('vehicle_choice', None)
    state.pop('entering_chat', None)
    state.pop('confirm_chat_exit', None)
    state.pop('exiting_chat', None)
    # 실행 중인 답변은 예전 대화에 남겨 두고, 새 화면에서 다시 붙이지 않습니다.
    job = state.pop('chat_job', None)
    if job:
        job['future'].cancel()
    if backend is not None and session_id:
        return _close_workers.submit(_finish_session, backend, session_id)
    return None


def request_chat_exit(state):
    """대화가 있으면 먼저 확인하고, 빈 대화는 바로 복귀 애니메이션을 시작합니다."""
    if state.get('messages') or state.get('pending'):
        state['confirm_chat_exit'] = True
    else:
        state['exiting_chat'] = True


EXIT_TRANSITION = """<span id="chat-exit-marker" aria-hidden="true"></span>
<style>
body:has(#chat-exit-marker) {pointer-events:none;}
body:has(#chat-exit-marker) [data-testid="stSidebar"] {
 animation:sidebar-out .4s cubic-bezier(.4,0,.8,.2) forwards!important;
}
body:has(#chat-exit-marker) .sidebar-car {
 animation:car-down .4s ease-in forwards!important;
}
body:has(#chat-exit-marker) .st-key-chat_history,
body:has(#chat-exit-marker) [data-testid="stChatMessage"],
body:has(#chat-exit-marker) .welcome-bubble,
body:has(#chat-exit-marker) [data-testid="stBottom"],
body:has(#chat-exit-marker) .st-key-vehicle_menu {
 animation:chat-out .3s ease-in forwards!important;
}
@keyframes sidebar-out {to {translate:-100% 0;opacity:0;}}
@keyframes car-down {to {transform:translateY(55px) scale(.9);opacity:0;}}
@keyframes chat-out {to {opacity:0;translate:0 22px;}}
@media(prefers-reduced-motion:reduce) {
 body:has(#chat-exit-marker) * {animation:none!important;}
}
</style>"""

RETURN_TRANSITION = """<style>
.landing-title {animation:landing-return .45s cubic-bezier(.16,1,.3,1) both;}
.st-key-vehicle_cards {animation:landing-return .55s .06s cubic-bezier(.16,1,.3,1) both;}
@keyframes landing-return {from {opacity:0;translate:0 65px;} to {opacity:1;translate:0 0;}}
@media(prefers-reduced-motion:reduce) {
 .landing-title, .st-key-vehicle_cards {animation:none!important;}
}
</style>"""
