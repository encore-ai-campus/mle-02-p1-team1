"""캐스퍼의 기존 RAG 위임과 기록 분리를 외부 호출 없이 확인합니다."""
import unittest
from unittest.mock import Mock
from car_search_rag.casper_manual.src.rag import CasperBackend, DEFAULT_TOP_K


def fake_rag():
    rag=Mock()
    rag.ask_manual.side_effect=lambda q,top_k:{'question':q,'answer':'캐스퍼 답변 [1]',
        'sources':[{'citation_id':1,'source_title':'충전','document_name':'CASPER.pdf',
                    'page_start':18,'page_end':19,'chunk_text':'캐스퍼 근거'}]}
    return rag


class CasperTests(unittest.TestCase):
    def test_calls_original_rag_without_other_car_or_history(self):
        rag=fake_rag(); backend=CasperBackend(rag); sid=backend.start_session()
        packet=backend.chat(sid,'질문',request_id='a')
        backend.chat(sid,'다음 질문',request_id='b')
        rag.ask_manual.assert_called_with('다음 질문',top_k=DEFAULT_TOP_K)
        self.assertEqual(packet['answer']['text'],'캐스퍼 답변 [1]')
        self.assertEqual(packet['sources'][0]['pdf_pages'],[18,19])
        self.assertEqual(backend.get_related_images(packet),[])
        self.assertEqual(backend.chat(sid,'질문',request_id='a'),packet)
        self.assertEqual(rag.ask_manual.call_count,2)

    def test_isolated_sessions_and_reset(self):
        rag=fake_rag(); one,two=CasperBackend(rag),CasperBackend(rag)
        a,b=one.start_session(),two.start_session()
        one.chat(a,'내 질문')
        self.assertEqual(two.sessions[b],[])
        self.assertFalse(two.is_session_active(a))
        one.end_session(a)
        self.assertFalse(one.is_session_active(a))
        self.assertEqual(one.sessions[one.start_session()],[])

    def test_failure_does_not_save_success(self):
        rag=fake_rag();rag.ask_manual.side_effect=RuntimeError('failed')
        backend=CasperBackend(rag);sid=backend.start_session()
        with self.assertRaises(RuntimeError):backend.chat(sid,'질문')
        self.assertEqual(backend.sessions[sid],[])

if __name__=='__main__': unittest.main()
