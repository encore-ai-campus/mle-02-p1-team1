"""파일 위치와 모델 설정을 한곳에서 관리합니다."""

# 표시 규칙: [수업 개념]은 확인한 수업 코드, [프로젝트 추가]는 싼타페용 설계입니다.
# 각 추가 항목의 근거와 관련 노트북은 learning_additions.md에서 확인합니다.

from dataclasses import dataclass, field
from pathlib import Path
import re
from uuid import UUID


# [프로젝트 추가] 초기 표본 도구의 저장 작업입니다. 전체 챗봇의 현재 검색 범위와는 구별합니다.
# 전체 원문 작업은 source_profile.py, OpenAI 벡터 작업 선택은 active_run.json에서 관리합니다.
SAMPLE_RUN_ID = UUID("dc327282-8cfd-4eb3-a2b0-1433e0b088ce")


# [프로젝트 추가] 소나타의 쪽수·순번 파일명 형식을 개인 표본 3개에 적용합니다.
# PDF 내부 키와 PC 파일명은 바꾸지 않고 Storage의 이름만 이 표로 결정합니다.
SAMPLE_IMAGE_OBJECT_NAMES = {
    (44, "I1.jpg"): "page_0044_image_01.jpg",
    (44, "I2.jpg"): "page_0044_image_02.jpg",
    (45, "I1.jpg"): "page_0045_image_01.jpg",
}


def sample_image_storage_path(file_sha256, pdf_page_number, file_name):
    """승인한 표본 그림의 개인 Storage 경로를 만듭니다. 그 외 그림은 거부합니다."""
    if not re.fullmatch(r"[0-9a-f]{64}", file_sha256):
        raise ValueError("PDF 파일 식별값을 확인하세요.")
    name = SAMPLE_IMAGE_OBJECT_NAMES.get((pdf_page_number, file_name))
    if name is None:
        raise ValueError("이번 업로드는 PDF 44·45쪽의 표본 그림 3개에 한정합니다.")
    return f"cars/hyundai/santafe_hev/zzong_santafe_lag/{file_sha256}/{name}"


@dataclass(frozen=True)
class ManualConfig:
    """현재 검토한 PDF와 로컬 모델의 설정을 보관합니다."""
    # [프로젝트 추가] 코드 파일 위치로 PDF 경로를 계산해 실행 폴더 차이로 생기는 파일 찾기 오류를 예방합니다.
    # [프로젝트 추가] src/car_search_rag 아래로 이동한 폴더에서 세 단계 위의 프로젝트 루트를 찾습니다.
    project_folder: Path = field(default_factory=lambda: Path(__file__).resolve().parents[3])
    # [모델 추가] 이 모델은 확인한 수업 노트북에서 찾지 못했습니다.
    # 선택 근거: 개인 02번 노트북에서 수업의 MiniLM과 같은 샘플로 비교해 우선 후보로 정했습니다.
    # 역할: PDF 글과 확인한 그림 설명을 768차원 벡터로 바꿔 비슷한 의미의 자료를 찾습니다.
    # 교체 시 토크나이저·입력 한도·차원을 확인하고 문서와 질문 벡터를 같은 모델로 다시 만들어야 합니다.
    model_name: str = "jhgan/ko-sroberta-multitask-mrl"
    # [프로젝트 추가] 16개씩 계산하고 CPU 스레드는 최대 4개로 제한한 현재 PC의 실험 설정입니다.
    # 모든 컴퓨터에서 가장 빠른 값이라는 뜻은 아닙니다.
    batch_size: int = 16
    cpu_threads: int = 4
    # [프로젝트 추가] 저장할 표본은 모델·토크나이저를 같은 캐시 버전으로 고정합니다.
    # None은 기존 실행 방식이며 실제 사용한 스냅샷은 TokenCounter에서 확인합니다.
    model_revision: str | None = None

    @property
    def pdf_path(self):
        """실행한 폴더와 무관하게 프로젝트의 PDF 경로를 돌려줍니다."""
        return self.project_folder / "data" / "santafe_hev_manual.pdf"
