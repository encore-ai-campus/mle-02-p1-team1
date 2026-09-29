"""임시 테이블 트랜잭션 예제의 실행 진입점."""

from pathlib import Path
import sys

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from car_search_rag.common.sql_session import SqlSession
from car_search_rag.car_search.transaction_sample_service import TransactionSampleService


def main() -> None:
    print(TransactionSampleService(SqlSession()).run_sample([(1, "첫 항목"), (2, "둘째 항목")]))


if __name__ == "__main__":
    main()
