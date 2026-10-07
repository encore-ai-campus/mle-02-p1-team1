"""싼타페 검색 점수·부모 선택 규칙을 아이오닉 A/B/C 30문항에 읽기 전용으로 비교합니다.

아이오닉에는 안내도 항목/자료 유형 메타데이터가 없어 목적 라우팅은 이식하지
않습니다. 기존 운영 코드, 정답지, DB는 변경하지 않고 저장된 질문 벡터를 씁니다.
"""
import argparse
import hashlib
import html
import json
import os
import re
import sys
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace

from evaluate_retrieval import HERE, ROOT, measure

sys.path.insert(0, str(ROOT / 'src'))

LABELS = {
    'cosine': '문장 임베딩·코사인',
    'rrf': '키워드·문장 임베딩 RRF',
    'sonata': '현재 아이오닉: AI 키워드 + LLM 리랭크',
    'char_hybrid': '싼타페 점수 결합만 · 청크 상위 5개',
    'char_bonus': '싼타페 점수 결합 + 표현 가산점 · 청크 상위 5개',
    'parent_hybrid': '싼타페 점수 결합 + 부모별 대표 선택',
    'parent_bonus': '싼타페 점수 결합 + 가산점 + 부모별 대표 선택',
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def run(out):
    import numpy as np
    import psycopg
    from dotenv import load_dotenv
    from car_search_rag.zzong_santafe_lag import retrieval, specific_terms

    if out.exists():
        raise FileExistsError('완료/진행 중인 실험을 덮어쓰지 않습니다.')
    raw = (HERE / 'golden_abc_v1/dataset.json').read_bytes()
    dataset = json.loads(raw)
    baseline = json.loads((HERE / 'm7_abc_v1/summary.json').read_text())
    qraw = (HERE / 'm7_abc_v1/query_vectors.json').read_bytes()
    queries = {q['id']: q['embedding'] for q in json.loads(qraw)}
    old = {r['id']: r for r in json.loads((HERE / 'm7_abc_v1/results.json').read_text())}
    sonata_rows = json.loads((HERE / 'sonata_transfer_v1/results.json').read_text())
    sonata = {r['question']: r for r in sonata_rows if r['section'] in {'A', 'B', 'C'}}
    load_dotenv(ROOT / '.env', override=False)
    with psycopg.connect(os.environ['DB_URL'], connect_timeout=10,
                         options='-c default_transaction_read_only=on') as conn:
        corpus = conn.execute('''SELECT chunk_id,section_id,chunk_type,pdf_pages,page_content,
            embedding_model,embedding_dimension,embedding::text FROM anna_rag.chunks
            WHERE document_id=%s ORDER BY chunk_id''', (dataset['document_id'],)).fetchall()
        sections = conn.execute('''SELECT section_id,title,full_text,pdf_pages FROM anna_rag.sections
            WHERE document_id=%s ORDER BY section_id''', (dataset['document_id'],)).fetchall()
    corpus_hash = digest(json.dumps(corpus, ensure_ascii=False).encode())
    assert corpus_hash == baseline['corpus_sha256']
    assert digest(raw) == baseline['dataset_sha256']
    assert len(dataset['questions']) == 30 and len(corpus) == 2338
    ids = [r[0] for r in corpus]
    position = {cid: i for i, cid in enumerate(ids)}
    parent_of = {r[0]: r[1] for r in corpus}
    parents = [{'content': body, 'raw_text': body, 'image_parts': [],
                'metadata': {'record_id': sid, 'title': title, 'content_type': 'unclassified',
                             'verification_status': 'not_used_for_ranking'}}
               for sid, title, body, pages in sections]
    chunks = [{'content': r[4], 'metadata': {'record_id': r[0], 'parent_record_id': r[1]}}
              for r in corpus]
    matrix = np.array([json.loads(r[7]) for r in corpus], dtype=np.float32)
    matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)
    assert all(parent_of[cid] in {p['metadata']['record_id'] for p in parents} for cid in ids)

    # 싼타페 원본은 안내도 목록이 비어 있으면 TF-IDF fit이 실패합니다.
    # 실험 복사본에서만 빈 색인 자리를 마련합니다. navigation_rows는 그대로 빈 목록이므로
    # 가짜 안내도 후보/점수는 만들어지지 않습니다. 목적 라우팅도 명시적으로 끕니다.
    source_path = Path(retrieval.__file__)
    source = source_path.read_text()
    needle = '[row["index_text"] for row in navigation_rows]'
    assert source.count(needle) == 1
    adapted = source.replace(needle, needle + ' or ["empty_navigation_index"]')
    namespace = {'__name__': 'car_search_rag.zzong_santafe_lag.transfer_experiment',
                 '__package__': 'car_search_rag.zzong_santafe_lag'}
    exec(compile(adapted, str(source_path), 'exec'), namespace)
    out.mkdir(parents=True)
    config = {
        'started_at': datetime.now(timezone.utc).isoformat(), 'question_count': 30,
        'dataset_sha256': digest(raw), 'corpus_sha256': corpus_hash,
        'parents_sha256': digest(json.dumps(sections, ensure_ascii=False).encode()),
        'query_vectors_sha256': digest(qraw), 'corpus_chunks': len(corpus), 'parents': len(parents),
        'source_sha256': digest(source.encode()), 'specific_terms_sha256': digest(Path(specific_terms.__file__).read_bytes()),
        'settings': {'semantic_weight': .5, 'keyword_weight': .5, 'char_ngram_range': [2, 4],
                     'specific_bonus_max': .15, 'top_k': 5, 'use_routing': False,
                     'normalization': 'float32 unit vectors; Santafe same text normalization',
                     'ties': 'stable chunk_id order; stable section_id order for parent results'},
        'packages': {name: version(name) for name in ['numpy', 'scikit-learn']},
        'limits': [
            '싼타페 전체 운영 파이프라인의 완전 이식이 아닌 검색 점수·부모 선택 규칙 비교.',
            '아이오닉에 안내도 번호·표 자료 유형 메타데이터가 없어 유형 우선/안내도 이름 검색 제외.',
            '싼타페의 검색 전 용어 치환·복합 질문 분리, 검색 후 근거 검증·후보 회복·답변 생성 제외.',
            '설명서 2338청크를 그대로 유지. 부모 본문==제목 필터는 추가하지 않음.',
            '부모 일치는 같은 소제목의 다른 청크도 맞다고 보는 완화 지표이며 기존 청크 정답 채점을 대체하지 않음.',
            '과거 코사인/RRF/LLM 리랭크 결과를 같은 질문·코퍼스로 비교. LLM 방식은 이번에 재실행하지 않음.',
            '저장된 질문 임베딩 재사용. API 호출·DB 쓰기·운영 코드 변경 없음.',
            '시간은 메모리 내 검색만 측정하며 DB·임베딩·답변 생성·전체 응답 시간은 제외.',
            '동일 개발용 A/B/C 30문항 1회 실험. 결과를 보고 가중치나 정답을 조정하지 않음.',
        ] + dataset['limitations'],
    }
    write_json(out / 'config.json', config)
    (out / 'dataset_snapshot.json').write_bytes(raw)
    (out / 'experiment_snapshot.py').write_bytes(Path(__file__).read_bytes())
    (out / 'santafe_retrieval_snapshot.py').write_text(source)
    (out / 'santafe_specific_terms_snapshot.py').write_bytes(Path(specific_terms.__file__).read_bytes())
    (out / 'santafe_retrieval_adapted.py').write_text(adapted)
    started = perf_counter()
    engine = namespace['SearchEngine'](parents, chunks, matrix, None, SimpleNamespace(count=len, budget=8191))
    norm = lambda text: ''.join(re.findall(r'[가-힣A-Za-z0-9ℓ+\-]+', text)).lower()
    index, lexical = retrieval.make_character_index([norm(r[4]) for r in corpus])
    matcher = specific_terms.SpecificTermMatcher(parents)
    setup_s = perf_counter() - started
    records = []
    for q in dataset['questions']:
        vector = np.array(queries[q['id']], dtype=np.float32)
        vector /= np.linalg.norm(vector)
        started = perf_counter()
        semantic = matrix @ vector
        keywords = (lexical @ index.transform([norm(q['question'])]).T).toarray().ravel()
        combined = .5 * semantic + .5 * keywords
        specific = matcher.bonuses(q['question'])
        bonuses = np.array([specific['by_record_id'][parent_of[cid]]['bonus'] for cid in ids])
        char_order = sorted(range(len(ids)), key=lambda i: -float(combined[i]))
        bonus_order = sorted(range(len(ids)), key=lambda i: -(float(combined[i]) + float(bonuses[i])))
        hits = engine.rank(q['question'], vector, top_k=5, use_routing=False, use_specific_terms=False)
        bonus_hits = engine.rank(q['question'], vector, top_k=5, use_routing=False, use_specific_terms=True)
        # 본문과 메타데이터 대응/수식 구현이 실제 싼타페 함수와 일치하는지 독립 확인합니다.
        for values, use_bonus in [(hits, False), (bonus_hits, True)]:
            for hit in values:
                i = position[hit['matched_chunk']['metadata']['record_id']]
                assert abs(hit['score'] - (float(combined[i]) + (float(bonuses[i]) if use_bonus else 0))) < 1e-6
        elapsed = perf_counter() - started
        previous = sonata[q['question']]
        assert set(previous['relevant_chunk_ids']) == set(q['relevant_chunk_ids'])
        rankings = {
            'cosine': [r['chunk_id'] for r in old[q['id']]['top5']['cosine']],
            'rrf': [r['chunk_id'] for r in old[q['id']]['top5']['hybrid']],
            'sonata': [r['chunk_id'] for r in previous['top5']],
            'char_hybrid': [ids[i] for i in char_order[:5]],
            'char_bonus': [ids[i] for i in bonus_order[:5]],
            'parent_hybrid': [h['matched_chunk']['metadata']['record_id'] for h in hits],
            'parent_bonus': [h['matched_chunk']['metadata']['record_id'] for h in bonus_hits],
        }
        gold = q['relevant_chunk_ids']
        parent_gold = list({parent_of[cid] for cid in gold})
        def detail(cid):
            i = position[cid]
            return {'chunk_id': cid, 'section_id': parent_of[cid], 'pdf_pages': corpus[i][3],
                    'text': corpus[i][4], 'semantic': float(semantic[i]), 'keyword': float(keywords[i]),
                    'combined': float(combined[i]), 'specific_bonus': float(bonuses[i]),
                    'specific_terms': specific['by_record_id'][parent_of[cid]]['matched_terms']}
        metrics = {name: measure(ranking, gold) for name, ranking in rankings.items()}
        assert metrics['cosine'] == old[q['id']]['metrics']['cosine']
        assert metrics['rrf'] == old[q['id']]['metrics']['hybrid']
        assert metrics['sonata'] == previous['after']
        records.append({'id': q['id'], 'section': q['section'], 'question': q['question'], 'relevant_chunk_ids': gold,
                        'relevant_parent_ids': parent_gold, 'metrics': metrics,
                        'parent_metrics': {m: measure([parent_of[c] for c in r], parent_gold) for m, r in rankings.items()},
                        'top5': {m: [detail(cid) for cid in ranking] for m, ranking in rankings.items()},
                        'gold_diagnostics': [detail(cid) for cid in gold], 'all_variants_memory_search_s': elapsed})
        print(q['id'], {m: s['rank'] for m, s in metrics.items()}, flush=True)
    def aggregate(field, method, selected=records):
        values = [r[field][method] for r in selected]
        return {'hits': sum(v['hit'] for v in values), 'count': len(values),
                'hit_at_5': sum(v['hit'] for v in values)/len(values), 'mrr_at_5': sum(v['rr'] for v in values)/len(values)}
    summary = {'status': 'complete', 'finished_at': datetime.now(timezone.utc).isoformat(),
               'scores': {m: aggregate('metrics', m) for m in LABELS},
               'section_scores': {section: {m: aggregate('metrics', m, [r for r in records if r['section'] in section]) for m in LABELS} for section in ['A', 'B', 'C', 'BC']},
               'parent_scores': {m: aggregate('parent_metrics', m) for m in LABELS},
               'diagnostics': {m: {
                   'gained_vs_current': [r['id'] for r in records if r['metrics'][m]['hit'] > r['metrics']['sonata']['hit']],
                   'lost_vs_current': [r['id'] for r in records if r['metrics'][m]['hit'] < r['metrics']['sonata']['hit']],
                   'parent_only_hit': [r['id'] for r in records if r['parent_metrics'][m]['hit'] and not r['metrics'][m]['hit']],
               } for m in LABELS}, 'setup_seconds': setup_s, 'limits': config['limits']}
    write_json(out / 'results.json', records)
    write_json(out / 'summary.json', summary)
    esc = html.escape
    rows = ''.join(f'<tr><td>{esc(label)}</td><td>{summary["scores"][m]["hits"]}/30</td>'
                   f'<td>{summary["scores"][m]["hit_at_5"]:.2%}</td><td>{summary["scores"][m]["mrr_at_5"]:.4f}</td>'
                   f'<td>{summary["parent_scores"][m]["hit_at_5"]:.2%}</td></tr>' for m,label in LABELS.items())
    details = ''
    for r in records:
        details += f'<details><summary>{r["id"]} · {esc(r["question"])}</summary>'
        details += '<p>정답 청크: '+esc(', '.join(r['relevant_chunk_ids']))+'</p>'
        for m in LABELS:
            details += f'<h3>{esc(LABELS[m])} · 첫 정답 {r["metrics"][m]["rank"] or "없음"}</h3><ol>'
            for item in r['top5'][m]:
                correct = ' ✓ 정답' if item['chunk_id'] in r['relevant_chunk_ids'] else ''
                details += f'<li><b>{esc(item["chunk_id"])}{correct}</b><p>{esc(item["text"])}</p></li>'
            details += '</ol>'
        details += '</details>'
    report = '<!doctype html><html lang="ko"><meta charset="utf-8"><title>싼타페 검색 방식 · 아이오닉 비교</title>'
    report += '<style>body{max-width:1100px;margin:50px auto;padding:24px;font-family:system-ui,sans-serif;color:#222;line-height:1.7}table{border-collapse:collapse;width:100%}td,th{padding:12px;border-bottom:1px solid #ddd;text-align:left}details{border:1px solid #ddd;margin:14px 0;padding:18px}summary{cursor:pointer;font-weight:650}li p{white-space:pre-wrap}h1{font-size:30px}h2{margin-top:40px}</style>'
    report += '<h1>싼타페 검색 방식의 아이오닉 적용 비교</h1><p>동일 아이오닉 A/B/C 30문항 · 2,338청크 · 기존 질문 임베딩 재사용 · 운영 미적용</p>'
    report += '<p>주 지표는 기존 정답 청크 ID 기준입니다. 마지막 열은 같은 부모에 도달했는지를 보는 완화된 보조 지표입니다.</p>'
    report += '<table><tr><th>방식</th><th>성공 문항</th><th>Hit@5</th><th>MRR@5</th><th>부모 Hit@5 · 보조</th></tr>'+rows+'</table>'
    for section, scores in summary['section_scores'].items():
        report += '<h2>'+section+' 섹션</h2><table><tr><th>방식</th><th>Hit@5</th><th>MRR@5</th></tr>'
        report += ''.join(f'<tr><td>{esc(LABELS[m])}</td><td>{v["hit_at_5"]:.2%}</td><td>{v["mrr_at_5"]:.4f}</td></tr>' for m,v in scores.items()) + '</table>'
    report += '<h2>실험 범위와 한계</h2><ul>'+''.join('<li>'+esc(n)+'</li>' for n in config['limits'])+'</ul>'
    report += '<h2>문항별 검색 결과</h2>'+details+'</html>'
    (out / 'report.html').write_text(report)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run(args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as error:
        print('실험 중단:', type(error).__name__, flush=True)
        raise SystemExit(1)
