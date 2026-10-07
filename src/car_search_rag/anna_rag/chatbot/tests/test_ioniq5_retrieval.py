"""검색 경계·캐시·동시 요청을 외부 API/DB 호출 없이 확인합니다."""
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import Mock

from langchain_core.documents import Document
from car_search_rag.anna_rag.chatbot.ioniq5_retrieval import IoniqHybridSearch, reciprocal_rank_fusion


class HybridSearchTests(unittest.TestCase):
    def setUp(self):
        self.a = Document(id='a', page_content='충전 커넥터 비상 해제 케이블', metadata={})
        self.b = Document(id='b', page_content='와이퍼 작동 유리창 빗물', metadata={})
        self.loader = Mock(return_value=[self.b, self.a])
        self.dense = Mock(return_value=[(self.b, .2)])
        self.search = IoniqHybridSearch(self.loader, self.dense, top_k=2)

    def test_lexical_only_candidate_keeps_its_distinct_score(self):
        hits = self.search.search('충전 커넥터', [1])
        self.assertEqual({h.document.id for h in hits}, {'a', 'b'})
        lexical = next(h for h in hits if h.document.id == 'a')
        self.assertIsNone(lexical.cosine_distance)
        self.assertIsNone(lexical.cosine_rank)
        self.assertEqual(lexical.tfidf_rank, 1)
        self.assertGreater(lexical.tfidf_similarity, 0)

    def test_empty_lexical_overlap_does_not_pad_arbitrary_documents(self):
        hits = self.search.search('!!!', [1])
        self.assertEqual([h.document.id for h in hits], ['b'])
        self.assertIsNone(hits[0].tfidf_rank)

    def test_concurrent_queries_build_once_without_shared_query_scores(self):
        with ThreadPoolExecutor(max_workers=3) as pool:
            first, second, third = list(pool.map(
                lambda q: self.search.search(q, [1]), ['충전 커넥터', '와이퍼', '!!!']))
        self.loader.assert_called_once()
        self.assertIn('a', [h.document.id for h in first])
        self.assertEqual([h.document.id for h in second], ['b'])
        self.assertEqual([h.document.id for h in third], ['b'])

    def test_changed_dense_content_refreshes_cached_index(self):
        self.search.warmup()
        new_b = Document(id='b', page_content='배터리 관리', metadata={})
        self.loader.return_value = [self.a, new_b]
        self.dense.return_value = [(new_b, .1)]
        hits = self.search.search('배터리', [1])
        self.assertEqual(self.loader.call_count, 2)
        self.assertEqual(hits[0].document.page_content, '배터리 관리')

    def test_repeated_ids_only_receive_one_vote_per_branch(self):
        ids, scores = reciprocal_rank_fusion(['b','b','a'], ['a','b'])
        self.assertEqual(ids, ['a','b'])
        self.assertEqual(scores['a'], scores['b'])


if __name__ == '__main__':
    unittest.main()
