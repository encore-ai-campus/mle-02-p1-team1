"""검색 실험 결과를 독립 HTML 보고서로 표시합니다. 채점 결과는 변경하지 않습니다."""
import json
from html import escape as e
from pathlib import Path

HERE=Path(__file__).resolve().parent
OUT=HERE/'sonata_transfer_v1'

def main():
 s=json.loads((OUT/'summary.json').read_text());rs=json.loads((OUT/'results.json').read_text());cfg=json.loads((OUT/'config.json').read_text())
 def metric(m):return f"{m['hits']}/{m['count']} · {m['hit_at_5']:.1%}",f"{m['mrr_at_5']:.4f}"
 def score_table():
  body=''
  names={'A':'A · 상위 주제 키워드','B':'B · 같은 맥락의 구체적 질문','C':'C · 여러 단서가 섞인 질문','BC':'B+C · 구체적 질문','ABC':'전체 30문항','original24':'기존 24문항'}
  for group in names:
   scores=s['scores'][group];before=metric(scores['hybrid']);after=metric(scores['sonata'])
   body+=f"<tr><th>{names[group]}</th><td>{before[0]}</td><td>{after[0]}</td><td>{before[1]}</td><td>{after[1]}</td></tr>"
  return '<div class="overflow"><table><thead><tr><th>질문 유형</th><th>현재 Hit@5</th><th>소나타식 Hit@5</th><th>현재 MRR@5</th><th>소나타식 MRR@5</th></tr></thead><tbody>'+body+'</tbody></table></div>'
 def rank(m):return str(m['rank'])+'위' if m['rank'] else '5위 밖'
 def snippets(items):
  return ''.join(f"<li><b>PDF {x.get('page',x.get('pdf_pages'))} · {e(x['chunk_id'])}</b><pre>{e(x.get('text',x.get('page_content','')))}</pre></li>" for x in items)
 abc={r['id']:r for r in json.loads((HERE/'m7_abc_v1/results.json').read_text())}
 old={r['id']:r for r in json.loads((HERE/'m7_three_way_v1/results.json').read_text())}
 questions=''
 for r in rs:
  meta=r['metadata'];ref=abc.get(r['id'],old.get(r['id']))
  reason='정답이 후보에 없음' if not r['candidate_hit'] else ('후보에 있으나 최종 5개 밖' if not r['after']['hit'] else '최종 5개 안에서 정답 발견')
  keywords=' / '.join(meta['keyword_phrases'])+' · '+', '.join(meta['keyword_terms'])
  questions+=f'''<details class="question" data-group="{e(r['section'])}"><summary><span class="qid">{e(r['id'])}</span> {e(r['question'])}<small>현재 {rank(r['baseline']['hybrid'])} → 소나타식 {rank(r['after'])}</small></summary>
  <p><b>검색어:</b> {e(keywords)}</p><p><b>판정:</b> {reason} · 후보 {len(r['merged_ids'])}개 · 검색 실험 {r['elapsed_s']:.2f}초 · 리랭크 {'성공' if meta['success'] else '실패 후 원순서 사용'}</p>
  <p class="muted">정답 ID {len(r['relevant_chunk_ids'])}개. 최초 정답 순위의 역수가 RR@5이며, 위 5개 안에 없으면 0입니다.</p>
  <div class="two"><section><h3>현재 TF-IDF + RRF</h3><ol>{snippets(ref['top5']['hybrid'])}</ol></section><section><h3>소나타식 키워드 + LLM 리랭크</h3><ol>{snippets(r['top5'])}</ol></section></div></details>'''
 diagnostic=''
 for group in ('ABC','BC','original24'):
  d=s['diagnostics'][group];n=s['scores'][group]['sonata']['count']
  diagnostic+=f"<tr><th>{group} ({n}문항)</th><td>{d['vector10_hits']}</td><td>{d['union_hits']}</td><td>{s['scores'][group]['sonata']['hits']}</td><td>{d['mean_keyword_s']:.2f}초</td><td>{d['mean_rerank_s']:.2f}초</td><td>{d['mean_elapsed_s']:.2f}초</td></tr>"
 d=s['diagnostics']['ABC'];b=s['scores']['ABC']['hybrid'];a=s['scores']['ABC']['sonata']
 status=f"30문항 Hit@5 {b['hit_at_5']:.1%} → {a['hit_at_5']:.1%}, MRR@5 {b['mrr_at_5']:.4f} → {a['mrr_at_5']:.4f}"
 analysis=OUT/'analysis.html'
 content=analysis.read_text() if analysis.exists() else ''
 html=f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>아이오닉 · 소나타 검색 방식 비교</title>
 <style>*{{box-sizing:border-box}}body{{font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo",sans-serif;color:#24242b;background:#fff;margin:0;line-height:1.8}}main{{max-width:1160px;margin:0 auto;padding:64px 32px 110px}}h1{{font-size:34px;letter-spacing:-1px;line-height:1.4;margin:0 0 20px}}h2{{font-size:24px;margin:60px 0 20px}}h3{{font-size:18px}}.muted,small{{color:#74747e}}.lead{{font-size:20px}}.note{{padding:20px 24px;background:#f6f4ff;border-left:3px solid #7258dd;margin:24px 0}}.flow{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:24px 0}}.flow>div{{padding:20px;border:1px solid #e4e4eb;border-radius:10px}}.flow b{{display:block}}table{{border-collapse:collapse;width:100%;white-space:nowrap}}th,td{{padding:14px;text-align:left;border-bottom:1px solid #e8e8ed}}thead{{background:#f7f7fa}}.overflow{{overflow-x:auto}}.two{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-family:inherit;font-size:14px;line-height:1.7;background:#f7f7fa;padding:16px;max-height:380px;overflow:auto}}li b{{font-size:12px;overflow-wrap:anywhere}}details{{border-top:1px solid #e4e4eb;padding:20px 0}}summary{{cursor:pointer;font-weight:600}}summary small{{display:block;margin-left:50px;font-weight:400}}.qid{{color:#6548cc;margin-right:10px}}button{{background:white;border:1px solid #ddd;padding:9px 16px;border-radius:8px;cursor:pointer;margin-right:8px}}button.active{{background:#f2eeff;color:#6042cb;border-color:#b6a5ed}}@media(max-width:780px){{main{{padding:32px 18px}}.two,.flow{{grid-template-columns:1fr}}h1{{font-size:28px}}}}</style>
 <main><p class="muted">로컬 비교 실험 · 운영 미적용</p><h1>아이오닉 · 소나타 검색 방식 비교</h1><p class="lead">{status}</p>
 <p>같은 아이오닉 설명서 2,338개 청크, 같은 질문과 정답 청크 ID를 사용했습니다. 소나타 차량의 점수를 옮겨 적은 결과가 아니라, 소나타 검색 코드를 아이오닉 자료에 연결해 측정한 결과입니다.</p>
 <h2>검색 구조</h2><p><b>현재 아이오닉:</b> 코사인 50개 + Kiwi 명사 TF-IDF 50개 → 동등 가중 RRF → 최종 5개</p>
 <div class="flow"><div><b>1 · 두 검색을 병렬 실행</b>코사인 10개<br>LLM이 핵심 구문·단어 추출</div><div><b>2 · 키워드 10개</b>문구 포함 여부로 점수 계산<br>구문 3점 + 단어 1점</div><div><b>3 · 후보 합치기</b>청크 ID 중복 제거<br>최대 20개</div><div><b>4 · LLM 재정렬</b>질문과 본문을 함께 읽고<br>최종 5개 선택</div></div>
 <p class="muted">키워드 추출 gpt-6-luna · 리랭크 {e(cfg['rerank_model'])}. 기존 소나타 메서드를 그대로 호출하고 DB 테이블·row 필드만 아이오닉 형식에 연결했습니다.</p>
 <h2>같은 시험지로 비교한 결과</h2>{score_table()}
 <div class="note">A는 넓은 목차 주제의 관련성을 평가하므로 정답 후보가 많습니다. 구체적 질문의 성능은 B+C도 함께 보세요. 기존 24문항 중 20개는 B/C에 재배치했고, 나머지 4개도 별도로 실행하여 24문항 기준 비교를 유지했습니다. 새 A 라벨 및 재분류는 추가 사람 검수 전 상태입니다.</div>
 {content}
 <h2>후보 확보와 추가 처리 시간</h2><div class="overflow"><table><thead><tr><th>평가셋</th><th>벡터10에 정답 있음</th><th>통합 후보에 정답 있음</th><th>최종5 성공</th><th>키워드 AI 평균</th><th>리랭크 AI 평균</th><th>검색 실험 평균</th></tr></thead><tbody>{diagnostic}</tbody></table></div>
 <p class="muted">후보 건수는 문서 개수가 아니라 정답 청크를 포함한 질문 수입니다. 질문 임베딩·벡터 후보는 고정 캐시를 재사용했으므로 측정 시간에 해당 API·DB 조회, 의도 판단, 답변 생성, 대화 저장, UI 표시 시간은 포함되지 않습니다. 운영 전체 응답 시간과 비교하면 안 됩니다.</p>
 <p>30문항 키워드 분기 실패 {d['keyword_failures']}건 · 리랭크 실패 {d['rerank_failures']}건. LLM은 문항별 1회 평가했으며 재시도는 소나타 기존 정책을 따랐습니다. 이번 정답지에 맞춰 프롬프트나 설정을 바꾸지 않았습니다.</p>
 <h2>소나타의 높은 점수를 비교할 때의 기준</h2><p>최근 소나타 UI 기록의 Hit@5 94%는 PDF 페이지 기준입니다. 이 실험은 기존 아이오닉과 동일하게 청크 ID가 일치해야 성공으로 처리했습니다. 소나타의 별도 50문항 검색기 평가에는 청크 기준 리랭크 Hit@5 88%라는 다른 기록도 있습니다. 질문·정답 범위·코퍼스가 다르므로 차량 간 점수 자체로 검색기 우열을 판단하지 않습니다.</p>
 <h2>문항별 검색 근거</h2><div id="filters"><button class="active" data-filter="all">전체</button><button data-filter="A">A</button><button data-filter="B">B</button><button data-filter="C">C</button><button data-filter="supplement">기존 추가 4개</button></div>{questions}
 <h2>재현 자료</h2><p>같은 폴더의 summary.json · results.json · config.json · dataset_snapshot.json · sonata_service_snapshot.py · sonata_sql_snapshot.sql · experiment_snapshot.py에 설정과 결과를 보존했습니다. 운영 코드·배포·DB 저장 자료는 변경하지 않았습니다. 초기 연결 코드 오류 실행은 별도 실패 기록으로 보존하고 점수에서 제외했습니다.</p></main>
 <script>document.querySelectorAll('#filters button').forEach(b=>b.onclick=()=>{{document.querySelectorAll('#filters button').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('.question').forEach(x=>x.hidden=b.dataset.filter!=='all'&&x.dataset.group!==b.dataset.filter)}});</script></html>'''
 (OUT/'report.html').write_text(html)
 print(OUT/'report.html')

if __name__=='__main__':main()
