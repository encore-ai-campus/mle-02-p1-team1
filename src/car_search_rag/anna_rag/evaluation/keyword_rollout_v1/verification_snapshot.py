"""검증된 34개 검색 결정을 새 아이오닉 구현에서 재생합니다. DB 읽기 전용.

LLM을 다시 채점하지 않고 기존 추출어·순위 응답을 재생하여 이식 과정의 차이를 검사합니다.
현재 DB의 LIKE 검색·거리 계산·부모/이미지 연결은 실제 실행합니다.
"""
import json,os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from dotenv import load_dotenv
from langchain_core.documents import Document

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
load_dotenv(ROOT/'.env',override=False)
os.environ['PGOPTIONS']='-c default_transaction_read_only=on'
from car_search_rag.anna_rag.chatbot import ioniq5_backend as b


def main():
    records=json.loads((HERE/'sonata_transfer_v1/results.json').read_text())
    vectors={r['id']:r['embedding'] for r in json.loads((HERE/'m7_abc_v1/query_vectors.json').read_text())}
    vectors.update({r['id']:r['embedding'] for r in json.loads((HERE/'m7_mmr_v1/query_vectors.json').read_text())})
    out=HERE/'keyword_rollout_v1';out.mkdir(exist_ok=True)
    with b.db.connect(camel_case_keys=False) as conn:
        rows=conn.execute('''SELECT chunk_id,page_content,document_id,section_id,chunk_type,
          pdf_pages,image_id,embedding_model,embedding_dimension FROM anna_rag.chunks
          WHERE document_id=%s ORDER BY chunk_id''',(b.document_id,)).fetchall()
    docs={r['chunk_id']:Document(id=r['chunk_id'],page_content=r['page_content'],metadata={k:v for k,v in r.items() if k not in ('chunk_id','page_content')}) for r in rows}
    checks=[]
    for record in records:
        class KeywordReplay:
            def invoke(self,messages):
                assert messages[-1][1]==record['question']
                return SimpleNamespace(content=json.dumps({'phrases':record['metadata']['keyword_phrases'],
                    'terms':record['metadata']['keyword_terms']}))
        class RerankReplay:
            def invoke(self,messages):
                payload=json.loads(messages[-1][1]);mapping=record['metadata']['candidate_mapping']
                assert payload['question']==record['question']
                assert len(payload['candidates'])==len(mapping)
                for actual,expected in zip(payload['candidates'],mapping):
                    assert actual=={'candidate_id':expected['candidate_id'],'page_no':expected['page_no'],
                        'chunk_id':expected['chunk_id'],'text':docs[expected['database_chunk_id']].page_content}
                masked={r['database_chunk_id']:r['candidate_id'] for r in mapping}
                return SimpleNamespace(content=json.dumps({'ranking':[dict(candidate_id=masked[cid],relevance_score=100-i)
                    for i,cid in enumerate(record['ranked_ids'])]}),usage_metadata={},response_metadata={})
        with patch.object(b.manual_search,'keyword_model',KeywordReplay()),patch.object(b.manual_search.reranker,'reranker_model',RerankReplay()),patch.object(type(b.embeddings),'embed_query',return_value=vectors[record['id']]),patch.object(b,'_search_vector_candidates',return_value=[(docs[cid],.1) for cid in record['vector_ids']]):
            packet=b.prepare_rag(record['question'])
        children=[s for s in packet['sources'] if s['chunk_id']]
        assert [s['chunk_id'] for s in children]==record['ranked_ids'][:5],record['id']
        assert packet['retrieval']['rerank']['success'],record['id']
        actual_map=packet['retrieval']['rerank']['candidate_mapping']
        assert actual_map==record['metadata']['candidate_mapping'],record['id']
        assert all(s['document_id']==b.document_id for s in packet['sources'])
        assert all(isinstance(s['distance'],float) for s in children)
        assert all(set(im['source_labels'])<=set(s['label'] for s in children) for im in packet['image_candidates'])
        checks.append(dict(id=record['id'],exact_top5=True,exact_candidates_and_prompt=True,
            image_count=len(packet['image_candidates']),omitted_parents=len(packet['omitted_parents'])))
        print(record['id'],'OK',flush=True)
    result={'verification':'recorded LLM decisions replayed; live read-only keyword SQL and context',
        'count':len(checks),'pipeline_version':b.pipeline_version,'configuration':b.manual_search.configuration(),
        'checks':checks,'new_quality_measurement':False}
    (out/'replay.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    (out/'verification_snapshot.py').write_bytes(Path(__file__).read_bytes())
    print('34개 입력의 이식 일치 검증 완료',flush=True)


if __name__=='__main__':
    try:main()
    except Exception as error:
        print('검증 오류 유형:',type(error).__name__,flush=True)
        raise
