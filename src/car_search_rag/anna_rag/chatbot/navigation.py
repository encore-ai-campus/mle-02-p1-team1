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
    if backend is not None and session_id:
        return _close_workers.submit(_finish_session, backend, session_id)
    return None


# body의 가상 요소를 사용해 Streamlit의 애니메이션/불투명도 레이어 밖에 표시합니다.
EXIT_OVERLAY = '''<span id="chat-exit-marker" role="status" aria-label="차량 선택 화면으로 이동 중"></span>
<style>
body:has(#chat-exit-marker)::before {
 content:"";position:fixed;inset:0;z-index:2147483646;
 background:rgba(35,30,52,.32);backdrop-filter:blur(2px);cursor:wait;
}
body:has(#chat-exit-marker)::after {
 content:"";position:fixed;left:50%;top:50%;width:54px;height:32px;
 transform:translate(-50%,-50%);z-index:2147483647;pointer-events:none;
 background-image:radial-gradient(circle,#8d79ec 3px,transparent 3.5px),
 radial-gradient(circle,#8d79ec 3px,transparent 3.5px),
 radial-gradient(circle,#8d79ec 3px,transparent 3.5px);
 background-size:12px 12px;background-repeat:no-repeat;
 background-position:8px 14px,21px 14px,34px 14px;
 animation:exit-dots 1.2s infinite ease-in-out;
}
@keyframes exit-dots {
 0%,70%,100% {background-position:8px 14px,21px 14px,34px 14px;}
 25% {background-position:8px 9px,21px 14px,34px 14px;}
 40% {background-position:8px 14px,21px 9px,34px 14px;}
 55% {background-position:8px 14px,21px 14px,34px 9px;}
}
@media(prefers-reduced-motion:reduce) {body:has(#chat-exit-marker)::after {animation:none;}}
</style>'''
