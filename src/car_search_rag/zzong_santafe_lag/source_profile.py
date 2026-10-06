"""승인한 PDF·저장 작업의 고정 기준을 한곳에 보관합니다. 파일이나 DB를 읽지 않습니다."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class SourceProfile:
    """다른 자료·불완전한 저장 작업이 섞이지 않도록 대조할 기준입니다. 자동으로 최신 작업을 선택하지 않습니다."""
    run_id: UUID
    pdf_sha256: str
    page_count: int
    parent_count: int
    chunk_count: int
    image_count: int
    input_manifest_sha256: str

    @property
    def search_counts(self):
        """DB 조회가 반환하는 것과 같은 개수 사전을 새로 만들어 돌려줍니다."""
        return {"parent_count": self.parent_count, "chunk_count": self.chunk_count}


# [프로젝트 추가] 여러 실행 파일에 반복되던 같은 기준만 모았습니다. 값과 승인 범위는 그대로입니다.
# PDF·청킹을 바꾸면 먼저 원문·벡터·검토 상태를 새 버전으로 확인해야 합니다. 숫자만 바꿔 통과시키지 않습니다.
FULL_SOURCE = SourceProfile(
    run_id=UUID("ca9d2721-3d48-42a8-8748-3935e78515e5"),
    pdf_sha256="8fef11ef06a5ec675868b54b00b49b40de6bd4445f9f123fd0b4f6e0c5daad1b",
    page_count=779, parent_count=527, chunk_count=2213, image_count=864,
    input_manifest_sha256="893151d66a49fab8f21060ee95e7917054ebb12753dc62eb4ead26cd52798a1b",
)
