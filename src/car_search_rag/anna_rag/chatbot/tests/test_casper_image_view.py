"""외부 검색·API 호출 없이 캐스퍼 이미지 계약과 Streamlit 표시를 확인합니다."""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest

from car_search_rag.anna_rag.chatbot.casper_image_view import (
    collect_casper_images, render_casper_images,
)
from car_search_rag.casper_manual.src.rag import CasperBackend, ManualRAG


def image_result():
    return {
        'answer': '잠금을 해제하세요. [그림 2]를 확인하세요. [1]',
        'image_input_count': 1,
        'image_notice': '일부 그림은 답변 모델에 전달하지 못했습니다.',
        'sources': [
            {'citation_id': 1, 'source_title': '충전', 'document_name': 'CASPER.pdf',
             'page_start': 18, 'page_end': 19, 'chunk_text': '충전 설명', 'images': [
                 {'image_id': 'same', 'url': 'https://example.com/a.png?token=one',
                  'caption': '충전구', 'pdf_page': 18, 'used_in_answer': False},
                 {'image_id': 'reference', 'url': 'https://example.com/b.png',
                  'caption': '참고 설명', 'pdf_page': 19, 'used_in_answer': False},
             ]},
            {'citation_id': 2, 'source_title': '잠금 해제', 'document_name': 'CASPER.pdf',
             'page_start': 18, 'page_end': 18, 'chunk_text': '잠금 설명', 'images': [
                 {'image_id': 'same', 'url': 'https://example.com/a.png?token=two',
                  'caption': '충전구', 'pdf_page': 18, 'used_in_answer': True,
                  'answer_image_label': '[그림 2]'},
             ]},
        ],
    }


class CasperImageTests(unittest.TestCase):
    def test_deduplicates_by_id_and_merges_later_label_without_mutation(self):
        result = image_result()
        original = deepcopy(result)
        images = collect_casper_images(result)
        self.assertEqual(len(images), 2)
        self.assertEqual(images[0]['citation_ids'], [1, 2])
        self.assertEqual(images[0]['answer_image_labels'], ['[그림 2]'])
        self.assertTrue(images[0]['used_in_answer'])
        self.assertEqual(images[0]['pdf_page'], 18)
        self.assertEqual(images[1]['answer_image_labels'], [])
        self.assertEqual(result, original)

    def test_preserves_all_labels_for_one_image(self):
        result = image_result()
        result['sources'][0]['images'][0]['answer_image_label'] = '[그림 1]'
        images = collect_casper_images(result)
        self.assertEqual(images[0]['answer_image_labels'], ['[그림 1]', '[그림 2]'])
        self.assertEqual(len(images), 2)

    def test_same_source_does_not_repeat_citation(self):
        result = image_result()
        result['sources'][0]['images'] *= 2
        self.assertEqual(collect_casper_images(result)[0]['citation_ids'], [1, 2])

    def test_old_empty_and_nullable_responses(self):
        for result in ({}, {'sources': []}, {'sources': None},
                       {'sources': [{'citation_id': 1}]}, {'sources': [{'images': None}]}):
            with self.subTest(result=result), patch(
                    'car_search_rag.anna_rag.chatbot.casper_image_view.st') as ui:
                self.assertEqual(collect_casper_images(result), [])
                render_casper_images(result)
                ui.image.assert_not_called()
                ui.caption.assert_not_called()

    def test_missing_url_can_be_completed_from_duplicate(self):
        result = image_result()
        result['sources'][0]['images'][0].pop('url')
        self.assertEqual(collect_casper_images(result)[0]['url'],
                         'https://example.com/a.png?token=two')

    def test_invalid_url_does_not_get_read_as_local_file(self):
        result = {'sources': [{'images': [{'image_id': 'bad', 'url': '/private/local.png'}]}]}
        with patch('car_search_rag.anna_rag.chatbot.casper_image_view.st') as ui:
            render_casper_images(result)
            ui.image.assert_not_called()
            self.assertIn('주소를 확인하지 못했어요', ui.caption.call_args.args[0])

    def test_image_error_does_not_abort_remaining_images(self):
        with patch('car_search_rag.anna_rag.chatbot.casper_image_view.st') as ui:
            ui.image.side_effect = [RuntimeError('render failed'), None]
            render_casper_images(image_result())
            self.assertEqual(ui.image.call_count, 2)
            self.assertTrue(any('표시하지 못했어요' in c.args[0] for c in ui.caption.call_args_list))

    def test_existing_backend_preserves_image_contract_and_cached_reply(self):
        result = image_result()
        backend = CasperBackend(Mock(ask_manual=Mock(return_value=result)))
        session = backend.start_session()
        packet = backend.chat(session, '충전구 잠금 해제', request_id='one')
        self.assertEqual(packet['native_result']['sources'], result['sources'])
        self.assertEqual(packet['native_result']['image_input_count'], 1)
        self.assertEqual(backend.chat(session, '충전구 잠금 해제', request_id='one'), packet)
        with patch('car_search_rag.anna_rag.chatbot.casper_image_view.st') as ui:
            render_casper_images(packet)
            self.assertEqual(ui.image.call_count, 2)
            captions = [call.args[0] for call in ui.caption.call_args_list]
            self.assertTrue(any('[그림 2]' in text and '[1] · [2]' in text for text in captions))
            self.assertIn(result['image_notice'], captions)

    def test_notice_is_visible_even_without_images(self):
        with patch('car_search_rag.anna_rag.chatbot.casper_image_view.st') as ui:
            render_casper_images({'image_notice': '이미지를 가져오지 못했어요.', 'sources': []})
            ui.caption.assert_called_once_with('이미지를 가져오지 못했어요.')
            ui.image.assert_not_called()

    def test_latest_rag_image_labels_reach_gallery_unchanged(self):
        # 실제 최신 ask_manual을 실행하되 DB·임베딩·LLM만 가짜 응답으로 대체합니다.
        rag = ManualRAG(Mock(), Mock(), Mock())
        chunks = image_result()['sources']
        for index, chunk in enumerate(chunks):
            chunk['chunk_id'] = f'chunk-{index}'
        rag.search_manual = Mock(return_value=chunks)
        rag.attach_source_images = Mock(return_value=None)
        rag.client.responses.create.return_value.output_text = '충전구를 확인하세요. [그림 1] [1]'
        backend = CasperBackend(rag)
        packet = backend.chat(backend.start_session(), '충전구는 어디에 있어?')
        result = packet['native_result']
        self.assertEqual(result['image_input_count'], 2)
        images = collect_casper_images(result)
        self.assertEqual(len(images), 2)
        self.assertEqual(images[0]['answer_image_labels'], ['그림 1'])
        self.assertEqual(images[1]['answer_image_labels'], ['그림 2'])
        self.assertEqual(images[0]['citation_ids'], [1, 2])
        self.assertTrue(all(image['used_in_answer'] for image in images))

    def test_streamlit_initial_and_history_render(self):
        script = '''
import streamlit as st
from car_search_rag.anna_rag.chatbot.answer_view import render_answer
from car_search_rag.anna_rag.chatbot.casper_image_view import render_casper_images
packet = st.session_state['packet']
with st.chat_message('assistant'):
    render_answer(packet['answer']['text'])
    render_casper_images(packet)
'''
        result = image_result()
        app = AppTest.from_string(script)
        app.session_state['packet'] = {'vehicle_id': 'casper', 'native_result': result,
                                      'answer': {'text': result['answer']}}
        for _ in range(2):
            app.run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(len(app.get('image')), 2)
            self.assertIn('[그림 2]', app.markdown[0].value)
            self.assertTrue(any('[그림 2]' in c.value for c in app.caption))
            self.assertFalse(any('[그림 1]' in c.value for c in app.caption))
        app.session_state['packet'] = {'answer': {'text': '이미지 없는 기존 답변'},
                                      'native_result': {'sources': []}}
        app.run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.get('image')), 0)
        self.assertEqual(app.markdown[0].value, '이미지 없는 기존 답변')

    def test_actual_team_chat_page_renders_images_and_sources(self):
        backend = CasperBackend(Mock(ask_manual=Mock(return_value=image_result())))
        session = backend.start_session()
        packet = backend.chat(session, '충전구 잠금 해제', request_id='ui-test')
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'))
        for key, value in {
            'active_vehicle': 'casper', 'conversation_id': session,
            'vehicle_backend_casper': backend,
            'messages': [{'role': 'assistant', 'packet': packet, 'images': [], 'ui_id': 'test'}],
        }.items():
            app.session_state[key] = value
        app.run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.get('image')), 2)
        self.assertTrue(any('[그림 2]' in c.value for c in app.caption))
        self.assertTrue(any(e.label == '검색에 사용한 설명서' for e in app.expander))
        self.assertTrue(any('잠금을 해제하세요.' in m.value for m in app.markdown))


if __name__ == '__main__':
    unittest.main()
