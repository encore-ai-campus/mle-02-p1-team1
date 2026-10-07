import os,json
from pathlib import Path
import numpy as np
import psycopg
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
root=Path(__file__).resolve().parents[5];p=root/'src/car_search_rag/anna_rag/evaluation/m6_baseline_v1';load_dotenv(root/'.env')
r=[q for q in json.loads((p/'results.json').read_text()) if not q['hit_at_5']];d=json.loads((p/'diagnostics.json').read_text());doc=json.loads((p/'dataset_snapshot.json').read_text())['document_id']
model=OpenAIEmbeddings(model='text-embedding-3-small',dimensions=1536,request_timeout=60,max_retries=2);vs=model.embed_documents([q['question'] for q in r]);checks=[]
with psycopg.connect(os.environ['DB_URL'],options='-c default_transaction_read_only=on') as c:
 rows=c.execute('SELECT chunk_id,embedding::text FROM anna_rag.chunks WHERE document_id=%s AND embedding_model=%s AND embedding_dimension=1536 ORDER BY chunk_id',(doc,'text-embedding-3-small')).fetchall();mat=np.array([json.loads(x[1]) for x in rows]);mat/=np.linalg.norm(mat,axis=1,keepdims=True)
 for q,v in zip(r,vs):
  sql=c.execute('SELECT chunk_id FROM anna_rag.chunks WHERE document_id=%s AND embedding_model=%s AND embedding_dimension=1536 ORDER BY embedding <=> %s::vector LIMIT 5',(doc,'text-embedding-3-small',json.dumps(v))).fetchall();a=np.asarray(v);a/=np.linalg.norm(a);order=np.argsort(-(mat@a));ids=[rows[j][0] for j in order[:5]]
  checks.append({'id':q['id'],'same_query_vector_sql_numpy_top5_equal':ids==[x[0] for x in sql]})
d['same_vector_sql_numpy_checks']=checks
(p/'diagnostics.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
print('Same query vector: SQL and exact NumPy top5 match',sum(x['same_query_vector_sql_numpy_top5_equal'] for x in checks),'/',len(checks))
