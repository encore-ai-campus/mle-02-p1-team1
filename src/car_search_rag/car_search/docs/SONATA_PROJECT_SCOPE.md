# Sonata 프로젝트 범위

이 문서는 Sonata 프로젝트의 분석·평가·제출 범위를 고정하는 기준 문서(Single Source of Truth)다. M0~M9, EDA, 검색 평가, 성능 측정, Notion, README, PPT 자료를 작성하기 전에 이 문서와 대조한다. 이 문서의 현재 DB 수치는 2026-10-04 재등록 후 Sonata `car_id`로 한정해 확인한 결과에 근거한다. 과거 평가·실험 결과는 각 실행 당시의 ID를 보존한다.

## 1. 프로젝트 대상

- 차량: Hyundai Sonata 2026 (영문 DB 값: `hyundai / sonata / 2026`)
- project/model code: `DN8`
- 공식 배포처: [현대자동차 공식 매뉴얼 사이트](https://ownersmanual.hyundai.com/manual/쏘나타?langCode=ko_KR&countryCode=A99&projCode=DN8&year=2026&content=pdfDownload)
- 자료 형태/언어: 사이트에서 직접 다운로드한 정적 국문 취급설명서 PDF (`ko_KR`); 별도 데이터 수집 API 미사용
- 현재 Sonata 식별자: `car_id = 20261004_000015`
- 원본 PDF: `data/DN8_2026_ko_KR.pdf`
- PDF 페이지: 508
- 비어 있지 않은 page text: 508페이지
- 동일 분할 코드로 재현한 chunk: 947개
- PDF 크기: 43,423,714 bytes
- PDF SHA-256: `F83F44ABCF8F59C30FA4D0B0B419A8E7AACA54DA7D6F5C5FC9B3F83CAB650E23`
- 현재 파일 검증일: 2026-10-04; 최초 다운로드일은 확인 가능한 기록 없음
- 문서 식별: Hyundai Sonata 2026 DN8 Korean owner's manual; 공식 revision/edition 표기는 확인되지 않음

차량 모델 정보는 `app_kbj.py`의 차량 선택 옵션, `car_manual.py`의 등록 예제, Sonata 조건으로 제한한 기존 DB 확인 자료에서 대조했다. `EDA_REPORT.md`에는 PDF 전체 508페이지에서 텍스트 추출 성공, `EXPERIMENT_LOG.md` 및 `DATASET_SPEC.md`에는 Sonata `car_id`와 DB 적재 건수가 기록되어 있다.

## 2. 데이터 범위

현재 데이터베이스에는 여러 차량/사용자의 데이터가 함께 있을 수 있다. 이 프로젝트의 분석·평가·제출 대상은 위 `car_id`로 식별되는 Sonata 데이터뿐이다.

- 다른 차량 데이터는 Sonata 프로젝트 통계에 포함하지 않는다.
- 다른 사용자/팀원의 파이프라인 결과는 사용하지 않는다.
- 공용 테이블을 조회할 때는 모든 관련 집계에 Sonata `car_id` 조건을 적용한다.
- 전체 DB, 전체 스키마 또는 다른 차량의 총계를 Sonata 수치로 인용하지 않는다.
- 행의 차량 귀속이 불명확하면 임의로 포함하지 않고 `[확인 필요]`로 남긴다.

## 3. 대상 DB 테이블

아래 네 테이블은 `CarManualRepository`, `car_manual.sql`, 제공된 프로젝트 DDL 및 2026-10-04 재등록 후 Sonata 범위 읽기 전용 DB 확인에서 확인한 테이블이다. 건수는 현재 Sonata `car_id=20261004_000015` 조건의 결과이며 데이터베이스 전체 건수가 아니다.

| 테이블 | Sonata 식별 조건 | 현재 건수 | 프로젝트에서의 역할 |
|---|---|---:|---|
| `public.car` | `car_id = '20261004_000015'` | 1 | Sonata 브랜드·차종·연식 식별 정보 |
| `public.car_manual_chapter` | `car_id = '20261004_000015'` | 10 | PDF 매뉴얼 장/Chapter 정보 |
| `public.car_manual_chunk` | `car_id = '20261004_000015'` | 947 | 페이지 출처가 연결된 검색 본문 및 embedding |
| `public.car_manual_image` | `car_id = '20261004_000015'` | 955 | 매뉴얼 페이지 이미지 URL 및 메타데이터 |

`car_manual_chunk` 중 embedding이 있는 row는 947개이며, 기존 DB 확인에서 벡터 길이는 모두 1536으로 기록되어 있다. 이 건수는 공유 테이블 전체의 통계로 일반화하지 않는다.

## 4. RAG 데이터 규격

확인 근거는 `common/document_reader.py`, `car_manual_register_service.py`, `car_manual_search_service.py`, `car_manual.sql`, 프로젝트 DDL 및 기존 DB catalog 확인이다.

- PDF 텍스트: `pypdf.PdfReader`를 통해 페이지별 `page.extract_text()` 호출
- 페이지 출처: PDF 순서 기준 1부터 시작하는 `page_no` 보존
- 분할: `RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)`
- chunk 순번: 전체 분할 결과에 1부터 연속 `chunk_no` 부여
- embedding 입력: 각 `chunk.page_content`
- embedding 모델: `text-embedding-3-small`
- embedding 차원: 1536
- 저장/검색: PostgreSQL + pgvector, `car_manual_chunk_embed_vec <=> :EMBEDDING`으로 cosine distance 정렬
- vector index: 실제 DB catalog 확인 결과 `car_manual_chunk_embed_vec` 대상 HNSW index와 `vector_cosine_ops`가 존재함
- 실행계획(2026-10-04): production `search_car_manual` 구조에 Sonata `car_id`의 저장 embedding을 사용한 `EXPLAIN (ANALYZE, BUFFERS, VERBOSE)`에서는 `car_manual_chunk_pkey` Index Scan과 top-N heapsort가 관찰됐고 HNSW index는 선택되지 않았다. Planning Time 5.835 ms, Execution Time 15.178 ms. 이는 이번 한 번의 실행계획 결과이며 planner가 인덱스를 선택하지 않은 이유를 데이터 규모 하나로 단정하지 않는다.

## 5. 전처리 규격

### 수행 확인

- 각 PDF 페이지에서 `extract_text()`로 텍스트를 읽고 페이지 번호를 보존한다.
- 페이지 Document를 `RecursiveCharacterTextSplitter`로 분할한다.
- 각 chunk에 page metadata와 순차 `chunk_no`를 부여한다.
- `chunk.page_content`를 `embed_documents()`에 전달한다.
- 이미지 추출은 별도 PyMuPDF 경로에서 수행한다. 이는 텍스트 chunk 생성과 별도 처리다.

### 등록 경로에서 확인되지 않은 처리

아래는 해당 등록 코드 경로에서 적용을 확인하지 못했다는 뜻이며, 다른 도구나 수작업에서 수행됐다고 추정하지 않는다.

- OCR 수행
- 별도 앞뒤 공백 trim 또는 전역 공백 정규화
- 개행 강제 제거
- 특수문자 제거
- chunk 본문 중복 제거
- 추출 텍스트를 대상으로 한 별도 규칙 기반 정제
- 빈 page text 제거 로직

따라서 분석·평가 문서에는 위 처리를 완료한 것으로 쓰지 않는다. 빈 문자열/중복 여부는 실제 집계가 있는 경우에만 수치를 인용한다.

### 원본 파일 및 재등록 기준

- 확인일: 2026-10-04. 최초 다운로드일은 확인 가능한 기록이 없다.
- 원본 크기: 43,423,714 bytes; SHA-256: `F83F44ABCF8F59C30FA4D0B0B419A8E7AACA54DA7D6F5C5FC9B3F83CAB650E23`.
- 문서 식별: Hyundai Sonata 2026 DN8 Korean owner's manual. 공식 revision/edition 번호는 확인되지 않았다.
- 등록 코드는 PDF를 자동 다운로드하거나 DB 적재를 idempotent upsert하지 않는다. 입력은 `data/DN8_2026_ko_KR.pdf`이며, car row가 없으면 `FN_GET_BIZ_ID('CAR')`에서 신규 ID를 만든다.
- Storage 경로는 `cars/{brand}/{model}/{image_name}`이고 `upsert=true`다. 동일 object key는 덮어쓰지만 car_id/사용자 ID가 경로에 없어 같은 차종은 prefix를 공유할 수 있다. 이 구조는 이번에 변경하지 않았으며 운영상 주의/개선 후보로 둔다.
- 2026-10-04 Sonata 재등록 후 새 ID `20261004_000015`와 적재 건수·중복 점검을 확인했다. 오류 및 상세 검증은 `EXPERIMENT_LOG.md`에 기록한다.

## 6. 검색 파이프라인

```text
Streamlit app_kbj.py
  → CarManual / CarManualSearchService
  → OpenAI text-embedding-3-small query embedding
  → CarManualRepository.search_manual()
  → SqlSession.select_list("car_manual.search_car_manual", ...)
  → car_manual.sql: search_car_manual
  → PostgreSQL + pgvector (<=> cosine distance)
  → Sonata 매뉴얼 검색 결과
  → ask_manual()의 답변 생성 흐름
```

`search_car_manual`은 브랜드·차종·연식 조건으로 검색 범위를 제한하고 chunk vector 거리로 정렬한다. 서비스 호출 시 사용하는 모델 조건은 `hyundai / sonata / 2026`이다. 실제 검색 품질 평가에서는 이 조건이 Sonata `car_id`에 대응하는지 검색 결과를 함께 확인해야 한다.

**평가 범위 주의:** 현재 SQL의 검색 조건은 `car_id` 직접 조건이 아니라 브랜드·차종·연식 조건이다. 2026-10-04 재등록 후 `hyundai / sonata / 2026` 조건은 현재 Sonata `car_id=20261004_000015` 한 건에 대응함을 확인했다. 과거 M6/E2E 실행은 당시 ID를 기록한 historical 결과이며 현재 ID로 소급 변경하지 않는다.

## 7. 평가 범위

M6/M7 평가에서는 다음 규칙을 적용한다.

- 질문과 정답 근거는 Sonata 매뉴얼에서 확인 가능한 내용으로 한정한다.
- 검색 대상은 Sonata 데이터만 사용하고, 평가 SQL/결과에도 Sonata 식별 조건을 유지한다.
- Hit@K/MRR 계산에는 Sonata 검색 결과 및 Sonata 근거 chunk만 넣는다.
- Santa Fe 또는 다른 차량 결과를 Sonata 점수와 합산하지 않는다.
- `zzong_santafe_lag` 자료와 그 파이프라인을 호출하는 notebook/결과는 Sonata 평가에서 제외한다.
- 다른 notebook의 검색 결과는 Sonata 평가셋과 근거를 독립적으로 확인하기 전에는 사용하지 않는다.
- SQL 결과 중복 제거/이미지 JOIN 정합성 개선은 검색 결과 무결성 변화로 기록하며, 별도 고정 질문셋의 지표 없이 검색 품질 향상으로 해석하지 않는다.

## 8. 제출 자료 사용 원칙

다음 자료는 Sonata 범위와 이 문서의 기준값을 사용한다.

- EDA 및 TF-IDF 분석
- 데이터셋/전처리 명세
- RAG 검색 평가 및 개선 실험
- Streamlit 설명 및 시연
- README와 Notion M0~M9
- PPT 및 최종 발표

문서별 오래된 수치나 미완료 상태가 발견되면 이 문서만으로 과거 내용을 자동 수정하지 않는다. 실제 근거를 확인한 뒤 해당 문서의 수정 작업을 별도로 한다.

## 9. 제외 대상

- `src/car_search_rag/zzong_santafe_lag`의 Santa Fe 파이프라인 및 결과
- `notebooks/23_db_retrieval_evaluation.ipynb`, `notebooks/24_m7_specific_term_comparison.ipynb` 등 위 별도 파이프라인을 참조하는 평가 결과
- 공유 DB의 다른 차량 row 및 Sonata `car_id`로 귀속되지 않는 데이터
- Sonata 앱과 직접 관계없는 별도 차량 실험

제외 대상은 범위 식별을 위해 경로/차량명만 적는다. 개인 식별 정보나 불필요한 상세는 기록하지 않는다.

## 10. 현재 프로젝트 기준값

| 항목 | 기준 |
|---|---|
| 차량 | Hyundai Sonata 2026 |
| `car_id` | `20261004_000015` |
| 원본 PDF | `data/DN8_2026_ko_KR.pdf` |
| PDF 페이지 | 508 |
| 비어 있지 않은 page text | 508 |
| DB chapter | 10 |
| DB chunk | 947 |
| DB image record | 955 |
| embedding 보유 chunk | 947 |
| embedding dimension | 1536 |
| chunk size / overlap | 800 / 150 |
| Vector DB | PostgreSQL + pgvector |
| 실제 DB vector index | HNSW, `car_manual_chunk_embed_vec`, `vector_cosine_ops` |

### 수치의 근거와 한계

PDF 페이지/텍스트 및 chunk 수는 `EDA_REPORT.md`, 동일 splitter 재처리 기록, `PREPROCESSING_SPEC.md`와 대조했다. DB 건수와 embedding dimension은 Sonata `car_id`만 대상으로 한 2026-10-04 읽기 전용 재집계 결과다. index 유형/operator class는 제공 DDL 및 catalog에서 확인했고, 이번 실제 실행계획에서는 HNSW가 선택되지 않은 것도 확인했다. 실행계획은 한 번의 관측으로 일반화하지 않는다.
