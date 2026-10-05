from pgvector.utils import Vector
from car_search_rag.common.sql_session import SqlSession


SYSTEM_USER_ID = "SYSTEM"


class CarManualRepository:

    sql_session: SqlSession  # 차량 매뉴얼 SQL 실행에 사용하는 데이터베이스 세션

    def __init__(self, sql_session):
        self.sql_session = sql_session  # 호출 측에서 전달한 데이터베이스 세션

    # =========================================================
    # 차량 및 매뉴얼 등록
    # =========================================================
    def get_car_manual_chapter_id(self):
        """DB에서 새 매뉴얼 chapter ID를 조회한다."""
        result = self.sql_session.select_one(
            "car_manual.get_car_manual_chapter_id"
        )  # 등록된 매뉴얼 장의 ID 조회
        return result["carManualChapterId"]

    def insert_car(self, car_brand_nm, car_brand_eng_nm, car_nm, car_eng_nm, car_model_yr):
        """차량 정보를 DB에 전달하고 저장된 차량 ID를 반환한다."""
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
        """Chunk와 embedding을 짝지어 batch insert용 parameter 목록을 만든다."""
        # 여러 청크를 한 번의 batch insert에 전달할 parameter 목록을 준비한다.
        parameters_list = []

        # 각 chunk와 같은 위치의 embedding으로 DB 행을 구성한다.
        # region [Python 설명] zip()으로 두 입력 짝짓기
        # `zip(chunks, embedding_list)`는 두 iterable의 같은 위치 값을 tuple처럼 묶는다.
        # 두 목록 길이가 다르면 더 짧은 쪽이 끝나는 시점에 순회도 끝난다.
        # 여기서는 chunk 본문/metadata와 해당 chunk embedding을 함께 처리한다.
        # endregion
        for chunk, embedding in zip(chunks, embedding_list):
            page_no = chunk.metadata["page_no"]  # 청크가 포함된 매뉴얼 페이지
            chapter_id = self._find_chapter_id(chapter_map=chapter_map, page_no=page_no)  # 해당 페이지의 장 ID

            # SQL mapper가 요구하는 이름으로 한 건의 parameter dict를 만든다.
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

        # 완성한 parameter 목록을 SQL mapper의 batch insert에 전달한다.
        return self.sql_session.execute_many(
            "car_manual.insert_car_manual_chunk",
            parameters_list
        )

    def insert_car_manual_images(self, car_id, chapter_map, image_list):
        """이미지 목록을 DB batch insert용 parameter로 바꿔 저장한다."""
        # 이미지마다 SQL mapper에 전달할 parameter dict를 만든다.
        parameters_list = []

        # 이미지 설명은 선택값이므로 없는 경우 None으로 저장한다.
        # region [Python 설명] dict.get()과 선택값
        # `image.get("image_desc")`는 key가 없으면 None을 반환한다.
        # key가 없어도 예외 없이 DB parameter를 구성할 수 있다.
        # endregion
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

        # 이미지 parameter 목록을 batch insert한다.
        return self.sql_session.execute_many(
            "car_manual.insert_car_manual_image",
            parameters_list
        )

    # =========================================================
    # 검색 및 이미지 조회
    # =========================================================
    def search_manual(self, car_brand_eng_nm, car_eng_nm, car_model_yr, embedding, limit):
        """차량 조건과 embedding으로 Vector 검색 row 목록을 조회한다."""
        # Python 값을 SQL mapper parameter 이름에 맞춰 전달한다.
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

    def find_car_id(self, car_brand_eng_nm, car_eng_nm, car_model_yr):
        """차량 조건과 일치하는 row가 하나인지 확인하고 차량 ID를 반환한다."""
        rows = self.sql_session.select_list(
            "car_manual.find_car_id",
            {
                "CAR_BRAND_ENG_NM": car_brand_eng_nm,
                "CAR_ENG_NM": car_eng_nm,
                "CAR_MODEL_YR": car_model_yr,
            },
        )
        if len(rows) != 1:
            raise LookupError(f"Expected one matching car row, found {len(rows)}")
        return rows[0].get("carId", rows[0].get("car_id"))

    def search_manual_by_keywords(self, car_id, phrases, terms, limit):
        """phrase/term 검색어를 정리해 Keyword Search row 목록을 조회한다."""
        # 문자열 검색어만 남기고 순서를 유지하며 중복을 제거한다.
        # region [Python 설명] generator expression과 dict.fromkeys()
        # 괄호 안의 `for ... if ...`는 조건을 통과한 값을 하나씩 만드는 generator expression이다.
        # `dict.fromkeys(...)`는 입력 순서를 유지하면서 같은 검색어를 한 번만 남긴다.
        # `list(...)`는 최종 결과를 SQL parameter로 전달할 list로 만든다.
        # endregion
        phrases = list(dict.fromkeys(item.strip() for item in phrases if isinstance(item, str) and item.strip()))
        terms = list(dict.fromkeys(item.strip() for item in terms if isinstance(item, str) and item.strip()))

        # 검색어가 전혀 없으면 SQL을 호출하지 않는다.
        if not phrases and not terms:
            return []

        # 정리된 검색어와 차량 ID를 mapper parameter로 전달한다.
        return self.sql_session.select_list(
            "car_manual.search_car_manual_by_keywords",
            {"CAR_ID": car_id, "PHRASES": phrases, "TERMS": terms, "LIMIT": limit},
        )

    def search_images_by_pages(self, car_id, page_nos):
        """지정 차량의 검색 결과 page에 해당하는 이미지 row를 조회한다."""
        if not car_id or not page_nos:
            return []

        # page 번호를 정수로 바꾸고 중복 제거·정렬해 mapper에 전달한다.
        # region [Python 설명] set comprehension과 sorted()
        # `{int(page) for page in page_nos}`는 변환된 page 번호의 중복을 제거한다.
        # `sorted(...)`는 set의 순서가 정해져 있지 않으므로 정렬된 list를 만든다.
        # endregion
        return self.sql_session.select_list(
            "car_manual.search_car_manual_images",
            {"CAR_ID": car_id, "PAGE_NOS": sorted({int(page) for page in page_nos})},
        )

    # =========================================================
    # 내부 page-chapter 매핑
    # =========================================================
    def _find_chapter_id(self, chapter_map, page_no):
        """페이지 번호가 포함된 chapter의 ID를 찾는다."""
        if not chapter_map:
            return None

        for chapter in chapter_map:
            if chapter["start_page"] <= page_no <= chapter["end_page"]:
                return chapter["chapter_id"]

        # 첫 장의 시작 페이지보다 앞선 페이지는 첫 장에 연결
        if page_no < chapter_map[0]["start_page"]:
            return chapter_map[0]["chapter_id"]

        return None
