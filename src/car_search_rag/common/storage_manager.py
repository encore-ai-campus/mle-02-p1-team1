import mimetypes
import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client


#=========================================================
# Supabase Storage 이미지 업로드 관리
#=========================================================
class StorageManager:
    """
    Supabase Storage 이미지 업로드 및 URL 조회 관리
    """

    bucket_name: str                 # 이미지 파일을 저장할 Storage bucket 이름
    supabase: object                 # Supabase Client 객체

    #=========================================================
    # 생성자 및 Supabase Client 설정
    #=========================================================
    def __init__(self, bucket_name: str = "images") -> None:
        """
        환경변수로 Supabase Client를 생성하고 Storage bucket을 설정한다.
        """
        load_dotenv()

        supabase_url = os.getenv("SUPABASE_URL")
        if not supabase_url:
            raise ValueError("SUPABASE_URL 환경변수가 설정되지 않았습니다.")

        supabase_secret_key = os.getenv("SUPABASE_SECRET_KEY")
        if not supabase_secret_key:
            raise ValueError("SUPABASE_SECRET_KEY 환경변수가 설정되지 않았습니다.")

        self.bucket_name = bucket_name
        self.supabase = create_client(supabase_url, supabase_secret_key)

    #=========================================================
    # 자동차 이미지 Storage 경로 생성
    #=========================================================
    def build_car_image_path(self, brand: str, model: str, image_name: str) -> str:
        """
        자동차 이미지의 Storage 경로를 생성한다.
        """
        return f"cars/{brand}/{model}/{image_name}"

    #=========================================================
    # 자동차 이미지 파일 업로드
    #=========================================================
    def upload_car_image(
        self,
        image_path: str | Path,
        brand: str,
        model: str,
        image_name: str,
    ) -> str:
        """
        자동차 이미지를 Storage에 업로드하고 Public URL을 반환한다.
        """
        image_path = Path(image_path)
        if not image_path.is_file():
            raise FileNotFoundError(f"이미지 파일을 찾을 수 없습니다: {image_path}")

        storage_path = self.build_car_image_path(brand, model, image_name)
        content_type, _ = mimetypes.guess_type(image_path.name)
        if content_type is None:
            content_type = "application/octet-stream"

        with image_path.open("rb") as image_file:
            self.supabase.storage.from_(self.bucket_name).upload(
                path=storage_path,
                file=image_file,
                file_options={
                    "content-type": content_type,
                    "upsert": "true"
                }
            )

        return self.get_public_url(storage_path)

    #=========================================================
    # 자동차 이미지 bytes 업로드
    #=========================================================
    def upload_car_image_bytes(
        self,
        image_bytes: bytes,
        brand: str,
        model: str,
        image_name: str,
    ) -> str:
        """
        자동차 이미지 bytes를 Storage에 업로드하고 Public URL을 반환한다.
        """
        storage_path = self.build_car_image_path(brand, model, image_name)
        content_type, _ = mimetypes.guess_type(image_name)
        if content_type is None:
            content_type = "application/octet-stream"

        self.supabase.storage.from_(self.bucket_name).upload(
            path=storage_path,
            file=image_bytes,
            file_options={
                "content-type": content_type,
                "upsert": "true"
            }
        )

        return self.get_public_url(storage_path)

    #=========================================================
    # Public URL 조회
    #=========================================================
    def get_public_url(self, storage_path: str) -> str:
        """
        Storage에 저장된 파일의 Public URL을 반환한다.
        """
        return self.supabase.storage.from_(self.bucket_name).get_public_url(storage_path)
