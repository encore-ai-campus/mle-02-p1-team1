import os,json
from pathlib import Path
from unittest.mock import patch
from dotenv import load_dotenv
root=Path(__file__).resolve().parents[5];load_dotenv(root/'.env',override=False)
os.environ['PGOPTIONS']='-c default_transaction_read_only=on'
from car_search_rag.anna_rag.chatbot import ioniq5_backend as b
base=root/'src/car_search_rag/anna_rag/evaluation'
questions=json.loads((base/'m7_three_way_v1/results.json').read_text())
vectors={x['id']:x['embedding'] for x in json.loads((base/'m7_mmr_v1/query_vectors.json').read_text())}
b.hybrid_search.warmup();checks=[]
for qid in ['G03','G06','G07','G09','G17','G21']:
    q=next(q for q in questions if q['id']==qid)
    with patch.object(type(b.embeddings),'embed_query',return_value=vectors[qid]):
        packet=b.prepare_rag(q['question'])
    children=[s for s in packet['sources'] if s['chunk_id']]
    assert [s['chunk_id'] for s in children]==[s['chunk_id'] for s in q['top5']['hybrid']]
    images={};seen=set();blocks=[];omitted=[]
    with b.db.connect(camel_case_keys=False) as conn:
        for s in children:
            meta=conn.execute('SELECT image_id FROM anna_rag.chunks WHERE chunk_id=%s',(s['chunk_id'],)).fetchone()
            key=(s['document_id'],s['section_id'])
            parent=conn.execute('SELECT s.*,m.source_file FROM anna_rag.sections s JOIN anna_rag.manuals m USING(document_id) WHERE s.document_id=%s AND s.section_id=%s',key).fetchone()
            if key not in seen:
                seen.add(key);label=f'P{len(seen)}'
                block=f"[{label}] {parent['title']} / {parent['source_file']} / PDF {parent['pdf_pages']}\n{parent['full_text']}"
                if len(b.encoding.encode('\n\n'.join(blocks+[block]),disallowed_special=()))<=b.parent_token_budget:blocks.append(block)
                else:omitted.append({'section_id':key[1],'title':parent['title']})
            rows=conn.execute('''SELECT i.* FROM anna_rag.section_images si JOIN anna_rag.images i USING(document_id,image_id)
              WHERE si.document_id=%s AND si.section_id=%s AND (i.image_id=%s OR i.pdf_page=ANY(%s))
              ORDER BY CASE WHEN i.image_id=%s THEN 0 ELSE 1 END,i.pdf_page,i.image_id''',(*key,meta['image_id'],s['pdf_pages'],meta['image_id'])).fetchall()
            for row in rows:
                ik=(row['document_id'],row['image_id'])
                images.setdefault(ik,{**row,'source_labels':[]})['source_labels'].append(s['label'])
    assert packet['image_candidates']==list(images.values()),qid
    assert packet['parent_context']=='\n\n'.join(blocks),qid
    assert packet['omitted_parents']==omitted,qid
    checks.append({'id':qid,'same_top5':True,'same_parents_and_budget':True,'same_images_and_labels':True,'image_count':len(images)})
print(json.dumps(checks,ensure_ascii=False),flush=True)
(root/'tmp/ioniq_latency').mkdir(parents=True,exist_ok=True)
(root/'tmp/ioniq_latency/context_verification.json').write_text(json.dumps(checks,indent=2))
