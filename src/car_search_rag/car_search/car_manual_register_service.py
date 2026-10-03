import logging

from langchain_openai import OpenAIEmbeddings
import pymupdf

from car_search_rag.common.sql_session import SqlSession
from car_search_rag.car_search.car_manual_repository import CarManualRepository
from car_search_rag.common.document_reader import DocumentReader
from car_search_rag.common.storage_manager import StorageManager
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


EMBEDDING_MODEL = "text-embedding-3-small"
machine_logger = logging.getLogger("car_search_rag.car_manual")


class CarManualRegisterService:

    # =========================================================
    # 인스턴스 변수
    # =========================================================

    sql_session: SqlSession                    # PDF 등록 과정에서 사용하는 데이터베이스 세션
    repository: CarManualRepository            # 차량 및 매뉴얼 데이터를 저장하는 저장소
    embedding_model: OpenAIEmbeddings          # 매뉴얼 청크 임베딩 생성 모델
    storage_manager: StorageManager            # PDF에서 추출한 이미지를 저장하는 관리자
    document_reader: DocumentReader            # PDF 페이지별 텍스트를 읽는 문서 리더

    # =========================================================
    # 생성자
    # =========================================================

    def __init__(self, sql_session):
        self.sql_session = sql_session                         # 전달받은 데이터베이스 세션
        self.repository = CarManualRepository(sql_session=self.sql_session)  # DB 작업 저장소
        self.embedding_model = OpenAIEmbeddings(model=EMBEDDING_MODEL)  # 청크 임베딩 모델
        self.storage_manager = StorageManager()                # 이미지 업로드 관리자

    # =========================================================
    # 차량 메뉴얼 PDF 처리 메인 파이프 라인
    # =========================================================
    def insert_pdf_docs(self, file_path, car_brand_nm, car_brand_eng_nm, car_nm, car_eng_nm, car_model_yr):
        """차량 매뉴얼 PDF 처리 메인 파이프라인"""

        # =========================================================
        # 1. 차량 정보 등록
        # =========================================================
        car_id = self.insert_car(
            car_brand_nm=car_brand_nm,
            car_brand_eng_nm=car_brand_eng_nm,
            car_nm=car_nm,
            car_eng_nm=car_eng_nm,
            car_model_yr=car_model_yr
        )

        machine_logger.info(f"차량 ID 생성 완료 : {car_id}")

        chapter_list = self._extract_pdf_chapters(file_path)


        chunks = self._extract_and_split_chunks(file_path)      # 2. 텍스트 추출 및 청크 생성

        embedding_list = self._create_chunk_embeddings(chunks=chunks)  # 3. 청크 임베딩

        image_list = self._extract_and_upload_images(file_path=file_path,brand=car_brand_eng_nm,model=car_eng_nm)  # 4. 이미지 추출 및 스토리지 업로드

        # =========================================================
        # 5. Chapter / Chunk / Image DB 등록
        # =========================================================
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


    # =========================================================
    # PDF 텍스트 추출 및 LangChain Chunk 분할 전담
    # =========================================================
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


    # =========================================================
    # PDF 내 이미지 추출 및 Supabase 업로드 전담
    # =========================================================
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



    # =========================================================
    # 차량 매뉴얼 Chunk Embedding 생성
    # =========================================================
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



    # =========================================================
    # PDF 내 이미지 추출 및 Supabase 업로드 전담
    # =========================================================
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




    # =========================================================
    # 결과 확인 및 디버깅용 출력
    # =========================================================
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


    # =========================================================
    # 차량 매뉴얼 Chapter / Chunk / Image DB 등록
    # =========================================================
    def _insert_car_manual_data(self,car_id,chapter_list,chunks,embedding_list,image_list):
        """차량 매뉴얼 Chapter / Chunk / Image DB 등록"""

        with self.sql_session.transaction():

            chapter_map = []

            # =========================================================
            # 1. Chapter 등록
            # =========================================================
            for chapter_no, chapter in enumerate(chapter_list, start=1):

                chapter_id = self.repository.get_car_manual_chapter_id()

                self.repository.insert_car_manual_chapter(
                    car_id=car_id,
                    car_manual_chapter_id=chapter_id,
                    car_manual_chapter_no=chapter_no,
                    car_manual_chapter_nm=chapter["chapter_nm"],
                    car_manual_chapter_sort_no=chapter_no
                )
                machine_logger.info(
                    f"차량 매뉴얼 Chapter 등록 완료 : {chapter_id}"
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



            # =========================================================
            # 2. Chunk 등록
            # =========================================================
            chunk_insert_count = self.repository.insert_car_manual_chunks(
                car_id=car_id,
                chapter_map=chapter_map,
                chunks=chunks,
                embedding_list=embedding_list
            )
            machine_logger.info(
                f"차량 매뉴얼 Chunk 등록 완료 : {chunk_insert_count}개"
            )


            # =========================================================
            # 3. Image 등록
            # =========================================================
            image_insert_count = self.repository.insert_car_manual_images(
                car_id=car_id,
                chapter_map=chapter_map,
                image_list=image_list
            )
            machine_logger.info(
                f"차량 매뉴얼 Image 등록 완료 : {image_insert_count}개"
            )


        machine_logger.info(
            f"차량 매뉴얼 DB 등록 완료 : "
            f"Chunk {chunk_insert_count}개 / "
            f"Image {image_insert_count}개"
        )

        return chunk_insert_count, image_insert_count    


    # =========================================================
    # 차량 매뉴얼 Chapter ID 생성
    # =========================================================
    def get_car_manual_chapter_id(self):
        """차량 매뉴얼 Chapter ID 생성"""
        return self.repository.get_car_manual_chapter_id()


    # =========================================================
    # 차량 등록
    # =========================================================
    def insert_car(self,car_brand_nm,car_brand_eng_nm,car_nm,car_eng_nm,car_model_yr):
        car_id = self.repository.insert_car(
            car_brand_nm=car_brand_nm,
            car_brand_eng_nm=car_brand_eng_nm,
            car_nm=car_nm,
            car_eng_nm=car_eng_nm,
            car_model_yr=car_model_yr
        )
        machine_logger.info(f"차량 등록 완료 : {car_id}")
        return car_id


    # =========================================================
    # 차량 매뉴얼 Chapter 등록
    # =========================================================
    def insert_car_manual_chapter(self,car_id,car_manual_chapter_id,  car_manual_chapter_no,car_manual_chapter_nm,car_manual_chapter_sort_no):
        self.repository.insert_car_manual_chapter(
            car_id=car_id,
            car_manual_chapter_id=car_manual_chapter_id,
            car_manual_chapter_no=car_manual_chapter_no,
            car_manual_chapter_nm=car_manual_chapter_nm,
            car_manual_chapter_sort_no=car_manual_chapter_sort_no
        )
        machine_logger.info(
            f"차량 매뉴얼 Chapter 등록 완료 : {car_manual_chapter_id}"
        )


    # =========================================================
    # 차량 매뉴얼 Chunk 등록
    # =========================================================
    def insert_car_manual_chunks(self,car_id,chapter_map,chunks,embedding_list):
        insert_count = self.repository.insert_car_manual_chunks(
            car_id=car_id,
            chapter_map=chapter_map,
            chunks=chunks,
            embedding_list=embedding_list
        )
        machine_logger.info(
            f"차량 매뉴얼 Chunk 등록 완료 : {insert_count}개"
        )
        return insert_count


    # =========================================================
    # 차량 매뉴얼 Image 등록
    # =========================================================
    def insert_car_manual_images(self,car_id,chapter_map,image_list):
        """차량 매뉴얼 이미지 정보 DB 등록"""
        insert_count = self.repository.insert_car_manual_images(
            car_id=car_id,
            chapter_map=chapter_map,
            image_list=image_list
        )
        machine_logger.info(
            f"차량 매뉴얼 Image 등록 완료 : {insert_count}개"
        )
        return insert_count




    # =========================================================
    # PDF 1레벨 목차 추출
    # =========================================================
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
