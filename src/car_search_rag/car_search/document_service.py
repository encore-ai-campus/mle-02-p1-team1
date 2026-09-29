"""문서 조회 업무 로직."""

from car_search_rag.common.sql_session import SqlSession


class DocumentService:
    # 인스턴스 속성
    sql_session: SqlSession  # 문서 SQL 실행 세션

    def __init__(self, sql_session: SqlSession) -> None:
        self.sql_session = sql_session

    def list_documents(self) -> list[dict]:
        return self.sql_session.select_list("document.select_documents")
