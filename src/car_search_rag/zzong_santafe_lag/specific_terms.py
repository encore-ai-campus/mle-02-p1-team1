"""질문의 구체적인 표현이 실제 원문에 있을 때만 작은 추가 점수를 계산합니다."""

# [프로젝트 추가] M7의 한 가지 변경 조건입니다. 모델·청킹·기대 출처는 바꾸지 않습니다.
# 자료 전체에서 드물게 나오는 질문 단어·연속 두 단어를 사용하며 특정 질문·페이지를 고정하지 않습니다.
# 정확한 표현이 없는 바꿔 말한 질문에는 도움이 없을 수 있고 답변 가능성을 판정하지 않습니다.

import math
import re


SPECIFIC_BONUS_WEIGHT = 0.15


def compact_text(text):
    """띄어쓰기 차이를 줄여 한글·영문·숫자 표현을 비교합니다."""
    return "".join(re.findall(r"[가-힣A-Za-z0-9]+", text)).lower()


def query_expressions(question):
    """간단한 조사와 질문 표현을 제외하고 단어·이웃한 두 단어 표현을 만듭니다."""
    ignored = {"어디", "어떻게", "언제", "얼마나", "무엇", "하나요", "되나요", "인가요",
               "알려줘", "알려주세요", "보여줘", "찾아줘", "무엇인가요", "관련", "있나요"}
    words = []
    for word in re.findall(r"[가-힣A-Za-z0-9]+", question.lower()):
        for ending in ("에서는", "에서", "으로", "까지", "부터", "에는", "은", "는", "을", "를", "의", "이", "가", "과", "와", "에"):
            if word.endswith(ending) and len(word) - len(ending) >= 2:
                word = word[:-len(ending)]
                break
        words.append(word if len(word) >= 2 and word not in ignored else None)
    expressions = {word for word in words if word}
    # 제거한 질문 표현을 건너뛰어 원래 이웃하지 않은 단어를 합치지 않습니다.
    expressions.update(left + right for left, right in zip(words, words[1:]) if left and right)
    return expressions


class SpecificTermMatcher:
    """원문에서 드문 질문 표현의 포함 여부로 0~0.15의 추가 점수를 계산합니다."""

    def __init__(self, parents):
        """검색 가능한 원문만 색인합니다. 검토 상태나 정답 ID는 점수에 사용하지 않습니다."""
        self.documents = {p["metadata"]["record_id"]: compact_text(p["content"]) for p in parents}
        # [프로젝트 추가] 흔한 표현은 제외합니다. 기준은 전체 원문의 2%, 최소 두 원문입니다.
        self.max_document_frequency = max(2, math.ceil(len(self.documents) * 0.02))

    def bonuses(self, question):
        """질문의 구체 표현과 원문별 추가 점수·일치 표현을 반환합니다."""
        features = []
        for term in query_expressions(question):
            frequency = sum(term in body for body in self.documents.values())
            if 1 <= frequency <= self.max_document_frequency:
                features.append({"term": term, "document_frequency": frequency,
                                 "weight": math.log((len(self.documents) + 1) / (frequency + 1))})
        # '차단클립'과 그 안의 '차단', '클립'을 중복으로 더해 점수가 부풀지 않게 합니다.
        features = [item for item in features if not any(
            item["term"] != other["term"] and item["term"] in other["term"] for other in features)]
        features.sort(key=lambda item: (item["document_frequency"], -len(item["term"]), item["term"]))
        total_weight = sum(item["weight"] for item in features)
        results = {}
        for record_id, body in self.documents.items():
            matched = [item for item in features if item["term"] in body]
            coverage = sum(item["weight"] for item in matched) / total_weight if total_weight else 0.0
            results[record_id] = {"bonus": SPECIFIC_BONUS_WEIGHT * coverage,
                                  "matched_terms": [item["term"] for item in matched]}
        return {"features": features, "by_record_id": results, "bonus_weight": SPECIFIC_BONUS_WEIGHT}
