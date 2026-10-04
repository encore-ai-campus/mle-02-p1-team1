"""Lightweight image selection using extracted PDF image descriptions.

This ranking only chooses which page images to display after existing pgvector
chunk retrieval has returned; it does not modify chunk scores or rank.
"""
import difflib
import re
import unicodedata

_TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9]+")
_PARTICLES = ("으로부터", "에게서", "에서는", "으로는", "으로", "에서", "에게", "까지", "부터", "보다", "처럼", "이랑", "하고", "은", "는", "이", "가", "을", "를", "과", "와", "의", "도", "에", "로", "만")
_STOP_WORDS = {"어떤", "상태", "때", "무엇", "어떻게", "하나요", "알려", "알려줘", "주세요", "해야", "확인", "방법", "기준", "순서", "뜻", "각각", "어느", "수준", "정도", "이하", "이상"}


def _tokens(text):
    normalized = unicodedata.normalize("NFKC", text or "").lower()
    terms = []
    for token in _TOKEN_RE.findall(normalized):
        for suffix in _PARTICLES:
            if token.endswith(suffix) and len(token) - len(suffix) >= 2:
                token = token[:-len(suffix)]
                break
        if len(token) > 1 and token not in _STOP_WORDS:
            terms.append(token)
    return terms


def image_description_relevance(question, image_desc):
    """Return a bounded lexical relevance score for a question and image title."""
    query_terms, description_terms = _tokens(question), _tokens(image_desc)
    if not query_terms or not description_terms:
        return 0.0
    matches = []
    for query_term in query_terms:
        best = 0.0
        for description_term in description_terms:
            if query_term == description_term:
                similarity = 1.0
            elif query_term in description_term or description_term in query_term:
                similarity = min(len(query_term), len(description_term)) / max(len(query_term), len(description_term))
            else:
                similarity = difflib.SequenceMatcher(None, query_term, description_term).ratio()
                if similarity < 0.72:
                    similarity = 0.0
            best = max(best, similarity)
        matches.append(best)
    return sum(matches) / len(matches)


def select_relevant_images(question, search_results, image_candidates, limit=3):
    """Rank images on already-retrieved pages without changing chunk ranking."""
    page_rank = {}
    for rank, result in enumerate(search_results or (), start=1):
        page = result.get("carManualChunkPageNo", result.get("car_manual_chunk_page_no"))
        if page is not None:
            page_rank.setdefault(int(page), rank)

    ranked = []
    for image in image_candidates or ():
        url = image.get("carManualImageUrl", image.get("car_manual_image_url"))
        page = image.get("carManualImagePageNo", image.get("car_manual_image_page_no"))
        description = image.get("carManualImageDesc", image.get("car_manual_image_desc"))
        if not url or page is None or not description:
            continue
        score = image_description_relevance(question, description)
        if score > 0:
            ranked.append((score, page_rank.get(int(page), 10**6), int(page), image))

    ranked.sort(key=lambda item: (-item[0], item[1], int(item[3].get("carManualImageNo", item[3].get("car_manual_image_no", 0)))))
    selected, seen_pages = [], set()
    for score, _, page, image in ranked:
        if page in seen_pages:
            continue
        selected.append({
            "url": image.get("carManualImageUrl", image.get("car_manual_image_url")),
            "page_no": page,
            "description": image.get("carManualImageDesc", image.get("car_manual_image_desc")),
            "relevance_score": round(score, 4),
            "selection_method": "image_desc lexical match",
        })
        seen_pages.add(page)
        if len(selected) >= limit:
            break
    return selected
