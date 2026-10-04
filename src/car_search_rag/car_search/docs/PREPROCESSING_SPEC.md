# 전처리 명세서

## 1. 전처리 목적

차량 매뉴얼 PDF를 페이지 출처가 보존된 검색 chunk로 만들고 embedding/pgvector 검색에 사용한다. 문서는 실제 구현과 데이터 점검을 구분하며, 코드에 없는 결측 제거·정규화·중복 제거를 했다고 기록하지 않는다.

## 2. 전처리 전 데이터 상태

- 입력: `data/DN8_2026_ko_KR.pdf`, 43,423,714 bytes, 508페이지.
- 같은 추출/split 흐름 재현: 추출 예외 0, None/빈/공백만 페이지 0, nonempty page 508, chunk 947.
- 현재 Sonata DB(`car_id=20261004_000015`, 2026-10-04 재등록 후): 차량 1, Chapter 10, chunk 947, embedding 947 (NULL 0, 모두 1536차원), image 955. Storage object도 955개다.
- chunk 텍스트 NULL/empty/whitespace 0, exact-text 중복 그룹 0. 이는 점검 결과이며 코드 dedupe 동작을 뜻하지 않는다.
- image description은 955건 모두 NULL.

## 3. 전처리 규칙

| 구분 | 대상 | 실제 처리 | 처리 전 → 후 | 코드/근거 |
|---|---|---|---|---|
| PDF 추출 | 페이지 | `extract_text()` 및 1-based page_no 수집; 빈 페이지 필터 확인 안 됨 | 508 pages → 508 page docs; 유효 text 508 | `DocumentReader.set_pdf_doc_list()` |
| Chapter | 목차 | PyMuPDF TOC level 1, 다음 시작 페이지 직전까지 | 10 Chapters | `_extract_pdf_chapters()` |
| 문자열 정리 | page text | 별도 trim, normalization, 머리말/꼬리말 제거 확인 안 됨 | 원문 추출값 유지 | `document_reader.py` |
| Chunk | page text | `RecursiveCharacterTextSplitter(800, overlap=150)`, page metadata, 순차 chunk_no | 508 page docs → 947 chunks | `_extract_and_split_chunks()` |
| 중복 제거 | chunk/image | 등록 코드에서 dedupe 확인 안 됨 | 처리 단계 없음; 실측 duplicate groups 0 | DB 집계/EDA |
| Embedding | chunk | `chunk.page_content`를 `embed_documents()`에 전달 | 947 chunks → 947 vectors | `_create_chunk_embeddings()` |
| 이미지 | PDF page images | PyMuPDF extract/upload, URL 저장, 설명 `None` | 955 image rows; description NULL 955 | `_extract_and_upload_images()` 및 repository |

## 4. 실제 처리 전후 건수

별도 결측 제거·중복 제거 단계는 없다. 해당 단계의 인위적 행 수를 만들지 않고 관측 단위 변환만 표시한다.

| 단계 | 데이터 건수 | 변화량 | 설명 |
|---|---:|---:|---|
| 원본 PDF 페이지 | 508 | - | 물리 페이지 |
| page text documents | 508 | 0 | 페이지당 한 문서 |
| 유효 텍스트 페이지 | 508 | 0 | None/빈/공백 전용 0 |
| 생성 chunk | 947 | +439 | page와 chunk는 단위가 다름 |
| DB 검색 대상 chunk | 947 | 0 | DB 행 수와 split 재현 수 일치 |
| non-NULL embedding | 947 | 0 | 전부 1536차원 |
| Chapter / Image | 10 / 955 | 별도 단위 | 검색 chunk와 합산하지 않음 |

## 5. 핵심 전처리 코드와 설명

### 페이지 텍스트 추출
- 코드: `src/car_search_rag/common/document_reader.py`, `DocumentReader.set_pdf_doc_list()`
- 각 PDF 페이지의 `page.extract_text()` 결과를 페이지 번호와 묶어 저장한다. 페이지 출처 연결을 위한 것이다. OCR·trim·빈 페이지 제거는 이 경로에서 확인되지 않는다.

### Chunk 분할
- 코드: `src/car_search_rag/car_search/car_manual_register_service.py`, `_extract_and_split_chunks()`
- `RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)`를 적용하고 page_no metadata 및 순서 번호를 유지한다.
- 검색 단위를 만들고 chunk 경계 문맥 일부를 겹치게 하기 위한 설정이다.

### Embedding 입력
- 코드: 같은 파일 `_create_chunk_embeddings()`
- `[chunk.page_content for chunk in chunks]`를 `embed_documents()`에 전달한다. 별도 trim/요약 텍스트는 확인되지 않는다.

### 이미지 저장
- 코드: `_extract_and_upload_images()` / `_upload_single_image()`, `car_manual_repository.py`
- 이미지 URL을 저장하고 description은 `None`을 전달한다. DB 실측상 description 955/955 NULL이다.

## M2 · 전처리 완료 기준

### 결측치 처리 기준

- 결측 컬럼: `public.car_manual_image.car_manual_image_desc`, 955건/955행, 100.00%.
- 나머지 40개 컬럼은 Null 0건. nullable로 정의된 Chapter sort, chunk page/vector, image page도 실측 Null 0.
- 검사한 문자열 필드의 empty/whitespace-only 값 0건.
- 처리 기준: NULL 대체나 행 제거는 하지 않았다. image_desc는 등록 코드에서 `None`으로 전달되고 설명 생성 처리가 확인되지 않아 유지한다.

### 중복 제거 기준

- 코드에 dedupe 단계 없음.
- 점검 기준: chunk text 완전 일치, image URL 완전 일치, `(car_id, chapter_id, image_page_no, image_no)` 조합.
- 결과: 947 chunk의 distinct text 947/중복 그룹 0; 955 URL distinct/중복 그룹 0; 기존 EDA 기록의 page/image 조합 중복 그룹 0.
- 제거하지 않았다. 점검 기준상 중복이 없었다. Hash unique 727/955는 이미지 내용의 반복 참조를 나타내며 등록 dedupe 근거가 아니다.

### 컬럼 / 문자열 정리

- 물리 page_no는 1부터, chunk_no는 split 결과 순서대로 부여한다.
- split 기준은 chunk_size 800, overlap 150.
- 별도 trim, newline/특수문자 제거, Unicode normalization, OCR은 등록 경로에서 확인되지 않는다.
- 실측: 줄바꿈 포함 chunk 943/947, 선행·후행 공백 chunk 0, CR/tab/기타 제어문자 0.

### 전처리 전후 건수 비교

| 단계 | 건수 | 변화량 | 설명 |
|---|---:|---:|---|
| 원본 PDF | 508 | - | pages |
| 추출 page docs | 508 | 0 | 페이지당 하나 |
| 결측 처리 | 별도 단계 없음 | - | 유효 page text 508 |
| 중복 처리 | 별도 단계 없음 | - | exact duplicate group 0 |
| split 후 chunk | 947 | +439 | 단위 전환 |
| 최종 RAG 검색 대상 | 947 | 0 | Sonata DB chunk rows |
| embedding | 947 | 0 | 모두 1536차원 |

## 6. 데이터 흐름

`DN8_2026_ko_KR.pdf` → pypdf page extraction → page_no metadata → 800/150 splitter → chunk text embedding → `car_manual_chunk` 적재 → pgvector `<=>` 검색. PDF image는 별도 추출되어 `car_manual_image`에 URL로 연결된다.

## 7. 결과와 한계

실측 기준으로 page text 508, chunk 947, embedding 947이며 재현 chunk 수와 DB 행 수가 일치한다. 2026-10-04 재등록 후 현재 ID는 `20261004_000015`다. 원본 PDF 공식 URL과 SHA-256을 기록했으며 최초 다운로드일과 공식 revision/edition 번호는 확인 가능한 기록이 없다. 전체 chunk 본문 원본 대조와 시각적 읽기 순서/OCR 필요성은 [추가 검증 필요]. Notion 완료 기준은 체크하지 않았다.

### 재등록 및 중복 정책 (2026-10-04 확인)

- PDF 입력 경로는 `data/DN8_2026_ko_KR.pdf`다. 등록 코드는 PDF를 자동 다운로드하거나 DB 적재를 idempotent upsert하지 않는다. 동일 경로의 파일을 교체하는 것은 파일 작업이며, 코드가 파일 overwrite를 수행하는 것은 아니다.
- 재등록은 Sonata 대상 기존 DB/Storage 데이터를 명시적으로 정리한 뒤 기존 등록 경로를 다시 실행하는 운영 절차다. car row가 없을 때 `merge_car`의 `FN_GET_BIZ_ID('CAR')`가 새 ID를 발급하며 이번 결과는 `20261004_000015`다.
- 이미지 Storage는 `cars/{brand}/{model}/{image_name}` 경로와 `upsert=true`를 사용한다. 같은 object key는 덮어쓰지만, car_id/사용자 식별자가 경로에 없고 새 등록에서 더 이상 생성되지 않는 이전 object를 청소하는 로직도 확인되지 않았다. 공유 환경에서는 동일 모델 prefix 충돌 및 잔존 object를 운영상 주의사항으로 둔다.
- 이번 사후 검증은 chunk 본문 중복 그룹 0, chunk ID 중복 0, image URL 중복 0, 동일 차종/연식 중복 car row 0이었다. Storage object 955개와 DB image row 955건이 일치했다.
