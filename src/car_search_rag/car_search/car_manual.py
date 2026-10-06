import logging
from dataclasses import dataclass
from html import escape
from pathlib import Path
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.tools import ToolRuntime
from langchain_core.tools import tool

from car_search_rag.common.sql_session import SqlSession
from car_search_rag.car_search.car_manual_search_service import CarManualSearchService

logger = logging.getLogger("CarManual")


# 최종 답변과 검색 결과를 함께 전달할 데이터 구조다.
# region [Python 설명] dataclass decorator와 type hint
# `@dataclass`는 클래스의 필드를 바탕으로 초기화 메서드 등을 자동으로 만든다.
# `frozen=True`인 dataclass는 생성한 뒤 필드 값을 다시 대입할 수 없다.
# `answer: str`, `search_results: tuple`은 각 필드에 기대하는 값의 종류를 표시한다.
# `Exception | None`은 Exception 객체 또는 None을 뜻하는 Python 타입 표기다.
# endregion
@dataclass(frozen=True)
class CarManualAnswer:
    """최종 답변과 해당 호출에서 찾은 검색 결과를 함께 전달한다."""

    answer: str
    search_results: tuple


# Streaming 중간 결과를 보관하는 데이터 구조다.
# region [Python 설명] dataclass 기본값과 mutable 객체
# 기본값은 새 인스턴스를 만들 때 해당 필드를 초기화하는 값이다.
# 여기서 `()`는 공유 상태를 바꾸지 않는 빈 tuple이고, `""`는 빈 문자열이다.
# `chunks: object = None`처럼 타입 표기와 기본값을 함께 둘 수 있다.
# endregion
@dataclass
class CarManualAnswerStream:
    """Streaming 답변 조각, 최종 답변, 검색 결과와 오류를 보관한다."""

    chunks: object = None
    answer: str = ""
    search_results: tuple = ()
    streamed_answer: str = ""
    error: Exception | None = None


class CarManual:

    service: CarManualSearchService                    # 차량 매뉴얼 검색/RAG 서비스
    model: object                                      # Agent에서 사용하는 LLM
    agent: object                                      # Tool 호출과 상담 흐름을 관리하는 Agent
    download_html: str | None                          # 다운로드용 대화 기록 HTML

    # =========================================================
    # 생성자
    # =========================================================
    
    def __init__(self):
        self.service = CarManualSearchService(                 # 차량 매뉴얼 검색 서비스
            sql_session=SqlSession(result_log=True)
        )
        self.model = init_chat_model("openai:gpt-6-luna",
        reasoning_effort="none")                               # Agent에서 사용할 LLM
        self.download_html = None                              # 생성된 대화 기록 HTML

        # Agent가 검색 기능과 기록 다운로드 기능을 호출할 수 있도록 Tool로 생성
        car_manual_search_tool = tool(
            self.car_manual_search,
            response_format="content_and_artifact",
        )
        car_manual_history_download_tool = tool(self.car_manual_history_download)

        # Agent가 사용자 요청에 맞는 기능을 선택하도록 두 Tool을 등록
        self.agent = create_agent(
            model=self.model,
            tools=[car_manual_search_tool,car_manual_history_download_tool],
            system_prompt="""너는 자동차 차량 매뉴얼 상담 AI다.

차량의 기능, 사용법, 조작법, 점검, 경고, 차량 문제 해결 등
차량 매뉴얼의 내용이 필요한 질문에는 car_manual_search 도구를 사용한다.
차량 메뉴얼 히스토리 다운로드 해달 라고 하면 car_manual_history_download_tool 도구를 사용 한다.

차량 매뉴얼과 관계없는 질문에는 car_manual_search 도구를 사용하지 않는다.
차량 매뉴얼과 관계없는 일반 대화는 직접 답변한다.
실시간 정보가 필요한 질문에 사용할 수 있는 도구가 없다면
확인할 수 없는 정보를 추측하지 않는다."""
        )

    # =========================================================
    # Agent 도구
    # =========================================================
    def prepare_history_html(self, messages) -> str | None:
        """user/assistant 대화 메시지로 다운로드할 HTML을 만든다."""
        entries = []
        export_message_count = 0
        for message in messages or ():
            if isinstance(message, dict):
                role = message.get("role")
                content = message.get("content")
                images = message.get("images", ())
            else:
                role = {"human": "user", "ai": "assistant"}.get(
                    getattr(message, "type", None)
                )
                content = getattr(message, "content", None)
                images = ()

            if role not in {"user", "assistant"}:
                continue

            message_entries = []
            if isinstance(content, str) and content:
                label = "사용자" if role == "user" else "AI"
                message_entries.append(
                    f"<div><strong>{label}</strong><p>{escape(content)}</p></div>"
                )

            if role == "assistant":
                for image in images or ():
                    if not isinstance(image, dict):
                        continue

                    image_url = image.get("url")
                    if not isinstance(image_url, str) or not image_url:
                        continue

                    description = image.get("description")
                    page_no = image.get("page_no")
                    caption = (
                        f"검색 결과 이미지 · p.{page_no}"
                        + (f" · {description}" if description else "")
                        if page_no is not None
                        else (description or "검색 결과 이미지")
                    )
                    escaped_url = escape(image_url, quote=True)
                    escaped_caption = escape(str(caption), quote=True)
                    message_entries.append(
                        "<figure>"
                        f'<a href="{escaped_url}" target="_blank" '
                        'rel="noopener noreferrer">'
                        f'<img src="{escaped_url}" alt="{escaped_caption}">'
                        "</a>"
                        f"<figcaption>{escape(str(caption))}</figcaption>"
                        "</figure>"
                    )

            if message_entries:
                entries.append("\n".join(message_entries))
                export_message_count += 1

        if not entries:
            return None

        html = f"""<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>Car Manual Conversation History</title>
</head>
<body>
    <h1>자동차 매뉴얼 상담 기록</h1>
    {''.join(entries)}
</body>
</html>
"""
        logger.info(
            "Conversation history HTML created export_messages=%d",
            export_message_count,
        )
        return html

    def car_manual_history_download(
        self,
        runtime: ToolRuntime,
    ) -> str:
        """현재 Agent 대화에서 사용자와 AI 메시지를 골라 HTML 기록을 만든다."""

        # Agent state에서 현재 대화 메시지 목록을 가져온다.
        messages = runtime.state["messages"]                      # 현재 Agent 대화 기록, HTML 생성에 사용
        html = self.prepare_history_html(messages)
        if html is None:
            return "대화 기록이 없어 HTML을 만들지 못했습니다."

        # Tool 호출 측에서 다운로드할 수 있도록 HTML을 인스턴스에 보관한다.
        self.download_html = html

        return "대화 기록 HTML 다운로드를 준비했습니다."


    def car_manual_search(
        self,
        car_brand_eng_nm: str,
        car_eng_nm: str,
        car_model_yr: int,
        question: str,
        runtime: ToolRuntime,
        limit: int = 5,
    ) -> tuple[str, dict]:
        """Agent Tool로 검색 service를 호출하고 답변과 검색 결과 artifact를 반환한다.

        처리 흐름:
        1. Agent 대화에서 현재 질문 이전의 user/assistant 이력을 추린다.
        2. 검색 service에 질문과 대화 이력을 전달한다.
        3. Tool에 보여줄 답변 문자열과 호출자가 사용할 artifact를 반환한다.

        Returns:
            `(답변 문자열, artifact dict)` 형태의 tuple.
            artifact의 `search_results`는 출처와 이미지 처리에 사용된다.
        """
        logger.info(
            f"car_manual_search Tool 호출 - "
            f"{car_brand_eng_nm} {car_eng_nm} {car_model_yr} / {question}"
        )
        # Agent state에서 대화 메시지 목록을 읽는다.
        # region [Python 설명] dict.get()과 기본값
        # `dict.get(key, default)`는 key가 있으면 그 값을, 없으면 default를 돌려준다.
        # 여기서는 `messages`가 없을 때 빈 list를 사용해 아래 순회를 안전하게 한다.
        # endregion
        messages = runtime.state.get("messages", [])              # Agent의 현재 대화 상태

        # 현재 질문과 이전 대화를 구분하기 위해 마지막 user 메시지 위치를 찾는다.
        # region [Python 설명] generator expression과 next() 기본값
        # 괄호 안의 `for ... if ...`는 조건에 맞는 index를 하나씩 만드는 generator expression이다.
        # `next(generator, len(messages))`는 첫 번째 값을 가져오며,
        # 찾는 값이 없으면 두 번째 인자인 `len(messages)`를 사용한다.
        # `range(len(messages) - 1, -1, -1)`은 마지막 index부터 0까지 역순으로 확인한다.
        # endregion
        latest_user_index = next(
            (
                index
                for index in range(len(messages) - 1, -1, -1)
                if getattr(messages[index], "type", None) == "human"
                or (isinstance(messages[index], dict) and messages[index].get("role") == "user")
            ),
            len(messages),
        )

        # 현재 질문은 제외하고 그 앞의 메시지만 대화 이력으로 변환한다.
        conversation_history = []
        for message in messages[:latest_user_index]:
            message_type = getattr(message, "type", None)                    # 객체형 메시지의 종류

            # dict 메시지와 LangChain 메시지 객체를 각각 읽는다.
            # region [Python/LangChain 설명] dict와 메시지 객체 구분
            # Agent 대화에는 일반 dict 또는 `type`, `content` attribute를 가진 객체가 올 수 있다.
            # `isinstance(value, dict)`는 값이 dict인지 확인한다.
            # dict에서는 `.get()`으로 key를 읽고, 객체에서는 `getattr()`로 attribute를 읽는다.
            # `None` 기본값은 해당 key/attribute가 없을 때 사용할 값이다.
            # endregion
            if isinstance(message, dict):
                role = message.get("role")                                    # 딕셔너리 메시지의 역할
                content = message.get("content")                              # 딕셔너리 메시지의 본문
            else:
                role = {"human": "user", "ai": "assistant"}.get(message_type)  # Agent 역할명으로 변환
                content = getattr(message, "content", None)                     # 객체형 메시지의 본문

            # user/assistant 역할의 문자열 본문만 검색 이력에 추가한다.
            if role in {"user", "assistant"} and isinstance(content, str):
                conversation_history.append({"role": role, "content": content})

        # 검색 service에 넘길 대화 이력을 기록한다.
        logger.info("car_manual_search 이전 대화 전달: %s", conversation_history)

        # 답변은 Tool content로, 검색 근거는 artifact로 전달한다.
        search_result = self.service.ask_manual_with_sources(
            car_brand_eng_nm=car_brand_eng_nm,
            car_eng_nm=car_eng_nm,
            car_model_yr=car_model_yr,
            question=question,
            conversation_history=conversation_history,
            limit=limit,
            stream_writer=runtime.stream_writer,
        )

        # Tool 답변과 호출자가 사용할 검색 결과를 tuple로 반환한다.
        return search_result.answer, {"search_results": search_result.search_results}

    # =========================================================
    # Agent 질문
    # =========================================================
    def ask(
        self,
        car_brand_eng_nm: str,
        car_eng_nm: str,
        car_model_yr: int,
        question: str,
        limit: int = 5,
        conversation_history=None,
    ) -> str:
        """차량 질문에 답하고 기존 API 형식의 답변 문자열을 반환한다."""

        # 기존 호출부에는 답변 문자열만 반환해 public API 호환성을 유지한다.
        return self.ask_with_sources(
            car_brand_eng_nm=car_brand_eng_nm,
            car_eng_nm=car_eng_nm,
            car_model_yr=car_model_yr,
            question=question,
            limit=limit,
            conversation_history=conversation_history,
        ).answer

    def ask_with_sources(
        self,
        car_brand_eng_nm: str,
        car_eng_nm: str,
        car_model_yr: int,
        question: str,
        limit: int = 5,
        conversation_history=None,
    ) -> CarManualAnswer:
        """Agent에 질문하고 최종 답변과 같은 호출의 검색 결과를 반환한다.

        이전 대화에서 user/assistant 메시지만 추려 Agent 입력으로 만들고,
        현재 차량 정보와 질문을 포함한 user 메시지를 마지막에 추가한다.
        Agent 실행이 끝나면 마지막 AI 답변과 Tool artifact의 검색 결과를
        `CarManualAnswer`에 함께 담는다.
        """

        user_message = (
            f"제조사: {car_brand_eng_nm}\n"
            f"차량: {car_eng_nm}\n"
            f"연식: {car_model_yr}\n"
            f"검색 문서 수: {limit}\n\n"
            f"질문: {question}"
        )

        # 이전 대화를 Agent가 받는 role/content 메시지 목록으로 변환한다.
        # region [Python 설명] list comprehension과 `(conversation_history or [])`
        # 대괄호 안의 `for ... if ...`는 list comprehension이다.
        # 기존 목록을 순회하며 조건에 맞는 항목만 새 list로 만든다.
        # `conversation_history or []`는 왼쪽 값이 비어 있지 않으면 그 값을 사용하고,
        # None 또는 빈 값처럼 falsy한 값이면 빈 list를 사용한다.
        # Python dict의 `.get("role")`은 role이 없을 때 None을 돌려준다.
        # endregion
        messages = [
            {"role": message["role"], "content": message["content"]}
            for message in (conversation_history or [])
            if message.get("role") in {"user", "assistant"}
        ]

        # 현재 질문을 user 메시지로 마지막에 추가한다.
        # region [Python 설명] list.append()
        # `.append(value)`는 기존 list의 맨 끝에 값 하나를 추가한다.
        # 이 코드는 새 list를 만드는 대신 `messages` 자체를 이어서 채운다.
        # endregion
        messages.append({"role": "user", "content": user_message})

        # Agent에 전체 대화 메시지를 전달해 답변을 생성한다.
        result = self.agent.invoke(
            {
                "messages": messages
            }
        )
        final_message = result["messages"][-1]

        # 이번 Agent 실행 결과에서 검색 Tool artifact를 수집한다.
        # region [Python 설명] getattr(), dict.get(), tuple fallback
        # 메시지 객체의 `artifact`는 `getattr()`로 읽고, 없으면 None을 사용한다.
        # artifact가 dict인지 확인한 뒤 `.get()`으로 검색 결과를 가져온다.
        # `or ()`는 결과가 None 또는 빈 값일 때 빈 tuple을 선택한다.
        # `tuple(...)`은 결과를 tuple로 바꿔 answer 객체에 보관한다.
        # endregion
        search_results = ()
        for message in result["messages"]:
            artifact = getattr(message, "artifact", None)
            if isinstance(artifact, dict) and "search_results" in artifact:
                search_results = tuple(artifact.get("search_results") or ())

        # 최종 답변과 이번 실행의 검색 결과를 함께 반환한다.
        return CarManualAnswer(
            answer=final_message.text,
            search_results=search_results,
        )

    def ask_with_sources_stream(
        self,
        car_brand_eng_nm: str,
        car_eng_nm: str,
        car_model_yr: int,
        question: str,
        limit: int = 5,
        conversation_history=None,
    ) -> CarManualAnswerStream:
        """Agent 답변을 조각 단위로 전달하면서 검색 결과도 함께 보관한다.

        처리 흐름:
        1. 이전 대화를 Agent 입력 형식으로 변환한다.
        2. 현재 질문을 마지막 user 메시지로 추가한다.
        3. Agent streaming iterator를 `chunks`에 연결한다.
        4. 생성 중인 답변 조각, 최종 답변, 검색 결과와 오류를 결과 객체에 보관한다.
        """
        user_message = (
            f"제조사: {car_brand_eng_nm}\n"
            f"차량: {car_eng_nm}\n"
            f"연식: {car_model_yr}\n"
            f"검색 문서 수: {limit}\n\n"
            f"질문: {question}"
        )

        # 이전 대화를 Agent 입력용 메시지 목록으로 변환한다.
        messages = [
            {"role": message["role"], "content": message["content"]}
            for message in (conversation_history or [])
            if message.get("role") in {"user", "assistant"}
        ]

        # 현재 질문을 user 메시지로 마지막에 추가한다.
        # region [Python 설명] list.append()
        # `.append(value)`는 기존 list의 맨 끝에 값 하나를 추가한다.
        # 이 코드는 새 list를 만드는 대신 `messages` 자체를 이어서 채운다.
        # endregion
        messages.append({"role": "user", "content": user_message})

        # 결과 객체에 streaming iterator를 연결해 호출자에게 반환한다.
        answer_stream = CarManualAnswerStream()
        answer_stream.chunks = self._stream_agent_answer(messages, answer_stream)
        return answer_stream

    def _stream_agent_answer(self, messages, answer_stream):
        """Agent event를 읽어 답변 조각을 내보내고 검색 결과를 모은다.

        주요 흐름:
        1. Agent streaming을 시작한다.
        2. custom event의 답변 token을 누적하고 하나씩 yield한다.
        3. updates event에서 Tool 검색 결과와 최종 AI 답변을 저장한다.
        4. 오류가 나고 최종 답변이 비어 있으면 이미 받은 조각을 fallback으로 사용한다.
        5. 성공/실패와 관계없이 전체 처리 시간을 기록한다.

        `answer_stream`은 yield한 조각을 누적하고 최종 답변, 검색 결과,
        오류를 함께 보관하는 결과 객체다.
        """
        total_started = perf_counter()

        try:
            # Agent streaming event를 순서대로 받는다.
            # region [LangGraph 설명] stream_mode
            # `custom` event는 Tool이 stream writer로 직접 보낸 데이터다.
            # 이 흐름에서는 `answer_token`을 답변 조각으로 사용한다.
            # `updates` event는 graph node의 상태 변경 결과를 전달한다.
            # 이 흐름에서는 node의 Tool 메시지 artifact와 최종 AI 메시지를 읽는다.
            # endregion
            for part in self.agent.stream(
                {"messages": messages},
                stream_mode=["updates", "custom"],
                version="v2",
            ):
                # Tool이 보낸 custom event에서 답변 token을 처리한다.
                if part.get("type") == "custom":

                    # event data가 없으면 빈 dict로 처리한다.
                    # region [Python 설명] dict.get()과 truthy/falsy fallback
                    # `.get("data")`는 data key가 없을 때 None을 반환한다.
                    # `or {}`는 data가 None이나 빈 값이면 빈 dict를 선택한다.
                    # Python에서는 None, 빈 문자열, 빈 list/dict 등이 falsy로 평가된다.
                    # endregion
                    data = part.get("data") or {}

                    # 답변 token event의 text를 읽는다.
                    if data.get("type") == "answer_token":

                        # text가 없으면 빈 문자열로 처리한다.
                        # region [Python 설명] `or ""`과 yield
                        # `.get("text")`로 가져온 값이 없거나 falsy하면 빈 문자열을 사용한다.
                        # `yield`는 값을 호출자에게 하나씩 전달하고, 다음 요청 때 이 위치부터 재개한다.
                        # 따라서 이 함수는 일반 반환값 대신 iterator를 만들어 streaming할 수 있다.
                        # endregion
                        text = data.get("text") or ""

                        # 빈 token은 건너뛰고, 나머지는 누적한 뒤 호출자에게 전달한다.
                        if text:
                            answer_stream.streamed_answer += text
                            yield text

                # Agent update event에서 node별 결과와 Tool artifact를 처리한다.
                elif part.get("type") == "updates":

                    # update dict의 각 node 이름과 결과를 확인한다.
                    # region [Python 설명] dict.items()와 unpacking
                    # `.items()`는 dict의 key와 value를 쌍으로 순회하게 한다.
                    # 아래에서 `node_name`은 key, `update`는 그 value를 받는다.
                    # `for node_name, update in ...`의 두 변수 대입은 tuple unpacking이다.
                    # `(part.get("data") or {})`는 data가 없거나 비었을 때 빈 dict를 사용한다.
                    # endregion
                    for node_name, update in (part.get("data") or {}).items():

                        # 각 node 결과에 포함된 메시지를 확인한다.
                        # region [Python 설명] 기본값 tuple 순회
                        # `update.get("messages", ())`는 messages key가 없으면 빈 tuple을 돌려준다.
                        # list와 tuple은 모두 `for ... in ...`으로 순회할 수 있다.
                        # endregion
                        for message in update.get("messages", ()):

                            # Tool 메시지의 artifact에 검색 결과가 있으면 저장한다.
                            # region [Python/LangChain 설명] artifact와 타입 확인
                            # Tool 메시지는 사용자에게 보여줄 content와 별도로 artifact를 가질 수 있다.
                            # `getattr(message, "artifact", None)`은 artifact attribute가 없으면 None을 준다.
                            # `isinstance(artifact, dict)`로 dict인지 확인한 다음,
                            # `.get()`으로 결과를 읽고 `tuple(...)`로 결과 형태를 고정한다.
                            # `or ()`는 검색 결과가 없을 때 사용할 빈 tuple이다.
                            # endregion
                            artifact = getattr(message, "artifact", None)
                            if isinstance(artifact, dict) and "search_results" in artifact:
                                answer_stream.search_results = tuple(
                                    artifact.get("search_results") or ()
                                )

                            # Tool 호출이 없는 최종 AI 메시지를 답변으로 저장한다.
                            # region [Python/LangChain 설명] getattr()와 tool_calls
                            # LangChain 메시지는 필요한 값을 attribute로 제공한다.
                            # `getattr(message, "type", None)`처럼 기본값을 두면
                            # attribute가 없는 메시지도 예외 없이 검사할 수 있다.
                            # `not getattr(message, "tool_calls", ())`는 tool_calls가 없거나
                            # 빈 tuple이면 참이 되어 일반 최종 답변인지 확인하는 조건으로 쓰인다.
                            # endregion
                            if (
                                node_name == "model"
                                and getattr(message, "type", None) == "ai"
                                and not getattr(message, "tool_calls", ())
                            ):
                                answer_stream.answer = getattr(message, "text", "") or ""

        # 예외를 결과 객체에 보관하고 이미 받은 답변 조각을 fallback으로 사용한다.
        except Exception as error:
            answer_stream.error = error
            logger.exception("Streaming vehicle manual answer failed")

            # 최종 답변이 비어 있을 때만 지금까지 받은 token을 사용한다.
            # region [Python 설명] None/빈 문자열의 truthy 검사
            # 빈 문자열은 Python에서 falsy이므로 `not answer_stream.answer`가 참이다.
            # 이미 최종 답변이 있으면 streaming 조각으로 덮어쓰지 않는다.
            # endregion
            if not answer_stream.answer:
                answer_stream.answer = answer_stream.streamed_answer

        # 성공 또는 예외 여부와 관계없이 전체 처리 시간을 기록한다.
        # region [Python 설명] finally
        # `finally` 블록은 try가 정상 종료되거나 except가 실행된 뒤 항상 실행된다.
        # 따라서 종료 시점의 elapsed 시간을 한곳에서 기록할 수 있다.
        # endregion
        finally:
            logger.info(
                "Vehicle manual streaming completed total_ms=%.1f",
                (perf_counter() - total_started) * 1000,
            )




# =========================================================
# 테스트 / 실행 코드
# =========================================================
# region [Python 설명] main guard
# `__name__`은 Python이 모듈에 자동으로 설정하는 이름이다.
# 이 파일을 직접 실행하면 값이 `"__main__"`이고, 다른 파일에서 import하면 모듈 이름이다.
# 따라서 아래 블록은 이 파일을 직접 실행할 때만 동작한다.
# endregion
if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="[%(name)s] %(message)s",
        stream=sys.stdout,
        force=True
    )
    
    
    # PDF 등록은 별도 CarManualRegisterService 테스트에서 수행한다.
    from car_search_rag.car_search.car_manual_register_service import CarManualRegisterService
    file_path = Path(__file__).resolve().parents[3] / "data" / "DN8_2026_ko_KR.pdf"
    register_service = CarManualRegisterService(sql_session=SqlSession(result_log=True))
    register_service.insert_pdf_docs(
        file_path=file_path,
        car_brand_nm="현대",
        car_brand_eng_nm="hyundai",
        car_nm="소나타",
        car_eng_nm="sonata",
        car_model_yr=2026,
    )

    # car_manual = CarManual()
    # answer = car_manual.ask(
    #     car_brand_eng_nm="hyundai",
    #     car_eng_nm="sonata",
    #     car_model_yr=2026,
    #     question="견인 방법 알려줘",
    #     limit=5,
    # )
    # print(answer)
