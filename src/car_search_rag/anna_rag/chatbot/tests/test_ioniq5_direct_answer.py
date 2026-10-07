"""DB/API 없이 검색 실행 순서·실패 처리·출처·스트림을 검증합니다."""
import ast
import json
from pathlib import Path
import re
from threading import Lock
from time import perf_counter
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from langchain_core.tools import tool
import tiktoken


class DirectAnswerTests(unittest.TestCase):
    def setUp(self):
        # 백엔드의 모듈 초기화는 DB를 열므로 실제 함수/프롬프트만 로드합니다.
        path = Path(__file__).resolve().parents[1] / 'ioniq5_backend.py'
        tree = ast.parse(path.read_text())
        functions = {'empty_packet', 'clarification_answer', 'make_search_tool',
                     'run_manual_agent', 'agent_pipeline'}
        constants = {'system_prompt', 'agent_system_prompt', 'no_evidence_answer'}
        nodes = [n for n in tree.body if
                 isinstance(n, ast.FunctionDef) and n.name in functions or
                 isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in constants for t in n.targets)]
        self.events = []
        self.rag = {'sources': [{'label': 'S1'}, {'label': 'P1'}], 'omitted_parents': [],
                    'evidence': '[S1] 근거', 'parent_context': '[P1] 조건과 경고',
                    'image_candidates': [{'image_id': 'img1'}]}
        self.model = Mock()
        self.model.stream.return_value = iter([SimpleNamespace(content='답변 '),
                                              SimpleNamespace(content=[{'type': 'text', 'text': '[S1]'}])])
        self.ns = dict(json=json, re=re, Lock=Lock, perf_counter=perf_counter, tool=tool,
                       encoding=tiktoken.get_encoding('cl100k_base'),
                       max_search_calls=1, input_token_budget=20000,
                       model=self.model, emit_ui_event=lambda *e: self.events.append(e),
                       prepare_rag=Mock(return_value=self.rag))
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), self.ns)

    def answer(self):
        return self.ns['run_manual_agent']('맥락을 반영한 질문',
                 {'intent': {'scope_question': '어떤 기능인가요?'}, 'timings': {'intent_seconds': .1}})

    def test_search_once_before_one_answer_call_preserves_evidence_and_images(self):
        def stream(messages):
            self.ns['prepare_rag'].assert_called_once_with('맥락을 반영한 질문')
            payload = json.loads(messages[1][1])
            self.assertEqual(payload['search_result']['parent_context'], self.rag['parent_context'])
            return iter([SimpleNamespace(content='답변 [S1]')])
        self.model.stream.side_effect = stream
        result = self.answer()
        self.model.stream.assert_called_once()
        self.assertEqual(result['answer']['status'], 'answered')
        self.assertEqual(result['image_candidates'], self.rag['image_candidates'])
        self.assertEqual(result['search_question'], '맥락을 반영한 질문')
        self.assertIn(('token', '답변 [S1]'), self.events)
        self.assertIn('answer_first_token_seconds', result['timings'])

    def test_unusable_evidence_never_calls_answer_model(self):
        for kind, expected in [('no_results', 'insufficient_evidence'),
                               ('parent_budget', 'needs_clarification'),
                               ('input_budget', 'needs_clarification'),
                               ('search_error', 'agent_error')]:
            with self.subTest(kind=kind):
                self.setUp()
                if kind == 'no_results': self.rag['sources'] = []
                if kind == 'parent_budget': self.rag['omitted_parents'] = ['missing']
                if kind == 'input_budget': self.ns['input_token_budget'] = 1
                if kind == 'search_error': self.ns['prepare_rag'].side_effect = TimeoutError('private value')
                result = self.answer()
                self.assertEqual(result['answer']['status'], expected)
                self.model.stream.assert_not_called()
                self.assertNotIn('private value', json.dumps(result))

    def test_invalid_citation_is_rejected(self):
        self.model.stream.return_value = iter([SimpleNamespace(content='답변 [S99]')])
        self.assertEqual(self.answer()['answer']['status'], 'invalid_citations')

    def test_stream_failure_does_not_become_success(self):
        def broken(messages):
            yield SimpleNamespace(content='미완성 ')
            raise TimeoutError('private value')
        self.model.stream.side_effect = broken
        result = self.answer()
        self.assertEqual(result['answer']['status'], 'agent_error')
        self.assertEqual(result['agent_error_type'], 'TimeoutError')

    def test_intent_still_reads_history_and_directly_dispatches_rewritten_question(self):
        history = ['이전 질문과 답변']
        decision = dict(action='search', search_question='맥락을 반영한 질문',
                        answering_clarification=False, scope_question='세부 기능은?')
        self.ns['check_conversation_intent'] = Mock(return_value=decision)
        result = self.ns['agent_pipeline'](dict(question='그건?', history=history, previous={}))
        self.ns['check_conversation_intent'].assert_called_once_with('그건?', history)
        self.ns['prepare_rag'].assert_called_once_with('맥락을 반영한 질문')
        self.assertEqual(result['answer']['status'], 'answered')

    def test_clarification_greeting_out_of_scope_skip_search(self):
        for action in ['clarify', 'greeting', 'out_of_scope']:
            self.ns['check_conversation_intent'] = Mock(return_value=dict(
                action=action, answering_clarification=False, clarification='어떤 기능인가요?'))
            self.ns['agent_pipeline'](dict(question='질문', history=[], previous={}))
        self.ns['prepare_rag'].assert_not_called()
        self.model.stream.assert_not_called()


if __name__ == '__main__':
    unittest.main()
