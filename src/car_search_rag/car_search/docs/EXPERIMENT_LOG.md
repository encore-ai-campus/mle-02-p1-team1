# 실험 로그

## 2026-10-04 — Sonata M4 Vector DB 적재 및 실행계획 검증

### 범위 및 방법

대상은 Hyundai Sonata 2026, `car_id = 20261003_000014`이다. 아래 집계는 `public.car_manual_chunk`에서 해당 `car_id`만 조회했으며, 차량 식별 매핑은 `public.car`의 `hyundai / sonata / 2026` 조건으로 확인했다. 모든 DB 작업은 `SET TRANSACTION READ ONLY` 이후 SELECT 또는 `EXPLAIN (ANALYZE, BUFFERS, VERBOSE)`만 실행했다. DDL, 데이터, index 및 planner 설정은 변경하지 않았다.

### 적재 상태

| 확인 항목 | 실측 결과 |
|---|---:|
| chunk 전체 | 947 |
| embedding 존재 | 947 |
| embedding NULL | 0 |
| vector dimension 최소/최대 | 1536 / 1536 |

차량 검색 조건 `CAR_BRAND_ENG_NM='hyundai'`, `CAR_ENG_NM='sonata'`, `CAR_MODEL_YR=2026`은 `car_id=20261003_000014` 한 건만 반환했다. 실행계획에 사용한 query vector도 해당 Sonata chunk에 이미 저장된 실제 embedding 하나를 선택했다.

### Index 및 실행계획

현재 DB catalog에서 `idx_car_manual_chunk_embed_vec_hnsw`가 한 건 확인됐고 `indisvalid=true`, `indisready=true`였다. 정의는 `public.car_manual_chunk`의 `car_manual_chunk_embed_vec`에 대한 `USING hnsw (... vector_cosine_ops)`다. 운영 검색 SQL의 vector 연산자는 `<=>`이고, 해당 거리로 `ORDER BY` 한 다음 `LIMIT 10`을 적용한다.

동일한 Sonata 차량 조건, JOIN, 이미지 correlated subquery, similarity 계산, `<=>` 정렬 및 `LIMIT 10`을 포함한 SELECT에 실제 저장 embedding을 넣어 `EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT JSON)`을 실행했다.

- HNSW 선택: **아니오**. catalog index는 유효하게 존재했지만 이번 실행계획에는 해당 index가 나타나지 않았다.
- 주요 node: `Limit` → `Sort (top-N heapsort)` → `Nested Loop`; `car_pkey`, `car_manual_chunk_pkey`, `car_manual_image_pkey`를 이용한 `Index Scan`이 포함됐다.
- `car_manual_chunk` 접근은 `car_manual_chunk_pkey` Index Scan이었다. vector distance 정렬은 별도의 HNSW scan이 아니라 top-N sort로 수행됐다.
- Planning Time: **5.835 ms**
- Execution Time: **15.178 ms**

이는 HNSW가 고장났거나 검색 실패했다는 뜻은 아니다. 이 쿼리의 필터·JOIN·LIMIT 및 현재 데이터/통계 등 여러 조건을 planner가 고려해 다른 경로를 고른 결과로 기록하며, 원인을 데이터 규모 하나로 단정하지 않는다. 실행계획 시간은 이번 한 번의 관측값이다.

### 판정

- 문서/Chunk 구조 결정: 충족 — page metadata 및 `RecursiveCharacterTextSplitter(800, 150)` 기반 chunk 구조가 코드와 scope 문서에 기록됨.
- metadata 설계: 충족 — `car_id`, chapter, page, chunk 순번·본문 및 검색 결과의 image metadata 구조가 확인됨.
- 임베딩 생성: 충족 — Sonata chunk 947건 모두 1536차원 vector 보유.
- Vector DB 적재 및 조회: 충족 — Sonata 범위 적재 건수와 검색 SQL, 실제 읽기 전용 검색 경로를 확인함.
- HNSW 인덱스: 유효하게 존재하나 이 실행계획에서 선택되지 않음. 이는 별도 관찰 결과이며 M4 적재/검색 성공 여부와 구분함.

EDA, TF-IDF, 검색 평가 과정에서 확인한 주요 측정값과 문제를 날짜순으로 누적한다. 각 기록은 실제 실행 결과만 반영한다.

## 2026-10-04 — Sonata Streamlit 질문 E2E 및 warm-up pool 측정

### 목적과 범위

`app_kbj.py`에서 Sonata 질문이 embedding, PostgreSQL/pgvector 검색, Chat API 답변으로 이어지는지 확인했다. 대상은 Hyundai Sonata 2026, `car_id = 20261003_000014`로 제한했다. 앱 질문 경로의 검색 SQL만 실행했으며 PDF 재등록, chunk/embedding 적재, INSERT, UPDATE, DELETE는 실행하지 않았다. 사전 읽기 전용 SELECT에서 `hyundai / sonata / 2026` 조건에 일치하는 차량은 해당 `car_id` 한 건이었다.

Streamlit 서버는 포트 8517에서 시작했고 health endpoint가 `ok`를 반환했다. 실행 환경에 브라우저 surface가 없어 widget 상호작용과 화면 검증은 실제 `app_kbj.py`를 Streamlit `AppTest`로 실행해 수행했다. 이 방식으로 일반 브라우저에서 직접 시연한 것은 아니다.

### E2E 검색 결과

질문: “엔진 오일량을 확인할 때 레벨 게이지를 다시 뽑기 전에 무엇을 해야 하나요?”
기대 근거: PDF p.463 / chunk_no 866.

- `text-embedding-3-small` embedding API 호출 성공, query embedding 길이 1536.
- `car_manual.search_car_manual` SELECT 성공, 10행 반환. 반환된 모든 행의 `car_id`는 `20261003_000014`였다.
- 기대 chunk 866은 3위, p.463, similarity 0.527330으로 Top-5에 포함됐다.
- Chat API 호출과 최종 답변 출력 성공. 답변: “레벨 게이지를 뽑아 깨끗한 헝겊으로 닦은 뒤, 다시 꽂으세요. 그다음 다시 뽑아 엔진 오일량을 확인하면 됩니다.”
- 결과 row에는 페이지와 image URL이 포함되고 prompt 문맥에도 전달됐지만, 실제 UI 답변에는 page 출처나 이미지 URL이 표시되지 않았다. app은 답변을 markdown으로 표시할 뿐 별도 source/image component를 렌더링하지 않는다.
- 실행 상세와 Top-5 결과는 `STREAMLIT_E2E_TEST.md`에 기록했다.

### USB 위치 질문으로 그림 링크 동작 확인

- 추가 질문 “차량 usb 위치 알려줘”를 1회 실행했다. 이 질문은 이미지 UI 동작 확인용이며 공식 M6 평가 문항이 아니다.
- 검색 Top-10은 Sonata `car_id=20261003_000014`만 반환했고, 7개 row에 image URL이 있었다. 주요 상위 결과는 p.236/chunk 429, p.12/chunk 22, p.243/chunk 442였다.
- 답변은 앞좌석·뒷좌석 USB 위치를 설명하고 USB 포트 및 기능 전환 그림 링크를 포함했다. 실제 이미지 preview는 나오지 않았다. 앱은 답변을 markdown으로 표시하므로 그림 링크가 텍스트 링크로 제공되는 상태다.
- USB 질문은 사전 정답 page/chunk를 지정하지 않아 검색 관련성 점수는 계산하지 않았다.

### ConnectionPool / warm-up timing

앱 resource 초기화에서 `DatabaseManager.warmup()`이 실행됐고 `DB POOL created min_size=1 max_size=5` 로그를 확인했다. 동일 질문의 3회 검색 timing은 `select_list()` 로그 기준이다.
Pool에서 생성된 연결로 vector parameter 검색이 성공해 pgvector 어댑터 경로가 동작함을 확인했다. 다만 callback 호출 횟수를 직접 계측하지는 않았다.

| 회차 | connect_ms | sql_log_ms | query_fetch_ms | total_ms |
|---:|---:|---:|---:|---:|
| 1 | 0.1 | 2.9 | 769.7 | 810.0 |
| 2 | 0.1 | 3.6 | 119.7 | 162.1 |
| 3 | 0.0 | 3.5 | 254.1 | 653.6 |

비교용 과거 측정(사용자 제공, pool/warm-up 이전): `connect_ms=577.1`, `sql_log_ms=5.5`, `query_fetch_ms=115.1`, `total_ms=729.5`. connect 구간은 이번 세 회에서 낮게 기록되어 warm-up pool 대여 경로 동작을 확인했지만, query/fetch와 total은 편차가 있어 전체 성능 개선으로 일반화하지 않는다. 과거 기록과의 실행 조건 통제도 확인되지 않았다. 최초 resource/warm-up 시간은 `select_list()` timing에 포함되지 않는다.

### 결론 및 한계

핵심 질문 E2E의 embedding → Sonata 한정 vector 검색 → 근거 chunk 회수 → Chat 답변 흐름은 성공했다. page citation은 답변에 없었다. USB 보조 질문은 그림 링크 표기까지 반환했으나 이미지 preview와 브라우저 상호작용은 환경 제약으로 확인하지 못했다. 이번 timing은 pool의 연결 대여 경로와 로그 수집을 확인하기 위한 3회 결과이며 추가 튜닝이나 장시간 분석은 수행하지 않았다.

## 2026-10-03 — 소나타 PDF 이미지·검색 JOIN 전수검증

### 작업 목적

`data/DN8_2026_ko_KR.pdf`와 Sonata 2026 (`CAR_ID = 20261003_000014`)에 등록된 이미지 데이터의 정합성을 확인하고, 현재 검색 SQL의 페이지 이미지 JOIN이 검색 결과 행에 미치는 영향을 검사했다. DB 조회는 대상 차량으로 제한한 SELECT만 사용했다.

### 실제 측정값

- `CAR_MANUAL_IMAGE`: 955행, 이미지가 연결된 PDF 페이지 368개.
- URL NULL/빈 값: 0/0. 중복 URL: 0. `(page_no, image_no)` 중복 그룹: 0. `page_no`/`image_no` NULL: 0/0.
- `image_desc` NULL: 955행(100%). 페이지별 이미지 수는 1개 107페이지, 2개 90페이지, 3개 83페이지, 4개 57페이지, 5개 15페이지, 6개 9페이지, 7개 3페이지, 8개 2페이지, 12개 1페이지, 13개 1페이지였다.
- Supabase 이미지 URL HTTP GET: 955/955 성공(HTTP 200), 디코딩 955/955 성공, 실패 0. PNG 808개, JPEG 147개. 파일 크기 중앙값 38,718 bytes, 범위 435–318,762 bytes. 모든 이미지의 디코딩된 너비와 높이는 양수였다.
- PDF 이미지 리소스가 있는 페이지: 368개. 인스턴스 1,038개, PDF 리소스 행 955개, unique xref 727개 및 추출 바이트 SHA-256 unique 727개. DB에서 받은 이미지도 SHA-256 unique 727개였고 PDF 추출 이미지와 727/727 일치했다.
- PDF 페이지별 리소스 수와 DB 이미지 수 불일치: 0페이지. PDF에만 있거나 DB에만 있는 이미지 페이지: 각각 0페이지.
- 저텍스트 페이지 p.4, p.6, p.108, p.500, p.501은 모두 PDF/DB 이미지 0개였다. 렌더링 확인에서 p.4, p.6, p.108, p.500은 거의 빈 페이지로 보였고 p.501은 ‘색인’ 표제만 확인됐다. 페이지의 편집상 의도는 판정하지 않았다.
- 이미지 JOIN 전 검색 chunk 행 947개, JOIN 후 1,842행(+895). 이미지가 2개 이상인 페이지 261개, 해당 페이지에 놓인 chunk 407개, JOIN 결과에서 중복된 chunk 그룹 407개.
- LIMIT 12 실제 조회에서 p.2 / chunk_no 2 / chunk_id `20261003_009009`가 같은 similarity 1로 image_no 3, 1, 2 각각에 연결되어 상위 3행에 반복됐다. 따라서 이미지 URL별 중복 행이 LIMIT 결과 슬롯을 차지하는 현상을 확인했다.

### 발견된 문제

- `image_desc`가 전 행 NULL이라 이미지 내용의 텍스트 설명은 현재 DB에서 확인되지 않는다.
- 한 페이지에 이미지가 여러 개이면 페이지 기준 LEFT JOIN이 chunk 행을 이미지 수만큼 늘린다. 실제 상위 LIMIT 결과에서 동일 chunk가 반복 노출되어 검색 결과의 고유 chunk 수를 줄일 수 있다. 검색 품질에 영향을 줄 수 있는 후보로 기록한다.
- 저텍스트 5페이지는 추출 이미지가 없어 이미지 중심 페이지로 확인되지 않았다. 빈 페이지 여부와 문서 편집 의도는 자동 결과만으로 확정할 수 없다.

### 현재 수정 여부

미수정. 이번 작업은 검증만 수행했으며 Python/SQL/Streamlit 코드, DB 데이터, Supabase 객체는 수정하지 않았다. 이미지 검증 결과는 `EDA_REPORT.md`에도 반영되어 있다.

### 다음 검토 항목

- 검색 결과를 chunk 단위로 고유하게 유지하면서 동일 페이지의 이미지들을 함께 반환할 수 있는 조회 형태를 검토한다.
- 상위 LIMIT 결과에서 중복 chunk가 제거될 때 실제 노출되는 고유 chunk 수와 이미지 연결 결과를 재검증한다.
- `image_desc`가 필요한 사용 사례와 생성·관리 방식을 검토한다.
- 저텍스트 페이지의 문서상 성격은 필요하면 원본 PDF를 사람이 추가 확인한다.

## 2026-10-03 — `search_car_manual` 이미지 JOIN 조건 재검증

### 수정 목적

`search_car_manual`에서 이미지 JOIN의 차량 및 chapter 연결 조건을 `C`/`H` 기준에서 `D`(chunk) 기준으로 바꾼 뒤, Sonata 2026 (`CAR_ID = 20261003_000014`) 실제 DB에서 중복과 검색 결과 변화를 확인했다. 기존 코드 추가 수정 없이 대상 차량만 조회했으며 DB 트랜잭션을 읽기 전용으로 설정하고 SELECT만 실행했다.

### 수정 전 JOIN과 수정 후 JOIN

- 수정 전: `I.CAR_ID = C.CAR_ID AND I.CAR_MANUAL_CHAPTER_ID = H.CAR_MANUAL_CHAPTER_ID AND I.CAR_MANUAL_IMAGE_PAGE_NO = D.CAR_MANUAL_CHUNK_PAGE_NO`
- 수정 후: `I.CAR_ID = D.CAR_ID AND I.CAR_MANUAL_CHAPTER_ID = D.CAR_MANUAL_CHAPTER_ID AND I.CAR_MANUAL_IMAGE_PAGE_NO = D.CAR_MANUAL_CHUNK_PAGE_NO`
- 앞선 INNER JOIN에서 `D.CAR_ID = C.CAR_ID`, `D.CAR_MANUAL_CHAPTER_ID = H.CAR_MANUAL_CHAPTER_ID`가 이미 성립하므로 이번 변경은 실제 행 매칭 조건을 좁히거나 1:1로 바꾸지 않는다.

### 실제 테스트 결과

- 이미지 JOIN 전 chunk 행: 947.
- 수정 전 JOIN: 전체 1,842행, distinct chunk 947개, 추가 반복행 895개.
- 수정 후 JOIN: 전체 1,842행, distinct chunk 947개, 추가 반복행 895개.
- JOIN 후 chunk 기준 중복 그룹: 407개. chunk 하나에 연결되어 최대 반환된 이미지 행: 13개.
- 이미지가 2개 이상인 페이지: 261개. 해당 페이지의 chunk는 페이지 이미지 수에 따라 여러 이미지 URL 행으로 반복됐다.
- p.2 / chunk_no 2 (`CAR_MANUAL_CHUNK_ID = 20261003_009009`): 현재 JOIN에서도 이미지 URL 3개에 대응하는 3행으로 반환된다.
- 수정 전·후 각각 대표 질문 3개에 대해 top-10 `(chunk, image URL)` 순서를 비교했고 세 질문 모두 동일했다.
  - “가솔린/LPI 엔진에 권장되는 엔진오일 등급과 용량은?” — LIMIT 5: 5행/4개 고유 chunk(반복 1행), LIMIT 10: 10행/5개 고유 chunk(반복 5행, 최대 동일 chunk 3행).
  - “후드는 어떻게 안전하게 닫나요?” — LIMIT 5: 5행/5개 고유 chunk(반복 없음), LIMIT 10: 10행/8개 고유 chunk(반복 2행, 최대 동일 chunk 2행).
  - “배터리 단자와 윗부분은 어떻게 관리하나요?” — LIMIT 5: 5행/4개 고유 chunk(반복 1행), LIMIT 10: 10행/6개 고유 chunk(반복 4행, 최대 동일 chunk 4행).
- 실제 top-10에서 중복으로 LIMIT 자리를 차지한 예: 엔진오일 질문의 p.24/chunk 41은 2행, p.464/chunk 868은 3행; 배터리 질문의 p.476/chunk 887은 4행이었다.

### 발견된 문제 및 결론

중복 문제는 그대로 존재한다(B). 수정은 부모 alias를 `C`/`H`에서 `D`로 바꿨지만, chunk가 같은 차량·chapter에 속한다는 INNER JOIN 조건 때문에 이미지 매칭 결과가 동일하다. 실제 집계와 세 질문의 정렬·이미지 URL 결과가 모두 같았으며, 이미지 여러 개가 연결된 chunk가 LIMIT 결과를 차지해 고유 검색 chunk 수를 줄이는 현상도 계속 확인됐다.

### 현재 수정 여부

JOIN 중복은 미해결이며 이번에는 추가 SQL이나 Python 코드를 수정하지 않았다. 현재 수정된 SQL의 기능 동작만 실제 Sonata DB에서 검증했다.

### 다음 검토 항목

- 가장 작은 범위의 후보는 검색 후보 chunk를 먼저 정렬·LIMIT한 뒤, 페이지 이미지들을 배열 등 단일 값으로 집계해 chunk당 한 행만 반환하는 방식이다. 단, 반환 필드가 단일 이미지 URL에서 URL 목록으로 바뀌면 Repository 및 호출부의 결과 처리 영향도 확인해야 한다.
- `array_agg`로 한 chunk당 한 행을 유지하면 여러 이미지를 잃지 않지만 결과 스키마가 바뀐다. `LATERAL`/하위 쿼리로 이미지 조회를 분리해 집계할 수도 있어 쿼리 내부 변경으로 범위를 제한하기 쉽다.
- Chunk Top-K 후 이미지 JOIN만 수행하면 검색 후보의 순위 선정은 보호하지만, 이미지가 여러 개면 최종 반환 행 수가 K보다 커지고 중복 행은 남는다. 단독 해결책으로 쓰려면 이미지 집계와 함께 적용해야 한다.
- 최종 결과에 단순 `DISTINCT`를 적용하면 URL이 서로 다른 행은 distinct로 남으므로 중복 제거를 보장하지 않는다. 이미지 하나만 선택하면 나머지 이미지를 잃을 수 있고, chunk 필드 기준 집계/대표 이미지 선택에는 명시적 정책이 필요하다.
- 후보 방식을 정한 뒤 같은 세 질문의 LIMIT 5/10에서 고유 chunk 수, 이미지 보존, 정렬 순서를 재검증한다.

## 2026-10-03 — correlated subquery 기반 이미지 조회 검증

### 수정 목적

소나타 검색 결과에서 이미지 다중 JOIN 때문에 chunk가 반복되고 LIMIT 자리를 차지하던 문제를 확인하고, 수정된 저장소 SQL이 이를 해소하는지 검증했다. 대상은 Hyundai Sonata 2026, `CAR_ID = 20261003_000014`로 고정했다. DB 트랜잭션은 읽기 전용으로 설정했고 SELECT만 실행했다.

### 문제 발견 및 원인

- 이전 이미지 JOIN 방식은 검색 대상 chunk 947개를 1,842행으로 늘렸고, 중복 chunk 그룹 407개, 최대 13행 반복을 만들었다.
- 원인은 동일 car/chapter/page에 이미지가 N개면 해당 page의 각 chunk가 이미지 row마다 JOIN되어 N행으로 반환되는 구조였다.
- 1차 수정에서 JOIN alias 조건을 C/H 기준에서 D 기준으로 바꿨지만, INNER JOIN상 D가 같은 car/chapter에 속하므로 실제 결과는 1,842행/947 distinct chunk로 그대로였다.

### 최종 수정 확인

저장소의 실제 `src/car_search_rag/car_search/car_manual.sql`에서 `search_car_manual`을 읽어 확인했다. SELECT의 correlated subquery가 D와 동일한 car, chapter, page를 조건으로 `CAR_MANUAL_IMAGE`를 찾고 `ORDER BY CAR_MANUAL_IMAGE_NO LIMIT 1`로 URL 하나를 반환한다. FROM/JOIN에는 `CAR_MANUAL_IMAGE`의 LEFT JOIN이 남아 있지 않았다. 이번 작업에서는 SQL, Python, DB를 수정하지 않았다.

### 검증 결과

- 전체 대상 chunk: 947. 현재 SQL 동등 형태로 전체 대상에 적용한 결과: 947행, distinct chunk 947개, 중복 chunk 그룹 0개, 최대 반복 1행.
- p.2 / chunk_no 2 (`CAR_MANUAL_CHUNK_ID = 20261003_009009`): 페이지 이미지 3개 중 단 1행이 반환됐다. 연결 이미지 번호 1은 실제 최소 `CAR_MANUAL_IMAGE_NO` 1과 일치했다.
- 기존 `CarManualSearchService.search_manual` 흐름으로 각 질문을 LIMIT 5와 LIMIT 10에 실행했다. 여섯 호출 모두 성공했고 반환 매핑 오류가 없었다. 각 LIMIT 결과의 반환 행 수와 고유 chunk 수는 각각 5/5 및 10/10, 중복은 모두 0이었다.

| 기존 대표 질문 | LIMIT 5 결과 (page/chunk_no 순서) | LIMIT 10 고유 chunk | similarity 순서 확인 |
|---|---|---:|---|
| 가솔린/LPI 엔진에 권장되는 엔진오일 등급과 용량은? | 7/10, 23/39, 24/41, 464/868, 463/866 | 10 | 기존 embedding 결과의 distinct chunk 순서와 동일 |
| 후드는 어떻게 안전하게 닫나요? | 110/201, 70/127, 61/112, 164/317, 333/634 | 10 | 기존 embedding 결과의 distinct chunk 순서와 동일 |
| 배터리 단자와 윗부분은 어떻게 관리하나요? | 475/885, 448/844, 233/425, 502/934, 498/927 | 10 | 기존 embedding 결과의 distinct chunk 순서와 동일 |

- 반환된 image URL은 이미지가 있는 page에서 NULL이 아니었고, 이미지가 없는 page에서는 NULL이었다. 이는 LEFT JOIN을 제거하고 URL만 correlated subquery로 조회할 때의 정상 결과다.
- p.2의 세 이미지 중 image_no 1의 URL이 선택됐다. 따라서 여러 이미지가 있는 page에서는 가장 작은 image_no 하나만 결과로 노출되며 나머지 이미지 URL은 반환되지 않는다.
- 검색/매핑 SQL 오류는 없었다. 대표 질문 호출 시간은 약 0.8–2.3초였으며 embedding 요청을 포함한 단일 실행 관측값이다.

### 결론 및 현재 수정 여부

판정: 해결. 전체 대상에서 chunk 중복이 0이고, LIMIT 5/10이 고유 chunk 5/10개를 반환했으며, 대표 질문의 embedding similarity 순서는 이전 distinct chunk 순서와 같았다. p.2 대표 이미지 선택도 최소 image_no 규칙과 일치했다. 사용자가 이미 반영한 SQL을 검증만 했고, 이번 작업에서는 코드나 DB를 추가 수정하지 않았다.

### 다음 검토 항목

- 상관 서브쿼리가 항상 가장 작은 `CAR_MANUAL_IMAGE_NO` 이미지 하나를 선택하는 동작은 현재 의도와 일치한다. 향후 같은 페이지의 모든 이미지를 UI에 제공할 필요가 생기면 chunk당 URL 목록을 반환하는 방식과 Repository 결과 스키마를 함께 검토한다.
- 0.8–2.3초는 대표 질문 3개에 대한 단일 관측이므로 성능 일반화나 튜닝 판단에 사용하지 않는다.

## 2026-10-04 — 검색 출처 metadata 및 이미지 preview UI

### 변경 전 관찰

- 사용자가 실제 Streamlit 앱 `http://localhost:8501`에서 확인한 변경 전 화면에는 page/chunk 출처 영역이 없었다.
- USB 질문 답변에는 page_0236이 포함된 그림 링크가 있었고 클릭하면 별도 탭에서 실제 이미지가 열렸지만, 채팅 내부 image preview는 없었다.
- 실제 사용자 브라우저 8501과 자동 검증용 별도 8517 서버는 서로 다른 인스턴스다. 이 기록의 AppTest 결과는 브라우저 수동 확인과 구분한다.

### 구현 및 자동 검증

- 기존 `CarManual.ask()`와 `CarManualSearchService.ask_manual()` 문자열 반환은 유지하고 metadata 반환용 `ask_with_sources()` / `ask_manual_with_sources()`를 추가했다.
- 검색 tool의 답변 문자열은 기존처럼 LLM에 전달하고 검색 row는 LangChain `content_and_artifact`의 호출 결과 artifact로 전달한다. 전역이나 cached singleton의 공유 mutable 검색 결과는 사용하지 않는다.
- Streamlit assistant message에 해당 요청의 source/image 표시용 데이터만 저장한다. page/chunk 최대 5개를 검색 순서대로 보여주고, image URL은 비어 있는 값과 중복을 제외해 최대 3개 preview 및 원본 링크로 표시한다.
- 실제 DB/API AppTest 두 질문 연속 실행은 답변 성공, 예외 0건, image element 6개였다. USB Top-5는 12/22, 236/429, 237/430, 243/442, 113/218이었고 image URL 3개를 확보했다.
- 이번 엔진오일 검색 Top-5는 488/908, 448/850, 448/845, 448/846, 141/277이었다. 기대 p.463/chunk 866은 이번 실행에 없었다. 이전 별도 E2E에서는 3위였다. 검색/rewrite 경로는 변경하지 않았으며 UI는 현재 실행에서 실제 반환한 metadata만 표시한다.
- Mock AppTest에서 p.463/chunk 866과 USB metadata, 고유 image preview/link 렌더링 및 두 대화 turn의 metadata 분리를 확인했다. `CarManual.ask()`와 service 기존 메서드의 문자열 반환도 stub으로 검증했다.

### 상태

- 자동 테스트에서 검색 출처 영역과 image preview element 생성 확인.
- 실제 브라우저에서 변경 후 최종 확인은 사용자 재검증 대기. 브라우저 최종 검증 완료로 간주하지 않는다.

## 2026-10-04 — Sonata PDF 재등록 및 사후 검증

### 범위와 원본

- 대상: Hyundai Sonata 2026, 공식 매뉴얼의 `DN8` / `ko_KR` PDF. 공식 URL: https://ownersmanual.hyundai.com/manual/쏘나타?langCode=ko_KR&countryCode=A99&projCode=DN8&year=2026&content=pdfDownload
- 원본: `data/DN8_2026_ko_KR.pdf`, 43,423,714 bytes, 508페이지.
- SHA-256: `F83F44ABCF8F59C30FA4D0B0B419A8E7AACA54DA7D6F5C5FC9B3F83CAB650E23`.
- 재등록 전 사용자가 Sonata DB 데이터와 `cars/hyundai/sonata/` Storage prefix를 수동 삭제했다. 추가 DELETE는 실행하지 않았고, 기존 Sonata 등록 경로를 사용했다.

### 재등록 결과

기존 car row가 없는 상태에서 기존 `merge_car`/`FN_GET_BIZ_ID('CAR')` 흐름이 새 `car_id=20261004_000015`를 발급했다. 등록을 재시도하지 않았다.

| 확인 항목 | 사후 검증 결과 |
|---|---:|
| Hyundai / Sonata / 2026 car row | 1 (`car_id=20261004_000015`) |
| Chapter | 10 |
| Chunk | 947 |
| Embedding | 947 |
| Embedding NULL | 0 |
| Embedding dimension | 1536 |
| Image DB row | 955 |
| Supabase Storage `images/cars/hyundai/sonata/` objects | 955 |
| 중복 chunk body | 0 |
| 중복 chunk ID | 0 |
| 중복 image URL | 0 |
| 동일 차종/연식 중복 car row | 0 |

### 실행 중 출력 오류와 해석

기존 등록 메서드는 DB/Storage 적재를 마친 뒤 `_print_summary()` 콘솔 출력 중 Windows cp949가 일부 Unicode 문자를 인코딩하지 못해 `UnicodeEncodeError`를 발생시켰다. 오류 지점은 적재 후 요약 출력 단계다. 이후 읽기 전용 사후 검증에서 위 데이터 수량과 vector dimension, Storage object 수가 정상 확인됐다. 재시도는 하지 않았으며 데이터 적재 실패로 해석하지 않는다. 이번 단계에서는 코드의 인코딩 동작을 수정하지 않았다.

### 재등록 방식과 운영상 주의

- PDF 입력은 `data/DN8_2026_ko_KR.pdf`다. 등록 코드 자체는 공식 사이트에서 자동 다운로드하지 않으며, DB 데이터를 자동 idempotent upsert하지 않는다.
- 재등록은 Sonata 대상 기존 DB/Storage 데이터를 명시적으로 정리한 뒤 기존 등록 경로를 실행하는 운영 절차다. 기존 car row가 없다면 새 `car_id`가 발급된다.
- Storage object key는 `cars/{brand}/{model}/{image_name}`이며 upload 옵션은 `upsert=true`다. 동일 object key는 overwrite된다. 경로에 `car_id` 또는 사용자 식별자가 없으므로 동일 Hyundai Sonata를 다른 사용자가 등록할 경우 같은 prefix를 공유할 수 있다. 새 처리 결과에 없는 옛 object 삭제도 자동 보장되지 않으므로 공유 환경에서 prefix 충돌/잔존 object를 주의한다. 이번에는 Storage 구조를 변경하지 않았다.

이 기록은 과거 `20261003_000014`를 사용한 기존 M4/M6/E2E 실험을 소급 수정하지 않는다. 해당 ID는 실행 당시의 historical ID이며, 당시 재등록 ID는 `20261004_000015`다.

## 2026-10-04 — Sonata 전체 재등록 및 규칙형 image_desc 검증

### 실행 범위와 방법

- 대상 PDF: `data/DN8_2026_ko_KR.pdf`; 기존 production `CarManualRegisterService.insert_pdf_docs()` 사용.
- 재등록 직전 읽기 전용 확인: Hyundai/Sonata/2026 car 0, chapter 0, chunk 0, image DB 0, Storage `images/cars/hyundai/sonata/` object 0.
- 추가 DELETE 없이 기존 등록 절차를 완료했다. 새 ID는 `merge_car` / `FN_GET_BIZ_ID('CAR')` 경로에서 생성됐다.
- image_desc는 production의 bbox + 인접 text block 규칙 경로로 생성했다. Vision API와 Text LLM은 사용하지 않았다. 기존 embedding API는 chunk embedding에 사용됐다.
- 초기 제한된 실행 환경에서는 네트워크 권한 때문에 DB 연결 전 실패했다. 데이터 작업이 시작되지 않은 것을 확인하고 네트워크 접근이 허용된 환경에서 등록을 실행했다. 등록 메서드는 정상 반환했으며 애플리케이션 수준의 등록 재시도는 하지 않았다. stdout을 UTF-8로 지정해 cp949 출력 오류도 발생하지 않았다.

### 읽기 전용 사후 검증

| 확인 항목 | 결과 |
|---|---:|
| Hyundai / Sonata / 2026 car row | 1 (`car_id=20261004_000016`) |
| Chapter | 10 |
| Chunk | 947 |
| Embedding | 947 |
| Embedding NULL | 0 |
| Embedding dimension | 1536 (947건 모두) |
| Image DB row | 955 |
| Storage `images/cars/hyundai/sonata/` objects | 955 |
| image_desc non-NULL | 9 (0.94%) |
| image_desc NULL | 946 (99.06%) |
| duplicate chunk body group | 0 |
| duplicate chunk ID group | 0 |
| duplicate image URL group | 0 |
| Hyundai/Sonata/2026 추가 car row | 0 (해당 조건 총 1건) |

### 저장된 image_desc 샘플

DB에서 확인한 non-NULL 설명은 총 9건이며, 요청한 10건보다 하나 적다. 존재하지 않는 열 번째 설명을 만들어내지 않았다.

| PDF page / image | 저장된 설명 |
|---|---|
| p.163 / i2 | 후드 2차 열림 레버 조작 |
| p.236 / i1 | 앞좌석 USB 충전 단자 위치 |
| p.236 / i2 | 뒷좌석 센터 콘솔의 USB 충전 단자 위치 |
| p.454 / i1 | 냉각팬 작동 및 점검 시 부상 주의 |
| p.463 / i1 | 엔진 오일 레벨 게이지 F-L 범위 확인 |
| p.466 / i1 | 냉각수 보조 탱크 MIN/MAX 수위 확인 |
| p.468 / i1 | 냉각팬 작동 및 점검 시 부상 주의 |
| p.468 / i2 | 브레이크액 MIN/MAX 점검 및 보충 |
| p.479 / i1 | 타이어 마모한도 표시밴드 |

### 의도적 NULL 사례 및 한계

- p.386/i1, p.386/i2, p.386/i3, p.387/i1은 DB에서 NULL로 확인했다. 주변 텍스트만으로 개별 이미지의 검색 의미를 안정적으로 연결하기 어려운 작은 화살표/fragment여서 description을 억지로 붙이지 않았다.
- p.163/i1·i3, p.463/i2·i3, p.466/i2–i4 등도 확인된 샘플에서 NULL이다.
- `image_desc`는 검색용 metadata 저장까지 완료됐으나 검색 순위나 이미지 relevance 개선 효과는 이번 재등록만으로 검증하지 않았다.

## 2026-10-06 — 발표용 RAG 품질 대시보드 및 main 병합

- `app_kbj.py`에 Golden Set 후보 11문항, Synthetic Holdout 50문항, Robustness 50문항의 Hit@1 / Hit@3 / Hit@5 그래프와 각 평가셋의 MRR@5 metric 카드를 추가했다.
- 기존 streaming 응답, 검색 출처 Top-5, 관련 이미지, conversation history, HTML 대화 기록 다운로드 경로를 merge 결과에 유지했다. Streamlit AppTest에서 대시보드, 그래프 1개, MRR 카드 3개, 차량 선택 및 질문 입력 UI를 확인했다.
- main 병합 중 `app_kbj.py` 충돌을 해결하고 대시보드 변경을 merge 결과에 포함했다. `pyproject.toml`에서는 양쪽에 필요한 의존성을 통합하고 중복 제약을 정리했다.
- 기존 lock의 conflict marker를 제거하기 위해 `uv lock`으로 `uv.lock`을 재생성했으며 `uv lock --check`를 통과했다.
- merge commit은 `7f455431ad25d82210fc159ca49491edf3c02545`이며, merge 직후 working tree clean을 확인했다.
