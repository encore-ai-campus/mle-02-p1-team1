"""사용자 실행 캡처의 대화 판정과 기존 자동 평가를 비교하여 저장합니다."""
import csv
import json
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.pagesizes import A4

FOLDER = Path(__file__).resolve().parent
RESULTS = FOLDER / 'evaluation_50_results'
ROOT = FOLDER.parents[2]

# 캡처를 직접 실행한 사람과 판정 작성자를 구분합니다. 원문 응답은 아래에 요약합니다.
# 번호|근거 판정|화면 판정|생성 평가|실제 자료|응답 요약|보완 메모
RECORDS = '''A01|해당 없음|실패|미실시|없음|날씨 질문에 설명서 검토 후 답변 가능 안내|설명서 밖 질문 안내 필요. 문구 수정 전 실행 화면.
A02|부적절|실패|미실시|주행 중 엔진 정지 금지, PDF 57~58|주식 질문에 무관한 자동차 자료와 답변 보류|설명서 밖 질문을 차단하고 무관한 근거를 표시하지 않기.
A03|해당 없음|실패|미실시|없음|식당 추천에 검토 보류 및 부품 이름 요청|설명서 밖 질문 안내 필요.
A04|해당 없음|실패|미실시|없음|파이썬 코드 질문에 검토 보류 및 부품 이름 요청|설명서 밖 질문 안내 필요.
A05|해당 없음|실패|미실시|없음|로또 추천에 검토 보류 및 부품 이름 요청|설명서 밖 질문 안내 필요.
A06|해당 없음|실패|미실시|없음|여행 일정 질문에 검토 보류 및 부품 이름 요청|설명서 밖 질문 안내 필요.
A07|해당 없음|실패|미실시|없음|생일 메시지 요청에 검토 보류 및 부품 이름 요청|자동 평가와 달리 실제 캡처에는 경고 메시지 자료가 표시되지 않음.
A08|해당 없음|통과|미실시|없음|가정 와이파이 질문에 근거 부족 안내, 추측하지 않음|기존 판정 1점 유지. 설명서 밖 질문임을 명시하고 자동차 부품 요청은 생략하기.
A09|해당 없음|실패|미실시|없음|환율 질문에 검토 보류 및 부품 이름 요청|설명서 밖 질문 안내 필요.
A10|해당 없음|실패|미실시|없음|일반 번역 요청에 검토 보류 및 부품 이름 요청|설명서 밖 질문 안내 필요.
B01|적절|통과|완료|PDF 43 / 매뉴얼 38, 용량 표·각주|엔진오일 4.8L, SAE 0W-20, API SN PLUS/SP 또는 ILSAC GF-6|일반 교체 용량과 주의사항을 제시함.
B02|적절|통과|완료|PDF 43 / 매뉴얼 38, 용량 표·각주|브레이크액 DOT-4 및 SAE J1704 DOT-4 LV, ISO4925 CLASS-6, FMVSS116 DOT-4|추천 규격과 순정 규격 준수 안내가 적절함.
B03|적절|통과|완료|PDF 43 / 매뉴얼 38, 용량 표·각주|리어 디퍼렌셜 0.53~0.63L, API GL-5, SAE 75W/85|핵심 값 적절. 일반 오일 게이지 F선 주의사항의 디퍼렌셜 적용 여부는 미확인.
B04|적절|통과|완료|PDF 43 / 매뉴얼 38, 용량 표·각주|트랜스퍼 케이스 0.62~0.68L, API GL-5, SAE 75W/85, 침수 시 즉시 교환|추가 캡처 반영. 핵심 값 적절. F선 안내의 해당 장치 적용 여부는 미확인.
B05|적절|통과|완료|PDF 45 / 매뉴얼 40, 차대번호|엔진과 실내 사이 차체 패널의 VIN 타각 위치와 화살표 그림|위치 설명과 그림 일치. 차대번호를 임의 생성하지 않음.
B06|적절|통과|완료|PDF 33~34, 차량 내부 I|실외 미러 접이 버튼은 내부 안내도 4번|버튼 번호와 그림 일치. 사양 차이 안내 포함.
B07|적절|통과|완료|PDF 246~249, 실외 미러|주행 중 미러 조절·접기 금지 및 사고 위험 안내|안전 경고를 맨 앞에 배치. 후진 하향 그림은 질문과 관련이 적음.
B08|부적절|실패|미실시|PDF 246~249, 실외 미러|실내 미러 조절 질문에 실외 미러 원문과 도어 버튼 그림|실내·실외 구분 필요. 실내 미러는 PDF 239쪽부터 확인.
B09|적절|통과|미실시|PDF 54 / 매뉴얼 49, 안전벨트 착용|바른 자세, 어깨·골반띠 위치, 꼬임 방지, 버클 체결 원문|내용 적절하나 원문이 김. 핵심 착용 방법 요약 필요. 그림 보류.
B10|적절|통과|완료|PDF 54 / 매뉴얼 49, 안전벨트 착용|차단 클립·스토퍼 사용 금지와 경고·감김 방해 이유|핵심 답변 적절. 그림 연결 확인은 남아 있음.
B11|부적절|실패|미실시|PDF 276~277, 스마트 테일게이트 기능 중지|기능 켜는 위치 질문에 중지 방법과 스마트 키 그림|켜기·중지 구분 필요. PDF 275쪽의 기능 설정 경로를 찾기.
B12|적절|통과|완료|PDF 275~278, 작동·중지·감지 영역|50~100cm, 도어 잠금 후 약 15초, 스마트 키 휴대 후 3초 이상 대기|감지 영역 그림을 먼저 제시하고 긴 경고는 뒤에 배치.
B13|적절|통과|미실시|PDF 275~278, 작동·중지·감지 영역|감지·경보 중 스마트 키 버튼을 짧게 눌러 중지하는 원문 포함|중지 설명을 첫 번째로 표시. 짧게 누르는 조건 강조.
B14|적절|실패|미실시|PDF 263~264, 선루프 초기화|미검토 자료로 확정 답변 보류, 펼침 영역에 초기화 원문|검색 성공 / 답변 보류. 깨진 문자·이미지 식별자 정리 필요.
B15|적절|실패|미실시|PDF 383~386, 엔진 시동 전 확인|미검토 자료로 답변 보류, 확인 사항 및 고장 대처 원문|시동 전 확인을 먼저 요약하고 고장 대처를 분리하기.
B16|적절|실패|미실시|PDF 387, 스마트 키 원격 시동|미검토 자료로 답변 보류, 10m·4초 등 원문 표시|버튼 기호가 깨짐. 검토 후 이름과 순서로 안내하기.
B17|적절|실패|미실시|PDF 661, 주행 중 시동이 꺼진 경우|미검토 자료로 답변 보류, 안전한 곳 이동 및 브레이크·조향 원문|검색 성공 / 긴급 대처 답변 보류. 핵심 대처를 우선 표시.
B18|적절|통과|완료|PDF 52 / 매뉴얼 47, 엔진룸 점검|차가운 엔진에서 냉각수 점검, 뜨거울 때 캡 개방 금지|화상 경고 그림 적절. 주의사항을 첫 문장에 배치.
B19|적절|통과|완료|PDF 43 / 매뉴얼 38, 용량 표·각주|연료 탱크 67L, 무연 휘발유|질문한 두 항목을 명확히 답함.
B20|적절|실패|미실시|후보 PDF 231 초기화, PDF 229 메모리 시스템|정확한 초기화 후보를 첫 번째로 찾았지만 답변 보류|검색 성공 / 답변 보류. 초기화 절차를 우선 안내.
C01|해당 없음|통과|미실시|없음|부품·기능과 상황을 추가로 질문|모호한 대상을 추측하지 않고 위치·모양 설명도 요청함.
C02|해당 없음|통과|미실시|없음|주행 중 시동 꺼짐·시동 불가·가속 불가를 구분해 질문|현재 주행·정차 확인 적절. 안전한 곳인지 먼저 확인하면 좋음.
C03|적절|통과|미실시|PDF 383~386, 시동 전 확인|계기판이 켜지는지 물어 시동 불가 증상을 좁힘|관련 자료와 실제 고장 원인을 구분. 해결 답변은 보류.
C04|적절|실패|미실시|PDF 383~386, 시동 전 확인|계기판이 켜진다고 답했지만 자료 안내·보류만 반복|브레이크·경고 문구 등 다음 확인 질문으로 이어가기.
C05|적절|실패|미실시|PDF 383~386, 시동 전 확인|계기판도 안 켜지는 증상에 자료 안내·보류만 반복|전기 장치 반응 등 확인. 배터리 원인으로 바로 단정하지 않기.
C06|부적절|실패|미실시|PDF 383~386, 밀기 시동 666, 교차로·건널목 661|달리다 시동 꺼짐에 정확한 주행 중 시동 꺼짐 항목 미표시|B17과 의미 같으나 검색 실패. 안전 확인과 구어체 연결 필요.
C07|부적절|실패|미실시|PDF 34~35, 차량 내부 II|시동 켜졌지만 가속 불가에 내부 부품 안내도 표시|사용자 번호 수정 반영. 안전 상태·변속 위치·경고 확인 필요.
C08|해당 없음|통과|미실시|없음|빽미러가 실외·실내 중 어느 미러인지 추가 질문|원래 C07 기록을 사용자 요청대로 C08로 변경. 간단한 확인 질문 권장.
C09|적절|통과|완료|PDF 246~249, 실외 미러|주차 시 안 접힘에 도어 잠금 자동 접힘 설정 안내|잠금 시 안 접힘인지 버튼도 안 되는지 추가 확인하면 좋음.
C10|부적절|실패|미실시|PDF 52, 엔진룸 점검|밤에 뒤 보는 거울 눈부심에 냉각수 원문·경고 그림|실내 미러·눈부심 연결 및 미러 종류 확인 필요.
C11|확인 불가|실패|미실시|표시 없음|차 뒤에서 안 열림에 일반 보류·부품 이름 요청|스마트 테일게이트인지, 키 휴대·잠금·대기 시간 확인 필요.
C12|부분 적절|부분|완료|PDF 278, 감지 영역|의도하지 않은 뒤쪽 문 열림에 테일게이트 감지 조건 안내|트렁크·뒷좌석 문 확인 누락. 작동 가능 조건이 실제 원인인 것은 아님.
C13|확인 불가|실패|미실시|표시 없음|뒤 경보음과 열림 중지 요청에 보류만 표시|B13 중지 방법을 구어체에서도 찾고 상황 확인 필요.
C14|부적절|실패|미실시|PDF 30, 차량 외부 I|천장 유리 닫힘·재설정 질문에 외부 위치 안내도|선루프 초기화 PDF 263~264 연결. 해결 원인을 단정하지 않기.
C15|부적절|실패|미실시|PDF 726~729, 배터리 관리|배터리 재연결 후 지붕 창 이상에 배터리 자료만 표시|배터리와 선루프를 함께 해석하고 구체적인 움직임 확인.
C16|적절|실패|미실시|PDF 105~112, 안전벨트 구속 장치|골반띠를 배 위로 올려도 되는지 답변 보류|검토 후 골반 착용 핵심 안내 필요.
C17|적절|통과|완료|PDF 54 / 매뉴얼 49, 안전벨트 착용|경고음 차단 클립 사용 금지 및 이유 안내|구어체 검색 성공. 그림은 보류됐지만 핵심 전달됨.
C18|적절|통과|완료|PDF 45 / 매뉴얼 40, 차대번호|VIN 타각 위치 설명과 화살표 그림|입력 질문은 캡처에 없음. 평가지 C18 문구 기준으로 대응시킴.
C19|부분 적절|부분|완료|PDF 43 / 매뉴얼 38, 용량 표·각주|오일 종류 확인 없이 엔진오일 교체 용량 4.8L 안내|오일 종류와 교체·보충 구분 필요. 4.8L는 보충량이 아님.
C20|확인 불가|실패|미실시|표시 없음|의자 저장 위치 재설정 질문에 보류·부품 이름 요청|위치 재저장과 시스템 초기화를 구분하고 PDF 229·231 연결.'''


def collect_rows():
    """50개의 대화 판정을 원래 질문 및 자동 판정과 연결합니다."""
    automated = json.loads((RESULTS / 'graded_results.json').read_text(encoding='utf-8'))
    lookup = {r['case_id']: r for r in automated}
    rows = []
    for line in RECORDS.splitlines():
        cid, source, grade, generation, sources, response, note = line.split('|')
        baseline = lookup[cid]
        rows.append(dict(case_id=cid, group=cid[0], question=baseline['question'],
                         source_grade=source, overall=grade, generation_grade=generation,
                         actual_sources=sources, response_summary=response, note=note,
                         automatic_overall=baseline['overall'], automatic_source_grade=baseline['source_grade'],
                         automatic_note=baseline['note'], automatic_generation='미평가',
                         evidence_type='사용자 실행 화면 캡처', annotator='Codex 캡처 판정',
                         human_confirmed=False))
    # 이 순서는 사용자가 대화에서 바로잡은 문항 번호를 따릅니다.
    overrides = {
        'C07':'시동은 켜져 있는데 밟아도 차가 안 나가',
        'C08':'빽미러 접는 거 어떻게 해?',
        'C09':'차 바깥 양쪽 거울이 주차할 때 안 접혀',
        'C10':'뒤 보는 거울이 밤에 너무 눈부셔.',
        'C11':'짐 들고 차 뒤에 서 있는데 왜 안 열리지?',
        'C13':'뒤에서 삐삐 소리 나는데 열리는 걸 멈추려면 뭐 눌러?',
        'C14':'천장 유리가 끝까지 안 닫히는데 다시 맞추는 거 있어?',
        'C15':'배터리 뺐다 연결했더니 지붕 쪽 창문이 이상하게 움직여',
        'C16':'허리 쪽 벨트가 불편한데 배 위로 올려서 매도 돼?',
        'C17':'벨트 경고음 귀찮은데 꽂아두는 클립 써도 돼?',
        'C19':'오일 얼마나 넣어?',
        'C20':'의자 위치 저장해둔 게 안 맞아. 처음부터 다시 맞출 수 있어?',
    }
    # 비교는 번호만이 아니라 같은 질문 의미를 가진 자동 평가에 대응시킵니다.
    for row in rows:
        if row['case_id'] in overrides:
            row['question'] = overrides[row['case_id']]
    return rows


def make_pdf(rows, summary, destination):
    """요약과 전 문항 비교를 한 PDF로 만듭니다. 캡처 원문은 응답 요약과 구분합니다."""
    pdfmetrics.registerFont(TTFont('Malgun', 'C:/Windows/Fonts/malgun.ttf'))
    pdfmetrics.registerFont(TTFont('MalgunBold', 'C:/Windows/Fonts/malgunbd.ttf'))
    body = ParagraphStyle('body', fontName='Malgun', fontSize=9, leading=14, wordWrap='CJK', spaceAfter=5)
    title = ParagraphStyle('title', parent=body, fontName='MalgunBold', fontSize=20, leading=28, spaceAfter=18)
    heading = ParagraphStyle('heading', parent=body, fontName='MalgunBold', fontSize=13, leading=20, spaceAfter=9)
    small = ParagraphStyle('small', parent=body, fontSize=8, leading=12)
    def p(value, style=body):
        """자료 문자열을 안전하게 문단으로 변환합니다."""
        return Paragraph(escape(str(value)), style)
    story = [p('싼타페 RAG 50문항 평가 통합 보고서', title), p('평가 기록일: 2026-10-06'),
             p('사용자 직접 실행 캡처 + Codex 판정 / 기존 자동 평가와 비교', heading),
             p('직접 실행 캡처 50/50문항을 기록했습니다. B04 추가 캡처 및 C07·C08 번호 정정을 반영했습니다. 사용자가 질문을 실행했고, 이 보고서의 판정은 대화에서 Codex가 작성했습니다. 사용자 최종 판정 확정과는 구분합니다.'),
             p('사용자 실행 화면은 원문 발췌, 확인 질문, 답변 보류, 생성 답변이 섞여 있습니다. 자동 평가 50문항은 독립 대화에서 검색·초기 응답만 수집했으며 생성 답변을 평가하지 않았습니다. 따라서 두 결과를 동일한 조건의 개선 전후 성능으로 해석할 수 없습니다.'),
             p('판정 기준', heading),
             p('통과: 질문에 맞는 내용 또는 필요한 추가 확인 질문을 제공. 부분: 관련 정보는 있으나 질문의 대상·의도를 먼저 확인하지 않음. 실패: 무관한 자료, 필요한 답변 보류, 후속 대응 부족. 근거 판정과 화면 응답 판정은 별도입니다. 안전하게 보류한 시스템 동작이 잘못됐다는 뜻은 아니며, 사용자가 필요한 답을 받았는지를 평가했습니다.'),
             p('결과 요약', heading)]
    table = [['평가 구분','통과','부분','실패'], ['사용자 실행 화면',summary['counts']['통과'],summary['counts']['부분'],summary['counts']['실패']], ['기존 자동 초기 응답',29,3,18]]
    t = Table(table, colWidths=[220,80,80,80]); t.setStyle(TableStyle([('FONTNAME',(0,0),(-1,-1),'Malgun'),('FONTSIZE',(0,0),(-1,-1),10),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8e7fa')),('GRID',(0,0),(-1,-1),.4,colors.lightgrey),('BOTTOMPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),10)])); story += [t, Spacer(1,14)]
    for group in 'ABC':
        c = summary['groups'][group]
        story.append(p(f"{group} 유형: 통과 {c.get('통과',0)} / 부분 {c.get('부분',0)} / 실패 {c.get('실패',0)}"))
    story += [p(f"생성 답변 확인 {summary['generated_answers']}문항. 나머지는 생성 답변 미실시로 기록. Hit@5·MRR는 정답 근거와 검색 순위 검증이 없어 계산하지 않았습니다."), PageBreak(), p('우선 보완할 내용',title)]
    priorities = [
        '1. 설명서 밖 질문 구분: A 10문항 중 9문항에서 무관한 검토 안내. 재검색보다 먼저 서비스 범위를 판단하고 잘못된 자료를 숨기기.',
        '2. 구어체·의도 구분: 실내/실외 미러, 켜기/중지, 달리다가/주행 중, 천장 유리/선루프, 의자 저장/자세 메모리의 연결을 개선하기.',
        '3. 미검토 자료 검토 반영: B14~B17·B20, C16은 관련 자료를 찾고도 답변 보류. 별도 검토 초안을 확인하고 활성화한 뒤 다시 평가하기.',
        '4. 후속 질문: C04·C05처럼 증상이 구체화돼도 대화가 끊김. C12는 문 종류, C19는 오일 종류와 교체/보충 구분 필요.',
        '5. 답변·그림 정리: 안전 핵심을 먼저 배치하고 불필요한 긴 원문과 그림 줄이기. 깨진 기호·이미지 식별자 정리.',
        '6. 주의사항 적용 범위: B03·B04의 용량과 규격은 맞지만 일반적인 F선 문구를 디퍼렌셜·트랜스퍼 케이스에 적용할 수 있는지는 미확인. 검증 전 장치별 주의사항으로 단정하지 않기.'
    ]
    story += [p(x) for x in priorities]
    story += [Spacer(1,12), p('기록의 한계', heading), p('응답은 캡처에서 확인한 내용을 요약한 것으로 전체 원문 전사가 아닙니다. C18은 입력 질문이 캡처에 없어 평가지 질문으로 대응시켰습니다. C12의 질문 일부는 화면 밖에 있어 의미 요약으로 기록했습니다. 전체 과정은 동일한 버전·독립 대화 조건으로 통제한 실험이 아닙니다. B03·B04는 대화에서 부여한 핵심 답변 통과 판정을 유지하되 주의사항 검증 과제를 별도 표시했습니다.'), p('자동 평가와 직접 평가가 다르게 보이는 이유: 자동 수집은 초기 응답만 확인했고, 직접 실행 중 일부 문항은 생성 답변까지 확인했습니다. B14 등은 자동 기준에서 후보 연결 성공으로 통과했지만 직접 화면에서는 필요한 답변을 받지 못해 실패로 기록했습니다. 이는 점수 기준과 평가 단계 차이이며 성능 하락률이 아닙니다.')]
    # 한 페이지에 5개씩 배치해 각 문항의 응답·근거·보완 기록을 함께 읽도록 합니다.
    for offset in range(0,50,5):
        story += [PageBreak(), p(f"문항별 비교 {offset+1}~{offset+5}",title)]
        for row in rows[offset:offset+5]:
            story += [p(f"{row['case_id']} | {row['question']}",heading),
                      p(f"직접 화면: {row['overall']} / 근거: {row['source_grade']} / 생성 평가: {row['generation_grade']}",small),
                      p('표시 자료: '+row['actual_sources'],small),
                      p('응답 요약: '+row['response_summary'],small),
                      p('기록·보완: '+row['note'],small),
                      p(f"자동 초기 응답: {row['automatic_overall']} / {row['automatic_note']}",small), Spacer(1,8)]
    def footer(canvas, doc):
        """모든 페이지에 보고서 이름과 페이지 번호를 표시합니다."""
        canvas.setFont('Malgun',8); canvas.setFillColor(colors.grey)
        canvas.drawString(35,24,'싼타페 개인 평가 기록 | 사용자 실행 · Codex 판정')
        canvas.drawRightString(A4[0]-35,24,str(doc.page))
    SimpleDocTemplate(str(destination),pagesize=A4,rightMargin=35,leftMargin=35,topMargin=35,bottomMargin=38).build(story,onFirstPage=footer,onLaterPages=footer)


def main():
    """자동 평가를 보존하고 별도 직접 평가 기록·CSV·통합 PDF를 생성합니다."""
    rows = collect_rows()
    summary = dict(date='2026-10-06', captured=50, counts=dict(Counter(r['overall'] for r in rows)),
                   groups={g:dict(Counter(r['overall'] for r in rows if r['group']==g)) for g in 'ABC'},
                   generated_answers=sum(r['generation_grade']=='완료' for r in rows),
                   user_final_confirmation=False, metrics=None)
    (RESULTS/'screenshot_evaluation.json').write_text(json.dumps(dict(summary=summary,rows=rows),ensure_ascii=False,indent=2),encoding='utf-8')
    with (RESULTS/'screenshot_evaluation.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    out=ROOT/'output/pdf/santafe_evaluation_combined.pdf'; out.parent.mkdir(parents=True,exist_ok=True)
    make_pdf(rows,summary,out)
    print(json.dumps(dict(summary=summary,pdf=str(out)),ensure_ascii=False))

if __name__=='__main__':
    main()
