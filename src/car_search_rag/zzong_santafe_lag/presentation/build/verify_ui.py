"""발표 화면이 대화를 보존하고 외부 검색 없이 렌더링되는지 확인합니다."""
import json
import socket
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[5]
MODULE = ROOT / 'src/car_search_rag/zzong_santafe_lag'
sys.path.insert(0, str(ROOT / 'src'))
NETWORK_ATTEMPTS = []
ORIGINAL_CONNECT = socket.socket.connect


def deny_connect(*args, **kwargs):
    """자료 화면에서 예상하지 않은 원격 연결이 있으면 검증을 실패시킵니다."""
    # Windows asyncio 내부 통신은 루프백 소켓을 사용하므로 허용합니다.
    address = args[1] if len(args) > 1 else None
    if isinstance(address, tuple) and address[0] in {'127.0.0.1', '::1', 'localhost'}:
        return ORIGINAL_CONNECT(*args, **kwargs)
    NETWORK_ATTEMPTS.append(str(args[1:] or args))
    raise AssertionError('자료 화면에 외부 연결이 발생했습니다.')


def verify():
    """두 메뉴 전환과 기존 대화 상태 보존, 다운로드·평가 탭을 대조합니다."""
    socket.socket.connect = deny_connect
    app = AppTest.from_file(str(MODULE / 'integrated_app.py'), default_timeout=45)
    app.session_state['active_vehicle'] = 'santafe'
    app.session_state['santafe_active_view'] = 'document'
    app.session_state['conversation_id'] = 'presentation-verification-session'
    app.session_state['messages'] = [{'role':'user','text':'기존 질문 보존 확인'}]
    app.run()
    assert not app.exception, [item.value for item in app.exception]
    assert any('싼타페 작업 Document' in item.value for item in app.title)
    assert app.session_state['conversation_id'] == 'presentation-verification-session'
    assert app.session_state['messages'][0]['text'] == '기존 질문 보존 확인'
    document_tabs = [item.label for item in app.tabs]
    app.button(key='santafe_menu_dashboard').click().run()
    assert not app.exception, [item.value for item in app.exception]
    assert app.session_state['santafe_active_view'] == 'dashboard'
    dashboard_tabs = [item.label for item in app.tabs]
    assert 'M0~M9 진행' in dashboard_tabs and '추가 30문항 평가' in dashboard_tabs
    assert app.session_state['conversation_id'] == 'presentation-verification-session'
    assert app.session_state['messages'][0]['text'] == '기존 질문 보존 확인'
    app.button(key='santafe_menu_document').click().run()
    assert not app.exception, [item.value for item in app.exception]
    assert app.session_state['santafe_active_view'] == 'document'
    assert NETWORK_ATTEMPTS == []
    report = {'passed':True, 'document_tabs':document_tabs, 'dashboard_tabs':dashboard_tabs,
              'network_attempts':len(NETWORK_ATTEMPTS), 'conversation_preserved':True,
              'download_labels':[item.label for item in app.get('download_button')]}
    (Path(__file__).parent / 'ui_verification.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    verify()
