"""아이오닉 전용: 코사인 50개 + 수업 TF-IDF 50개 → RRF → 최종 5개.

화면·대화 기록·답변 모델은 다루지 않습니다. 정답지나 평가 결과도 읽지 않습니다.
TF-IDF는 설명서의 page_content만 학습하며, 한 프로세스에서 재사용합니다.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
from threading import RLock
from typing import Callable

from kiwipiepy import Kiwi
from langchain_core.documents import Document
from sklearn.feature_extraction.text import TfidfVectorizer


@dataclass(frozen=True)
class HybridHit:
    document: Document
    cosine_distance: float | None
    cosine_rank: int | None
    tfidf_rank: int | None
    tfidf_similarity: float
    rrf_score: float


def reciprocal_rank_fusion(dense_ids, lexical_ids, constant=60):
    """두 순위표를 동등하게 합칩니다. 점수는 확률이 아닌 정렬 기준입니다."""
    scores = {}
    for branch in (dense_ids, lexical_ids):
        for rank, chunk_id in enumerate(dict.fromkeys(branch), 1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1 / (constant + rank)
    # 평가 때와 같은 동점 처리: ID의 오름차순.
    return sorted(scores, key=lambda cid: (-scores[cid], cid)), scores


class IoniqHybridSearch:
    def __init__(self, load_documents: Callable, vector_search: Callable,
                 *, top_k=5, candidate_k=50, rrf_constant=60):
        self.load_documents = load_documents
        self.vector_search = vector_search
        self.top_k = top_k
        self.candidate_k = candidate_k
        self.rrf_constant = rrf_constant
        self._lock = RLock()
        self._index = None

    def warmup(self):
        """차량 진입 때 한 번 준비합니다. 질문마다 설명서를 다시 학습하지 않습니다."""
        with self._lock:
            if self._index is not None:
                return
            documents = sorted(self.load_documents(), key=lambda d: d.id)
            if not documents or len({d.id for d in documents}) != len(documents):
                raise ValueError('아이오닉 TF-IDF 자료가 비었거나 청크 ID가 중복됩니다.')
            kiwi = Kiwi(num_workers=1)

            def nouns(text):
                # 수업·평가와 동일: 두 글자 이상의 명사, 동의어/질문별 규칙 없음.
                return [t.form for t in kiwi.tokenize(text)
                        if t.tag.startswith('N') and len(t.form) > 1]

            vectorizer = TfidfVectorizer(tokenizer=nouns, token_pattern=None)
            matrix = vectorizer.fit_transform([d.page_content for d in documents])
            fingerprint = sha256(json.dumps(
                [(d.id, d.page_content, d.metadata) for d in documents],
                ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            self._index = (documents, vectorizer, matrix, fingerprint)

    def clear_index(self):
        """같은 문서 ID의 본문을 재적재했다면 호출하거나 로컬 서버를 재시작합니다."""
        with self._lock:
            self._index = None

    def configuration(self):
        with self._lock:
            index = self._index
            return dict(method='cosine_tfidf_rrf', top_k=self.top_k,
                        candidate_k=self.candidate_k, rrf_constant=self.rrf_constant,
                        weights=[1, 1], tokenizer='Kiwi noun len>1', lowercase=True,
                        tfidf_norm='l2', smooth_idf=True, sublinear_tf=False,
                        lexical_positive_only=True, tie_break='chunk_id ascending',
                        tfidf_chunks=len(index[0]) if index else None,
                        tfidf_corpus_sha256=index[3] if index else None)

    def search(self, question, vector):
        # 같은 검색 질문을 두 검색에 전달합니다. 사용자 대화는 인덱스에 저장하지 않습니다.
        dense = self.vector_search(vector, self.candidate_k)
        self.warmup()
        with self._lock:
            documents, vectorizer, matrix, _ = self._index
            positions = {d.id: i for i, d in enumerate(documents)}
            # 운영 중 자료가 바뀐 사실을 발견하면 오래된 인덱스로 섞어서 검색하지 않습니다.
            if any(d.id not in positions or d.page_content != documents[positions[d.id]].page_content
                   for d, _ in dense):
                self.clear_index()
                self.warmup()
                documents, vectorizer, matrix, _ = self._index
                positions = {d.id: i for i, d in enumerate(documents)}
                if any(d.id not in positions or d.page_content != documents[positions[d.id]].page_content
                       for d, _ in dense):
                    raise ValueError('아이오닉 벡터·TF-IDF 자료 버전이 일치하지 않습니다.')
            scores = (matrix @ vectorizer.transform([question]).T).toarray().ravel()

        # TF-IDF가 0점인 문서는 임의로 채우지 않습니다. 명사가 없으면 벡터 검색만 남습니다.
        lexical = sorted((i for i, score in enumerate(scores) if score > 0),
                         key=lambda i: (-float(scores[i]), documents[i].id))[:self.candidate_k]
        lexical_ids = [documents[i].id for i in lexical]
        dense_ids = [d.id for d, _ in dense]
        ranked_ids, fused = reciprocal_rank_fusion(dense_ids, lexical_ids, self.rrf_constant)
        dense_ranks = {cid: rank for rank, cid in enumerate(dense_ids, 1)}
        lexical_ranks = {cid: rank for rank, cid in enumerate(lexical_ids, 1)}
        distances = {d.id: float(distance) for d, distance in dense}
        return [HybridHit(document=documents[positions[cid]], cosine_distance=distances.get(cid),
                          cosine_rank=dense_ranks.get(cid), tfidf_rank=lexical_ranks.get(cid),
                          tfidf_similarity=float(scores[positions[cid]]), rrf_score=fused[cid])
                for cid in ranked_ids[:self.top_k]]
