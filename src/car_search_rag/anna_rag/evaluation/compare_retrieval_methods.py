"""고정된 24문항으로 코사인 / 수업 TF-IDF / 동등 가중 RRF를 비교합니다.

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


def run(output_dir):
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
    raw = (baseline_dir / 'dataset_snapshot.json').read_bytes()
    dataset = json.loads(raw)
    baseline = json.loads((baseline_dir / 'summary.json').read_text())
    frozen = {q['id']: q for q in json.loads((frozen_dir / 'results.json').read_text())}
    vector_bytes = (frozen_dir / 'query_vectors.json').read_bytes()
    queries = {q['id']: q['embedding'] for q in json.loads(vector_bytes)}

    # 1. M6와 같은 설명서인지 해시로 확인합니다. 접속 정보는 저장하지 않습니다.
    load_dotenv(ROOT / '.env', override=False)
    with psycopg.connect(os.environ['DB_URL'], options='-c default_transaction_read_only=on') as conn:
        corpus = conn.execute('''SELECT chunk_id, section_id, chunk_type, pdf_pages, page_content,
            embedding_model, embedding_dimension, embedding::text FROM anna_rag.chunks
            WHERE document_id=%s ORDER BY chunk_id''', (dataset['document_id'],)).fetchall()
    corpus_hash = hashlib.sha256(json.dumps(corpus, ensure_ascii=False).encode()).hexdigest()
    if corpus_hash != baseline['corpus_sha256'] or hashlib.sha256(raw).hexdigest() != baseline['dataset_sha256']:
        raise ValueError('M6 정답지/설명서와 달라 비교를 중단합니다.')
    ids = [r[0] for r in corpus]
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
        vector = np.array(queries[q['id']], dtype=float)
        dense_scores = dense_matrix @ (vector / np.linalg.norm(vector))
        dense_order = sorted(range(len(ids)), key=lambda i: (-float(dense_scores[i]), ids[i]))
        # 기존 PGVector가 실제 반환한 상위 50개를 그대로 사용합니다.
        # 독립 코사인 계산으로 같은 후보/상위 5개인지 확인합니다.
        native_ids = [c['chunk_id'] for c in frozen[q['id']]['candidates']]
        if set(native_ids) != {ids[i] for i in dense_order[:BRANCH_K]}:
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
        entry = dict(id=q['id'], question=q['question'], relevant_chunk_ids=gold,
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
        results.append(entry)
        print(q['id'], {m: entry['metrics'][m]['rank'] for m in rankings}, flush=True)

    # 3. 검색을 마친 결과를 고정 정답지와 대조합니다.
    n = len(results)
    scores = {method: dict(hits=sum(r['metrics'][method]['hit'] for r in results),
        hit_at_5=sum(r['metrics'][method]['hit'] for r in results)/n,
        mrr_at_5=sum(r['metrics'][method]['rr'] for r in results)/n,
        gained=[r['id'] for r in results if not r['metrics']['cosine']['hit'] and r['metrics'][method]['hit']],
        lost=[r['id'] for r in results if r['metrics']['cosine']['hit'] and not r['metrics'][method]['hit']])
        for method in ('cosine', 'tfidf', 'hybrid')}
    assert scores['cosine']['hits'] == 14 and abs(scores['cosine']['mrr_at_5'] - 7/18) < 1e-10
    summary = dict(experiment='cosine_tfidf_hybrid_v1', status='complete', question_count=n,
        started_at=started, evaluated_at=datetime.now(timezone.utc).isoformat(),
        dataset_version=dataset['dataset_version'], dataset_sha256=baseline['dataset_sha256'],
        corpus_sha256=corpus_hash, corpus_chunks=len(corpus),
        query_vectors_sha256=hashlib.sha256(vector_bytes).hexdigest(),
        query_vectors_source='m7_mmr_v1/query_vectors.json',
        experiment_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        packages={name: version(name) for name in ('kiwipiepy','kiwipiepy_model','scikit-learn','numpy')},
        settings=dict(k=TOP_K, branch_k=BRANCH_K, rrf_constant=RRF_CONSTANT, weights=[1,1],
            tokenizer='Kiwi: tag startswith N and len(form)>1', lowercase=True,
            tfidf_norm='l2', smooth_idf=True, sublinear_tf=False, fitted_field='page_content',
            vocabulary_size=len(feature_names), lexical_positive_only=True, lexical_and_rrf_tie_break='chunk_id ascending'),
        scores=scores,
        candidate_hits={m: sum(r['candidate_hit'][m] for r in results) for m in ('cosine','tfidf')},
        union_candidate_hits=sum(r['union_candidate_hit'] for r in results),
        notes=['AI 초안 후 사람이 정답 근거를 검수한 고정 24문항. 독립 홀드아웃 아님.',
            'M6와 코퍼스·정답지 해시 동일. 기존 질문 임베딩 재사용. 새 API 호출 없음.',
            '코사인 순위는 기존 PGVector 반환 결과이며 현재 DB 벡터의 NumPy 계산으로 검증. 같은 점수의 문서는 기존 반환 순서를 유지. 수치 허용 오차 1e-6.',
            '수업의 명사 TF-IDF를 사용. RRF 결합은 수업 방식의 프로젝트 응용.',
            '정답은 채점에만 사용. 질문 변환·동의어·리랭크·MMR·부모 확장 미사용.',
            '설정을 결과 확인 전에 고정. 챗봇 검색/DB/배포 미변경.'])
    out.mkdir(parents=True)
    (out/'dataset_snapshot.json').write_bytes(raw)
    (out/'query_vectors.json').write_bytes(vector_bytes)
    (out/'experiment_snapshot.py').write_bytes(Path(__file__).read_bytes())
    for name, data in [('summary', summary), ('results', results)]:
        (out/f'{name}.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
    with (out/'results.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['id','question','method','hit_at_5','rr_at_5','first_relevant_rank_at_5'])
        for r in results:
            for method, score in r['metrics'].items():
                writer.writerow([r['id'],r['question'],method,score['hit'],score['rr'],score['rank']])
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output), ensure_ascii=False, indent=2))
