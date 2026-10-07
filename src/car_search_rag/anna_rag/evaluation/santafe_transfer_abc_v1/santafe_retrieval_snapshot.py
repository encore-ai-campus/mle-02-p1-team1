"""질문 목적에 맞는 PDF 근거를 찾고 부모 원문·그림 참조를 연결합니다."""

# [수업 개념] 임베딩 검색은 7_RAG시스템, TF-IDF는 5_자연어처리/4_TF_IDF에서 다뤘습니다.
# [프로젝트 추가] 부모·자식 검색, 글자 색인, 안내도 항목 검색, 목적 규칙, 연결 근거 묶음을 적용합니다.

import json
import re
from collections import defaultdict
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


def make_character_index(texts):
    """같은 글자 2~4개 설정으로 TF-IDF 색인과 행렬을 만듭니다. 모델·DB 호출은 없습니다."""
    # [프로젝트 추가] 부모·자식·안내도에서 반복하던 설정을 한곳에 모았습니다. 실험 설정은 유지합니다.
    index = TfidfVectorizer(analyzer="char", ngram_range=(2, 4), dtype=np.float32)
    return index, index.fit_transform(texts)


def _make_search_functions(parents, chunks, vectors, model, token_counter):
    """같은 PDF의 색인을 한 번 준비하고 이를 사용하는 검색 함수들을 돌려줍니다."""
    full_parent_records = parents
    full_search_chunks = chunks
    parent_lookup = {p["metadata"]["record_id"]: p for p in parents}
    chunk_vectors = vectors
    embedding_model = model
    token_count, token_budget = token_counter.count, token_counter.budget
    # [프로젝트 추가] 같은 부모의 자식 중 최고 점수를 부모 후보 점수로 사용하고 전체 문맥은 부모에서 읽습니다.
    groups = defaultdict(list)
    for index, chunk in enumerate(chunks):
        groups[chunk["metadata"]["parent_record_id"]].append(index)

    # 첫 비교 방식도 남겨 두어 노트북과 같은 조건으로 결과를 비교할 수 있습니다.
    parent_ids = list(parent_lookup)
    parent_positions = {parent_id: index for index, parent_id in enumerate(parent_ids)}

    def normalize_keyword(text):
        """한글·영문·숫자와 표 조작 기호를 남겨 띄어쓰기 차이를 줄입니다."""
        return "".join(re.findall(r"[가-힣A-Za-z0-9+\-]+", text)).lower()

    lexical_texts = []
    for parent_id in parent_ids:
        parent = parent_lookup[parent_id]
        items = parent["metadata"].get("navigation_items")
        # 안내도 참조 쪽수를 부품 이름으로 오인하지 않도록 이름만 색인합니다.
        text = "\n".join(item["name"] for item in items) if items else parent["content"]
        lexical_texts.append(normalize_keyword(text))
    # [프로젝트 추가] TF-IDF 단위를 단어 대신 글자 2~4개로 정해 띄어쓰기 차이에 대응합니다.
    lexical_index, lexical_matrix = make_character_index(lexical_texts)
    # [프로젝트 추가] 의미 점수 50%와 글자 점수 50%를 합치는 고정 실험 기준입니다.
    # 이 결합 점수는 정답 확률이나 별도 재순위 모델의 출력이 아닙니다.
    semantic_weight = 0.5

    def rank_candidates(question, question_vector, method="semantic", top_k=3):
        """가장 잘 맞는 자식 조각의 점수로 부모 원문 후보를 정렬합니다."""
        if method not in {"semantic", "hybrid"}:
            raise ValueError("검색 방식은 semantic 또는 hybrid입니다.")
        if not 1 <= top_k <= len(parent_ids):
            raise ValueError("검색 결과 수를 확인하세요.")
        chunk_scores = chunk_vectors @ question_vector
        keyword_scores = np.zeros(len(parent_ids), dtype=np.float32)
        if method == "hybrid":
            query_terms = lexical_index.transform([normalize_keyword(question)])
            keyword_scores = (lexical_matrix @ query_terms.T).toarray().ravel()
        hits = []
        for parent_id, indices in groups.items():
            best_index = max(indices, key=lambda index: float(chunk_scores[index]))
            semantic_score = float(chunk_scores[best_index])
            keyword_score = float(keyword_scores[parent_positions[parent_id]])
            score = semantic_score if method == "semantic" else (
                semantic_weight * semantic_score + (1 - semantic_weight) * keyword_score
            )
            hits.append({
                "score": score, "semantic_score": semantic_score, "keyword_score": keyword_score,
                "matched_chunk": full_search_chunks[best_index],
                "parent_record": parent_lookup[parent_id],
            })
        hits.sort(key=lambda hit: hit["score"], reverse=True)
        return hits[:top_k]

    def full_manual_search(question, method="hybrid", top_k=3):
        """질문 길이를 확인한 뒤 전체 청크에서 출처가 담긴 검색 후보를 찾습니다."""
        if not question.strip() or token_count(question) > token_budget:
            raise ValueError("질문을 비우지 말고 입력 한도 안에서 짧게 작성하세요.")
        vector = embedding_model.encode(
            question, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False
        )
        return rank_candidates(question, vector, method=method, top_k=top_k)

    # [프로젝트 추가] 각주·주의사항의 연결 ID를 따라 부모 원문들을 함께 읽습니다.
    # 서로 연결된 자료도 seen으로 이미 읽은 ID를 기억해 무한 반복을 막습니다.
    def read_context(parent_id):
        """부모 원문과 필수 연결 기록을 읽되, 아직 검토 중인 자료는 상태를 함께 남깁니다."""
        pending, seen, context = [parent_id], set(), []
        while pending:
            record_id = pending.pop(0)
            if record_id in seen:
                continue
            seen.add(record_id)
            record = parent_lookup[record_id]
            context.append(record)
            pending.extend(record["metadata"].get("required_context_record_ids", []))
        return context


    # 작은 청크와 안내도 번호 항목을 각각 글자 색인으로 만듭니다.
    def normalize_query_text(text):
        """공백 차이를 줄이고 한글·영문·숫자·조작 기호를 남깁니다."""
        return "".join(re.findall(r"[가-힣A-Za-z0-9ℓ+\-]+", text)).lower()
    assert normalize_query_text("ℓ") == "ℓ"

    chunk_keyword_index, chunk_keyword_matrix = make_character_index(
        [normalize_query_text(c["content"]) for c in full_search_chunks]
    )

    # [프로젝트 추가] 번호별 부품 이름을 따로 색인합니다. 참조 쪽수 대신 이름·제목을 비교합니다.
    navigation_rows = []
    for parent_id, parent in parent_lookup.items():
        for item in parent["metadata"].get("navigation_items", []):
            navigation_rows.append({
                "parent_id": parent_id, "number": item["number"], "name": item["name"],
                "index_text": normalize_query_text(parent["metadata"]["title"] + " " + item["name"]),
            })
    navigation_keyword_index, navigation_keyword_matrix = make_character_index(
        [row["index_text"] for row in navigation_rows]
    )
    indices_by_parent = defaultdict(list)
    for index, chunk in enumerate(full_search_chunks):
        indices_by_parent[chunk["metadata"]["parent_record_id"]].append(index)

    # [프로젝트 추가] M7에서 비교한 원문 표현 색인입니다. 현재 purpose_specific 방식에서 사용합니다.
    # purpose 방식은 보너스를 사용하지 않아 이전 실험 조건도 비교할 수 있습니다.
    from .specific_terms import SpecificTermMatcher
    specific_matcher = SpecificTermMatcher(full_parent_records)

    navigation_names = {
        normalize_query_text(item["name"])
        for parent in parent_lookup.values()
        for item in parent["metadata"].get("navigation_items", [])
    }
    # 드라이브 모드 값도 정답 질문에서 가져오지 않고 확인된 표의 열에서 읽습니다.
    table_mode_values = {
        normalize_query_text(row["drive_mode"])
        for parent in parent_lookup.values()
        for row in parent["metadata"].get("table_rows", [])
        if "drive_mode" in row
    }

    def has_any(text, phrases):
        """질문에 정해진 목적 표현이 있는지 확인합니다."""
        normalized = [normalize_query_text(phrase) for phrase in phrases]
        # 빈 표현은 모든 질문에 포함되므로 반드시 제외합니다.
        return any(phrase and phrase in text for phrase in normalized)

    # [프로젝트 추가] 안내도·표·설명문을 선택하는 직접 작성한 표현 규칙입니다.
    # 별도 분류 모델이나 LLM 호출은 없으며 새로운 표현·혼합 질문에서 범위를 잘못 좁힐 수 있습니다.
    def classify_question(question):
        """질문 표현과 자료 구조를 보고 필요한 자료 유형과 판단 이유를 돌려줍니다."""
        from .question_intent import evidence_intent
        text = normalize_query_text(question)
        shared_intent = evidence_intent(question)
        # [프로젝트 추가] 그림 요청은 안내도뿐 아니라 설명 그림도 포함합니다.
        # '그림' 하나만으로 안내도 5개를 앞세우면 일반 부품 설명 그림을 놓치므로,
        # 명시적인 안내도/번호 표현 또는 실제 안내도 부품 이름으로만 범위를 좁힙니다.
        explicit_navigation = shared_intent == "location" and has_any(text, [
            "안내도", "도안", "몇 번", "어느 항목", "번호로 표시", "번호가 표시"])
        location_words = has_any(text, ["위치", "어디", "자리"])
        operation_words = has_any(text, [
            "사용", "조작", "작동", "방법", "당기", "누르", "눌", "기능", "변속",
            "문제", "주의", "제한", "왜", "이유", "안 되는", "하면 안",
            "할 수 없", "변경", "상황", "언제", "어떻게", "밀어",
        ])
        known_component = any(name and name in text for name in navigation_names)
        quantity_words = has_any(text, [
            "용량", "규격", "추천 사양", "점도", "SAE", "각주", "리터", "ℓ",
            "표를", "표의", "표에", "온도 눈금",
        ])
        mode_function = (
            has_any(text, ["모드"]) and any(mode in text for mode in table_mode_values)
            and not explicit_navigation
        )
        intents, reasons = [], []
        if shared_intent not in {"procedure", "symptom"} and (explicit_navigation or (location_words and known_component)):
            intents.append("navigation")
            reasons.append("안내도·번호 표현 또는 자료에 있는 부품의 위치 질문")
        if quantity_words or mode_function:
            intents.append("table")
            reasons.append("용량·규격·각주 표현 또는 표의 모드 기능 질문")
        # 명시적으로 위치만 묻는 경우 일반적인 '버튼' 등의 표현은 조작으로 판단하지 않습니다.
        if shared_intent in {"procedure", "symptom"} or (operation_words and not explicit_navigation):
            if not mode_function or has_any(text, ["제한", "주의", "왜", "안 되는"]):
                intents.append("explanation")
                reasons.append("사용·조작·주의·제한 질문")
        if not intents:
            intents, reasons = ["general"], ["유형이 명확하지 않아 전체 자료 검색"]
        return {
            "intents": intents, "reasons": reasons,
            "inside_vehicle_only": "navigation" in intents and has_any(text, ["차량 내부", "내부 안내도"]),
        }

    # [프로젝트 추가] 자료 유형으로 후보를 고르고 평가의 기대 ID는 사용하지 않습니다.
    # 표 유형으로 확인하지 못한 자동 초안은 표 질문에서 제외될 수 있습니다.
    def parent_matches_intent(parent, decision):
        """기록된 자료 유형으로 검색 범위를 고릅니다. 원문 ID나 평가 정답은 사용하지 않습니다."""
        meta = parent["metadata"]
        kind = meta["content_type"]
        for intent in decision["intents"]:
            if intent == "general":
                return True
            if intent == "navigation" and kind == "vehicle_overview_navigation":
                if decision["inside_vehicle_only"] and "차량 내부" not in meta["title"]:
                    continue
                return True
            if intent == "table" and (
                kind in {"structured_table", "table_with_images"} or bool(meta.get("footnotes"))
            ):
                return True
            if intent == "explanation" and kind in {"instruction_text", "figure_with_text"}:
                return True
        return False


    def purpose_rank(question, question_vector, top_k=3, use_routing=True, use_specific_terms=False):
        """작은 조각의 결합 점수로 부모를 정렬하고 질문 목적에 맞는 범위를 선택합니다."""
        if not 1 <= top_k <= len(parent_lookup):
            raise ValueError("검색 결과 수를 확인하세요.")
        semantic_scores = chunk_vectors @ question_vector
        query_terms = chunk_keyword_index.transform([normalize_query_text(question)])
        keyword_scores = (chunk_keyword_matrix @ query_terms.T).toarray().ravel()
        # [프로젝트 추가] 작은 청크의 의미·글자 점수를 같은 비중으로 결합하며 질문별로 비중을 맞추지 않습니다.
        combined_scores = 0.5 * semantic_scores + 0.5 * keyword_scores

        # 안내도 긴 목록 전체 대신 각각의 부품 이름을 비교합니다.
        row_terms = navigation_keyword_index.transform([normalize_query_text(question)])
        row_scores = (navigation_keyword_matrix @ row_terms.T).toarray().ravel()
        best_navigation_rows = {}
        for row, score in zip(navigation_rows, row_scores):
            parent_id = row["parent_id"]
            if parent_id not in best_navigation_rows or score > best_navigation_rows[parent_id]["score"]:
                best_navigation_rows[parent_id] = {"score": float(score), "row": row}

        all_hits = []
        specific = specific_matcher.bonuses(question) if use_specific_terms else None
        for parent_id, indices in indices_by_parent.items():
            best_index = max(indices, key=lambda index: float(combined_scores[index]))
            score = float(combined_scores[best_index])
            matched_row = None
            if parent_id in best_navigation_rows:
                # 번호 항목의 이름 점수와 해당 부모의 최고 의미 점수를 같은 비중으로 씁니다.
                best_semantic_index = max(indices, key=lambda index: float(semantic_scores[index]))
                navigation_score = 0.5 * float(semantic_scores[best_semantic_index]) + (
                    0.5 * best_navigation_rows[parent_id]["score"]
                )
                if navigation_score > score:
                    score = navigation_score
                    best_index = best_semantic_index
                    matched_row = best_navigation_rows[parent_id]["row"]
            # [프로젝트 추가] 같은 기존 점수에 구체 표현의 포함 점수만 더합니다.
            # 정답 출처·페이지 번호·검토 완료 여부는 순위 계산에 넣지 않습니다.
            term_match = specific["by_record_id"][parent_id] if specific else {"bonus": 0.0, "matched_terms": []}
            score += term_match["bonus"]
            all_hits.append({
                "score": score, "matched_chunk": full_search_chunks[best_index],
                "parent_record": parent_lookup[parent_id], "matched_navigation_row": matched_row,
                "specific_bonus": term_match["bonus"], "specific_terms": term_match["matched_terms"],
            })
        all_hits.sort(key=lambda hit: hit["score"], reverse=True)

        decision = classify_question(question) if use_routing else {
            "intents": ["general"], "reasons": ["유형 선택 없이 전체 검색"],
            "inside_vehicle_only": False,
        }
        # [프로젝트 추가] 유형 후보가 부족하면 전체 후보로 보충하고 used_fallback 표시를 남깁니다.
        # 자료 밖 질문에도 후보가 나올 수 있어 이 기능만으로 답변 가능 여부를 판정하지 않습니다.
        preferred = [hit for hit in all_hits if parent_matches_intent(hit["parent_record"], decision)]
        used_fallback = not preferred
        if not preferred:
            preferred = all_hits
        selected = preferred[:top_k]
        if len(selected) < top_k:
            seen = {hit["parent_record"]["metadata"]["record_id"] for hit in selected}
            selected.extend(hit for hit in all_hits if hit["parent_record"]["metadata"]["record_id"] not in seen)
            selected = selected[:top_k]
            used_fallback = True
        for hit in selected:
            hit["routing"] = decision
            hit["preferred_candidate_count"] = len(preferred)
            hit["used_fallback"] = used_fallback
            hit["verification_status"] = hit["parent_record"]["metadata"]["verification_status"]
        return selected

    def purpose_search(question, top_k=3):
        """질문을 벡터로 바꾸고 목적에 따른 검색 후보와 선택 이유를 가져옵니다."""
        if not question.strip() or token_count(question) > token_budget:
            raise ValueError("짧고 비어 있지 않은 질문을 입력하세요.")
        vector = embedding_model.encode(
            question, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False
        )
        return purpose_rank(question, vector, top_k=top_k)

    # [프로젝트 추가] 원문·필수 연결·그림 참조·미검토 상태를 함께 반환합니다. 답변 생성은 이후 단계입니다.
    def build_evidence_package(hit):
        """검색 후보의 부모·각주·주의사항·그림 참조와 검토 상태를 함께 묶습니다."""
        parent_id = hit["parent_record"]["metadata"]["record_id"]
        context = read_context(parent_id)
        images, seen_images = [], set()
        for record in context:
            for part in record["image_parts"]:
                identity = (
                    part["pdf_page_number"],
                    json.dumps(part.get("pdf_image_key", part.get("name")), ensure_ascii=False),
                )
                if identity not in seen_images:
                    seen_images.add(identity)
                    images.append(part)
        pending_ids = [
            record["metadata"]["record_id"] for record in context
            if record["metadata"]["verification_status"] == "auto_draft_needs_review"
        ]
        continuation_ids = [
            record_id for record in context
            for record_id in record["metadata"].get("unreviewed_continuation_record_ids", [])
        ]
        return {
            "matched_chunk": hit["matched_chunk"], "context_records": context, "image_parts": images,
            "routing": hit["routing"], "pending_review_record_ids": pending_ids,
            "unreviewed_continuation_record_ids": list(dict.fromkeys(continuation_ids)),
            "answer_generation_status": "not_implemented",
        }

    return {
        "search": purpose_search, "rank": purpose_rank,
        "baseline_rank": rank_candidates, "classify": classify_question,
        "read_context": read_context, "evidence": build_evidence_package,
    }


class SearchEngine:
    """미리 만든 청크 벡터를 재사용해 여러 질문의 근거를 검색합니다."""

    def __init__(self, parents, chunks, vectors, model, token_counter):
        """노트북 12번과 같은 색인과 검색 함수를 준비합니다."""
        self.parents = parents
        self.chunks = chunks
        self.model = model
        self.token_counter = token_counter
        self._functions = _make_search_functions(parents, chunks, vectors, model, token_counter)

    def search(self, question, top_k=3):
        """질문 목적을 판단하고 관련 원문 후보를 돌려줍니다. 답변 생성은 하지 않습니다."""
        return self._functions["search"](question, top_k=top_k)

    def rank(self, question, vector, top_k=3, use_routing=True, use_specific_terms=False):
        """이미 임베딩한 질문으로 검색합니다. 여러 방식 비교 때 모델 호출을 줄입니다."""
        return self._functions["rank"](question, vector, top_k=top_k, use_routing=use_routing,
                                       use_specific_terms=use_specific_terms)

    def baseline_rank(self, question, vector, top_k=3):
        """기존 부모 전체 글자 색인 방식으로 같은 질문 벡터를 비교합니다."""
        return self._functions["baseline_rank"](question, vector, method="hybrid", top_k=top_k)

    def evidence(self, hit):
        """한 후보의 원문·필수 연결 자료·그림 참조·검토 상태를 묶어 돌려줍니다."""
        return self._functions["evidence"](hit)
