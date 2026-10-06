"""Sonata 개인 화면과 공통 화면이 함께 호출하는 챗봇 실행 흐름입니다.

화면은 이 모듈의 chunks를 표시하고 최종 answer/sources/images/download_html을 렌더링합니다.
Agent, 검색 도구, 다운로드 도구 및 검색 알고리즘은 CarManual이 담당합니다.
"""
from dataclasses import dataclass, field
from inspect import signature
from typing import Iterator

from car_search_rag.car_search.car_manual import CarManual


def _is_conversation_download_request(question):
    """대화 기록과 다운로드 의도가 함께 있는 질문을 판별한다."""
    normalized = " ".join((question or "").casefold().split())
    history_terms = (
        "대화", "채팅", "기록", "내역", "히스토리", "history", "conversation", "chat"
    )
    download_terms = ("다운로드", "내려받", "내보내", "download", "export")
    return (
        any(term in normalized for term in history_terms)
        and any(term in normalized for term in download_terms)
    )


def _display_metadata(search_results, question=None, image_selector=None, answer=None):
    """검색 row에서 출처와 화면에 표시할 이미지를 분리해 만든다.

    출처는 chunk 순서를 유지하며 최대 5개까지 모은다. image selector가 있으면
    질문 관련도로 이미지를 고르고, 없으면 검색 row의 URL에서 최대 3개를 가져온다.

    Returns:
        `(출처 목록, 이미지 metadata 목록)` 형태의 tuple.
    """
    # 검색 row 순서대로 중복 없는 출처 목록을 만든다.
    # region [Python 설명] list, set, tuple key와 dict.get()
    # `sources`는 출처 dict를 담는 list이고 `seen_sources`는 중복 검사 set이다.
    # row의 key는 camelCase 또는 snake_case일 수 있어 중첩 `.get()`으로 둘 다 확인한다.
    # `(page_no, chunk_no)` tuple은 출처 한 건을 구별하는 set key로 사용한다.
    # `search_results or ()`는 결과가 None 또는 비어 있으면 빈 tuple로 순회한다.
    # endregion
    sources = []
    seen_sources = set()

    for result in search_results or ():
        page_no = result.get("carManualChunkPageNo", result.get("car_manual_chunk_page_no"))
        chunk_no = result.get("carManualChunkNo", result.get("car_manual_chunk_no"))
        source_key = (page_no, chunk_no)
        if page_no is not None and chunk_no is not None and source_key not in seen_sources:
            sources.append({"page_no": page_no, "chunk_no": chunk_no})
            seen_sources.add(source_key)

        if len(sources) >= 5:
            break

    # image selector가 있으면 질문을 전달해 관련 이미지를 선택한다.
    # region [Python 설명] callback 함수와 truthy 검사
    # `image_selector`는 호출자가 함수로 전달한 callback이다.
    # 질문과 검색 row를 넘겨 실행하고 이미지 표시용 metadata 목록을 받는다.
    # `question and image_selector`는 두 값이 모두 있을 때만 이 경로를 선택한다.
    # endregion
    if question and image_selector:
        images = image_selector(question, search_results, limit=3, answer=answer)
    else:
        # selector가 없으면 검색 row에 붙은 image URL에서 순서대로 모은다.
        images = []
        seen_images = set()

        # URL이 문자열이고 유효하며 이미 쓰이지 않았는지 확인한다.
        # region [Python 설명] isinstance()와 set membership
        # `isinstance(image_url, str)`는 URL 값이 문자열인지 확인한다.
        # `.strip()`은 앞뒤 공백을 제거하고, set membership은 이미 본 URL을 건너뛴다.
        # endregion
        for result in search_results or ():
            image_url = result.get("carManualImageUrl", result.get("car_manual_image_url"))
            page_no = result.get("carManualChunkPageNo", result.get("car_manual_chunk_page_no"))
            if isinstance(image_url, str) and image_url.strip() and image_url.strip() not in seen_images:
                images.append({"url": image_url.strip(), "page_no": page_no})
                seen_images.add(image_url.strip())

            if len(images) >= 3:
                break

    # 출처와 이미지 목록을 tuple로 반환한다.
    # region [Python 설명] 여러 값 반환
    # `return a, b`는 `(a, b)` tuple을 반환한다.
    # 호출 측은 `sources, images = ...`처럼 두 변수로 나누어 받을 수 있다.
    # endregion
    return sources[:5], images


@dataclass
class ChatReply:
    """스트림을 모두 소비한 후 최종 답변과 표시 자료를 읽습니다."""
    chunks: Iterator[str] = field(default_factory=lambda: iter(()))
    answer: str = ''
    sources: list = field(default_factory=list)
    images: list = field(default_factory=list)
    download_html: str | None = None
    error: Exception | None = None


def _pin_vehicle(service, vehicle):
    """Agent 도구가 선택 카드와 다른 차량의 DB를 조회하지 못하게 확인합니다."""
    original = service.ask_manual_with_sources
    call_signature = signature(original)

    def selected_vehicle_search(*args, **kwargs):
        bound = call_signature.bind(*args, **kwargs)
        requested = tuple(bound.arguments[name] for name in
                          ('car_brand_eng_nm', 'car_eng_nm', 'car_model_yr'))
        if requested != vehicle:
            raise ValueError('선택된 차량의 설명서만 검색할 수 있습니다.')
        return original(*args, **kwargs)

    service.ask_manual_with_sources = selected_vehicle_search


def prepare_reply(question, history, vehicle=('hyundai', 'sonata', 2026), *, manual_factory=CarManual):
    """개인 앱의 대화 6개·검색 10개·다운로드 분기를 한 곳에서 실행합니다."""
    reply = ChatReply()
    # 호출자가 현재 질문을 추가하기 전의 이력을 전달합니다.
    history = list(history)

    def stream():
        # 다운로드 상태가 다른 사용자에게 섞이지 않도록 요청별 Agent를 만듭니다.
        manual = manual_factory()
        try:
            _pin_vehicle(manual.service, vehicle)
            if _is_conversation_download_request(question):
                reply.download_html = manual.prepare_history_html(
                    history + [{'role': 'user', 'content': question}])
                reply.answer = ('대화 기록 HTML 다운로드를 준비했습니다.' if reply.download_html
                                else '대화 기록 HTML을 만들지 못했습니다. 다시 시도해 주세요.')
                return

            result = manual.ask_with_sources_stream(
                car_brand_eng_nm=vehicle[0], car_eng_nm=vehicle[1], car_model_yr=vehicle[2],
                question=question, limit=10, conversation_history=history[-6:],
            )
            tokens = []
            for token in result.chunks:
                tokens.append(token)
                yield token
            reply.answer = result.answer or ''.join(tokens)
            reply.error = result.error
            # Agent가 다운로드 도구를 선택했을 때의 산출물도 UI에 전달합니다.
            reply.download_html = manual.download_html
            reply.sources, reply.images = _display_metadata(
                result.search_results, question=question, answer=reply.answer,
                image_selector=manual.service.select_relevant_images,
            )
        except Exception as error:
            reply.error = error
            if not reply.answer:
                reply.answer = '답변을 생성하지 못했습니다. 다시 시도해 주세요.'
        finally:
            manual.service.sql_session.database_manager.close()

    reply.chunks = stream()
    return reply
