# 실험 로그

EDA, TF-IDF, 검색 평가 과정에서 확인한 주요 측정값과 문제를 날짜순으로 누적한다. 각 기록은 실제 실행 결과만 반영한다.

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
