"""실제 아이오닉 하이브리드 코드와 고정 평가 결과의 일치 여부를 확인합니다.
DB는 읽기 전용이며 질문 임베딩을 재사용합니다. 채팅 이력 저장/LLM 호출 없음.
"""
import os
import json
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch
from time import perf_counter
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
load_dotenv(ROOT/'.env', override=False)
os.environ['PGOPTIONS'] = '-c default_transaction_read_only=on'
from car_search_rag.anna_rag.chatbot import ioniq5_backend as backend
from car_search_rag.anna_rag.chatbot.ioniq5_retrieval import IoniqHybridSearch


def run():
    out = HERE/'hybrid_local_rollout_v1'
    if out.exists():
        raise FileExistsError('기존 검증 기록을 덮어쓰지 않습니다.')
    old_results = json.loads((HERE/'m7_three_way_v1/results.json').read_text())
    old_candidates = {q['id']:q for q in json.loads((HERE/'m7_mmr_v1/results.json').read_text())}
    old_vectors = {q['id']:q['embedding'] for q in json.loads((HERE/'m7_mmr_v1/query_vectors.json').read_text())}
    abc_results = json.loads((HERE/'m7_abc_v1/results.json').read_text())
    abc_vectors = {q['id']:q['embedding'] for q in json.loads((HERE/'m7_abc_v1/query_vectors.json').read_text())}
    docs = backend._load_tfidf_documents()
    byid = {d.id:d for d in docs}
    current_candidates = []
    retriever = IoniqHybridSearch(lambda: docs, lambda vector,k: current_candidates[:k])
    verified = []
    for q in old_results + [q for q in abc_results if q['section']=='A']:
        if q['id'].startswith('G'):
            current_candidates = [(byid[c['chunk_id']],c['cosine_distance']) for c in old_candidates[q['id']]['candidates']]
            vector = old_vectors[q['id']]
        else:
            current_candidates = [(byid[cid],0.0) for cid in q['dense_candidate_ids']]
            vector = abc_vectors[q['id']]
        hits = retriever.search(q['question'], vector)
        expected = q['top5']['hybrid']
        assert [h.document.id for h in hits] == [x['chunk_id'] for x in expected], q['id']
        assert all(abs(h.rrf_score-e['rrf_score'])<1e-12 and abs(h.tfidf_similarity-e['tfidf_similarity'])<1e-12 for h,e in zip(hits,expected))
        verified.append(q['id'])
    # 실제 DB 검색과 부모·이미지 연결까지 실행. 질문 벡터만 고정값으로 대체합니다.
    live = []
    t = perf_counter()
    backend.create_backend()
    warmup_ms = round((perf_counter()-t)*1000)
    for q in old_results:
        if q['id'] not in ['G03','G06','G07','G09','G17']:
            continue
        t = perf_counter()
        with patch.object(type(backend.embeddings),'embed_query',return_value=old_vectors[q['id']]):
            packet = backend.prepare_rag(q['question'])
        child = [s for s in packet['sources'] if s['chunk_id']]
        assert [s['chunk_id'] for s in child] == [s['chunk_id'] for s in q['top5']['hybrid']], q['id']
        assert len(child)==5 and len({s['chunk_id'] for s in child})==5
        assert packet['parent_context'] and packet['retrieval']['method']=='cosine_tfidf_rrf'
        assert all(isinstance(s['distance'],float) and s['retrieval_method']=='cosine_tfidf_rrf' for s in child)
        live.append(dict(id=q['id'],child_count=len(child),parent_count=sum(s['chunk_id'] is None for s in packet['sources']),
                         image_candidates=len(packet['image_candidates']),omitted_parents=len(packet['omitted_parents']),
                         lexical_only_results=sum(s['cosine_rank'] is None for s in child),
                         elapsed_ms=round((perf_counter()-t)*1000)))
    summary=dict(verified_at=datetime.now(timezone.utc).isoformat(),
        fixed_candidate_replays=len(verified),verified_ids=verified,
        ranking_and_scores_match=True,live_db_prepare_rag=live,warmup_ms=warmup_ms,
        config=backend.current_config()['retrieval'],pipeline_version=backend.pipeline_version,
        limits=['질문 벡터 재사용: 새 임베딩 API 호출 없음',
                '검색 및 부모·이미지 연결 검증. 의도 판단·답변 LLM·세션 저장은 실행하지 않음.',
                'DB 기본 트랜잭션 읽기 전용. 저장 데이터/배포/GitHub 변경 없음.'])
    out.mkdir()
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    (out/'verification_snapshot.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':
    run()
