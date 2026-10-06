"""확정된 질문 50개와 수기 채점 칸을 한글 PDF로 만듭니다. 정답 판정은 비워둡니다."""

import hashlib
import json
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(__file__).with_name("evaluation_50_questions.json")
OUTPUT = ROOT / "output/pdf/santafe_evaluation_50.pdf"


def paragraph(pdf, text, x, top, width, size=11, bold=False, color="#263044"):
    """한글 줄바꿈을 지원하는 문단을 그리고 실제 높이를 반환합니다."""
    style = ParagraphStyle("ko", fontName="MalgunBold" if bold else "Malgun", fontSize=size,
                           leading=size*1.55, wordWrap="CJK", textColor=colors.HexColor(color))
    item=Paragraph(escape(text),style)
    _,height=item.wrap(width,500)
    item.drawOn(pdf,x,top-height)
    return height


def footer(pdf, page):
    """페이지 번호와 기록지 성격을 표시합니다."""
    pdf.setStrokeColor(colors.HexColor("#DDE2EC"))
    pdf.line(42,37,A4[0]-42,37)
    pdf.setFont("Malgun",8)
    pdf.setFillColor(colors.HexColor("#707C90"))
    pdf.drawString(42,23,"싼타페 HEV RAG | 질문지 및 평가 기록지 | 2026-10-06")
    pdf.drawRightString(A4[0]-42,23,f"{page} / 11")


def main():
    """질문 순서를 그대로 보존해 표지 1쪽과 질문 기록지 10쪽을 만듭니다."""
    data=json.loads(SOURCE.read_text(encoding="utf-8"))
    assert [len(g["questions"]) for g in data["groups"]]==[10,20,20]
    pdfmetrics.registerFont(TTFont("Malgun","C:/Windows/Fonts/malgun.ttf"))
    pdfmetrics.registerFont(TTFont("MalgunBold","C:/Windows/Fonts/malgunbd.ttf"))
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    pdf=canvas.Canvas(str(OUTPUT),pagesize=A4)
    pdf.setTitle("싼타페 HEV RAG 50문항 평가 질문지")
    pdf.setAuthor("싼타페 HEV 개인 프로젝트")
    width=A4[0]-84
    paragraph(pdf,"싼타페 HEV RAG",42,780,width,22,True)
    paragraph(pdf,"50문항 평가 질문지 · 채점 기록",42,735,width,18,True)
    paragraph(pdf,"설명서 밖 10개 / 직접 키워드 20개 / 모호한 표현·증상 20개",42,692,width,11)
    y=640
    for heading,text in [
        ("평가 방법","1. 질문마다 새 대화로 시작합니다. 2. 문장을 그대로 입력합니다. 3. 표시된 자료·페이지·대응을 기록합니다. 4. 정답 근거와 대조해 성공 여부를 판단합니다."),
        ("무엇을 확인하나요?","자료 연결: 질문에 맞는 원문과 페이지를 찾았는가? 대응: 답변·원문 안내·확인 질문·범위 밖 안내 중 적절한 처리를 했는가?"),
        ("미검토 자료","미검토 자료에서 원문만 보여주는 것은 허용될 수 있습니다. 검토를 마치지 않은 내용을 확정 답변으로 생성하는지 확인합니다."),
        ("채점 전 주의","현재 질문은 확정됐지만 정답 페이지·후보 관련성은 사람 확인이 필요합니다. 판단하기 어려우면 미판정으로 남겨주세요. 일반 시동 안내가 실제 고장 원인을 입증하지는 않습니다."),
        ("이번 자동 수집 범위","현재 검색·근거 선택·초기 화면 응답을 수집합니다. 답변 정리 버튼은 자동 실행하지 않습니다. 생성 답변 평가는 사용자가 버튼을 누른 결과를 별도로 기록합니다."),
        ("점수 기준","자료 연결과 대응은 각각 1=적절, 0=부적절, 미판정=확인 필요로 기록합니다. 검색 점수는 직접 근거 판정 후 계산하며 설명서 밖·검색 미실행 사례는 별도 집계합니다.")]:
        paragraph(pdf,heading,42,y,width,12,True)
        height=paragraph(pdf,text,42,y-25,width,10)
        y-=height+52
    paragraph(pdf,"평가자: ____________________    평가일: ____________________",42,105,width,10)
    footer(pdf,1)
    pdf.showPage()
    page=2
    for group in data["groups"]:
        for start in range(0,len(group["questions"]),5):
            paragraph(pdf,f"{group['group']}  {group['label']}",42,790,width,16,True)
            paragraph(pdf,f"{start+1}~{min(start+5,len(group['questions']))}번 | 각 질문은 독립적으로 입력",42,758,width,9)
            for offset,question in enumerate(group["questions"][start:start+5]):
                top=725-offset*130
                number=f"{group['group']}{start+offset+1:02}"
                paragraph(pdf,number,42,top,38,11,True,"#5644C8")
                height=paragraph(pdf,question,88,top,width-46,11,True)
                assert height<=52, (number,height)
                paragraph(pdf,"대응: 답변 / 원문 안내 / 확인 질문 / 범위 밖 / 오류",88,top-50,width-46,9)
                paragraph(pdf,"자료·PDF 쪽수: __________________________________________________",88,top-69,width-46,9)
                paragraph(pdf,"자료 연결: 1 / 0 / 미판정    대응: 1 / 0 / 미판정",88,top-88,width-46,9)
                paragraph(pdf,"메모: __________________________________________________________",88,top-107,width-46,9)
                pdf.setStrokeColor(colors.HexColor("#E3E7F0"))
                pdf.line(42,top-122,A4[0]-42,top-122)
            footer(pdf,page)
            pdf.showPage()
            page+=1
    pdf.save()
    print(f"PDF_CREATED: {OUTPUT} | 50 questions | 11 pages")


if __name__ == "__main__":
    main()
