import logging

from langchain_openai import OpenAIEmbeddings, ChatOpenAI

from car_search_rag.common.sql_session import SqlSession
from car_search_rag.car_search.car_manual_repository import CarManualRepository
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536
machine_logger = logging.getLogger("car_search_rag.car_manual")

#=========================================================
# 차량 매뉴얼 검색 Service
#=========================================================
class CarManualSearchService:

    sql_session : SqlSession
    embedding_model : OpenAIEmbeddings
    chat_model : ChatOpenAI

    #=========================================================
    # 생성자
    #=========================================================
    def __init__(self,sql_session):
        self.sql_session = sql_session
        self.repository = CarManualRepository(sql_session=self.sql_session)

        self.embedding_model = OpenAIEmbeddings(
            model=EMBEDDING_MODEL
        )

        self.chat_model = ChatOpenAI(
                model="gpt-6-luna"
            )


        #=====================================================
        # 검색 질문 재작성 Chain
        #=====================================================
        self.rewrite_search_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
    너는 차량 매뉴얼 검색용 질문을 만드는 역할이다.

    이전 대화를 참고해서 현재 질문을
    혼자 읽어도 의미가 통하는 검색 문장으로 다시 작성해라.

    차량 매뉴얼 검색에 도움이 되는 관련 용어나 동의어가 있으면 포함해라.

    설명하지 말고 검색 문장 하나만 반환해라.
    """
                ),
                (
                    "human",
                    """
    [이전 대화]
    {history}

    [현재 질문]
    {question}
    """
                )
            ]
        )

        self.rewrite_search_chain = (
            self.rewrite_search_prompt
            | self.chat_model
            | StrOutputParser()
        )

        #=====================================================
        # 차량 매뉴얼 답변 생성 Chain
        #=====================================================
        self.manual_answer_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
        너는 차량 사용 설명서를 안내하는 AI 어시스턴트다.

        이전 대화와 차량 매뉴얼 검색 결과를 참고해서
        현재 사용자의 질문에 자연스럽게 답변해라.

        규칙:
        - 이전 대화의 맥락을 유지한다.
        - 매뉴얼 내용에 근거해서 답변한다.
        - 매뉴얼에 없는 내용은 추측하지 않는다.
        - 관련 페이지 번호를 함께 알려준다.
        - 관련 이미지 URL이 있으면 함께 알려준다.
        """
                ),
                (
                    "human",
                    """
        [이전 대화]
        {history}

        [현재 질문]
        {question}

        [차량 매뉴얼]
        {context}
        """
                )
            ]
        )

        self.manual_answer_chain = (
            self.manual_answer_prompt
            | self.chat_model
            | StrOutputParser()
        )






    #=========================================================
    # 차량 매뉴얼 AI 검색
    #=========================================================
    def search_manual(self,car_brand_eng_nm,car_eng_nm,car_model_yr,question,limit=5):
        query_vector = self.embedding_model.embed_query(question)
        return self.repository.search_manual(
            car_brand_eng_nm=car_brand_eng_nm,
            car_eng_nm=car_eng_nm,
            car_model_yr=car_model_yr,
            embedding=query_vector,
            limit=limit
        )



    #=========================================================
    # 차량 매뉴얼 LLM 답변 생성
    #=========================================================
    def generate_manual_answer(self,question,search_docs,conversation_history=None):
        
        if not search_docs:
            return "관련된 차량 매뉴얼 내용을 찾지 못했습니다."

        context_list = []

        for index, doc in enumerate(search_docs, start=1):

            context_list.append(
                f"""
    [검색 문서 {index}]

    페이지:
    {doc.get("carManualChunkPageNo")}

    내용:
    {doc.get("carManualChunkTxt")}

    이미지 URL:
    {doc.get("carManualImageUrl") or "없음"}
    """
            )

        context = "\n".join(context_list)

        #=====================================================
        # 이전 대화 문자열 생성
        #=====================================================
        if conversation_history:

            recent_messages = conversation_history

            history_text = "\n".join(
                [
                    f"{message['role']}: {message['content']}"
                    for message in recent_messages
                ]
            )

        else:
            history_text = "없음"

        #=====================================================
        # LangChain 실행
        #=====================================================
        answer = self.manual_answer_chain.invoke(
            {
                "history": history_text,
                "question": question,
                "context": context
            }
        )

        return answer


    #=========================================================
    # 차량 매뉴얼 AI 질의
    #=========================================================
    def ask_manual(self, car_brand_eng_nm, car_eng_nm, car_model_yr, question, conversation_history=None, limit=5):

        #=====================================================
        # 이전 대화 기반 검색 질문 재작성
        #=====================================================
        search_question = self.rewrite_search_question(
            question=question,
            conversation_history=conversation_history
        )


        #=====================================================
        # 차량 매뉴얼 검색
        #=====================================================
        search_docs = self.search_manual(
            car_brand_eng_nm=car_brand_eng_nm,
            car_eng_nm=car_eng_nm,
            car_model_yr=car_model_yr,
            question=search_question,
            limit=limit
        )


        #=====================================================
        # LLM 답변 생성
        #=====================================================
        answer = self.generate_manual_answer(
            question=question,
            search_docs=search_docs,
            conversation_history=conversation_history
        )

        return answer


    #=========================================================
    # 이전 대화 기반 검색 질문 재작성
    #=========================================================
    def rewrite_search_question(self, question, conversation_history=None ):
        """이전 대화를 참고하여 검색용 질문을 독립적인 문장으로 재작성"""

        # 이전 대화가 없으면 현재 질문 그대로 사용
        if not conversation_history:
            return question


        # 최근 6개 메시지만 사용
        recent_messages = conversation_history


        history_text = "\n".join(
            [
                f"{message['role']}: {message['content']}"
                for message in recent_messages
            ]
        )


        #=====================================================
        # LangChain 실행
        #=====================================================
        search_question = self.rewrite_search_chain.invoke(
            {
                "history": history_text,
                "question": question
            }
        )

        return search_question.strip()
