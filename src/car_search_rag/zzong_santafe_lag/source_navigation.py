"""찾은 후보의 원본 안내와 명시적인 직전 자료 요청을 처리합니다. 검색·생성은 하지 않습니다."""

import re
from copy import deepcopy
from urllib.parse import quote, urlparse

from .source_profile import FULL_SOURCE
from .answer_service import question_terms
from .question_input import prepare_question, starting_symptom_prompt, symptom_candidate_fits


def focused_candidates(result):
    """단일 질문의 후보 제목에서 주제 단어가 가장 많이 일치하는 자료만 표시합니다."""
    candidates = result.get("review_candidates", [])
    # 복합 질문은 서로 다른 주제를 요청하므로 제목 점수 하나로 일부 항목을 없애지 않습니다.
    if len(result.get("subquestions", [])) > 1:
        return candidates
    prepared = result.get("input_processing") or prepare_question(result.get("question", ""))
    question = prepared.get("search_question", result.get("question", ""))
    # 기존 대화에 저장된 후보도 같은 상황 기준으로 표시합니다. 다른 상태의 자료를 뒤섞지 않습니다.
    candidates = [candidate for candidate in candidates
                  if symptom_candidate_fits(question, candidate.get("title", ""))]
    terms = question_terms(question)
    scored = [(sum(term in re.sub(r"\s+", "", str(candidate.get("title", "")).lower())
                   for term in terms), candidate) for candidate in candidates]
    highest = max((score for score, _ in scored), default=0)
    # [프로젝트 추가] 본문의 우연한 단어 일치를 표시 후보에서 줄입니다. 의미 정확도 판정은 아닙니다.
    # 제목 일치가 없으면 넓은 후보를 대신 제시하지 않습니다. 원래 후보·검토 상태는 보존합니다.
    return [candidate for score, candidate in scored if score == highest and highest > 0]


def followup_kind(question):
    """본문/그림을 보여달라는 짧은 요청만 인식합니다. 새 주제가 있는 질문은 연결하지 않습니다."""
    text = re.sub(r"[\s?!？！.,。~]", "", question)
    prefix = r"(?:(?:방금|직전|앞의|이전|그|관련|같은)(?:찾은|보여준)?)?"
    suffix = r"(?:좀)?(?:다시)?(?:찾아봐|찾아줘|보여줘|보여주세요|열어줘|열어주세요)"
    if re.fullmatch(prefix + r"(?:본문|원문|설명서)(?:을|를)?" + suffix, text):
        return "source"
    if re.fullmatch(prefix + r"(?:그림|사진)(?:을|를)?" + suffix, text):
        return "image"
    return None


def pdf_locator(service):
    """기존 검색이 확인한 문서 행과 Storage 주소만 재사용합니다. 새 DB 조회는 없습니다."""
    search = getattr(getattr(service, "evidence_service", None), "search_service", None)
    document = getattr(search, "document", None) or {}
    storage_url = getattr(search, "storage_url", None) or ""
    parsed = urlparse(storage_url)
    expected = f"cars/hyundai/santafe_hev/zzong_santafe_lag/{FULL_SOURCE.pdf_sha256}/santafe_hev_manual.pdf"
    # 경로·PDF 식별값을 대조해 다른 팀원의 PDF나 임의 주소로 연결하지 않습니다.
    if (document.get("file_sha256") != FULL_SOURCE.pdf_sha256
            or document.get("storage_bucket") != "images" or document.get("storage_path") != expected
            or parsed.scheme != "https" or not (parsed.hostname or "").endswith(".supabase.co")
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        return None
    return f"https://{parsed.hostname}/storage/v1/object/public/images/{quote(expected, safe='/')}"


def clean_pages(row):
    """실제 자료에서 가져온 유효한 PDF 쪽수만 반환합니다. 임의 쪽수는 만들지 않습니다."""
    return list(dict.fromkeys(page for page in row.get("source_pages", [])
                             if type(page) is int and 1 <= page <= FULL_SOURCE.page_count))


def source_groups(result):
    """확인된 출처 또는 미검토 후보 묶음 최대 3개를 서로 구분해 반환합니다."""
    if result.get("sources"):
        return [{"title": "직전 질문의 설명서 원문", "rows": deepcopy(result["sources"]),
                 "unreviewed": False}]
    if result.get("status") != "needs_review":
        return []
    groups, seen = [], set()
    for candidate in focused_candidates(result):
        rows = candidate.get("context_records", [])
        identity = tuple(row.get("record_id") for row in rows)
        if not identity or identity in seen:
            continue
        seen.add(identity)
        rows = [deepcopy(row) for row in rows if clean_pages(row)]
        if rows:
            groups.append({"title": candidate.get("title", "설명서 후보"),
                           "rows": rows, "unreviewed": True})
        if len(groups) == 3:
            break
    return groups


def markdown_label(text):
    """PDF 제목을 표시 문자로만 사용하도록 링크·제목 기호와 줄바꿈을 보호합니다."""
    text = re.sub(r"\s+", " ", str(text))
    return re.sub(r"([\\`*\[\]<>#_])", r"\\\1", text)


def candidate_notice(result, locator):
    """미검토 후보 제목·쪽수·원본 열기 링크를 만듭니다. 내용 요약이나 확정 답변은 하지 않습니다."""
    groups = source_groups(result)
    if result.get("status") != "needs_review":
        return "", []
    if not groups:
        return ("질문과 제목이 일치하는 원문 후보를 좁히지 못했습니다. "
                "찾으려는 부품이나 기능 이름과 궁금한 내용을 함께 알려주세요."), []
    symptom_prompt = starting_symptom_prompt(result.get("question", ""))
    if len(groups) == 1:
        # 하나뿐인 자료는 선택 번호·중간 버튼 없이 원본과 보존 원문으로 바로 연결합니다.
        # 미검토 내용을 간추린 절차로 생성하지 않고 제목·실제 쪽수만 안내합니다.
        group = groups[0]
        pages = list(dict.fromkeys(page for row in group["rows"] for page in clean_pages(row)))
        lines = [f"**{markdown_label(group['title'])}** · PDF {', '.join(map(str, pages))}쪽",
                 "검토 중인 설명서 자료입니다. 질문에 대한 확정 답변은 보류합니다."]
        if symptom_prompt:
            lines.append("찾은 자료는 시동 관련 설명서 항목입니다. 실제 고장 원인을 확인한 결과는 아닙니다.")
            lines.append(symptom_prompt)
        if locator:
            lines.append(f"[원본 PDF 열기]({locator}#page={pages[0]})")
        else:
            lines.append("연결된 PDF 주소를 확인하지 못했습니다. 내려받은 원본 PDF에서 위 쪽수를 확인해주세요.")
        lines.append("아래 ‘검색에 사용한 설명서’를 펼치면 저장된 원문과 이어지는 문맥을 볼 수 있습니다.")
        return "\n\n".join(lines), []
    # 공통 화면은 '확인' 제목에 완료 체크 아이콘을 붙이므로 미검토 제목은 굵은 글자로 표시합니다.
    lines = ["**검토가 필요한 원문 후보**", "아래 자료는 미검토 후보이며, 질문에 대한 확정 답변이 아닙니다."]
    if symptom_prompt:
        lines.append("찾은 자료는 시동 관련 설명서 항목입니다. 실제 고장 원인을 확인한 결과는 아닙니다.")
        lines.append(symptom_prompt)
    actions = []
    for index, group in enumerate(groups):
        pages = list(dict.fromkeys(page for row in group["rows"] for page in clean_pages(row)))
        lines.append(f"- 후보 {index + 1}: {markdown_label(group['title'])} · PDF {', '.join(map(str, pages))}쪽")
        if locator:
            lines.append(f"  [후보 {index + 1} 원본 PDF 열기]({locator}#page={pages[0]})")
        actions.append({"id": f"view_source_{index}", "label": f"후보 {index + 1} 원문 보기"})
    if not locator:
        lines.append("연결된 PDF 주소를 확인하지 못했습니다. 내려받은 원본 PDF에서 위 쪽수를 확인해주세요.")
    lines.append("원문 보기 버튼으로 이 후보와 이어지는 문맥을 확인할 수 있습니다.")
    return "\n\n".join(lines), actions


def source_view(result, group, question, locator):
    """선택한 묶음의 보존 원문을 별도 보기로 만듭니다. 검토 상태·생성 근거는 변경하지 않습니다."""
    unreviewed = group["unreviewed"]
    text = ("설명서 원문입니다. 아직 검토 중이며, 절차나 고장 원인을 확정한 답변이 아닙니다."
            if unreviewed else "직전 질문과 연결된 설명서 원문입니다. 아래 ‘검색에 사용한 설명서’를 펼쳐 확인해주세요.")
    sources = []
    for number, row in enumerate(group["rows"], 1):
        pages = clean_pages(row)
        if not pages:
            continue
        title = row.get("title", "설명서 원문")
        text += f"\n\n- {markdown_label(title)} · PDF {', '.join(map(str, pages))}쪽"
        if locator:
            text += f"\n\n[원본 PDF {pages[0]}쪽 열기]({locator}#page={pages[0]})"
        # 원문은 st.text로 표시하는 기존 출처 영역에 전달합니다. 요약·잘라내기·Markdown 실행을 하지 않습니다.
        has_raw = bool(row.get("raw_text"))
        raw = row.get("raw_text") or row.get("content") or row.get("quote") or ""
        kind = "보존 원문 · " if has_raw else "보존 원문 없음 — 저장된 글 · "
        sources.append({"label": f"원문 {number}", "title": ("미검토 후보 · " if unreviewed else "") + kind + title,
                        "source_file": "santafe_hev_manual.pdf", "pdf_pages": pages, "quote": raw})
    return {"question": question, "status": "source_view", "answer": text, "view_sources": sources,
            "sources": [], "images": deepcopy(result.get("images", [])) if not unreviewed else [],
            "pending_image_references": [], "review_candidates": deepcopy(result.get("review_candidates", [])),
            "related_question": result.get("question"), "unreviewed_source_view": unreviewed,
            "retrieval_performed": False, "query_embedding_api_called": False, "llm_called": False,
            "db_written": False, "storage_uploaded": False}


def image_view(result, question):
    """직전 결과의 표시 가능한 그림만 재사용하고 없는 그림은 만들어 안내하지 않습니다."""
    view = deepcopy(result)
    available = len(result.get("images", []))
    pending = len(result.get("pending_image_references", []))
    view.update(question=question, status="source_view", sources=[], view_sources=[],
                answer=("직전 질문과 연결된 그림입니다. 아래 그림과 원본 설명서를 함께 확인해주세요." if available else
                        "직전 자료의 그림은 원본 또는 연결 확인이 남아 표시를 보류합니다." if pending or result.get("status") == "needs_review" else
                        "직전 결과에는 표시할 수 있는 그림이 없습니다. 어떤 부품의 그림인지 알려주세요."),
                related_question=result.get("question"), retrieval_performed=False,
                query_embedding_api_called=False, llm_called=False, db_written=False, storage_uploaded=False)
    return view
