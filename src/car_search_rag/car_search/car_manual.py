from pathlib import Path
import sys
import logging

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.tools import ToolRuntime
from langchain_core.tools import tool

from car_search_rag.common.sql_session import SqlSession
from car_search_rag.car_search.car_manual_search_service import CarManualSearchService

logger = logging.getLogger("CarManual")


class CarManual:

    # =========================================================
    # 인스턴스 변수
    # =========================================================

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

        # =========================================================
        # Agent 생성
        # =========================================================
        # Agent가 검색 기능과 기록 다운로드 기능을 호출할 수 있도록 Tool로 생성
        car_manual_search_tool = tool(self.car_manual_search)
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
    # 차량 매뉴얼 히스토리 다운로드
    # =========================================================
    def car_manual_history_download(
        self,
        runtime: ToolRuntime,
    ) -> str:
        """현재 자동차 상담 대화 기록을 HTML 형태로 생성한다."""

        messages = runtime.state["messages"]                      # 현재 Agent 대화 기록, HTML 생성에 사용

        html = """
        <html>
        <head>
            <meta charset="utf-8">
            <title>Car Manual Conversation History</title>
        </head>
        <body>
            <h1>자동차 매뉴얼 상담 기록</h1>
        """

        for message in messages:

            message_type = getattr(message, "type", "")           # 메시지 종류(human, ai 등)
            content = getattr(message, "content", "")             # 메시지 본문

            if message_type == "human":
                html += f"""
                <div>
                    <strong>사용자</strong>
                    <p>{content}</p>
                </div>
                """

            elif message_type == "ai" and content:
                html += f"""
                <div>
                    <strong>AI</strong>
                    <p>{content}</p>
                </div>
                """

        html += """
        </body>
        </html>
        """

        # Tool 실행 결과를 호출 측에서 다운로드할 수 있도록 인스턴스에 보관
        self.download_html = html

        return "대화 기록 HTML 다운로드를 준비했습니다."


    # =========================================================
    # 차량 매뉴얼 검색 Tool
    # =========================================================
    def car_manual_search(
        self,
        car_brand_eng_nm: str,
        car_eng_nm: str,
        car_model_yr: int,
        question: str,
        runtime: ToolRuntime,
        limit: int = 5,
    ) -> str:
        """차량 매뉴얼을 검색하여 질문에 답변한다."""
        logger.info(
            f"car_manual_search Tool 호출 - "
            f"{car_brand_eng_nm} {car_eng_nm} {car_model_yr} / {question}"
        )
        messages = runtime.state.get("messages", [])              # Agent의 현재 대화 상태

        # 현재 질문과 구분할 수 있도록 대화 기록에서 가장 최근 사용자 메시지를 찾음
        latest_user_index = next(
            (
                index
                for index in range(len(messages) - 1, -1, -1)
                if getattr(messages[index], "type", None) == "human"
                or (isinstance(messages[index], dict) and messages[index].get("role") == "user")
            ),
            len(messages),
        )
        # 현재 질문이 이전 기록에 중복되지 않도록 마지막 사용자 메시지 이전까지만 구성
        conversation_history = []
        for message in messages[:latest_user_index]:
            message_type = getattr(message, "type", None)                    # 객체형 메시지의 종류
            if isinstance(message, dict):
                role = message.get("role")                                    # 딕셔너리 메시지의 역할
                content = message.get("content")                              # 딕셔너리 메시지의 본문
            else:
                role = {"human": "user", "ai": "assistant"}.get(message_type)  # Agent 역할명으로 변환
                content = getattr(message, "content", None)                     # 객체형 메시지의 본문
            if role in {"user", "assistant"} and isinstance(content, str):
                conversation_history.append({"role": role, "content": content})

        logger.info("car_manual_search 이전 대화 전달: %s", conversation_history)
        # 사용자/AI의 이전 발화를 검색 서비스에 전달해 후속 질문의 문맥을 반영
        return self.service.ask_manual(
            car_brand_eng_nm=car_brand_eng_nm,
            car_eng_nm=car_eng_nm,
            car_model_yr=car_model_yr,
            question=question,
            conversation_history=conversation_history,
            limit=limit,
        )

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

        user_message = (
            f"제조사: {car_brand_eng_nm}\n"
            f"차량: {car_eng_nm}\n"
            f"연식: {car_model_yr}\n"
            f"검색 문서 수: {limit}\n\n"
            f"질문: {question}"
        )


        messages = [
            {"role": message["role"], "content": message["content"]}
            for message in (conversation_history or [])
            if message.get("role") in {"user", "assistant"}
        ]  # Agent에 전달할 이전 사용자/AI 대화
        messages.append({"role": "user", "content": user_message})

        result = self.agent.invoke(
            {
                "messages": messages
            }
        )
        final_message = result["messages"][-1]
        return final_message.text




# =========================================================
# 테스트 / 실행 코드
# =========================================================
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
