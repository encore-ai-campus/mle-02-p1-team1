"""산타페 고유 검색·생성 단계와 접속별 기록을 외부 호출 없이 검증합니다."""
import unittest
from unittest.mock import Mock, patch
from car_search_rag.zzong_santafe_lag.app import SantafeBackend, prepare_entry


def fake_service():
    service = Mock()
    service.evidence_service = None  # PDF 저장 정보가 없는 응답을 재현합니다.
    service.prepare_evidence.side_effect = lambda q, top_k: {
        'question': q, 'answer': '원문 발췌', 'status': 'evidence_excerpt',
        'sources': [{'citation_id':1, 'label':'1', 'title':'제목', 'source_pages':[44], 'quote':'근거'}],
        'images': [{'public_url':'https://example.com/car.png', 'pdf_page_number':44,
                    'descriptions':[{'description':'그림 설명'}]}]}
    service.preview.return_value = {'ready_for_generation':True, 'reason':''}
    service.settings.return_value = {'api_key_configured':True}
    service.generate.side_effect = lambda e: dict(e, answer='생성 답변',status='generated_answer')
    return service


class SantafeTests(unittest.TestCase):
    def test_search_does_not_generate_or_forward_history(self):
        service = fake_service()
        backend = SantafeBackend(service)
        sid = backend.start_session()
        packet = backend.chat(sid,'첫 질문',request_id='1')
        backend.chat(sid,'두번째 질문')
        service.generate.assert_not_called()
        service.prepare_evidence.assert_called_with('두번째 질문',top_k=5)
        self.assertEqual(packet['native_result']['answer'], '원문 발췌')
        self.assertIn('설명서에서 관련 자료를 찾았습니다.', packet['answer']['text'])
        self.assertIn('답변 정리하기', packet['answer']['text'])
        self.assertEqual(packet['actions'][0]['id'],'generate')
        backend.perform_action(sid,packet,'generate')
        again = backend.perform_action(sid,packet,'generate')
        self.assertEqual(again['native_result']['answer'], '생성 답변')
        self.assertEqual(again['answer']['text'], '### 답변\n\n생성 답변')
        self.assertEqual(again['actions'],[])
        service.generate.assert_called_once()
        self.assertEqual(backend.get_related_images(again)[0]['pdf_page'],44)

    def test_history_is_bounded_and_sessions_are_isolated(self):
        service = fake_service()
        backend = SantafeBackend(service)
        a,b=backend.start_session(),backend.start_session()
        for i in range(12): backend.chat(a,str(i),request_id=str(i))
        self.assertEqual(len(backend.sessions[a]),10)
        self.assertEqual(backend.sessions[b],[])
        backend.chat(a,'11',request_id='11')
        self.assertEqual(service.prepare_evidence.call_count,12)
        backend.end_session(a)
        self.assertFalse(backend.is_session_active(a))
        self.assertTrue(backend.is_session_active(b))

    def test_unreviewed_evidence_has_no_generation_button(self):
        service = fake_service()
        service.preview.return_value={'ready_for_generation':False,'reason':'검토 필요'}
        backend=SantafeBackend(service)
        packet=backend.chat(backend.start_session(),'질문')
        self.assertEqual(packet['actions'],[])
        self.assertIn('검토 필요',packet['notices'])
        service.generate.assert_not_called()

    def test_failed_generation_not_retried(self):
        service=fake_service()
        service.generate.side_effect=RuntimeError('private error')
        backend=SantafeBackend(service); sid=backend.start_session()
        packet=backend.chat(sid,'질문')
        result=backend.perform_action(sid,packet,'generate')
        backend.perform_action(sid,packet,'generate')
        self.assertEqual(result['answer']['text'],'원문 발췌')
        self.assertNotIn('private error',str(result))
        service.generate.assert_called_once()

if __name__=='__main__': unittest.main()
