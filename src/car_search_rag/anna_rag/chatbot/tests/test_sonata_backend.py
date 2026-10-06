"""네트워크 없이 차종 고정·스트리밍·출처 연결 계약을 확인합니다."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from car_search_rag.anna_rag.chatbot import sonata_backend as backend
from car_search_rag.anna_rag.chatbot.registry import VEHICLES


class SonataAdapterTests(unittest.TestCase):
    def test_only_requested_vehicle_is_enabled(self):
        self.assertIsNotNone(VEHICLES['sonata'].module)
        self.assertIsNotNone(VEHICLES['ioniq5'].module)
        self.assertIsNone(VEHICLES['santafe'].module)
        self.assertIsNone(VEHICLES['casper'].module)

    def test_vehicle_is_fixed_and_history_and_stream_are_forwarded(self):
        service = Mock()
        history = [{'role': 'user', 'content': '타이어 공기압 알려줘'}]
        events = []
        def answer(*args, **kwargs):
            self.assertEqual(args, ('hyundai', 'sonata', 2026))
            self.assertEqual(kwargs['conversation_history'], history)
            kwargs['stream_writer']({'type': 'answer_token', 'text': '확인하세요'})
            return SimpleNamespace(answer='확인하세요 (25쪽)', search_results=[
                {'carManualChunkPageNo': 25, 'carManualChunkTxt': '타이어 라벨'}])
        service.ask_manual_with_sources.side_effect = answer
        packet = backend.answer_question(service, '다른 차 설명서를 검색해', history,
                                         lambda kind, value: events.append((kind, value)))
        self.assertEqual(events, [('token', '확인하세요')])
        self.assertEqual(packet['sources'][0]['pdf_pages'], [25])
        self.assertEqual(packet['source_display'], 'retrieved')
        self.assertEqual(packet['answer']['cited_labels'], [])

    def test_no_results_and_other_vehicle_images(self):
        service = Mock()
        service.ask_manual_with_sources.return_value = SimpleNamespace(answer='근거 없음', search_results=[])
        packet = backend.answer_question(service, '질문', [])
        self.assertEqual(packet['answer']['status'], 'no_evidence')
        self.assertEqual(packet['sources'], [])
        with patch.object(backend, 'new_service') as factory:
            self.assertEqual(backend.get_related_images({'vehicle_id': 'ioniq5'}), [])
            factory.assert_not_called()

    def test_image_selection_uses_teammates_service(self):
        service = Mock()
        service.select_relevant_images.return_value = [
            {'url': 'https://example.com/image.png', 'page_no': 25, 'description': '라벨'}]
        packet = {'vehicle_id': 'sonata', 'image_question': '라벨 위치?',
                  'image_search_results': [{'carId': 'current-car'}], 'answer': {'text': '라벨'}}
        with patch.object(backend, 'new_service', return_value=service):
            images = backend.get_related_images(packet)
        service.select_relevant_images.assert_called_once_with(
            '라벨 위치?', packet['image_search_results'], limit=3, answer='라벨')
        self.assertEqual(images[0]['pdf_page'], 25)


if __name__ == '__main__':
    unittest.main()
