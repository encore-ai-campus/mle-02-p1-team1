"""실제 50개 초기 응답을 근거로 AI 잠정 판정을 기록하고, 채점된 PDF를 만듭니다.

검색 또는 생성 모델을 다시 호출하지 않습니다. 정답 기준은 실행 이후 설명서와
대조해 작성한 잠정 기준이며, 사용자 확인 전에는 확정 골든셋·Hit@5·MRR로 쓰지 않습니다.
"""

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .build_evaluation_pdf import paragraph

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[2]
RESULTS = FOLDER / "evaluation_50_results"
OUTPUT = ROOT / "output/pdf/santafe_evaluation_50_graded.pdf"

# 이 판정은 초기 자료 연결·확인 질문의 적절성만 평가합니다. 생성 답변은 미평가입니다.
# 부분 판정은 정답 처리하지 않습니다. 증상 질문의 자료 연결은 고장 원인 확인과 다릅니다.
GRADES = {
    "A01": ("실패", "해당 없음", "부적절", "설명서 밖 질문임을 안내", "날씨 질문에 설명서 검토 안내가 나옴. 질문과 맞는 자료가 없음."),
    "A02": ("실패", "해당 없음", "부적절", "설명서 밖 질문임을 안내", "주식 질문에 주행 중 엔진 정지 금지 자료가 연결됨."),
    "A03": ("실패", "해당 없음", "부적절", "설명서 밖 질문임을 안내", "식당 추천을 설명서 검토 대상으로 처리함."),
    "A04": ("실패", "해당 없음", "부적절", "설명서 밖 질문임을 안내", "파이썬 질문을 설명서 검토 대상으로 처리함."),
    "A05": ("실패", "해당 없음", "부적절", "설명서 밖 질문임을 안내", "로또 질문을 설명서 검토 대상으로 처리함."),
    "A06": ("실패", "해당 없음", "부적절", "설명서 밖 질문임을 안내", "여행 일정 질문을 설명서 검토 대상으로 처리함."),
    "A07": ("실패", "해당 없음", "부적절", "설명서 밖 질문임을 안내", "생일 메시지 질문에 하이브리드 경고 메시지 자료가 연결됨."),
    "A08": ("통과", "해당 없음", "적절", "설명서 밖 또는 근거 부족 안내", "근거 부족을 알리고 추측 답변을 막음. 차량 밖 질문이라는 안내는 개선 필요."),
    "A09": ("실패", "해당 없음", "부적절", "설명서 밖 질문임을 안내", "환율 질문을 설명서 검토 대상으로 처리함."),
    "A10": ("실패", "해당 없음", "부적절", "설명서 밖 질문임을 안내", "영어 번역을 설명서 검토 대상으로 처리함."),
    "B01": ("통과", "적절", "적절", "PDF 43쪽: 엔진 오일 용량·점도 및 각주", "추천 오일 표와 각주를 함께 연결함. 생성 답변 수치는 미평가."),
    "B02": ("통과", "적절", "적절", "PDF 43쪽: 브레이크액 규격·각주 3", "표와 상세 규격 각주를 함께 연결함."),
    "B03": ("통과", "적절", "적절", "PDF 43쪽: HTRAC 리어 디퍼런셜 오일", "해당 용량·규격 행과 각주를 연결함."),
    "B04": ("통과", "적절", "적절", "PDF 43쪽: HTRAC 트랜스퍼 케이스 오일", "해당 용량·규격 행과 각주를 연결함."),
    "B05": ("통과", "적절", "적절", "PDF 45쪽: 차대번호 위치와 연결 그림", "차대번호 위치 원문에 연결됨. 그림 표시 여부는 저장된 응답 기준으로 확인."),
    "B06": ("통과", "적절", "적절", "PDF 33쪽: 실외 미러 접이 버튼 안내 번호", "차량 내부 I 원문에 연결됨. 번호 4가 있는 안내도."),
    "B07": ("통과", "적절", "적절", "PDF 246쪽: 주행 중 미러 조절·접기 경고", "실외 미러의 주행 중 조작 경고가 포함된 자료를 연결함."),
    "B08": ("실패", "부적절", "부적절", "PDF 239쪽: 실내 미러 조절", "실내 미러 질문에 실외 미러 PDF 246~249쪽이 선택됨."),
    "B09": ("통과", "적절", "적절", "PDF 54쪽: 올바른 안전벨트 착용", "착용 순서와 주의사항이 있는 자료에 연결됨."),
    "B10": ("통과", "적절", "적절", "PDF 54쪽: 차단 클립·스토퍼 금지", "질문의 두 물품에 대한 경고가 원문에 포함됨."),
    "B11": ("실패", "부적절", "부적절", "PDF 275쪽: 스마트 테일게이트 기능 설정", "켜는 위치 대신 기능 중지 방법 PDF 276~277쪽을 선택함."),
    "B12": ("통과", "적절", "적절", "PDF 275~278쪽: 작동 조건·감지 영역", "작동 조건과 감지 영역 자료를 함께 연결함. 중지 방법도 포함됨."),
    "B13": ("통과", "적절", "적절", "PDF 276~277쪽: 스마트 테일게이트 중지", "중지 방법 근거를 포함함. 작동 방법·감지 영역까지 표시해 후보는 넓음."),
    "B14": ("통과", "적절", "적절", "PDF 263~264쪽: 선루프 초기화", "정확한 미검토 원문을 안내하고 확정 답변은 보류함."),
    "B15": ("통과", "적절", "적절", "PDF 383쪽: 엔진 시동 전 확인할 사항", "해당 항목 원문을 안내하고 검토 상태를 유지함."),
    "B16": ("통과", "적절", "적절", "PDF 387쪽: 스마트 키 원격 시동", "원격 시동 원문을 안내하고 검토 상태를 유지함."),
    "B17": ("통과", "적절", "적절", "PDF 661쪽: 주행 중 시동이 꺼진 경우", "해당 상황의 원문을 안내함. 실제 원인 진단은 하지 않음."),
    "B18": ("통과", "적절", "적절", "PDF 52쪽: 냉각수 점검 경고", "제목은 엔진룸 점검이지만 본문에 냉각수 점검 경고가 있음."),
    "B19": ("통과", "적절", "적절", "PDF 43쪽: 연료 용량·종류", "추천 오일 표의 연료 67 L·무연 휘발유 행이 포함됨."),
    "B20": ("통과", "적절", "적절", "PDF 231쪽: 운전석 자세 메모리 초기화", "첫 후보로 초기화 원문을 찾음. 일반 메모리 설명도 함께 표시됨."),
    "C01": ("통과", "해당 없음", "적절", "부품·기능과 상황 확인 질문", "대상을 물어보고 검색은 실행하지 않음."),
    "C02": ("통과", "해당 없음", "적절", "시동 불가·주행 중 꺼짐·가속 불가 구분", "상태와 주행/정차 여부를 물음. 고장 원인을 확정하지 않음."),
    "C03": ("통과", "적절", "적절", "계기판 상태 확인 + 시동 관련 원문", "계기판 상태를 물으며 시동 전 확인 사항 원문을 안내함."),
    "C04": ("통과", "적절", "적절", "시동 관련 원문 안내; 계기판 질문 반복 제외", "시동 전 확인 사항을 안내하고 계기판 질문은 반복하지 않음. 진단 완료는 아님."),
    "C05": ("통과", "적절", "적절", "시동 관련 원문 안내; 계기판 질문 반복 제외", "시동 전 확인 사항을 안내함. 계기판 꺼짐의 원인을 특정한 것은 아님."),
    "C06": ("부분", "부분", "부분", "PDF 661쪽의 주행 중 시동 꺼짐 항목", "661쪽 후보는 있으나 교차로/건널목 항목임. 밀기 시동·시동 전 확인도 혼재함."),
    "C07": ("실패", "부적절", "부적절", "변속 상태·경고 표시 등 증상 확인", "가속 불가 증상에 차량 내부 II 안내도를 선택함."),
    "C08": ("통과", "해당 없음", "적절", "실외 미러인지 실내 미러인지 확인", "모호한 별칭을 바로 단정하지 않고 미러 종류를 물음."),
    "C09": ("통과", "적절", "적절", "PDF 246~249쪽: 실외 미러 접힘 설정", "외부 양쪽 거울을 실외 미러 자료로 연결함. 고장 원인은 미평가."),
    "C10": ("실패", "부적절", "부적절", "실내 미러 확인 또는 PDF 239쪽 밝기 조절", "거울 눈부심에 엔진룸 점검 자료를 선택함."),
    "C11": ("실패", "부적절", "부분", "테일게이트 확인 후 PDF 275쪽 조건 안내", "이름 재입력을 요청하지만 짐·차 뒤·열리지 않음의 의미를 좁히지 못함."),
    "C12": ("부분", "부분", "부분", "뒤쪽 문 종류 확인; 테일게이트면 275~278쪽", "감지 영역 자료는 관련 가능성이 있으나 문 종류·작동 조건을 확인하지 않음."),
    "C13": ("실패", "부적절", "부분", "테일게이트 확인 후 PDF 276~277쪽 중지", "이름 재입력을 요청하고 경보·열림 중지 의도에 맞는 원문은 표시하지 못함."),
    "C14": ("실패", "부적절", "부적절", "선루프 확인 후 PDF 263~264쪽 초기화", "닫힘 이상에 차량 외부 I 안내도를 선택함."),
    "C15": ("실패", "부적절", "부적절", "선루프 확인 후 PDF 264쪽 전원 차단·초기화", "배터리 관리 자료를 선택함. 선루프 초기화 조건·절차에 연결하지 못함."),
    "C16": ("통과", "적절", "적절", "PDF 105~110쪽: 안전벨트 골반띠 위치", "미검토 원문에 골반띠 위치와 복부 압박 경고가 포함되어 있음."),
    "C17": ("통과", "적절", "적절", "PDF 54쪽: 안전벨트 차단 클립 금지", "별칭 표현에서 안전벨트 차단 클립 경고 자료를 찾음."),
    "C18": ("통과", "적절", "적절", "PDF 45쪽: 차대번호 타각 위치", "고유번호·보닛 표현을 차대번호 위치 자료로 연결함."),
    "C19": ("부분", "부분", "부분", "엔진·변속기 등 어떤 오일인지 먼저 확인", "오일 표는 관련 있지만 종류 확인 질문 없이 여러 오일 용량 자료를 제시함."),
    "C20": ("실패", "부적절", "부분", "좌석 메모리 확인 후 PDF 231쪽 초기화", "이름 재입력을 요청하며 의자 위치 저장·다시 맞춤의 의미를 좁히지 못함."),
}


def load_and_grade():
    """마지막 파일 교체 실패를 복구합니다. 질문은 재실행하지 않으며 원시 결과는 보존합니다."""
    paths = [RESULTS / "results.json", RESULTS / "results.json.tmp"]
    choices = [json.loads(p.read_text(encoding="utf-8")) for p in paths if p.exists()]
    saved = max(choices, key=lambda d: (len(d["results"]), d.get("complete", False)))
    plan = json.loads((RESULTS / "plan.json").read_text(encoding="utf-8"))
    rows = saved["results"]
    assert len(rows) == 50 and len({r["case_id"] for r in rows}) == 50
    assert [(r["case_id"], r["question"]) for r in rows] == [(r["case_id"], r["question"]) for r in plan["cases"]]
    assert saved["dataset_sha256"] == plan["dataset_sha256"]
    assert all(hashlib.sha256((FOLDER / name).read_bytes()).hexdigest() == sha for name, sha in plan["code_hashes"].items())
    assert not any(r["error_type"] for r in rows)
    assert not any(r["packet"]["native_result"].get("llm_called", False) for r in rows)
    assert not any(r["packet"]["native_result"].get("db_written", False) for r in rows)
    assert hashlib.sha256((ROOT / "data/santafe_hev_manual.pdf").read_bytes()).hexdigest() == "8fef11ef06a5ec675868b54b00b49b40de6bd4445f9f123fd0b4f6e0c5daad1b"
    saved.update(complete=True, finalization_recovered=True)
    # 임시 파일은 증빙으로 남기고 정식 결과 파일을 완성합니다.
    (RESULTS / "results.json").write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
    graded = []
    for row in rows:
        overall, source, response, expected, note = GRADES[row["case_id"]]
        packet = row["packet"]
        native = packet["native_result"]
        actual = [{"title":s["title"].split(" · 매뉴얼")[0].replace("미검토 후보 · 보존 원문 · ", ""),
                   "pages":s["pdf_pages"]} for s in packet.get("sources", [])]
        # 여러 미검토 후보는 sources 배열 대신 화면 문구에 표시되므로 같은 실제 응답에서 복원합니다.
        if not actual:
            actual = [{"title":title, "pages":[int(n) for n in re.findall(r"\d+",pages)]}
                      for title,pages in re.findall(r"- 후보 \d+: (.+?) · PDF ([\d, ]+)쪽",packet["answer"]["text"])]
        graded.append({"case_id":row["case_id"], "group":row["group"], "question":row["question"],
                       "overall":overall, "source_grade":source, "response_grade":response,
                       "expected":expected, "note":note, "actual_sources":actual,
                       "native_status":packet["native_status"], "answer_text":packet["answer"]["text"],
                       "images_count":len(native.get("images",[])), "search_count":len(row["search_results"]),
                       "generation_grade":"미평가", "annotator":"Codex AI 잠정 평가", "human_confirmed":False})
    counts = dict(Counter(r["overall"] for r in graded))
    summary = {"completed":50,"failure_count":0,"finalization_recovered":True,
               "status_counts":dict(Counter(r["packet"]["native_status"] for r in rows)),
               "search_calls":sum(len(r["search_results"]) for r in rows),
               "generation_calls":0,"db_written":False,"human_confirmed":False,
               "ai_provisional_counts":counts,
               "groups":{g:dict(Counter(r["overall"] for r in graded if r["group"]==g)) for g in "ABC"},
               "quality_metrics":None,"note":"초기 응답의 AI 잠정 판정. 생성 답변·사용자 확정 골든셋·Hit@5·MRR는 미평가."}
    for name, data in [("graded_results.json",graded),("summary.json",summary),("failures.json",[])]:
        (RESULTS/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    with (RESULTS/"human_grading.csv").open("w",encoding="utf-8-sig",newline="") as stream:
        fields=["case_id","group","question","overall","source_grade","response_grade","expected","note","native_status","answer_text","search_count","generation_grade","annotator","human_confirmed"]
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction="ignore")
        writer.writeheader()
        writer.writerows(graded)
    return graded, summary


def make_pdf(rows, summary):
    """사용자에게 검토 가능한 질문별 실제 자료·기준·판정 이유를 표시합니다."""
    pdfmetrics.registerFont(TTFont("Malgun","C:/Windows/Fonts/malgun.ttf"))
    pdfmetrics.registerFont(TTFont("MalgunBold","C:/Windows/Fonts/malgunbd.ttf"))
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    pdf=canvas.Canvas(str(OUTPUT),pagesize=A4)
    pdf.setTitle("싼타페 50문항 평가 결과 - AI 잠정 판정")
    pdf.setAuthor("Codex AI - 사용자 검토 전 잠정 판정")
    width=A4[0]-84
    chunks=[rows[:10][i:i+4] for i in range(0,10,4)] + [rows[10:30][i:i+4] for i in range(0,20,4)] + [rows[30:][i:i+4] for i in range(0,20,4)]
    total=1+len(chunks)

    def footer(page):
        pdf.setStrokeColor(colors.HexColor("#DDE2EC"))
        pdf.line(42,37,A4[0]-42,37)
        pdf.setFont("Malgun",8)
        pdf.setFillColor(colors.HexColor("#707C90"))
        pdf.drawString(42,23,"2026-10-06 | 초기 응답 평가 | AI 잠정 판정 · 사용자 미확정")
        pdf.drawRightString(A4[0]-42,23,f"{page} / {total}")

    paragraph(pdf,"싼타페 HEV RAG",42,785,width,22,True)
    paragraph(pdf,"50문항 평가 결과 · 채점 완료본",42,742,width,18,True)
    paragraph(pdf,"AI가 실제 결과와 설명서를 대조한 잠정 평가입니다.",42,702,width,11,True,"#5644C8")
    y=651
    sections=[
        ("실행 결과",f"50/50문항 완료 · 질문 실행 오류 0건 · 검색 {summary['search_calls']}회 · 생성 답변 호출 0회. 마지막 저장 접근 오류는 보존된 50개 결과로 복구했습니다. 질문 재실행은 하지 않았습니다."),
        ("잠정 판정 요약", " / ".join(f"{k} {v}개" for k,v in summary["ai_provisional_counts"].items())+". 부분 판정은 통과에 포함하지 않습니다. 이 집계는 검색 Hit@5 또는 MRR 점수가 아닙니다."),
        ("유형별 판정", "\n".join(f"{g}: "+" / ".join(f"{k} {v}개" for k,v in summary["groups"][g].items()) for g in "ABC")),
        ("판정 기준", "통과: 맞는 원문 안내 또는 필요한 확인 질문. 부분: 관련 자료는 있으나 상황 구분·추가 확인이 부족. 실패: 다른 자료 선택 또는 설명서 밖 질문을 관련 자료로 처리. 미검토 원문 안내는 적절할 수 있으며 고장 원인 진단을 뜻하지 않습니다."),
        ("무엇을 확인했나요?", "저장된 실제 초기 응답·표시 원문과 동일한 779쪽 설명서의 관련 페이지를 대조했습니다. 쪽수는 PDF 기준입니다. 질문마다 새 대화로 실행했습니다. 사용자 브라우저의 실제 조작·그림 확대·후속 대화는 이번 평가에 포함하지 않았습니다."),
        ("이번 결과의 한계", "생성 버튼을 누른 최종 답변은 모두 미평가입니다. 정답 기준은 결과 수집 후 작성한 AI 잠정 기준으로, 사용자 확인 전에는 확정 골든셋으로 취급하지 않습니다. 전체 검색 후보의 순위별 관련성 채점도 남아 있어 Hit@5·MRR는 계산하지 않았습니다."),
        ("우선 보완 대상", "1. 설명서 밖 질문 분리  2. 실내/실외 미러 및 켜기/중지 의도 구분  3. 구어체 증상·위치 표현 연결  4. 오일·뒤쪽 문 등 모호한 대상 확인")]
    for heading,text in sections:
        paragraph(pdf,heading,42,y,width,11,True)
        # 줄바꿈을 단락으로 나누어 표시합니다.
        used=0
        for line in text.split("\n"):
            used+=paragraph(pdf,line,42,y-23-used,width,9.5)
        y-=used+43
    assert y>55,y
    footer(1)
    pdf.showPage()
    labels={"A":"설명서 밖 질문", "B":"직접 키워드 질문", "C":"모호한 표현·증상 질문"}
    status={"needs_review":"미검토 원문 안내", "evidence_excerpt":"검토 자료·답변 정리 버튼", "needs_clarification":"확인 질문", "insufficient_evidence":"근거 부족 안내"}
    palette={"통과":"#16714F","부분":"#9A6810","실패":"#AA3344"}
    for page,batch in enumerate(chunks,2):
        paragraph(pdf,f"{batch[0]['group']}  {labels[batch[0]['group']]}",42,789,width,16,True)
        paragraph(pdf,"자료 연결·초기 대응 판정 | 생성 답변은 전 문항 미평가",42,758,width,9)
        for index,row in enumerate(batch):
            top=725-index*166
            paragraph(pdf,row["case_id"],42,top,40,11,True,"#5644C8")
            h=paragraph(pdf,row["question"],88,top,width-46,11,True)
            cursor=top-max(h,20)-7
            fields=[
                (f"판정: {row['overall']} | 자료: {row['source_grade']} | 대응: {row['response_grade']}",True,palette[row["overall"]]),
                ("실제 대응: "+status.get(row["native_status"],row["native_status"]),False,"#263044"),
                ("표시 자료: "+(" / ".join(s["title"]+" ["+",".join(map(str,s["pages"]))+"]" for s in row["actual_sources"]) or "표시 원문 없음"),False,"#263044"),
                ("기대 대응·근거: "+row["expected"],False,"#263044"),
                ("평가 메모: "+row["note"],False,"#263044")]
            for text,bold,color in fields:
                cursor-=paragraph(pdf,text,88,cursor,width-46,9,bold,color)+3
            assert cursor>top-156,(row["case_id"],top-cursor)
            pdf.setStrokeColor(colors.HexColor("#E3E7F0"))
            pdf.line(42,top-156,A4[0]-42,top-156)
        footer(page)
        pdf.showPage()
    pdf.save()
    print(json.dumps({"pdf":str(OUTPUT),"pages":total,"summary":summary},ensure_ascii=False))


if __name__ == "__main__":
    make_pdf(*load_and_grade())
