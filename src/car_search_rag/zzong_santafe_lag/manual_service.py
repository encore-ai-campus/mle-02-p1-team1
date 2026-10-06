"""PDF 읽기 → 주제 묶기 → 청킹 → 임베딩 → 검색의 실행 순서를 관리합니다."""

# [프로젝트 추가] 노트북 실행 순서를 재사용할 서비스 함수로 옮겼습니다.
# SQL Mapper Documentation의 실행 파일/서비스 분리를 참고했고, DB 연결은 아직 포함하지 않습니다.

from collections import Counter
from .config import ManualConfig
from .pdf_reader import inspect_pdf
from .sample_records import build_confirmed_samples
from .topics import build_auto_topics
from .reviews import apply_paddle_review, apply_oil_review, apply_seat_image_descriptions
from .chunking import TokenCounter, split_record


class ManualService:
    """개인 PDF 실험을 한 번 준비한 뒤 검색에 재사용합니다."""

    def __init__(self, config=None):
        """설정만 보관합니다. 객체를 만드는 시점에는 PDF나 모델을 읽지 않습니다."""
        self.config = config or ManualConfig()
        self.inventory = None
        self.parents = []
        self.chunks = []
        self.token_counter = None
        self.engine = None

    def prepare(self, progress=print):
        """전체 PDF를 청킹해 메모리에 준비합니다. 파일이나 DB에 저장하지 않습니다."""
        if self.inventory is not None:
            return self
        if progress:
            progress(f"1/4 PDF 확인: {self.config.pdf_path}")
        inventory = inspect_pdf(self.config.pdf_path)
        if progress:
            progress("2/4 확인한 예제와 자동 주제 초안 만들기")
        samples, override_pages = build_confirmed_samples(inventory, self.config.project_folder)
        parents = samples + build_auto_topics(inventory, override_pages)
        # 화면에서 대조한 표·기호만 보완합니다. 다른 초안의 검토 상태는 올리지 않습니다.
        parents = apply_paddle_review(parents, inventory)
        parents = apply_oil_review(parents, inventory)
        # [프로젝트 추가] 기존 노트북의 74쪽 그림 설명을 청킹 전에 붙입니다.
        # 검색 글이 바뀌므로 전체 저장에서는 새 청크·벡터·작업 버전을 준비합니다.
        parents = apply_seat_image_descriptions(parents, inventory)
        if progress:
            progress("3/4 로컬 토크나이저로 검색 조각 나누기")
        token_counter = TokenCounter(self.config.model_name, revision=self.config.model_revision)
        chunks = [chunk for parent in parents for chunk in split_record(parent, token_counter)]
        if progress:
            progress("4/4 원문 연결과 토큰 한도 확인")
        # [프로젝트 추가] 중복 ID·잘못된 연결·빠진 글·입력 한도 초과를 임베딩 전에 확인합니다.
        self._validate_records(parents, chunks, token_counter)
        # 모든 단계가 끝난 경우에만 준비한 상태를 보관합니다.
        self.inventory, self.parents, self.chunks = inventory, parents, chunks
        self.token_counter = token_counter
        return self

    @staticmethod
    def _validate_records(parents, chunks, token_counter):
        """중복 ID, 누락된 연결, 청크 구간과 입력 한도를 확인합니다."""
        lookup = {p["metadata"]["record_id"]: p for p in parents}
        if len(lookup) != len(parents):
            raise ValueError("부모 원문 ID가 중복되었습니다.")
        chunk_ids = [c["metadata"]["record_id"] for c in chunks]
        if len(set(chunk_ids)) != len(chunk_ids):
            raise ValueError("검색 조각 ID가 중복되었습니다.")
        by_parent = {parent_id: [] for parent_id in lookup}
        for chunk in chunks:
            meta = chunk["metadata"]
            parent_id = meta["parent_record_id"]
            if parent_id not in lookup:
                raise ValueError("검색 조각의 부모 원문이 없습니다.")
            if token_counter.count(chunk["content"]) > token_counter.budget:
                raise ValueError("모델 입력 한도를 넘는 검색 조각이 있습니다.")
            by_parent[parent_id].append(chunk)
        for parent_id, parent in lookup.items():
            meta = parent["metadata"]
            for key in ["required_context_record_ids", "unreviewed_continuation_record_ids"]:
                if not set(meta.get(key, [])) <= set(lookup):
                    raise ValueError(f"연결된 원문을 찾을 수 없습니다: {parent_id}")
            cursor = 0
            for chunk in by_parent[parent_id]:
                child_meta = chunk["metadata"]
                start, end = child_meta["parent_content_start"], child_meta["parent_content_end"]
                if not cursor <= start < end <= len(parent["content"]):
                    raise ValueError(f"검색 조각의 글자 구간을 확인해야 합니다: {parent_id}")
                if parent["content"][cursor:start].strip():
                    raise ValueError(f"청킹하면서 빠진 글이 있습니다: {parent_id}")
                cursor = end
            if not by_parent[parent_id] or parent["content"][cursor:].strip():
                raise ValueError(f"청킹하지 않은 원문이 있습니다: {parent_id}")

    def summary(self):
        """준비한 자료의 개수와 검토 상태를 사람이 읽기 쉬운 값으로 돌려줍니다."""
        if self.inventory is None:
            raise RuntimeError("먼저 prepare()로 PDF와 청크를 준비하세요.")
        return {
            "pdf_pages": len(self.inventory["reader"].pages),
            "image_references": len(self.inventory["image_manifest"]),
            "parent_records": len(self.parents),
            "search_chunks": len(self.chunks),
            "embedding_dimension": 768,
            "token_budget": self.token_counter.budget,
            "largest_chunk_tokens": max(c["metadata"]["token_count"] for c in self.chunks),
            "verification_status": dict(Counter(p["metadata"]["verification_status"] for p in self.parents)),
        }

    def build_search(self, progress=print):
        """청크를 로컬 CPU 모델로 임베딩하고 검색기를 만듭니다. 실행 중 메모리에만 둡니다."""
        if self.engine is not None:
            return self.engine
        self.prepare(progress=progress)
        # 미리보기에서는 큰 모델을 읽지 않도록 실제 검색 때만 가져옵니다.
        from .embedding import LocalEmbedder
        from .retrieval import SearchEngine
        if progress:
            progress("로컬 모델 준비 → 전체 청크 임베딩 시작")
        embedder = LocalEmbedder(self.config, self.token_counter)
        vectors = embedder.embed_chunks(self.chunks, progress=progress)
        # [프로젝트 추가] 한 실행 안에서는 준비한 벡터·색인을 재사용합니다.
        # 현재 벡터는 메모리에 있으며 새 실행에서는 다시 계산합니다.
        self.engine = SearchEngine(self.parents, self.chunks, vectors, embedder.model, self.token_counter)
        if progress:
            progress(f"검색 준비 완료 | 벡터 크기: {vectors.shape}")
        return self.engine
