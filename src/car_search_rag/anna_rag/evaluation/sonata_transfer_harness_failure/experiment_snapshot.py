"""소나타의 실제 검색 orchestration/키워드 추출/rerank를 아이오닉에 읽기 전용 적용.

DB 테이블과 row 필드만 adapter로 변환합니다. 소나타·아이오닉 운영 코드는 수정하지 않습니다.
같은 골든셋/청크/고정 벡터 후보로 비교하고 정답은 검색이 끝난 뒤 채점에만 사용합니다.
"""
import hashlib,json,logging,os,sys,time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from datetime import datetime,timezone

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/'src'))
from evaluate_retrieval import measure


def main():
    import psycopg
    from psycopg.rows import dict_row
    from dotenv import load_dotenv
    from car_search_rag.car_search import car_manual_search_service as sonata
    load_dotenv(ROOT/'.env',override=False)
    logging.getLogger('car_search_rag.car_manual').setLevel(logging.CRITICAL)
    out=HERE/'sonata_transfer_v1';out.mkdir(exist_ok=True)
    if (out/'summary.json').exists():raise FileExistsError('완료한 실험은 덮어쓰지 않습니다.')
    abc=json.loads((HERE/'golden_abc_v1/dataset.json').read_text())
    old=json.loads((HERE/'m6_baseline_v1/dataset_snapshot.json').read_text())
    abc_results={r['id']:r for r in json.loads((HERE/'m7_abc_v1/results.json').read_text())}
    old_results={r['id']:r for r in json.loads((HERE/'m7_three_way_v1/results.json').read_text())}
    frozen={r['id']:r for r in json.loads((HERE/'m7_mmr_v1/results.json').read_text())}
    used_origins={q['origin_ids'][0] for q in abc['questions'] if q['origin_type']=='existing_question_verbatim'}
    questions=abc['questions']+[{**q,'section':'supplement','origin_ids':[q['id']]} for q in old['questions'] if q['id'] not in used_origins]
    assert len(questions)==34
    with psycopg.connect(os.environ['DB_URL'],options='-c default_transaction_read_only=on') as c:
        corpus=c.execute('''SELECT chunk_id,section_id,chunk_type,pdf_pages,page_content,
          embedding_model,embedding_dimension,embedding::text FROM anna_rag.chunks
          WHERE document_id=%s ORDER BY chunk_id''',(abc['document_id'],)).fetchall()
    corpus_hash=hashlib.sha256(json.dumps(corpus,ensure_ascii=False).encode()).hexdigest()
    assert corpus_hash==json.loads((HERE/'m6_baseline_v1/summary.json').read_text())['corpus_sha256']
    rows={r[0]:{'carManualChunkId':r[0],'carId':abc['document_id'],
               'carManualChapterId':r[1],'carManualChunkPageNo':min(r[3]),
               'carManualChunkNo':i,'carManualChunkTxt':r[4]} for i,r in enumerate(corpus,1)}
    service_path=Path(sonata.__file__)
    sql_path=service_path.with_name('car_manual.sql')
    config={'started_at':datetime.now(timezone.utc).isoformat(),'corpus_sha256':corpus_hash,
        'sonata_service_sha256':hashlib.sha256(service_path.read_bytes()).hexdigest(),
        'sonata_sql_sha256':hashlib.sha256(sql_path.read_bytes()).hexdigest(),
        'question_count':34,'vector_k':sonata.HYBRID_TOP_K,'keyword_k':sonata.HYBRID_TOP_K,
        'keyword_phrase_weight':3,'keyword_term_weight':1,'rerank_model':sonata.RERANKER_MODEL,
        'keyword_model':'gpt-6-luna','rerank_timeout':sonata.RERANKER_TIMEOUT_SECONDS,
        'rerank_retries':sonata.RERANKER_MAX_RETRIES,'rerank_completion_tokens':sonata.HYBRID_RERANK_COMPLETION_TOKENS,
        'final_k':5,'corpus_chunks':len(corpus),
        'mapping':['문서는 기존 아이오닉 page_content 전체를 사용(목차 포함, 이미지 설명 청크 포함).',
                   '아이오닉은 소나타의 페이지별 chunk_no가 없어 PDF 첫 페이지와 chunk_id 오름차순을 동점 기준으로 대응.',
                   '벡터 후보는 검증된 기존 PGVector top50에서 top10을 고정 재사용. 실제 API 임베딩/벡터 조회 시간은 측정에서 제외.',
                   'LIKE는 소나타와 같은 대소문자 구분·구문 3점/단어 1점. DB 조회만 anna_rag로 변경.',
                   '소나타 _keyword_branch, _search_manual_hybrid, rerank_search_results 원본 메서드 그대로 호출.',
                   '키워드 모델 timeout 30초/max_retries=0: 평가 무한 대기 방지용 전송 설정만 변경.',
                   '질문 재작성·의도 판단·답변 생성·부모 문맥 확장은 제외한 검색기 비교.'],
        'question_sets':{'abc_sha256':hashlib.sha256((HERE/'golden_abc_v1/dataset.json').read_bytes()).hexdigest(),
                         'original24_sha256':hashlib.sha256((HERE/'m6_baseline_v1/dataset_snapshot.json').read_bytes()).hexdigest()}}
    config_path=out/'config.json'
    if config_path.exists():
        previous=json.loads(config_path.read_text());assert all(previous[k]==v for k,v in config.items() if k!='started_at')
    else:config_path.write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n')
    (out/'dataset_snapshot.json').write_text(json.dumps(questions,ensure_ascii=False,indent=2)+'\n')
    (out/'sonata_service_snapshot.py').write_bytes(service_path.read_bytes())
    (out/'sonata_sql_snapshot.sql').write_bytes(sql_path.read_bytes())
    (out/'experiment_snapshot.py').write_bytes(Path(__file__).read_bytes())

    class IoniqRepositoryAdapter:
        def __init__(self,*args,**kwargs):pass
        def find_car_id(self,*args):return abc['document_id']
        def search_manual_by_keywords(self,car_id,phrases,terms,limit):
            # ソナタ SQL과 같은 가중 LIKE. 공유 데이터에는 쓰지 않습니다.
            with psycopg.connect(os.environ['DB_URL'],options='-c default_transaction_read_only=on',row_factory=dict_row) as c:
                found=c.execute('''WITH scored AS (
                  SELECT chunk_id,pdf_pages,
                    (SELECT count(*)*3 FROM unnest(%s::text[]) AS p(phrase)
                     WHERE page_content LIKE '%%'||p.phrase||'%%')+
                    (SELECT count(*) FROM unnest(%s::text[]) AS t(term)
                     WHERE page_content LIKE '%%'||t.term||'%%') AS keyword_score
                  FROM anna_rag.chunks WHERE document_id=%s)
                  SELECT chunk_id,keyword_score FROM scored WHERE keyword_score>0
                  ORDER BY keyword_score DESC,(SELECT min(p) FROM unnest(pdf_pages) AS p),chunk_id
                  LIMIT %s''',(phrases,terms,car_id,limit)).fetchall()
            self_outer.keyword_rows=[{**rows[r['chunk_id']],'keywordScore':r['keyword_score']} for r in found]
            return self_outer.keyword_rows

    class TransferService(sonata.CarManualSearchService):
        def _vector_branch(self,*args):
            return {'rows':[dict(rows[cid]) for cid in self.vector_ids], 'latency':0.0}
        def rerank_search_results(self,question,candidates,**kwargs):
            self.merged_ids=[r['carManualChunkId'] for r in candidates]
            ranked,meta=super().rerank_search_results(question,candidates,**kwargs)
            self.ranked_ids=[r['carManualChunkId'] for r in ranked]
            return ranked,meta

    self_outer=TransferService(None)
    self_outer.sql_session=SimpleNamespace(database_manager=None)
    self_outer.hybrid_search_enabled=True;self_outer.reranking_enabled=True
    # ソナタと同じ model/prompt。評価のハングだけを防ぐ transport timeout。
    self_outer.chat_model=self_outer.chat_model.bind(timeout=30,max_retries=0)
    records=json.loads((out/'results.json').read_text()) if (out/'results.json').exists() else []
    finished={r['id'] for r in records}
    with patch.object(sonata,'SqlSession',lambda **kwargs:None),patch.object(sonata,'CarManualRepository',IoniqRepositoryAdapter):
        for q in questions:
            if q['id'] in finished:continue
            origin=q['origin_ids'][0]
            ref=abc_results[q['id']] if q['id'] in abc_results else old_results[q['id']]
            native=ref['dense_candidate_ids'] if q['id'] in abc_results else [r['chunk_id'] for r in frozen[origin]['candidates']]
            self_outer.vector_ids=native[:10];self_outer.keyword_rows=[];self_outer.merged_ids=[];self_outer.ranked_ids=[]
            started=time.perf_counter()
            selected,meta=self_outer._search_manual_hybrid('hyundai','ioniq5','2027',q['question'],5)
            keyword_ids=[r['carManualChunkId'] for r in self_outer.keyword_rows]
            entry={'id':q['id'],'section':q['section'],'origin_ids':q['origin_ids'],'question':q['question'],
                'relevant_chunk_ids':q['relevant_chunk_ids'],
                'baseline':ref['metrics'],
                'after':measure([r['carManualChunkId'] for r in selected],q['relevant_chunk_ids']),
                'vector10_hit':measure(self_outer.vector_ids,q['relevant_chunk_ids'],10)['hit'],
                'keyword10_hit':measure(keyword_ids,q['relevant_chunk_ids'],10)['hit'],
                'candidate_hit':measure(self_outer.merged_ids,q['relevant_chunk_ids'],20)['hit'],
                'vector_ids':self_outer.vector_ids,'keyword_ids':keyword_ids,
                'merged_ids':self_outer.merged_ids,'ranked_ids':self_outer.ranked_ids,
                'top5':[{'chunk_id':r['carManualChunkId'],'page':r['carManualChunkPageNo'],
                         'text':r['carManualChunkTxt']} for r in selected],
                'metadata':meta,'elapsed_s':time.perf_counter()-started}
            records.append(entry)
            (out/'results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
            print(json.dumps({'id':q['id'],'before':entry['baseline']['hybrid']['rank'],'after':entry['after']['rank'],
                'candidate_hit':entry['candidate_hit'],'rerank_ok':meta['success'],
                'keyword_ok':not meta['keyword_branch_failed'],'seconds':round(entry['elapsed_s'],2)}),flush=True)
    def aggregate(rs,method):
        ms=[r['after'] if method=='sonata' else r['baseline'][method] for r in rs]
        return dict(count=len(ms),hits=sum(m['hit'] for m in ms),hit_at_5=sum(m['hit'] for m in ms)/len(ms),mrr_at_5=sum(m['rr'] for m in ms)/len(ms))
    groups={g:[r for r in records if r['section'] in g] for g in ['A','B','C','BC','ABC']}
    groups['original24']=[r for r in records if r['section'] not in ['A']]
    summary={'status':'complete','finished_at':datetime.now(timezone.utc).isoformat(),
       'scores':{g:{m:aggregate(rs,m) for m in ['cosine','tfidf','hybrid','sonata']} for g,rs in groups.items()},
       'diagnostics':{g:{'vector10_hits':sum(r['vector10_hit'] for r in rs),'union_hits':sum(r['candidate_hit'] for r in rs),
          'keyword10_hits':sum(r['keyword10_hit'] for r in rs),
          'rerank_failures':sum(not r['metadata']['success'] for r in rs),
          'keyword_failures':sum(r['metadata']['keyword_branch_failed'] for r in rs),
          'gained':[r['id'] for r in rs if r['after']['hit']>r['baseline']['hybrid']['hit']],
          'lost':[r['id'] for r in rs if r['after']['hit']<r['baseline']['hybrid']['hit']],
          'mean_elapsed_s':sum(r['elapsed_s'] for r in rs)/len(rs),
          'mean_keyword_s':sum(r['metadata']['keyword_extraction_latency_seconds'] for r in rs)/len(rs),
          'mean_rerank_s':sum(r['metadata']['reranking_latency_seconds'] for r in rs)/len(rs)} for g,rs in groups.items()},
       'notes':config['mapping']+abc['limitations']+['LLM 1회 실행 비교. 테스트셋으로 설정을 최적화하지 않았으며 재실행 변동 가능. 운영 미적용.']}
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary['scores'],ensure_ascii=False),flush=True)

if __name__=='__main__':
    try:main()
    except Exception as error:
        print('실험 중단:',type(error).__name__,flush=True)
        raise SystemExit(1)
