"""화면에서 대조한 8개 자료의 보완안을 저장합니다. 평가 종료 전에는 운영에 적용하지 않습니다."""

import hashlib
import json
from copy import deepcopy

from .review_batch_20261006 import FOLDER, IDS


def restore_steps(content, phrases):
    """원본 화면에서 확인한 순서 번호를 문장 앞에 복원합니다. 원문 문장을 삭제하지 않습니다."""
    for number, phrase in enumerate(phrases,1):
        if content.count(phrase)!=1:
            raise ValueError("번호를 복원할 문장이 유일하지 않습니다: "+phrase)
        content=content.replace(phrase,f"\n{number}. "+phrase,1)
    return content


def main():
    """본문·표·사양 조건과 그림 연결을 별도 수정안으로 남깁니다. 벡터와 DB는 변경하지 않습니다."""
    source=json.loads((FOLDER/"source_snapshot.json").read_text(encoding="utf-8"))
    rows={r["record_id"]:deepcopy(r) for r in source["records"]}
    assert set(rows)==IDS
    notes={
        "auto_topic_135":["PDF 229쪽 제목의 사양 적용 시 조건 복원", "메모리 버튼 1·2 그림 확인. 개인화 설정은 다른 제목으로 경계 제외"],
        "auto_topic_139":["PDF 231쪽 초기화 방법 1~4 및 진행 1~3 번호 복원", "이전 승하차 설정과 다음 스마트 자세 제어 시스템 제외. 정지 조건·주의·참고 보존"],
        "auto_topic_149":["PDF 239~246쪽 전체와 오류 표의 다음 페이지 연속 확인", "디지털 센터 미러 사양 적용 시 조건, A 센서·버튼 1~5·A/B 모드·조작 단계 복원", "깨진 밝기/상하 각도 아이콘과 오류 표의 열 관계 복원", "246쪽 실외 미러 그림 연결 제외. 실내/ECM과 디지털 센터 미러 구간 분리는 후속 검색 설계 과제"],
        "auto_topic_160":["PDF 263~264쪽 초기화 조건·단계 1~4 복원", "앞좌석 선루프·뒷좌석 파워 선블라인드 그림을 구별", "264쪽 선루프 열림 경고 그림 연결 제외. 262~263쪽 일반 경고는 별도 필수 문맥 검토 대상으로 기록"],
        "auto_topic_274":["PDF 383쪽 확인 순서 1~5와 384쪽 출발 순서 1~3 복원", "385~386쪽 비상 시동·경고·불가 조치까지 대조. 383쪽 위 시동 버튼 경고 및 386쪽 엔진 정지 방법은 다른 제목으로 제외", "제목은 시동 전 확인이지만 여러 시동 상황이 포함돼 있어 검색용 세부 제목 분리가 후속 과제"],
        "auto_topic_276":["PDF 387쪽 잠금·원격 시동 버튼 깨진 기호를 명시적 버튼 이름으로 복원", "거리 10m·잠금 후 4초·탑승 제한 10분·P 조건 및 후드/테일게이트 조건 보존", "387쪽 위 엔진 정지 경고 및 다음 자동 변속기 제외"],
        "auto_topic_420":["PDF 661쪽 해당 제목의 두 문장과 경계 확인. 본문 보완 불필요", "교차로·펑크·브레이크 제동 불량은 서로 다른 항목. 이 기록은 모든 차량 고장 대응을 다루지 않음"],
        "auto_topic_73":["PDF 105~112쪽 본문·경고·착용 그림과 113쪽 경계 확인", "110쪽 착용 1~4·112쪽 중앙 좌석 1~3 번호 및 중앙 좌석 사양 적용 시 조건 복원", "112쪽 다음 제목 안전벨트 프리텐셔너 그림 연결 제외. 105쪽 통풍 시트 주의는 다른 항목으로 제외"]}
    r=rows["auto_topic_135"]
    r["content"]=r["content"].replace("운전석 자세 메모리 시스템", "운전석 자세 메모리 시스템 (사양 적용 시)",1)
    r=rows["auto_topic_139"]
    r["content"]=restore_steps(r["content"],["시동 'ON' 상태에서 'P'(주차)로 변속하고 운전석 도어를 여십시오.","운전석 전후 위치 및 등받이 각도 조절 스위치를 이용하여", "1번 버튼과 운전석 전방 이동 스위치를 동시에 누르십시오", "알림음이 울리면 스위치에서 손을 떼십시오."])
    r["content"]=restore_steps(r["content"],["경고음이 작동하며 초기화 진행을 시작합니다.","좌석 및 등받이가 뒤쪽으로 자동 이동합니다.","다시 좌석 및 등받이가 정중앙으로 이동하고"])
    r=rows["auto_topic_160"]
    r["content"]=restore_steps(r["content"],["시동을 걸거나 차량 전원을 'ON' 상태로 두십시오.","선루프 스위치로 앞좌석 선루프 글라스 또는", "선루프 글라스 또는 파워 선블라인드가 닫힌 상태에서", "선루프 글라스 또는 파워 선블라인드가 열렸다가 완전히 닫힐 때까지"])
    r=rows["auto_topic_274"]
    r["content"]=restore_steps(r["content"],["스마트 키를 휴대하고 운전석에 앉으십시오.","엔진에 시동을 걸기 전에 우선 안전벨트를 착용하십시오.","파킹 브레이크를 걸고, 기어가 'P'(주차) 상태인지 확인하십시오.","모든 전기 장치를 끄십시오.","가속 페달과 브레이크 페달의 위치와 헐거운 정도를 오른발로 확인하십시오."])
    r["content"]=restore_steps(r["content"],["브레이크 페달을 밟은 상태에서 시동 버튼을 누르십시오.","브레이크 페달을 계속 밟고 있는 상태에서", "파킹 브레이크를 해제한 후 브레이크 페달에서 발을 떼면서"])
    r=rows["auto_topic_276"]
    r["content"]=r["content"].replace("( Ď)","(잠금 기호)").replace("(Ĕ)","(원격 시동 기호)").replace("( Ĕ)","(원격 시동 기호)")
    r=rows["auto_topic_73"]
    r["content"]=restore_steps(r["content"],["플레이트(1)와 벨트를 잡으십시오.","벨트를 천천히 당기십시오.","\"찰칵\" 소리가 날 때까지 플레이트(1)를 버클(2)에 밀어 넣으십시오.","골반띠를 복부 아래 골반에 위치시키고"])
    r["content"]=restore_steps(r["content"],["시트 쿠션에 있는 수납 홈에서 버클(2)을 빼십시오.","버클(2)에 'CENTER'가 표기되었는지 확인하고", "안전벨트를 해제한 후에는 다시 버클을 시트 쿠션에 있는 수납 홈에 넣으십시오."])
    r["content"]=r["content"].replace("뒷좌석 중앙(5인승, 7인승)","뒷좌석 중앙(5인승, 7인승) (사양 적용 시)",1)
    r=rows["auto_topic_149"]
    r["content"]=r["content"].replace("센서A:A:","A: 센서",1)
    r["content"]=r["content"].replace("디지털 센터 미러 디지털 센터 미러는","디지털 센터 미러 (사양 적용 시) 디지털 센터 미러는",1)
    old="시스템 구성요소 아이콘 표시 영역 아이콘 표시, 밝기 및 각도 조절 레버 디지털 미러 모드와 광학 미러 모드의 전환에 사용 메뉴 버튼 메뉴 버튼을 눌러 아이콘 표시 영역을 확인하고 원하는 밝기와 각도를 선택함 선택/조절 버튼 원하는 항목의 설정을 변경 카메라 표시등 카메라의 정상 작동을 나타냄"
    new="시스템 구성요소\n1. 아이콘 표시 영역: 아이콘 표시, 밝기 및 각도 조절\n2. 레버: 디지털 미러 모드와 광학 미러 모드의 전환에 사용\n3. 메뉴 버튼: 메뉴 버튼을 눌러 아이콘 표시 영역을 확인하고 원하는 밝기와 각도를 선택함\n4. 선택/조절 버튼: 원하는 항목의 설정을 변경\n5. 카메라 표시등: 카메라의 정상 작동을 나타냄"
    assert r["content"].count(old)==1
    r["content"]=r["content"].replace(old,new,1)
    r["content"]=r["content"].replace("모드 변경 방법 디지털 모드 일반 모드", "모드 변경 방법 A: 디지털 모드 / B: 일반 모드",1)
    r["content"]=restore_steps(r["content"],["모드 선택 레버를 끝까지 당기면", "모드 선택 레버를 끝까지 밀어서"])
    r["content"]=restore_steps(r["content"],["메뉴 버튼(1)을 통해 디스플레이 밝기와", "메뉴 버튼을 반복해서 눌러 조절하려는 항목을 선택하십시오.", "버튼(2) 또는 버튼(3)을 눌러 설정을 변경합니다."])
    r["content"]=r["content"].replace("아이콘 설정 Ń", "아이콘 설정 [밝기 아이콘]").replace("ń 표시화면", "[상하 각도 아이콘] 표시화면")
    marker="디지털 센터 미러 오류 아이콘 및 해결 방법"
    assert r["content"].count(marker)==1
    r["content"]=r["content"].split(marker)[0]+marker+"\n"+"\n".join([
        "증상: 화면 오른쪽에 온도계 아이콘 표시 | 가능한 원인: 디지털 센터 미러가 매우 뜨겁습니다. 화면이 점차 어두워지며 온도가 계속 상승하면 디지털 센터 미러가 꺼집니다. | 해결책: 실내 온도를 낮춰 미러 온도를 낮추십시오. 거울이 식으면 아이콘이 사라집니다. 미러가 차가워도 아이콘이 사라지지 않으면 당사 직영 하이테크센터나 블루핸즈에 문의해 점검을 받으십시오.",
        "증상: 디지털 모드 아이콘이 꺼지고 영상에러 아이콘 표시 | 가능한 원인: 시스템이 오작동할 수 있습니다. | 해결책: 광학 미러 모드로 변경 후 당사 직영 하이테크센터나 블루핸즈에 문의해 점검을 받으십시오."])
    # 아래 보완안은 본문과 그림 경계를 확인한 기록입니다. 운영 검토 상태는 승격하지 않습니다.
    removed={("auto_topic_149",246,"/I1"):"다음 실외 미러 항목의 그림", ("auto_topic_160",264,"/I4"):"다음 선루프 열림 경고 항목의 그림", ("auto_topic_73",112,"/I3"):"다음 안전벨트 프리텐셔너 항목의 그림"}
    image_proposals=[]
    for image in source["images"]:
        identity=(image["parent_record_id"],image["pdf_page_number"],image["pdf_image_key"])
        image_proposals.append({"image_id":str(image["id"]),"parent_record_id":identity[0],"pdf_page_number":identity[1],"pdf_image_key":identity[2],
                                "proposal":"연결 제외" if identity in removed else "해당 구간 그림으로 유지 후보",
                                "reason":removed.get(identity,"원본 페이지 배치와 본문 구간을 대조함. 개별 저장 이미지 파일 내용·ID·경로 검증은 적용 전에 추가 필요"),
                                "production_linkage_status_changed":False})
    payload={"source_run_id":source["source_run_id"],"pdf_sha256":source["pdf_sha256"],
             "reviewer":"Codex 원본 전체 페이지 화면 대조", "human_confirmed":False,
             "apply_after":"사용자 직접 평가 완료 후", "activated":False,"db_written":False,"new_embeddings":False,
             "original_content_sha256":{r["record_id"]:hashlib.sha256(r["content"].encode()).hexdigest() for r in source["records"]},
             "draft_records":list(rows.values()),"findings":notes,"image_proposals":image_proposals,
             "raw_text_preserved":all(r["raw_text"]==rows[r["record_id"]]["raw_text"] for r in source["records"]),
             "counts":{"source_compared_records":8,"original_text_no_change":1,"text_drafts":7,"image_links_checked_by_page":26,"exclude_link_proposals":3},
             "pending_before_activation":["그림 파일별 ID·내부 키·Storage 경로와 실제 픽셀 일치 확인", "선루프 일반 경고 등 필수 문맥 의존성 검토", "본문 변경 구간의 재청킹·두 벡터 공간 재임베딩", "새 검토 버전 저장 및 독립 검색 비교", "사용자 직접 평가 종료 확인"],
             "remaining_original_unreviewed_not_compared":494}
    assert payload["raw_text_preserved"]
    (FOLDER/"draft_review.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    lines=["# 미검토 자료 2차 원본 대조", "", "검토일: 2026-10-06. 사용자 요청에 따라 직접 평가 종료 전 운영 반영하지 않습니다.", "",
           "8개 자료의 본문과 경계를 대조했습니다. 7개는 본문 보완안을 작성했고 1개는 본문 변경이 불필요합니다.",
           "그림 연결 26개를 페이지 배치에서 대조해 다른 항목 그림 3개를 제외하는 안을 기록했습니다. 개별 파일 검증은 남아 있습니다.", "",
           "운영 상태는 검토 25개·미검토 502개를 유지합니다. 이번에 대조하지 않은 미검토 원래 자료는 494개입니다.", ""]
    for identity,row in rows.items():
        lines.extend([f"## {row['title']} ({identity})", "", "PDF 페이지: "+", ".join(map(str,row["source_pages"])), ""]+["- "+note for note in notes[identity]]+[""])
    lines.extend(["## 적용 전 남은 작업", ""]+["- "+note for note in payload["pending_before_activation"]]+[""])
    (FOLDER/"report.md").write_text("\n".join(lines),encoding="utf-8")
    print(json.dumps(payload["counts"],ensure_ascii=False))


if __name__=="__main__":
    main()
