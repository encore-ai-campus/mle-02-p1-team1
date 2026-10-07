"""저장된 추가 평가를 사람이 읽은 판정과 연결해 보고서·CSV로 정리합니다."""
import csv
import json
from collections import Counter
from pathlib import Path

FOLDER=Path(__file__).resolve().parent
OUTPUT=FOLDER/'evaluation_30_results'
# 번호|첫 관련 후보 순위|최종 응답 판정|표시 근거|판정 이유
# A는 주제와 관련된 위치 안내나 여러 원문 후보도 허용합니다. 구체 답을 요구하는 B/C와 다릅니다.
LABELS='''A01|1|실패|부적절|스마트 키 후보가 검색 1위였으나 화면에는 스마트 키 설명이 없는 차량 내부 II 선택. 생성 검증 후 무관한 원문 발췌로 복귀.
A02|1|통과|적절|상위 주제 질문에 파워 테일게이트 작동·설정 등 관련 원문 선택지를 제공. 구체 조작 답변을 생성한 것은 아님.
A03|1|통과|적절|주제와 관련된 실외 미러 위치 안내를 정확히 제공. A의 폭넓은 관련 문서 허용 기준 적용.
A04|1|통과|적절|주제와 관련된 메모리 버튼 위치 안내를 정확히 제공. 저장 방법 질문이었다면 부족하나 A에서는 허용.
A05|1|통과|적절|선루프 작동·초기화·실내 공기 순환 등 관련 원문 선택지를 제공.
A06|1|통과|적절|안전벨트 착용 및 사용 주의사항을 근거와 함께 생성.
A07|1|통과|적절|회생 제동 시스템·사용·설정 관련 원문 선택지를 제공.
A08|1|통과|적절|Auto Hold 관련 원문 링크와 펼침 영역 제공. 조작 답변은 미검토 보류.
A09|1|통과|적절|타이어 위치 안내를 근거와 함께 제공. A의 관련 문서 허용 기준 적용.
A10|1|부분|부분 적절|무선 충전 위치가 포함된 내부 안내도이나 24개 부품 전체 나열로 주제에 집중하지 못함. 생성 검증 후 원문 발췌.
B01|4|실패|부적절|건전지 교체 문서는 4위에 있었으나 엔진오일 표·각주가 선택됨. CR2450 1개를 답하지 못함.
B02|1|실패|적절|열림 높이 설정 문서를 찾아 후보로 제시했으나 구체 설정 방법은 미검토 보류.
B03|1|통과|적절|웰컴 미러/라이트 설정과 도어 잠금 시 접힘을 직접 안내. 표시 메뉴 이름은 도어 잠금 해제로 줄여 썼음.
B04|1|실패|부적절|검색 1위는 230쪽 저장 방법이나 화면에는 초기화·일반 소개만 제시. 저장과 초기화의 의도 구분 실패.
B05|1|실패|부적절|중지 방법이 있는 슬라이드·틸트 자료를 검색했으나 일반 선루프·초기화 자료만 화면 후보로 표시.
B06|1|실패|부적절|높이 조절이 포함된 원문을 검색했으나 일반 착용 원문으로 대체. 조절 버튼 동작을 답하지 못함.
B07|1|실패|부적절|회생 단계 조절 문서를 검색했으나 패들 위치 안내도로 대체. 왼쪽 패들·ECO 조건 누락.
B08|1|실패|적절|Auto Hold 근거는 맞으나 출발 방법을 답하지 않고 미검토 보류.
B09|1|실패|부분 적절|차가운 상태 점검 근거는 검색 1위지만 일반 공기압 점검 주의 원문을 선택. 질문의 온도 조건에 답하지 못함.
B10|2|실패|적절|무선 충전 원문은 맞으나 주황색 점멸의 대응 안내를 미검토 보류.
C01|2|실패|적절|시동 버튼을 스마트 키로 직접 누르는 근거가 검색됨. 관련 시동 후보도 표시했으나 실제 조작 안내는 보류.
C02|0|실패|확인 불가|낮은 차고·트렁크 높이 목적을 함께 해석하지 못함. 상위 5개에 파워 테일게이트 높이 설정 근거가 없고 화면 후보도 없음.
C03|5|실패|부적절|실외 미러가 5위에 검색됐으나 무관한 차량 내부 II 선택. 생성 검증 후 무관한 원문 발췌로 복귀.
C04|1|실패|부적절|메모리 재생 방법은 1위지만 실외 미러 조절 원문 선택. 좌석·미러 동시 복원 목적에 답하지 못함.
C05|1|실패|확인 불가|루프바 적재 시 선루프 금지 근거는 1위에 있으나 화면 원문 후보 없음. 지붕 유리 표현과 기능 연결 실패.
C06|1|실패|부적절|높이 조절 근거가 1위지만 일반 안전벨트 착용 원문 선택. 목 접촉·높이 낮추기·버튼 조작을 함께 답하지 못함.
C07|1|실패|부분 적절|충전량에 따른 제한 경고가 1위이나 다른 사용 제한 자료를 선택하고 답변 보류. 표시 PDF 402·397·398쪽의 페이지 연결도 확인 필요.
C08|1|실패|적절|Auto Hold 세차기 주의 근거는 맞지만 기능 해제 여부의 답변을 미검토 보류.
C09|2|실패|적절|주행 직후 공기압 조정 금지 근거를 2위에 찾고 표시했으나 실제 답변은 보류.
C10|1|실패|적절|무선 충전 금속·발열 주의 근거는 1위에 찾았으나 구체 점검 안내는 미검토 보류.'''


def finalize():
    """원시 실행 결과를 보존하고 잠정 판정 파일을 별도로 저장합니다."""
    raw=json.loads((OUTPUT/'results.json').read_text(encoding='utf-8'))
    if not raw.get('complete') or len(raw['results'])!=30:
        raise ValueError('30문항 실행 완료 전에는 최종 보고서를 만들지 않습니다.')
    labels={}
    for line in LABELS.splitlines():
        cid,rank,grade,source,note=line.split('|'); labels[cid]=(int(rank),grade,source,note)
    if len(labels)!=30:
        raise ValueError('30문항 판정을 모두 작성해야 합니다.')
    rows=[]
    for case in raw['results']:
        initial=case['initial_packet']; final=case.get('generated_packet',initial)
        rank,grade,source,note=labels[case['case_id']]
        candidates=(case['search_results'][0]['candidates'] if case['search_results'] else [])[:5]
        native=final.get('native_result',{})
        rows.append(dict(case_id=case['case_id'],group=case['group'],question=case['question'],
                         semantic_contexts=case['semantic_contexts'],expected=case['expected'],reference_pages=case['reference_pages'],
                         first_relevant_rank=rank or None,hit5=bool(1<=rank<=5),
                         overall=grade,displayed_source_grade=source,note=note,
                         initial_status=initial.get('native_status'),final_status=final.get('native_status'),
                         generation_attempted=case['generation_attempted'],
                         generation_error_type=native.get('generation_error_type'),
                         generation_diagnostic=native.get('generation_diagnostics',{}).get('code'),
                         generation_llm_called=native.get('llm_called',False) if case['generation_attempted'] else False,
                         initial_text=initial['answer']['text'],final_text=final['answer']['text'],
                         displayed_sources=final.get('sources',[]),
                         top5=[dict(rank=i+1,title=c['title'],parent_record_id=c['parent_record_id']) for i,c in enumerate(candidates)],
                         search_calls=len(case['search_results']),seconds=case['seconds'],
                         annotator='Codex 원본·응답 대조 잠정 판정',human_confirmed=False))
    groups={g:dict(Counter(r['overall'] for r in rows if r['group']==g)) for g in 'ABC'}
    metrics={g:dict(n=10,hit5=sum(r['hit5'] for r in rows if r['group']==g)/10,
                    mrr5=sum(1/r['first_relevant_rank'] if r['hit5'] else 0 for r in rows if r['group']==g)/10) for g in 'ABC'}
    summary=dict(completed=30,counts=dict(Counter(r['overall'] for r in rows)),groups=groups,
                 search_calls=sum(r['search_calls'] for r in rows),
                 generation_attempts=sum(r['generation_attempted'] for r in rows),
                 generated_answers=sum(r['final_status']=='generated_answer' for r in rows),
                 generation_fallbacks=sum(r['generation_attempted'] and r['final_status']!='generated_answer' for r in rows),
                 failure_count=len(json.loads((OUTPUT/'failures.json').read_text(encoding='utf-8'))),
                 provisional_search_metrics=metrics,elapsed_seconds=raw['elapsed_seconds'],
                 human_confirmed=False,db_written=False,
                 rubric_note='A는 관련 주제 문서·위치·원문 선택지를 허용. B/C는 목적에 대한 답변이 필요. 미검토 보류는 검색 성공과 응답 실패로 분리.',
                 metrics_note='상위 5개 부모 후보를 원본과 대조한 Codex 잠정 관련성. A는 여러 관련 문서를 허용. 사용자 확정 골든셋 점수가 아님.')
    (OUTPUT/'graded_results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUTPUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    with (OUTPUT/'evaluation_30.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0])); writer.writeheader()
        for row in rows:
            writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()})
    lines=['# 싼타페 추가 30문항 평가','', '## 실행·판정 범위','',
           '현재 개인 싼타페 서비스에서 독립 대화로 30문항을 실행했습니다. 생성 가능한 경우에만 생성 동작을 요청했습니다. 기존 50문항 및 원문 DB 검토 상태는 보존했습니다.',
           '', '판정은 Codex 잠정 판정입니다. 사용자 확정 골든셋과 구분합니다. A는 단어 중심의 폭넓은 주제 질문이므로 관련 위치 안내나 원문 선택지도 허용합니다. B/C는 명확한 목적에 답해야 통과합니다.',
           '', f"실행 30/30 · 검색 {summary['search_calls']}회 · 생성 동작 요청 {summary['generation_attempts']}회 · 생성 답변 {summary['generated_answers']}개 · 원문 복귀 {summary['generation_fallbacks']}개 · 실행 예외 {summary['failure_count']}건",'',
           '|유형|통과|부분|실패|잠정 Hit@5|잠정 MRR@5|','|---|---:|---:|---:|---:|---:|']
    for g in 'ABC':
        c=groups[g];m=metrics[g];lines.append(f"|{g}|{c.get('통과',0)}|{c.get('부분',0)}|{c.get('실패',0)}|{m['hit5']:.2f}|{m['mrr5']:.2f}|")
    lines+=['', summary['metrics_note'], '', '## 주요 보완 사항','',
            '- 관련 검색 후보를 찾고도 검토된 무관한 안내도·표를 선택하는 문제를 우선 수정해야 합니다.',
            '- 미검토 자료의 답변 보류는 원문 검토·활성화 과제와 연결해야 합니다. 이를 검색 실패와 혼동하지 않습니다.',
            '- 생성 검증 실패 시 무관한 원문 전체를 보여주는 대신, 답변 근거 부족과 관련 후보를 명확하게 안내해야 합니다.',
            '- A/B/C는 다른 질문을 같은 10개 기능 영역으로 구성했습니다. A의 통과가 B/C의 구체 답변 능력을 보장하지 않습니다.', '', '## 30문항과 문항별 결과','']
    for row in rows:
        lines += [f"### {row['case_id']} · {row['question']}", '',
                  '의미 맥락: '+' + '.join(row['semantic_contexts']),
                  '', '기대 근거: '+row['expected']+' (PDF '+', '.join(map(str,row['reference_pages']))+'쪽)',
                  '', f"판정: {row['overall']} / 표시 근거: {row['displayed_source_grade']} / 첫 관련 후보: {row['first_relevant_rank'] or '상위 5개에 없음'} / 최종 상태: {row['final_status']}",
                  '', row['note'], '', '검색 상위 5개: '+' / '.join(f"{c['rank']}. {c['title']}" for c in row['top5']), '',
                  '<details><summary>실제 최종 응답</summary>', '', row['final_text'], '', '</details>','']
    (OUTPUT/'report.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':
    finalize()
