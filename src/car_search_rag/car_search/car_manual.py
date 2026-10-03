from pathlib import Path
import sys
import logging

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.tools import tool

from car_search_rag.common.sql_session import SqlSession
from car_search_rag.car_search.car_manual_search_service import CarManualSearchService

logger = logging.getLogger("CarManual")


class CarManual:
    def __init__(self):
        self.service = CarManualSearchService(sql_session=SqlSession(result_log=True))
        self.model = init_chat_model("openai:gpt-6-luna")

        #=========================================================
        # Agent 생성
        #=========================================================
        car_manual_search_tool = tool(self.car_manual_search)
        self.agent = create_agent(
            model=self.model,
            tools=[car_manual_search_tool],
            system_prompt="""너는 자동차 차량 매뉴얼 상담 AI다.

차량의 기능, 사용법, 조작법, 점검, 경고, 차량 문제 해결 등
차량 매뉴얼의 내용이 필요한 질문에는 car_manual_search 도구를 사용한다.
차량 매뉴얼과 관계없는 질문에는 car_manual_search 도구를 사용하지 않는다.
차량 매뉴얼과 관계없는 일반 대화는 직접 답변한다.
실시간 정보가 필요한 질문에 사용할 수 있는 도구가 없다면
확인할 수 없는 정보를 추측하지 않는다."""
        )

    #=========================================================
    # 차량 매뉴얼 검색 Tool
    #=========================================================
    def car_manual_search(
        self,
        car_brand_eng_nm: str,
        car_eng_nm: str,
        car_model_yr: int,
        question: str,
        limit: int = 5,
    ) -> str:
        """차량 매뉴얼을 검색하여 질문에 답변한다."""
        logger.info(
            f"car_manual_search Tool 호출 - "
            f"{car_brand_eng_nm} {car_eng_nm} {car_model_yr} / {question}"
        )
        return self.service.ask_manual(
            car_brand_eng_nm=car_brand_eng_nm,
            car_eng_nm=car_eng_nm,
            car_model_yr=car_model_yr,
            question=question,
            limit=limit,
        )

    #=========================================================
    # Agent 질문
    #=========================================================
    def ask(
        self,
        car_brand_eng_nm: str,
        car_eng_nm: str,
        car_model_yr: int,
        question: str,
        limit: int = 5,
    ) -> str:

        user_message = (
            f"제조사: {car_brand_eng_nm}\n"
            f"차량: {car_eng_nm}\n"
            f"연식: {car_model_yr}\n"
            f"검색 문서 수: {limit}\n\n"
            f"질문: {question}"
        )


        result = self.agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": user_message,
                    }
                ]
            }
        )
        final_message = result["messages"][-1]
        return final_message.text


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
