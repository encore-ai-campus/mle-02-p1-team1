"""연속 전송·재실행 시 이전 답변이 사용자 말풍선으로 섞이지 않는지 확인합니다."""
from pathlib import Path
import unittest
from unittest.mock import Mock

from streamlit.testing.v1 import AppTest

from car_search_rag.casper_manual.src.rag import CasperBackend


class MessageLayoutTests(unittest.TestCase):
    def test_consecutive_turns_keep_sources_in_assistant_messages(self):
        rag = Mock()
        rag.ask_manual.side_effect = lambda question, top_k: {
            'answer': f'{question}에 대한 답변',
            'sources': [{'citation_id': 1, 'source_title': '설명서',
                         'page_start': 18, 'page_end': 18, 'chunk_text': '근거 본문'}],
        }
        backend = CasperBackend(rag)
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'))
        app.session_state['active_vehicle'] = 'casper'
        app.session_state['conversation_id'] = backend.start_session()
        app.session_state['vehicle_backend_casper'] = backend
        app.run()
        for number, question in enumerate(('첫 질문', '이미지 보여줘', '다음 질문'), 1):
            app.chat_input[0].set_value(question).run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(len(app.chat_message), number * 2)
            self.assertEqual(len(app.expander), number)
            for index, message in enumerate(app.chat_message):
                if index % 2 == 0:
                    self.assertEqual(len(message.get('expander')), 0)
                    self.assertEqual(len(message.get('markdown')), 1)
                else:
                    self.assertEqual(len(message.get('expander')), 1)
            # 전송이 없는 재실행에서도 마지막 답변을 중복 표시하지 않습니다.
            app.run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(len(app.chat_message), number * 2)
            self.assertEqual(len(app.expander), number)
        self.assertEqual(rag.ask_manual.call_count, 3)


if __name__ == '__main__':
    unittest.main()
