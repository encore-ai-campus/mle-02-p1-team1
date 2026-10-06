from collections.abc import Iterator                                                                                         # aiosql의 지연 조회(Iterator/Generator) 결과 여부 확인용
from contextlib import contextmanager                                                                                        # 트랜잭션과 DB 연결 사용 범위를 관리
import logging                                                                                                               # SQL 실행 내용을 표준 로그로 출력
from pathlib import Path                                                                                                     # 기능별 SQL 파일 경로 처리용
from time import perf_counter                                                                                                # 쿼리 실행 시간을 측정
from unicodedata import combining, east_asian_width                                                              # 한글 등 표 출력 너비 계산
from typing import ClassVar, Self                                                                                            # 공유 클래스 속성과 검증 메서드 반환 타입
import aiosql                                                                                                                # .sql 파일에 정의된 named query를 Python 함수 형태로 로드하는 라이브러리
from aiosql.queries import Queries                                                                                           # aiosql이 SQL 파일에서 생성하는 쿼리 모음 타입
from aiosql.utils import SQLLoadException                                                                                    # 같은 SQL 이름을 중복 등록할 때 나는 aiosql 예외

import psycopg                                                                                                               # PostgreSQL 연결 및 트랜잭션 처리용 드라이버
from pgvector.utils import Vector                                                                                             # SQL 로그에서 벡터 일부 값과 차원을 표시할 타입
from .database_manager import DatabaseManager                                                                                # SQL 실행에 사용할 DB 연결 관리자
from collections.abc import Generator                                                                                        # Generator 타입의 지연 조회 결과 여부 확인용
import os                                                                                                                    # 환경 변수 및 운영체제 관련 설정값 조회용
from langchain_postgres import PGEngine                                                                                      # LangChain에서 PostgreSQL/PGVector 연결 및 테이블 관리를 위한 엔진
from sqlalchemy.engine import make_url                                                                                       # PostgreSQL 연결 문자열을 SQLAlchemy URL 객체로 변환

sql_logger = logging.getLogger("car_search_rag.sql")                                                                           # SQL 로그만 구분해서 설정할 수 있는 이름
SQL_LOG_DIVIDER = "=" * 72                                                                                                    # SQL 본문 위아래에 표시할 구분선


#=========================================================
# DB 연결 위임, SQL 문 및 트랜잭션 관리 
#=========================================================
class SqlSession:                                                                                                             # SQL 파일을 statement ID로 찾아 실행하는 공통 세션
    """SQL mapper를 등록하고 statement ID로 동기식 쿼리를 실행한다.

    생성 시 ``MAPPER_ROOT`` 아래의 ``*.sql`` 파일을 재귀적으로
    찾아 aiosql의 psycopg 어댑터로 등록한다. 파일명이 namespace, SQL 파일의
    ``-- name:`` 값이 statement 이름이다. 조회와 실행은 ``DatabaseManager`` 가
    만든 연결을 사용하며, ``transaction()`` 안에서는 연결 하나를 재사용한다.

    Args:
        camel_case_keys: 조회 결과의 키를 camelCase로 변환할지 여부.
            기본값은 ``True`` 다.
        database_manager: 연결 관리자. 생략하면 ``DatabaseManager`` 를 만든다.
        sql_log_mode: SQL 상세 로그 형식. combined, separate, none 중 선택한다.
        result_log: 반환 데이터를 표로 기록할지 여부. 기본값은 ``False`` 다.
        result_log_limit: 상세 로그에 표시할 최대 행 수. 기본값은 ``100`` 이다.

    Attributes:
        camel_case_keys: 기본값 ``True``. 조회 결과 dict의 snake_case 컬럼명을
            camelCase 키로 만든다. ``False`` 이면 원래 컬럼명을 유지한다.
        database_manager: 연결 생성에 사용할 관리자. 기본 생성되며 주입도 가능하다.
        sql_log_mode: 인스턴스별 SQL 상세 로그 형식. 기본값은 combined다.
        result_log: SQL 상세 로그 모드와 독립적인 결과 표 로그 설정.
        result_log_limit: 상세 로그의 최대 표시 행 수.
        mappers: SQL 파일명(namespace)별 aiosql ``Queries`` 객체.
        mapper_paths: namespace별 원본 SQL 파일 경로.
        MAPPER_ROOT: mapper 파일 검색의 시작 경로인 클래스 속성.

    Example:
        .. code-block:: python

            session = SqlSession()
            rows = session.select_list(
                "cff_caps.select_by_brand", {"brand": "NESPRESSO"}
            )

            original_keys = SqlSession(camel_case_keys=False)
            rows = original_keys.select_list("cff_caps.count_by_brand")

    Note:
        생성할 때 mapper를 등록하지만 DB 연결은 쿼리 실행 시 만든다.
    """

    # 클래스 공통 속성
    MAPPER_ROOT: ClassVar[Path] = Path(__file__).resolve().parents[1]                   # 모든 인스턴스가 공유하는 검색 시작 위치
    SQL_LOG_MODES: ClassVar[tuple[str, ...]] = ("combined", "separate", "none")         # 허용하는 SQL 로그 모드
    RESULT_LOG_COLUMN_WIDTH: ClassVar[int] = 40                                        # 표의 컬럼별 최대 표시 폭
    VECTOR_LOG_PREVIEW_COUNT: ClassVar[int] = 6                                        # 로그에 표시할 벡터 앞부분 값 개수
    VECTOR_LOG_SEQUENCE_MIN_LENGTH: ClassVar[int] = 32                                 # 숫자 시퀀스를 벡터로 취급할 최소 길이

    # 인스턴스 속성
    camel_case_keys: bool                           # 조회 결과 camelCase 변환 여부
    database_manager: DatabaseManager               # DB 연결 관리자
    result_log: bool                             # 반환 데이터 상세 로그 여부
    result_log_limit: int                       # 상세 로그 최대 표시 행 수
    mappers: dict[str, Queries]                     # namespace별 SQL mapper
    mapper_paths: dict[str, Path]                   # namespace별 SQL 파일 경로
    _active_connection: psycopg.Connection | None   # 트랜잭션 중 재사용할 연결
    _pg_engine: PGEngine | None                     # PGVector 엔진 지연 생성 캐시
    _sql_log_mode: str                              # 검증된 SQL 로그 모드

    #=========================================================
    # 생성자
    #=========================================================
    def __init__(
        self,
        camel_case_keys: bool = True,
        database_manager: DatabaseManager | None = None,
        sql_log_mode: str = "combined",
        result_log: bool = False,
        result_log_limit: int = 100,
    ) -> None:
        """연결 관리자와 SQL/결과 로그 옵션을 설정하고 mapper를 등록한다.

        ``result_log`` 는 ``sql_log_mode`` 와 독립적으로 동작한다.
        ``result_log_limit`` 는 0 이상이며, 0이면 행 상세를 출력하지 않는다.
        """
        self.camel_case_keys = camel_case_keys                                                                                  # 조회 결과 컬럼명 변환 여부
        self.database_manager = database_manager if database_manager is not None else DatabaseManager()                         # DB 연결 관리자
        self.mappers: dict[str, Queries] = {}                                                                                   # namespace별 SQL mapper
        self.mapper_paths: dict[str, Path] = {}                                                                                 # namespace별 SQL 파일 경로
        self._active_connection: psycopg.Connection | None = None                                                               # 트랜잭션 중 재사용할 연결
        self._pg_engine: PGEngine | None = None                                                                                 # PGVector 엔진 지연 생성 캐시
        self.sql_log_mode = sql_log_mode                                                                                        # setter에서 로그 모드 검증
        if isinstance(result_log_limit, bool) or not isinstance(result_log_limit, int) or result_log_limit < 0:
            raise ValueError("result_log_limit must be a non-negative integer")
        self.result_log = result_log                     # SQL 상세 로그와 독립적으로 결과 데이터 출력
        self.result_log_limit = result_log_limit         # 출력할 최대 행 수
        self.register_mappers()                                                                                                 # SQL mapper를 명시적으로 등록

    #=========================================================
    # SQL 로그 모드 조회
    #=========================================================
    @property
    def sql_log_mode(self) -> str:
        return self._sql_log_mode

    #=========================================================
    # SQL 로그 모드 설정 및 검증
    #=========================================================
    @sql_log_mode.setter
    def sql_log_mode(self, value: str) -> None:
        if value not in self.SQL_LOG_MODES:
            raise ValueError("sql_log_mode must be one of: combined, separate, none")
        self._sql_log_mode = value

    #=========================================================
    # SQL 상세 로그 출력
    #=========================================================
    @staticmethod
    def _format_vector_preview(values: list | tuple, dimension: int) -> str:
        """벡터 앞부분만 표시할 로그 문자열을 만든다."""
        preview = ", ".join(f"{item:.6f}" for item in values[:SqlSession.VECTOR_LOG_PREVIEW_COUNT])
        if dimension > SqlSession.VECTOR_LOG_PREVIEW_COUNT:
            preview += ", ..."
        return f"<VECTOR [{preview}] dimension={dimension}>"

    @staticmethod
    def _sanitize_log_value(value):
        """로그용 복사본에서 벡터의 앞부분과 차원만 표시한다."""
        if isinstance(value, Vector):
            dimension = value.dimensions()
            try:
                return SqlSession._format_vector_preview(value.to_list(), dimension)
            except Exception:
                return f"<VECTOR dimension={dimension}>"
        if isinstance(value, dict):
            return {key: SqlSession._sanitize_log_value(item) for key, item in value.items()}
        if isinstance(value, list):
            if len(value) >= SqlSession.VECTOR_LOG_SEQUENCE_MIN_LENGTH and all(
                isinstance(item, (int, float)) and not isinstance(item, bool) for item in value
            ):
                return SqlSession._format_vector_preview(value, len(value))
            return [SqlSession._sanitize_log_value(item) for item in value]
        if isinstance(value, tuple):
            if len(value) >= SqlSession.VECTOR_LOG_SEQUENCE_MIN_LENGTH and all(
                isinstance(item, (int, float)) and not isinstance(item, bool) for item in value
            ):
                return SqlSession._format_vector_preview(value, len(value))
            return tuple(SqlSession._sanitize_log_value(item) for item in value)
        return value

    def _log_batch_query(self, statement_id: str, sql: str, parameters_list: list[dict]) -> None:
        """배치 SQL과 앞의 최대 100건 로그용 파라미터를 실행 전에 기록한다."""
        if not sql_logger.isEnabledFor(logging.INFO):
            return

        total = len(parameters_list)
        log_limit = 100
        lines = [
            f"BATCH QUERY [{statement_id}]",
            SQL_LOG_DIVIDER,
            sql,
            SQL_LOG_DIVIDER,
            f"BATCH PARAMS rows={total}",
        ]
        for index, parameters in enumerate(parameters_list[:log_limit], start=1):
            try:
                log_parameters = repr(self._sanitize_log_value(parameters))
            except Exception as exc:
                # 표시용 변환 오류가 DB 실행을 막지 않도록 원본 파라미터는 로그에도 출력하지 않는다.
                sql_logger.warning("배치 로그 파라미터 변환 실패 [%s] row=%d: %s", statement_id, index, type(exc).__name__)
                log_parameters = "<PARAMS unavailable>"
            lines.extend(("", f"[{index}/{total}]", log_parameters))

        omitted_count = total - log_limit
        if omitted_count > 0:
            lines.extend(("", "...", f"생략된 배치 파라미터: {omitted_count}건"))

        sql_logger.info("%s", "\n".join(lines))

    def _log_query(self, statement_id: str, sql: str, parameters, connection: psycopg.Connection, *, force: bool = False, full_vector_sql: bool = False) -> None:
        """실행과 별개로 SQL 상세 로그를 출력한다."""
        # execute()는 none 모드에서도 QUERY를 combined 형식으로 표시한다.
        log_mode = "combined" if force and self.sql_log_mode == "none" else self.sql_log_mode
        if log_mode == "none" or not sql_logger.isEnabledFor(logging.INFO):
            return

        try:
            log_parameters = self._sanitize_log_value(parameters or {})
        except Exception as exc:
            # 로그 변환 실패가 실제 쿼리 실행에 영향을 주지 않도록 원본 파라미터를 출력하지 않는다.
            sql_logger.warning("SQL 로그 파라미터 변환 실패 [%s]: %s", statement_id, type(exc).__name__)
            log_parameters = {}

        if log_mode == "combined":
            try:
                # select_list()만 full_vector_sql=True로 호출해 실제 embedding 전체를 QUERY에 남긴다.
                # 복사 가능한 SQL로 EXPLAIN 등을 확인하기 위함이며 PARAMS는 기존 sanitize 미리보기를 유지한다.
                # execute()/execute_many()는 이 옵션을 쓰지 않아 변경/배치 SQL 로그에 영향이 없다.
                render_parameters = parameters if full_vector_sql else log_parameters
                with psycopg.ClientCursor(connection) as cursor:
                    rendered_sql = cursor.mogrify(sql, render_parameters or None)
            except Exception as exc:
                # 로그 렌더링만 실패해도 실행에는 영향을 주지 않고 SQL 원문으로 되돌린다.
                sql_logger.warning("SQL 로그 렌더링 실패 [%s]: %s", statement_id, type(exc).__name__)
            else:
                sql_logger.info(
                    "QUERY [%s]\n%s\n%s\n%s\nPARAMS %r",
                    statement_id, SQL_LOG_DIVIDER, rendered_sql, SQL_LOG_DIVIDER, log_parameters,
                )
                return

        sql_logger.info(
            "QUERY [%s]\n%s\n%s\n%s\nPARAMS %r",
            statement_id, SQL_LOG_DIVIDER, sql, SQL_LOG_DIVIDER, log_parameters,
        )

    #=========================================================
    # 검색 범위의 SQL mapper 파일을 현재 세션에 등록한다.
    #=========================================================
    def register_mappers(self) -> Self:                                                                                       # mapper SQL 파일을 찾아 인스턴스 필드에 등록
        """검색 범위의 SQL mapper 파일을 현재 세션에 등록한다.

        ``MAPPER_ROOT`` 아래의 ``*.sql`` 파일을 재귀적으로 검색한다.
        파일 stem을 namespace로 삼고 UTF-8 SQL을
        ``aiosql.from_path(..., "psycopg")`` 로 로드한다.
        ``SqlSession.__init__()`` 에서 필드를 초기화한 뒤 명시적으로 호출한다.

        Returns:
            mapper 등록을 마친 현재 ``SqlSession`` 인스턴스.

        Raises:
            ValueError: namespace가 중복되거나 SQLLoadException이 발생한 경우.
                오류 메시지에 관련 SQL 파일 경로를 포함한다.

        Example:
            .. code-block:: python

                session = SqlSession()
                mapper = session.mappers["cff_caps"]

        Note:
            기존 mapper를 지우지 않으므로 같은 세션에서 다시 호출하면 등록된
            namespace와 충돌할 수 있다.
        """
        mapper_files = sorted(self.MAPPER_ROOT.rglob("*.sql"))                                                                # MAPPER_ROOT 아래 모든 하위 폴더의 SQL mapper 파일 조회
        for path in mapper_files:                                                                                             # 찾은 SQL 파일을 하나씩 등록
            namespace = path.stem                                                                                             # document.sql → document
            if namespace in self.mappers:                                                                                     # 서로 다른 파일의 이름이 같으면 충돌
                raise ValueError(                                                                                             # 충돌한 두 파일 경로를 함께 알림
                    f"Duplicate SQL mapper namespace '{namespace}': "
                    f"'{self.mapper_paths[namespace]}' and '{path}'"
                )
            try:                                                                                                              # SQL 파일 안의 -- name: 정의를 aiosql 함수로 변환
                self.mappers[namespace] = aiosql.from_path(                                                                   # namespace로 등록
                    path, "psycopg", mandatory_parameters=False, encoding="utf-8"
                )
            except SQLLoadException as exc:                                                                                   # 같은 파일 안의 statement 이름 중복 등
                raise ValueError(f"Duplicate or conflicting SQL statement in '{path}': {exc}") from exc                       # 파일 정보 추가
            self.mapper_paths[namespace] = path                                                                               # 오류 메시지에서 사용할 원본 경로 저장
        return self                                                                                                           # 등록을 마친 세션 반환

    #=========================================================
    # statement ID로 실행할 SQL 함수 찾기
    #=========================================================
    def _query(self, statement_id: str):                                                                                      # namespace.statement 이름을 실행 함수로 변환
        """``namespace.statement`` ID에 해당하는 aiosql 함수를 찾는다.

        Args:
            statement_id: 예: ``"document.select_documents"``.

        Returns:
            등록된 aiosql 쿼리 함수.

        Raises:
            ValueError: ID 형식이 잘못된 경우.
            LookupError: namespace 또는 statement가 없는 경우.
        """
        # 'document.select_documents' 문자열을 namespace('document'), separator('.'), query_id('select_documents')로 분할
        namespace, separator, query_id = statement_id.partition(".")                                                          # 첫 번째 점을 기준으로 분리
        
        # 구분자가 없거나, 네임스페이스/쿼리ID가 비어있거나, 쿼리ID 내에 점(.)이 더 포함된 경우 검증 오류 처리
        if not separator or not namespace or not query_id or "." in query_id:                                                 # 정확히 두 부분인지 확인
            raise ValueError("statement_id must be 'namespace.query_id'")                                                     # 잘못된 호출 형식 알림
        
        mapper = self.mappers.get(namespace)                                                                                  # 파일명에 해당하는 mapper 찾기
        if mapper is None:                                                                                                    # 해당 이름의 SQL 파일이 없는 경우
            raise LookupError(f"SQL mapper namespace '{namespace}' not found for '{statement_id}'")                           # 누락 파일명 알림
        if query_id not in mapper.available_queries:                                                                          # SQL 파일에 -- name: 정의가 없는 경우
            raise LookupError(                                                                                                # 어떤 파일에서 어떤 statement를 못 찾았는지 알림
                f"SQL statement '{query_id}' not found in mapper '{namespace}' "
                f"({self.mapper_paths[namespace]})"
            )
        return getattr(mapper, query_id)                                                                                      # aiosql이 만든 실행 함수를 반환

    #=========================================================
    # 트랜잭션 중이면 기존 연결, 아니면 새 연결 제공
    #=========================================================
    # _connection()은 SQL 실행부의 단일 진입점이다.
    # 트랜잭션 중이면 이미 빌린 연결을 내주고, 그 외에는 DatabaseManager.connect()를 통해 pool에서 대여한다.
    # 후자의 with 블록 종료는 physical connection close가 아니라 pool 반환이다.
    @contextmanager                                                                                                           # with 블록 안의 연결 사용 방식을 공통 처리
    def _connection(self) -> Generator[psycopg.Connection]:                                                                   # 트랜잭션 연결 또는 독립 연결 제공
        if self._active_connection is not None:                                                                               # 활성 트랜잭션이면 그 연결을 그대로 공유
            yield self._active_connection                                                                                     # 같은 연결을 재사용하고 여기서 닫지 않음
        else:                                                                                                                 # 트랜잭션 밖에서는
            with self.database_manager.connect(camel_case_keys=self.camel_case_keys) as connection:  # pool 대여 후 블록 종료 시 반환
                yield connection                                                                                              # 사용 후 연결 컨텍스트가 정리

    # 사용법: car_search/transaction_sample.sql의 쿼리를 같은 작업으로 묶는다.
    # sql_session = SqlSession()
    # with sql_session.transaction():
    #     sql_session.execute("transaction_demo.create_temp_table")
    #     sql_session.execute("transaction_demo.insert_item", {"item_id": 1, "item_name": "첫 항목"})
    #     rows = sql_session.select_list("transaction_demo.select_items")
    # with 블록을 정상적으로 나오면 COMMIT, 예외가 밖으로 나가면 ROLLBACK한다.
    # 오류를 처리할 때는 try/except를 with 바깥에 둔다. 블록 안에서 오류를 삼키면 COMMIT된다.
    # SQL 이름은 'mapper 파일명.쿼리 이름'이며, _connection()은 내부에서 자동 호출된다.
    # 전체 실행 예제: car_search/transaction_sample.py
    @contextmanager                                                                                                           # with sql_session.transaction() 형태 지원
    def transaction(self) -> Generator[Self]:                                                                                 # 여러 SQL을 하나의 연결과 작업 단위로 실행
        """여러 mapper 호출을 하나의 PostgreSQL 트랜잭션으로 묶는다.

        블록 진입 때 pool에서 연결 하나를 대여하고 블록 안의 ``select_list()``,
        ``select_one()``, ``execute()``가 같은 연결을 공유한다. 정상 종료는 commit,
        예외는 rollback하며, 마지막에는 physical connection을 닫지 않고 pool에 반환한다.

        Yields:
            현재 ``SqlSession`` 인스턴스.

        Raises:
            RuntimeError: 같은 세션에서 이미 트랜잭션이 활성화된 경우.
            BaseException: 블록에서 발생한 예외를 rollback 후 다시 전파한다.

        Example:
            .. code-block:: python

                session = SqlSession()
                with session.transaction():
                    session.execute("transaction_demo.create_temp_table")
                    session.execute(
                        "transaction_demo.insert_item",
                        {"item_id": 1, "item_name": "첫 항목"},
                    )

        Note:
            중첩 트랜잭션과 SAVEPOINT는 제공하지 않는다. 블록 내부에서 예외를
            처리하고 정상 종료하면 commit된다. ``camel_case_keys`` 옵션은 이
            트랜잭션 연결의 row factory에도 적용된다.
        """
        if self._active_connection is not None:                                                                               # 중첩 트랜잭션은 지원하지 않음
            raise RuntimeError("이미 Transaction이 실행 중입니다.")                                                               # 중첩 사용을 명확히 알림
        # transaction 전체가 하나의 pool lease 안에 있어 중간에 connection이 바뀌지 않는다.
        # 이 context 종료가 pool 반환을 담당하므로 여기서 connection.close()를 직접 호출하지 않는다.
        with self.database_manager.connect(camel_case_keys=self.camel_case_keys) as connection:
            self._active_connection = connection
            try:
                try:
                    yield self
                except BaseException:
                    # 실패한 작업은 되돌리고 예외는 호출자에게 전파한 뒤 pool context가 연결을 반환한다.
                    connection.rollback()
                    sql_logger.info("TRANSACTION ROLLBACK")
                    raise
                else:
                    # 모든 SQL이 성공한 경우에만 확정하고, 다음으로 바깥 pool context가 연결을 반환한다.
                    connection.commit()
                    sql_logger.info("TRANSACTION COMMIT")
            finally:
                self._active_connection = None

    #=========================================================
    # 반환 데이터 상세 로그 출력
    #=========================================================
    @staticmethod
    def _display_width(value: str) -> int:
        """터미널 표시 폭을 계산한다. 한글 전각 문자는 두 칸으로 센다."""
        return sum(0 if combining(char) else 2 if east_asian_width(char) in ("F", "W") else 1 for char in value)


    #=========================================================
    # 결과값을 표 출력용으로 변환(컬럼)
    #=========================================================
    @classmethod
    def _format_result_cell(cls, value) -> str:
        """표시용 값만 문자열로 바꾸고 긴 값은 컬럼 폭에 맞게 줄인다."""
        try:
            text = "NULL" if value is None else str(value)
        except Exception:
            text = repr(value)
        text = text.replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
        if cls._display_width(text) <= cls.RESULT_LOG_COLUMN_WIDTH:
            return text
        width = 0
        shortened = []
        for char in text:
            char_width = cls._display_width(char)
            if width + char_width > cls.RESULT_LOG_COLUMN_WIDTH - 3:
                break
            shortened.append(char)
            width += char_width
        return "".join(shortened) + "..."

    #=========================================================
    # 결과값을 표 출력용으로 변환(테이블)
    #=========================================================
    @classmethod
    def _format_result_table(cls, rows: list) -> str:
        """반환된 행을 원본 변경 없이 한글 표시 폭을 고려한 ASCII 표로 만든다."""
        table_rows = rows if all(isinstance(row, dict) for row in rows) else [{"value": row} for row in rows]
        columns = list(dict.fromkeys(key for row in table_rows for key in row))
        if not columns:
            columns = ["value"]
        headers = [cls._format_result_cell(column) for column in columns]
        cells = [[cls._format_result_cell(row.get(column)) for column in columns] for row in table_rows]
        widths = [max(cls._display_width(cell) for cell in (header, *(row[index] for row in cells)))
                  for index, header in enumerate(headers)]
        border = "+" + "+".join("-" * (width + 2) for width in widths) + "+"

        def table_line(values: list[str]) -> str:
            return "| " + " | ".join(
                value + " " * (width - cls._display_width(value))
                for value, width in zip(values, widths)
            ) + " |"

        return "\n".join([border, table_line(headers), border,
                          *(table_line(row) for row in cells), border])
    
    
    #=========================================================
    # SQL 실행 결과를 로그로 출력
    #=========================================================
    def _log_result_data(self, statement_id: str, result) -> None:
        """설정된 경우 반환 데이터를 최대 지정 행 수까지 한 번의 INFO 로그로 출력한다."""
        if not self.result_log or not sql_logger.isEnabledFor(logging.INFO) or result is None:
            return
        if isinstance(result, dict):
            rows = [result]
        elif isinstance(result, list):
            rows = result
        else:
            sql_logger.info("RESULT DATA [%s] %r", statement_id, result)  # rowcount 등 스칼라 반환값
            return
        if not rows:
            sql_logger.info("RESULT DATA [%s] no rows", statement_id)
            return
        shown = rows[: self.result_log_limit]
        if shown:
            sql_logger.info("RESULT DATA [%s]\n%s", statement_id, self._format_result_table(shown))
        else:
            sql_logger.info("RESULT DATA [%s] no rows shown", statement_id)
        if len(rows) > self.result_log_limit:
            sql_logger.info(
                "RESULT DATA truncated: showing %d of %d rows",
                self.result_log_limit,
                len(rows),
            )

    
    #=========================================================
    # SELECT 결과를 리스트로 반환
    #=========================================================
    def select_list(self, statement_id: str, parameters=None) -> list[dict]:                                                   
        """mapper SELECT를 실행하고 모든 결과 행을 dict 목록으로 반환한다.

        트랜잭션 밖에서는 DatabaseManager pool에서 연결을 빌려 전체 fetch 후 반환한다.
        트랜잭션 안에서는 이미 대여한 연결을 재사용한다. 성능 로그는 연결 대여,
        SQL 로그 렌더링, 실제 실행 및 fetch, 전체 시간을 구분한다.

        full_vector_sql=True는 이 SELECT 로그에만 적용되어 QUERY 본문에 원본
        embedding 전체를 렌더링하고, PARAMS에는 기존 축약 미리보기를 남긴다.
        변경 SQL과 배치 SQL의 로그 방식은 그대로 유지한다.
        """
        query = self._query(statement_id)                                                                                     # 실행할 쿼리 매핑 함수 조회
        started = perf_counter()  # select_list 진입부터 결과 로깅까지의 기존 전체 시간
        with self._connection() as connection:  # transaction 연결 또는 pool 대여 연결
            connected = perf_counter()
            # pool warm-up 이후에는 대개 준비된 연결을 빌리는 시간이며, SQL 로그/조회는 아직 포함하지 않는다.
            connect_ms = (connected - started) * 1000
            sql_log_started = connected
            # 조회 본문에만 원본 embedding을 렌더링해 전체 벡터를 남긴다.
            # PARAMS는 기존 sanitize 미리보기이며, 변경/배치 SQL의 로깅 동작에는 적용하지 않는다.
            self._log_query(statement_id, query.sql, parameters, connection, full_vector_sql=True)                                # 조회 QUERY는 원본 바인딩으로 렌더링
            # SQL과 파라미터의 로그용 렌더링(mogrify 포함) 시간만 측정한다.
            sql_log_ms = (perf_counter() - sql_log_started) * 1000
            # 커넥션이 열려 있는 상태에서 지연 조회(Iterator) 결과를 list로 완전히 평가(eval)하여 객체로 확정
            query_fetch_started = perf_counter()
            # 서버 실행, 왕복/전송, psycopg decode, aiosql 처리와 모든 결과 fetch를 포함한다.
            rows = list(query(connection, **(parameters or {})))                                                              # 연결이 닫히기 전에 결과를 모두 읽음
            query_fetch_ms = (perf_counter() - query_fetch_started) * 1000
        self._log_result_data(statement_id, rows)  # 설정된 경우 조회 결과를 표로 출력
        # result_log 출력도 포함해 select_list의 기존 elapsed_ms 의미를 유지한다.
        total_ms = (perf_counter() - started) * 1000
        sql_logger.info(
            "RESULT [%s] rows=%d connect_ms=%.1f sql_log_ms=%.1f query_fetch_ms=%.1f total_ms=%.1f",
            statement_id, len(rows), connect_ms, sql_log_ms, query_fetch_ms, total_ms,
        )
        return rows                                                                                                           # 조회 결과 반환

    
    #=========================================================
    # SELECT 결과의 첫 행 반환 1건 조회용
    #=========================================================
    def select_one(self, statement_id: str, parameters=None) -> dict | None:                                                  
        """mapper 조회 결과의 첫 행 또는 ``None`` 을 반환한다.

        ``select_list()`` 를 호출하므로 쿼리의 모든 행을 읽은 뒤 첫 행을 고른다.

        Args:
            statement_id: ``namespace.statement`` 형식의 mapper ID.
            parameters: SQL에 전달할 이름 있는 파라미터의 매핑. ``None`` 이면
                빈 매핑을 전달한다.

        Returns:
            첫 행의 dict 또는 조회 결과가 없을 때 ``None``. dict 키는
            ``camel_case_keys`` 설정을 따른다.

        Raises:
            ValueError: statement ID 형식이 잘못된 경우.
            LookupError: namespace 또는 statement가 없는 경우.
            Exception: 연결 또는 SQL 실행 중 발생한 예외를 전파한다.

        Example:
            .. code-block:: python

                row = session.select_one(
                    "cff_caps.select_by_brand", {"brand": "NESPRESSO"}
                )

        Note:
            데이터베이스에 ``LIMIT 1`` 을 자동 추가하지 않는다.
        """
        rows = self.select_list(statement_id, parameters)                                                                     # select_list를 재활용하여 전체 결과 수집
        return rows[0] if rows else None                                                                                      # 결과 리스트에 행이 존재하면 첫번째 행 반환, 없으면 None 반환


    #=========================================================
    # INSERT, UPDATE, DELETE 등 변경 SQL 실행
    #=========================================================
    def execute(self, statement_id: str, parameters=None):                                                                    
        """mapper의 변경 SQL 또는 기타 SQL 명령을 실행한다.

        aiosql이 지연 ``Iterator`` 를 반환하면 연결이 열려 있을 때 목록으로
        모두 읽는다. 그 밖의 결과는 aiosql의 반환값을 그대로 돌려준다.

        ``result_log=True`` 이면 반환 dict/list는 최대 ``result_log_limit`` 행까지 표로 출력한다.

        Args:
            statement_id: ``namespace.statement`` 형식의 mapper ID.
                변경 명령은 SQL 파일에서 ``-- name: insert_item!`` 처럼 정의한다.
            parameters: SQL에 전달할 이름 있는 파라미터의 매핑. ``None`` 이면
                빈 매핑을 전달한다.

        Returns:
            지연 ``Iterator`` 이면 list, 그 외에는 aiosql이 반환한 값.

        Raises:
            ValueError: statement ID 형식이 잘못된 경우.
            LookupError: namespace 또는 statement가 없는 경우.
            Exception: 연결 또는 SQL 실행 중 발생한 예외를 전파한다.

        Example:
            .. code-block:: python

                with session.transaction():
                    session.execute("transaction_demo.create_temp_table")
                    session.execute(
                        "transaction_demo.insert_item",
                        {"item_id": 1, "item_name": "첫 항목"},
                    )

        Note:
            트랜잭션 밖에서는 호출마다 별도 연결을 사용한다. 결과 dict가
            반환되는 SQL이라면 키는 연결의 ``camel_case_keys`` 설정을 따른다.
        """
        query = self._query(statement_id)                                                                                     # 실행할 쿼리 매핑 함수 조회
        started = perf_counter()                                                                                              # DB 연결과 명령 실행 시간 측정 시작
        with self._connection() as connection:                                                                                # 트랜잭션 안에서는 같은 연결 재사용
            self._log_query(statement_id, query.sql, parameters, connection, force=True)                                          # none 모드에서도 변경 SQL 로그를 표시하고 바인딩 실행은 유지
            result = query(connection, **(parameters or {}))                                                                  # SQL 명령 실행
            
            # RETURNING 구문 등으로 인해 결과가 Iterator(지연 결과)로 반환된 경우,
            # 커넥션이 닫히기 전에 list로 소진(consume)하여 반환하고, 일반 반환값은 그대로 반환
            result = list(result) if isinstance(result, Iterator) else result                                                 # 지연 결과만 리스트로 변환
        self._log_result_data(statement_id, result)  # 반환 데이터가 있으면 타입에 맞게 출력
        sql_logger.info("DONE [%s] elapsed_ms=%.1f", statement_id, (perf_counter() - started) * 1000)                         # 완료 시간 기록
        return result                                                                                                         # SQL 실행 결과 반환


    #=========================================================
    # INSERT, UPDATE, DELETE Batch 실행
    #=========================================================
    def execute_many(self, statement_id: str, parameters_list: list[dict]):
        """같은 변경 SQL을 여러 파라미터에 적용해 배치 실행한다.

        ``execute()`` 는 파라미터 한 건으로 SQL을 한 번 실행하고,
        ``execute_many()`` 는 INSERT·UPDATE·DELETE 등에 같은 SQL을 여러 건 적용한다.
        빈 목록이면 연결을 열지 않고 0을 반환한다. 그 외에는
        ``cursor.executemany(query.sql, parameters_list)`` 로 실행한다.

        Args:
            statement_id: ``namespace.statement`` 형식의 mapper ID.
                예: ``"coffee_search.insert_machine_detail"``.
            parameters_list: SQL의 이름 있는 파라미터에 대응하는 dict 목록.
                각 dict가 한 번의 SQL 실행에 사용할 값이다.

        Returns:
            빈 목록이면 0, 그 외에는 ``cursor.rowcount`` 값.

        Raises:
            ValueError: statement ID 형식이 잘못된 경우.
            LookupError: namespace 또는 statement가 없는 경우.
            Exception: 연결 또는 배치 SQL 실행 중 발생한 예외를 전파한다.

        Example:
            .. code-block:: python

                parameters_list = [
                    {
                        "CFF_MACH_ID": machine_id,
                        "PAGE_NO": "1",
                        "TEXT": "첫 번째 내용",
                        "EMBEDDING": Vector(embeddings[0]),
                        "USER_ID": user_id,
                    },
                    {
                        "CFF_MACH_ID": machine_id,
                        "PAGE_NO": "2",
                        "TEXT": "두 번째 내용",
                        "EMBEDDING": Vector(embeddings[1]),
                        "USER_ID": user_id,
                    },
                ]

                with session.transaction():
                    session.execute_many(
                        "coffee_search.insert_machine_detail",
                        parameters_list,
                    )

        Note:
            ``transaction()`` 안에서는 기존 연결을 재사용하고 정상 종료 시 COMMIT,
            예외가 전파되면 ROLLBACK한다. 블록 밖에서는 일반 연결 처리 방식을 따른다.
            INFO 로그가 활성화되면 실행 전에 ``BATCH QUERY`` 와 모든 건의
            ``BATCH PARAMS`` 를, 실행 후 ``BATCH DONE`` 건수·시간을 기록한다.
            Vector 값은 로그에서만 앞부분으로 축약하며 DB에는 원본
            ``parameters_list`` 를 그대로 전달한다.
        """

        # 실행할 SQL mapper 조회
        query = self._query(statement_id)

        # Batch 데이터가 없으면 실행하지 않음
        if not parameters_list:
            return 0

        started = perf_counter()

        # Transaction 안이면 기존 Connection 재사용
        with self._connection() as connection:

            # 실제 Batch 실행
            with connection.cursor() as cursor:

                self._log_batch_query(statement_id, query.sql, parameters_list)                                                # 원본과 분리한 표시용 파라미터 전건 로그

                cursor.executemany(
                    query.sql,
                    parameters_list
                )

                row_count = cursor.rowcount

        sql_logger.info(
            "BATCH DONE [%s] rows=%d elapsed_ms=%.1f",
            statement_id,
            len(parameters_list),
            (perf_counter() - started) * 1000
        )

        return row_count
    
    
    #=========================================================
    # PGVector용 DB 엔진 생성 및 반환
    #=========================================================
    def get_pg_engine(self) -> PGEngine:
        """``DB_URL`` 로 PGVector용 ``PGEngine`` 을 지연 생성하고 재사용한다.

        URL의 드라이버를 ``postgresql+asyncpg`` 로 바꿔 엔진을 만든다. 생성한
        엔진은 세션의 ``_pg_engine`` 에 보관해 다음 호출부터 같은 객체를 돌려준다.

        Returns:
            현재 세션에서 재사용하는 ``langchain_postgres.PGEngine``.

        Raises:
            ValueError: ``DB_URL`` 환경변수가 비어 있는 경우.

        Example:
            .. code-block:: python

                session = SqlSession()
                engine = session.get_pg_engine()

        Note:
            이 엔진은 psycopg ``DatabaseManager`` 연결과 별개로 만든다.
            ``camel_case_keys`` row factory 설정은 이 엔진에 적용되지 않는다.
        """
        if self._pg_engine is None:
            db_url = os.getenv("DB_URL")
            if not db_url:
                raise ValueError("DB_URL is required to create a PGEngine")
            async_url = make_url(db_url).set(drivername="postgresql+asyncpg")
            self._pg_engine = PGEngine.from_connection_string(async_url)
        return self._pg_engine
