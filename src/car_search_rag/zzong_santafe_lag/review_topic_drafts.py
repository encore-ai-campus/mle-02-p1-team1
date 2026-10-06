"""화면에서 대조한 두 주제의 수정안을 만듭니다. 운영 부모·벡터·DB에 적용하지 않습니다."""

import json
import re
from copy import deepcopy

from .openai_migration import digest, write_json
from .post_refactor_checks import FOLDER
from .source_profile import FULL_SOURCE


def build_drafts():
    """원문 보존, 적용 사양·번호 복원, 그림의 실제 배치를 기록한 검토용 수정안을 반환합니다."""
    source = json.loads((FOLDER / "review_scope_expanded.json").read_text(encoding="utf-8"))
    if source["pdf_sha256"] != FULL_SOURCE.pdf_sha256:
        raise ValueError("검토한 PDF가 아닙니다.")
    rows = {row["record_id"]: deepcopy(row) for row in source["records"]}
    expected_ids = {"auto_topic_150", "auto_topic_171", "auto_topic_172", "auto_topic_173", "auto_topic_174"}
    if set(rows) != expected_ids:
        raise ValueError("검토한 다섯 원문 구간을 다시 확인하세요.")
    edits = []
    mirror = rows["auto_topic_150"]
    heading = "후진 시 실외 미러 자동 조절 기능"
    if heading not in mirror["content"]:
        raise ValueError("실외 미러의 확인한 제목이 없습니다.")
    mirror["content"] = mirror["content"].replace(heading, heading + " (사양 적용 시)", 1)
    mirror["content"] = mirror["content"].replace("Ď", "잠금 기호").replace("ď", "잠금 해제 기호")
    # [프로젝트 추가] 페이지 249의 단계 번호를 같은 원문 문장 앞에 복원합니다. 경고·조건은 요약하지 않습니다.
    step_starts = ["차량이 정지한 상태인지 확인하십시오.", "브레이크 페달을 밟고, 기어를 'R'(후진)로 변속하십시오.",
                   "조절을 원하는 실외 미러 선택을 위해", "다시 'P'(주차), 'N'(중립), 'D'(주행)로 변속하거나",
                   "반대편 미러도 동일한 방법(1-4)으로 설정하십시오."]
    for number, phrase in enumerate(step_starts, 1):
        if mirror["content"].count(phrase) != 1:
            raise ValueError("원문 조작 단계의 시작 문장이 달라졌습니다.")
        mirror["content"] = mirror["content"].replace(phrase, f"\n{number}. " + phrase, 1)
    edits.append({"record_id": mirror["record_id"], "pages": [248, 249],
                  "changes": ["후진 자동 조절의 사양 적용 시 조건 복원", "오토리버스 조작 단계 1~5 복원", "추출이 깨진 잠금 기호를 버튼 이름으로 설명"]})
    stop = rows["auto_topic_173"]
    old_buttons = "도어 잠금 버튼 도어 잠금 해제 버튼 테일게이트 열림/닫힘 버튼 비상 경보 버튼"
    new_buttons = "\n1: 도어 잠금 버튼\n2: 도어 잠금 해제 버튼\n3: 테일게이트 열림/닫힘 버튼\n4: 비상 경보 버튼\n"
    if stop["content"].count(old_buttons) != 1:
        raise ValueError("스마트 키의 확인한 버튼 목록이 달라졌습니다.")
    stop["content"] = stop["content"].replace(old_buttons, new_buttons, 1)
    stop["content"] = re.sub(r"\(\s*û\s*\)", "", stop["content"])
    edits.append({"record_id": stop["record_id"], "pages": [276, 277],
                  "changes": ["A/B타입 스마트 키의 버튼 번호 1~4 복원", "문맥에 이미 이름이 있는 깨진 테일게이트 기호 제거"]})
    descriptions = {
        (246, "/I1"): ("실외 미러", "차량 문에 장착된 실외 미러를 보여준다."),
        (247, "/I1"): ("실외 미러 조절 방법", "1번 L/R 선택 스위치와 2번 미러 방향 조절부를 보여준다."),
        (247, "/I4"): ("실외 미러 접힘/펴짐 방법", "실외 미러 접이 버튼을 화살표로 가리킨다."),
        (249, "/I1"): ("후진 시 실외 미러 자동 조절 기능", "후진 변속, L/R 선택 스위치 1번과 미러가 아래로 기울어지는 모습을 보여준다."),
        (275, "/I1"): ("스마트 테일게이트", "짐을 든 사람이 차량 뒤로 접근하는 방향과 테일게이트가 위로 열리는 방향을 보여준다."),
        (276, "/I4"): ("스마트 테일게이트 기능 중지 방법", "A타입 스마트 키의 잠금 1번, 잠금 해제 2번, 테일게이트 3번, 비상 경보 4번 버튼을 보여준다."),
        (277, "/I1"): ("스마트 테일게이트 기능 중지 방법", "B타입 스마트 키의 잠금 1번, 잠금 해제 2번, 테일게이트 3번, 비상 경보 4번 버튼을 보여준다."),
        (278, "/I1"): ("감지 영역", "테일게이트 뒤쪽 감지 영역과 약 50~100cm 범위를 표시한다."),
    }
    links, removed = [], []
    for image in source["images"]:
        # [프로젝트 추가] 275쪽 그림은 개요 제목 아래, 276쪽 스마트 키는 기능 중지 제목 아래에 있습니다.
        # 작동 설명에 같은 페이지라는 이유만으로 연결한 두 그림은 이 수정안에서 제외합니다.
        if image["parent_record_id"] == "auto_topic_172":
            removed.append({"parent_record_id": image["parent_record_id"], "image_id": str(image["id"]),
                            "pdf_page_number": image["pdf_page_number"], "reason": "페이지 전체 연결을 실제 그림 소제목 연결로 보완"})
            continue
        identity = (image["pdf_page_number"], image["pdf_image_key"])
        if identity not in descriptions:
            raise ValueError("직접 대조한 그림 키가 아닙니다.")
        title, description = descriptions[identity]
        links.append({"parent_record_id": image["parent_record_id"], "image_id": str(image["id"]),
                      "pdf_page_number": identity[0], "pdf_image_key": identity[1],
                      "source_heading": title, "description": description,
                      "storage_path": image["storage_path"], "scope": "Codex의 PDF 화면 대조. 아직 DB 연결 변경 없음."})
    return {"source_run_id": source["source_run_id"], "pdf_sha256": source["pdf_sha256"],
            "source_content_sha256": {row["record_id"]: digest(row["content"]) for row in source["records"]},
            "draft_records": list(rows.values()), "edits": edits, "draft_image_links": links,
            "removed_links": removed,
            "required_context_proposal": {"auto_topic_171": ["auto_topic_172", "auto_topic_173", "auto_topic_174"],
                                          "auto_topic_172": ["auto_topic_173", "auto_topic_174"]},
            "boundary_review": "246쪽 위의 디지털 센터 미러 표와 250쪽 하이패스는 실외 미러에서 제외. 275~278쪽 스마트 테일게이트·감지 영역을 함께 대조.",
            "reviewer": "Codex의 원본 화면 대조", "human_confirmed": False,
            "raw_text_preserved": all(row["raw_text"] == rows[row["record_id"]]["raw_text"] for row in source["records"]),
            "production_verification_status_changed": False, "applied": False,
            "db_written": False, "storage_uploaded": False, "new_embeddings": False,
            "next_integration": "새 원문/청킹 버전의 미리보기와 영향 개수 확인 후 변경된 입력만 재임베딩할 수 있는 저장 방안을 검토. 검토 상태만 현재 DB에서 승격하지 않음."}


if __name__ == "__main__":
    result = build_drafts()
    target = FOLDER / "review_drafts.json"
    if target.exists():
        raise SystemExit("기존 수정안이 있습니다. 같은 파일을 덮어쓰지 않습니다.")
    write_json(target, result)
    print(json.dumps({"path": str(target), "draft_records": len(result["draft_records"]),
                      "draft_image_links": len(result["draft_image_links"]),
                      "removed_links": len(result["removed_links"]), "applied": False}, ensure_ascii=False))
