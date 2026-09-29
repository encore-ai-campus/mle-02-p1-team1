"""캡슐 조회 예제 프로그램의 실행 진입점."""

from pathlib import Path
import sys

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from car_search_rag.common.sql_session import SqlSession
from car_search_rag.car_search.query_examples_service import QueryExamplesService


def main() -> None:
    print(QueryExamplesService(SqlSession()).list_brand_counts())


if __name__ == "__main__":
    main()
