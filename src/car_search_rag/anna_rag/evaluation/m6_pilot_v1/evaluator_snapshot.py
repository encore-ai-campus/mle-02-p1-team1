"""IONIQ 5 예비셋 검색 평가. 설명서·임베딩·채팅 이력은 수정하지 않습니다."""
import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent


def measure(ranked_ids, relevant_ids, k=5):
    """정답이 처음 나온 순위의 역수. 상위 k개 안에 없으면 0점입니다."""
    gold = set(relevant_ids)
    if not gold:
        raise ValueError('정답 라벨이 비어 있습니다.')
    rank = next((i for i, cid in enumerate(ranked_ids[:k], 1) if cid in gold), None)
    return {'hit': int(rank is not None), 'rr': 1 / rank if rank else 0.0, 'rank': rank}


def evaluate(dataset_path, output_dir, env_file=None):
    import os
    import psycopg
    from dotenv import load_dotenv
    from langchain_openai import OpenAIEmbeddings
    from langchain_postgres import PGEngine, PGVectorStore
    from sqlalchemy.engine import make_url

    load_dotenv(env_file or ROOT / '.env', override=False)
    raw_dataset = Path(dataset_path).read_bytes()
    dataset = json.loads(raw_dataset)
    questions = dataset['questions']
    if not questions or len({q['id'] for q in questions}) != len(questions):
        raise ValueError('평가 질문이 비어 있거나 ID가 중복됩니다.')
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError('기존 평가 결과는 덮어쓰지 않습니다. 새 결과 폴더를 지정하세요.')
    document_id = dataset['document_id']
    model, dimension = 'text-embedding-3-small', 1536

    # DB 스냅샷과 라벨을 먼저 검증합니다. 접속 비밀번호는 결과 파일에 남기지 않습니다.
    with psycopg.connect(os.environ['DB_URL'], options='-c default_transaction_read_only=on') as conn:
        corpus = conn.execute('''SELECT chunk_id, section_id, chunk_type, pdf_pages, page_content,
            embedding_model, embedding_dimension, embedding::text FROM anna_rag.chunks
            WHERE document_id=%s ORDER BY chunk_id''', (document_id,)).fetchall()
    if not corpus or any(r[5] != model or r[6] != dimension or r[7] is None for r in corpus):
        raise ValueError('전체 청크의 임베딩 모델·차원·완료 여부를 확인하세요.')
    ids = {r[0] for r in corpus}
    for q in questions:
        if not q['relevant_chunk_ids'] or not set(q['relevant_chunk_ids']) <= ids:
            raise ValueError(f"{q['id']}: 현재 DB와 정답 청크 ID가 일치하지 않습니다.")
    corpus_hash = hashlib.sha256(json.dumps(corpus, ensure_ascii=False).encode()).hexdigest()
    embeddings = OpenAIEmbeddings(model=model, dimensions=dimension, request_timeout=60, max_retries=2)
    url = make_url(os.environ['DB_URL']).set(drivername='postgresql+psycopg').update_query_dict(
        {'options': '-c default_transaction_read_only=on'})
    engine = PGEngine.from_connection_string(url=url)
    store = PGVectorStore.create_sync(
        engine=engine, embedding_service=embeddings,
        schema_name='anna_rag', table_name='chunks', id_column='chunk_id',
        content_column='page_content', embedding_column='embedding',
        metadata_columns=['document_id', 'section_id', 'chunk_type', 'pdf_pages', 'image_id',
                          'embedding_model', 'embedding_dimension'],
    )
    scope = {'document_id': document_id, 'embedding_model': model, 'embedding_dimension': dimension}
    results = []
    for q in questions:
        vector = embeddings.embed_query(q['question'])
        # 배포 앱과 같은 혼합(본문+이미지 설명) 검색이며 부모 본문 확장은 점수에 넣지 않습니다.
        top5 = store.similarity_search_with_score_by_vector(vector, k=5, filter=scope)
        # MRR에 cutoff가 지정되지 않았으므로 전체 순위 MRR도 별도로 계산합니다.
        full = store.similarity_search_with_score_by_vector(vector, k=len(corpus), filter=scope)
        hit5 = measure([doc.id for doc, _ in top5], q['relevant_chunk_ids'])
        full_score = measure([doc.id for doc, _ in full], q['relevant_chunk_ids'], len(corpus))
        if full_score['rank'] is None:
            raise ValueError(f"{q['id']}: 전체 순위에서 정답 청크를 찾을 수 없습니다.")
        entry = {**q, 'hit_at_5': hit5['hit'], 'rr_at_5': hit5['rr'],
                 'first_relevant_rank_at_5': hit5['rank'], 'rr_full': full_score['rr'],
                 'first_relevant_rank_full': full_score['rank'],
                 'top5': [dict(rank=i, chunk_id=doc.id, distance=float(distance),
                               **doc.metadata, page_content=doc.page_content)
                          for i, (doc, distance) in enumerate(top5, 1)]}
        results.append(entry)
        print(q['id'], 'Hit@5=', hit5['hit'], '正답 순위=', full_score['rank'], flush=True)
    n = len(results)
    summary = dict(
        dataset_version=dataset['dataset_version'], question_count=n,
        evaluated_at=datetime.now(timezone.utc).isoformat(),
        label_status='assistant_draft_needs_team_review',
        scope='Raw standalone-question retrieval only; excludes parent expansion, intent checks and answer generation.',
        embedding_model=model, embedding_dimension=dimension, corpus_chunks=len(corpus),
        dataset_sha256=hashlib.sha256(raw_dataset).hexdigest(), corpus_sha256=corpus_hash,
        evaluator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        hit_at_5=sum(r['hit_at_5'] for r in results)/n,
        mrr_at_5=sum(r['rr_at_5'] for r in results)/n,
        mrr_full=sum(r['rr_full'] for r in results)/n,
    )
    output_dir.mkdir(parents=True)
    (output_dir/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    (output_dir/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
    fields = ['id','category','question','hit_at_5','rr_at_5','first_relevant_rank_at_5','rr_full','first_relevant_rank_full']
    with (output_dir/'results.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(results)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',type=Path,default=HERE/'pilot_v1.json')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--env-file',type=Path)
    args=parser.parse_args()
    print(json.dumps(evaluate(args.dataset,args.output,args.env_file),ensure_ascii=False,indent=2))
