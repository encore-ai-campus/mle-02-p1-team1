"""A/B/C 각 10문항으로 코사인 / 수업 TF-IDF / 동등 가중 RRF를 비교합니다.

챗봇·DB를 변경하지 않습니다. 정답은 검색을 끝낸 뒤 채점에만 사용합니다.
이전 실험의 질문 임베딩을 재사용해 모델 호출에 따른 차이를 제거합니다.
"""
import argparse
import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from evaluate_retrieval import HERE, ROOT, measure

TOP_K = 5
BRANCH_K = 50
RRF_CONSTANT = 60


def fuse(dense_ids, lexical_ids):
    """각 검색 순위에 1/(60+순위)를 주고 합산합니다. 동점은 청크 ID 순서입니다."""
    scores = {}
    for branch in (dense_ids, lexical_ids):
        for rank, cid in enumerate(dict.fromkeys(branch), 1):
            scores[cid] = scores.get(cid, 0.0) + 1 / (RRF_CONSTANT + rank)
    return sorted(scores, key=lambda cid: (-scores[cid], cid)), scores


def run(output_dir, dataset_path, resume_vectors=None):
    import numpy as np
    import psycopg
    from dotenv import load_dotenv
    from kiwipiepy import Kiwi
    from sklearn.feature_extraction.text import TfidfVectorizer

    out = Path(output_dir)
    if out.exists():
        raise FileExistsError('기존 평가 결과를 덮어쓰지 않습니다.')
    started = datetime.now(timezone.utc).isoformat()
    baseline_dir = HERE / 'm6_baseline_v1'
    frozen_dir = HERE / 'm7_mmr_v1'
    raw = Path(dataset_path).read_bytes()
    dataset = json.loads(raw)
    baseline = json.loads((baseline_dir / 'summary.json').read_text())
    frozen = {q['id']: q for q in json.loads((frozen_dir / 'results.json').read_text())}
    from langchain_openai import OpenAIEmbeddings
    from langchain_postgres import PGEngine, PGVectorStore
    from sqlalchemy.engine import make_url
    old_queries = {q['id']: q['embedding'] for q in json.loads((frozen_dir / 'query_vectors.json').read_text())}
    query_records = []
    saved_vectors = {q['id']: q['embedding'] for q in json.loads(Path(resume_vectors).read_text())} if resume_vectors else {}

    # 1. M6와 같은 설명서인지 해시로 확인합니다. 접속 정보는 저장하지 않습니다.
    load_dotenv(ROOT / '.env', override=False)
    with psycopg.connect(os.environ['DB_URL'], options='-c default_transaction_read_only=on') as conn:
        corpus = conn.execute('''SELECT chunk_id, section_id, chunk_type, pdf_pages, page_content,
            embedding_model, embedding_dimension, embedding::text FROM anna_rag.chunks
            WHERE document_id=%s ORDER BY chunk_id''', (dataset['document_id'],)).fetchall()
    corpus_hash = hashlib.sha256(json.dumps(corpus, ensure_ascii=False).encode()).hexdigest()
    if corpus_hash != baseline['corpus_sha256']:
        raise ValueError('M6 정답지/설명서와 달라 비교를 중단합니다.')
    embedder = OpenAIEmbeddings(model='text-embedding-3-small', dimensions=1536, request_timeout=60, max_retries=2)
    url = make_url(os.environ['DB_URL']).set(drivername='postgresql+psycopg').update_query_dict({'options':'-c default_transaction_read_only=on'})
    engine = PGEngine.from_connection_string(url=url)
    store = PGVectorStore.create_sync(engine=engine, embedding_service=embedder,
        schema_name='anna_rag',table_name='chunks',id_column='chunk_id',content_column='page_content',embedding_column='embedding',
        metadata_columns=['document_id','section_id','chunk_type','pdf_pages','image_id','embedding_model','embedding_dimension'])
    scope = {'document_id':dataset['document_id'],'embedding_model':'text-embedding-3-small','embedding_dimension':1536}
    old_questions = {q['id']:q for q in json.loads((baseline_dir/'dataset_snapshot.json').read_text())['questions']}
    out.mkdir(parents=True)
    (out/'dataset_snapshot.json').write_bytes(raw)
    (out/'experiment_snapshot.py').write_bytes(Path(__file__).read_bytes())
    assert len(dataset['questions']) == 30
    assert all(sum(q['section']==section for q in dataset['questions'])==10 for section in 'ABC')
    ids = [r[0] for r in corpus]
    assert all(set(q['relevant_chunk_ids']) <= set(ids) and q['relevant_chunk_ids'] for q in dataset['questions'])
    positions = {cid: i for i, cid in enumerate(ids)}
    dense_matrix = np.array([json.loads(r[7]) for r in corpus], dtype=float)
    dense_matrix /= np.linalg.norm(dense_matrix, axis=1, keepdims=True)

    # 2. 수업과 동일하게 두 글자 이상의 명사로 TF-IDF를 만듭니다.
    # 정답지의 표현을 추가하거나 특정 질문에 유리한 단어를 넣지 않습니다.
    kiwi = Kiwi(num_workers=1)

    def extract_nouns(text):
        return [t.form for t in kiwi.tokenize(text) if t.tag.startswith('N') and len(t.form) > 1]

    vectorizer = TfidfVectorizer(tokenizer=extract_nouns, token_pattern=None)
    lexical_matrix = vectorizer.fit_transform([r[4] for r in corpus])
    feature_names = vectorizer.get_feature_names_out()
    results = []
    for q in dataset['questions']:
        origin = q['origin_ids'][0]
        reuse = q['origin_type'] == 'existing_question_verbatim'
        if reuse:
            assert q['question'] == old_questions[origin]['question']
            assert q['relevant_chunk_ids'] == old_questions[origin]['relevant_chunk_ids']
        query_vector = old_queries[origin] if reuse else (saved_vectors[q['id']] if q['id'] in saved_vectors else embedder.embed_query(q['question']))
        query_records.append(dict(id=q['id'],embedding=query_vector,source=origin if reuse else 'new_embedding'))
        (out/'query_vectors.json').write_text(json.dumps(query_records)+'\n')
        vector = np.array(query_vector, dtype=float)
        dense_scores = dense_matrix @ (vector / np.linalg.norm(vector))
        dense_order = sorted(range(len(ids)), key=lambda i: (-float(dense_scores[i]), ids[i]))
        # 기존 PGVector가 실제 반환한 상위 50개를 그대로 사용합니다.
        # 독립 코사인 계산으로 같은 후보/상위 5개인지 확인합니다.
        native_ids = ([c['chunk_id'] for c in frozen[origin]['candidates']] if reuse else
            [doc.id for doc, distance in store.similarity_search_with_score_by_vector(query_vector,k=BRANCH_K,filter=scope)])
        # 후보 경계에 동일 임베딩의 이미지가 겹칠 수 있어 ID 대신 순위별 점수를 대조합니다.
        if not np.allclose([dense_scores[positions[cid]] for cid in native_ids],
                           [dense_scores[i] for i in dense_order[:BRANCH_K]], rtol=0, atol=1e-6):
            raise ValueError(f"{q['id']}: 코사인 후보 검증 실패")
        if not np.allclose([dense_scores[positions[cid]] for cid in native_ids[:TOP_K]],
                           [dense_scores[i] for i in dense_order[:TOP_K]], rtol=0, atol=1e-6):
            raise ValueError(f"{q['id']}: 코사인 순서 검증 실패")
        query_tfidf = vectorizer.transform([q['question']])
        lexical_scores = (lexical_matrix @ query_tfidf.T).toarray().ravel()
        # 겹치는 명사가 전혀 없는 0점 문서를 임의로 채워 넣지 않습니다.
        lexical_order = sorted((i for i, score in enumerate(lexical_scores) if score > 0),
                               key=lambda i: (-float(lexical_scores[i]), ids[i]))
        lexical_ids = [ids[i] for i in lexical_order]
        hybrid_ids, rrf_scores = fuse(native_ids, lexical_ids[:BRANCH_K])
        rankings = {'cosine': native_ids, 'tfidf': lexical_ids, 'hybrid': hybrid_ids}
        dense_ranks = {ids[i]: rank for rank, i in enumerate(dense_order, 1)}
        dense_ranks.update({cid: rank for rank, cid in enumerate(native_ids, 1)})
        lexical_ranks = {cid: rank for rank, cid in enumerate(lexical_ids, 1)}

        def serialize(cid, rank, method):
            i = positions[cid]
            row = corpus[i]
            overlap = lexical_matrix[i].multiply(query_tfidf).tocoo()
            terms = sorted(zip(overlap.col, overlap.data), key=lambda item: (-item[1], feature_names[item[0]]))
            return dict(chunk_id=cid, rank=rank, section_id=row[1], chunk_type=row[2], pdf_pages=row[3],
                page_content=row[4], cosine_similarity=float(dense_scores[i]), tfidf_similarity=float(lexical_scores[i]),
                rrf_score=rrf_scores.get(cid), dense_rank=dense_ranks[cid], tfidf_rank=lexical_ranks.get(cid),
                matched_terms=[{'term': str(feature_names[j]), 'contribution': float(value)} for j, value in terms],
                relevant=cid in q['relevant_chunk_ids'])

        gold = q['relevant_chunk_ids']
        entry = dict(id=q['id'], section=q['section'], origin_ids=q['origin_ids'], question=q['question'], relevant_chunk_ids=gold,
            dense_candidate_ids=native_ids, tfidf_candidate_ids=lexical_ids[:BRANCH_K],
            query_nouns=extract_nouns(q['question'].lower()), query_vocabulary_terms=feature_names[query_tfidf.indices].tolist(),
            tfidf_positive_documents=len(lexical_ids),
            metrics={method: measure(ranking, gold) for method, ranking in rankings.items()},
            top5={method: [serialize(cid, rank, method) for rank, cid in enumerate(ranking[:TOP_K], 1)]
                  for method, ranking in rankings.items()},
            candidate_hit={method: measure(ranking[:BRANCH_K], gold, BRANCH_K)['hit']
                           for method, ranking in list(rankings.items())[:2]},
            union_candidate_hit=int(bool(set(gold) & set(hybrid_ids))),
            gold_ranks=[dict(chunk_id=cid, cosine=dense_ranks[cid], tfidf=lexical_ranks.get(cid),
                hybrid=(hybrid_ids.index(cid)+1 if cid in hybrid_ids else None)) for cid in gold])
        if reuse:
            assert entry['metrics']['cosine'] == frozen[origin]['before']
        results.append(entry)
        (out/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
        print(q['id'], {m: entry['metrics'][m]['rank'] for m in rankings}, flush=True)

    # 3. 검색을 마친 결과를 고정 정답지와 대조합니다.
    n = len(results)
    scores = {method: dict(hits=sum(r['metrics'][method]['hit'] for r in results),
        hit_at_5=sum(r['metrics'][method]['hit'] for r in results)/n,
        mrr_at_5=sum(r['metrics'][method]['rr'] for r in results)/n,
        gained=[r['id'] for r in results if not r['metrics']['cosine']['hit'] and r['metrics'][method]['hit']],
        lost=[r['id'] for r in results if r['metrics']['cosine']['hit'] and not r['metrics'][method]['hit']])
        for method in ('cosine', 'tfidf', 'hybrid')}
    section_scores = {}
    for section in ['A','B','C','BC']:
        subset = [r for r in results if r['section'] in section]
        section_scores[section] = {m:dict(count=len(subset),hits=sum(r['metrics'][m]['hit'] for r in subset),
            hit_at_5=sum(r['metrics'][m]['hit'] for r in subset)/len(subset),
            mrr_at_5=sum(r['metrics'][m]['rr'] for r in subset)/len(subset)) for m in scores}
    vector_bytes = (out/'query_vectors.json').read_bytes()
    summary = dict(experiment='abc30_cosine_tfidf_hybrid_v1', status='complete', question_count=n,
        started_at=started, evaluated_at=datetime.now(timezone.utc).isoformat(),
        dataset_version=dataset['dataset_version'], dataset_sha256=hashlib.sha256(raw).hexdigest(),
        corpus_sha256=corpus_hash, corpus_chunks=len(corpus),
        query_vectors_sha256=hashlib.sha256(vector_bytes).hexdigest(),
        query_vectors_source='20 existing cached + 10 new topic queries',
        experiment_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        packages={name: version(name) for name in ('kiwipiepy','kiwipiepy_model','scikit-learn','numpy')},
        settings=dict(k=TOP_K, branch_k=BRANCH_K, rrf_constant=RRF_CONSTANT, weights=[1,1],
            tokenizer='Kiwi: tag startswith N and len(form)>1', lowercase=True,
            tfidf_norm='l2', smooth_idf=True, sublinear_tf=False, fitted_field='page_content',
            vocabulary_size=len(feature_names), lexical_positive_only=True, lexical_and_rrf_tie_break='chunk_id ascending'),
        scores=scores, section_scores=section_scores,
        section_macro_mean={m:{metric:sum(section_scores[g][m][metric] for g in 'ABC')/3 for metric in ['hit_at_5','mrr_at_5']} for m in scores},
        candidate_hits={m: sum(r['candidate_hit'][m] for r in results) for m in ('cosine','tfidf')},
        union_candidate_hits=sum(r['union_candidate_hit'] for r in results),
        notes=dataset['limitations'] + ['설정은 이전 24문항 비교와 동일: k=5, branch_k=50, RRF 60, 동등 가중.',
            '새 A10 임베딩만 생성. 기존 B/C20은 이전 질문 벡터와 코사인 후보 재사용.',
            'A 목차 관련성 라벨은 검색 전 고정. B/C 사람 검수 라벨과 새 분류/신규 라벨의 검수 상태를 구분.',
            '같은 청크 ID로 Hit@5, MRR@5를 계산. 각 섹션 10문항이므로 섹션 평균과 전체 30문항 평균이 같음.',
            '되묻기·질문 재작성·부모 확장·MMR·리랭크·답변 생성 제외. 운영 미변경.'])
    (out/'dataset_snapshot.json').write_bytes(raw)
    (out/'query_vectors.json').write_bytes(vector_bytes)
    (out/'experiment_snapshot.py').write_bytes(Path(__file__).read_bytes())
    for name, data in [('summary', summary), ('results', results)]:
        (out/f'{name}.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
    with (out/'results.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['id','section','origin_ids','question','method','hit_at_5','rr_at_5','first_relevant_rank_at_5'])
        for r in results:
            for method, score in r['metrics'].items():
                writer.writerow([r['id'],r['section'],','.join(r['origin_ids']),r['question'],method,score['hit'],score['rr'],score['rank']])
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--resume-vectors', type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.output,args.dataset,args.resume_vectors), ensure_ascii=False, indent=2))
