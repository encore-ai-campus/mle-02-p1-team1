# Hyundai Sonata 2026 차량 매뉴얼 RAG 발표 자료 — 수정본

> 16장 발표자 노트. 데일리 스크럼의 중간 평가는 당시 관찰로 기록하며 최신 최종 Retrieval과 Answer 평가는 분리한다.

## 1. SONATA 차량 매뉴얼 RAG

### 화면 핵심

검색과 응답 품질을 개선한 개발 과정 / 검색 / → / 답변 / 자연어 질문 / 매뉴얼 근거 / Vector RAG · Hybrid 보조 검색 · Streaming / 508 pages   /   947 chunks   /   955 images

### 발표자 노트

차량 매뉴얼에서 질문의 근거를 찾고 답변하는 RAG를 구현했다. 발표는 초기 검색 구조, 실제 실패, 보완 과정, 사용자 화면과 평가 결과를 따라간다.

## 2. 문제 정의

### 화면 핵심

508 / 페이지 / 질문 표현과 매뉴얼 표현은 다를 수 있다 / “엔진 번호는 차량의 어느 부위에서 확인할 수 있나요?” / 자연어 질문 / → 관련 페이지와 chunk를 검색 / → 근거 기반 답변과 이미지 표시

### 발표자 노트

508페이지 매뉴얼에서 사용자가 정확한 용어나 페이지를 몰라도 질문할 수 있어야 했다. 엔진 번호 질문은 뒤의 이미지 선택 사례와 연결된다.

## 3. PDF 데이터 구성

### 화면 핵심

508 / PDF pages / 508 / 508 / 텍스트 추출 성공 / 947 / chunks / 955 / images / 검색 단위 / 텍스트 / page / chunk / image / 텍스트 chunk와 이미지 정보를 분리해 저장

### 발표자 노트

10/02 구조와 구현 방향을 정리하고 10/03 프로토타입을 완성했다. 등록·검색 코드를 역할별로 나눈 뒤 PDF와 DB를 탐색했다. 페이지 텍스트, 947개 chunk, 이미지 955건을 별도로 다뤘다.

## 4. 초기 Vector RAG

### 화면 핵심

적재 / PDF page text  →  chunk 800 / overlap 150  →  text-embedding-3-small  →  PostgreSQL + pgvector / 질문·답변 / 질문 / 자연어 / Embedding / 1536차원 / Vector 검색 / <=> cosine / 근거 chunk / Top-K / LLM / 근거 기반 / Streamlit / 답변 표시 / Embedding과 pgvector로 Top-K 근거를 찾는 초기 구조 / 실제 평가에서 Vector 검색의 miss를 발견

### 발표자 노트

질문을 embedding하고 pgvector cosine 검색으로 Top-K 근거를 찾은 뒤 LLM 답변에 전달했다. 800자 chunk, 150자 overlap으로 적재했다. 이 초기 경로는 실제 평가에서 원하는 근거를 놓치는 경우가 있었다.

## 5. Retrieval-only 기준

### 화면 핵심

공식 Retrieval-only / 81.8% / Hit@5   9 / 11 / 0.5333 / MRR@5 / 11문항 · 독립 query 검색 / Top-5 밖: M6-05 (rank 6) · M6-11 (rank 10) / 실제 UI E2E 관찰과 평가 경로 분리

### 발표자 노트

M6 공식 11문항 Retrieval-only에서 Hit@5 9/11, MRR@5 0.5333이었다. M6-05와 M6-11의 정답 chunk는 각각 6위와 10위였다. 10/04 실제 UI M6 11문항 결과는 별도 실행 경로이므로 이 수치와 직접 비교하지 않는다.

## 6. Vector miss

### 화면 핵심

Vector Top-5 miss / 6위 / M6-05 정답 chunk / 10위 / M6-11 정답 chunk / M6 공식 11문항 검색에서 발견 / 기대 근거가 Top-5 밖에 위치 / 보조 retrieval 경로를 검토한 출발점

### 발표자 노트

Vector Top-5가 기대 chunk를 놓친 사례가 보조 검색 경로를 검토한 출발점이었다. 특정 질문의 순위를 강제로 맞추기보다 후보 검색의 빈틈을 살폈다.

## 7. Hybrid 설계

### 화면 핵심

질문 / 자연어 입력 / 키워드 / phrase / term / 병렬 검색 / Vector + LIKE / 후보 병합 / OR · +3/+1 / 재순위화 / reranking / Hybrid의 역할 / Vector 검색의 miss를 보완하는 보조 retrieval 경로 / Keyword 추출과 reranking은 실행별 변동 가능 / 최종 94%의 직접 원인으로 단정하지 않음

### 발표자 노트

Vector Search와 Keyword LIKE를 병렬 실행해 후보를 합친 뒤 reranking했다. Hybrid는 Vector miss를 보완하기 위한 보조 retrieval 경로다. 이후 94%가 관찰됐지만 실행 조건과 LLM 결과 변동이 있어 Hybrid의 직접 효과로 단정하지 않는다.

## 8. Keyword 시행착오

### 화면 핵심

실패 사례 / 후보 0건 / 긴 복합어만 추출 / Keyword 경로 보완 / phrase 분리 / 구문 일치 +3 / term 분리 / 단어 일치 +1 / OR 검색 / 후보 범위 확장 / 실행 / 별도 DB session / Vector·Keyword branch를 병렬 실행 / 두 결과를 합친 뒤 reranking

### 발표자 노트

LLM이 긴 복합어 하나만 키워드로 만들면 LIKE 후보가 0건이 됐다. phrase와 term으로 분리하고 OR 조건으로 후보를 확장했다. 기존 scoring은 phrase 일치 +3, term 일치 +1이다. Vector와 Keyword branch는 별도 DB session으로 병렬 실행했다.

## 9. 이미지 문제

### 화면 핵심

초기 UI 관찰 · U50-004 엔진 번호 질문 / 질문 / 엔진 번호 / 차량 어느 부위에서 확인하나요? / 기존 선택 / 무관 이미지 / 자기 인증 라벨 · 차대번호 / 문제 / 텍스트와 이미지의 주제가 달랐다 / 검색된 페이지의 이미지를 그대로 보여주면 질문과 어긋날 수 있음 / 이미지 관련성은 Retrieval과 별도로 점검

### 발표자 노트

초기에는 텍스트 답변과 다른 주제의 이미지가 함께 표시됐다. U50-004 엔진 번호 질문에서는 자기 인증 라벨이나 차대번호 쪽 그림이 선택됐다. 이미지 품질은 검색 근거 Hit와 별도로 확인해야 했다.

## 10. 이미지 문맥과 선택

### 화면 핵심

PDF / 그림 / 설명 / 제목·주변 텍스트 / 레이아웃 / 위치·동일 column / 판정 / 질문·답변·근거 / 표시 / 관련 이미지 / 0개 / U50-004 엔진 번호 질문 / 기존: 자기 인증 라벨·차대번호 이미지 / 개선: p.26 Smartstream 엔진 이미지 / Text LLM이 질문·최종 답변·검색 근거·이미지 설명을 보고 선택

### 발표자 노트

검색 결과에 함께 표시되는 이미지의 의미를 파악할 수 있도록 PDF의 제목·주변 텍스트·레이아웃을 활용해 이미지 설명 정보를 추가했다. 모델만 바꾸거나 문맥을 무작정 넓히는 실험은 주제 혼입과 정보 손실이 있었다. 이미지 위쪽 제목, 동일 column, 위치 관계를 활용했다. 이후 Text LLM이 질문, 최종 답변, 검색 근거, 이미지 설명을 함께 보고 관련성을 판단했다. 불명확하면 0개 표시를 허용했다. U50-004에서는 p.26 Smartstream 엔진 관련 이미지 선택을 확인했다.

## 11. latency 측정

### 화면 핵심

UI 관찰 / 19.830초 / 50문항 평균 UI latency / 처리 단계 로그 / 검색 완료 / 검색 시간 기록 / reranking 완료 / 답변 시작 전 지연 / 첫 token / TTFT·생성 완료·전체 시간 / Streaming / st.write_stream() / 생성 중 답변을 화면에 표시 / 검색·reranking·첫 token 대기는 남음

### 발표자 노트

Synthetic Holdout 실제 UI 실행 당시 평균 latency는 19.830초였다. 검색 완료, reranking 완료, 첫 token(TTFT), 생성 완료, 전체 처리 시간을 로그로 나눠 보았다. 병목 위치를 관찰하는 목적이며 속도가 완전히 해결됐다는 뜻은 아니다.

## 12. Streaming

### 화면 핵심

기존 / 변경 / → / 일괄 대기 / 생성 중 / 답변 완료 후 표시 / st.write_stream() / 검색·reranking 후 대기 / 첫 token 이후 순차 표시 / 변경 범위 / 답변 표시 방식 / 병목 지점은 로그로 측정 / 체감 응답을 개선했지만 실제 검색·TTFT 지연은 남음

### 발표자 노트

답변을 한 번에 기다리는 UI에서 st.write_stream()으로 생성 중 답변을 보여주는 방식으로 바꿨다. 사용자가 답변 생성 과정을 볼 수 있게 됐지만 검색과 reranking, 첫 token까지의 대기는 남았다.

## 13. UI 상태와 대화 길이

### 화면 핵심

UI / 전체 history / Agent / 최근 6개 / 질문 / RAG 실행 / 답변 / 대화 유지 / 출력 / Streaming / 대화 상태 관리 / 화면의 전체 대화 기록은 유지 / Agent 입력에는 최근 6개 message만 전달 / 작은 그림은 원본 크기에 맞춰 표시

### 발표자 노트

긴 대화에서 Agent context가 커지는 문제를 줄이기 위해 화면의 전체 conversation history는 유지하고 Agent에 전달하는 message만 최근 6개로 제한했다. 작은 매뉴얼 그림은 st.image(..., width="content")로 과도한 확대를 막았다.

## 14. Synthetic Holdout Retrieval

### 화면 핵심

최신 Retrieval Top-5 / 94% / Hit@5 · 47 / 50 / 47/50 / 정답 근거 포함 / 10/04 관찰: Top-5 90%, MRR@5 0.8033 / 10/05 관찰: Top-5 92%, MRR@5 0.8083 / 일부 조건이 달라 동일 조건 직접 비교 아님

### 발표자 노트

최신 최종 Synthetic Holdout 50문항에서 Retrieval Top-5 HIT는 47/50, 94%다. 10/04 관찰은 Top-5 90%, MRR@5 0.8033, 10/05 관찰은 Top-5 92%, MRR@5 0.8083이었다. 특히 10/05에는 이미지 relevance와 대화 이력 조건이 달라 동일 조건 직접 비교가 아니다. 이를 성능 향상 추세로 그리지 않는다.

## 15. Answer 평가와 해석

### 화면 핵심

Retrieval Top-5 / Answer Accuracy · 엄격 / ≠ / 94% / 98% / 47 / 50 HIT / 정답 49 / 50 / 근거 기준 / 부분 정답 1 · 오답 0 / 평가 대상 / Top-5 근거 포함 여부 / 최종 답변의 정확성 / 다른 유효 근거로 정답을 만들 수 있음

### 발표자 노트

최종 답변 판정은 정답 49, 부분 정답 1, 오답 0이다. 엄격 기준 Answer Accuracy는 98%다. Retrieval은 정답 근거가 Top-5에 들어왔는지, Answer 평가는 최종 답변이 맞는지를 본다. 검색 근거를 놓쳐도 다른 유효 근거로 정확한 답변이 가능했으므로 두 지표를 분리한다.

## 16. 결론

### 화면 핵심

질문 / 자연어 입력 / 검색 / Hybrid 후보 / 답변 / 근거 기반 생성 / 이미지 / 관련성 판정 / UI / Streaming 표시 / 최종 결과 / Retrieval Top-5 47/50 = 94% / 엄격 기준 Answer Accuracy 49/50 = 98% / 이미지는 PDF 문맥을 활용하고 관련 없으면 표시하지 않음

### 발표자 노트

검색에서는 Vector의 빈틈을 확인하고 Hybrid를 보조 경로로 추가했다. 이미지에서는 PDF의 문서 구조와 문맥을 활용하고 관련성을 별도 품질 축으로 관리했다. 최신 평가는 Retrieval Top-5 94%, 엄격 기준 Answer Accuracy 98%다. 남은 latency와 검색 miss는 후속 과제다.

## 근거 및 수치 해석

- 사용자 제공 Notion 데일리 스크럼 (10/02–10/05): 개발 과정과 중간 평가 관찰.
- M6_RETRIEVAL_EVALUATION.md: 초기 공식 Retrieval-only 11문항 결과.
- 사용자 제공 최신 Synthetic Holdout 50문항 최종 결과: Retrieval 47/50, 답변 정답 49·부분 1·오답 0.
- 10/04와 10/05 중간 수치는 일부 실행 조건이 달라 동일 조건 직접 비교가 아니다.
- Hybrid Search는 Vector miss를 보완하는 보조 retrieval 경로다. 최신 94%의 직접 원인으로 단정하지 않는다.
