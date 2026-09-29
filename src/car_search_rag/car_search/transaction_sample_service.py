"""임시 테이블 작업을 하나의 트랜잭션으로 실행한다."""

from car_search_rag.common.sql_session import SqlSession


class TransactionSampleService:
    # 인스턴스 속성
    sql_session: SqlSession  # 트랜잭션 SQL 실행 세션

    def __init__(self, sql_session: SqlSession) -> None:
        self.sql_session = sql_session

    def run_sample(self, items: list[tuple[int, str]]) -> list[dict]:
        with self.sql_session.transaction():
            self.sql_session.execute("transaction_sample.create_temp_table")
            for item_id, item_name in items:
                self.sql_session.execute(
                    "transaction_sample.insert_item", {"item_id": item_id, "item_name": item_name}
                )
            return self.sql_session.select_list("transaction_sample.select_items")

    def verify_rollback(self) -> None:
        """기존 예제의 오류 발생 시 ROLLBACK 흐름을 확인한다."""
        try:
            with self.sql_session.transaction():
                self.sql_session.execute("transaction_sample.create_temp_table")
                self.sql_session.execute(
                    "transaction_sample.insert_item", {"item_id": 3, "item_name": "취소할 항목"}
                )
                raise RuntimeError("롤백 확인용 오류")
        except RuntimeError as exc:
            print("ROLLBACK 완료:", exc)
