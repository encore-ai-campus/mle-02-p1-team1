"""저장된 PDF 근거를 골라 설명서 발췌·출처·그림을 함께 반환합니다."""

# [프로젝트 적용] 기존 DB 검색 결과의 부모 원문·필수 각주·검토 상태를 재사용합니다.
# [프로젝트 추가] 첫 M5 단계는 원문 발췌입니다. 별도 LLM·외부 자료 API는 호출하지 않습니다.
# 문장을 새로 요약하지 않으므로 수치·경고·각주를 생성 과정에서 바꾸지 않습니다.
# 한계: 아래 단어 일치 규칙은 관련 근거 선택용이며 질문 전체의 답변 가능성을 증명하지 않습니다.

import re
from copy import deepcopy

from .db_search_service import DbFullSearchService


REVIEWED_STATUSES = {"sample_verified", "visually_reviewed_source"}
NO_EVIDENCE_MESSAGE = "제공된 설명서에서 확인할 수 없습니다. 현재 질문에 답할 근거를 확보하지 못했습니다."


def question_terms(question):
    """간단한 조사·질문 표현을 제외한 글자를 근거 선택에 사용합니다. 형태소 분석기는 아닙니다."""
    # [프로젝트 추가] 이미 배운 정규표현식으로 최소 규칙을 작성합니다.
    # 새 라이브러리 없이 '차대번호는'과 본문의 '차대번호'를 비교하려는 용도입니다.
    ignored = {"어디", "어디서", "언제", "어떻게", "무엇", "무엇인가요", "얼마", "몇", "알려줘",
               "알려주세요", "설명", "확인", "확인하나요", "점검", "하나요", "해야", "되나요",
               "방법", "용량", "사양", "추천", "주의", "관련", "기능", "있는", "없나요", "맞나요",
               "나요", "궁금", "것", "좀", "차량", "차", "내", "싼타페", "hev", "시스템"}
    terms = []
    for word in re.findall(r"[가-힣A-Za-z0-9]+", question.lower()):
        for ending in ("에서는", "에서", "으로", "까지", "부터", "처럼", "에는", "은", "는", "을", "를", "의", "이", "가", "과", "와", "에"):
            if word.endswith(ending) and len(word) - len(ending) >= 2:
                word = word[:-len(ending)]
                break
        if len(word) >= 2 and word not in ignored:
            terms.append(word)
    return list(dict.fromkeys(terms))


def outside_pdf_reason(question):
    """실시간 조회·개별 차량 고장 진단 요청만 명시적 표현으로 구별합니다. 모든 범위 밖 질문 분류기는 아닙니다."""
    text = re.sub(r"\s+", "", question.lower())
    if any(word in text for word in ("최신리콜", "현재리콜", "오늘날씨", "현재가격", "오늘가격", "실시간교통")):
        return "실시간 또는 최신 정보는 제공된 PDF 한 개로 확인할 수 없습니다."
    personal = any(word in text for word in ("내차", "내차량", "지금차", "현재차"))
    # [프로젝트 추가] 설명서의 리콜 안내와 개별 차량의 현재 리콜 대상 조회를 구별합니다.
    # '리콜' 단어만으로 차단하지 않습니다. 차량 식별·최신 조회가 필요한 명시적 표현에 한정합니다.
    if personal and "리콜" in text and any(word in text for word in ("대상", "해당", "적용여부")):
        return "제공된 PDF만으로 내 차량의 현재 리콜 대상 여부를 조회할 수 없습니다."
    diagnosis = "고장" in text and any(word in text for word in ("인가", "인지", "건가", "맞", "판단", "진단", "났나", "난거"))
    if personal and diagnosis:
        return "사용설명서만으로 개별 차량의 실제 고장 여부를 판단할 수 없습니다."
    return None


def split_question(question):
    """'함께/각각/둘 다'와 '과/와'로 요청한 두세 항목만 나눕니다. 범용 질문 분석기는 아닙니다."""
    # [프로젝트 추가] A04·A05에서 첫 근거만 선택된 문제를 줄이기 위한 작은 규칙입니다.
    # 문장 속 모든 '과/와'를 나누면 '안전벨트 경고등과 경고음' 같은 한 주제를 손상시킬 수 있습니다.
    # 명시적 묶음 요청에만 적용하며 생략된 공통 주어를 자동 복원하지는 않습니다.
    if not any(marker in question for marker in ("함께", "각각", "둘 다", "둘다")):
        return [question]
    parts = re.split(r"(?<=[가-힣])(?:과|와)\s+", question)
    if not 2 <= len(parts) <= 3:
        return [question]
    parts = [re.sub(r"함께|각각|둘\s*다", "", part).strip() for part in parts]
    return parts if all(parts) else [question]


def source_label(source):
    """PDF 쪽수와 인쇄 매뉴얼 쪽수를 구별해 표시합니다. 일괄 +5 변환을 사용하지 않습니다."""
    pages = source["source_pages"]
    page_text = ", ".join(str(page) for page in pages)
    label = f"[{source['citation_id']}] PDF {page_text}쪽"
    manual = source["manual_page_number"]
    if manual is not None:
        label += f" / 매뉴얼{' 시작' if len(pages) > 1 else ''} {manual}쪽"
    return label


class ManualAnswerService:
    """검색 → 확인한 근거 선택 → 발췌·출처·그림 연결을 담당합니다. DB 쓰기는 하지 않습니다."""

    def __init__(self, run_id, search_service=None, method="purpose_specific"):
        """전체 저장 작업 번호를 받고 기존 검색 서비스를 재사용할 준비만 합니다."""
        # [프로젝트 추가] M7 비교에서 Q19가 개선되고 기존 30문항의 기대 순위가 나빠지지 않았습니다.
        # 발췌 답변은 구체 표현 점수 방식을 기본 사용하며 purpose를 지정하면 변경 전과 비교할 수 있습니다.
        # 같은 30문항 결과는 새 질문의 정확도 보장이 아닙니다. 기존 검토 상태·근거 선택 규칙은 유지합니다.
        self.search_service = search_service or DbFullSearchService(run_id, method=method)

    def answer(self, question, top_k=3, progress=None):
        """질문을 받아 발췌 또는 근거 부족·검토 필요 안내를 반환합니다. 후보를 정답으로 단정하지 않습니다."""
        if not isinstance(question, str) or not question.strip():
            raise ValueError("질문을 입력하세요.")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 10:
            raise ValueError("검색 후보 수는 1~10 사이로 입력하세요.")
        question = question.strip()
        reason = outside_pdf_reason(question)
        if reason:
            return self._empty_result(question, "outside_pdf_scope", reason)
        parts = split_question(question)
        answers = []
        for index, part in enumerate(parts, start=1):
            if progress and len(parts) > 1:
                progress(f"질문 항목 {index}/{len(parts)} 근거 검색: {part}")
            result = self.search_service.search(part, top_k=top_k, progress=progress)
            answers.append(self.from_search_result(result))
        if len(parts) == 1:
            return answers[0]
        return self.combine_answers(question, answers)

    @staticmethod
    def combine_answers(question, answers):
        """항목별 확인 근거를 중복 없이 모으고, 근거가 없는 항목은 별도로 안내합니다."""
        # [프로젝트 추가] 각 항목의 필수 각주·원문은 자르지 않고 record_id로만 중복 제거합니다.
        sources, seen = [], set()
        for result in answers:
            for source in result["sources"]:
                if source["record_id"] not in seen:
                    source = deepcopy(source)
                    source["citation_id"] = len(sources) + 1
                    source["label"] = source_label(source)
                    sources.append(source)
                    seen.add(source["record_id"])
        missing = [{"question": row["question"], "status": row["status"], "reason": row.get("reason", "")}
                   for row in answers if not row["sources"]]
        # 그림의 파일명은 다른 페이지에서 중복될 수 있어 PDF 페이지와 내부 키를 함께 사용합니다.
        images, pending_images = {}, {}
        for row in answers:
            for target, field in ((images, "images"), (pending_images, "pending_image_references")):
                for image in row[field]:
                    identity = (image["pdf_page_number"], image["pdf_image_key"])
                    if identity not in target:
                        target[identity] = deepcopy(image)
                    else:
                        for description in image["descriptions"]:
                            if description not in target[identity]["descriptions"]:
                                target[identity]["descriptions"].append(deepcopy(description))
        # 다른 항목에서 확인돼 표시할 수 있는 동일 그림은 보류 목록에서 제외합니다.
        pending_images = [image for key, image in pending_images.items() if key not in images]
        combined = deepcopy(answers[0])
        combined.update(question=question, sources=sources, images=list(images.values()),
                        pending_image_references=pending_images, subquestions=[row["question"] for row in answers],
                        missing_subquestions=missing,
                        review_candidates=[candidate for row in answers for candidate in row["review_candidates"]],
                        matched_chunk_record_ids=[row["matched_chunk_record_id"] for row in answers
                                                  if "matched_chunk_record_id" in row])
        combined.pop("matched_chunk_record_id", None)
        if sources:
            combined["status"] = "partial_evidence" if missing else "evidence_excerpt"
            combined["answer"] = "설명서에서 항목별로 확인한 내용입니다.\n\n" + "\n\n".join(
                row["label"] + " · " + row["title"] + "\n" + row["quote"] for row in sources)
            combined["reason"] = "일부 요청 항목의 확인 근거를 확보하지 못했습니다." if missing else ""
            if missing:
                combined["answer"] += "\n\n확인하지 못한 항목:\n" + "\n".join(
                    f"- {row['question']}: {row['reason']}" for row in missing)
        else:
            combined["status"] = "needs_review" if any(row["status"] == "needs_review" for row in answers) else "insufficient_evidence"
            combined["answer"] = "항목별로 찾았지만 확정 답변에 사용할 근거를 확보하지 못했습니다."
            combined["reason"] = " / ".join(row["reason"] for row in missing)
        combined["limitation"] = "항목별 단어 일치·검토 상태를 확인했으며 질문의 모든 의미 조건 충족을 보장하지 않습니다."
        return combined

    @staticmethod
    def _empty_result(question, status, reason, result=None):
        """답변 근거를 선택하지 못한 경우 출처나 그림을 만들어 붙이지 않습니다."""
        return {"question": question, "status": status, "answer_mode": "pdf_excerpt",
                "answer": NO_EVIDENCE_MESSAGE if status != "needs_review" else
                    "관련 설명서 후보는 찾았지만, 원본 대조가 필요한 자료여서 확정 답변을 보류합니다.",
                "reason": reason, "sources": [], "images": [], "pending_image_references": [],
                "review_candidates": deepcopy(result["candidates"]) if result and status == "needs_review" else [],
                "run_id": result["run_id"] if result else None,
                "semantic_answerability_validated": False, "llm_called": False,
                "db_written": False, "storage_uploaded": False,
                "retrieval_performed": result is not None}

    @classmethod
    def from_search_result(cls, result):
        """검색 결과에서 관련 단어가 있는 확인 자료 한 묶음을 선택합니다. 필수 각주는 함께 보존합니다."""
        terms = question_terms(result["question"])
        eligible, pending = [], []
        for candidate in result["candidates"]:
            context = candidate["context_records"]
            body = re.sub(r"\s+", "", " ".join(row["content"] for row in context).lower())
            if not terms or not any(term in body for term in terms):
                continue
            if (all(row["verification_status"] in REVIEWED_STATUSES for row in context)
                    and not candidate["unreviewed_continuation_record_ids"]):
                eligible.append(candidate)
            else:
                pending.append(candidate)
        if not eligible:
            status = "needs_review" if pending else "insufficient_evidence"
            reason = "검색된 원문 또는 이어지는 주의사항의 검토가 필요합니다." if pending else (
                "현재 상위 후보에서 질문 단어와 일치하는 확인 자료를 선택하지 못했습니다. "
                "일상 표현이나 복합 질문에서는 관련 자료가 있어도 보류할 수 있습니다.")
            review_result = {**result, "candidates": pending} if pending else result
            return cls._empty_result(result["question"], status, reason, review_result)

        # [프로젝트 추가] 여러 후보를 무조건 이어 붙이지 않고 첫 관련 근거와 필수 문맥만 사용합니다.
        # 이 선택 규칙은 임시 보수적 기준입니다. M6의 범위 밖·복합 질문 평가로 개선해야 합니다.
        chosen = eligible[0]
        sources = []
        for number, row in enumerate(chosen["context_records"], start=1):
            source = {"citation_id": number, "record_id": row["record_id"], "title": row["title"],
                      "source_pages": list(row["source_pages"]), "manual_page_number": row["manual_page_number"],
                      "verification_status": row["verification_status"], "quote": row["content"],
                      "quote_source": "stored_parent_content", "raw_text": row["raw_text"]}
            source["label"] = source_label(source)
            sources.append(source)
        images, pending_images = [], []
        source_ids = {source["record_id"] for source in sources}
        for image in chosen["image_parts"]:
            # [프로젝트 추가] 파일 업로드와 문맥 연결 검토를 각각 확인합니다.
            # 그림 설명이 없거나 페이지 단위 미검토 참조이면 답변 그림으로 확정하지 않습니다.
            descriptions = [row for row in image["descriptions"] if row["parent_record_id"] in source_ids
                            and row["description"] and row["linkage_status"] in {"sample_linked", "visually_verified"}]
            if image["public_url"] and descriptions:
                displayed = deepcopy(image)
                displayed["descriptions"] = descriptions
                images.append(displayed)
            else:
                pending_images.append(deepcopy(image))
        answer = "설명서에서 확인한 관련 내용입니다.\n\n" + "\n\n".join(
            source["label"] + " · " + source["title"] + "\n" + source["quote"] for source in sources)
        return {"question": result["question"], "status": "evidence_excerpt", "answer_mode": "pdf_excerpt",
                "answer": answer, "sources": sources, "images": images,
                "pending_image_references": pending_images, "review_candidates": [],
                "run_id": result["run_id"], "search_method": result["search_method"],
                "matched_chunk_record_id": chosen["matched_chunk_record_id"],
                "semantic_answerability_validated": False, "llm_called": False,
                "db_written": False, "storage_uploaded": False, "retrieval_performed": True,
                "limitation": "검색용 글의 발췌이며 질문의 모든 조건을 만족하는지 의미 검증하거나 LLM으로 생성한 답변은 아닙니다."}
