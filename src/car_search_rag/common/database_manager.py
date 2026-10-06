from dotenv import load_dotenv                                                        # .env 파일의 환경변수를 불러오는 함수 가져오기
import logging
import psycopg                                                                        # PostgreSQL 연결에 사용하는 psycopg3
from psycopg.rows import RowMaker, dict_row, no_result                                                     # 조회 결과를 컬럼명으로 접근할 수 있는 dict로 반환
from pgvector.psycopg import register_vector                                         # 같은 PostgreSQL 연결에 pgvector 타입 등록
import os                                                                             # DB_URL 환경변수 읽기
from collections.abc import Sequence
from contextlib import contextmanager
from threading import RLock
from typing import Any                                                                # 연결 객체 타입 지정
from psycopg_pool import ConnectionPool

db_logger = logging.getLogger("car_search_rag.database")


def _configure_connection(connection: psycopg.Connection) -> None:
    """새 physical connection에 pgvector 어댑터를 등록하고 idle 상태로 둔다."""
    # ConnectionPool이 새 PostgreSQL 연결을 만들었을 때만 호출되는 callback이다.
    # SELECT마다 반복하지 않고 연결별로 한 번 등록해, 이후 pool 대여 때 그대로 사용한다.
    register_vector(connection)
    # pgvector 등록 과정의 catalog 조회가 연 transaction을 정리한 뒤 pool에 넣는다.
    connection.commit()


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
    """DatabaseManager는 psycopg connection pool을 관리하고 대여한 연결을 제공한다.

    pool은 생성자에서 열지 않는다. Streamlit resource 초기화가 warmup()을
    호출하거나 첫 connect()가 요청될 때 필요한 row_factory pool을 만든다.
    각 pool은 min_size physical connection과 pgvector adapter를 준비하고,
    이후 호출은 연결을 새로 만들지 않고 대여/반환한다.

    Args:
        connection: 기존 호출 호환을 위한 초기 연결 참조.

    Attributes:
        connection: 가장 최근 대여된 연결 참조. pool 자체는 _pools가 관리한다.
    """


    # 인스턴스 속성
    connection: Any                              # 마지막으로 생성한 DB 연결

    def __init__(self, connection: Any = None) -> None:
        load_dotenv()                                                                 # DB_URL 등을 .env에서 읽음
        self.connection = connection                                                  # 마지막으로 생성한 DB 연결
        # camelCase/snake_case row_factory별 pool을 manager 생명주기 동안 보관한다.
        self._pools: dict[bool, ConnectionPool] = {}
        self._pool_lock = RLock()  # 동시 Streamlit 요청이 같은 pool을 중복 생성하지 않게 보호


    def _get_pool(self, camel_case_keys: bool) -> ConnectionPool:
        """요청한 row_factory에 맞는 pool을 처음 만들고 이후 계속 재사용한다."""
        with self._pool_lock:
            pool = self._pools.get(camel_case_keys)
            if pool is not None:
                # 매 SELECT나 Streamlit rerun마다 pool을 새로 만들지 않는다.
                return pool

            # import나 SqlSession 생성만으로 DB에 접속하지 않고 실제 warm-up/조회 시 생성한다.
            min_size = int(os.getenv("DB_POOL_MIN_SIZE", "1"))
            max_size = int(os.getenv("DB_POOL_MAX_SIZE", "5"))
            if min_size < 0 or max_size < 1 or min_size > max_size:
                raise ValueError("DB_POOL_MIN_SIZE and DB_POOL_MAX_SIZE must satisfy 0 <= min <= max and max >= 1")

            # row_factory는 physical connection 설정이므로 결과 형식별로 pool을 나눈다.
            row_factory = camel_dict_row if camel_case_keys else dict_row
            # Pool 객체는 연결 관리 틀이다. 실제 min_size 연결 준비는 open/wait에서 완료된다.
            pool = ConnectionPool(
                conninfo=os.getenv("DB_URL"),
                min_size=min_size,
                max_size=max_size,
                kwargs={"row_factory": row_factory},
                configure=_configure_connection,  # physical connection마다 최초 생성 때 pgvector 등록
                open=True,
            )
            try:
                pool.wait()  # min_size 연결 및 configure callback 처리가 끝날 때까지 대기
            except Exception:
                # 초기 준비에 실패한 pool은 보관하지 않고 worker/연결을 정리한다.
                pool.close()
                raise
            self._pools[camel_case_keys] = pool
            # DB URL 등 민감정보는 출력하지 않고 pool 크기만 기록한다.
            db_logger.info("DB POOL created min_size=%d max_size=%d", min_size, max_size)
            return pool


    def warmup(self, camel_case_keys: bool = True) -> None:
        """지정 row_factory pool과 최소 연결을 미리 준비한다. 반복 호출해도 안전하다."""
        # Streamlit resource 생성 시 호출해 첫 검색에서 연결 초기화를 기다리지 않게 한다.
        pool = self._get_pool(camel_case_keys)
        pool.wait()  # 이미 준비된 pool이면 즉시 끝나고 min_size 충족도 보장한다.


    @contextmanager
    def connect(self, camel_case_keys: bool = True):
        """요청한 row_factory pool에서 connection을 대여하고 종료 시 반환한다."""
        pool = self._get_pool(camel_case_keys)
        # psycopg.connect()로 매번 새 physical connection을 만들지 않는다.
        # 이 context manager는 블록 종료 때 물리 연결을 닫지 않고 pool에 반환한다.
        with pool.connection() as connection:
            self.connection = connection
            yield connection


    def close(self) -> None:
        """앱 종료 등 명시적인 정리 시 모든 pool을 닫는다."""
        with self._pool_lock:
            pools = list(self._pools.values())
            self._pools.clear()
        for pool in pools:
            pool.close()  # 대여 중인 연결은 반환 시 정리되며 새 대여는 막힌다.
