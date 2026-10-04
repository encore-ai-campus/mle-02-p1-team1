from pgvector.utils import Vector
from car_search_rag.common.sql_session import SqlSession


SYSTEM_USER_ID = "SYSTEM"


class CarManualRepository:

    # =========================================================
    # 인스턴스 변수
    # =========================================================

    sql_session: SqlSession  # 차량 매뉴얼 SQL 실행에 사용하는 데이터베이스 세션

    # =========================================================
    # 생성자
    # =========================================================

    def __init__(self, sql_session):
        self.sql_session = sql_session  # 호출 측에서 전달한 데이터베이스 세션

    # =========================================================
    # 매뉴얼 데이터 조회 및 저장 메서드
    # =========================================================
    def get_car_manual_chapter_id(self):
        result = self.sql_session.select_one(
            "car_manual.get_car_manual_chapter_id"
        )  # 등록된 매뉴얼 장의 ID 조회
        return result["carManualChapterId"]

    def insert_car(self, car_brand_nm, car_brand_eng_nm, car_nm, car_eng_nm, car_model_yr):
        result = self.sql_session.execute(  # 차량 정보를 저장하고 생성된 ID를 조회
            "car_manual.merge_car",
            {
                "CAR_BRAND_NM": car_brand_nm,
                "CAR_BRAND_ENG_NM": car_brand_eng_nm,
                "CAR_NM": car_nm,
                "CAR_ENG_NM": car_eng_nm,
                "CAR_MODEL_YR": car_model_yr,
                "USER_ID": SYSTEM_USER_ID
            }
        )
        return result[0]["carId"]

    def insert_car_manual_chapter(self, car_id, car_manual_chapter_id, car_manual_chapter_no,
                                  car_manual_chapter_nm, car_manual_chapter_sort_no):
        self.sql_session.execute(
            "car_manual.insert_car_manual_chapter",
            {
                "CAR_ID": car_id,
                "CAR_MANUAL_CHAPTER_ID": car_manual_chapter_id,
                "CAR_MANUAL_CHAPTER_NO": car_manual_chapter_no,
                "CAR_MANUAL_CHAPTER_NM": car_manual_chapter_nm,
                "CAR_MANUAL_CHAPTER_SORT_NO": car_manual_chapter_sort_no,
                "USER_ID": SYSTEM_USER_ID
            }
        )

    def insert_car_manual_chunks(self, car_id, chapter_map, chunks, embedding_list):
        parameters_list = []  # 여러 청크를 일괄 저장할 SQL 파라미터

        for chunk, embedding in zip(chunks, embedding_list):
            page_no = chunk.metadata["page_no"]  # 청크가 포함된 매뉴얼 페이지
            chapter_id = self._find_chapter_id(chapter_map=chapter_map, page_no=page_no)  # 해당 페이지의 장 ID

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

        return self.sql_session.execute_many(
            "car_manual.insert_car_manual_chunk",
            parameters_list
        )

    def insert_car_manual_images(self, car_id, chapter_map, image_list):
        parameters_list = []  # 이미지 메타데이터 일괄 저장용 SQL 파라미터

        for image in image_list:
            page_no = image["page_no"]  # 이미지가 속한 매뉴얼 페이지
            chapter_id = self._find_chapter_id(chapter_map=chapter_map, page_no=page_no)  # 해당 페이지의 장 ID

            parameters_list.append(
                {
                    "CAR_ID": car_id,
                    "CAR_MANUAL_CHAPTER_ID": chapter_id,
                    "CAR_MANUAL_IMAGE_PAGE_NO": image["page_no"],
                    "CAR_MANUAL_IMAGE_NO": image["image_no"],
                    "CAR_MANUAL_IMAGE_URL": image["image_url"],
                    "CAR_MANUAL_IMAGE_DESC": image.get("image_desc"),
                    "USER_ID": SYSTEM_USER_ID
                }
            )

        return self.sql_session.execute_many(
            "car_manual.insert_car_manual_image",
            parameters_list
        )

    def search_manual(self, car_brand_eng_nm, car_eng_nm, car_model_yr, embedding, limit):
        return self.sql_session.select_list(
            "car_manual.search_car_manual",
            {
                "CAR_BRAND_ENG_NM": car_brand_eng_nm,
                "CAR_ENG_NM": car_eng_nm,
                "CAR_MODEL_YR": car_model_yr,
                "EMBEDDING": Vector(embedding),
                "LIMIT": limit
            }
        )

    def search_images_by_pages(self, car_id, page_nos):
        """Fetch image descriptions only for pages already returned by chunk search."""
        if not car_id or not page_nos:
            return []
        return self.sql_session.select_list(
            "car_manual.search_car_manual_images",
            {"CAR_ID": car_id, "PAGE_NOS": sorted({int(page) for page in page_nos})},
        )

    # =========================================================
    # 내부 보조 메서드
    # =========================================================
    def _find_chapter_id(self, chapter_map, page_no):
        if not chapter_map:
            return None

        for chapter in chapter_map:
            if chapter["start_page"] <= page_no <= chapter["end_page"]:
                return chapter["chapter_id"]

        # 첫 장의 시작 페이지보다 앞선 페이지는 첫 장에 연결
        if page_no < chapter_map[0]["start_page"]:
            return chapter_map[0]["chapter_id"]

        return None
