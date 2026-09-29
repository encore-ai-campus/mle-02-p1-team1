"""브랜드별 캡슐 조회 업무 로직."""

from car_search_rag.common.sql_session import SqlSession


class QueryExamplesService:
    # 인스턴스 속성
    sql_session: SqlSession  # 브랜드 SQL 실행 세션

    def __init__(self, sql_session: SqlSession) -> None:
        self.sql_session = sql_session

    def list_brand_counts(self) -> list[dict]:
        return self.sql_session.select_list("query_examples.count_by_brand")

    def list_by_brand(self, brand: str) -> list[dict]:
        return self.sql_session.select_list("query_examples.select_by_brand", {"brand": brand})
