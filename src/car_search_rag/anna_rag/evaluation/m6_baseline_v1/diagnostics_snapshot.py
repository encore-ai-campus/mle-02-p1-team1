import os,json,hashlib
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
root=Path(__file__).resolve().parents[5]; base=root/'src/car_search_rag/anna_rag/evaluation/m6_baseline_v1'
load_dotenv(root/'.env')
r=json.loads((base/'results.json').read_text()); dataset=json.loads((base/'dataset_snapshot.json').read_text())
with psycopg.connect(os.environ['DB_URL'],options='-c default_transaction_read_only=on',row_factory=dict_row) as conn:
 corpus=conn.execute('SELECT chunk_id,section_id,page_content,embedding::text,embedding_model,embedding_dimension FROM anna_rag.chunks WHERE document_id=%s ORDER BY chunk_id',(dataset['document_id'],)).fetchall()
 sections=conn.execute('SELECT section_id,full_text FROM anna_rag.sections WHERE document_id=%s',(dataset['document_id'],)).fetchall()
 indexes=conn.execute("SELECT indexname,indexdef FROM pg_indexes WHERE schemaname='anna_rag' AND tablename='chunks'").fetchall()
print('Read corpus',len(corpus),'and parent sections',len(sections),flush=True)
lookup={x['chunk_id']:x for x in corpus}; vectors=np.array([json.loads(x['embedding']) for x in corpus]); normalized=vectors/np.linalg.norm(vectors,axis=1,keepdims=True)
sample_ids=sorted({cid for q in r for cid in q['relevant_chunk_ids']}|{q['top5'][0]['chunk_id'] for q in r if not q['hit_at_5']})
model=OpenAIEmbeddings(model='text-embedding-3-small',dimensions=1536,request_timeout=60,max_retries=2)
fresh=np.array(model.embed_documents([lookup[cid]['page_content'] for cid in sample_ids])); fresh/=np.linalg.norm(fresh,axis=1,keepdims=True)
comparison=[]
for cid,v in zip(sample_ids,fresh):
 scores=normalized@v; idx=next(i for i,c in enumerate(corpus) if c['chunk_id']==cid); best=int(np.argmax(scores))
 comparison.append({'chunk_id':cid,'same_content_vector_cosine':float(scores[idx]),'nearest_stored_chunk_id':corpus[best]['chunk_id'],'nearest_cosine':float(scores[best]),'self_rank':int(np.count_nonzero(scores>scores[idx])+1)})
print('Compared fresh vectors',len(comparison),'cosine range',min(x['same_content_vector_cosine'] for x in comparison),max(x['same_content_vector_cosine'] for x in comparison),flush=True)
misses=[q for q in r if not q['hit_at_5']]
qvecs=np.array(model.embed_documents([q['question'] for q in misses])); qvecs/=np.linalg.norm(qvecs,axis=1,keepdims=True)
checks=[]
for q,v in zip(misses,qvecs):
 order=np.argsort(-(normalized@v)); gold=set(q['relevant_chunk_ids']); rank=next(i for i,j in enumerate(order,1) if corpus[j]['chunk_id'] in gold)
 top=[corpus[j]['chunk_id'] for j in order[:5]]
 overlap=set(q['relevant_section_ids'])&{t['section_id'] for t in q['top5']}
 checks.append({'id':q['id'],'exact_cosine_gold_rank':rank,'baseline_gold_rank':q['first_relevant_rank_full'],'exact_top5_matches_baseline':top==[t['chunk_id'] for t in q['top5']],'gold_parent_sections_reached':sorted(overlap),'unique_top5_sections':len({t['section_id'] for t in q['top5']})})
 print(q['id'],'exact rank',rank,'same top5',checks[-1]['exact_top5_matches_baseline'],'parent overlap',sorted(overlap),flush=True)
out={'checked_at':datetime.now(timezone.utc).isoformat(),'method':'Read-only DB snapshot; regenerate current page_content embeddings for all golden chunks plus failed-question top-1 chunks; compare cosine; independently rank failed raw questions by NumPy exact cosine over stored vectors. No DB writes.','sample_count':len(comparison),'corpus_count':len(corpus),'index_definitions':indexes,'embedding_checks':comparison,'failed_query_checks':checks}
(base/'diagnostics.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print('Saved diagnostics.json',flush=True)
