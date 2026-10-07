"""검색 변경 시 후보·프롬프트·실패 복구·대화 간 격리를 확인합니다."""
import ast
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from langchain_core.documents import Document
from car_search_rag.anna_rag.chatbot.ioniq5_keyword_search import IoniqKeywordRerankSearch
from car_search_rag.anna_rag.chatbot import ioniq5_search_policy as policy


def message(value):
    return SimpleNamespace(content=json.dumps(value),usage_metadata={},response_metadata={})


class Keywords:
    def invoke(self, messages):
        return message({'phrases':[messages[-1][1]],'terms':[]})


class Ranker:
    def invoke(self, messages):
        data=json.loads(messages[-1][1])
        return message({'ranking':[{'candidate_id':d['candidate_id'],'relevance_score':100-i}
            for i,d in enumerate(reversed(data['candidates']))]})


class SearchTests(unittest.TestCase):
    def searcher(self,keyword_model=None,reranker_model=None):
        def docs(q):
            return [Document(id=f'{q}{i:02}',page_content=f'{q} 본문 {i}',metadata={'pdf_pages':[i+1]}) for i in range(12)]
        def dense(q,k,vector):return [1.0],[(d,.1+i/100) for i,d in enumerate(docs(q)[:k])]
        def lexical(phrases,terms,k):return [(d,3) for d in docs(phrases[0])[8:]]
        return IoniqKeywordRerankSearch(lambda:[d.id for q in ['A','B'] for d in docs(q)],
            dense,lexical,keyword_model=keyword_model or Keywords(),reranker_model=reranker_model or Ranker())

    def test_union_deduplicates_and_lexical_only_documents_can_win(self):
        result=self.searcher().search('A')
        self.assertEqual([h.document.id for h in result.hits],['A11','A10','A09','A08','A07'])
        self.assertEqual(result.metadata['merged_candidate_count'],12)
        self.assertIsNone(result.hits[0].cosine_distance)
        self.assertEqual(result.hits[0].keyword_rank,4)
        self.assertEqual(result.hits[2].cosine_rank,10)

    def test_failed_keyword_still_reranks_vector_candidates(self):
        class Broken:
            def invoke(self,*a):raise TimeoutError('secret must not be stored')
        result=self.searcher(keyword_model=Broken()).search('A')
        self.assertTrue(result.metadata['keyword_branch_failed'])
        self.assertEqual(result.metadata['keyword_fallback_reason'],'TimeoutError')
        self.assertTrue(result.metadata['rerank']['success'])
        self.assertEqual(result.hits[0].document.id,'A09')

    def test_invalid_rerank_retries_then_preserves_vector_order(self):
        class Broken:
            calls=0
            def invoke(self,*a):
                self.calls+=1
                return message({'ranking':[{'candidate_id':'unknown','relevance_score':100}]})
        model=Broken()
        with patch.object(policy.time,'sleep'):
            result=self.searcher(reranker_model=model).search('A')
        self.assertEqual(model.calls,2)
        self.assertFalse(result.metadata['rerank']['success'])
        self.assertEqual([h.document.id for h in result.hits],[f'A{i:02}' for i in range(5)])

    def test_concurrent_questions_do_not_share_candidates_or_metadata(self):
        search=self.searcher()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(search.search,['A','B']))
        for q,r in zip(['A','B'],results):
            self.assertEqual(r.metadata['keyword_phrases'],[q])
            self.assertTrue(all(h.document.id.startswith(q) for h in r.hits))

    def test_evaluated_prompts_and_rerank_policy_are_preserved(self):
        snapshot=Path(__file__).resolve().parents[2]/'evaluation/sonata_transfer_v1/sonata_service_snapshot.py'
        tree=ast.parse(snapshot.read_text());current=ast.parse(Path(policy.__file__).read_text())
        for name in ['KEYWORD_EXTRACTION_PROMPT','RERANKER_SYSTEM_PROMPT']:
            assignment=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets))
            self.assertEqual(getattr(policy,name),ast.literal_eval(assignment.value))
        original_class=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='CarManualSearchService')
        current_class=next(n for n in current.body if isinstance(n,ast.ClassDef))
        for name in ['_chunk_identity','rerank_search_results']:
            original=next(n for n in original_class.body if isinstance(n,ast.FunctionDef) and n.name==name)
            copied=next(n for n in current_class.body if isinstance(n,ast.FunctionDef) and n.name==name)
            self.assertEqual(ast.dump(original),ast.dump(copied))


if __name__=='__main__':unittest.main()
