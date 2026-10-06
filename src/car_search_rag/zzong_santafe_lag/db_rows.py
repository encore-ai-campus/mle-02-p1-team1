"""PDF 예제 기록을 개인 여섯 테이블의 행으로 변환합니다. DB에 쓰지 않습니다."""

# [프로젝트 추가] 원래 딕셔너리와 DB 컬럼을 연결하는 변환 단계입니다.
# UUID는 테이블 사이 연결 번호, SHA-256은 파일·글·이미지 키의 변경 확인값입니다.
# 임베딩은 이전 실행의 메모리에만 있었으므로 이 단계에서는 None으로 명시합니다.
# 임의의 0 벡터를 넣거나, 임베딩이 없는 행을 저장 완료로 표시하지 않습니다.

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from huggingface_hub import hf_hub_download


def sha256_text(text):
    """글을 UTF-8 바이트로 바꿔 내용 식별값을 계산합니다."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha256(path):
    """PDF를 작은 묶음으로 읽어 파일 전체의 식별값을 계산합니다."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def local_model_revision(model_name):
    """다운로드된 모델 설정의 스냅샷 버전을 읽습니다. 다운로드하지 않습니다."""
    # [프로젝트 추가] 모델 이름만 같아도 버전이 달라질 수 있어 캐시의 버전을 기록합니다.
    # 이 값은 예정 모델 버전입니다. 실제 임베딩 단계에서도 같은 버전 사용을 확인해야 합니다.
    path = Path(hf_hub_download(model_name, "sentence_bert_config.json", local_files_only=True))
    if path.parent.parent.name != "snapshots":
        raise ValueError("모델 스냅샷 경로를 확인해야 합니다.")
    return path.parent.name


@dataclass
class RowPreview:
    """변환한 행과 미완료 항목을 메모리에 보관합니다. 저장 기능은 없습니다."""

    tables: dict
    selection_reasons: dict
    embedding_report: dict | None = None

    def summary(self):
        """전체 벡터나 비밀번호 없이 건수·출처·그림 연결 상태를 보여줍니다."""
        parents = self.tables["parent_records"]
        chunks = self.tables["chunks"]
        images = self.tables["images"]
        pending = sum(row["embedding"] is None for row in chunks)
        saved = bool(self.embedding_report and self.embedding_report.get("db_written"))
        return {
            "table_counts": {name: len(rows) for name, rows in self.tables.items()},
            "parents": [{
                "record_id": row["record_id"], "title": row["title"],
                "source_pages": row["source_pages"],
                "verification_status": row["verification_status"],
                "required_context_record_ids": row["metadata"].get("required_context_record_ids", []),
                "selection_reason": self.selection_reasons[row["record_id"]],
            } for row in parents],
            "images": [{
                "pdf_page_number": row["pdf_page_number"], "pdf_image_key": row["pdf_image_key"],
                "file_name": row["file_name"], "local_path": row["local_path"],
                "upload_status": row["upload_status"],
            } for row in images],
            "largest_chunk_tokens": max((row["token_count"] for row in chunks), default=0),
            "pending_embeddings": pending,
            "embedding_report": deepcopy(self.embedding_report),
            "embedding_complete": pending == 0 and self.embedding_report is not None,
            "db_saved": saved,
            "ready_for_insert": False,
            "note": ("승인한 표본을 DB에 저장하고 새 연결에서 값·벡터를 대조했습니다."
                     if saved else "표본 벡터 계산을 완료했습니다. 저장 전 검토·승인이 남았으며 DB에 쓰지 않았습니다."
                     if pending == 0 and self.embedding_report is not None else
                     "메모리 변환 미리보기입니다. 임베딩 확정·저장 전 검토가 필요하며 DB에 쓰지 않았습니다."),
        }


def select_sample_parents(service):
    """44·45쪽 예제와 43쪽 오일 표·각주, 필요한 연결 기록을 함께 선정합니다."""
    lookup = {record["metadata"]["record_id"]: record for record in service.parents}
    if len(lookup) != len(service.parents):
        raise ValueError("원문 ID가 중복되었습니다.")
    reasons = {"table_44": "44쪽 점도 표 예제", "vin_45": "45쪽 차대번호 예제"}
    # [프로젝트 추가] 43쪽은 용량·추천 사양·각주의 문맥입니다.
    # 44쪽과 새 필수 연결을 임의로 만들지는 않고, 예제 범위에 함께 포함합니다.
    for record in service.parents:
        meta = record["metadata"]
        if meta["pdf_page_number"] == 43 and meta["title"].startswith("추천 오일 및 용량"):
            reasons[meta["record_id"]] = "앞쪽 오일 표·각주 문맥"
    if len(reasons) != 4:
        raise ValueError("43쪽의 오일 표와 각주 두 기록을 확인해야 합니다.")
    queue = list(reasons)
    while queue:
        record_id = queue.pop()
        if record_id not in lookup:
            raise ValueError(f"연결할 원문이 없습니다: {record_id}")
        meta = lookup[record_id]["metadata"]
        # 서로 연결된 표와 각주는 방문 목록으로 순환을 막으며 미검토 연결도 보존합니다.
        for field in ("required_context_record_ids", "unreviewed_continuation_record_ids"):
            for target in meta.get(field, []):
                if target not in reasons:
                    reasons[target] = f"{record_id}의 {field} 연결"
                    queue.append(target)
    selected = [record for record in service.parents if record["metadata"]["record_id"] in reasons]
    return selected, reasons


def resolve_image(part, service):
    """PDF 내부 키와 실제 이름·크기를 대조하고 개인 로컬 경로를 확인합니다."""
    page_number = part["pdf_page_number"]
    page_images = service.inventory["reader"].pages[page_number - 1].images
    key = part.get("pdf_image_key")
    if key is None:
        # [프로젝트 추가] 기존 예제에는 파일명만 있어 현재 PDF에서 실제 내부 키를 찾습니다.
        # 이름이 중복되면 추측하지 않고 중단합니다. 파일명만으로 전체 PDF를 연결하지 않습니다.
        candidates = [candidate for candidate in page_images.keys()
                      if page_images[candidate].name == part.get("name")]
        if len(candidates) != 1:
            raise ValueError(f"PDF {page_number}쪽 이미지 이름과 내부 키를 대조해야 합니다.")
        key = candidates[0]
    image = page_images[key]
    if part.get("name") and part["name"] != image.name:
        raise ValueError("이미지 이름과 내부 키가 일치하지 않습니다.")
    if part.get("size") and tuple(part["size"]) != image.image.size:
        raise ValueError("이미지 크기가 기존 기록과 다릅니다.")
    # pypdf 중첩 키는 목록 형태로 JSONB에 보관합니다.
    json_key = list(key) if isinstance(key, tuple) else key
    key_text = json.dumps(json_key, ensure_ascii=False, separators=(",", ":"))
    local_path = part.get("local_path")
    if local_path:
        project = service.config.project_folder.resolve()
        path = (project / local_path).resolve()
        image_root = (project / "data" / "zzong_santafe_lag" / "images").resolve()
        if not path.is_relative_to(image_root) or not path.is_file() or path.name != image.name:
            raise ValueError("개인 이미지 경로 또는 파일을 확인해야 합니다.")
        local_path = path.relative_to(project).as_posix()
    return {
        "pdf_page_number": page_number, "pdf_image_key": json_key,
        "image_key_sha256": sha256_text(key_text), "file_name": image.name,
        "width": image.image.width, "height": image.image.height,
        "local_path": local_path, "storage_bucket": None, "storage_path": None,
        "upload_status": "local_available" if local_path else "reference_only",
    }


def build_sample_rows(service):
    """준비한 원문·청크에서 여섯 테이블의 예제 행을 만듭니다. DB 연결은 없습니다."""
    if service.inventory is None:
        raise ValueError("먼저 ManualService.prepare()로 자료를 준비하세요.")
    parents, reasons = select_sample_parents(service)
    selected_ids = set(reasons)
    chunks = [record for record in service.chunks
              if record["metadata"]["parent_record_id"] in selected_ids]
    if not chunks:
        raise ValueError("예제의 검색 청크가 없습니다.")
    if not 1 <= service.token_counter.budget <= 128:
        raise ValueError("현재 DB 설계의 128토큰 한도와 다릅니다.")
    tables = {name: [] for name in (
        "documents", "processing_runs", "parent_records", "chunks", "images", "record_images"
    )}
    # [프로젝트 추가] DB 접속 없이 연결 번호를 미리 발급합니다.
    # 미리보기를 다시 실행하면 새 번호이므로 실제 저장 시 확정한 묶음을 그대로 사용해야 합니다.
    document_id, run_id = uuid4(), uuid4()
    parent_ids = {record_id: uuid4() for record_id in sorted(selected_ids)}
    config = service.config
    tables["documents"].append({
        "id": document_id, "file_name": config.pdf_path.name,
        "file_sha256": file_sha256(config.pdf_path),
        "total_pages": len(service.inventory["reader"].pages),
        "local_path": config.pdf_path.relative_to(config.project_folder).as_posix(),
        "storage_bucket": None, "storage_path": None,
    })
    tables["processing_runs"].append({
        "id": run_id, "document_id": document_id,
        "pipeline_version": "db_sample_preview_v1",
        "model_name": config.model_name, "model_revision": service.token_counter.model_revision,
        "embedding_dimension": 768, "token_budget": service.token_counter.budget,
        "normalized": True,
        "settings": {
            "scope": "sample_preview", "seed_record_ids": ["table_44", "vin_45"],
            "selected_record_ids": sorted(selected_ids),
            "batch_size": config.batch_size, "cpu_threads": config.cpu_threads,
            "embedding_state": "pending", "model_revision_state": "planned_local_snapshot",
        },
    })
    image_ids = {}
    image_links = set()
    for parent in parents:
        meta = parent["metadata"]
        record_id = meta["record_id"]
        tables["parent_records"].append({
            "id": parent_ids[record_id], "run_id": run_id, "document_id": document_id,
            "record_id": record_id, "title": meta["title"],
            "raw_text": parent["raw_text"], "content": parent["content"],
            "pdf_page_number": meta["pdf_page_number"],
            "manual_page_number": meta["manual_page_number"],
            "source_pages": deepcopy(meta["source_pages"]), "content_type": meta["content_type"],
            "verification_status": meta["verification_status"],
            "review_flags": deepcopy(meta.get("review_flags", [])), "metadata": deepcopy(meta),
        })
        for part in parent["image_parts"]:
            if part["pdf_page_number"] not in meta["source_pages"]:
                raise ValueError("그림 쪽수가 해당 부모의 출처 쪽수에 없습니다.")
            image_row = resolve_image(part, service)
            identifier = (image_row["pdf_page_number"], image_row["image_key_sha256"])
            if identifier not in image_ids:
                image_ids[identifier] = uuid4()
                tables["images"].append({"id": image_ids[identifier], "document_id": document_id, **image_row})
            else:
                # 같은 그림을 다시 참조해도 파일 정보가 충돌하면 중단합니다.
                existing = next(row for row in tables["images"] if row["id"] == image_ids[identifier])
                if any(existing[field] != value for field, value in image_row.items()):
                    raise ValueError("같은 그림의 경로·크기 정보가 서로 다릅니다.")
            link = (parent_ids[record_id], image_ids[identifier])
            if link in image_links:
                raise ValueError("같은 부모와 그림 연결이 중복되었습니다.")
            image_links.add(link)
            tables["record_images"].append({
                "document_id": document_id, "parent_id": parent_ids[record_id],
                "image_id": image_ids[identifier], "description": part.get("description"),
                # 파일 키 확인은 그림과 본문 배치의 새로운 시각 검토를 뜻하지 않습니다.
                "linkage_status": "sample_linked" if part.get("description") else "unreviewed_page_reference",
                "metadata": {"source_image_part": deepcopy(part), "key_resolution": "matched_current_pdf"},
            })
    for chunk in chunks:
        meta = chunk["metadata"]
        parent = next(record for record in parents
                      if record["metadata"]["record_id"] == meta["parent_record_id"])
        start, end = meta["parent_content_start"], meta["parent_content_end"]
        expected = "주제: " + parent["metadata"]["title"] + "\n" + parent["content"][start:end].strip()
        if not 0 <= start < end <= len(parent["content"]) or chunk["content"] != expected:
            raise ValueError("청크 글과 부모 글자 구간이 일치하지 않습니다.")
        if service.token_counter.count(chunk["content"]) != meta["token_count"]:
            raise ValueError("기록한 토큰 수가 현재 글과 다릅니다.")
        if not 1 <= meta["token_count"] <= service.token_counter.budget:
            raise ValueError("모델 입력 토큰 한도를 넘는 청크입니다.")
        tables["chunks"].append({
            "id": uuid4(), "run_id": run_id, "parent_id": parent_ids[meta["parent_record_id"]],
            "record_id": meta["record_id"], "chunk_index": meta["chunk_index"],
            "content": chunk["content"], "content_sha256": sha256_text(chunk["content"]),
            "token_count": meta["token_count"], "parent_content_start": start,
            "parent_content_end": end, "embedding": None, "metadata": deepcopy(meta),
        })
    # 기존 원문·출처 딕셔너리는 직접 바꾸지 않고 새 행으로 복사했습니다.
    return RowPreview(tables, reasons)
