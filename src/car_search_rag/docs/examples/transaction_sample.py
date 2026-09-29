"""같은 연결에서 여러 SQL을 실행하고 COMMIT/ROLLBACK하는 예제.

group_project 폴더에서 `python -B car_search_rag/docs/examples/transaction_sample.py`로 실행한다.
DB_URL로 연결할 PostgreSQL과 pgvector 확장이 준비되어 있어야 한다.
임시 테이블은 트랜잭션이 끝나면 삭제되므로 기존 업무 데이터는 바꾸지 않는다.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from group_project.common.sql_session import SqlSession
from car_search_rag.car_search.transaction_sample_service import TransactionSampleService


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s", stream=sys.stdout)
    sql_session = SqlSession()

    service = TransactionSampleService(sql_session)
    print("COMMIT 전 조회:", service.run_sample([(1, "첫 항목"), (2, "둘째 항목")]))
    service.verify_rollback()


if __name__ == "__main__":
    main()
