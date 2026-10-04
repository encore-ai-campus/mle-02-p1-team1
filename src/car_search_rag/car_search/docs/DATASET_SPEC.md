# 데이터셋 명세서

## 1. 데이터셋 개요

| 항목 | 확인 내용 |
|---|---|
| 이름 / 목적 | Hyundai Sonata 2026 매뉴얼을 검색·RAG 근거로 사용하는 데이터 |
| 데이터 출처 | 현대자동차 공식 매뉴얼 사이트에서 직접 다운로드한 Sonata 2026 국문 PDF (`DN8`, `ko_KR`): [공식 자료 페이지](https://ownersmanual.hyundai.com/manual/쏘나타?langCode=ko_KR&countryCode=A99&projCode=DN8&year=2026&content=pdfDownload). 로컬 원본: `data/DN8_2026_ko_KR.pdf` (43,423,714 bytes). 별도 데이터 수집 API는 사용하지 않음 |
| 원본 / 최종 형식 | 508페이지 PDF → 페이지 텍스트·chunk·embedding·이미지 레코드 |
| DB 범위 | `public.car`, `public.car_manual_chapter`, `public.car_manual_chunk`, `public.car_manual_image`만. 현재 Sonata `car_id=20261004_000016` 한정 |
| DB 확인일 | 2026-10-04 재등록 후 |
| 한 행의 의미 | 테이블별 차량 1건 / Chapter 1건 / 매뉴얼 chunk 1건 / 이미지 1건 |
| RAG 사용 | chunk 본문과 pgvector embedding 검색, Chapter/page/image URL을 결과에 연결 |

공식 PDF URL, 파일 크기, 508페이지, SHA-256은 2026-10-04에 확인했다. SHA-256은 `F83F44ABCF8F59C30FA4D0B0B419A8E7AACA54DA7D6F5C5FC9B3F83CAB650E23`이다. 최초 다운로드 날짜와 공식 revision/edition 번호는 확인 가능한 기록이 없다. 문서 식별은 “Hyundai Sonata 2026 DN8 Korean owner's manual”로 한정한다.

## 2. 데이터 흐름

`DN8_2026_ko_KR.pdf` → `DocumentReader.set_pdf_doc_list()`의 페이지별 `page.extract_text()` → `RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)` → DB chunk 적재 → `text-embedding-3-small` 1536차원 vector 생성/저장 → query embedding → `CarManualRepository.search_manual()` → `car_manual.sql` `search_car_manual`의 `<=>` 검색. 별도 trim/정규화/OCR/dedupe는 이 등록 경로에서 확인되지 않는다. 이미지는 별도 PyMuPDF 분기다.

## 3. 데이터 단위별 실제 건수

| 데이터 단위 | 건수 | 근거 |
|---|---:|---|
| PDF 물리 페이지 / page documents | 508 / 508 | 로컬 PDF 재처리 |
| `public.car` | 1 | Sonata 범위 DB 집계 |
| `public.car_manual_chapter` | 10 | DB 집계 |
| `public.car_manual_chunk` | 947 | DB 집계 및 splitter 재현 |
| non-NULL 1536차원 embedding | 947 | DB vector 검사 |
| `public.car_manual_image` | 955 | DB 집계 |

2026-10-04 수동 정리 후 기존 등록 경로로 재등록했다. 최신 사후 조회에서 현재 `car_id=20261004_000016`의 차량 1건, chapter 10건, chunk 947건, non-NULL embedding 947건(1536차원), image row 955건을 확인했다. 규칙 기반 image_desc는 9건, NULL은 946건이다. 중복 chunk 본문/ID와 image URL 그룹은 각각 0건이며, Storage `images/cars/hyundai/sonata/` object는 955개다. 직전 재등록의 `car_id=20261004_000015`는 역사 기록으로 `EXPERIMENT_LOG.md`에 보존한다.

엔티티별 건수는 서로 다른 단위이므로 합산하지 않는다.

## 4. 컬럼 명세

결측률 = 실제 NULL 건수 / 해당 테이블의 전체 행 수 × 100. 아래 41개 컬럼은 프로젝트 코드/SQL과 제공 DDL에서 확인한 네 테이블만 포함한다. 문자열 열의 빈 문자열과 공백 전용 값은 실측 0건이다.

| 테이블 | 컬럼 | 타입 | Null 건수 | 결측률 | 설명 | 출처 | RAG 사용 |
| `public.car` | `car_id` | `varchar(20)` | 0 | 0.00% | 차량 ID | 프로젝트 차량 메타데이터 | 차량 식별/검색 필터 |
| `public.car` | `car_brand_nm` | `varchar(100)` | 0 | 0.00% | 차량 브랜드 한글명 | 프로젝트 차량 메타데이터 | 차량 검색 조건 |
| `public.car` | `car_brand_eng_nm` | `varchar(100)` | 0 | 0.00% | 차량 브랜드 영문명 | 프로젝트 차량 메타데이터 | 차량 검색 조건 |
| `public.car` | `car_nm` | `varchar(150)` | 0 | 0.00% | 차량 한글명 | 프로젝트 차량 메타데이터 | 차량 검색 조건 |
| `public.car` | `car_eng_nm` | `varchar(150)` | 0 | 0.00% | 차량 영문명 | 프로젝트 차량 메타데이터 | 차량 검색 조건 |
| `public.car` | `car_model_yr` | `int4` | 0 | 0.00% | 차량 모델 연도 | 프로젝트 차량 메타데이터 | 차량 검색 조건 |
| `public.car` | `create_date` | `timestamptz` | 0 | 0.00% | 등록 일시 | 프로젝트 차량 메타데이터 | 감사 정보 |
| `public.car` | `create_user_id` | `varchar(50)` | 0 | 0.00% | 등록 사용자 ID | 프로젝트 차량 메타데이터 | 감사 정보 |
| `public.car` | `update_date` | `timestamptz` | 0 | 0.00% | 수정 일시 | 프로젝트 차량 메타데이터 | 감사 정보 |
| `public.car` | `update_user_id` | `varchar(50)` | 0 | 0.00% | 수정 사용자 ID | 프로젝트 차량 메타데이터 | 감사 정보 |
| `public.car_manual_chapter` | `car_id` | `varchar(20)` | 0 | 0.00% | 차량 ID | DN8_2026_ko_KR.pdf 및 등록 코드 | 차량 연결 |
| `public.car_manual_chapter` | `car_manual_chapter_id` | `varchar(20)` | 0 | 0.00% | Chapter ID | DN8_2026_ko_KR.pdf 및 등록 코드 | chunk/image 연결 |
| `public.car_manual_chapter` | `car_manual_chapter_no` | `varchar(20)` | 0 | 0.00% | Chapter 번호 | DN8_2026_ko_KR.pdf 및 등록 코드 | 결과 표시/정렬 |
| `public.car_manual_chapter` | `car_manual_chapter_nm` | `varchar(200)` | 0 | 0.00% | Chapter명 | DN8_2026_ko_KR.pdf 및 등록 코드 | 검색 결과 맥락 |
| `public.car_manual_chapter` | `car_manual_chapter_sort_no` | `int4` | 0 | 0.00% | Chapter 정렬 순번 | DN8_2026_ko_KR.pdf 및 등록 코드 | 정렬; nullable |
| `public.car_manual_chapter` | `create_date` | `timestamptz` | 0 | 0.00% | 등록 일시 | DN8_2026_ko_KR.pdf 및 등록 코드 | 감사 정보 |
| `public.car_manual_chapter` | `create_user_id` | `varchar(50)` | 0 | 0.00% | 등록 사용자 ID | DN8_2026_ko_KR.pdf 및 등록 코드 | 감사 정보 |
| `public.car_manual_chapter` | `update_date` | `timestamptz` | 0 | 0.00% | 수정 일시 | DN8_2026_ko_KR.pdf 및 등록 코드 | 감사 정보 |
| `public.car_manual_chapter` | `update_user_id` | `varchar(50)` | 0 | 0.00% | 수정 사용자 ID | DN8_2026_ko_KR.pdf 및 등록 코드 | 감사 정보 |
| `public.car_manual_chunk` | `car_id` | `varchar(20)` | 0 | 0.00% | 차량 ID | DN8_2026_ko_KR.pdf 및 등록 코드 | 차량 필터 |
| `public.car_manual_chunk` | `car_manual_chapter_id` | `varchar(20)` | 0 | 0.00% | Chapter ID | DN8_2026_ko_KR.pdf 및 등록 코드 | Chapter 연결 |
| `public.car_manual_chunk` | `car_manual_chunk_id` | `varchar(20)` | 0 | 0.00% | chunk ID | DN8_2026_ko_KR.pdf 및 등록 코드 | 검색 결과 식별 |
| `public.car_manual_chunk` | `car_manual_chunk_page_no` | `int4` | 0 | 0.00% | PDF 물리 페이지 | DN8_2026_ko_KR.pdf 및 등록 코드 | 검색 결과 출처 |
| `public.car_manual_chunk` | `car_manual_chunk_no` | `int4` | 0 | 0.00% | chunk 순번 | DN8_2026_ko_KR.pdf 및 등록 코드 | 검색 결과 식별/정렬 |
| `public.car_manual_chunk` | `car_manual_chunk_txt` | `text` | 0 | 0.00% | chunk 텍스트 | DN8_2026_ko_KR.pdf 및 등록 코드 | 검색 결과 본문 |
| `public.car_manual_chunk` | `car_manual_chunk_embed_vec` | `vector` | 0 | 0.00% | chunk embedding | DN8_2026_ko_KR.pdf 및 등록 코드 | 1536차원 cosine 검색 |
| `public.car_manual_chunk` | `create_date` | `timestamptz` | 0 | 0.00% | 등록 일시 | DN8_2026_ko_KR.pdf 및 등록 코드 | 감사 정보 |
| `public.car_manual_chunk` | `create_user_id` | `varchar(50)` | 0 | 0.00% | 등록 사용자 ID | DN8_2026_ko_KR.pdf 및 등록 코드 | 감사 정보 |
| `public.car_manual_chunk` | `update_date` | `timestamptz` | 0 | 0.00% | 수정 일시 | DN8_2026_ko_KR.pdf 및 등록 코드 | 감사 정보 |
| `public.car_manual_chunk` | `update_user_id` | `varchar(50)` | 0 | 0.00% | 수정 사용자 ID | DN8_2026_ko_KR.pdf 및 등록 코드 | 감사 정보 |
| `public.car_manual_image` | `car_id` | `varchar(20)` | 0 | 0.00% | 차량 ID | DN8_2026_ko_KR.pdf 및 등록 코드 | 차량 연결 |
| `public.car_manual_image` | `car_manual_chapter_id` | `varchar(20)` | 0 | 0.00% | Chapter ID | DN8_2026_ko_KR.pdf 및 등록 코드 | Chapter 연결 |
| `public.car_manual_image` | `car_manual_image_id` | `varchar(20)` | 0 | 0.00% | 이미지 ID | DN8_2026_ko_KR.pdf 및 등록 코드 | 이미지 식별 |
| `public.car_manual_image` | `car_manual_image_page_no` | `int4` | 0 | 0.00% | PDF 물리 페이지 | DN8_2026_ko_KR.pdf 및 등록 코드 | 검색 결과 이미지 연결 |
| `public.car_manual_image` | `car_manual_image_no` | `int4` | 0 | 0.00% | 페이지 내 이미지 순번 | DN8_2026_ko_KR.pdf 및 등록 코드 | 이미지 선택 순서 |
| `public.car_manual_image` | `car_manual_image_url` | `varchar(1000)` | 0 | 0.00% | 이미지 URL | DN8_2026_ko_KR.pdf 및 등록 코드 | 검색 결과 이미지 표시 |
| `public.car_manual_image` | `car_manual_image_desc` | `text` | 946 | 99.06% | 이미지 설명 | DN8_2026_ko_KR.pdf 주변 bbox 텍스트 및 규칙 기반 등록 코드 | 9건 생성; 검색 ranking 반영은 미구현 |
| `public.car_manual_image` | `create_date` | `timestamptz` | 0 | 0.00% | 등록 일시 | DN8_2026_ko_KR.pdf 및 등록 코드 | 감사 정보 |
| `public.car_manual_image` | `create_user_id` | `varchar(50)` | 0 | 0.00% | 등록 사용자 ID | DN8_2026_ko_KR.pdf 및 등록 코드 | 감사 정보 |
| `public.car_manual_image` | `update_date` | `timestamptz` | 0 | 0.00% | 수정 일시 | DN8_2026_ko_KR.pdf 및 등록 코드 | 감사 정보 |
| `public.car_manual_image` | `update_user_id` | `varchar(50)` | 0 | 0.00% | 수정 사용자 ID | DN8_2026_ko_KR.pdf 및 등록 코드 | 감사 정보 |

## 5. 데이터 품질 확인

- `car` 1행, chapter 10행, chunk 947행, image 955행.
- 최신 재등록 기준 `car_manual_image.car_manual_image_desc`는 946/955(99.06%) NULL, 9/955(0.94%) non-NULL이다. 근거가 부족한 이미지는 NULL을 유지한다. 나머지 40개 컬럼의 NULL 0건은 이전 읽기 전용 점검 결과다.
- 검사한 문자열 열의 빈 문자열 및 공백 전용 값: 각각 0건.
- Chunk: NULL/empty/whitespace-only 0, 정확히 같은 본문 중복 그룹 0(947개 distinct), 길이 min 19 / median 717 / avg 607.35 / max 800자. 50자 미만 5개이며 제거하지 않았다.
- Chunk 문자열: 줄바꿈 포함 943건, 선행/후행 공백 0, CR/tab/기타 제어문자 각각 0. page_no 1~508, 508개 페이지 coverage.
- Embedding: non-NULL 947건, 1536차원 947건. vector text 검사에서 `NaN|Infinity` 패턴 일치 0.
- Image: URL null/empty 0, 중복 URL 그룹 0(955 distinct), page 2~492의 368개 페이지. 최신 재등록 `image_desc`: 9 non-NULL / 946 NULL; NULL 비율 99.06%.
- 기존 EDA에는 PDF 이미지 레코드 955개 중 hash unique 727개로 기록되어 있다. 등록 코드가 이를 deduplicate한다는 근거는 없다.

## 5.1 최신 재등록 및 image_desc 확인 (2026-10-04)

현재 Sonata `car_id=20261004_000016` 기준 읽기 전용 사후 확인 결과: car 1, chapter 10, chunk 947, embedding 947(NULL 0, dimension 1536), image DB 955, Storage `images/cars/hyundai/sonata/` object 955. chunk body/ID, image URL 중복 그룹 및 Hyundai/Sonata/2026 중복 car row는 각각 0이다.

production 등록 경로는 이미지 bbox와 주변 PDF text block을 규칙으로 매칭한다. Vision/Text LLM 호출 없이 설명 9건을 생성하고, 근거가 부족한 나머지 946건은 NULL로 유지했다(99.06%). 저장된 설명은 p.163/i2 후드 2차 열림 레버, p.236/i1 앞좌석 USB, p.236/i2 뒷좌석 센터 콘솔 USB, p.454/i1 냉각팬 주의, p.463/i1 엔진 오일 F-L, p.466/i1 냉각수 MIN/MAX, p.468/i1 냉각팬 주의, p.468/i2 브레이크액 MIN/MAX, p.479/i1 타이어 마모한도다. p.386/i1–i3 및 p.387/i1은 NULL이다. non-NULL 설명이 총 9건이므로 10개 샘플은 존재하지 않는다. image_desc의 검색 ranking 효과는 아직 검증하지 않았다.

## 6. 데이터 출처 및 스키마 근거

- 분석 자산: `notebooks/kbj_sonata_pdf_eda.ipynb`, `notebooks/kbj_sonata_tfidf_analysis.ipynb` 및 EDA/TF-IDF/실험 보고서. 별도 CSV 분석 산출 파일은 확인하지 못했다.
- 구현 근거: `src/car_search_rag/common/document_reader.py`, `src/car_search_rag/car_search/car_manual_register_service.py`, `car_manual_repository.py`, `car_manual.sql`.
- 제공 DDL과 2026-10-04 `information_schema`/`pg_catalog` 결과를 대조했다. 네 대상 테이블 41개 컬럼의 타입/nullability 및 확인된 PK/FK 정의가 일치했다.
- Vector index: 제공 DDL 및 실 DB catalog에서 `idx_car_manual_chunk_embed_vec_hnsw`가 유효한 HNSW index이며 대상 컬럼 `car_manual_chunk_embed_vec`, operator class `vector_cosine_ops`임을 확인했다. 2026-10-04 실제 검색 형태의 `EXPLAIN (ANALYZE, BUFFERS, VERBOSE)`에서는 HNSW가 선택되지 않고 `car_manual_chunk_pkey` Index Scan과 top-N heapsort가 관찰됐다 (Planning 5.835 ms, Execution 15.178 ms). 이는 단일 실행 결과다.
- 타 PDF `data/NE1_2027_ko_KR.pdf`, `data/에센자미니_c30.pdf`와 다른 사용자의 테이블은 이 Sonata 집계에서 제외했다.

## 7. 한계 / 확인 필요

- 정확한 PDF 다운로드 날짜와 공식 판본 표기는 현재 저장소 근거에서 확인되지 않았다. 필요할 때 원본 파일/사이트 메타데이터에서 추가 확인할 수 있으며, 공식 배포처와 자료 URL은 확인 완료했다.
- DB 수치는 2026-10-04 대상 차량의 읽기 전용 조회 시점 값이다.
- 페이지 텍스트 추출 성공이 표/레이아웃/읽기 순서의 완전한 보존을 뜻하지 않는다.
- 규칙 기반 image_desc 9건이 생성됐으며, bbox 주변 텍스트 근거가 약한 이미지 946건은 NULL로 남았다. image_desc를 검색 ranking에 사용하는 기능은 추가 검증이 필요하다.
- 등록 재현 chunk 수와 DB 행 수는 모두 947이나, 전체 텍스트 본문을 행별 비교한 결과는 별도 확인 필요.
