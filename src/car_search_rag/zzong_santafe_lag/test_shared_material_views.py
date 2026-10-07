"""공통 앱의 싼타페 자료 전환과 다른 차종 메뉴를 외부 호출 없이 확인합니다."""
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / 'anna_rag/chatbot/app.py'


def setup_app(vehicle='santafe', view='chat'):
    """가짜 접속을 넣어 실제 DB·API 없이 공통 화면을 실행합니다."""
    app = AppTest.from_file(str(APP), default_timeout=30)
    backend = Mock()
    backend.is_session_active.return_value = True
    app.session_state['active_vehicle'] = vehicle
    app.session_state['conversation_id'] = 'test-session'
    app.session_state[f'vehicle_backend_{vehicle}'] = backend
    app.session_state['messages'] = [{'role': 'user', 'text': '보존할 질문', 'ui_id': 'saved'}]
    app.session_state['santafe_active_view'] = view
    return app, backend


class MaterialViewsTests(unittest.TestCase):
    """실제 저장 자료의 표시·메뉴 이동·차종별 상태 분리를 검사합니다."""

    def test_santafe_round_trip_preserves_chat(self):
        app, backend = setup_app()
        app.run()
        for key, view in [('santafe_menu_dashboard', 'dashboard'), ('santafe_menu_document', 'document')]:
            app.button(key=key).click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.session_state['santafe_active_view'], view)
            self.assertEqual(app.session_state['conversation_id'], 'test-session')
            self.assertEqual(app.session_state['messages'][0]['text'], '보존할 질문')
            self.assertGreater(len(app.tabs), 0)
            if view == 'dashboard':
                self.assertIn('추가 30문항 평가', [tab.label for tab in app.tabs])
            else:
                self.assertIn('싼타페 작업 Document', [title.value for title in app.title])
            app.button(key='santafe_material_back').click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.session_state['santafe_active_view'], 'chat')
            self.assertEqual(len(app.chat_input), 1)
        backend.chat.assert_not_called()
        backend.start_session.assert_not_called()

    def test_material_view_does_not_initialize_backend(self):
        app, _ = setup_app(view='dashboard')
        app.session_state['conversation_id'] = None
        with patch('car_search_rag.anna_rag.chatbot.registry.load_backend', side_effect=AssertionError('자료 조회 중 백엔드 생성')):
            app.run()
        self.assertEqual(len(app.exception), 0)
        self.assertIsNone(app.session_state['conversation_id'])

    def test_other_vehicle_menus_remain_separate(self):
        for vehicle in ('ioniq5', 'sonata', 'casper'):
            with self.subTest(vehicle=vehicle):
                app, backend = setup_app(vehicle, view='document')
                app.run()
                self.assertEqual(len(app.exception), 0)
                self.assertFalse(any(button.key == 'santafe_menu_dashboard' for button in app.button))
                self.assertTrue(any(button.key == 'menu_data_dashboard' for button in app.button))
                self.assertEqual(len(app.chat_input), 1)
                self.assertEqual(app.session_state['active_vehicle'], vehicle)
                backend.chat.assert_not_called()


if __name__ == '__main__':
    unittest.main()
