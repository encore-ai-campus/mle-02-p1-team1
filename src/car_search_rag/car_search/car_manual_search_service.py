import logging
import re
from pathlib import Path

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from pgvector.utils import Vector
from pypdf import PdfReader
import pymupdf

from car_search_rag.common.sql_session import SqlSession
from car_search_rag.common import document_reader
from car_search_rag.common.document_reader import DocumentReader
from car_search_rag.common.storage_manager import StorageManager
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser



SYSTEM_USER_ID = "SYSTEM"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536
machine_logger = logging.getLogger("car_search_rag.car_manual")

#=========================================================
# 차량 매뉴얼 검색 Service
#=========================================================
class CarManualSearchService:

    sql_session : SqlSession
    embedding_model : OpenAIEmbeddings
    storage_manager: StorageManager
    chat_model : ChatOpenAI

    #=========================================================
    # 생성자
    #=========================================================
    def __init__(self,sql_session):
        self.sql_session = sql_session

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


        self.storage_manager = StorageManager()


    #=========================================================
    # 차량 메뉴얼 PDF 처리 메인 파이프 라인
    #=========================================================
    def insert_pdf_docs(self, file_path, car_brand_nm, car_brand_eng_nm, car_nm, car_eng_nm, car_model_yr):
        """차량 매뉴얼 PDF 처리 메인 파이프라인"""

        #=====================================================
        # 1. 차량 정보 등록
        #=====================================================
        car_id = self.insert_car(
            car_brand_nm=car_brand_nm,
            car_brand_eng_nm=car_brand_eng_nm,
            car_nm=car_nm,
            car_eng_nm=car_eng_nm,
            car_model_yr=car_model_yr
        )

        machine_logger.info(f"차량 ID 생성 완료 : {car_id}")

        chapter_list = self._extract_pdf_chapters(file_path)


        # 2. 텍스트 추출 및 청크 생성
        chunks = self._extract_and_split_chunks(file_path)

        # 3. 청크 임베딩
        embedding_list = self._create_chunk_embeddings(chunks=chunks)

        # 4. 이미지 추출 및 스토리지 업로드
        image_list = self._extract_and_upload_images(file_path=file_path,brand=car_brand_eng_nm,model=car_eng_nm)

        #=====================================================
        # 5. Chapter / Chunk / Image DB 등록
        #=====================================================
        self._insert_car_manual_data(
            car_id=car_id,
            chapter_list=chapter_list,
            chunks=chunks,
            embedding_list=embedding_list,
            image_list=image_list
        )

        # 6. 디버깅 출력 (필요 시 별도 디버그 함수로 추출 가능)
        self._print_summary(chunks, image_list)
        
        return chunks, image_list


    #=========================================================
    # PDF 텍스트 추출 및 LangChain Chunk 분할 전담
    #=========================================================
    def _extract_and_split_chunks(self, file_path):
        """PDF 텍스트 추출 및 LangChain Chunk 분할 전담"""
        self.document_reader = DocumentReader(file_path=file_path)
        self.document_reader.set_pdf_reader()
        self.document_reader.set_pdf_doc_list()
        
        machine_logger.info(f"PDF Text 읽기 완료 : {len(self.document_reader.doc_list)} 페이지")

        documents = [
            Document(
                page_content=doc["text"],
                metadata={"page_no": doc["page_no"]}
            )
            for doc in self.document_reader.doc_list
        ]

        splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)
        chunks = splitter.split_documents(documents)

        for chunk_no, chunk in enumerate(chunks, start=1):
            chunk.metadata["chunk_no"] = chunk_no

        machine_logger.info(f"Chunk 분할 완료 : 전체 {len(chunks)}개")
        return chunks


    #=========================================================
    # PDF 내 이미지 추출 및 Supabase 업로드 전담
    #=========================================================
    def _extract_and_upload_images(self, file_path, brand, model):
        """PDF 내 이미지 추출 및 Supabase 업로드 전담"""
        car_manual_image_list = []
        
        with pymupdf.open(file_path) as pdf_document:
            total_pages = len(pdf_document)
            machine_logger.info(f"이미지 추출 및 Storage 업로드 시작 : 전체 {total_pages} 페이지")

            for page_index in range(total_pages):
                page = pdf_document[page_index]
                page_no = page_index + 1
                page_image_list = page.get_images(full=True)

                for image_index, image_info in enumerate(page_image_list, start=1):
                    image_data = self._upload_single_image(
                        pdf_document, image_info, page_no, image_index, brand, model
                    )
                    if image_data:
                        car_manual_image_list.append(image_data)

        return car_manual_image_list



    #=========================================================
    # 차량 매뉴얼 Chunk Embedding 생성
    #=========================================================
    def _create_chunk_embeddings(self, chunks):
        """차량 매뉴얼 Chunk 텍스트 Embedding 생성"""

        machine_logger.info(
            f"Chunk Embedding 생성 시작 : {len(chunks)}개"
        )

        chunk_text_list = [
            chunk.page_content
            for chunk in chunks
        ]

        embedding_list = self.embedding_model.embed_documents(
            chunk_text_list
        )

        machine_logger.info(
            f"Chunk Embedding 생성 완료 : {len(embedding_list)}개"
        )

        return embedding_list



    #=========================================================
    # PDF 내 이미지 추출 및 Supabase 업로드 전담
    #=========================================================
    def _upload_single_image(self, pdf_document, image_info, page_no, image_index, brand, model):
        """단일 이미지 추출 및 업로드 처리"""
        try:
            xref = image_info[0]
            image_data = pdf_document.extract_image(xref)
            image_bytes = image_data["image"]
            image_ext = image_data["ext"]

            image_name = f"page_{page_no:04d}_image_{image_index:02d}.{image_ext}"

            machine_logger.info(
                f"이미지 업로드 시작 : {image_name} ({len(image_bytes):,} bytes)"
            )

            image_url = self.storage_manager.upload_car_image_bytes(
                image_bytes=image_bytes,
                brand=brand,
                model=model,
                image_name=image_name
            )

            machine_logger.info(f"이미지 업로드 완료 : {image_name}")

            return {
                "page_no": page_no,
                "image_no": image_index,
                "image_xref": xref,
                "image_name": image_name,
                "image_url": image_url
            }

        except Exception as e:
            machine_logger.exception(
                f"이미지 업로드 실패 : 페이지 {page_no}, 이미지 {image_index} - {e}"
            )
            return None




    #=========================================================
    # 결과 확인 및 디버깅용 출력
    #=========================================================
    def _print_summary(self, chunks, car_manual_image_list):
        """결과 확인 및 디버깅용 출력"""
        for index, chunk in enumerate(chunks[:10]):
            print(f"===== CHUNK {index + 1} =====")
            print("페이지:", chunk.metadata.get("page_no"))
            print("청크 번호:", chunk.metadata.get("chunk_no"))
            print("길이:", len(chunk.page_content))
            print(chunk.page_content)
            print()

        print("전체 Chunk 수:", len(chunks))
        print("전체 이미지 수:", len(car_manual_image_list))

        for car_manual_image in car_manual_image_list[:10]:
            print(car_manual_image)


    #=========================================================
    # 차량 매뉴얼 Chapter / Chunk / Image DB 등록
    #=========================================================
    def _insert_car_manual_data(self,car_id,chapter_list,chunks,embedding_list,image_list):
        """차량 매뉴얼 Chapter / Chunk / Image DB 등록"""

        with self.sql_session.transaction():

            chapter_map = []

            #=====================================================
            # 1. Chapter 등록
            #=====================================================
            for chapter_no, chapter in enumerate(chapter_list, start=1):

                chapter_id = self.get_car_manual_chapter_id()

                self.insert_car_manual_chapter(
                    car_id=car_id,
                    car_manual_chapter_id=chapter_id,
                    car_manual_chapter_no=chapter_no,
                    car_manual_chapter_nm=chapter["chapter_nm"],
                    car_manual_chapter_sort_no=chapter_no
                )

                chapter_map.append({
                        "chapter_id": chapter_id,
                        "chapter_nm": chapter["chapter_nm"],
                        "start_page": chapter["start_page"],
                        "end_page": chapter["end_page"]
                    })


                machine_logger.info(
                    f"차량 매뉴얼 Chapter 등록 완료 : "
                    f"{chapter_no}. {chapter['chapter_nm']}"
                )



            #=====================================================
            # 2. Chunk 등록
            #=====================================================
            chunk_insert_count = self.insert_car_manual_chunks(
                car_id=car_id,
                chapter_map=chapter_map,
                chunks=chunks,
                embedding_list=embedding_list
            )


            #=====================================================
            # 3. Image 등록
            #=====================================================
            image_insert_count = self.insert_car_manual_images(
                car_id=car_id,
                chapter_map=chapter_map,
                image_list=image_list
            )


        machine_logger.info(
            f"차량 매뉴얼 DB 등록 완료 : "
            f"Chunk {chunk_insert_count}개 / "
            f"Image {image_insert_count}개"
        )

        return chunk_insert_count, image_insert_count    


    #=========================================================
    # 차량 매뉴얼 Chapter ID 생성
    #=========================================================
    def get_car_manual_chapter_id(self):
        """차량 매뉴얼 Chapter ID 생성"""

        result = self.sql_session.select_one(
            "car_manual_search.get_car_manual_chapter_id"
        )

        return result["carManualChapterId"]    


    #=========================================================
    # 차량 등록
    #=========================================================
    def insert_car(self,car_brand_nm,car_brand_eng_nm,car_nm,car_eng_nm,car_model_yr):

        result = self.sql_session.execute(
        "car_manual_search.merge_car",
        {
            "CAR_BRAND_NM": car_brand_nm,
            "CAR_BRAND_ENG_NM": car_brand_eng_nm,
            "CAR_NM": car_nm,
            "CAR_ENG_NM": car_eng_nm,
            "CAR_MODEL_YR": car_model_yr,
            "USER_ID": SYSTEM_USER_ID
        }
        )

        car_id = result[0]["carId"]

        machine_logger.info(f"차량 등록 완료 : {car_id}")

        return car_id


    #=========================================================
    # 차량 매뉴얼 Chapter 등록
    #=========================================================
    def insert_car_manual_chapter(self,car_id,car_manual_chapter_id,  car_manual_chapter_no,car_manual_chapter_nm,car_manual_chapter_sort_no):

        self.sql_session.execute(
            "car_manual_search.insert_car_manual_chapter",
            {
                "CAR_ID": car_id,
                "CAR_MANUAL_CHAPTER_ID": car_manual_chapter_id,
                "CAR_MANUAL_CHAPTER_NO": car_manual_chapter_no,
                "CAR_MANUAL_CHAPTER_NM": car_manual_chapter_nm,
                "CAR_MANUAL_CHAPTER_SORT_NO": car_manual_chapter_sort_no,
                "USER_ID": SYSTEM_USER_ID
            }
        )

        machine_logger.info(
            f"차량 매뉴얼 Chapter 등록 완료 : {car_manual_chapter_id}"
        )


    #=========================================================
    # 차량 매뉴얼 Chunk 등록
    #=========================================================
    def insert_car_manual_chunks(self,car_id,chapter_map,chunks,embedding_list):

        parameters_list = []

        for chunk, embedding in zip(chunks, embedding_list):

            page_no = chunk.metadata["page_no"]    

            chapter_id = self._find_chapter_id(chapter_map=chapter_map,page_no=page_no)

            parameters_list.append(
                {
                    "CAR_ID": car_id,
                    "CAR_MANUAL_CHAPTER_ID": chapter_id,
                    "CAR_MANUAL_CHUNK_PAGE_NO": chunk.metadata["page_no"],
                    "CAR_MANUAL_CHUNK_NO": chunk.metadata["chunk_no"],
                    "CAR_MANUAL_CHUNK_TXT": chunk.page_content,
                    "CAR_MANUAL_CHUNK_EMBED_VEC": Vector(embedding),
                    "USER_ID": SYSTEM_USER_ID
                }
            )

        insert_count = self.sql_session.execute_many(
            "car_manual_search.insert_car_manual_chunk",
            parameters_list
        )

        machine_logger.info(
            f"차량 매뉴얼 Chunk 등록 완료 : {insert_count}개"
        )

        return insert_count


    #=========================================================
    # 차량 매뉴얼 Image 등록
    #=========================================================
    def insert_car_manual_images(self,car_id,chapter_map,image_list):
        """차량 매뉴얼 이미지 정보 DB 등록"""

        parameters_list = []

        for image in image_list:

            page_no = image["page_no"]    

            chapter_id = self._find_chapter_id(chapter_map=chapter_map,page_no=page_no)

            parameters_list.append(
                {
                    "CAR_ID": car_id,
                    "CAR_MANUAL_CHAPTER_ID": chapter_id,
                    "CAR_MANUAL_IMAGE_PAGE_NO": image["page_no"],
                    "CAR_MANUAL_IMAGE_NO": image["image_no"],
                    "CAR_MANUAL_IMAGE_URL": image["image_url"],
                    "CAR_MANUAL_IMAGE_DESC": None,
                    "USER_ID": SYSTEM_USER_ID
                }
            )

        insert_count = self.sql_session.execute_many(
            "car_manual_search.insert_car_manual_image",
            parameters_list
        )

        machine_logger.info(
            f"차량 매뉴얼 Image 등록 완료 : {insert_count}개"
        )

        return insert_count




    #=========================================================
    # 차량 매뉴얼 AI 검색
    #=========================================================
    def search_manual(self,car_brand_eng_nm,car_eng_nm,car_model_yr,question,limit=5):

        #=====================================================
        # 질문 임베딩
        #=====================================================
        query_vector = self.embedding_model.embed_query(question)


        #=====================================================
        # 질문과 유사한 PDF 내용 검색
        #=====================================================
        result = self.sql_session.select_list(
            "car_manual_search.search_car_manual",
            {
                "CAR_BRAND_ENG_NM": car_brand_eng_nm,
                "CAR_ENG_NM": car_eng_nm,
                "CAR_MODEL_YR": car_model_yr,
                "EMBEDDING": Vector(query_vector),
                "LIMIT": limit
            }
        )

        return result



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




    #=========================================================
    # PDF 1레벨 목차 추출
    #=========================================================
    def _extract_pdf_chapters(self, file_path):

        chapter_list = []

        with pymupdf.open(file_path) as pdf_document:

            total_pages = len(pdf_document)

            toc_list = [
                (title, page_no)
                for level, title, page_no
                in pdf_document.get_toc(simple=True)
                if level == 1
            ]

            for index, (title, start_page) in enumerate(toc_list):

                if index + 1 < len(toc_list):
                    end_page = toc_list[index + 1][1] - 1
                else:
                    end_page = total_pages

                chapter_list.append({
                    "chapter_nm": title,
                    "start_page": start_page,
                    "end_page": end_page
                })

        return chapter_list


    #=========================================================
    # 페이지 번호에 해당하는 Chapter 찾기
    #=========================================================
    def _find_chapter_id(self, chapter_map, page_no):

        if not chapter_map:
                return None

        for chapter in chapter_map:

            if chapter["start_page"] <= page_no <= chapter["end_page"]:
                return chapter["chapter_id"]

        # 첫 Chapter 시작 전 페이지는 첫 Chapter로 처리
        if page_no < chapter_map[0]["start_page"]:
            return chapter_map[0]["chapter_id"]

        return None

