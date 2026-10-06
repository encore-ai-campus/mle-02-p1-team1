"""뒤로가기 확인·취소·진행 중 답변 복구를 외부 호출 없이 검증합니다."""
from concurrent.futures import Future
from pathlib import Path
from queue import Queue
import unittest
from unittest.mock import Mock

from streamlit.testing.v1 import AppTest
from car_search_rag.anna_rag.chatbot.navigation import detach_chat
from car_search_rag.casper_manual.src.rag import CasperBackend


def setup_app():
    backend = CasperBackend(Mock())
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'))
    app.session_state['active_vehicle'] = 'casper'
    app.session_state['conversation_id'] = backend.start_session()
    app.session_state['vehicle_backend_casper'] = backend
    app.session_state['messages'] = []
    return app, backend


class ChatExitTests(unittest.TestCase):
    def test_empty_chat_returns_without_confirmation(self):
        app, backend = setup_app()
        app.run().button(key='back_to_vehicles').click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertIsNone(app.session_state['active_vehicle'])
        self.assertFalse(any(b.key == 'confirm_leave_chat' for b in app.button))
        self.assertTrue(any('landing-return' in m.value for m in app.markdown))

    def test_cancel_preserves_session_confirm_clears_view(self):
        app, backend = setup_app()
        messages = [{'role': 'user', 'text': '질문', 'ui_id': 'one_user'}]
        app.session_state['messages'] = messages
        session = app.session_state['conversation_id']
        app.run().button(key='back_to_vehicles').click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(app.session_state['confirm_chat_exit'])
        self.assertEqual(app.session_state['messages'], messages)
        app.button(key='keep_chat').click().run()
        self.assertEqual(app.session_state['conversation_id'], session)
        self.assertEqual(app.session_state['messages'], messages)
        self.assertFalse(app.session_state['confirm_chat_exit'])
        app.button(key='back_to_vehicles').click().run()
        app.button(key='confirm_leave_chat').click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertIsNone(app.session_state['active_vehicle'])
        self.assertEqual(app.session_state['messages'], [])
        self.assertTrue(any(b.key == 'car_casper' for b in app.button))

    def test_pending_reply_resumes_after_cancel_without_second_call(self):
        app, backend = setup_app()
        future = Future()
        packet = {'vehicle_id': 'casper', 'answer': {'text': '완료한 답변', 'status': 'answered'}, 'sources': []}
        app.session_state['pending'] = {'text': '질문', 'id': 'one'}
        app.session_state['messages'] = [{'role': 'user', 'text': '질문', 'ui_id': 'one_user'}]
        app.session_state['chat_job'] = {'id': 'one', 'future': future, 'events': Queue(), 'text': '', 'buffer': ''}
        app.session_state['confirm_chat_exit'] = True
        app.run()
        self.assertEqual(len(app.exception), 0)
        future.set_result(packet)
        app.button(key='keep_chat').click().run()
        self.assertEqual(len(app.exception), 0)
        backend.rag.ask_manual.assert_not_called()
        self.assertIsNone(app.session_state['pending'])
        self.assertEqual(app.session_state['messages'][-1]['packet'], packet)
        self.assertFalse(app.chat_input[0].disabled)

    def test_leaving_detaches_running_reply(self):
        future = Future()
        future.set_running_or_notify_cancel()
        state = {'active_vehicle': 'casper', 'conversation_id': 'old',
                 'messages': [{'role': 'user', 'text': '질문'}], 'pending': {'id': 'one'},
                 'chat_job': {'future': future}, 'confirm_chat_exit': True, 'exiting_chat': True}
        detach_chat(state)
        future.set_result({'answer': '늦게 도착한 답변'})
        self.assertNotIn('chat_job', state)
        self.assertIsNone(state['active_vehicle'])
        self.assertEqual(state['messages'], [])
        self.assertNotIn('confirm_chat_exit', state)


if __name__ == '__main__':
    unittest.main()
