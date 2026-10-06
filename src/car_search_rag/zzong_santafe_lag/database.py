"""팀 SQL Mapper의 실행 방식을 재사용해 개인 SQL 파일을 읽습니다."""

# [프로젝트 적용] SQL Mapper Documentation의 SQL/파이썬 분리를 사용합니다.
# [프로젝트 추가] 개인 mapper 경로·연결 변수를 분리합니다.
# import하거나 세션을 만드는 것만으로 테이블 생성·자료 저장은 실행되지 않습니다.

import logging
import os
from pathlib import Path

import aiosql
from aiosql.utils import SQLLoadException
import psycopg
from dotenv import dotenv_values
from pgvector.psycopg import register_vector
from psycopg import sql
from psycopg.rows import dict_row

from car_search_rag.common.sql_session import SqlSession


class PersonalDatabaseManager:
    """개인 연결 문자열을 사용하며 팀 DB_URL과 공통 설정을 변경하지 않습니다."""

    def __init__(self, dsn=None, *, read_only=False):
        """연결 문자열만 보관하고 실제 연결은 SQL 실행 때 엽니다."""
        # [프로젝트 추가] ZZONG_DB_URL만 읽습니다. 팀 DB_URL로 자동 대체하지 않습니다.
        # dotenv_values는 .env를 읽기만 하며 파일이나 환경변수를 변경하지 않습니다.
        # [프로젝트 추가] 폴더 이동 후에도 기존 프로젝트 루트의 .env를 읽습니다.
        project_folder = Path(__file__).resolve().parents[3]
        values = dotenv_values(project_folder / ".env") if dsn is None else {}
        # [프로젝트 추가] 개인 폴더의 .env가 우선합니다. 팀 .env의 값을 수정하지 않습니다.
        if dsn is None:
            values.update(dotenv_values(Path(__file__).resolve().parent / ".env"))
        self._dsn = dsn or os.getenv("ZZONG_DB_URL") or values.get("ZZONG_DB_URL")
        self.read_only = read_only
        self.connection = None

    def connect(self, camel_case_keys=False):
        """Supabase에 연결하고 실제 pgvector 설치 위치를 현재 연결에 등록합니다."""
        if not self._dsn:
            raise ValueError("ZZONG_DB_URL을 먼저 설정하세요. 비밀번호를 채팅에 붙여 넣지 마세요.")
        if camel_case_keys:
            raise ValueError("개인 기록은 snake_case 키를 사용합니다.")
        connection = psycopg.connect(
            self._dsn, row_factory=dict_row, connect_timeout=10,
            sslmode="require", application_name="zzong_santafe_lag",
        )
        try:
            # [프로젝트 추가] Supabase 연결 중계기가 시작 옵션을 반영하지 않을 수 있어
            # 첫 SQL에서 이번 트랜잭션을 읽기 전용으로 지정합니다. 팀 DB 설정은 바꾸지 않습니다.
            if self.read_only:
                connection.execute("SET TRANSACTION READ ONLY")
            # 설치 위치를 읽습니다. 확장·테이블·권한을 만들거나 수정하지 않습니다.
            row = connection.execute(
                "SELECT n.nspname FROM pg_extension e "
                "JOIN pg_namespace n ON n.oid = e.extnamespace WHERE e.extname = 'vector'"
            ).fetchone()
            if row is None:
                raise RuntimeError("pgvector가 없습니다. DBeaver의 확인 SQL로 설치 상태를 확인하세요.")
            # 설치 위치가 extensions/public 중 어디든 현재 연결에서 찾을 수 있게 합니다.
            connection.execute(sql.SQL("SET search_path TO pg_catalog, zzong_santafe_lag, {}").format(
                sql.Identifier(row["nspname"])
            ))
            register_vector(connection)
        except BaseException:
            connection.close()
            raise
        self.connection = connection
        return connection


class PersonalSqlSession(SqlSession):
    """개인 mappers 폴더의 SQL만 등록하고 공통 클래스 설정은 유지합니다."""

    # [프로젝트 추가] 공통 로더의 실제 검색 범위는 src/car_search_rag입니다.
    # 개인 .sql.txt만 읽어 공통 로더의 *.sql 검색에 개인 스크립트가 포함되지 않게 합니다.
    MAPPER_ROOT = Path(__file__).resolve().parent / "mappers"

    def register_mappers(self):
        """개인 .sql.txt 파일을 등록합니다. SQL 실행이나 DB 연결은 하지 않습니다."""
        # [프로젝트 추가] 공통 로더를 바꾸지 않고 개인 파일만 별도 확장자로 읽습니다.
        for path in sorted(self.MAPPER_ROOT.glob("*.sql.txt")):
            namespace = path.name.removesuffix(".sql.txt")
            if namespace in self.mappers:
                raise ValueError(f"개인 SQL 이름이 중복되었습니다: {namespace}")
            try:
                self.mappers[namespace] = aiosql.from_str(
                    path.read_text(encoding="utf-8"), "psycopg", mandatory_parameters=False,
                )
            except SQLLoadException as error:
                raise ValueError(f"개인 SQL 등록을 확인하세요: {path.name}") from error
            self.mapper_paths[namespace] = path
        return self

    def __init__(self, dsn=None, *, read_only=False):
        """기존 필드 이름을 유지하고 개인 연결 관리자를 공통 세션에 전달합니다."""
        super().__init__(
            camel_case_keys=False, database_manager=PersonalDatabaseManager(dsn, read_only=read_only),
            sql_log_mode="none", result_log=False,
        )

    def _log_query(self, statement_id, query_sql, parameters, connection, *, force=False, full_vector_sql=False):
        """SQL 이름만 기록하고 원문·전체 벡터·연결 비밀번호는 출력하지 않습니다."""
        # [프로젝트 추가] 공통 로그를 바꾸지 않고 개인 인스턴스의 로그만 간단히 처리합니다.
        # 최신 공통 세션의 full_vector_sql 인자를 받아도 개인 비밀값·벡터 전체를 출력하지 않습니다.
        logging.getLogger(__name__).debug("개인 SQL 실행: %s", statement_id)

    def _log_batch_query(self, statement_id, query_sql, parameters_list):
        """일괄 저장도 이름·건수만 기록합니다. 전체 글과 벡터는 로그에 남기지 않습니다."""
        logging.getLogger(__name__).debug("개인 일괄 SQL: %s, %d건", statement_id, len(parameters_list))


class ManualRepository:
    """준비된 DB 행을 저장하고 개인 기록을 조회하는 작은 작업 도구입니다."""

    INSERT_NAMES = {
        "documents": "insert_document", "processing_runs": "insert_run",
        "parent_records": "insert_parent", "chunks": "insert_chunk",
        "images": "insert_image", "record_images": "insert_record_image",
    }

    def __init__(self, session=None):
        """세션을 준비합니다. 생성 SQL과 전체 저장은 자동 실행하지 않습니다."""
        self.session = session if session is not None else PersonalSqlSession()

    def list_tables(self):
        """개인 테이블 이름을 읽습니다. 생성 전에는 빈 목록입니다."""
        return self.session.select_list("manual_store.list_tables")

    def connection_report(self):
        """개인 테이블의 건수·용량과 현재 연결 정보를 읽기만 합니다."""
        # [프로젝트 추가] 여러 조회를 같은 연결에서 실행해 연결 대상을 일관되게 확인합니다.
        with self.session.transaction():
            return {
                "connection": self.session.select_one("manual_store.connection_info"),
                "tables": self.session.select_list("manual_store.personal_table_counts"),
                "sizes": self.session.select_list("manual_store.personal_table_sizes"),
            }

    def insert_row(self, table_name, row):
        """컬럼에 맞게 준비한 한 행을 저장합니다. 노트북 기록을 그대로 받지는 않습니다."""
        parameters = self.row_parameters(table_name, row)
        return self.session.execute("manual_store." + self.INSERT_NAMES[table_name], parameters)

    @classmethod
    def row_parameters(cls, table_name, row):
        """한 행의 JSON·벡터를 DB 드라이버가 이해하는 값으로 복사합니다."""
        from psycopg.types.json import Jsonb
        from pgvector.utils import Vector

        if table_name not in cls.INSERT_NAMES:
            raise ValueError("개인 6개 테이블만 지정할 수 있습니다.")
        parameters = dict(row)
        # [프로젝트 적용] 딕셔너리·목록은 JSONB, 벡터는 pgvector 어댑터로 전달합니다.
        # 전체 기록 변환·연결 검증은 full_store_service에서 먼저 수행합니다.
        for key in ("metadata", "review_flags", "settings", "pdf_image_key"):
            if key in parameters:
                parameters[key] = Jsonb(parameters[key])
        if "embedding" in parameters:
            parameters["embedding"] = Vector(parameters["embedding"])
        return parameters

    def insert_rows(self, table_name, rows):
        """같은 개인 테이블의 여러 행을 SQL Mapper의 일괄 실행으로 저장합니다."""
        # [프로젝트 적용] 기존 공통 execute_many를 재사용해 청크마다 왕복하는 시간을 줄입니다.
        if table_name not in self.INSERT_NAMES:
            raise ValueError("개인 6개 테이블만 지정할 수 있습니다.")
        parameters = [self.row_parameters(table_name, row) for row in rows]
        return self.session.execute_many("manual_store." + self.INSERT_NAMES[table_name], parameters)

    def get_parent(self, run_id, record_id):
        """같은 처리 버전의 부모 기록을 출처·각주 정보와 함께 읽습니다."""
        return self.session.select_one(
            "manual_store.get_parent", {"run_id": run_id, "record_id": record_id}
        )

    def get_parent_images(self, run_id, record_id):
        """부모에 연결된 그림의 설명과 파일 경로를 읽습니다."""
        return self.session.select_list(
            "manual_store.get_parent_images", {"run_id": run_id, "record_id": record_id}
        )

    def search_chunks(self, run_id, query_vector, *, model_name, model_revision, limit=5, best_per_parent=False):
        """같은 모델·버전의 질문 벡터로 의미 검색합니다. 기존 결합 검색과는 별개입니다."""
        from pgvector.utils import Vector
        import numpy as np

        # [프로젝트 추가] 전체 검색은 부모별 대표 청크 527개를 모두 읽어 문맥 중복을 제거합니다.
        # 상위 청크 100개만 읽으면 긴 주제 하나가 후보를 채울 수 있어 별도 SQL을 사용합니다.
        maximum = 1000 if best_per_parent else 100
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= maximum:
            raise ValueError(f"결과 수는 1~{maximum} 사이 정수입니다.")
        run = self.session.select_one("manual_store.get_run", {"run_id": run_id})
        if run is None or run["status"] != "ready":
            raise ValueError("저장을 완료한 처리 버전만 검색할 수 있습니다.")
        if (model_name, model_revision) != (run["model_name"], run["model_revision"]):
            raise ValueError("질문과 문서의 임베딩 모델·버전이 다릅니다.")
        vector = np.asarray(query_vector, dtype=np.float32)
        if vector.shape != (run["embedding_dimension"],) or not np.isfinite(vector).all():
            raise ValueError("질문 벡터의 차원과 숫자를 확인하세요.")
        # 기존 실험의 정규화 기준을 질문에도 적용합니다.
        if not np.isclose(np.linalg.norm(vector), 1.0, atol=1e-4):
            raise ValueError("기존 모델 설정대로 질문 벡터를 정규화하세요.")
        query_name = "search_parent_chunks" if best_per_parent else "search_chunks"
        return self.session.select_list("manual_store." + query_name, {
            "run_id": run_id, "query_embedding": Vector(vector), "limit": limit,
        })
