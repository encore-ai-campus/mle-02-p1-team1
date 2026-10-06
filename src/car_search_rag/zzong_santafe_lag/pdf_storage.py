"""싼타페 원본 PDF 한 개를 Storage에 보관하고 개인 문서 행에 연결합니다."""

# [프로젝트 추가] 원본 파일은 Storage에, 경로는 documents 테이블에 저장합니다.
# 팀 공통 설정·테이블·파일은 변경하지 않습니다. 같은 이름을 덮어쓰지 않습니다.
# Storage와 SQL은 하나의 거래가 아니므로, 중단 후에는 같은 파일을 대조해 재사용합니다.

import argparse
import hashlib
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values
from psycopg.conninfo import conninfo_to_dict
from supabase import ClientOptions, create_client

from .config import ManualConfig
from .database import PersonalDatabaseManager, PersonalSqlSession
from .source_profile import FULL_SOURCE


BUCKET = "images"
OBJECT_PATH = (
    f"cars/hyundai/santafe_hev/zzong_santafe_lag/{FULL_SOURCE.pdf_sha256}/"
    "santafe_hev_manual.pdf"
)


class PdfStorageService:
    """설정 확인·원본 업로드·DB 연결을 명시적으로 실행하는 개인 작업 도구입니다."""

    def __init__(self):
        """실행 상태만 준비합니다. 생성만으로 네트워크 요청은 하지 않습니다."""
        self.root = ManualConfig().project_folder
        self.stage = "not_started"

    def read_document(self, connection, *, lock=False):
        """현재 PDF의 문서 한 행만 읽습니다. DB 연결 때는 해당 행만 잠급니다."""
        statement = (
            "SELECT * FROM zzong_santafe_lag.documents WHERE file_sha256=%s"
            + (" FOR UPDATE" if lock else "")
        )
        rows = connection.execute(statement, (FULL_SOURCE.pdf_sha256,)).fetchall()
        if len(rows) != 1:
            raise ValueError("현재 싼타페 원본에 해당하는 문서 한 행이 필요합니다.")
        return rows[0]

    def prepare(self):
        """원본·DB·저장소가 같은 프로젝트인지 확인합니다. 쓰기는 하지 않습니다."""
        self.stage = "preflight"
        self.payload = ManualConfig().pdf_path.read_bytes()
        if hashlib.sha256(self.payload).hexdigest() != FULL_SOURCE.pdf_sha256:
            raise ValueError("현재 원본 PDF가 임베딩에 사용한 파일과 다릅니다.")
        values = dict(dotenv_values(self.root / ".env"))
        self.dsn = values.get("DB_URL")
        if not self.dsn:
            raise ValueError("루트 .env의 팀 DB_URL이 필요합니다.")
        # [프로젝트 추가] 사용자가 지정한 팀 DB_URL을 쓰되 기존 개인 자료와 같은 DB인지 확인합니다.
        team_info = conninfo_to_dict(self.dsn)
        own_info = conninfo_to_dict(PersonalDatabaseManager(read_only=True)._dsn)
        if any(team_info.get(key) != own_info.get(key) for key in ("host", "port", "dbname", "user")):
            raise ValueError("팀 DB와 개인 원문 DB가 다릅니다. 자동 이관하지 않습니다.")
        values.update(dotenv_values(Path(__file__).resolve().parent / ".env"))
        for key in ("SUPABASE_URL", "SUPABASE_SECRET_KEY", "ZZONG_SUPABASE_URL"):
            if key in os.environ:
                values[key] = os.environ[key]
        url = values.get("ZZONG_SUPABASE_URL") or values.get("SUPABASE_URL")
        secret = values.get("SUPABASE_SECRET_KEY")
        if not url or not secret:
            raise ValueError("같은 Supabase 프로젝트의 Storage 설정이 필요합니다.")
        parsed = urlparse(url)
        host = parsed.hostname or ""
        project = host.split(".")[0] if host.endswith(".supabase.co") else ""
        if parsed.scheme != "https" or not project or not (
            team_info.get("host") == f"db.{project}.supabase.co"
            or team_info.get("user", "").endswith("." + project)
        ):
            raise ValueError("Storage와 팀 DB의 프로젝트가 다릅니다.")
        reader = PersonalSqlSession(self.dsn, read_only=True)
        with reader.transaction():
            connection = reader.database_manager.connection
            self.before = self.read_document(connection)
            existing = connection.execute(
                "SELECT name FROM storage.objects WHERE bucket_id=%s AND name=%s",
                (BUCKET, OBJECT_PATH),
            ).fetchone()
        if (self.before["file_name"], self.before["local_path"], self.before["total_pages"]) != (
            "santafe_hev_manual.pdf", "data/santafe_hev_manual.pdf", FULL_SOURCE.page_count
        ):
            raise ValueError("저장된 문서의 원본 경로·쪽수가 다릅니다.")
        linked = (self.before["storage_bucket"], self.before["storage_path"])
        if linked not in ((None, None), (BUCKET, OBJECT_PATH)):
            raise ValueError("문서에 다른 원본 경로가 연결돼 있습니다.")
        self.client = create_client(url, secret, options=ClientOptions(storage_client_timeout=120))
        bucket = self.client.storage.get_bucket(BUCKET)
        if bucket.file_size_limit and len(self.payload) > bucket.file_size_limit:
            raise ValueError("PDF 크기가 버킷의 파일 크기 제한을 넘습니다.")
        allowed = bucket.allowed_mime_types
        if allowed and not any(mime in allowed for mime in ("application/pdf", "application/*", "*/*")):
            raise ValueError("현재 버킷이 PDF 업로드를 허용하지 않습니다.")
        self.existing = existing is not None
        if self.existing:
            self.verify_remote()
        elif linked != (None, None):
            raise ValueError("DB에 연결된 원본 파일이 Storage에 없습니다.")
        self.public_url = self.client.storage.from_(BUCKET).get_public_url(OBJECT_PATH) if bucket.public else None
        return {
            "bucket": BUCKET, "storage_path": OBJECT_PATH, "file_bytes": len(self.payload),
            "pdf_sha256": FULL_SOURCE.pdf_sha256, "page_count": FULL_SOURCE.page_count,
            "reusable_existing": self.existing, "public_url": self.public_url,
            "db_and_storage_project_match": True,
        }

    def verify_remote(self):
        """업로드한 파일을 다시 읽어 크기와 SHA-256을 원본과 대조합니다."""
        remote = self.client.storage.from_(BUCKET).download(OBJECT_PATH)
        if len(remote) != len(self.payload) or hashlib.sha256(remote).hexdigest() != FULL_SOURCE.pdf_sha256:
            raise ValueError("원격 파일이 PDF 원본과 다릅니다. 덮어쓰지 않습니다.")

    def upload(self):
        """PDF 한 개를 업로드한 후 개인 문서의 보관 경로 두 칼럼만 연결합니다."""
        result = self.prepare()
        self.stage = "storage_upload"
        if not self.existing:
            print("원본 PDF 업로드 중…", flush=True)
            try:
                self.client.storage.from_(BUCKET).upload(
                    OBJECT_PATH, self.payload,
                    file_options={"content-type": "application/pdf", "upsert": "false"},
                )
            except Exception as upload_error:
                # 응답이 끊겨도 파일이 저장됐을 수 있어, 재업로드보다 실제 내용부터 확인합니다.
                try:
                    self.verify_remote()
                except Exception:
                    raise upload_error from None
        self.stage = "remote_readback"
        print("원격 PDF와 원본을 대조 중…", flush=True)
        self.verify_remote()
        expected = {**self.before, "storage_bucket": BUCKET, "storage_path": OBJECT_PATH}
        self.stage = "db_linking"
        writer = PersonalSqlSession(self.dsn)
        with writer.transaction():
            connection = writer.database_manager.connection
            current = self.read_document(connection, lock=True)
            if current not in (self.before, expected):
                raise ValueError("준비 이후 문서 기록이 변경돼 연결을 중단합니다.")
            updated = connection.execute(
                "UPDATE zzong_santafe_lag.documents SET storage_bucket=%s, storage_path=%s "
                "WHERE id=%s AND file_sha256=%s RETURNING *",
                (BUCKET, OBJECT_PATH, self.before["id"], FULL_SOURCE.pdf_sha256),
            ).fetchall()
            if updated != [expected]:
                raise ValueError("문서 경로 이외의 값이 달라졌습니다.")
        self.stage = "db_readback"
        reader = PersonalSqlSession(self.dsn, read_only=True)
        with reader.transaction():
            if self.read_document(reader.database_manager.connection) != expected:
                raise ValueError("저장 후 문서 경로를 다시 확인하세요.")
        self.stage = "complete"
        result.update(completed=True, document_id=str(self.before["id"]),
                      db_linked_documents=1, download_sha256_matches=True,
                      added_file_bytes=0 if self.existing else len(self.payload),
                      completed_at=datetime.now(timezone.utc).isoformat())
        return result


def main():
    """check는 조회만, upload는 사용자 요청에 따라 원본 저장과 경로 연결을 실행합니다."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(description="개인 싼타페 원본 PDF의 Supabase 보관")
    parser.add_argument("command", choices=("check", "upload"))
    args = parser.parse_args()
    service = PdfStorageService()
    try:
        result = service.prepare() if args.command == "check" else service.upload()
        if args.command == "upload":
            # 결과에는 공개 주소·보관 경로만 기록합니다. API 키·DB 비밀번호는 기록하지 않습니다.
            report = service.root / "data/zzong_santafe_lag/reports/original_pdf_storage_result.json"
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            result["local_report"] = str(report)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as error:
        # 외부 오류 메시지에는 비밀 설정이 들어갈 수 있어 종류와 진행 단계만 보여줍니다.
        print(json.dumps({"completed": False, "stage": service.stage,
                          "error_type": type(error).__name__}, ensure_ascii=False), file=sys.stderr)
        if isinstance(error, ValueError):
            print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
