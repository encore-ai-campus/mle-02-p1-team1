"""주제·구체 질문·복합 맥락 30문항을 고정하고 현재 싼타페 서비스를 평가합니다."""
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from .app import create_answer_service, SantafeBackend
from .evaluation_50 import write_json
from .openai_search_service import active_embedding_run
from .review_revision import selection_file
from .source_profile import FULL_SOURCE

FOLDER=Path(__file__).resolve().parent
OUTPUT=FOLDER/'evaluation_30_results'
# 정답 근거는 원본 PDF를 읽고 실행 전에 작성합니다. 서비스에는 질문만 전달합니다.
# A는 예시 페이지가 정답 전체를 제한하지 않습니다. 제목·본문 주제 관련성을 판정해야 합니다.
CASES='''A01|스마트 키|188-194|스마트 키 사용·버튼·주의·건전지 등 관련 문서|주제 키워드
A02|파워 테일게이트|268-274|파워 테일게이트 작동·설정·초기화·주의 등 관련 문서|주제 키워드
A03|실외 미러|246-249|실외 미러 조절·접힘·자동 조절 등 관련 문서|주제 키워드
A04|운전석 자세 메모리 시스템|229-232|기억·재생·초기화·승하차 기능 등 관련 문서|주제 키워드
A05|선루프|259-264|선루프 작동·선블라인드·끼임·초기화 등 관련 문서|주제 키워드
A06|안전벨트|54-56,105-114|안전벨트 착용·조절·경고·프리텐셔너 등 관련 문서|주제 키워드
A07|회생 제동|8-15,400-405|회생 제동 원리·단계·게이지·제한 등 관련 문서|주제 키워드
A08|자동 정차 기능|420-423|Auto Hold 설정·해제·주의·경고 등 관련 문서|주제 키워드
A09|타이어|40-42,47,669-682,731-736|타이어 규격·공기압·관리·응급 처치 등 관련 문서|주제 키워드
A10|스마트폰 무선 충전|360-363|무선 충전 사용·설정·이상 표시·주의 등 관련 문서|주제 키워드
B01|스마트 키 건전지의 규격과 필요한 개수는 뭐야?|193-194|CR2450 1개를 직접 확인할 수 있는 근거|같은 기능: 스마트 키+건전지+규격
B02|파워 테일게이트가 열리는 높이는 어떻게 설정해?|273|열림 높이 설정 경로 또는 사용자 높이 저장 절차|같은 기능: 테일게이트+열림 높이+설정
B03|도어를 잠글 때 실외 미러가 자동으로 접히도록 설정하려면?|247-248|웰컴 미러/라이트의 도어 잠금 해제 시 설정과 잠금 시 접힘|같은 기능: 미러+자동 접힘+설정
B04|운전석 자세를 메모리 1번 버튼에 저장하려면 어떻게 해?|230|P단·ON·자세 조절 후 1번 버튼 길게 눌러 저장|같은 기능: 메모리+저장+버튼
B05|선루프를 자동으로 닫다가 중간에서 멈추려면 스위치를 어떻게 조작해?|261-262|자동 작동 중 스위치를 어느 방향으로든 살짝 눌러 중지|같은 기능: 선루프+자동 닫힘+중지
B06|앞좌석 안전벨트의 어깨 높이는 어떻게 조절해?|111|올리기와 잠금 버튼을 누르며 내리는 조절 방법|같은 기능: 안전벨트+높이+조절
B07|회생 제동 단계를 높이려면 어느 쪽 패들 쉬프트를 당겨?|400-402|ECO에서 왼쪽 패들로 단계 증가; 주행 모드 조건 보존|같은 기능: 회생 제동+단계+패들
B08|AUTO HOLD가 작동 중일 때 출발하려면 어떻게 해?|420-421|가속 페달을 천천히 밟아 출발; 조건별 수동 해제 주의|같은 기능: Auto Hold+해제+출발
B09|타이어 공기압은 차가운 상태에서 확인해야 해?|731|차가운 상태에서 점검; 주행 직후 공기압 조정 금지|같은 기능: 타이어+공기압+점검 조건
B10|무선 충전 표시등이 주황색으로 깜빡이면 어떻게 해야 해?|362|충전 이상 시 주황색 10초 점멸; 다시 놓거나 충전 상태 확인|같은 기능: 무선 충전+표시등+대응
C01|스마트 키 건전지가 방전돼 차 안에서 시동을 못 걸 때, 키를 어디에 대고 눌러야 해?|193,385|스마트 키로 시동 버튼을 직접 누르는 비상 시동 근거|키 건전지 방전+실내 시동 불가+키를 대는 조작
C02|천장이 낮은 차고에서 트렁크 문이 천장에 닿지 않게 열리는 높이를 줄이려면?|273|파워 테일게이트 열림 높이 설정·사용자 높이 저장|낮은 차고+테일게이트와 천장 간섭+높이 제한 목적
C03|후진 주차할 때 옆 주차선을 잘 보려고 양쪽 거울을 자동으로 아래로 향하게 하려면?|248-249|R단 및 미러 선택 스위치 L/R로 후진 자동 하향 작동|후진 주차+주차선 시야+양쪽 미러 하향 조작
C04|가족이 운전한 뒤 내 좌석과 거울 위치로 한 번에 돌리려면 저장해 둔 버튼을 어떻게 써?|229-230|P단에서 저장된 1/2번 기억 재생; 좌석·미러 위치 복원|운전자 교대+좌석과 미러 위치 변화+저장 자세 복원
C05|루프바에 캠핑 짐을 실은 상태에서 지붕 유리를 열어 환기해도 돼?|259|루프바 설치 또는 적재 상태에서 선루프 작동 금지|캠핑 적재+지붕 루프바+선루프 환기 조작
C06|운전석에 앉으면 벨트가 목에 닿는데, 어깨 높이를 낮추려면 어느 버튼을 눌러?|111|앞좌석 어깨띠 고정 장치의 잠금 버튼을 누르며 아래로 조절|운전석 착석+목 접촉 위치+높이 낮추기 조작
C07|내리막을 내려가는데 배터리가 충분히 충전돼 회생 제동이 제한된다고 떠. 감속은 어떻게 해야 해?|401-403|충전량 높으면 회생 제한; 브레이크 페달로 직접 감속|내리막 주행+높은 배터리 충전량+회생 제한 경고와 감속 목적
C08|자동 세차장 컨베이어가 바퀴를 굴리는 곳에 들어갈 때 AUTO HOLD는 어떻게 해둬야 해?|422|바퀴 구동 자동 세차기 진입 시 Auto Hold 해제|컨베이어 세차 상황+바퀴 구동+자동 정차 기능 처리
C09|고속도로를 오래 달린 직후 공기압이 높게 보이는데, 지금 공기를 빼서 권장값에 맞춰도 돼?|731|주행 직후 높아진 공기압을 낮추지 말고 식은 상태 점검|장시간 고속 주행+뜨거운 타이어 공기압 상승+공기 빼기 판단
C10|센터 콘솔 충전 패드에 금속 케이스를 씌운 휴대폰을 놓았더니 뜨겁고 충전도 멈춰. 뭘 확인해야 해?|361-363|금속 이물·커버·온도 및 패드 밀착 확인; 단일 고장 원인 단정 금지|실내 콘솔 위치+금속 휴대폰 케이스+발열과 무선 충전 중단'''


def make_dataset():
    """번호별 질문·의미 맥락·원본 근거 후보를 실행 전에 고정합니다."""
    rows=[]
    for line in CASES.splitlines():
        cid,question,spans,expected,context=line.split('|')
        pages=[]
        for span in spans.split(','):
            edges=list(map(int,span.split('-')))
            pages.extend(range(edges[0],edges[-1]+1))
        rows.append(dict(case_id=cid,group=cid[0],question=question,reference_pages=pages,
                         expected=expected,semantic_contexts=context.split('+'),
                         reference_scope='주제 관련 페이지 예시; 전부가 아님' if cid[0]=='A' else '직접 근거 페이지 후보'))
    return dict(name='추가 30문항 주제·구체 질문·복합 맥락',cases=rows,
                rubric={'A':'상위 주제와 관련된 문서를 허용. 단일 정답 문서로 제한하지 않음. 주제 확인 질문도 적절한 대응으로 구분.',
                        'B':'명확한 기능 목적에 직접 답할 근거와 조건을 확인.',
                        'C':'서로 다른 의미 맥락을 함께 해석해 하나의 목적에 답하는 근거 또는 구체 확인 질문 평가.',
                        'retrieval':'검색 상위 후보의 관련성은 Codex 잠정 판정. 사용자 확정 골든셋과 구분.',
                        'response':'검색 후보 적절성과 초기 화면·생성 답변을 분리. 미검토 보류는 임의 생성하지 않음.'})


def collect():
    """30문항을 독립 세션으로 실행하고 가능한 생성 동작도 같은 근거로 평가합니다."""
    OUTPUT.mkdir(exist_ok=True)
    dataset=make_dataset()
    write_json(FOLDER/'evaluation_30_questions.json',dataset)
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in FOLDER.glob('*.py')}
    selected=selection_file()
    plan=dict(dataset=dataset,code_hashes=hashes,source_run_id=str(FULL_SOURCE.run_id),
              embedding_run_id=str(active_embedding_run()),
              review_selection=json.loads(selected.read_text(encoding='utf-8')) if selected else None,
              git_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
              independent_sessions=True,generation_policy='현재 서비스가 생성 가능하다고 판정한 경우에만 1회 요청',
              gold_human_confirmed=False)
    plan_path=OUTPUT/'plan.json'
    if plan_path.exists() and json.loads(plan_path.read_text(encoding='utf-8'))!=plan:
        raise ValueError('이미 고정한 평가 버전과 다릅니다. 기존 결과를 덮어쓰지 않습니다.')
    write_json(plan_path,plan)
    path=OUTPUT/'results.json'
    saved=json.loads(path.read_text(encoding='utf-8')) if path.exists() else dict(results=[],complete=False)
    service=create_answer_service('OpenAI','답변 아래 관련 그림 보기')
    backend=SantafeBackend(service)
    search=service.evidence_service.search_service
    original=search.search
    captured=[]
    def capture(*args,**kwargs):
        """서비스의 실제 검색 결과를 기록하며 정답을 검색에 전달하지 않습니다."""
        result=original(*args,**kwargs); captured.append(result); return result
    search.search=capture
    started=time.perf_counter()
    for case in dataset['cases']:
        if any(r['case_id']==case['case_id'] for r in saved['results']):
            continue
        captured.clear(); session=backend.start_session(is_test=True); tick=time.perf_counter()
        row={**case,'generation_attempted':False,'generation_error':None,'error_type':None}
        try:
            packet=backend.chat(session,case['question'],request_id='extra30_'+case['case_id'])
            row['initial_packet']=packet
            if any(action['id']=='generate' for action in packet.get('actions',[])):
                row['generation_attempted']=True
                try:
                    row['generated_packet']=backend.perform_action(session,packet,'generate')
                except Exception as error:
                    row['generation_error']=type(error).__name__
        except Exception as error:
            row['error_type']=type(error).__name__
        finally:
            backend.sessions.pop(session,None)
        row.update(search_results=list(captured),seconds=round(time.perf_counter()-tick,3))
        saved['results'].append(row)
        saved.update(completed=len(saved['results']),total=30,pid=os.getpid(),
                     elapsed_seconds=round(time.perf_counter()-started,2),updated_at=datetime.now(timezone.utc).isoformat())
        # 기존 수집기의 원자 저장을 재사용합니다. 저장 실패 시 실행을 중단해 결과 유실을 숨기지 않습니다.
        write_json(path,saved)
        write_json(OUTPUT/'failures.json',[{'case_id':r['case_id'],'error_type':r['error_type'],'generation_error':r['generation_error']}
                                         for r in saved['results'] if r['error_type'] or r['generation_error']])
        print(f"완료 {len(saved['results'])}/30 | {case['case_id']} | 상태 {row.get('initial_packet',{}).get('native_status')} | 생성 {row['generation_attempted']}",flush=True)
    saved['complete']=len(saved['results'])==30
    write_json(path,saved)
    print('추가 30문항 실행 완료. 저장 결과를 원본 근거와 비교하여 판정해야 합니다.',flush=True)


if __name__=='__main__':
    collect()
