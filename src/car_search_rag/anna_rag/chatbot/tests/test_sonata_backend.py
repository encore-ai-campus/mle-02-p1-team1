"""공통 화면은 Sonata runtime의 결과를 가공 없이 전달하는지 확인합니다."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from car_search_rag.anna_rag.chatbot import sonata_backend as backend
from car_search_rag.anna_rag.chatbot.registry import VEHICLES


class SonataAdapterTests(unittest.TestCase):
    def test_only_requested_vehicle_is_enabled(self):
        self.assertIsNotNone(VEHICLES['sonata'].module)
        self.assertIsNotNone(VEHICLES['ioniq5'].module)
        self.assertIsNone(VEHICLES['santafe'].module)
        self.assertIsNone(VEHICLES['casper'].module)

    def test_adapter_delegates_to_runtime_and_preserves_final_answer(self):
        history = [{'role':'user','content':'이전 질문'}]
        reply = SimpleNamespace(chunks=iter(['검색 초안']), answer='Agent 최종 답변', error=None,
            sources=[{'page_no':25,'chunk_no':1}], images=[], download_html='<html>기록</html>')
        events=[]
        with patch.object(backend,'prepare_reply',return_value=reply) as prepare:
            packet=backend.answer_question('질문',history,lambda k,v:events.append((k,v)))
        prepare.assert_called_once_with('질문',history,vehicle=('hyundai','sonata',2026))
        self.assertEqual(packet['answer']['text'],'Agent 최종 답변')
        self.assertEqual(events,[('token','검색 초안')])
        self.assertEqual(packet['sources'][0]['pdf_pages'],[25])
        self.assertEqual(packet['download_html'],'<html>기록</html>')

    def test_greeting_without_sources_is_not_no_evidence(self):
        reply=SimpleNamespace(chunks=iter(()),answer='안녕하세요',error=None,sources=[],images=[],download_html=None)
        with patch.object(backend,'prepare_reply',return_value=reply):
            packet=backend.answer_question('안녕',[])
        self.assertEqual(packet['answer']['status'],'answered')

    def test_images_use_completed_runtime_output(self):
        self.assertEqual(backend.get_related_images({'vehicle_id':'ioniq5'}),[])
        images=backend.get_related_images({'vehicle_id':'sonata','images':[
            {'url':'https://example.com/image.png','page_no':25,'description':'라벨'}]})
        self.assertEqual(images,[{'data':'https://example.com/image.png','pdf_page':25,'caption':'라벨'}])


if __name__=='__main__':unittest.main()
