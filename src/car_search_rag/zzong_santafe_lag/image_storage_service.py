"""개인 그림 3개의 준비 확인 → Storage 업로드 → DB 경로 연결을 담당합니다."""

# [프로젝트 적용] 소나타의 images 버킷·쪽수/순번 파일명·Supabase SDK를 사용합니다.
# [프로젝트 추가] 개인 경로, 덮어쓰기 금지, 파일 재조회 후 DB 연결을 적용합니다.
# 한계: Storage와 PostgreSQL은 하나의 트랜잭션이 아닙니다. 실패 시 자동 삭제하지 않고
# 다음 실행에서 같은 경로의 파일 내용을 대조해 재사용합니다. 전체 업로드 기능은 아닙니다.

import hashlib
import json
import os
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import httpx
from dotenv import dotenv_values
from PIL import Image
from psycopg.conninfo import conninfo_to_dict
from pypdf import PdfReader
from supabase import ClientOptions, create_client

from .config import ManualConfig, SAMPLE_IMAGE_OBJECT_NAMES, SAMPLE_RUN_ID, sample_image_storage_path
from .database import ManualRepository, PersonalDatabaseManager, PersonalSqlSession
from .sample_store import APPROVED_COUNTS, APPROVED_MANIFEST, load_sample_bundle


BUCKET = "images"


def compare_bundles(expected, actual):
    """이번에 변경할 경로 외에 원문·벡터·그림 설명이 유지됐는지 대조합니다."""
    for table, rows in expected.items():
        def row_key(row):
            """테이블에 맞는 고유 번호로 같은 행을 찾습니다."""
            return (row["parent_id"], row["image_id"]) if table == "record_images" else row["id"]
        lookup = {row_key(row): row for row in actual[table]}
        if len(rows) != len(lookup):
            raise ValueError("개인 표본의 행 건수가 바뀌었습니다.")
        for before in rows:
            after = lookup.get(row_key(before))
            if after is None or set(before) != set(after):
                raise ValueError("개인 표본의 연결 번호 또는 컬럼이 바뀌었습니다.")
            for field, value in before.items():
                if field == "embedding":
                    equal = np.array_equal(value, after[field])
                else:
                    equal = json.dumps(value, sort_keys=True, default=str) == json.dumps(after[field], sort_keys=True, default=str)
                if not equal:
                    raise ValueError(f"예정하지 않은 값 변경입니다: {table}.{field}")


class SampleImageStorageService:
    """이미 저장한 PDF 44·45쪽 표본만 업로드하며 팀 파일·설정을 수정하지 않습니다."""

    def __init__(self):
        """진행 상태를 준비합니다. 생성만으로 접속·업로드하지 않습니다."""
        self.project_folder = ManualConfig().project_folder
        self.stage = "not_started"
        self.completed_objects = []
        self.client = None
        self.plans = []
        self.before = None

    def prepare(self):
        """파일·DB·프로젝트 일치·Storage 접속을 확인합니다. 업로드와 DB 쓰기는 없습니다."""
        self.stage = "preflight"
        reader = ManualRepository(PersonalSqlSession(read_only=True))
        with reader.session.transaction():
            self.before = load_sample_bundle(reader, SAMPLE_RUN_ID)
            writable = reader.session.select_one("manual_store.image_update_permission")
        if {name: len(rows) for name, rows in self.before.items()} != APPROVED_COUNTS:
            raise ValueError("저장된 개인 표본 23개 행부터 확인하세요.")
        run = self.before["processing_runs"][0]
        if run["status"] != "ready" or run["settings"].get("input_manifest_sha256") != APPROVED_MANIFEST:
            raise ValueError("승인한 저장 완료 표본이 아닙니다.")
        if not writable["can_update"]:
            raise ValueError("개인 images 테이블의 경로 변경 권한이 필요합니다.")
        document = self.before["documents"][0]
        pdf_path = self.project_folder / document["local_path"]
        if pdf_path.resolve() != ManualConfig().pdf_path.resolve():
            raise ValueError("이번 표본의 싼타페 PDF 경로가 아닙니다.")
        if hashlib.sha256(pdf_path.read_bytes()).hexdigest() != document["file_sha256"]:
            raise ValueError("PDF가 표본 저장 당시 파일과 다릅니다.")
        pdf = PdfReader(pdf_path)
        self.plans = []
        keys = set()
        for image in sorted(self.before["images"], key=lambda row: (row["pdf_page_number"], row["file_name"])):
            key = (image["pdf_page_number"], image["file_name"])
            keys.add(key)
            relative = f"data/zzong_santafe_lag/images/pdf_page_{key[0]}/{key[1]}"
            if image["local_path"] != relative:
                raise ValueError("승인한 개인 그림 파일 경로가 아닙니다.")
            path = (self.project_folder / relative).resolve()
            personal_folder = (self.project_folder / "data/zzong_santafe_lag/images").resolve()
            if not path.is_relative_to(personal_folder) or not path.is_file():
                raise ValueError("개인 폴더에서 표본 그림 파일을 찾지 못했습니다.")
            local_payload = path.read_bytes()
            with Image.open(BytesIO(local_payload)) as picture:
                if picture.format != "JPEG" or picture.size != (image["width"], image["height"]):
                    raise ValueError("그림 형식 또는 크기가 저장 정보와 다릅니다.")
                picture.verify()
            internal_key = image["pdf_image_key"]
            if isinstance(internal_key, list):
                internal_key = tuple(internal_key)
            extracted = pdf.pages[key[0] - 1].images[internal_key]
            if extracted.name != key[1]:
                raise ValueError("PDF 내부 그림 키와 저장한 파일 이름이 다릅니다.")
            # [프로젝트 추가] PC의 예제 JPEG는 저장 과정에서 재압축됐을 수 있습니다.
            # 승인한 PDF 내부 키에서 현재 추출한 bytes를 사용하고 PC 파일은 수정하지 않습니다.
            payload = extracted.data
            with Image.open(BytesIO(payload)) as picture:
                if picture.format != "JPEG" or picture.size != (image["width"], image["height"]):
                    raise ValueError("PDF 내부 그림의 형식 또는 크기가 저장 정보와 다릅니다.")
                picture.verify()
            target = sample_image_storage_path(document["file_sha256"], *key)
            if image["upload_status"] == "uploaded":
                if (image["storage_bucket"], image["storage_path"]) != (BUCKET, target):
                    raise ValueError("다른 Storage 경로가 이미 연결돼 있습니다.")
            elif image["upload_status"] != "local_available" or image["storage_path"] is not None or image["storage_bucket"] is not None:
                raise ValueError("그림의 보관 상태를 먼저 확인하세요.")
            self.plans.append({"image": image, "path": target, "payload": payload,
                               "local_bytes_equal_pdf": local_payload == payload,
                               "sha256": hashlib.sha256(payload).hexdigest()})
        if keys != set(SAMPLE_IMAGE_OBJECT_NAMES):
            raise ValueError("표본 그림 3개의 페이지와 파일명이 다릅니다.")
        # [프로젝트 추가] 기존 설정은 읽기만 합니다. 주소·비밀키를 결과에 출력하지 않습니다.
        values = dict(dotenv_values(self.project_folder / ".env"))
        values.update(dotenv_values(Path(__file__).resolve().parent / ".env"))
        values.update({key: os.environ[key] for key in ("SUPABASE_URL", "SUPABASE_SECRET_KEY") if key in os.environ})
        url, secret = values.get("SUPABASE_URL"), values.get("SUPABASE_SECRET_KEY")
        if not url or not secret:
            raise ValueError("로컬 환경 설정에 SUPABASE_URL과 SUPABASE_SECRET_KEY가 필요합니다.")
        host = urlparse(url).hostname or ""
        project_ref = host.split(".")[0] if host.endswith(".supabase.co") else ""
        info = conninfo_to_dict(PersonalDatabaseManager(read_only=True)._dsn)
        same_project = project_ref and (info.get("host") == f"db.{project_ref}.supabase.co" or info.get("user", "").endswith("." + project_ref))
        if urlparse(url).scheme != "https" or not same_project:
            raise ValueError("Storage와 개인 DB가 같은 Supabase 프로젝트인지 확인하세요.")
        self.client = create_client(url, secret, options=ClientOptions(storage_client_timeout=20))
        bucket = self.client.storage.get_bucket(BUCKET)
        if not bucket.public:
            raise ValueError("현재 소나타와 같은 공개 images 저장소가 아닙니다.")
        total = sum(len(plan["payload"]) for plan in self.plans)
        for plan in self.plans:
            if bucket.file_size_limit and len(plan["payload"]) > bucket.file_size_limit:
                raise ValueError("그림 파일이 저장소의 파일 크기 제한을 넘습니다.")
        if bucket.allowed_mime_types and "image/jpeg" not in bucket.allowed_mime_types and "image/*" not in bucket.allowed_mime_types:
            raise ValueError("저장소에서 JPEG 업로드를 허용하지 않습니다.")
        # 업로드 전에도 같은 이름이 있으면 실제 내용을 대조합니다. 다른 파일은 덮어쓰지 않습니다.
        with reader.session.transaction():
            objects = reader.session.select_list("manual_store.sample_storage_objects", {
                "bucket_id": BUCKET, "prefix": self.plans[0]["path"].rsplit("/", 1)[0] + "/%"})
        existing = {row["name"] for row in objects}
        if existing - {plan["path"] for plan in self.plans}:
            raise ValueError("예정한 개인 경로에 표본 외 파일이 있습니다. 먼저 확인하세요.")
        for plan in self.plans:
            plan["existing"] = plan["path"] in existing
            if plan["existing"]:
                self.verify_object(plan)
            elif plan["image"]["upload_status"] == "uploaded":
                raise ValueError("DB는 업로드 완료인데 Storage 파일이 없습니다.")
        return {"preflight_passed": True, "run_id": str(SAMPLE_RUN_ID), "bucket": BUCKET,
                "upload_source": "pdf_extracted_image_bytes", "local_files_modified": False,
                "db_and_storage_project_match": True, "total_file_bytes": total,
                "objects": [{"pdf_page": p["image"]["pdf_page_number"], "file_name": p["image"]["file_name"],
                             "storage_path": p["path"], "bytes": len(p["payload"]), "reusable_existing": p["existing"]} for p in self.plans]}

    def verify_object(self, plan):
        """Storage에서 읽은 실제 파일이 PDF에서 추출한 원본 그림과 같은지 확인합니다."""
        remote = self.client.storage.from_(BUCKET).download(plan["path"])
        if len(remote) != len(plan["payload"]) or hashlib.sha256(remote).hexdigest() != plan["sha256"]:
            raise ValueError("Storage 파일이 원본 그림과 다릅니다. 덮어쓰지 않고 중단합니다.")

    def verify_public_object(self, plan):
        """로그인·비밀키 없는 공개 주소로도 같은 그림을 읽을 수 있는지 확인합니다."""
        public_url = self.client.storage.from_(BUCKET).get_public_url(plan["path"])
        # [프로젝트 추가] URL을 만드는 것만으로 파일 존재를 확인할 수 없어 실제 GET을 합니다.
        response = httpx.get(public_url, timeout=20, follow_redirects=False)
        response.raise_for_status()
        if hashlib.sha256(response.content).hexdigest() != plan["sha256"]:
            raise ValueError("공개 주소의 그림 파일이 원본과 다릅니다.")
        plan["public_url"] = public_url

    def upload(self, progress=print):
        """표본 3개만 업로드·재조회한 뒤 개인 DB의 경로 세 항목만 함께 변경합니다."""
        preflight = self.prepare()
        self.stage = "storage_upload"
        newly_uploaded = 0
        for plan in self.plans:
            if not plan["existing"]:
                # [프로젝트 추가] upsert=false는 같은 경로의 파일을 자동 덮어쓰지 않는 설정입니다.
                # 응답이 끊긴 경우에도 재업로드하지 않고 실제 파일부터 읽어 확인합니다.
                try:
                    self.client.storage.from_(BUCKET).upload(plan["path"], plan["payload"],
                        file_options={"content-type": "image/jpeg", "upsert": "false"})
                    newly_uploaded += 1
                except Exception as upload_error:
                    try:
                        self.verify_object(plan)
                    except Exception:
                        raise upload_error
            self.verify_object(plan)
            self.verify_public_object(plan)
            self.completed_objects.append(plan["path"])
            progress(f'그림 확인 완료: PDF {plan["image"]["pdf_page_number"]}쪽 / {plan["image"]["file_name"]}')
        expected = deepcopy(self.before)
        plan_by_id = {plan["image"]["id"]: plan for plan in self.plans}
        for row in expected["images"]:
            row.update(storage_bucket=BUCKET, storage_path=plan_by_id[row["id"]]["path"], upload_status="uploaded")
        self.stage = "db_linking"
        repository = ManualRepository(PersonalSqlSession())
        with repository.session.transaction():
            # [프로젝트 적용] Storage 성공 뒤에만 DB 경로 3건을 한 트랜잭션으로 확정합니다.
            for plan in self.plans:
                image = plan["image"]
                repository.session.select_one("manual_store.lock_sample_image", {
                    "image_id": image["id"], "document_id": image["document_id"]})
            compare_bundles(self.before, load_sample_bundle(repository, SAMPLE_RUN_ID))
            for plan in self.plans:
                image = plan["image"]
                count = repository.session.execute("manual_store.mark_image_uploaded", {
                    "image_id": image["id"], "document_id": image["document_id"],
                    "local_path": image["local_path"], "storage_bucket": BUCKET, "storage_path": plan["path"]})
                if count != 1:
                    raise ValueError("개인 그림 경로의 변경 건수가 다릅니다.")
            compare_bundles(expected, load_sample_bundle(repository, SAMPLE_RUN_ID))
        self.stage = "readback"
        reader = ManualRepository(PersonalSqlSession(read_only=True))
        with reader.session.transaction():
            compare_bundles(expected, load_sample_bundle(reader, SAMPLE_RUN_ID))
        self.stage = "complete"
        return {**preflight, "storage_uploaded": True, "new_upload_responses": newly_uploaded,
                "db_linked_images": 3, "other_sample_fields_and_vectors_unchanged": True,
                "objects": [{"pdf_page": p["image"]["pdf_page_number"], "storage_path": p["path"],
                             "bytes": len(p["payload"]), "download_sha256_matches": True,
                             "public_download_sha256_matches": True,
                             "public_url": p["public_url"]} for p in self.plans]}
