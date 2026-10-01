"""원문을 보존하면서 모델 입력 한도 안의 검색 조각을 만듭니다."""

# [수업 개념] 문서 청킹은 8_RAG파이프라인구축/1_문서로드_청킹.ipynb에서 다뤘습니다.
# [프로젝트 추가] 선택 모델의 실제 입력 한도와 싼타페 표·안내도 경계를 함께 지킵니다.

import json
import re
from copy import deepcopy
from functools import lru_cache
from pathlib import Path


class TokenCounter:
    """이미 내려받은 토크나이저로 입력 한도와 실제 토큰 수를 확인합니다."""

    def __init__(self, model_name):
        """모델 이름에 맞는 로컬 설정과 토크나이저를 읽습니다."""
        from transformers import AutoTokenizer
        from huggingface_hub import hf_hub_download

        # [프로젝트 추가] 글자 수 대신 현재 모델의 실제 한도인 128토큰을 사용합니다.
        # 이미 받은 로컬 설정·토크나이저만 읽습니다. 캐시가 없으면 별도의 다운로드 단계가 필요합니다.
        config_path = hf_hub_download(model_name, "sentence_bert_config.json", local_files_only=True)
        self.budget = json.loads(Path(config_path).read_text(encoding="utf-8"))["max_seq_length"]
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=True)

    # [프로젝트 추가] 같은 글의 토큰 수를 재계산하지 않도록 최근 계산 결과를 메모리에 보관합니다.
    @lru_cache(maxsize=8192)
    def count(self, text):
        """특수 토큰을 포함한 길이를 셉니다. 글을 자동으로 자르지 않습니다."""
        return len(self.tokenizer(text, add_special_tokens=True, truncation=False, verbose=False)["input_ids"])


# [프로젝트 추가] 확인한 경고 기호와 이미지 코드만 정리하며 raw_text는 대조할 원문으로 보존합니다.
def prepare_text(raw_text):
    """확인한 기호와 코드만 정리하고, 원문 문장은 유지합니다."""
    text = raw_text
    for old, new in {"҃Ҋ": "[경고]", "઱੄": "[주의]", "ӝ": "[참고]"}.items():
        text = text.replace(old, new)
    text = re.sub(r"^[12]C_[A-Za-z0-9_]+[ \t]*$", "", text, flags=re.MULTILINE)
    return re.sub(r"\s+", " ", text).strip()

def make_search_chunks(parent, budget, token_count):
    """유형별 경계를 지키며 실제 토큰 한도 안의 검색 조각을 만듭니다."""
    text = parent["content"]
    kind = parent["metadata"]["content_type"]
    # [프로젝트 추가] 짧은 청크의 문맥을 보충할 주제 제목을 붙입니다. 입력 한도는 제목까지 포함해 셉니다.
    prefix = "주제: " + parent["metadata"]["title"] + "\n"

    # 표는 한 묶음으로, 안내도는 한 줄의 번호 항목을 단위로 사용합니다.
    if kind == "table_with_images":
        units = [(0, len(text))]
    elif kind == "vehicle_overview_navigation":
        units = []
        start = 0
        for line in text.splitlines(keepends=True):
            units.append((start, start + len(line)))
            start += len(line)
    else:
        units = [(m.start(), m.end()) for m in re.finditer(r".+?(?:[.!?](?=\s|$)|$)", text, flags=re.DOTALL)]

    # [프로젝트 추가] 긴 설명문은 공백 단위로 더 나누고 표 행·안내도 항목은 검토하도록 중단합니다.
    # 길이에 맞추다가 표의 항목·수치 관계가 끊어지는 것을 막는 규칙입니다.
    expanded_units = []
    split_for_budget = False
    for start, end in units:
        if token_count(prefix + text[start:end].strip()) <= budget:
            expanded_units.append((start, end))
            continue
        # 표의 수치나 안내도 번호 항목은 자동으로 잘라 관계를 깨뜨리지 않습니다.
        if kind in {"table_with_images", "vehicle_overview_navigation"}:
            raise ValueError(f'{parent["metadata"]["title"]}: 한 항목이 토큰 한도를 넘으므로 별도 검토가 필요합니다.')
        split_for_budget = True
        words = list(re.finditer(r"\S+\s*", text[start:end]))
        if not words:
            raise ValueError("분할할 문장을 확인해야 합니다.")
        # 선행 공백까지 포함해 원문 묶음의 검색 글을 빠짐없이 덮습니다.
        for i, word in enumerate(words):
            word_start = start if i == 0 else start + word.start()
            word_end = start + word.end()
            if token_count(prefix + text[word_start:word_end].strip()) > budget:
                raise ValueError("공백이 없는 긴 단어는 별도 검토가 필요합니다.")
            expanded_units.append((word_start, word_end))

    # 이웃한 단위를 합치되 모델 입력 한도는 넘지 않습니다.
    ranges = []
    group_start = group_end = None
    for start, end in expanded_units:
        if group_start is None:
            group_start, group_end = start, end
        elif token_count(prefix + text[group_start:end].strip()) <= budget:
            group_end = end
        else:
            ranges.append((group_start, group_end))
            group_start, group_end = start, end
    if group_start is not None:
        ranges.append((group_start, group_end))

    # [프로젝트 추가] 자식 청크에서 전체 부모 원문을 찾도록 ID와 글자 구간을 기록합니다.
    # 그림은 부모에 연결하고 검색 후 원문·주의사항과 함께 읽습니다.
    children = []
    for index, (start, end) in enumerate(ranges):
        children.append({
            "content": prefix + text[start:end].strip(),
            # 원문은 부모 주제 전체입니다. 구간 위치는 부모의 검색 글을 기준으로 기록합니다.
            "raw_text": parent["raw_text"],
            "metadata": {
                "record_id": parent["metadata"]["record_id"] + f"_chunk_{index}",
                "parent_record_id": parent["metadata"]["record_id"],
                "pdf_page_number": parent["metadata"]["pdf_page_number"],
                "manual_page_number": parent["metadata"]["manual_page_number"],
                "source_pages": parent["metadata"]["source_pages"],
                "content_type": kind,
                "chunk_index": index,
                "parent_content_start": start,
                "parent_content_end": end,
                "raw_text_scope": "parent_topic",
                "parent_read_required": True,
                "sentence_split_for_budget": split_for_budget,
                "token_count": token_count(prefix + text[start:end].strip()),
            },
            # 그림은 연결된 부모 기록에서 가져옵니다.
            "image_parts": [],
        })
    return children

# [프로젝트 추가] 확인한 표는 행 경계를 보존하고 검토 상태·필수 연결 ID를 자식에도 전달합니다.
def split_record(parent, token_counter):
    """확인한 표 행을 유지하고 나머지 글은 문장 단위로 나눕니다."""
    if parent["metadata"]["content_type"] == "structured_table":
        # 한 줄 보존 기능을 확인한 표 행에도 적용합니다.
        proxy = deepcopy(parent)
        proxy["metadata"]["content_type"] = "vehicle_overview_navigation"
        chunks = make_search_chunks(proxy, token_counter.budget, token_counter.count)
        for chunk in chunks:
            chunk["metadata"]["content_type"] = "structured_table"
            chunk["metadata"]["chunking_unit"] = "complete_table_row_or_context_line"
    else:
        chunks = make_search_chunks(parent, token_counter.budget, token_counter.count)
    for chunk in chunks:
        chunk["metadata"]["verification_status"] = parent["metadata"]["verification_status"]
        chunk["metadata"]["review_flags"] = parent["metadata"].get("review_flags", [])
        chunk["metadata"]["required_context_record_ids"] = parent["metadata"].get("required_context_record_ids", [])
    return chunks
