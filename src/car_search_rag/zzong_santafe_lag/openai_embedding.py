"""같은 검색 글을 OpenAI 벡터로 바꾸는 작은 도구입니다. 생성만으로 API를 호출하지 않습니다."""

import numpy as np
import tiktoken

MODEL = "text-embedding-3-small"
DIMENSION = 1536
RECIPE = "openai_small_1536_same_chunks_float32_normalized_v1"


class OpenAITokenCounter:
    """OpenAI의 글자 묶음(토큰)을 셉니다. 기존 로컬 모델의 128토큰과 단위가 다릅니다."""

    def __init__(self):
        """모델에 맞는 cl100k_base 사전을 준비합니다. 임베딩 API 호출은 없습니다."""
        # [모델 추가] 공식 입력 한도 8,192토큰보다 한 토큰 작은 값을 사용합니다.
        # 청킹은 바꾸지 않습니다. 이 한도는 기존 청크를 넣을 수 있는지 확인하는 용도입니다.
        self.budget = 8191
        self.encoding = tiktoken.get_encoding("cl100k_base")

    def count(self, text):
        """특수 기호도 PDF 글자로 취급해 토큰 수를 반환합니다."""
        return len(self.encoding.encode(text, disallowed_special=()))


def normalize_vectors(values):
    """벡터의 차원·숫자를 확인하고 문서와 질문 모두 길이를 1로 맞춥니다."""
    vectors = np.asarray(values, dtype=np.float32)
    if vectors.ndim != 2 or vectors.shape[1] != DIMENSION or not np.isfinite(vectors).all():
        raise ValueError("OpenAI 벡터의 1536차원·숫자를 확인하세요.")
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    if (norms <= 0).any():
        raise ValueError("길이가 0인 벡터는 저장할 수 없습니다.")
    return vectors / norms


class OpenAIEmbedder:
    """LangChain OpenAIEmbeddings로 문서와 질문을 같은 모델에 보냅니다."""

    def __init__(self, token_counter=None):
        """키를 화면에 출력하지 않고 공식 API 연결만 준비합니다."""
        from langchain_openai import OpenAIEmbeddings
        from .llm_answer_service import openai_key

        key = openai_key()
        if not key:
            raise ValueError("기존 개인 환경 설정에 OPENAI_API_KEY가 필요합니다.")
        self.token_counter = token_counter or OpenAITokenCounter()
        self.model_name, self.model_revision = MODEL, RECIPE
        self.dimension, self.model = DIMENSION, self
        # [수업 개념/프로젝트 적용] LangChain OpenAIEmbeddings 연결 방식을 사용합니다.
        # [모델 추가] API 모델에는 로컬 파일 revision이 없습니다. recipe는 우리 처리 설정의 버전입니다.
        # 입력을 자동 분할·평균내지 않고 동일한 청크 글을 그대로 보냅니다. 실패 시 자동 재호출도 하지 않습니다.
        self.client = OpenAIEmbeddings(
            model=MODEL, dimensions=DIMENSION, api_key=key,
            base_url="https://api.openai.com/v1", max_retries=0, request_timeout=60,
            check_embedding_ctx_length=False, chunk_size=64,
        )

    def embed_texts(self, texts):
        """최대 64개 글을 한 번 호출합니다. 성공 결과는 호출자가 체크포인트에 보관합니다."""
        counts = [self.token_counter.count(text) for text in texts]
        if not texts or len(texts) > 64 or any(not text.strip() for text in texts):
            raise ValueError("비어 있지 않은 글 1~64개를 지정하세요.")
        if any(count > self.token_counter.budget for count in counts) or sum(counts) > 300000:
            raise ValueError("OpenAI 입력 한도를 넘었습니다. 글을 자동으로 잘라서 저장하지 않습니다.")
        return normalize_vectors(self.client.embed_documents(texts))

    def embed_question(self, question):
        """질문 하나만 유료 API로 임베딩합니다. 기존 문서는 다시 임베딩하지 않습니다."""
        return self.embed_texts([question])[0]
