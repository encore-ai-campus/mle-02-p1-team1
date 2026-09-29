from dotenv import load_dotenv                                                        # .env 파일의 환경변수를 불러오는 함수 가져오기
import psycopg                                                                        # PostgreSQL 연결에 사용하는 psycopg3
from psycopg.rows import RowMaker, dict_row, no_result                                                     # 조회 결과를 컬럼명으로 접근할 수 있는 dict로 반환
from pgvector.psycopg import register_vector                                         # 같은 PostgreSQL 연결에 pgvector 타입 등록
import os                                                                             # DB_URL 환경변수 읽기
from collections.abc import Sequence
from typing import Any                                                                # 연결 객체 타입 지정

def snake_to_camel(name: str) -> str:
    """밑줄로 구분된 컬럼명을 camelCase 문자열로 변환한다.

    Args:
        name: 변환할 컬럼명 또는 SQL 결과 컬럼의 별칭.

    Returns:
        첫 부분은 그대로 두고, 이후 각 부분의 첫 글자를 대문자로 바꾼 이름.

    Example:
        .. code-block:: python

            >>> snake_to_camel("cff_caps_id")
            'cffCapsId'
            >>> snake_to_camel("capsule_count")
            'capsuleCount'
    """
    parts = name.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


def camel_dict_row(cursor: psycopg.Cursor[Any]) -> RowMaker[dict[str, Any]]:
    """psycopg 행을 camelCase 키를 가진 dict로 만드는 row factory를 반환한다.

    커서의 결과 컬럼명을 행 생성 전에 한 번 변환한다. 반환된 RowMaker는 각 행의
    값으로 dict를 직접 생성하며, 이미 생성한 dict를 다시 순회하지 않는다.

    Args:
        cursor: ``description`` 에 결과 컬럼 정보가 들어 있는 psycopg 커서.

    Returns:
        행 값의 시퀀스를 camelCase 키의 dict로 만드는 RowMaker. 결과 컬럼이
        없는 명령에는 psycopg의 ``no_result`` RowMaker를 반환한다.

    Example:
        ``DatabaseManager.connect(camel_case_keys=True)`` 에서 이 함수를
        ``psycopg.connect(..., row_factory=camel_dict_row)`` 에 전달한다.

    Note:
        변환 후 이름이 같은 컬럼이 여러 개면 dict의 동일 키에 마지막 값이 남는다.
    """
    if cursor.description is None:
        return no_result

    columns = [snake_to_camel(column.name) for column in cursor.description]

    def make_row(values: Sequence[Any]) -> dict[str, Any]:
        return dict(zip(columns, values))

    return make_row


#===============================================================================
# DatabaseManager : 데이터베이스 관리 클래스
#===============================================================================
class DatabaseManager:                                                     # PostgreSQL 연결을 생성하고 보관하는 관리자
    """``DB_URL`` 로 PostgreSQL 연결을 만들고 pgvector 타입을 등록한다.

    ``connect()`` 를 호출할 때마다 새 psycopg 연결을 만든다. 연결의 row factory는
    기본적으로 SQL 결과 컬럼명을 camelCase dict 키로 변환하며, 옵션을 끄면
    psycopg의 ``dict_row`` 를 사용한다. 연결 직후 ``register_vector()`` 를 호출한다.
    ``.env`` 는 ``__init__()`` 에서 ``load_dotenv()`` 로 로드한다.

    Args:
        connection: 마지막 연결을 보관할 초기 값. 일반적으로 생략한다.

    Attributes:
        connection: 마지막으로 생성한 연결. 연결 전에는 ``None`` 이다.

    Example:
        .. code-block:: python

            manager = DatabaseManager()
            with manager.connect(camel_case_keys=False) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT cff_caps_id FROM cff_caps LIMIT 1")
                    row = cursor.fetchone()
    """


    # 인스턴스 속성
    connection: Any                              # 마지막으로 생성한 DB 연결

    def __init__(self, connection: Any = None) -> None:
        load_dotenv()                                                                 # DB_URL 등을 .env에서 읽음
        self.connection = connection                                                  # 마지막으로 생성한 DB 연결


    def connect(self, camel_case_keys: bool = True):                                                                # 호출할 때마다 DB 연결을 새로 생성
        """새 PostgreSQL 연결을 만들고 pgvector 어댑터를 등록한다.

        Args:
            camel_case_keys: ``True`` 이면 ``camel_dict_row`` 를, ``False`` 이면
                psycopg의 ``dict_row`` 를 연결의 row factory로 사용한다.

        Returns:
            ``DB_URL`` 에 연결된 psycopg 연결. 호출자가 사용 후 닫아야 한다.

        Raises:
            Exception: 연결 생성 또는 pgvector 등록이 실패하면 원래 예외를
                전파한다. pgvector 등록에 실패한 경우 생성한 연결을 닫는다.

        Example:
            .. code-block:: python

                manager = DatabaseManager()
                with manager.connect() as connection:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT COUNT(*) AS capsule_count FROM cff_caps")
                        count = cursor.fetchone()["capsuleCount"]

        Note:
            각 호출은 새 연결을 생성한다. ``False`` 이면 위 결과 키는
            ``capsule_count`` 가 된다.
        """
        row_factory = camel_dict_row if camel_case_keys else dict_row
        self.connection = psycopg.connect(os.getenv("DB_URL"), row_factory=row_factory)  # 기존 DB_URL로 연결하고 dict 행 사용
        try:
            register_vector(self.connection)                                         # vector 컬럼 조회와 vector 파라미터 전달 지원
        except Exception:
            self.connection.close()                                                  # 타입 등록 실패 시 열린 연결 정리
            raise

        return self.connection                                                        # SqlSession 등 호출자가 연결을 사용하도록 반환

