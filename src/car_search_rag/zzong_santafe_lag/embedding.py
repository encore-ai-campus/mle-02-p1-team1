"""외부 추론 API 없이 CPU에서 전체 검색 조각을 임베딩합니다."""

# [수업 개념] SentenceTransformer 사용은 5_자연어처리/6_임베딩_벡터.ipynb에서 확인했습니다.
# [모델 추가] 실제 모델은 config.py의 jhgan/ko-sroberta-multitask-mrl이며 개인 비교 실험에서 선택했습니다.

import os
import time
import numpy as np


class LocalEmbedder:
    """다운로드된 한국어 모델을 읽고 벡터를 메모리에 만듭니다."""

    def __init__(self, config, token_counter):
        """CPU 사용량과 입력 한도를 확인해 로컬 모델을 준비합니다."""
        import torch
        from sentence_transformers import SentenceTransformer
        # [프로젝트 추가] 로컬 CPU와 모델 캐시로 실행하고 청킹의 토큰 한도·768차원 설정을 확인합니다.
        # 입력은 텍스트이며 그림 검색 정보에는 사람이 확인해 작성한 설명을 사용합니다.
        torch.set_num_threads(min(config.cpu_threads, os.cpu_count() or 1))
        self.model = SentenceTransformer(config.model_name, device="cpu", local_files_only=True)
        self.batch_size = config.batch_size
        self.token_counter = token_counter
        if self.model.max_seq_length != token_counter.budget:
            raise ValueError("토큰 한도와 임베딩 모델 설정이 다릅니다.")
        self.dimension = self.model.get_embedding_dimension()
        if self.dimension != 768:
            raise ValueError("검토한 768차원 모델과 다릅니다.")

    def embed_chunks(self, chunks, progress=print):
        """청크 순서를 유지해 임베딩하며 오류가 나면 해당 구간에서 멈춥니다."""
        if not chunks:
            raise ValueError("임베딩할 검색 조각이 없습니다.")
        if any(self.token_counter.count(c["content"]) > self.token_counter.budget for c in chunks):
            raise ValueError("모델 입력 한도를 넘는 청크가 있습니다.")
        # [프로젝트 추가] 청크와 벡터 순서를 유지해 숫자가 어느 원문을 뜻하는지 찾을 수 있게 합니다.
        # 오류가 나면 해당 배치(여러 개씩 묶은 구간)에서 중단해 누락을 숨기지 않습니다.
        vectors = np.empty((len(chunks), self.dimension), dtype=np.float32)
        started = time.perf_counter()
        for start in range(0, len(chunks), self.batch_size):
            end = min(start + self.batch_size, len(chunks))
            try:
                # [프로젝트 적용] normalize_embeddings=True는 벡터 길이를 1로 맞춥니다.
                # 이렇게 만든 문서·질문 벡터의 내적으로 의미 유사도를 비교합니다.
                batch = self.model.encode([c["content"] for c in chunks[start:end]],
                    batch_size=self.batch_size, convert_to_numpy=True,
                    normalize_embeddings=True, show_progress_bar=False)
                if batch.shape != (end - start, self.dimension) or not np.isfinite(batch).all():
                    raise ValueError("벡터 크기나 숫자를 확인해야 합니다.")
                vectors[start:end] = batch
            except Exception as error:
                raise RuntimeError(f"임베딩 실패 구간: {start}~{end}") from error
            # [프로젝트 추가] 64개마다 진행 상황을 출력합니다. 남은 시간은 평균 속도로 계산한 추정입니다.
            if progress and (end % 64 == 0 or end == len(chunks)):
                elapsed = time.perf_counter() - started
                remaining = (len(chunks) - end) * elapsed / end
                progress(f"임베딩 {end}/{len(chunks)} | 경과 {elapsed:.1f}초 | 예상 남은 시간 {remaining:.1f}초")
        if not np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-5):
            raise ValueError("벡터 정규화 결과를 확인해야 합니다.")
        return vectors
