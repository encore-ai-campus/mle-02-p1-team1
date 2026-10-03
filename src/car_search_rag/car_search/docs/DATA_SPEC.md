# 데이터 명세서

## 범위와 데이터 원천

핵심 프로젝트 데이터셋은 소나타 매뉴얼 PDF 한 개다.

| 파일 | 차량 매핑 | 저장소 위치 | 출처 |
|---|---|---|---|
| DN8_2026_ko_KR.pdf | 코드 실행 예제에서 hyundai / sonata / 2026으로 등록 | data/DN8_2026_ko_KR.pdf | 저장소에 포함된 PDF. 제조사 원본 URL·수집 일자·판본 출처는 확인되지 않음 |

분석·전처리·평가의 입력 범위는 위 PDF만으로 한정한다. 현재 실행 자료에는 이 PDF 기준 페이지 수, 텍스트 길이, chunk 수, 결측률 또는 검색 평가 수치가 없다. 이 값은 현재 미측정으로 둔다.

사용자가 제공한 public.car, public.car_manual_chapter, public.car_manual_chunk, public.car_manual_image DDL을 아래 저장 스키마의 근거로 사용한다. DB 배포 환경이 이 DDL과 일치하는지는 별도 확인하지 않았다.

## 핵심 RAG 저장 구조

아래는 `car_manual_repository.py`가 mapper에 전달하고 `car_manual.sql`이 쓰거나 조회하는 필드다. 타입·NULL 여부는 사용자가 제공한 DDL을 기준으로 적었다. 이 DDL 정의와 별개로 각 insert에서 실제로 전달되는 값은 생성 과정에 기술했다.

| 데이터/컬럼 | 타입 | Nullable 여부 | 의미 | 출처 | 생성 과정 |
|---|---|---|---|---|---|
| 차량 `car.car_id` | `varchar(20)` | NOT NULL | 차량 식별자, PK | DB 함수 및 merge 반환값 | `CarManualRegisterService.insert_car` → `CarManualRepository.insert_car` → `merge_car` |
| 차량 `car.car_brand_nm`, `car_brand_eng_nm` | `varchar(100)` | NOT NULL | 제조사 한글명·영문명 | 등록 함수 인자 | PDF 등록 호출자가 전달; `merge_car`에 사용 |
| 차량 `car.car_nm`, `car_eng_nm` | `varchar(150)` | NOT NULL | 차종 한글명·영문명 | 등록 함수 인자 | PDF 등록 호출자가 전달; `merge_car`에 사용 |
| 차량 `car.car_model_yr` | `int4` | NOT NULL | 차종 연식 | 등록 함수 인자 | PDF 등록 호출자가 전달; 검색 필터에도 사용 |
| 차량 `car.create_date`, `update_date` | `timestamptz` | NOT NULL; `DEFAULT now()` | 등록·수정 일시 | DB 기본값 또는 update SQL | 삽입 시 기본값; 차량 merge 시 `update_date=now()` |
| 차량 `car.create_user_id`, `update_user_id` | `varchar(50)` | NOT NULL | 생성·수정 사용자 ID | Repository의 `SYSTEM` 상수 | 차량 merge SQL에 바인딩 |
| 장 `car_manual_chapter.car_id`, `car_manual_chapter_id` | 각각 `varchar(20)` | NOT NULL; 복합 PK | 차량·장 식별자 | 차량 등록 결과 및 `FN_GET_BIZ_ID` | `_insert_car_manual_data`가 ID 생성 후 장을 등록 |
| 장 `car_manual_chapter.car_manual_chapter_no` | `varchar(20)` | NOT NULL | 매뉴얼 장 번호 | PDF 목차 순서 | `_extract_pdf_chapters` 결과 순번을 등록 코드가 전달 |
| 장 `car_manual_chapter.car_manual_chapter_nm` | `varchar(200)` | NOT NULL | 장 제목 | PDF 1단계 목차 | `_extract_pdf_chapters` → `insert_car_manual_chapter` |
| 장 `car_manual_chapter.car_manual_chapter_sort_no` | `int4` | NULL 허용 | 장 정렬 순번 | PDF 목차 순서 | 등록 코드에서 순번 전달 |
| 장 `create_date`, `update_date` | `timestamptz` | NOT NULL; `DEFAULT now()` | 등록·수정 일시 | DB 기본값 | 삽입 시 기본값 |
| 장 `create_user_id`, `update_user_id` | `varchar(50)` | NOT NULL | 생성·수정 사용자 ID | Repository의 `SYSTEM` 상수 | 장 INSERT 파라미터에 전달 |
| 청크 `car_manual_chunk.car_id`, `car_manual_chapter_id`, `car_manual_chunk_id` | 각각 `varchar(20)` | NOT NULL; 복합 PK | 차량·장·청크 식별 및 연결 | 차량·장 ID, `FN_GET_BIZ_ID` | Repository가 장 범위를 찾아 청크 INSERT 파라미터에 전달 |
| 청크 `car_manual_chunk.car_manual_chunk_page_no` | `int4` | NULL 허용 | 청크가 나온 PDF 페이지 | `DocumentReader` 페이지 순회 | `page_no` metadata를 Repository가 전달 |
| 청크 `car_manual_chunk.car_manual_chunk_no` | `int4` | NOT NULL | 분할 결과 내 청크 순번 | split 결과 순서 | `_extract_and_split_chunks`가 1부터 부여 |
| 청크 `car_manual_chunk.car_manual_chunk_txt` | `text` | NOT NULL | 검색 대상 청크 텍스트 | PDF 페이지 텍스트 | `RecursiveCharacterTextSplitter` 결과를 Repository가 전달 |
| 청크 `car_manual_chunk.car_manual_chunk_embed_vec` | `public.vector` (차원 미지정) | NULL 허용 | 청크 embedding vector | `text-embedding-3-small` 출력 | `_create_chunk_embeddings` 뒤 Repository가 pgvector `Vector`로 전달; 검색 서비스 상수는 1536 |
| 청크 `create_date`, `update_date` | `timestamptz` | NOT NULL; `DEFAULT now()` | 등록·수정 일시 | DB 기본값 | 삽입 시 기본값 |
| 청크 `create_user_id`, `update_user_id` | `varchar(50)` | NOT NULL | 생성·수정 사용자 ID | Repository의 `SYSTEM` 상수 | 청크 INSERT 파라미터에 전달 |
| 이미지 `car_manual_image.car_id`, `car_manual_chapter_id`, `car_manual_image_id` | 각각 `varchar(20)` | NOT NULL; 복합 PK | 차량·장·이미지 식별 및 연결 | 차량·장 ID, `FN_GET_BIZ_ID` | Repository가 장 범위를 찾아 이미지 INSERT 파라미터에 전달 |
| 이미지 `car_manual_image.car_manual_image_page_no` | `int4` | NULL 허용 | 이미지가 나온 PDF 페이지 | `pymupdf` 이미지 추출 순서 | `_extract_and_upload_images`, `_upload_single_image` |
| 이미지 `car_manual_image.car_manual_image_no` | `int4` | NOT NULL | 페이지 내 이미지 순번 | `pymupdf` 이미지 추출 순서 | `_upload_single_image` |
| 이미지 `car_manual_image.car_manual_image_url` | `varchar(1000)` | NOT NULL | 업로드 이미지 URL | Supabase Storage 업로드 결과 | `StorageManager.upload_car_image_bytes` 결과를 Repository가 저장 |
| 이미지 `car_manual_image.car_manual_image_desc` | `text` | NULL 허용 | 이미지 설명 | 현재 등록 코드에서 `None` | `CarManualRepository.insert_car_manual_images`가 현재 `None` 전달 |
| 이미지 `create_date`, `update_date` | `timestamptz` | NOT NULL; `DEFAULT now()` | 등록·수정 일시 | DB 기본값 | 삽입 시 기본값 |
| 이미지 `create_user_id`, `update_user_id` | `varchar(50)` | NOT NULL | 생성·수정 사용자 ID | Repository의 `SYSTEM` 상수 | 이미지 INSERT 파라미터에 전달 |

제공된 DDL에서 이미지의 `(car_id, car_manual_chapter_id)`는 장 테이블을 참조하는 FK다. 차량/장/청크 관계는 복합 PK 및 mapper SQL join으로 표현된다. 별도의 원본 PDF 레코드 테이블, PDF 경로·해시·발행판 정보 컬럼은 제공된 핵심 DDL에서 확인되지 않았다. 페이지 번호는 PDF의 1부터 시작하는 페이지 인덱스를 사용한다. chapter는 목차 1단계 기준으로 만들고 청크 페이지 번호가 장의 시작·끝 범위에 들면 Repository에서 장 ID를 연결한다.

## 결측 데이터

- 소나타 PDF에서 추출해 저장한 핵심 DB 행의 컬럼별 결측률 계산 결과는 확인되지 않았다. 결측률은 소나타 car_id에 해당하는 행만 필터링해 산출해야 한다.
- 청크 텍스트가 빈 페이지에서 생성되는지 사전 필터링하는 동작은 핵심 `DocumentReader.set_pdf_doc_list`에서 확인되지 않았다.
- 이미지 설명은 현재 등록 코드가 `None`을 저장한다. 이는 설명 필드가 비어 있을 수 있음을 보여주지만 전체 DB 결측률은 아니다.
- **소나타 기준 현재 결측률 측정 결과 없음 - EDA 단계에서 소나타 레코드만 필터링해 측정 필요**

## 핵심 구현 근거

- `src/car_search_rag/common/document_reader.py`: `DocumentReader.set_pdf_reader`, `set_pdf_doc_list`
- `src/car_search_rag/car_search/car_manual_register_service.py`: `CarManualRegisterService.insert_pdf_docs`, `_extract_pdf_chapters`, `_extract_and_split_chunks`, `_create_chunk_embeddings`, `_extract_and_upload_images`, `_insert_car_manual_data`
- `src/car_search_rag/car_search/car_manual_repository.py`: 차량·chapter·chunk·image 저장 및 검색 메서드
- `src/car_search_rag/car_search/car_manual.sql`: `merge_car`, chapter/chunk/image INSERT 및 `search_car_manual`
