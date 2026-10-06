# 발표용 PPT 초안

> 검토용 슬라이드 원고다. EDA·TF-IDF·실험 로그·RAG 평가 문서와 실제 코드 흐름을 기준으로 작성했다. 성능 수치는 과거 대화에서 공유된 측정값임을 표시했으며, warm-up 적용 후 결과는 만들지 않고 `[추가 측정 필요]`로 남겼다. 슬라이드 본문은 발표 화면에 들어갈 핵심만 두고, 설명은 발표 멘트로 분리했다.

## 1. 프로젝트 소개

### 제목
차량 매뉴얼 기반 RAG 검색

### 화면에 표시할 핵심 내용
- 대상: Hyundai Sonata 2026 사용자 매뉴얼
- PDF 매뉴얼에서 검색 가능한 문서 chunk를 구성
- 질문과 관련된 매뉴얼 내용을 찾아 답변 흐름에 연결
- 이번 분석의 초점: 데이터 정합성, 검색 동작, 조회 지연

### 넣으면 좋은 그림/표/코드
- Sonata 매뉴얼 표지 이미지 또는 Streamlit 검색 화면 캡처 `[자료 필요]`
- 오른쪽 아래에 프로젝트 범위: `검색 파이프라인 + EDA + 성능 분석`

### 발표 멘트
이 프로젝트는 차량 매뉴얼을 질문으로 검색하고 답변에 연결하는 RAG 애플리케이션입니다. 분석 대상으로 Sonata 2026 매뉴얼을 사용했습니다. 작업을 진행하면서 검색 코드뿐 아니라 원본 PDF와 DB에 적재된 데이터가 잘 대응하는지, 검색 결과가 중복되지 않는지, 그리고 느린 구간이 어디인지 함께 확인했습니다. 오늘은 분석이 실제 SQL 및 연결 구조 개선으로 어떻게 이어졌는지 설명하겠습니다.

## 2. 전체 시스템 구조

### 제목
질문은 embedding 검색을 거쳐 매뉴얼 답변으로 연결된다

### 화면에 표시할 핵심 내용
```text
사용자 질문
  → Streamlit (app_kbj.py)
  → CarManualSearchService
  → 질문 embedding
  → CarManualRepository
  → SqlSession / search_car_manual
  → PostgreSQL + pgvector
  → 검색 결과
  → RAG 답변
```
- 서비스 검색 함수: `search_manual()`
- 답변 흐름: `ask_manual()`

### 넣으면 좋은 그림/표/코드
- 위 흐름을 7개 박스와 화살표로 표현한 시스템 구성도
- 코드 캡처는 함수명만 보이도록 `search_manual()` → `search_car_manual` 호출부 `[자료 필요]`

### 발표 멘트
Streamlit 화면에서 질문이 들어오면 `CarManualSearchService`가 검색을 담당합니다. 질문을 embedding으로 바꾸고, repository가 `SqlSession`을 통해 `search_car_manual` SQL을 호출합니다. PostgreSQL의 pgvector가 가까운 chunk를 찾고, 결과를 답변 생성 흐름에 넘깁니다. 이 경로를 코드에서 확인해 각 분석 결과가 어느 계층을 설명하는지 구분했습니다.

## 3. 데이터 및 EDA

### 제목
PDF 508페이지와 DB chunk·이미지의 대응을 점검했다

### 화면에 표시할 핵심 내용
- 원본: `data/DN8_2026_ko_KR.pdf`, Sonata 2026
- PDF 508페이지, 텍스트 추출 성공 508/508로 기록
- DB 기준: chunk 947건, image 955건으로 보고됨
- 모든 페이지에 chunk가 있으나, 페이지별 존재가 본문 완전성을 보장하지는 않음
- image 설명은 955건 모두 NULL로 기록

### 넣으면 좋은 그림/표/코드
- EDA 노트북의 페이지별 텍스트 길이 그래프 또는 chapter별 분포 `[노트북에서 그래프 확인 후 캡처 필요]`
- PDF → chapter → chunk / image 관계를 보여주는 간단한 데이터 구조 그림
- 실제 DB DDL 기준 네 테이블(`car`, `chapter`, `chunk`, `image`)은 작은 구조표로 표시

### 발표 멘트
EDA에서는 PDF 텍스트 추출 상태뿐 아니라 DB chunk와 이미지가 원본 페이지에 맞게 연결되는지도 확인했습니다. 문서에는 508페이지 전체에서 텍스트 추출이 성공했다고 기록되어 있고, DB에는 947개 chunk와 955개 이미지가 적재된 것으로 정리되어 있습니다. 다만 페이지마다 chunk가 있다는 사실만으로 표나 이미지까지 포함한 내용이 완전하다고 볼 수는 없습니다. 이미지 설명이 전부 비어 있는 점도 남은 한계입니다.

## 4. TF-IDF 분석

### 제목
키워드 검색과 vector 검색은 질문별로 다른 순위를 보였다

### 화면에 표시할 핵심 내용
- 대상 corpus: Sonata 2026 DB chunk 947건
- 설정: `ngram_range=(2,4)`, vocabulary 175,451개
- 비교 질의: 엔진 오일 / 후드 닫기 / 배터리 단자 3개
- 후드 닫기: 근거 chunk TF-IDF top 5 밖, vector rank 4
- 3개 질의만 사용한 진단 결과이며 일반화 가능한 benchmark는 아님

### 넣으면 좋은 그림/표/코드
- 보고서의 세 질의 순위 표를 간결하게 재작성
  - 엔진 오일 근거: TF-IDF 2위, vector 2위
  - 후드 닫기 근거: TF-IDF top 5 밖, vector 4위
  - 배터리 단자 근거: TF-IDF 1위, vector 1위
- 질의별 rank 비교 막대/점 그래프 `[원 데이터 확인 후 제작 필요]`

### 발표 멘트
TF-IDF는 키워드 기반 결과를 비교 기준으로 보기 위해 분석에 사용했습니다. 세 질문에서 엔진 오일과 배터리 단자는 두 방식 모두 근거 chunk를 상위에 배치했습니다. 후드 닫기 질문에서는 TF-IDF 상위 결과가 관련 근거를 놓쳤고 vector 검색에서는 4위였습니다. 이 결과는 키워드가 달라지는 질문의 사례를 보여주지만, 질의가 세 개뿐이라 vector 검색의 일반적인 우수성을 입증하지는 않습니다.

## 5. RAG 검색 파이프라인

### 제목
1536차원 질문 embedding을 cosine distance로 정렬한다

### 화면에 표시할 핵심 내용
- 모델: `text-embedding-3-small`
- 코드의 embedding 차원 상수: 1536
- `search_manual()` → `CarManualRepository.search_manual()`
- SQL `search_car_manual`: 차량 조건 필터 + pgvector `<=>` 정렬
- 결과 similarity: `1 - distance`
- 실제 DB catalog에서 유효한 HNSW index 확인: `car_manual_chunk_embed_vec`, `vector_cosine_ops`
- 실제 검색형 `EXPLAIN`: 이번 실행은 HNSW 미선택; `car_manual_chunk_pkey` Index Scan + top-N heapsort

### 넣으면 좋은 그림/표/코드
- SQL에서 거리 계산과 `ORDER BY ... <=> :EMBEDDING` 부분을 짧게 발췌
- vector index 존재와 planner 선택 여부를 분리한 표식
- Planning 5.835 ms / Execution 15.178 ms (단일 실측, 2026-10-04)

### 발표 멘트
검색 서비스와 등록 코드에는 `text-embedding-3-small`이 설정되어 있고 Sonata 데이터는 1536차원 embedding 947개를 보유합니다. `search_car_manual`은 차량 조건을 적용한 뒤 pgvector의 `<=>` 거리로 정렬합니다. 실 DB catalog에서 HNSW와 `vector_cosine_ops`를 확인했지만, 이번 실행계획에서는 HNSW 대신 PK Index Scan과 top-N heapsort가 선택됐습니다. 한 번의 계획 결과이므로 그 원인을 특정 하나로 단정하지 않습니다.

## 6. 검색 성능 분석

### 제목
서버 실행 시간과 애플리케이션 체감 시간은 측정 범위가 다르다

### 화면에 표시할 핵심 내용
| 지표 | 포함 구간 |
|---|---|
| `connect_ms` | SqlSession이 connection을 확보하는 시간 |
| `sql_log_ms` | SELECT 로그 SQL 렌더링 시간 |
| `query_fetch_ms` | SQL 실행부터 전체 결과 fetch까지 |
| `total_ms` | `select_list()` 전체 시간 |

- 사용자 제공 과거 측정: DB `Execution Time` 12.467ms
- Python: connect 577.1ms / SQL log 5.5ms / query+fetch 115.1ms / total 729.5ms
- 위 수치는 pool warm-up 전후 비교가 아님

### 넣으면 좋은 그림/표/코드
- 12.467ms와 729.5ms를 별도 축 또는 범위가 다른 두 막대로 표시
- Python 측 4개 항목 누적 막대: connect 577.1, SQL log 5.5, query/fetch 115.1, 기타/측정 차이 31.8ms
- 그래프 제목에 `과거 1회 측정, 사용자 제공` 표기

### 발표 멘트
PostgreSQL에서 전달받은 `EXPLAIN (ANALYZE, BUFFERS)` 기록의 Execution Time은 약 12.5ms였습니다. 반면 Python 애플리케이션에서는 전체 729.5ms가 기록됐고, 그 중 connection 확보가 577.1ms였습니다. 두 측정은 포함하는 범위가 다릅니다. `query_fetch_ms`에는 네트워크 전달, 드라이버 decode와 fetch 등이 들어갈 수 있어 서버 실행 시간과 직접 같지 않습니다. 이 수치는 과거 한 번의 관측으로, 개선 후 결과는 아닙니다.

## 7. 발견한 문제

### 제목
가장 큰 관측 구간은 SQL 로그가 아니라 connection 확보였다

### 화면에 표시할 핵심 내용
- 당시 측정에서 `connect_ms=577.1ms`
- 같은 기록의 `sql_log_ms=5.5ms`
- `query_fetch_ms=115.1ms`, `total_ms=729.5ms`
- 서버 `Execution Time=12.467ms`와 Python 전체 측정은 범위가 다름
- 원인을 DNS/TCP/TLS 등으로 분리 측정한 것은 아님

### 넣으면 좋은 그림/표/코드
- connect 577.1 / SQL 로그 5.5 / query+fetch 115.1의 수평 막대 비교
- 아래에 주석: “단일 과거 관측, 인과 원인 세부 계측 아님”
- SQL 실행계획 전문은 부록 또는 발표자 노트에 배치

### 발표 멘트
이 측정에서 가장 큰 구간은 SQL 로그 렌더링이 아니라 connection 확보였습니다. 당시 일반 조회 경로는 `psycopg.connect()`로 연결을 만드는 구조였다는 코드 분석과 함께 보면, 매 요청의 연결 생성 비용을 줄이는 것이 우선 개선 후보라고 판단할 수 있습니다. 다만 connect 구간 안에서 DNS, TLS, 인증 등 무엇이 몇 밀리초를 차지했는지는 따로 측정하지 않았습니다. 그래서 원인을 특정 네트워크 단계로 단정하지 않습니다.

## 8. 개선 작업

### 제목
요청마다 연결을 새로 만들던 경로를 pool 대여로 바꿨다

### 화면에 표시할 핵심 내용
```text
@st.cache_resource 최초 생성
  → CarManual / SqlSession / DatabaseManager
  → warmup()
  → ConnectionPool 준비

검색 요청
  → pool에서 대여
  → SQL 실행
  → pool 반환
```
- 기본 pool: `min_size=1`, `max_size=5`
- `DB_POOL_MIN_SIZE`, `DB_POOL_MAX_SIZE` 지원
- row factory별 pool 분리
- physical connection 생성 callback에서 `register_vector()`
- transaction은 connection 하나를 유지하고 성공 commit / 예외 rollback 후 반환

### 넣으면 좋은 그림/표/코드
- “요청마다 새 연결”과 “pool에서 대여·반환” 비교 그림
- `DatabaseManager.warmup()` 호출부와 `transaction()`의 commit/rollback 구조를 작은 코드 캡처로 제시
- `PGEngine` 및 `PersonalDatabaseManager`는 별도 경로라는 각주

### 발표 멘트
개선은 일반 psycopg 연결 경로에 pool을 적용하는 방향으로 진행했습니다. Streamlit의 cached resource가 최초 생성될 때 `warmup()`을 호출해 검색 전에 최소 연결을 준비하도록 했습니다. pgvector adapter 등록은 SELECT마다 반복하지 않고 물리 연결을 만들 때 callback에서 처리합니다. transaction은 블록 전체에서 같은 연결을 사용하고 정상 종료 시 commit, 예외 시 rollback한 뒤 pool에 반환합니다. 이 구조의 실측 효과는 아직 확인하지 않았습니다.

## 9. 개선 전후 성능

### 제목
pool 적용 후 반복 측정으로 효과를 확인해야 한다

### 화면에 표시할 핵심 내용
| 구분 | 개선 전 기록 | 개선 후 |
|---|---:|---:|
| `connect_ms` | 577.1ms | [추가 측정 필요] |
| `sql_log_ms` | 5.5ms | [추가 측정 필요] |
| `query_fetch_ms` | 115.1ms | [추가 측정 필요] |
| `total_ms` | 729.5ms | [추가 측정 필요] |

※ 개선 전은 사용자 제공 과거 1회 값. DB 조건·질의·캐시 조건을 맞춘 반복 비교인지 확인되지 않음.

### 넣으면 좋은 그림/표/코드
- 위 전후 표를 그대로 사용하되 개선 후 칸은 측정 후 채움
- 1회차/2회차/3회차 `connect_ms` 점 그래프 자리 `[추가 측정 필요]`
- 측정 시 동일 질문, 동일 limit, 동일 앱 프로세스 조건을 각주로 기록

### 발표 멘트
현재는 개선 전 과거 값만 표에 넣을 수 있습니다. warm-up과 pool을 적용한 뒤의 숫자는 아직 없기 때문에 비워 두었습니다. 오늘 이후 실제 앱에서 같은 질문을 적어도 세 번 실행하고 첫 검색과 후속 검색을 나눠 기록해야 합니다. 질문과 limit, 앱 프로세스 조건도 함께 맞춰야 변화가 pool 때문인지 비교할 수 있습니다. 이 표는 실측을 마친 뒤 갱신할 예정입니다.

## 10. 검색 품질 평가

### 제목
데이터 정합성 실험은 완료됐지만 정량 품질 평가는 남아 있다

### 화면에 표시할 핵심 내용
- 이미지 JOIN 문제: 947 chunk → 1,842행, 중복 chunk 그룹 407개
- 상관 subquery 수정 확인: 947행, 고유 chunk 947개, 중복 0
- 대표 질의 3개에서 limit 5/10 결과 중복 없음으로 기록
- Sonata 검색 평가셋 없음
- Hit@k / MRR 및 개선 전후 동일셋 비교: 결과 없음

### 넣으면 좋은 그림/표/코드
- JOIN 전후 행 수·중복 그룹 비교 막대
- 대표 질문 세 개의 결과 확인 상태 표
- “검색 결과 중복 검증”과 “검색 relevance 평가”를 서로 다른 상자로 표시

### 발표 멘트
실험 로그에서 확인한 중요한 결과는 이미지 JOIN이 같은 chunk를 여러 행으로 만들었다는 점입니다. 이미지 하나를 대표로 선택하는 상관 subquery를 적용한 SQL은 문서에 기록된 검증에서 chunk 중복을 없앴습니다. 하지만 이 검증은 결과 행의 정합성을 본 것이지 질문에 대한 관련성을 평가한 것은 아닙니다. Sonata의 정답 근거가 붙은 평가셋이 없어서 Hit@k나 MRR 결과는 아직 없습니다.

## 11. 최종 결과 및 배운 점

### 제목
데이터 분석 결과가 SQL과 연결 구조 개선으로 이어졌다

### 화면에 표시할 핵심 내용
```text
PDF / 적재 데이터 EDA
  → 검색·SQL 구조 추적
  → 중복 결과와 지연 구간 확인
  → 이미지 조회 SQL 및 연결 관리 개선
  → 실제 환경에서 성능·품질 재검증 예정
```
- 이미지 다중 JOIN 문제를 데이터 행 수와 대표 검색으로 확인
- 연결 생성 구간이 컸던 과거 측정에 대응해 pool + warm-up 적용
- 개선의 효과와 일반 검색 품질은 아직 측정 전

### 넣으면 좋은 그림/표/코드
- 문제 → 분석 → 판단 → 개선 → 검증 상태를 한 줄 타임라인으로 표현
- 각 단계의 실제 산출물 파일명: `EDA_REPORT.md`, `EXPERIMENT_LOG.md`, `car_manual.sql`, `DatabaseManager`

### 발표 멘트
이번 작업은 기능을 나열하는 데서 끝나지 않았습니다. EDA와 검색 결과 확인에서 이미지 JOIN이 chunk를 복제하는 문제를 찾았고, 실험으로 대표 이미지 선택 SQL의 결과를 검증했습니다. 성능 로그에서는 연결 확보 시간이 컸던 과거 관측을 바탕으로 pool과 warm-up을 적용했습니다. 이제 남은 단계는 실제 환경에서 개선 효과를 측정하고, 별도의 근거 기반 평가셋으로 검색 품질을 확인하는 것입니다.

## 12. 향후 작업 및 마무리

### 제목
다음 단계는 실제 측정과 재현 가능한 품질 평가다

### 화면에 표시할 핵심 내용
- [추가 측정 필요] warm-up 후 동일 검색 3회 이상 timing 비교
- M4 실행계획 확인 완료: index는 존재하지만 이번 실제 계획에서는 미선택 (반복/조건별 분석은 필요할 때 별도 수행)
- Sonata 근거 chunk 평가셋 작성, Hit@k / MRR 계산
- README 실행·환경·적재 안내 보완
- 발표 자료 최종화

### 넣으면 좋은 그림/표/코드
- 측정 / 품질 평가 / 제출 정리 3개 작업 항목 체크리스트
- 마지막 장에는 수치 대신 “검증할 항목”과 다음 일정 자리 `[발표 일정 자료 필요]`

### 발표 멘트
현재 확인된 구현과 문서 결과는 초안에 반영했습니다. HNSW index는 DB에 유효하게 존재하지만 이번 production 검색형 실행계획에서 선택되지는 않았습니다. 이후 우선순위는 고정 Sonata 평가셋의 Hit@5/MRR@5와 제출물 정리이며, 반복적인 실행계획 분석은 별도 성능 개선 실험이 필요할 때 수행합니다.

## PPT 작성에 필요한 자료 목록

- [ ] Streamlit 첫 화면 및 실제 검색 결과 화면 캡처 `[자료 필요]`
- [ ] 실제 사용자 질문과 반환된 chunk/image가 보이는 검색 화면 캡처 `[자료 필요]`
- [ ] 전체 시스템 구성도 작성
- [ ] 데이터 관계도: `car` / `car_manual_chapter` / `car_manual_chunk` / `car_manual_image`
- [ ] PDF 페이지별 텍스트 길이 또는 chapter 분포 그래프를 노트북에서 확인 후 캡처
- [ ] TF-IDF와 vector의 세 질의 순위 비교 표 또는 그래프
- [ ] 검색 성능 과거 측정 막대 그래프 작성, 단일 과거 관측 출처 각주 표시
- [ ] warm-up 적용 후 동일 검색 3회 이상 측정 표와 그래프 `[추가 측정 필요]`
- [ ] 개선 전후 pool timing 비교 `[추가 측정 필요]`
- [ ] HNSW index의 실제 DB 존재 여부와 `EXPLAIN (ANALYZE, BUFFERS)` 계획 `[추가 측정 필요]`
- [ ] 이미지 JOIN 전후 중복 행 수 비교 그림
- [ ] 코드 캡처: `search_manual()` → repository → `search_car_manual` 흐름
- [ ] 코드 캡처: `DatabaseManager.warmup()` 및 pool 대여·반환 흐름
- [ ] Sonata 정답 근거 평가셋과 Hit@k / MRR 결과 `[자료 필요]`
- [ ] 발표 일정 및 목표 발표 시간 `[자료 필요]`
