"""문서 조회 프로그램의 실행 진입점."""

from pathlib import Path
import sys

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from car_search_rag.common.sql_session import SqlSession
from car_search_rag.car_search.document_service import DocumentService


def main() -> None:
    print(DocumentService(SqlSession()).list_documents())


if __name__ == "__main__":
    main()
