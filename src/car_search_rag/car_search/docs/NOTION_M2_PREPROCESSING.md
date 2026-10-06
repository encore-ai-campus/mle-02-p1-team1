# M2 · 전처리

## 목표

결측치·이상치·중복·불필요한 문자열을 정리하고 같은 뜻의 값을 통일합니다.

## 완료 기준

- [ ] 결측치 처리 기준 기록
- [ ] 중복 제거 기준 기록
- [ ] 컬럼/문자열 정리
- [ ] 전처리 전후 데이터 건수 비교

## 개인 완주 체크

각자 주요 전처리 규칙을 코드와 함께 설명할 수 있어야 합니다.

## 사용 데이터

<table fit-page-width="true" header-row="true">
<tr><td>항목</td><td>내용</td></tr>
<tr><td>데이터 출처</td><td>Hyundai 공식 Sonata 2026 DN8 국문 매뉴얼 PDF; 공식 URL은 DATASET_SPEC.md 참조. 파일 SHA-256 기록 완료. 최초 취득일 및 공식 revision/edition 번호는 확인 가능한 기록 없음</td></tr>
<tr><td>원본 형식</td><td>508페이지 PDF, 43,423,714 bytes</td></tr>
<tr><td>데이터 건수</td><td>페이지 508, Chapter 10, chunk 947, image 955 (별도 단위)</td></tr>
<tr><td>주요 데이터 단위</td><td>PDF page → text → chunk; image는 별도 추출</td></tr>
<tr><td>RAG 사용 목적</td><td>chunk text 및 1536차원 embedding을 pgvector `<=>`로 검색</td></tr>
</table>

## 데이터 명세

2026-10-04 재등록 후 집계는 현재 Sonata `car_id=20261004_000015`와 코드/DDL에서 확인한 아래 네 테이블만 대상으로 했습니다. 41개 전체 컬럼은 `DATASET_SPEC.md`에 있습니다.

<table fit-page-width="true" header-row="true">
<tr><td>테이블</td><td>행 / 컬럼</td><td>Null 결과</td><td>설명</td></tr>
<tr><td>`public.car`</td><td>1 / 10</td><td>0</td><td>차량 식별 및 검색 조건</td></tr>
<tr><td>`public.car_manual_chapter`</td><td>10 / 9</td><td>0</td><td>목차 및 chunk 연결</td></tr>
<tr><td>`public.car_manual_chunk`</td><td>947 / 11</td><td>embedding NULL 0</td><td>chunk 본문/vector 검색; 모두 1536차원</td></tr>
<tr><td>`public.car_manual_image`</td><td>955 / 11</td><td>image_desc 955 (100%)</td><td>이미지 URL; 설명 전부 NULL</td></tr>
</table>

## 1. 결측치 처리 기준

- `public.car_manual_image.car_manual_image_desc`: 955건 중 955건 NULL, 결측률 100.00%.
- 나머지 40개 컬럼은 Null 0건. 일부 nullable 컬럼도 실측 Null 0건.
- 검사한 문자열의 빈 문자열/공백 전용 값은 0건.
- NULL 대체나 행 제거는 하지 않았습니다. `image_desc`는 등록 코드가 `None`을 전달하고 설명 생성 코드가 확인되지 않아 그대로 유지합니다.

## 2. 중복 제거 기준

- 등록 코드에서 자동 dedupe는 확인되지 않았습니다.
- chunk 본문 exact duplicate groups 0 (947행/947 distinct); image URL 중복 0 (955개/955 distinct); 기존 EDA 기록상 page/image 번호 중복 0.
- 제거는 수행하지 않았습니다. 점검 기준에서 실제 중복이 없었습니다. 기존 PDF image hash unique 727/955는 반복 이미지 내용 확인값이며 dedupe 동작 근거가 아닙니다.

## 3. 컬럼 / 문자열 정리

- PDF 물리 페이지 번호를 1부터 부여하고 `page_no` metadata에 보존합니다.
- `RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)`로 나누고 순번 `chunk_no`를 부여합니다.
- `chunk.page_content`를 그대로 embedding 입력으로 사용합니다.
- 별도 trim, 개행/특수문자 제거, OCR은 확인되지 않았습니다. 줄바꿈 포함 943/947, 경계 공백 chunk 0, CR/tab/기타 제어문자 0.

## 4. 전처리 전후 데이터 건수

<table fit-page-width="true" header-row="true">
<tr><td>단계</td><td>건수</td><td>변화량</td><td>설명</td></tr>
<tr><td>원본 PDF</td><td>508 pages</td><td>-</td><td>물리 페이지</td></tr>
<tr><td>추출 text</td><td>508 page docs</td><td>0</td><td>None/빈/공백 페이지 0</td></tr>
<tr><td>결측 처리</td><td>별도 단계 없음</td><td>-</td><td>유효 텍스트 page 508</td></tr>
<tr><td>중복 처리</td><td>별도 단계 없음</td><td>-</td><td>exact chunk duplicate groups 0</td></tr>
<tr><td>chunk 생성</td><td>947</td><td>+439</td><td>page와 chunk는 단위가 다름</td></tr>
<tr><td>RAG 검색 대상</td><td>947</td><td>0</td><td>Sonata DB chunk와 일치</td></tr>
<tr><td>embedding</td><td>947</td><td>0</td><td>모두 1536차원, NULL 0</td></tr>
</table>

## 5. 주요 전처리 코드

### 페이지 텍스트 추출
- 코드 위치: `src/car_search_rag/common/document_reader.py` — `DocumentReader.set_pdf_doc_list()`
- 처리: 페이지별 `page.extract_text()`를 page 번호와 저장합니다.
- 이유: 검색 근거를 원본 물리 페이지와 연결합니다. OCR/trim/빈 페이지 제거는 확인되지 않습니다.

### Chunk 분할
- 코드 위치: `src/car_search_rag/car_search/car_manual_register_service.py` — `_extract_and_split_chunks()`
- 처리: `RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)`, `page_no` metadata 유지.
- 이유: 검색 단위 생성 및 경계 문맥 일부 중첩.

### Embedding 입력
- 코드 위치: 같은 파일 `_create_chunk_embeddings()`
- 처리: `chunk.page_content`를 그대로 `embed_documents()`에 전달합니다.
- 이유: chunk 본문과 embedding 입력을 일치시킵니다.

### 이미지 저장
- 코드 위치: `_extract_and_upload_images()` / `_upload_single_image()` 및 `car_manual_repository.py`
- 처리: 이미지 URL을 저장하고 설명은 `None`을 전달합니다. 실제 `image_desc` 955건 전부 NULL.

## 6. 데이터 흐름

`DN8_2026_ko_KR.pdf` → 페이지 텍스트 추출 → page metadata → 800/150 chunk 분할 → embedding 및 `car_manual_chunk` 적재 → pgvector 검색. 이미지는 별도로 `car_manual_image`에 URL을 기록합니다.

## 7. 전처리 결과

PDF 508페이지의 유효 텍스트를 재현 추출했고, 2026-10-04 재등록 후 현재 Sonata ID `20261004_000015`의 DB chunk와 embedding은 각각 947개입니다. image DB와 Storage object는 각각 955개입니다. 제공 DDL과 실 DB catalog는 대상 네 테이블에서 확인 범위상 일치했습니다. 최초 취득일·공식 revision/edition 번호는 확인 가능한 기록이 없습니다.

## 개인 완주 체크

주요 규칙을 위 코드 위치와 연결했습니다. 기존 완료 기준 체크박스는 변경하지 않았습니다.
