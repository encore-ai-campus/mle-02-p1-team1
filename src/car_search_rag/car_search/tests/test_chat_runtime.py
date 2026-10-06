"""네트워크 없이 두 화면이 공유하는 Agent 실행 계약을 검증합니다."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from app_kbj import prepare_reply, _pin_vehicle


class FakeService:
    def __init__(self):
        self.sql_session=SimpleNamespace(database_manager=Mock())
        self.select_relevant_images=Mock(return_value=[])
        self.search_calls=[]

    def ask_manual_with_sources(self,car_brand_eng_nm,car_eng_nm,car_model_yr,question,**kwargs):
        self.search_calls.append((car_brand_eng_nm,car_eng_nm,car_model_yr,question))
        return '검색 결과'


class RuntimeTests(unittest.TestCase):
    def manual(self):
        manual=Mock()
        manual.service=FakeService()
        manual.download_html=None
        manual.ask_with_sources_stream.return_value=SimpleNamespace(
            chunks=iter(['초안']),answer='Agent 최종 답변',error=None,search_results=())
        return manual

    def test_uses_agent_and_latest_six_messages_and_ten_results(self):
        manual=self.manual()
        history=[{'role':'user' if i%2==0 else 'assistant','content':str(i)} for i in range(12)]
        result=prepare_reply('질문',history,manual_factory=lambda:manual)
        self.assertEqual(list(result.chunks),['초안'])
        manual.ask_with_sources_stream.assert_called_once_with(
            car_brand_eng_nm='hyundai',car_eng_nm='sonata',car_model_yr=2026,
            question='질문',limit=10,conversation_history=history[-6:])
        self.assertEqual(result.answer,'Agent 최종 답변')
        manual.service.sql_session.database_manager.close.assert_called_once()

    def test_full_history_export_includes_images(self):
        manual=self.manual();manual.prepare_history_html.return_value='<html>전체 기록</html>'
        history=[{'role':'assistant','content':str(i),'images':[{'url':'https://example.com/a.png'}]} for i in range(8)]
        result=prepare_reply('대화 기록 다운로드',history,manual_factory=lambda:manual)
        self.assertEqual(list(result.chunks),[])
        passed=manual.prepare_history_html.call_args.args[0]
        self.assertEqual(passed[:-1],history)
        self.assertEqual(passed[-1]['content'],'대화 기록 다운로드')
        manual.ask_with_sources_stream.assert_not_called()
        self.assertEqual(result.download_html,'<html>전체 기록</html>')

    def test_agent_selected_download_tool_output_is_forwarded(self):
        manual=self.manual();manual.download_html='<html>도구 결과</html>'
        result=prepare_reply('내 대화를 파일로 줘',[],manual_factory=lambda:manual)
        list(result.chunks)
        manual.ask_with_sources_stream.assert_called_once()
        self.assertEqual(result.download_html,'<html>도구 결과</html>')

    def test_tool_cannot_search_another_vehicle(self):
        service=FakeService();_pin_vehicle(service,('hyundai','sonata',2026))
        with self.assertRaises(ValueError):
            service.ask_manual_with_sources('hyundai','ioniq5',2027,'질문')
        self.assertEqual(service.search_calls,[])
        self.assertEqual(service.ask_manual_with_sources('hyundai','sonata',2026,'질문'),'검색 결과')

    def test_partial_stream_failure_remains_error(self):
        manual=self.manual()
        manual.ask_with_sources_stream.return_value.error=RuntimeError('실패')
        result=prepare_reply('질문',[],manual_factory=lambda:manual);list(result.chunks)
        self.assertIsInstance(result.error,RuntimeError)


if __name__=='__main__':unittest.main()
