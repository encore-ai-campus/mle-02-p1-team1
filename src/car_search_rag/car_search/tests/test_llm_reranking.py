"""Offline validation for production LLM reranking and Vector fallback."""

import json
import unittest
from types import SimpleNamespace

from car_search_rag.car_search.car_manual_search_service import CarManualSearchService


def rows():
    return [
        {
            "carManualChunkPageNo": page,
            "carManualChunkNo": chunk,
            "carManualChunkTxt": f"document {chunk}",
            "carId": "sonata-test",
        }
        for page, chunk in enumerate(range(100, 110), start=1)
    ]


def ranking(ids=None):
    ids = ids or [f"C{i:02d}" for i in range(1, 11)]
    return {"ranking": [{"candidate_id": item, "relevance_score": 100 - index} for index, item in enumerate(ids)]}


class FakeModel:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        if self.error:
            raise self.error
        content = self.response if isinstance(self.response, str) else json.dumps(self.response)
        return SimpleNamespace(
            content=content,
            usage_metadata={"input_tokens": 20, "output_tokens": 10},
            response_metadata={},
        )


class FakeEmbeddings:
    def embed_query(self, question):
        self.question = question
        return [0.1, 0.2]


class FakeRepository:
    def __init__(self, source):
        self.source = source
        self.kwargs = None

    def search_manual(self, **kwargs):
        self.kwargs = kwargs
        return self.source


def service(model):
    result = object.__new__(CarManualSearchService)
    result.reranker_model = model
    return result


class ProductionRerankingTests(unittest.TestCase):
    def test_success_sends_c_ids_and_maps_rows_without_mutation(self):
        source = rows()
        model = FakeModel(ranking([f"C{i:02d}" for i in range(10, 0, -1)]))
        result, metadata = service(model).rerank_search_results("question", source)

        sent = json.loads(model.calls[0][1][1])["candidates"]
        self.assertEqual([item["candidate_id"] for item in sent], [f"C{i:02d}" for i in range(1, 11)])
        self.assertEqual(sent[0], {"candidate_id": "C01", "page_no": 1, "chunk_id": 100, "text": "document 100"})
        self.assertEqual(result, list(reversed(source)))
        self.assertTrue(metadata["success"])
        self.assertEqual(metadata["input_tokens"], 20)
        self.assertEqual(metadata["output_tokens"], 10)
        self.assertEqual(metadata["candidate_mapping"][0], {"candidate_id": "C01", "page_no": 1, "chunk_id": 100})
        self.assertNotIn("candidate_id", source[0])

    def test_api_error_falls_back_to_vector_order_after_one_retry(self):
        source = rows()
        model = FakeModel(error=TimeoutError("timeout"))
        result, metadata = service(model).rerank_search_results("question", source)
        self.assertEqual(result, source)
        self.assertFalse(metadata["success"])
        self.assertEqual(metadata["request_count"], 2)
        self.assertEqual(metadata["retry_count"], 1)
        self.assertIn("TimeoutError", metadata["fallback_reason"])

    def test_malformed_json_falls_back(self):
        source = rows()
        result, metadata = service(FakeModel(response="not json")).rerank_search_results("q", source)
        self.assertEqual(result, source)
        self.assertIn("JSONDecodeError", metadata["fallback_reason"])

    def test_missing_duplicate_or_bad_ids_fall_back(self):
        source = rows()
        cases = [
            ranking([f"C{i:02d}" for i in range(1, 10)]),
            ranking(["C01"] * 10),
            ranking([f"X{i:02d}" for i in range(1, 11)]),
        ]
        for malformed in cases:
            with self.subTest(ids=[item["candidate_id"] for item in malformed["ranking"]]):
                result, metadata = service(FakeModel(response=malformed)).rerank_search_results("q", source)
                self.assertEqual(result, source)
                self.assertEqual(metadata["fallback_reason"], "ValueError: ranking must include C01-C10 exactly once")

    def test_unsorted_or_out_of_range_scores_fall_back(self):
        source = rows()
        unsorted = ranking()
        unsorted["ranking"][0]["relevance_score"] = 0
        result, metadata = service(FakeModel(response=unsorted)).rerank_search_results("q", source)
        self.assertEqual(result, source)
        self.assertIn("sorted by descending", metadata["fallback_reason"])

        bad_score = ranking()
        bad_score["ranking"][0]["relevance_score"] = 101
        result, metadata = service(FakeModel(response=bad_score)).rerank_search_results("q", source)
        self.assertEqual(result, source)
        self.assertIn("invalid relevance_score", metadata["fallback_reason"])

    def test_non_top10_candidate_count_falls_back_without_api(self):
        model = FakeModel(ranking())
        source = rows()[:5]
        result, metadata = service(model).rerank_search_results("q", source)
        self.assertEqual(result, source)
        self.assertEqual(model.calls, [])
        self.assertIn("expected 10 vector candidates", metadata["fallback_reason"])

    def test_production_search_method_reranks_repository_top10(self):
        source = rows()
        service_instance = object.__new__(CarManualSearchService)
        service_instance.reranking_enabled = True
        service_instance.embedding_model = FakeEmbeddings()
        service_instance.repository = FakeRepository(source)
        service_instance.reranker_model = FakeModel(ranking([f"C{i:02d}" for i in range(10, 0, -1)]))

        ranked, metadata = service_instance.search_manual_with_metadata(
            "hyundai", "sonata", 2026, "question", limit=10,
        )
        self.assertEqual(service_instance.embedding_model.question, "question")
        self.assertEqual(service_instance.repository.kwargs["limit"], 10)
        self.assertEqual(service_instance.repository.kwargs["embedding"], [0.1, 0.2])
        self.assertEqual(ranked, list(reversed(source)))
        self.assertTrue(metadata["success"])

    def test_feature_flag_disabled_preserves_vector_rows(self):
        source = rows()
        service_instance = object.__new__(CarManualSearchService)
        service_instance.reranking_enabled = False
        service_instance.embedding_model = FakeEmbeddings()
        service_instance.repository = FakeRepository(source)
        service_instance.reranker_model = None
        result, metadata = service_instance.search_manual_with_metadata(
            "hyundai", "sonata", 2026, "question", limit=10,
        )
        self.assertEqual(result, source)
        self.assertEqual(metadata["fallback_reason"], "reranking disabled")
        self.assertEqual(metadata["request_count"], 0)


if __name__ == "__main__":
    unittest.main()
