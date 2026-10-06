"""저장된 싼타페 PDF 그림 전체를 개인 Storage 경로에 추가하고 용량을 측정합니다."""

# [프로젝트 적용] 기존 pypdf·Supabase SDK·SQL Mapper를 사용합니다. 새 모델은 없습니다.
# [프로젝트 추가] PDF 식별값, 그림 내부 키, 파일 내용, 개인 경로를 대조합니다.
# 파일은 덮어쓰거나 삭제하지 않습니다. 중단 후 같은 파일은 내용 확인 뒤 재사용합니다.
# 업로드 완료와 그림 설명 검토 완료는 다릅니다. 설명·검토 상태는 변경하지 않습니다.

import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path
from time import perf_counter, sleep
from urllib.parse import urlparse

import httpx
from dotenv import dotenv_values
from PIL import Image
from psycopg.conninfo import conninfo_to_dict
from pypdf import PdfReader
from supabase import ClientOptions, create_client

from .config import ManualConfig, SAMPLE_IMAGE_OBJECT_NAMES
from .database import PersonalDatabaseManager, PersonalSqlSession
from .source_profile import FULL_SOURCE


# 기존 도구의 공개 상수 이름은 유지하며 승인 범위는 같은 설정에서 읽습니다.
FULL_RUN_ID = FULL_SOURCE.run_id
PDF_SHA256 = FULL_SOURCE.pdf_sha256
BUCKET = "images"
PERSONAL_ROOT = "cars/hyundai/santafe_hev/zzong_santafe_lag/"
EXPECTED_IMAGE_COUNT = FULL_SOURCE.image_count


def ordered_state(rows):
    """DB 내용 비교를 위해 테이블 이름 순서로 정렬합니다."""
    return sorted(rows, key=lambda row: row["table_name"])


class FullImageStorageService:
    """사용자가 요청한 개인 PDF의 그림만 추가합니다. 생성만으로 접속하지 않습니다."""

    def __init__(self, progress=None):
        """진행 알림 함수와 메모리 작업 목록을 준비합니다."""
        self.progress = progress or (lambda event: None)
        self.stage = "not_started"
        self.started = perf_counter()
        self.plans = []
        self.verified = []
        self.failures = []
        self.new_uploads = 0
        self.config = ManualConfig()
        self.client = None
        self.public_client = None

    def emit(self, **event):
        """비밀키 없이 단계·건수·경과 시간만 호출자에게 전달합니다."""
        self.progress({"stage": self.stage, "elapsed_seconds": round(perf_counter() - self.started, 1), **event})

    def read_snapshot(self):
        """개인 자료와 개인 Storage 경로의 상태를 읽기 전용 연결에서 읽습니다."""
        session = PersonalSqlSession(read_only=True)
        with session.transaction():
            run = session.select_one("manual_store.get_run", {"run_id": FULL_RUN_ID})
            if not run or run["status"] != "ready" or run["settings"].get("scope") != "full_manual":
                raise ValueError("지정한 전체 PDF 처리 버전이 저장 완료 상태가 아닙니다.")
            document = session.select_one("manual_store.get_document", {"document_id": run["document_id"]})
            if document["file_sha256"] != PDF_SHA256 or document["total_pages"] != FULL_SOURCE.page_count:
                raise ValueError("저장 당시의 싼타페 PDF 식별값과 쪽수를 확인하세요.")
            return {
                "run": run, "document": document,
                "images": session.select_list("manual_store.get_document_images", {"document_id": document["id"]}),
                "protected": ordered_state(session.select_list("full_image_storage.protected_state")),
                # [프로젝트 추가] 용량은 내 경로 전체를 집계하되 다른 사람 경로는 조회하지 않습니다.
                "objects": session.select_list("full_image_storage.storage_objects", {"bucket_id": BUCKET, "prefix": PERSONAL_ROOT}),
                "sizes": session.select_list("manual_store.personal_table_sizes"),
                "descriptions": session.select_list("full_image_storage.description_counts", {"run_id": FULL_RUN_ID}),
                "permission": session.select_one("manual_store.image_update_permission"),
            }

    def connect_storage(self):
        """기존 설정을 읽어 DB와 같은 Storage인지 확인합니다. 버킷 설정은 수정하지 않습니다."""
        values = dict(dotenv_values(self.config.project_folder / ".env"))
        values.update(dotenv_values(Path(__file__).resolve().parent / ".env"))
        values.update({key: os.environ[key] for key in ("SUPABASE_URL", "SUPABASE_SECRET_KEY") if key in os.environ})
        url, secret = values.get("SUPABASE_URL"), values.get("SUPABASE_SECRET_KEY")
        host = urlparse(url or "").hostname or ""
        ref = host.split(".")[0] if host.endswith(".supabase.co") else ""
        dsn = conninfo_to_dict(PersonalDatabaseManager(read_only=True)._dsn)
        same = ref and (dsn.get("host") == f"db.{ref}.supabase.co" or dsn.get("user", "").endswith("." + ref))
        if not secret or urlparse(url or "").scheme != "https" or not same:
            raise ValueError("개인 DB와 Storage의 같은 프로젝트 설정을 확인하세요.")
        self.client = create_client(url, secret, options=ClientOptions(storage_client_timeout=30))
        bucket = self.client.storage.get_bucket(BUCKET)
        if not bucket.public:
            raise ValueError("기존 images 버킷의 공개 상태가 예상과 다릅니다. 설정을 변경하지 않습니다.")
        self.bucket = bucket
        # [프로젝트 추가] 공개 파일을 실제 읽어 원본 바이트와 비교합니다. URL 생성만으로 완료 처리하지 않습니다.
        self.public_client = httpx.Client(timeout=30, follow_redirects=False, limits=httpx.Limits(max_connections=4))

    def prepare(self):
        """DB·PDF·이미지를 대조하고 추가될 파일 수와 바이트를 계산합니다. 원격 쓰기는 없습니다."""
        self.stage = "preflight_db"
        self.emit(message="개인 DB의 그림 목록·보존 대상·사용 용량 조회")
        self.before = self.read_snapshot()
        if not self.before["permission"]["can_update"] or len(self.before["images"]) != EXPECTED_IMAGE_COUNT:
            raise ValueError("개인 그림 864개와 경로 변경 권한을 확인하세요.")
        self.document = self.before["document"]
        pdf_path = self.config.project_folder / self.document["local_path"]
        if pdf_path.resolve() != self.config.pdf_path.resolve() or hashlib.sha256(pdf_path.read_bytes()).hexdigest() != PDF_SHA256:
            raise ValueError("PDF 파일의 위치 또는 내용이 저장 당시와 다릅니다.")
        self.connect_storage()
        self.stage = "preflight_pdf"
        pdf = PdfReader(pdf_path)
        existing = {row["name"] for row in self.before["objects"]}
        by_page = {}
        for row in self.before["images"]:
            by_page.setdefault(row["pdf_page_number"], []).append(row)
        self.plans = []
        extracted_count = 0
        for number, page in enumerate(pdf.pages, 1):
            keys = page.images.keys()
            extracted_count += len(keys)
            rows = by_page.get(number, [])
            if len(keys) != len(rows):
                raise ValueError(f"PDF {number}쪽의 그림 수가 DB와 다릅니다.")
            used = set()
            for row in rows:
                key = row["pdf_image_key"]
                text = json.dumps(key, ensure_ascii=False, separators=(",", ":"))
                if hashlib.sha256(text.encode()).hexdigest() != row["image_key_sha256"]:
                    raise ValueError("DB의 PDF 내부 그림 키가 변경됐습니다.")
                lookup = tuple(key) if isinstance(key, list) else key
                # keys()의 중첩 키는 목록, 실제 조회 키는 튜플인 pypdf 규칙을 따릅니다.
                normalized_keys = [tuple(k) if isinstance(k, list) else k for k in keys]
                index = normalized_keys.index(lookup) + 1
                if index in used:
                    raise ValueError("같은 페이지의 그림 키가 중복됐습니다.")
                used.add(index)
                extracted = page.images[lookup]
                # [프로젝트 추가] 자동 추출 참조는 이름·크기를 NULL로 저장했던 자료입니다.
                # 내부 키로 실물을 꺼내며, 이전에 이름·크기가 확인된 그림은 그 값까지 대조합니다.
                # 이번 작업은 파일 보관이므로 기존 NULL 메타데이터를 임의로 덮어쓰지 않습니다.
                if row["file_name"] is not None and extracted.name != row["file_name"]:
                    raise ValueError(f"PDF {number}쪽의 그림 이름 대조 필요: DB={row['file_name']}, 추출={extracted.name}, 키={key}")
                payload = extracted.data
                with Image.open(BytesIO(payload)) as picture:
                    formats = {"JPEG": ("jpg", "image/jpeg"), "PNG": ("png", "image/png"), "JPEG2000": ("jp2", "image/jp2")}
                    if picture.format not in formats or (row["width"] is not None and picture.size != (row["width"], row["height"])):
                        raise ValueError("그림 형식 또는 픽셀 크기가 저장 정보와 다릅니다.")
                    suffix, mime = formats[picture.format]
                    pixel_size = picture.size
                    picture.verify()
                filename = f"page_{number:04d}_image_{index:02d}.{suffix}"
                # [프로젝트 추가] 이미 올린 예제 3개의 경로는 그대로 유지합니다.
                sample_name = SAMPLE_IMAGE_OBJECT_NAMES.get((number, extracted.name))
                if sample_name and filename != sample_name:
                    raise ValueError("표본 파일의 쪽수·순번 경로가 기존 값과 다릅니다.")
                target = f"{PERSONAL_ROOT}{PDF_SHA256}/{filename}"
                if row["upload_status"] == "uploaded":
                    if (row["storage_bucket"], row["storage_path"]) != (BUCKET, target) or target not in existing:
                        raise ValueError("기존 완료 그림의 경로 또는 원격 파일이 다릅니다.")
                elif row["upload_status"] not in {"reference_only", "local_available"} or row["storage_bucket"] or row["storage_path"]:
                    raise ValueError("예정하지 않은 그림 보관 상태입니다.")
                if self.bucket.file_size_limit and len(payload) > self.bucket.file_size_limit:
                    raise ValueError("기존 버킷의 파일 크기 제한을 초과합니다.")
                allowed = self.bucket.allowed_mime_types
                if allowed and mime not in allowed and "image/*" not in allowed:
                    raise ValueError("기존 버킷에서 그림 형식을 허용하지 않습니다.")
                self.plans.append({"image": row, "path": target, "payload": payload, "mime": mime,
                                   "sha256": hashlib.sha256(payload).hexdigest(), "existing": target in existing,
                                   "extracted_name": extracted.name, "pixel_size": pixel_size})
            if number % 50 == 0 or number == len(pdf.pages):
                self.emit(pdf_pages_checked=number, pdf_pages_total=len(pdf.pages), images_prepared=len(self.plans))
        if extracted_count != EXPECTED_IMAGE_COUNT or len({p["path"] for p in self.plans}) != EXPECTED_IMAGE_COUNT:
            raise ValueError("전체 그림 864개 또는 고유 업로드 경로 수가 다릅니다.")
        self.plans.sort(key=lambda p: p["path"])
        # [프로젝트 추가] 기존 파일은 업로드 전에도 공개 주소로 읽고 내용이 같을 때만 재사용합니다.
        self.stage = "verifying_existing_files"
        existing_plans = [plan for plan in self.plans if plan["existing"]]
        self.emit(existing_files_total=len(existing_plans), existing_files_checked=0)
        for checked, plan in enumerate(existing_plans, 1):
            if plan["existing"]:
                self.verify_public(plan)
            if checked % 25 == 0 or checked == len(existing_plans):
                self.emit(existing_files_total=len(existing_plans), existing_files_checked=checked)
        self.stage = "prepared"
        self.preflight = {
            "preflight_passed": True, "run_id": str(FULL_RUN_ID), "image_count": len(self.plans),
            "existing_objects_reused": sum(p["existing"] for p in self.plans),
            "new_objects_planned": sum(not p["existing"] for p in self.plans),
            "all_pdf_image_bytes": sum(len(p["payload"]) for p in self.plans),
            "additional_file_bytes": sum(len(p["payload"]) for p in self.plans if not p["existing"]),
            "db_before_bytes": sum(row["bytes"] for row in self.before["sizes"]),
            "storage_scope": BUCKET + "/" + PERSONAL_ROOT, "db_scope": "zzong_santafe_lag.images",
            "remote_writes": False,
        }
        self.emit(**self.preflight)
        return self.preflight

    def verify_public(self, plan):
        """로그인 없이 읽은 원격 그림의 길이와 SHA-256을 원본 추출 바이트와 비교합니다."""
        url = self.client.storage.from_(BUCKET).get_public_url(plan["path"])
        last = None
        for attempt in range(3):
            try:
                response = self.public_client.get(url)
                response.raise_for_status()
                if len(response.content) != len(plan["payload"]) or hashlib.sha256(response.content).hexdigest() != plan["sha256"]:
                    raise ValueError("원격 그림 내용이 PDF 원본과 다릅니다. 파일을 덮어쓰지 않습니다.")
                plan["public_url"] = url
                return
            except ValueError:
                raise
            except Exception as error:
                last = error
                sleep(attempt + 1)
        raise RuntimeError("공개 그림 내용 확인을 완료하지 못했습니다.") from last

    def upload_one(self, plan):
        """한 파일만 추가합니다. 응답 유실 시 기존 원격 내용을 비교하며 덮어쓰지 않습니다."""
        submitted = False
        if not plan["existing"]:
            last = None
            for attempt in range(3):
                try:
                    self.client.storage.from_(BUCKET).upload(plan["path"], plan["payload"], file_options={
                        "content-type": plan["mime"], "upsert": "false"})
                    submitted = True
                    break
                except Exception as error:
                    last = error
                    try:
                        remote = self.client.storage.from_(BUCKET).download(plan["path"])
                    except Exception:
                        sleep(attempt + 1)
                        continue
                    if hashlib.sha256(remote).hexdigest() != plan["sha256"] or len(remote) != len(plan["payload"]):
                        raise ValueError("같은 경로에 다른 내용의 파일이 있습니다. 변경하지 않습니다.")
                    # 서버에는 저장됐지만 응답을 받지 못한 경우도 원본 대조 후 재사용합니다.
                    break
            else:
                raise RuntimeError("파일 추가를 완료하지 못했습니다.") from last
        self.verify_public(plan)
        return submitted

    def upload(self, workers=4):
        """최대 4개씩 추가·내용 확인하고 개인 DB의 그림 보관 경로만 연결합니다."""
        if not self.plans or self.stage != "prepared":
            raise ValueError("먼저 prepare로 개인 자료와 추가 용량을 확인하세요.")
        if workers not in range(1, 5):
            raise ValueError("동시 작업 수는 1~4개로 제한합니다.")
        self.stage = "uploading"
        self.emit(total=len(self.plans), completed=0, failures=0)
        # [프로젝트 추가] CPU 임베딩은 실행하지 않습니다. 소수의 파일 요청만 동시에 보냅니다.
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(self.upload_one, plan): plan for plan in self.plans}
            for future in as_completed(futures):
                plan = futures[future]
                try:
                    self.new_uploads += int(future.result())
                    self.verified.append(plan)
                except Exception as error:
                    self.failures.append({"path": plan["path"], "error_type": type(error).__name__})
                self.emit(total=len(self.plans), completed=len(self.verified), failures=len(self.failures),
                          latest_pdf_page=plan["image"]["pdf_page_number"])
        if self.failures:
            raise RuntimeError("일부 그림 확인에 실패했습니다. 보고서의 파일만 확인한 뒤 재실행하세요.")
        self.stage = "linking_private_db"
        self.emit(message="864개 그림의 내용 확인 완료 → 개인 DB 경로만 연결")
        writer = PersonalSqlSession()
        with writer.transaction():
            locked = writer.select_list("full_image_storage.lock_document_images", {"document_id": self.document["id"]})
            if {str(r["id"]): r for r in locked} != {str(r["id"]): r for r in self.before["images"]}:
                raise ValueError("작업 중 개인 그림 정보가 변경됐습니다. DB 연결을 중단합니다.")
            if ordered_state(writer.select_list("full_image_storage.protected_state")) != self.before["protected"]:
                raise ValueError("작업 중 개인 원문·벡터·설명·검토 상태가 변경됐습니다.")
            parameters = []
            for plan in self.verified:
                row = plan["image"]
                if row["upload_status"] == "uploaded":
                    continue
                parameters.append({"image_id": row["id"], "document_id": self.document["id"],
                    "local_path": row["local_path"], "storage_bucket": BUCKET, "storage_path": plan["path"],
                    "before_status": row["upload_status"], "before_bucket": row["storage_bucket"], "before_path": row["storage_path"]})
            changed = writer.execute_many("full_image_storage.mark_uploaded", parameters)
            if changed != len(parameters):
                raise ValueError("개인 그림 경로 연결 건수가 예상과 다릅니다.")
            if ordered_state(writer.select_list("full_image_storage.protected_state")) != self.before["protected"]:
                raise ValueError("Storage 경로 외 개인 자료에 변경이 있습니다. DB 변경을 취소합니다.")
        self.stage = "readback"
        self.emit(message="새 읽기 전용 연결에서 파일 건수·DB 연결·용량 재확인")
        after = self.read_snapshot()
        if after["protected"] != self.before["protected"]:
            raise ValueError("업로드 후 개인 자료 보존 확인이 실패했습니다.")
        actual = {str(row["id"]): row for row in after["images"]}
        expected_paths = {p["path"]: p for p in self.plans}
        objects = {row["name"]: row for row in after["objects"]}
        for plan in self.plans:
            row = actual[str(plan["image"]["id"])]
            if (row["storage_bucket"], row["storage_path"], row["upload_status"]) != (BUCKET, plan["path"], "uploaded"):
                raise ValueError("원격 확인을 마친 그림과 DB 경로가 다릅니다.")
            obj = objects.get(plan["path"])
            if not obj or int(obj["metadata"].get("size", -1)) != len(plan["payload"]):
                raise ValueError("Storage의 파일 건수 또는 저장 크기가 원본과 다릅니다.")
        # [프로젝트 추가] 기존 개인 파일의 내용·Storage 메타데이터를 그대로 보존했는지 대조합니다.
        if any(objects.get(row["name"]) != row for row in self.before["objects"]):
            raise ValueError("기존 개인 Storage 파일의 메타데이터가 바뀌었습니다.")
        if set(objects) != set(expected_paths) | {row["name"] for row in self.before["objects"]}:
            raise ValueError("예정하지 않은 개인 Storage 파일의 증감이 있습니다.")
        total_storage = sum(int(row["metadata"]["size"]) for row in after["objects"])
        database_bytes = sum(row["bytes"] for row in after["sizes"])
        self.stage = "completed"
        result = {"completed": True, "run_id": str(FULL_RUN_ID), "pdf_sha256": PDF_SHA256,
            "image_count": len(self.plans), "new_objects_added": len(objects) - len(self.before["objects"]),
            "existing_objects_reused": self.preflight["existing_objects_reused"], "db_image_rows_updated": changed,
            "verified_public_images": len(self.verified), "failure_count": len(self.failures),
            "storage_bytes": total_storage, "storage_objects": len(objects), "db_relation_bytes": database_bytes,
            "combined_measured_bytes": total_storage + database_bytes,
            "additional_storage_bytes": self.preflight["additional_file_bytes"], "db_table_sizes": after["sizes"],
            "protected_personal_rows_unchanged": True, "protected_state": after["protected"],
            "existing_storage_objects_unchanged": True, "description_review_unchanged": True,
            "description_counts": after["descriptions"], "teammate_write_scope": [],
            "write_scope": [BUCKET + "/" + PERSONAL_ROOT + PDF_SHA256 + "/", "zzong_santafe_lag.images (3 columns)"],
            "original_pdf_uploaded": bool(self.document["storage_path"]), "embedding_executed": False,
            "measurement_excludes": ["other schemas and Storage paths", "WAL and global DB management", "billing/egress"],
            "elapsed_seconds": round(perf_counter() - self.started, 1),
            "files": [{"image_id": str(p["image"]["id"]), "pdf_page": p["image"]["pdf_page_number"],
                       "file_name": p["extracted_name"], "db_file_name": p["image"]["file_name"],
                       "pixel_size": p["pixel_size"], "path": p["path"], "bytes": len(p["payload"]),
                       "sha256": p["sha256"], "public_url": p["public_url"], "reused": p["existing"]}
                      for p in self.plans]}
        self.emit(completed=len(self.plans), total=len(self.plans), failures=0,
                  storage_bytes=total_storage, db_relation_bytes=database_bytes)
        return result

    def close(self):
        """공개 파일 확인에 사용한 네트워크 연결을 닫습니다."""
        if self.public_client:
            self.public_client.close()
