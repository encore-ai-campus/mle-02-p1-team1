"""TF-IDF 단독 후보 및 실제 의도→검색→답변 경로 확인. DB 저장은 하지 않습니다."""
import os,json
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch
from dotenv import load_dotenv
HERE=Path(__file__).resolve().parent
load_dotenv(HERE.parents[3]/'.env',override=False)
os.environ['PGOPTIONS']='-c default_transaction_read_only=on'
from car_search_rag.anna_rag.chatbot import ioniq5_backend as b
out=HERE/'hybrid_local_rollout_v1'
old=json.loads((HERE/'m7_three_way_v1/results.json').read_text())
q=next(q for q in old if q['id']=='G21')
v=next(q['embedding'] for q in json.loads((HERE/'m7_mmr_v1/query_vectors.json').read_text()) if q['id']=='G21')
with patch.object(type(b.embeddings),'embed_query',return_value=v):
    packet=b.prepare_rag(q['question'])
children=[s for s in packet['sources'] if s['chunk_id']]
assert [s['chunk_id'] for s in children]==[s['chunk_id'] for s in q['top5']['hybrid']]
assert sum(s['cosine_rank'] is None for s in children)==2
assert all(isinstance(s['distance'],float) for s in children)
check={'verified_at':datetime.now(timezone.utc).isoformat(),'question_id':'G21',
       'lexical_only_selected':2,'distance_lookup_ok':True,'db_read_only':True}
(out/'lexical_only_integration.json').write_text(json.dumps(check,ensure_ascii=False,indent=2)+'\n')
print('TF-IDF 단독 후보 2개 거리 계산·부모 연결 검증 통과',flush=True)
# 실제 API 호출: 대화 저장 함수 chat() 대신 동일 파이프라인을 직접 호출합니다.
try:
    result=b.conversation_chain.invoke({'question':'충전 중인데 바로 멈추려면 차에서 어떤 버튼을 눌러야 해?', 'history':[], 'previous':{}})
    check={'verified_at':datetime.now(timezone.utc).isoformat(),'intent_action':result.get('intent',{}).get('action'),
           'answer_status':result['answer']['status'],'answer':result['answer']['text'],
           'retrieval':result.get('retrieval'), 'source_count':len(result.get('sources',[])),
           'cited_labels':result['answer'].get('cited_labels',[]),
           'tool_statuses':[c['status'] for c in result.get('tool_calls',[])],
           'db_read_only':True,'chat_sessions_written':False}
    (out/'answer_smoke.json').write_text(json.dumps(check,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in check.items() if k not in ['answer','retrieval']},ensure_ascii=False,indent=2))
    assert result['answer']['status']=='answered' and result.get('retrieval',{}).get('method')=='cosine_tfidf_rrf'
except Exception as error:
    # 비밀 접속 정보가 예외 메시지에 포함될 수 있어 유형만 출력합니다.
    print('실제 답변 검증 오류 유형:',type(error).__name__,flush=True)
    raise SystemExit(1)
