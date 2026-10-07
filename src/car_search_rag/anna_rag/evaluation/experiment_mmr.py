"""수업 방식 MMR 비교: 같은 질문 벡터로 기존 검색과 MMR을 평가합니다.

DB/배포 코드는 수정하지 않습니다. M6 정답지·코퍼스 해시를 먼저 대조합니다.
실제 PGVectorStore 반환 순서로 MRR@5를 계산합니다.
"""
import argparse
import hashlib
import inspect
import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from evaluate_retrieval import HERE, ROOT, measure

FETCH_K = 50
TOP_K = 5
LAMBDA_MULT = 0.25


def run(output_dir):
    import os
    import numpy as np
    import psycopg
    from dotenv import load_dotenv
    from langchain_openai import OpenAIEmbeddings
    from langchain_postgres import PGEngine, PGVectorStore
    from langchain_postgres.v2.async_vectorstore import AsyncPGVectorStore
    from langchain_core.vectorstores.utils import maximal_marginal_relevance
    from sqlalchemy.engine import make_url

    load_dotenv(ROOT / '.env', override=False)
    out = Path(output_dir)
    if out.exists():
        raise FileExistsError('기존 실험 기록을 덮어쓰지 않습니다.')
    baseline_dir = HERE / 'm6_baseline_v1'
    raw = (baseline_dir / 'dataset_snapshot.json').read_bytes()
    dataset = json.loads(raw)
    baseline = json.loads((baseline_dir / 'summary.json').read_text())
    original = {q['id']: q for q in json.loads((baseline_dir / 'results.json').read_text())}
    document_id = dataset['document_id']
    model, dimension = 'text-embedding-3-small', 1536
    with psycopg.connect(os.environ['DB_URL'], options='-c default_transaction_read_only=on') as conn:
        corpus = conn.execute('''SELECT chunk_id, section_id, chunk_type, pdf_pages, page_content,
            embedding_model, embedding_dimension, embedding::text FROM anna_rag.chunks
            WHERE document_id=%s ORDER BY chunk_id''', (document_id,)).fetchall()
    corpus_hash = hashlib.sha256(json.dumps(corpus, ensure_ascii=False).encode()).hexdigest()
    if corpus_hash != baseline['corpus_sha256'] or hashlib.sha256(raw).hexdigest() != baseline['dataset_sha256']:
        raise ValueError('M6와 정답지 또는 코퍼스가 달라 비교를 중단합니다.')
    vectors = {r[0]: np.array(json.loads(r[7]), dtype=float) for r in corpus}
    embedder = OpenAIEmbeddings(model=model, dimensions=dimension, request_timeout=60, max_retries=2)
    url = make_url(os.environ['DB_URL']).set(drivername='postgresql+psycopg').update_query_dict(
        {'options': '-c default_transaction_read_only=on'})
    engine = PGEngine.from_connection_string(url=url)
    store = PGVectorStore.create_sync(engine=engine, embedding_service=embedder,
        schema_name='anna_rag', table_name='chunks', id_column='chunk_id',
        content_column='page_content', embedding_column='embedding',
        metadata_columns=['document_id', 'section_id', 'chunk_type', 'pdf_pages', 'image_id',
                          'embedding_model', 'embedding_dimension'])
    scope = {'document_id': document_id, 'embedding_model': model, 'embedding_dimension': dimension}
    out.mkdir(parents=True)
    (out / 'dataset_snapshot.json').write_bytes(raw)
    (out / 'experiment_snapshot.py').write_bytes(Path(__file__).read_bytes())
    (out / 'pgvector_mmr_snapshot.py').write_text(inspect.getsource(
        AsyncPGVectorStore.amax_marginal_relevance_search_with_score_by_vector))
    started = datetime.now(timezone.utc).isoformat()
    results, query_vectors = [], []

    def serialize(items, candidate_rank):
        return [dict(chunk_id=doc.id, rank=i, vector_rank=candidate_rank[doc.id],
                     cosine_distance=float(distance), cosine_similarity=1-float(distance),
                     page_content=doc.page_content, **doc.metadata)
                for i, (doc, distance) in enumerate(items, 1)]

    def redundancy(items):
        mat = np.array([vectors[doc.id] for doc, _ in items])
        mat /= np.linalg.norm(mat, axis=1, keepdims=True)
        sim = mat @ mat.T
        return float(sim[np.triu_indices(len(items), 1)].mean())

    try:
        for q in dataset['questions']:
            # 두 검색 방법이 정확히 같은 질문 벡터를 사용합니다. 정답은 검색 후 채점에만 사용합니다.
            vector = embedder.embed_query(q['question'])
            query_vectors.append({'id': q['id'], 'embedding': vector})
            t = perf_counter()
            candidates = store.similarity_search_with_score_by_vector(vector, k=FETCH_K, filter=scope)
            plain = candidates[:TOP_K]
            vector_ms = round((perf_counter()-t)*1000)
            t = perf_counter()
            mmr = store.max_marginal_relevance_search_with_score_by_vector(
                vector, k=TOP_K, fetch_k=FETCH_K, lambda_mult=LAMBDA_MULT, filter=scope)
            mmr_ms = round((perf_counter()-t)*1000)
            greedy = maximal_marginal_relevance(np.array(vector, dtype=np.float32),
                [vectors[doc.id].tolist() for doc, _ in candidates], k=TOP_K, lambda_mult=LAMBDA_MULT)
            greedy_ids = [candidates[i][0].id for i in greedy]
            if set(greedy_ids) != {doc.id for doc, _ in mmr}:
                raise ValueError('MMR 선택 결과와 독립 검증이 일치하지 않습니다.')
            candidate_rank = {doc.id: i for i, (doc, _) in enumerate(candidates, 1)}
            gold = q['relevant_chunk_ids']
            before = measure([doc.id for doc, _ in plain], gold)
            after = measure([doc.id for doc, _ in mmr], gold)
            candidate_gold = measure([doc.id for doc, _ in candidates], gold, FETCH_K)
            result = dict(id=q['id'], question=q['question'], relevant_chunk_ids=gold,
                before=before, after=after, candidate_gold=candidate_gold,
                original_m6={'hit':original[q['id']]['hit_at_5'], 'rr':original[q['id']]['rr_at_5']},
                before_top5=serialize(plain, candidate_rank), after_top5=serialize(mmr, candidate_rank),
                candidates=serialize(candidates, candidate_rank),
                mmr_greedy_selection_ids=greedy_ids,
                returned_order_is_vector_order=[candidate_rank[doc.id] for doc, _ in mmr] ==
                    sorted(candidate_rank[doc.id] for doc, _ in mmr),
                before_unique_sections=len({doc.metadata['section_id'] for doc, _ in plain}),
                after_unique_sections=len({doc.metadata['section_id'] for doc, _ in mmr}),
                before_pairwise_cosine=redundancy(plain), after_pairwise_cosine=redundancy(mmr),
                vector_search_ms=vector_ms, mmr_search_ms=mmr_ms)
            results.append(result)
            (out / 'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2)+'\n')
            print(q['id'], 'before', before['hit'], before['rank'], 'after', after['hit'], after['rank'],
                  'gold in50', candidate_gold['rank'], flush=True)
    finally:
        (out / 'query_vectors.json').write_text(json.dumps(query_vectors)+'\n')
    n = len(results)
    score = lambda side: {'hit_at_5': sum(r[side]['hit'] for r in results)/n,
                          'mrr_at_5': sum(r[side]['rr'] for r in results)/n}
    summary = dict(experiment='class_mmr_v1', status='complete', question_count=n,
        started_at=started, evaluated_at=datetime.now(timezone.utc).isoformat(),
        dataset_version=dataset['dataset_version'], dataset_sha256=baseline['dataset_sha256'],
        corpus_sha256=corpus_hash, corpus_chunks=len(corpus), embedding_model=model,
        settings={'k':TOP_K,'fetch_k':FETCH_K,'lambda_mult':LAMBDA_MULT},
        original_m6=score('original_m6'), paired_vector=score('before'), mmr=score('after'),
        candidate_hit_at_50=sum(r['candidate_gold']['hit'] for r in results)/n,
        gained=[r['id'] for r in results if not r['before']['hit'] and r['after']['hit']],
        lost=[r['id'] for r in results if r['before']['hit'] and not r['after']['hit']],
        before_mean_unique_sections=sum(r['before_unique_sections'] for r in results)/n,
        after_mean_unique_sections=sum(r['after_unique_sections'] for r in results)/n,
        before_mean_pairwise_cosine=sum(r['before_pairwise_cosine'] for r in results)/n,
        after_mean_pairwise_cosine=sum(r['after_pairwise_cosine'] for r in results)/n,
        notes=['코퍼스·정답지 M6 해시 동일. 원문 질문·동일 질문 벡터로 방법 비교.',
               'MMR은 추가 LLM 호출 없이 관련성과 다양성으로 후보를 선택한다.',
               '현재 PGVectorStore는 MMR로 고른 청크를 원래 벡터 순서로 반환한다. 실제 반환 순서로 MRR@5 계산.',
               '반환 점수는 MMR 점수가 아니라 코사인 거리. 유사도=1-거리. 정답 확률 아님.',
               '수업 코드 조건을 고정해 한 번 비교. 배포 로직 미변경.'])
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output), ensure_ascii=False, indent=2))
