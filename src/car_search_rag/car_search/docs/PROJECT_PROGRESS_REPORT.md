# 프로젝트 분석 및 구현 진행 보고서

> **초안 / 검토용** — 저장소 문서와 코드에서 확인한 사실을 정리했다. 2026-10-04에 `app_kbj.py`의 Sonata 질문 경로를 Streamlit `AppTest`로 실제 실행해 API·DB·답변 및 pool timing을 확인했다. 이전 성능 값은 과거 사용자 제공 기록으로 이번 반복 측정값과 구분한다. 상세 결과는 `STREAMLIT_E2E_TEST.md`와 `EXPERIMENT_LOG.md`에 기록했다.

## 1. 분석 목적

이 프로젝트의 대상은 현대 Sonata 2026 사용자 매뉴얼을 대상으로 한 검색·RAG 애플리케이션이다. PDF에서 추출·분할한 매뉴얼 데이터를 검색 가능한 형태로 저장하고, 질문과 의미적으로 가까운 chunk를 검색하여 답변 생성에 연결하는 구조를 파악한다.

이번 진행에서는 두 종류의 문제를 확인했다.

- **검색 결과 무결성:** 매뉴얼 chunk와 이미지의 관계를 SQL로 결합할 때 한 chunk가 이미지 수만큼 중복되어 검색 결과 수와 순위 해석이 왜곡되는지 확인했다.
- **조회 지연:** PostgreSQL 내부 SQL 실행 시간과 Python 애플리케이션에서 관찰되는 지연의 차이를 분해하고, 매 SELECT마다 새 DB 연결을 생성하던 구조를 connection pool로 개선했다.

별도로 데이터 추출 상태와 TF-IDF 진단 결과를 정리했다. 현재 문서에는 Sonata 검색의 공식 golden set 기반 품질 평가 결과가 없으므로, 진단 실험을 최종 검색 품질 증명으로 해석하지 않는다.

## 2. 시스템 구조 파악

### 2.1 검색 전체 흐름

```text
사용자 질문
→ Streamlit (app_kbj.py)
→ CarManual / CarManualSearchService
→ 질문 embedding 생성
→ CarManualRepository.search_manual()
→ SqlSession.select_list("car_manual.search_car_manual", ...)
→ car_manual.sql의 search_car_manual
→ PostgreSQL + pgvector <=> 검색
→ 검색 chunk / 이미지 URL
→ 답변 생성 및 Streamlit 표시
```

### 2.2 Embedding

`car_manual_search_service.py`에서 query embedding 모델은 `text-embedding-3-small`, 차원 상수는 1536으로 지정되어 있다. `CarManualSearchService.search_manual()`은 질문을 `embedding_model.embed_query(question)`에 전달한 뒤 결과를 repository 검색에 넘긴다. 인덱싱 측 `car_manual_register_service.py`에도 `text-embedding-3-small` 설정이 있다.

2026-10-04 E2E에서 실제 질문 embedding API 호출이 성공했고 생성된 query vector 길이는 1536이었다. 검색 결과를 전달한 Chat API 답변 생성도 성공했다. 앱 모델 설정은 `gpt-6-luna`이며 상세 실행 결과는 `STREAMLIT_E2E_TEST.md`에 기록했다.

### 2.3 Vector Search

`car_manual.sql`의 `search_car_manual`은 차량 제조사·차종·연식 조건을 적용하고 `CAR_MANUAL_CHUNK_EMBED_VEC <=> :EMBEDDING` 거리로 정렬한다. SELECT 결과에는 `1 - distance` 형태의 `SIMILARITY`가 포함된다. `app_kbj.py` 호출은 limit 10이며, 서비스 메서드의 기본 limit은 5로 문서화되어 있다.

사용자가 제공한 실제 구성용 DDL에는 `car_manual_chunk.car_manual_chunk_embed_vec`에 대한 HNSW vector index가 정의되어 있다. 인덱스명은 `idx_car_manual_chunk_embed_vec_hnsw`, operator class는 `vector_cosine_ops`다. 저장소의 검색 SQL에는 schema/index DDL이 포함되어 있지 않아 앞서 저장소 코드만으로는 발견할 수 없었던 내용이다. 단, 아래 판단은 **제공된 DDL 기준**이며 이 DDL이 현재 운영 DB에 적용되어 있는지, 검색 시 planner가 해당 인덱스를 사용하는지는 아직 확인하지 않았다.

### 2.4 주요 클래스 / 함수 / SQL 관계

| 구성 요소 | 역할 |
|---|---|
| `app_kbj.py` | Streamlit UI와 `@st.cache_resource` 기반 `CarManual` 초기화 |
| `CarManual` | `CarManualSearchService`와 `SqlSession` 구성 |
| `CarManualSearchService.search_manual()` | 질문 embedding 생성 후 repository 호출 |
| `CarManualRepository.search_manual()` | embedding을 `Vector`로 감싸고 mapper statement 실행 |
| `car_manual.sql` / `search_car_manual` | 차량 조건, similarity 계산, 거리 정렬, limit 적용 |
| `SqlSession` | aiosql mapper 실행, connection 관리, 쿼리 로그·성능 로그 |
| `DatabaseManager` | row factory별 psycopg `ConnectionPool` 보관 및 대여 |

## 3. EDA 및 데이터 분석

### 3.1 데이터 구조

확인한 원본은 현대자동차 공식 매뉴얼 사이트에서 직접 다운로드한 Sonata 2026 (`DN8`, `ko_KR`) 국문 정적 PDF인 `data/DN8_2026_ko_KR.pdf`이다. [공식 자료 페이지](https://ownersmanual.hyundai.com/manual/쏘나타?langCode=ko_KR&countryCode=A99&projCode=DN8&year=2026&content=pdfDownload). 데이터 수집 API는 사용하지 않는다. 2026-10-04 재등록 후 현재 분석 대상 차량은 `CAR_ID = 20261004_000015`로 확인됐다. 과거 EDA·TF-IDF·M6·E2E 및 실험 기록의 `20261003_000014`는 당시 실행 ID로 보존한다. 전처리 문서 기준 핵심 데이터는 차량, chapter, chunk, image이며 chunk에는 페이지·chunk 정보와 embedding이 연결된다.

2026-10-04 재등록 후 사후 검증에서 현재 Sonata는 car 1건, chapter 10건, chunk 947건, embedding 947건(NULL 0, 모두 1536차원), image DB 955건으로 확인됐다. Storage `images/cars/hyundai/sonata/` object도 955개다. chunk 본문·ID·image URL 중복과 동일 차종/연식 car 중복은 각각 0건이다. 원본 PDF는 43,423,714 bytes, 508페이지이며 SHA-256은 `F83F44ABCF8F59C30FA4D0B0B419A8E7AACA54DA7D6F5C5FC9B3F83CAB650E23`이다.

사용자가 추가 제공한 PostgreSQL DDL 기준 스키마는 다음과 같다.

| 테이블 | 주요 구조 (DDL 기준) |
|---|---|
| `public.car` | `car_id`가 PK. 한글/영문 브랜드·차량명, 모델 연도와 생성·수정 메타데이터 보유 |
| `public.car_manual_chapter` | 복합 PK `(car_id, car_manual_chapter_id)`. chapter 번호·명칭·정렬 순번 보유 |
| `public.car_manual_chunk` | 복합 PK `(car_id, car_manual_chapter_id, car_manual_chunk_id)`. 페이지 번호, chunk 순번·본문, `public.vector` embedding 보유 |
| `public.car_manual_image` | 복합 PK `(car_id, car_manual_chapter_id, car_manual_image_id)`. 페이지·이미지 순번, URL, nullable 설명 보유. `(car_id, car_manual_chapter_id)`로 chapter를 참조하는 FK가 정의됨 |

chunk embedding 컬럼은 DDL에서 `public.vector NULL`로 선언되어 있으며 차원 길이를 지정한 `vector(1536)` typmod는 보이지 않는다. 따라서 코드의 1536차원 embedding 사용 설정과 별개로, 이 DDL 자체만으로 DB 컬럼 차원 제약을 확인할 수 없다. 제공된 DDL에서 명시적으로 보이는 참조 제약은 image→chapter FK이며, chunk→chapter FK는 선언되어 있지 않다. 각 테이블의 PK 제약도 정의되어 있다.

vector index 정의는 다음과 같다.

```sql
CREATE INDEX idx_car_manual_chunk_embed_vec_hnsw
ON public.car_manual_chunk USING hnsw
(car_manual_chunk_embed_vec vector_cosine_ops);
```

제공 DDL과 2026-10-04 현재 DB catalog에서 `idx_car_manual_chunk_embed_vec_hnsw`가 유효한 HNSW index이며 대상 컬럼은 `public.car_manual_chunk.car_manual_chunk_embed_vec`, operator class는 `vector_cosine_ops`임을 확인했다. 이는 SQL의 `<=>` cosine distance와 대응한다. 다만 실제 production 검색 형태를 재현한 이번 실행계획에서는 HNSW가 선택되지 않았다. `car_manual_chunk_pkey` Index Scan과 top-N heapsort가 관찰됐으며, 상세 및 관측 한계는 `EXPERIMENT_LOG.md`에 기록했다.

2026-10-04 재등록 후 Sonata `car_id=20261004_000015` 한정 읽기 전용 조회에서 chunk 947건, embedding 947건, NULL vector 0건, dimension 1536으로 확인했다. `hyundai / sonata / 2026` 차량 조건은 이 현재 `car_id` 한 건만 반환했다. 앞서 기록된 실행 당시 ID는 historical evidence로 유지한다.

### 3.2 데이터 확인 과정

`EDA_REPORT.md`와 `PREPROCESSING_SPEC.md`에 기록된 분석은 PDF 텍스트·페이지 분포, DB chunk/image 집계, 이미지 URL 다운로드·디코딩 및 PDF 이미지와의 대응 확인을 포함한다.

- PDF 508페이지에서 텍스트 추출 성공 508/508, `text=None` 0, 공백 텍스트 페이지 0, 예외 0으로 기록되어 있다.
- 페이지 텍스트 길이는 평균 1,019.55자, 중앙값 944자, 최소 21자, 최대 4,180자, 표준편차 582.36자다.
- level 1 chapter는 10개다. 텍스트가 짧았던 4, 6, 108, 500, 501페이지는 시각적으로 검토했으며, 짧다는 이유만으로 추출 오류로 분류하지 않았다.
- DB chunk의 페이지 범위는 1~508이며, 각 페이지에 적어도 하나의 chunk가 있다고 보고되어 있다. 이는 페이지 단위 존재 여부만 뜻하며 페이지 내용의 완전성이나 시각 자료 추출의 완전성을 증명하지 않는다.
- image 955건에서 URL 누락·중복, `page_no`/`image_no` 누락, `(page_no,image_no)` 중복 그룹은 각각 0으로 기록되어 있다. `image_desc`는 955건 모두 NULL이다.
- 저장소 URL GET 성공 955/955, 디코딩 성공 955/955로 기록되어 있으며 PNG 808건, JPEG 147건이다. 파일 크기 중앙값 38,718 bytes, 범위 435~318,762 bytes다.
- PDF 이미지 리소스 955건, 표시 인스턴스 1,038건, 고유 xref 및 byte hash 각 727건으로 기록되어 있다. DB 다운로드 이미지 hash와 PDF 추출 바이트가 727/727 일치했다고 보고되어 있다.

전처리 명세는 `pypdf` 텍스트 추출, PyMuPDF chapter·이미지 처리, `RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)` 등을 기술한다. 별도 공백 정규화와 OCR은 등록 경로에서 확인되지 않는다. PDF SHA-256 및 출처 URL은 기록했으나 최초 취득일과 공식 revision/edition 번호는 확인할 수 있는 기록이 없다. 문서에 적힌 전처리 의도와 실제 재현 실행 여부를 구분해야 한다.

### 3.3 TF-IDF 분석

`TFIDF_ANALYSIS.md`에 따르면 대상 corpus는 Sonata 2026의 DB chunk 947건이며 NULL·빈 문자열·공백 문자열은 제외했다. 중복 본문, NULL embedding/page는 0건으로 기록되어 있다. chunk 본문 길이는 평균·중앙값 607.35자, 최소 19자, 최대 800자다. TF-IDF 설정은 `ngram_range=(2,4)`, `min_df=1`, `max_df=1.0`이며 vocabulary는 175,451개다.

세 개의 근거 확인 질의에서 TF-IDF와 vector 검색을 비교했다.

| 질의 주제 | 근거 chunk | TF-IDF 관측 | Vector 관측 |
|---|---|---|---|
| 엔진 오일 | p23, chapter 1, chunk 39 | rank 2, score 0.179207 | rank 2, similarity 0.593598 |
| 후드 닫기 | p164, chunk 317 | 정답 근거가 top 5에 없음. 상위에는 SD 카드 제거 등 무관 결과 | rank 4, similarity 0.457099 |
| 배터리 단자 | p475, chunk 885 | rank 1, score 0.158059 | rank 1, similarity 0.469004 |

질의가 3개뿐인 탐색적 진단으로, 통계적·일반화 가능한 품질 비교가 아니다. TF-IDF는 분석용 baseline이며 서비스 검색 경로에 적용된 방식이 아니다.

### 3.4 검색 데이터에서 발견한 특징

기존 이미지 `LEFT JOIN`은 947개 chunk를 1,842행으로 늘리고, 407개 chunk 그룹에서 중복을 만들었다고 실험 로그에 기록되어 있다. 한 chunk에 최대 13개의 결합 결과가 있었다. 차량/chapter/page 조건만 JOIN alias 기준으로 바꾼 실험에서는 결과가 달라지지 않았다.

최종 SQL은 이미지 `LEFT JOIN` 대신 correlated subquery를 사용해 동일 차량·chapter·page의 이미지 중 `CAR_MANUAL_IMAGE_NO`가 가장 작은 URL 하나를 반환한다. 문서에 기록된 최종 확인에서 947행, distinct chunk 947개, duplicate chunk group 0, 최대 동일 chunk 반복 1이었다. limit 5/10과 엔진 오일·후드·배터리 질의에서도 중복 없는 결과가 기록되어 있다.

### 3.5 분석 결과와 RAG 개선의 관계

페이지·chunk·이미지 정합성 확인은 검색 결과가 중복되거나 관련 이미지가 부정확하게 붙는 문제를 줄이는 데 직접 연결된다. TF-IDF 비교는 키워드 중첩만으로 놓치는 질문이 있다는 진단 근거를 제공하지만, 3개 사례만으로 vector 검색이 항상 우수하다고 결론 내릴 수 없다. 다음 단계는 근거 chunk가 명시된 더 큰 질의 평가셋과 일관된 ranking 지표를 만드는 것이다.

## 4. RAG 검색 구조 분석

### 4.1 검색 파이프라인

`CarManualSearchService.search_manual()`이 query embedding을 만들고, `CarManualRepository.search_manual()`이 `SqlSession.select_list("car_manual.search_car_manual", params)`를 호출한다. repository는 embedding을 `Vector(embedding)` 형태로 전달한다. SQL은 차량 조건과 vector 거리 순위를 계산한다. `ask_manual()`은 대화 이력 기반 질문 처리 및 검색 결과를 답변 생성 흐름에 연결한다.

### 4.2 Embedding 방식

검색 질문과 등록 chunk 모두 `text-embedding-3-small`을 사용하도록 코드에 설정되어 있고, 검색 서비스의 embedding 차원 상수는 1536이다. 서비스는 검색 단계에서 질문 embedding을 만들며, 저장 chunk embedding 생성은 등록 서비스 경로에 있다.

### 4.3 pgvector 유사도 검색

SQL은 pgvector cosine distance 연산자 `<=>`로 정렬하고 `1 - distance`를 similarity로 반환한다. 실 DB catalog에는 유효한 HNSW index가 존재하지만, 2026-10-04 실제 SQL 형태의 `EXPLAIN`에서는 해당 index를 선택하지 않고 `car_manual_chunk_pkey` Index Scan 후 top-N heapsort를 사용했다 (Planning 5.835 ms, Execution 15.178 ms). 이는 단일 실행계획이며 planner 선택 이유는 데이터 규모만으로 단정하지 않는다.

M4 완료 기준을 Sonata 범위에서 재점검한 결과는 다음과 같다.

| 기준 | 판정 | 확인 근거 |
|---|---|---|
| 문서/Chunk 구조 결정 | 충족 | page 단위 추출 및 `RecursiveCharacterTextSplitter(800, 150)`, `page_no`·순차 `chunk_no` 기록 |
| metadata 설계 | 충족 | 차량/chapter/page/chunk 본문·순번 및 검색결과 image URL 구조 확인 |
| 임베딩 생성 | 충족 | Sonata chunk 947개 모두 vector 보유, 차원 1536, NULL 0 |
| Vector DB 적재 및 조회 | 충족 | 재등록 전 M4 기록은 당시 `car_id=20261003_000014` 범위의 실행계획/조회 결과이며, 2026-10-04 재등록 후 현재 `car_id=20261004_000015`의 chunk·embedding 적재도 사후 검증 |

HNSW index가 이번 plan에서 선택되지 않았다는 관찰은 별도로 남긴다. 이는 해당 기준의 적재나 조회가 실패했다는 의미가 아니다.

### 4.4 검색 결과 처리

최종 쿼리는 chunk당 이미지 URL을 최대 하나 반환하도록 고쳐 중복 row가 검색 순위 결과를 부풀리지 않도록 했다. `CarManualSearchService`는 조회된 chunk를 검색 결과로 전달하고 `ask_manual()`이 답변 생성 흐름에 사용한다. 검색 결과의 인용·근거 표기 품질 및 답변 사실성은 별도 정량 평가가 아직 필요하다.

## 5. 검색 성능 분석

### 5.1 측정한 지표

`SqlSession.select_list()`의 timing 로그는 다음 구간으로 나뉜다.

- `connect_ms`: `_connection()` 진입부터 connection을 확보하기까지. 현재 pool 적용 후에는 대여 시간이 중심이며 첫 pool 생성/warm-up이 동반되면 그 비용도 포함될 수 있다.
- `sql_log_ms`: `_log_query()` 수행 시간. SELECT는 원본 parameters로 `mogrify()`해 전체 vector SQL 본문을 로그에 렌더링한다.
- `query_fetch_ms`: `rows = list(query(connection, **(parameters or {})))` 수행 시간. SQL 실행뿐 아니라 응답 전달, 드라이버 decode, row 구성, 전체 fetch 및 mapper 처리 비용이 포함될 수 있다.
- `total_ms`: `select_list()` 전체 소요 시간으로 위 구간 외 메서드 내부 작업도 포함한다.

SELECT `QUERY` 로그는 `full_vector_sql=True`로 전체 embedding 벡터를 렌더링하고, 하단 `PARAMS`는 `_sanitize_log_value()`로 축약한다. 이 로깅 수정은 로그 표현만 바꾸며 DB 실행 parameters/SQL 실행 방식은 유지하도록 구현되어 있다.

### 5.2 DB 내부 실행 시간

사용자가 이전 대화에서 전달한 동일 SQL의 `EXPLAIN (ANALYZE, BUFFERS)` 기록은 Planning Time 0.459ms, Execution Time 12.467ms다. 이 보고서 작성 시점에 해당 명령을 DB에서 다시 실행하지 않았다. PostgreSQL `Execution Time`은 서버 내부 실행 측정치이며 애플리케이션과 서버 사이의 네트워크 왕복 및 Python fetch/decode 전체를 포함하는 값으로 해석하면 안 된다.

### 5.3 Python 애플리케이션 측 시간

사용자가 전달한 과거 측정 예시는 다음과 같다.

```text
connect_ms=577.1
sql_log_ms=5.5
query_fetch_ms=115.1
total_ms=729.5
```

이 값은 저장소에 재현 가능한 원시 로그 파일로 확인되지 않았고, 이번 작업에서 재측정한 값도 아니다. 이전 분석에 공유된 다른 한 회 관측으로 `connect_ms=671.4`, `sql_log_ms=6.5`, `query_fetch_ms=392.1`, `total_ms=1109.1`도 있으나 같은 조건의 반복 비교인지 확인되지 않는다.

### 5.4 병목 가설

이전 구조에서는 일반 조회마다 `DatabaseManager.connect()`가 `psycopg.connect()`를 수행했으므로 DNS/TCP/TLS/authentication 및 adapter 초기화 비용이 연결 구간에 포함될 가능성이 있었다. 서버 측 실행 12.467ms와 Python 측 fetch 구간의 차이는 네트워크 왕복, 결과 전송, psycopg decode, row 생성, aiosql 처리 등을 포함할 수 있다. 실제로 각 하위 작업을 별도 계측한 것은 아니므로 원인을 하나로 확정하지 않는다.

2026-10-04 Streamlit `AppTest`에서 warm-up 이후 동일 질문 3회의 `connect_ms`는 0.0–0.1ms로 기록됐다. 이는 pool 대여 경로가 동작한 관측 근거다. 과거 값과 실행 조건이 완전히 통제된 비교가 아니고 `query_fetch_ms`/`total_ms` 편차도 있으므로 전체 개선 효과나 query/fetch 원인은 추가 검증이 필요하다.

## 6. Connection Pool 개선

### 6.1 기존 문제

기존 일반 조회 연결 경로는 `DatabaseManager.connect()`에서 물리 psycopg 연결을 만들고 사용 후 닫는 방식이었다고 앞선 코드 분석에서 확인되었다. 매 검색에 연결 생성 비용이 반복될 가능성이 있어 pool 적용 대상으로 삼았다.

### 6.2 ConnectionPool 적용

`DatabaseManager`는 `psycopg_pool.ConnectionPool`을 manager 생명주기 동안 보관하고 재사용한다. 기본 크기는 min 1 / max 5이며 `DB_POOL_MIN_SIZE`, `DB_POOL_MAX_SIZE` 환경변수로 조정 가능하다. pool 생성은 lazy이며 `warmup()` 또는 첫 connect에서 필요한 pool을 만든다. `camel_case_keys`에 따라 row factory가 달라지므로 bool 키로 별도 pool을 보관한다.

### 6.3 warm-up 적용

`app_kbj.py`의 `@st.cache_resource` 함수에서 `CarManual`과 `SqlSession`을 만든 뒤 `database_manager.warmup(camel_case_keys=...)`을 호출한다. cache resource 최초 생성 시 pool을 준비하고, 매 검색마다 warm-up을 반복하지 않는 구조다. `warmup()`은 pool을 얻고 `pool.wait()`로 최소 연결 준비를 기다린다.

2026-10-04 실제 앱 스크립트의 `AppTest` 실행에서 `DB POOL created min_size=1 max_size=5` 로그와 warm-up 이후 검색 성공을 확인했다. 사용자는 별도 실제 앱 `http://localhost:8501`에서 UI 변경 전 Sonata 질문/답변을 수동 확인했고, 변경 후 출처·이미지 UI의 브라우저 재검증은 대기 중이다. 자동 테스트용 8517 서버와 사용자 앱 8501은 별도 인스턴스다.

### 6.4 transaction 처리

`SqlSession.transaction()`은 하나의 `DatabaseManager.connect()` context에서 connection 하나를 빌려 transaction 블록 전체에 활성 connection으로 둔다. 정상 종료 때 commit, 예외 때 rollback 후 예외를 다시 전달하고, 마지막에 pool context가 connection을 반환한다. transaction 중간에 새 connection으로 바뀌지 않으며 직접 `connection.close()`로 물리 연결을 닫지 않는다. nested transaction 미지원 정책은 유지한다.

### 6.5 변경 범위

확인한 구현은 `DatabaseManager` psycopg 경로와 `SqlSession` 연결 관리에 해당한다. 별도 `PGEngine` 경로와 `PersonalDatabaseManager`는 이번 pool 적용 대상이 아니며 해당 경로는 변경하지 않은 것으로 코드에서 확인했다. 의존성은 `pyproject.toml`의 `psycopg[binary,pool]>=3.3.6` 선언으로 확인된다. SELECT timing 및 full vector SQL logging도 유지된다.

## 7. 검증

### 7.1 정적 검증

2026-10-04 `.venv`의 Python으로 `app_kbj.py`, `car_manual.py`, `car_manual_search_service.py`, `car_manual_repository.py`, `database_manager.py`, `sql_session.py`에 `py_compile`을 실행해 통과했다. Streamlit 1.64.0, psycopg 3.3.6, `psycopg_pool`, `pgvector`, `langchain_openai` import도 통과했다.

### 7.2 Mock 테스트

앞선 작업 기록에는 mock 기반 pool/warm-up/transaction 검증이 수행되었다고 사용자가 제공한 진행 내역에 적혀 있다. 해당 mock 테스트 산출물이나 결과 로그는 저장소에서 확인하지 못했으며 이번 turn에 재실행하지 않았다. 따라서 독립 재현 가능한 테스트 완료로 확대 해석하지 않는다.

### 7.3 실제 환경 테스트

- warm-up 후 동일 질문 3회 timing은 자동 검증 기록이며, 사용자 브라우저 8501의 성능값이 아니다: `connect_ms=0.1/0.1/0.0`, `sql_log_ms=2.9/3.6/3.5`, `query_fetch_ms=769.7/119.7/254.1`, `total_ms=810.0/162.1/653.6`. 결과는 `STREAMLIT_E2E_TEST.md` 참조.
- Streamlit resource warm-up, Sonata 질문 입력, embedding/pgvector 검색, 기대 chunk Top-5 포함, Chat 답변은 `AppTest` 실행에서 확인.
- metadata UI 변경 후 실제 DB/API를 쓰는 두 질문 AppTest에서 답변 성공, source row 전달 및 6 image elements를 확인했다. 이번 엔진오일 재실행의 Top-5에는 기대 p.463/chunk 866이 없었으며 이전 실행의 3위 결과와 달라졌다. USB 검색 결과 image URL 3개를 반환했다. mock UI 테스트에서는 p.463/chunk 866 표시, 링크와 preview, 연속 질문 metadata 격리를 확인했다. 상세 결과는 `STREAMLIT_E2E_TEST.md` 참조.
- 실제 DB transaction commit/rollback 및 connection 재대여 확인: **아직 검증하지 않음**.
- pool 연결에서 vector parameter 검색이 성공해 pgvector 어댑터 경로가 동작함을 확인. `register_vector()` callback의 physical connection별 호출 횟수는 직접 계측하지 않음.
- 제공된 DDL에는 HNSW vector index가 정의되어 있음을 확인했다. 실제 DB catalog에 적용되어 있는지와 `EXPLAIN (ANALYZE, BUFFERS)`에서 사용되는지는 **아직 검증하지 않음**.

## 8. 검색 품질 평가

### 평가 데이터

`RAG_EVALUATION_REPORT.md`는 핵심 `car_search`에 대해 query와 정답 근거 ID로 구성된 검증 데이터셋을 확인하지 못했다고 명시한다. TF-IDF 문서에는 세 개의 근거 확인 질의가 있으나 공식 평가셋으로 정의되어 있지 않다.

### 평가 방식

세 질의에 대해 TF-IDF와 vector 순위를 비교한 탐색적 분석이 있다. core Sonata 검색의 Hit@k, MRR 또는 동일 평가셋의 before/after 비교 결과는 기록되어 있지 않다. 답변 생성의 정확도/근거 충실도 평가도 확인되지 않는다.

### 실험 조건 및 결과

TF-IDF 비교의 실제 설정과 세 질의 결과는 3.3절에 정리했다. 이 비교는 answer generation 없이 검색 순위를 관찰한 것이다. `EXPERIMENT_LOG.md`의 이미지 JOIN 검증은 중복 row 및 검색 결과 유일성을 확인한 데이터 정합성 실험이며, 검색 relevance 품질 평가와 구별된다.

### 해석 및 한계

세 사례만으로 일반적인 검색 성능 우열을 결론 내릴 수 없다. 평가셋의 구성·정답 근거 정의·검색 조건을 고정한 뒤 Hit@k/MRR 및 답변 근거성 검토를 수행해야 한다. `zzong_santafe_lag`의 별도 Santa Fe 프로젝트 수치는 Sonata `car_search` 성능 결과로 합산하지 않았다.

## 9. 현재까지의 결과

| 문제 | 분석 | 변경 | 확인 결과 |
|---|---|---|---|
| 이미지 결합으로 검색 chunk가 중복될 수 있음 | 기존 `LEFT JOIN` 결과 1,842행/947 chunk, 중복 그룹 407개로 기록 | 이미지 JOIN을 제거하고 페이지 내 최소 image number를 반환하는 correlated subquery 사용 | 문서 기록상 947행, distinct chunk 947, 중복 그룹 0. 검색 limit 5/10 예시에서도 중복 없음 |
| SELECT SQL 로그에서 embedding이 축약됨 | 로그 formatter가 vector를 sanitize한 표현을 SQL 렌더링에 사용 | SELECT에 `full_vector_sql=True`, 원본 parameters로 QUERY 렌더링; PARAMS는 sanitize 유지 | 이번 E2E에서 SELECT timing/result logs를 확인. SQL 본문과 full vector는 문서에 복사하지 않음 |
| 서버 실행 시간과 앱 지연에 큰 차이가 있음 | 사용자 제공 EXPLAIN 12.467ms와 Python 구간 측정 비교 | `connect_ms`, `sql_log_ms`, `query_fetch_ms`, `total_ms` 계측 및 connection pool 적용 | E2E 3회 timing은 별도 기록. connect는 낮게 관찰됐지만 query/fetch 및 total 변동으로 전체 개선률은 단정하지 않음 |
| 첫 검색에서 pool 연결 준비가 필요함 | `@st.cache_resource` 객체 생명주기 확인 | resource 생성 때 `DatabaseManager.warmup()` 호출 | AppTest에서 pool 생성 로그 및 검색별 connect 0.0–0.1ms 확인. 다른 timing은 변동해 전체 개선 효과로 일반화하지 않음 |
| 실제 Sonata 질문의 검색·답변 및 출처 표시 확인 필요 | AppTest에서 실제 검색 metadata 전달 단계를 추가 확인 | `ask_with_sources()`와 tool artifact를 통해 page/chunk/image를 UI로 전달 | 답변·출처 UI·이미지 preview 요소는 AppTest 통과. 기대 chunk 검색 순위는 실행에 따라 달라졌고, 수정 후 사용자 브라우저 재확인 대기 |
| Sonata 검색 품질을 정량 보고할 근거가 부족함 | 평가 문서에서 gold query/evidence set 부재 확인 | 이번 단계에서 평가셋 생성은 미실시 | Hit@k/MRR 및 답변 품질 결과 미완료 |

## 10. 남은 작업

- [x] UI 변경 전 실제 브라우저(8501)에서 Sonata 질문과 USB 이미지 링크 동작을 사용자 확인
- [ ] metadata UI 변경 후 실제 브라우저(8501)에서 page/chunk 출처·image preview·레이아웃 재검증
- [ ] 실제 DB로 pool 대여/반환, transaction commit/rollback, 예외 후 재대여 검증
- [ ] 각 row factory pool에서 결과 key 형식이 세션 간 섞이지 않는지 확인
- [ ] 실제 physical connection 생성 시 `register_vector()` callback 동작 확인
- [x] Sonata 대상 DB catalog에서 `idx_car_manual_chunk_embed_vec_hnsw` 존재 및 유효성 확인
- [x] production 검색 형태에 `EXPLAIN (ANALYZE, BUFFERS, VERBOSE)` 실행; 이번 계획에서 HNSW 미선택 및 주요 plan node 기록
- [x] Sonata chunk/embedding 적재 건수, NULL 수, vector dimension 및 차량 조건의 단독 `car_id` 매핑 재확인
- [ ] Sonata 매뉴얼 질의와 정답 chunk/evidence ID를 갖춘 검색 평가셋 작성
- [ ] 고정 평가셋에서 Hit@k/MRR 및 답변 근거성 평가 수행, 설정과 결과 기록
- [ ] OCR·문자열 정규화·dedup 적용 필요성을 결정하고 원본 PDF 대비 chunk 본문 검증 범위를 보완하기
- [ ] `image_desc`가 전부 NULL인 현재 상태에서 이미지 설명 생성/사용 필요성 검토
- [ ] 루트 README를 프로젝트 설치·환경 설정·실행·데이터 적재 절차에 맞게 보강
- [ ] PPT 초안의 성능 placeholder 및 E2E 상태를 이번 측정 결과로 갱신
- [ ] GitHub 원격 저장소와 제출 브랜치/커밋 상태 확인

## 11. 제출물 기준 현재 상태

| 제출 항목 | 상태 | 근거 | 추가 작업 |
|---|---|---|---|
| 데이터셋 + 전처리 명세서 | 부분 완료 | `data/DN8_2026_ko_KR.pdf`, `PREPROCESSING_SPEC.md`, `DATA_SPEC.md` | 명세의 미확정 정책과 실제 재현 적재 절차 보완 |
| 분석 노트북 / EDA / 통계 / TF-IDF / 실험 결과 보고서 | 부분 완료 | `notebooks/kbj_sonata_pdf_eda.ipynb`, `notebooks/kbj_sonata_tfidf_analysis.ipynb`, `EDA_REPORT.md`, `TFIDF_ANALYSIS.md`, `EXPERIMENT_LOG.md`, `STATISTICAL_TEST_PLAN.md` | 평가셋 확장, 통계 검정 실행 결과 및 재현 경로 보강 |
| RAG 파이프라인 코드 | 완료 (코드 존재 기준) | `car_manual_search_service.py`, `car_manual_repository.py`, `car_manual.sql`, `sql_session.py` | 실제 서비스 환경 smoke test는 별도 미완료 |
| 인덱싱 코드 | 부분 완료 | `car_manual_register_service.py`, `car_manual.sql`의 등록 statement | 실제 재적재 재현 로그와 전처리 검증 보완 |
| 적재 로그 | 미완료 | 저장소에서 재현 가능한 별도 적재 로그를 확인하지 못함 | 입력 파일, 실행 조건, 건수, 실패/재시도 정보를 기록 |
| RAG Chain 코드 | 부분 완료 | `CarManualSearchService.ask_manual()` 및 Streamlit 통합 경로 | 통합 실행과 답변 근거성 검증 결과 추가 |
| 검색 품질 평가 리포트 | 미완료 | `RAG_EVALUATION_REPORT.md`에서 core Sonata 평가 데이터/Hit@k/MRR 미확인 명시 | 고정 평가셋 및 정량·정성 결과 작성 |
| Streamlit 통합 앱 | 부분 완료 | `app_kbj.py`, `@st.cache_resource`, warm-up 호출 코드 | 실제 앱 기동, DB 연결 및 검색 확인 |
| GitHub 저장소 | 확인 필요 | 현재 로컬 저장소 파일은 확인. 원격 URL·제출 상태는 이 조사에서 검증하지 않음 | remote, 권한, 최종 push/commit 확인 |
| README | 미완료 | 루트 `README.md` 크기 17 bytes, 제목만 확인 | 실행·환경변수·데이터/인덱싱·평가 절차 작성 |
| PPT | 미완료 | 저장소에서 `.pptx` 제출물을 찾지 못함 | 발표 자료 작성 |

## 12. 발표 때 설명할 수 있는 핵심 흐름

1. 프로젝트는 Sonata 2026 매뉴얼 PDF를 페이지·chunk·이미지 단위로 처리하고, chunk embedding을 저장해 질문 기반 검색에 사용한다.
2. 검색 질문도 `text-embedding-3-small`로 1536차원 embedding을 만들고, PostgreSQL pgvector의 `<=>`로 가까운 chunk를 찾는다.
3. 이미지 JOIN이 한 chunk를 여러 결과 행으로 복제하는 데이터 정합성 문제가 있어, 페이지에서 대표 이미지 URL 하나를 고르는 correlated subquery로 바꾸었다.
4. EDA 기록에서는 PDF 508페이지의 텍스트 추출과 947 chunk/955 image 데이터의 대응을 검사했지만, 페이지별 chunk 존재만으로 내용의 완전성을 보장하지 않는다는 한계가 있다.
5. 세 개 질의의 TF-IDF 비교에서는 후드 닫기 질문의 근거가 TF-IDF 상위 5개에 들지 않았고 vector는 4위였다. 이는 사례 진단이지 일반 성능 결론은 아니다.
6. 서버 `EXPLAIN` 실행 시간은 약 12.467ms였지만 사용자 제공 Python 로그의 전체 지연은 약 729.5ms였다. 서버 실행 시간만으로 애플리케이션 지연을 설명할 수 없어서 연결·로그 렌더링·실행 및 fetch 구간을 따로 계측했다.
7. 기존 연결 생성 비용을 줄이려고 manager가 pool을 재사용하게 했고, Streamlit cached resource 초기화 때 warm-up하도록 연결했다. E2E 3회에서 connect_ms 0.0–0.1ms를 관찰했지만 query/fetch·total 변동과 실행 조건 차이 때문에 전체 성능 개선률로 단정하지 않았다.
8. core Sonata 검색의 고정 평가 데이터셋과 Hit@k/MRR 결과가 없으므로, 다음 품질 작업은 근거 chunk가 정의된 평가셋을 만들고 동일 조건에서 반복 평가하는 것이다.

### M1 데이터 수집 및 재등록 상태 (2026-10-04)

M1은 현재 근거 기준 완료 가능으로 판정한다. 공식 Hyundai PDF URL, 원본 파일명·크기·페이지 수·SHA-256, 기존 등록 코드에 의한 재등록, 실제 DB/Storage 적재 수와 중복 점검 결과가 확보됐다. 최초 취득일과 공식 revision/edition 번호는 확인할 수 있는 근거가 없어 미기록이며, 이는 데이터 수집 API 구현의 미완료를 뜻하지 않는다. 실제 등록 종료 시 데이터 적재 후 `_print_summary()`의 콘솔 출력에서 Windows cp949 `UnicodeEncodeError`가 발생했으나, 사후 검증은 적재 정상 완료를 확인했다. 등록 재시도는 하지 않았다. 상세 결과는 `EXPERIMENT_LOG.md`에 기록했다.

재등록 정책은 파일을 입력 경로 `data/DN8_2026_ko_KR.pdf`에서 읽고, DB에는 자동 idempotent upsert를 적용하지 않는 방식이다. car row가 없는 경우 `FN_GET_BIZ_ID('CAR')`로 새 `car_id`를 발급하며 이번 ID는 `20261004_000015`다. Storage는 `cars/{brand}/{model}/{image_name}` 및 `upsert=true`를 사용한다. 경로에 car_id/사용자 ID가 없어 같은 차종 등록자가 prefix를 공유할 수 있고, 같은 object key 외의 이전 object 정리는 자동으로 보장되지 않는 운영상 한계가 있다.
