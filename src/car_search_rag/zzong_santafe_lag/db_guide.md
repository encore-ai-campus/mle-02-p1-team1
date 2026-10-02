# 개인 Supabase 테이블 준비와 DBeaver 사용

## 현재 상태 — 2026-10-02

**전체 글·벡터 저장 완료:** 개인 스키마 `zzong_santafe_lag`의 새 작업 `ca9d2721-3d48-42a8-8748-3935e78515e5`가 `ready`입니다. 부모 527개·청크 2,213개를 저장했고 저장 전후 모든 필드·벡터가 일치했습니다. 기존 표본 모든 행·벡터의 내용도 동일함을 확인했습니다.

| 테이블 | 개인 스키마 합계 | 이번 전체 작업 |
|---|---:|---:|
| documents | 1 | 기존 PDF 재사용 |
| processing_runs | 2 | 새 작업 1 |
| parent_records | 531 | 527 |
| chunks | 2,224 | 2,213 |
| images | 864 | 864 참조, 기존 3개 재사용 |
| record_images | 1,160 | 1,157 |

테이블·색인·TOAST 할당 합계 **16,072,704바이트(15.33MiB)**입니다. Storage 파일과 DB 전체 관리 영역·WAL은 제외합니다. 추가 파일 업로드는 0개이며 공개 그림은 기존 3개입니다. 자동 초안 507개·설명 없는 그림 연결 1,145건을 검토 완료로 변경하지 않았습니다.

**DBeaver에서 이번 자료만 보기:** 연결 → postgres → Schemas → zzong_santafe_lag → Tables를 새로고침합니다. processing_runs의 Data에서 위 작업 번호와 ready를 찾습니다. parent_records 또는 chunks의 Data 필터에 다음을 입력하면 기존 표본과 구분됩니다.

```sql
run_id = 'ca9d2721-3d48-42a8-8748-3935e78515e5'
```

전체 검색은 `manual.py db-full-search --run-id <위 작업 번호> --question "질문"` 또는 `notebooks/21_full_db_search.ipynb`에서 사용합니다. 기본값은 기존 글자·질문 목적 검색을 저장 벡터에 적용합니다. `--method semantic`은 pgvector 코사인 검색만 수행합니다. 문서 임베딩을 다시 계산하거나 DB에 쓰지 않습니다.

M5 첫 단계는 `manual.py answer --run-id <위 작업 번호> --question "질문"` 또는 `notebooks/22_pdf_excerpt_answer.ipynb`입니다. 검색 결과에서 확인한 자료와 필수 각주 한 묶음을 발췌하고 출처·사용 가능한 그림을 붙입니다. 사용자 선택으로 LLM은 아직 연결하지 않았습니다. 최신 정보·근거 부족·미검토 자료는 각각 확인 불가 또는 검토 필요를 안내하며 DB나 Storage에 새로 저장하지 않습니다. 이 임시 선택 규칙은 모든 질문의 의미를 검증하는 기능은 아닙니다.

### 이전 표본 준비·확대 준비 기록

아래는 각 작업 당시의 결과입니다. 이전의 23행·512KiB와 '전체 저장 전' 표현은 당시 상태이며 현재 합계는 위 표를 봅니다.

- 개인 테이블 6개·컬럼 66개의 한국어 설명을 등록했습니다. 새 읽기 전용 연결에서 문구를 대조했고, 개인 표본 23개 행의 건수와 컬럼 자료형·제약 조건은 그대로입니다. 설명 SQL은 `db/04_describe_tables.sql.txt`입니다.
- 사용자 승인 후 그림 3개를 개인 Storage 경로에 업로드했습니다. 합계 63,745바이트. 인증·공개 다운로드를 원본과 대조한 뒤 개인 images의 storage_bucket·storage_path·upload_status를 연결하고 새 읽기 전용 연결에서 다른 필드·벡터 유지도 확인했습니다.
- 개인 브랜치: zzong/santafe-lag.
- 저장된 청크 11개로 세 질문의 의미 검색을 실행했습니다. PDF 43쪽 표·필수 각주, 44쪽 그림 2개, 45쪽 그림 1개가 관련 결과에 연결됐습니다. 조회 트랜잭션은 읽기 전용이며 문서 벡터를 다시 계산하지 않았습니다.
- 전체 저장 범위 조사: 부모 527·청크 2,213·고유 그림 864·주제와 그림 연결 1,157건. 설명 없는 연결은 1,147건입니다. 현재 DB는 23행·512KiB 그대로이며 전체 저장·추가 그림 업로드는 아직입니다.
- 이후 74쪽 그림 설명 2개를 Python에 반영하고 전체 저장용 prepare/embed/save 코드를 준비했습니다. full-preview에서 전체 행 변환·연결·토큰 검사를 실행했고 실제 임베딩·전체 저장은 아직입니다. 19번의 1,147건은 보완 전 조사 수치입니다.
- DBeaver의 zzong 연결에서 postgres DB와 기존 public 테이블을 확인했습니다.
- 읽기 전용 SQL이 1행을 반환했습니다. DB 사용자 postgres, vector 0.8.0, 확장 위치 public.
- 사용자 승인 후 개인 스키마 zzong_santafe_lag와 빈 테이블 6개를 DBeaver에서 생성했습니다. 생성 SQL은 개인 스키마에만 적용했습니다.
- 승인한 표본 23개 행을 개인 SQL Mapper로 저장했습니다. PDF·처리 설정 각각 1개, 원문 4개, 청크 11개, 이미지·연결 각각 3개입니다. 처리 상태 ready.
- 저장 확정 후 새 읽기 전용 연결에서 원문·출처·각주·이미지 경로와 벡터를 대조했습니다. 저장 전후 벡터 값은 float32 기준으로 정확히 일치합니다.
- 테이블·기본 색인의 실제 할당 용량은 524,288바이트(512KiB, 약 0.5MB)입니다. 빈 구조의 192KiB에서 320KiB 증가했습니다. DB 전체 관리 영역·WAL·Storage는 제외한 값입니다.
- Storage는 표본 그림 3개만 완료했습니다. DB 표본 코사인 검색은 완료했고 PDF 원본 파일·전체 그림 업로드·전체 기록 저장·기존 결합 검색의 DB 적용은 아직입니다.
- 개인 연결 변수는 src/car_search_rag/zzong_santafe_lag/.env의 ZZONG_DB_URL에 분리했습니다. 기존 연결 설정을 읽기 전용으로 대조한 뒤 복사했으며 팀 .env는 수정하지 않았습니다. 개인 .env의 Git 제외도 확인했습니다.
- DBeaver에 연결해도 Python 연결 설정이 자동으로 생기는 것은 아닙니다.

## 질문으로 내 표본 찾기

**그림을 볼 수 있는 입구:** 프로젝트 루트의 `notebooks/18_db_sample_search.ipynb`. 위에서 아래로 실행하고 `question` 변수만 바꾸어 같은 모델을 재사용합니다. 노트북 실행 결과는 아직 저장하지 않았습니다.

터미널에서는 다음 명령을 사용합니다.

```powershell
.\.venv\Scripts\python.exe src\car_search_rag\zzong_santafe_lag\manual.py db-search --question "차대번호는 어디에서 확인하나요?" --top-k 1 --full-text
```

1. 개인 DB의 ready 작업 `dc327282-8cfd-4eb3-a2b0-1433e0b088ce`와 저장한 모델 버전을 확인합니다.
2. 같은 로컬 한국어 모델로 **질문 하나만** 768차원 벡터로 바꿉니다.
3. `chunks.embedding`과 질문 벡터의 코사인 유사도를 비교합니다. `<=>`는 코사인 거리이고 `1 - 거리`가 출력 점수입니다.
4. `parent_records`에서 전체 검색용 글·보존 원문·PDF/매뉴얼 쪽수를 읽습니다. metadata의 required_context_record_ids를 따라 필수 각주도 읽습니다.
5. `record_images`의 설명과 `images`의 개인 Storage 경로로 공개 그림 주소를 만듭니다. 그림 자체 표시는 노트북에서 합니다.

실제 첫 결과: 용량·추천 사양 질문은 PDF 43/매뉴얼 38(표와 각주 2기록), SAE 점도 질문은 PDF 44/매뉴얼 39(그림 2개), 차대번호 질문은 PDF 45/매뉴얼 40(그림 1개). DB 표본 안에서의 세 질문 연결 확인입니다.

이 명령은 표본만 읽습니다. 기존 메모리 실험의 글자 검색·질문 목적 규칙을 결합하지 않았으며, 근거 부족 판정과 답변 생성은 미구현입니다. 따라서 관련 없는 질문에도 후보가 나올 수 있고 유사도는 정답 확률이 아닙니다. 새 DB 테이블·색인을 만들거나 팀 공통 자료를 수정하지 않습니다.

## 여섯 테이블을 읽는 순서

| 테이블 | 무엇을 담나 |
|---|---|
| documents | PDF 파일과 SHA-256, 페이지 수, 경로 |
| processing_runs | 청킹·임베딩 설정과 버전 |
| parent_records | 주제 전체 글, 원문, 출처, 검토 상태 |
| chunks | 실제 검색 글과 768차원 벡터 |
| images | PDF 내부 그림 식별자와 파일 경로 |
| record_images | 주제와 그림의 연결, 그림 설명, 연결 검토 상태 |

documents → processing_runs → parent_records → chunks 순서로 연결됩니다.
parent_records와 images는 record_images를 통해 연결됩니다.
파일 업로드 상태와 그림 설명의 검토 상태는 서로 다른 정보입니다.

- 부모의 raw_text는 보존 원문, content는 정리한 검색용 글입니다.
- 자식의 content는 제목을 포함하여 모델에 실제 넣은 글입니다. 벡터와 반드시 일치해야 합니다.
- metadata는 기존 출처 딕셔너리 전체를 JSONB로 보관합니다. 표 행·각주·필수 문맥 연결을 버리지 않습니다.
- 자식 metadata에도 기존 정보가 남지만 검토 상태를 조회할 때는 부모 컬럼을 기준으로 합니다.
- 같은 작업 안에서만 record_id가 고유합니다. 청킹 규칙 변경 시 새 run_id로 저장합니다.
- PDF의 실제 이미지 키를 식별자로 사용합니다. 확인한 예제에 키가 없으면 pypdf 키와 실제 파일명을 대조해야 합니다.
- image_key_sha256은 내부 키를 JSON으로 일정하게 직렬화한 식별값입니다. 이미지 파일 내용의 해시와는 다릅니다.
- 현재 768차원·128토큰에 맞춘 설계입니다. 다른 차원·입력 한도로 바꾸면 SQL 구조도 재검토합니다.

## 파일 역할

1. db/01_create_tables.sql.txt: 개인 스키마와 빈 테이블 6개 생성. 2026-10-01 승인 후 실행 완료. 다시 실행하지 않습니다.
2. db/02_inspect_tables.sql.txt: DB·pgvector·개인 테이블의 읽기 전용 확인.
3. mappers/manual_store.sql.txt: Python에서 호출할 저장·조회·의미 검색 SQL.
4. database.py: 개인 SQL을 등록하고 SQL Mapper 방식으로 실행.
5. notebooks/13_supabase_table_design.ipynb: 개념·파일 위치·읽기 전용 조회 연습.
6. db_rows.py: 43·44·45쪽 예제를 여섯 테이블의 행으로 메모리 변환. 실제 저장은 하지 않습니다.
7. db_sample.py: connection(읽기 전용 조회) / preview(행 변환 미리보기) 실행 파일.
8. notebooks/14_db_sample_rows.ipynb: 연결 조회·행 변환·원문/청크/그림 연결을 작은 셀로 확인하는 연습.
9. db/04_describe_tables.sql.txt: 개인 스키마·테이블 6개·컬럼 66개의 한국어 설명. 데이터 저장·테이블 생성 SQL이 아닙니다. 2026-10-02 승인 후 적용했습니다.
10. manual.py db-search / db_search_service.py: 질문만 임베딩하고 저장된 표본의 원문·각주·그림을 연결하는 읽기 전용 실행·서비스입니다.
11. notebooks/18_db_sample_search.ipynb: 질문·출처·그림을 작은 셀로 확인하는 연습입니다. notebooks는 프로젝트 루트 폴더입니다.

생성 SQL에는 기존 자료 삭제·덮어쓰기나 공통 확장 설치를 넣지 않았습니다.
같은 스키마가 이미 있으면 중단합니다. 재실행용 수정 스크립트가 아닙니다.
전체 스크립트의 BEGIN부터 COMMIT까지 한 번에 실행해야 합니다.
오류가 나면 뒤의 COMMIT을 실행하지 말고 ROLLBACK;으로 열린 트랜잭션을 정리한 뒤 원인을 확인합니다.

## DBeaver에서 테이블 보기

생성 SQL 적용 후 탐색기의 Schemas에서 새로 고침(F5)을 합니다.

zzong → Databases → postgres → Schemas → zzong_santafe_lag → Tables

- 테이블을 열고 Properties에서 Columns를 보면 컬럼 구조를 볼 수 있습니다.
- Data를 선택하면 저장된 행을 볼 수 있습니다. 빈 구조만 만들면 0행이 정상입니다.
- 엔티티 관계도에서는 부모·자식·이미지 연결을 볼 수 있습니다.
- 현재 public의 car_manual_chunk 등은 기존 자료이므로 개인 저장 대상으로 사용하지 않습니다.
- schema는 DB의 테이블 공간이며 Storage 버킷과 다릅니다. 이 생성 SQL은 버킷을 만들지 않습니다.

확인 SQL은 새 SQL 편집기에 가져와 사용합니다. 생성 SQL과 섞어 실행하지 않습니다.
DBeaver 메뉴 명칭·단축키는 현재 창의 표시를 우선합니다.
공식 참고: https://dbeaver.com/docs/dbeaver/Script-Management/

### DBeaver에서 한국어 설명 보기

1. 왼쪽 `Schemas → zzong_santafe_lag`를 선택하고 새로 고침합니다.
2. 테이블의 `Properties / 속성 → Columns / 컬럼`에서 `Comment / 설명` 항목을 확인합니다.
3. 관계도 빈 곳을 오른쪽 클릭하고 `Show Attributes / 속성 표시 → Show comments / 설명 표시`를 켭니다. 메뉴 번역은 창에 따라 다를 수 있습니다.
4. 이미 열린 관계도에 반영되지 않으면 닫았다가 다시 엽니다. 아래 전체 컬럼 설명표에서도 읽을 수 있습니다.

같은 DB를 조회하는 팀원도 등록한 설명을 볼 수 있습니다. DBeaver 표시 설정은 각자 켜야 합니다. 컬럼 이름을 한국어로 바꾸는 작업은 아닙니다.

공식 안내: https://dbeaver.com/docs/dbeaver/How-to-use-Diagrams/

## 팀 저장 방식과 다음 단계 — 2026-10-02

이 절은 업로드 전 검토 기록입니다. 이후 그림 3개 업로드·조회·DB 경로 연결과 세 질문의 표본 검색은 완료했습니다. 전체 저장은 준비 전이며 위의 현재 상태를 기준으로 봅니다. 실제 개인 파일명은 소나타에 맞춰 `page_0044_image_01.jpg` 형식을 적용했습니다.

팀 파일을 실행하지 않고 읽었으며, Supabase 구조·건수·모델 메타데이터·Storage 경로를 읽기 전용으로 조회했습니다. 아래는 조회 시점의 상태입니다. 이후 다른 사람이 저장하면 건수는 달라질 수 있으며, 테이블 이름만으로 작성자를 확정하지 않습니다.

| 확인 대상 | 실제 확인 상태 | 개인 프로젝트에 참고할 점 |
|---|---|---|
| `car_search`의 구성 | `document.py → document_service.py → document.sql` 등 실행·서비스·SQL 분리 | 개인 파일도 역할을 맞추고 README에 읽는 순서를 제시 |
| `public.car`, `car_manual_chapter`, `car_manual_chunk`, `car_manual_image` | 구조는 있음. 조회 시점에는 각각 0행 | 공통 차량/장/청크/그림 설계이며 저장 완료로 보지는 않음 |
| `public.casper_manual_chunks` | 1,874행. 제목·장·절·쪽수 범위·글·토큰 수 | 검색 글과 출처를 함께 보관하는 점은 현재 방식과 같음 |
| `public.casper_manual_embeddings` | 1,874행. 모델 `intfloat/multilingual-e5-base`, 버전 `v1`, `vector(768)` | 모델·버전·차원을 기록. 개인 모델과 다름 |
| Storage `images` | 공개 버킷. `cars/hyundai/sonata/` 151개, `cars/hyundai/ioniq5/` 1개 | 그림 파일은 Storage에, 경로·설명은 DB에 저장 |
| `common/storage_manager.py` | `cars/<브랜드>/<모델>/<파일명>` 경로, `upsert=true` | 개인 경로와 덮어쓰기 방침을 별도로 정해야 함 |

`car_manual_search_service.py`에는 OpenAI `text-embedding-3-small`, 1,536차원 설정이 있습니다. 실제 저장된 캐스퍼의 E5 768차원과 다릅니다. 0행인 공통 청크 테이블의 실제 저장 모델은 코드 설정만으로 확정하지 않습니다. 개인 모델은 로컬 `jhgan/ko-sroberta-multitask-mrl` 768차원을 유지했습니다.

**현재 PostgreSQL·pgvector 방향은 적절합니다.** 테이블을 여섯 개로 나눈 이유는 원문 보존, 처리 버전 구분, 각주 연결, 같은 그림의 여러 주제 연결입니다. 공통 테이블로 옮기거나 테이블 수를 줄이려면 이 정보를 보관하는 방법부터 다시 설계해야 합니다. 파일 구성 간소화와 DB 설계 변경은 별도로 판단합니다.

**768차원이 같아도 서로 다른 모델의 벡터를 섞어 검색하지 않습니다.** 개인 `run_id`와 모델 버전으로 범위를 고르고 질문도 같은 모델로 변환합니다. E5를 도입하려면 `query:` / `passage:` 입력 규칙, 문서 재임베딩을 별도로 검토해야 합니다. 이번에는 새 모델을 다운로드하거나 적용하지 않았습니다.

권장하는 다음 실험과 판단 순서:

1. **DB 청크 11개로 질문 검색:** 점도·VIN·오일 용량 질문을 같은 로컬 모델로 변환하고 부모·각주·그림 연결까지 읽습니다. `search_chunks` SQL과 메서드는 있지만 시작 명령 통합·이 실험 실행은 아직입니다.
2. **그림 3개만 개인 경로로 업로드·조회:** 예정 경로는 `images` 버킷의 `cars/hyundai/santafe_hev/zzong_santafe_lag/<PDF식별값>/pdf_page_0044/I1.jpg` 같은 형식입니다. 개인 폴더와 기존 파일 덮어쓰기 방침을 지정하고 업로드 범위·권한·용량을 확인한 뒤 적용합니다. 아직 경로나 파일을 생성하지 않았습니다.
3. **출처·문맥·그림 확인:** 표 각주, PDF/인쇄 쪽수, 다른 PC의 그림 표시, 재업로드 없는 조회를 점검합니다.
4. **전체 저장 범위 결정:** 전체 부모 527개·청크 2,213개에는 자동 초안 507개가 포함됩니다. 실험용 저장은 검토 상태를 유지해서 진행할 수 있지만, 저장을 검토 완료·답변 품질 완료로 표시하지 않습니다. 그림 864개의 설명도 모두 완료된 상태는 아닙니다.

우선 모델을 더 바꾸는 실험보다 저장한 표본의 검색·그림 표시 경로를 완성하는 것이 다음 목표입니다. 전체 그림 파일 크기는 추출 후 합산해야 확정됩니다. 현재 DB 약 0.5MB와 전체 DB 예상 15~30MB는 Storage 파일 용량과 별개입니다.

공식 모델 입력 규칙: https://huggingface.co/intfloat/multilingual-e5-base
공식 Storage 업로드·덮어쓰기 안내: https://supabase.com/docs/guides/storage/uploads/standard-uploads

## 업로드한 그림을 찾는 방법

**Supabase:** Storage → images → cars → hyundai → santafe_hev → zzong_santafe_lag → PDF 식별값 폴더. 안에 page_0044_image_01.jpg·page_0044_image_02.jpg·page_0045_image_01.jpg가 있습니다. 이 경로는 폴더 이름을 포함한 파일 경로이며 별도 버킷을 만들지는 않았습니다.

**DBeaver:** Schemas → zzong_santafe_lag → Tables → images → Data → 새로 고침. 3행의 upload_status는 uploaded, storage_bucket은 images, storage_path는 위 개인 경로입니다. file_name과 local_path는 기존 PC 파일 정보이며 그대로 보관합니다. 그림 설명은 record_images.description에 있습니다.

**노트북:** 17번의 셀을 위부터 실행하면 읽기 전용 준비 확인과 공개 주소의 그림 표시를 볼 수 있습니다. 이 노트북은 업로드하지 않습니다. 서비스의 준비 확인은 실제 파일을 읽어 원본과 비교하므로 URL 생성만 하는 확인과 다릅니다.

업로드 파일 크기는 PDF 44쪽 첫 그림 5,501바이트, 둘째 그림 19,316바이트, 45쪽 그림 38,928바이트입니다. 합계 63,745바이트는 그림 파일 내용이며 DB 할당 용량·Storage의 내부 관리 영역과는 다른 값입니다.

## SQL Mapper에서 Python으로 연결하는 방식

현재 실제 공통 로더는 src/car_search_rag 아래의 *.sql을 재귀 검색합니다.
기존 가이드의 car_search만 읽는다는 설명과 범위가 다릅니다.
개인 PersonalSqlSession은 MAPPER_ROOT를 개인 mappers 폴더로 지정하고 .sql.txt만 등록합니다.
폴더 이동 후 개인 SQL 세 파일은 .sql.txt로 보관하여 공통 로더의 검색에서 제외합니다.
DBeaver에서는 해당 파일의 내용을 SQL 편집기에 가져와 사용합니다.
공통 파일이나 다른 세션의 설정을 바꾸지 않습니다.

Python의 연결 변수는 ZZONG_DB_URL입니다. 팀의 DB_URL로 자동 대체하지 않습니다.
개인 폴더 src/car_search_rag/zzong_santafe_lag/.env에 분리했으며, 같은 이름의 환경변수가 있으면 환경변수가 우선합니다. 기존 루트 .env의 ZZONG_DB_URL도 호환을 위해 읽을 수 있습니다.
비밀번호를 포함한 주소를 채팅·노트북·Git에 기록하지 않습니다.
DBeaver와 같은 Supabase 프로젝트에 연결되었는지 읽기 전용 확인부터 합니다.
세션 생성만으로 연결하지 않고 list_tables 같은 SQL 실행 때 연결합니다.
조회 연습은 PersonalSqlSession(read_only=True)를 사용합니다. Supabase 중계기에서 시작 옵션이 반영되지 않아 연결의 첫 SQL로 SET TRANSACTION READ ONLY를 적용했습니다. 이 읽기 전용 상태는 이번 연결의 트랜잭션에만 적용됩니다. 다른 사람의 연결과 DB 기본 설정은 바꾸지 않습니다.

ManualRepository.insert_row는 테이블 컬럼에 맞춘 한 행을 받습니다.
전체 노트북 딕셔너리는 그대로 SQL에 보내지 않습니다. `full_store_service.py`가 DB 컬럼에 맞춘 행으로 변환합니다. 전체 저장 코드는 준비했고 실제 embed/save 실행은 아직입니다.
여러 테이블을 저장할 때는 session.transaction() 안에서 묶어 성공 시 함께 확정해야 합니다.
DB 행 변환·ID 연결·참조 검증·토큰/벡터 검증·저장 건수 확인 후에만 run을 ready로 바꿉니다.

## 다음 작업

1. 19번 노트북과 `manual.py storage-plan`의 집계로 전체 범위를 살펴봅니다. 개인 DB 읽기 전용 상태 on, 현재 PDF 식별값·모델 버전·표본 원문 일치를 확인했습니다.
2. PDF 74쪽 설명 두 건의 반영 결과를 20번 노트북에서 살펴봅니다. 전체 앞좌석 부모의 검토 상태와 페이지 수준 연결 표시는 그대로입니다.
3. `manual.py full-preview`로 준비한 행을 확인하고 `full-embed`에서 전체 벡터를 메모리에 계산합니다. 실제 DB 저장은 `full-save --confirm-save --manifest-sha256 <검토한 값>`이 필요합니다. 개인 documents와 기존 images 3개를 재사용하고 새 run_id의 자료만 추가하는 코드입니다.
4. 이번 확대의 추가 그림 업로드는 0개로 제안합니다. 설명 없는 주제↔그림 연결 1,147건은 원본 대조 후 설명과 연결 상태를 별도 보완합니다. 자동 초안 507건을 저장하더라도 검토 상태를 그대로 유지합니다.
5. 전체 저장 후 검색 범위를 새 run_id로 지정하고 기존 결합 검색·근거 부족 판정·답변 구성을 차례로 연결합니다. 현재 표본 검색은 표본 ID·건수로 제한돼 있어 자동으로 전체 검색이 되지 않습니다.

고유 그림 864개와 연결 1,157건은 다른 단위입니다. 그림 하나가 여러 주제에 쓰여도 images에는 한 번, record_images에는 주제마다 연결합니다. 전체 벡터의 내용 예상 6,816,040바이트는 DB 전체 용량이나 Storage 크기가 아닙니다.

### 전체 저장 코드의 동작 범위

- 준비한 전체 목록: PDF 1·작업 1·부모 527·청크 2,213·그림 864·연결 1,157. 새 저장 추가 예상: PDF 0·작업 1·부모 527·청크 2,213·그림 861·연결 1,157. 아직 실제로 추가된 행은 없습니다.
- 미리보기 식별값 `893151d66a49fab8f21060ee95e7917054ebb12753dc62eb4ead26cd52798a1b`. 원문·청크·각주·그림 설명·검토 상태·모델을 포함합니다. 새로운 미리보기에서 값이 달라지면 예전 승인값으로 저장하지 않습니다.
- 문서 한 행 잠금으로 중복 실행 순서를 정하고 기존 그림은 읽어 대조합니다. INSERT와 새 작업의 ready 변경을 함께 확정합니다. 같은 완료 작업은 전 필드·벡터를 비교한 뒤 재사용합니다.
- 기존 PDF·그림·표본 원문·벡터를 수정하는 SQL과 Storage 업로드는 없습니다. 전체 글·벡터 저장, 재실행, 실패 복구는 실행 전입니다.
- 확정 후 조회가 실패하면 이미 저장됐을 수 있으므로 상태를 먼저 확인합니다. 서비스는 오류를 자동 삭제·재삽입으로 처리하지 않습니다.

기본 의미 검색 SQL만으로 이전 결합 검색의 결과가 재현된다고 보장하지 않습니다.
새 모델·라이브러리는 이번 단계에서 추가하지 않았습니다.

## 표본 행 변환 결과 — 2026-10-01

| 테이블 | 메모리에 준비한 행 수 | 설명 |
|---|---:|---|
| documents | 1 | 같은 PDF의 파일 정보 |
| processing_runs | 1 | 표본 범위와 예정 모델·청킹 설정 |
| parent_records | 4 | 44쪽 점도 표, 45쪽 차대번호, 43쪽 추천 오일 표와 각주 |
| chunks | 11 | 실제 모델 입력 글, 최대 128토큰. embedding은 아직 None |
| images | 3 | 44쪽 /I1·/I2, 45쪽 /I1. 모두 기존 로컬 파일 경로 있음 |
| record_images | 3 | 부모와 그림 설명의 연결 |

43쪽 표와 각주의 기존 상호 필수 연결을 유지했습니다. 44쪽과 43쪽을 새로운 필수 연결로 임의 지정하지는 않고 표본 범위에 함께 포함했습니다.
원문·검색 글·출처 딕셔너리는 새 행에 복사하며 기존 기록을 직접 바꾸지 않습니다. 그림의 파일명·크기와 현재 PDF 내부 키를 대조했습니다. 그림 파일을 새로 저장하거나 업로드하지 않았습니다.

미리보기는 ready_for_insert=False입니다. 모델 버전은 로컬 캐시의 예정 스냅샷이고 실제 벡터가 확정된 버전은 아직 아닙니다. 이전 전체 임베딩은 메모리에만 있었으므로 새 실행에서 선택한 11개 청크를 다시 임베딩해야 합니다. 0 벡터로 대체하지 않습니다. 변환 결과 JSON 파일은 저장하지 않았습니다.

프로젝트 루트의 터미널에서 사용합니다. 아래 명령은 DB 자료를 저장하지 않습니다.

```powershell
.\.venv\Scripts\python.exe src\car_search_rag\zzong_santafe_lag\db_sample.py connection
.\.venv\Scripts\python.exe src\car_search_rag\zzong_santafe_lag\db_sample.py preview
.\.venv\Scripts\python.exe src\car_search_rag\zzong_santafe_lag\db_sample.py preview --full-text
```

connection은 개인 설정으로 테이블 건수와 읽기 전용 상태를 조회합니다. preview는 전체 PDF에 기존 청킹 규칙을 적용한 뒤 표본의 행만 만들며 로컬 토크나이저는 사용하지만 임베딩 모델은 실행하지 않습니다. --full-text는 변환한 부모의 검색용 글 전체도 표시합니다. 14번 노트북에서는 행을 한 단계씩 살펴볼 수 있습니다.

## 표본 임베딩 결과 — 2026-10-02

`db_sample.py embed`는 위의 23개 행 중 청크 11개를 기존 로컬 모델로 임베딩하며 이 명령은 DB에 쓰지 않습니다. `.py`와 15번 노트북에 한국어 설명을 추가했습니다. 실제 저장은 별도 save --confirm-save 명령입니다.

- 모델: jhgan/ko-sroberta-multitask-mrl, 버전 3ec6ac494ac7ab802fbeed415a99d546c3a0503c. 토크나이저도 같은 버전 사용.
- 벡터: 11 × 768, float32. 숫자 유효성 확인 완료, 정규화 길이 1.0~1.0000001192.
- 모델 준비·계산: 4.076초. PDF 조사·청킹 시간은 제외.
- 부모 4개·청크 11개·이미지 3개·연결 3개. PDF 정보와 처리 설정 각각 1행 포함.
- 원문·출처·필수 연결·그림 참조, 글 식별값·청크 순서·부모 구간·토큰 한도 확인 완료. 그림은 기존 로컬 경로이며 업로드하지 않았습니다.
- 벡터 자체 예상 크기 33,880바이트(약 33.9KB). 글·JSONB·기본 색인 등 전체 표본 DB 용량은 실제 저장 후 측정해야 합니다.
- 개인 DB 읽기 전용 조회 결과는 오늘도 여섯 테이블 0행, 용량 192KiB입니다. DB·Storage에는 새 자료를 저장하지 않았습니다.

embedding_complete=True는 이번 실행에서 계산이 끝났다는 뜻입니다. ready_for_insert=False는 저장 전 검토·승인이 남아 있다는 뜻이고, DB에 ready 처리 작업이 생겼다는 뜻은 아닙니다. 벡터는 파일 저장 없이 메모리에만 있었으므로 실행 종료 후에는 표본만 재계산합니다. 입력 식별값과 모델 버전으로 같은 글과 버전을 쓰는지 대조해야 합니다.

```powershell
.\.venv\Scripts\python.exe src\car_search_rag\zzong_santafe_lag\db_sample.py embed
```

`embed --full-text`는 저장할 부모 글 전체도 보여줍니다. 이번 확인은 저장 형식과 숫자·연결에 대한 것으로 검색 품질·생성 답변 정확도를 확인한 결과가 아닙니다.

## 표본 저장·새 연결 조회 결과 — 2026-10-02

사용자의 저장 승인을 받아 `db_sample.py save --confirm-save`를 실행했습니다. 승인된 모델 스냅샷·입력 식별값·건수로 범위를 제한했고 모든 저장은 한 트랜잭션에 묶었습니다. 저장 도중 같은 연결에서 값·벡터·관계를 읽어 비교한 뒤 processing_runs의 해당 새 작업만 ready로 바꾸고 COMMIT했습니다. 이후 새 읽기 전용 연결에서 다시 대조했습니다.

- 저장 run_id: `dc327282-8cfd-4eb3-a2b0-1433e0b088ce`.
- documents 1, processing_runs 1, parent_records 4, chunks 11, images 3, record_images 3.
- 모델 스냅샷은 앞의 임베딩과 같고 재계산 결과 `(11, 768)` float32가 DB에서 읽은 벡터와 정확히 일치했습니다.
- 원문·검색 글·출처·필수 각주 연결·이미지 설명·로컬 경로를 저장 전후 대조했습니다. 재실행 시 달라질 수 있는 계산 시간 보고서는 별도이며 이를 이유로 기존 자료를 덮어쓰지 않습니다.
- 표본 외 파일·공통 설정·public 테이블은 이번 저장 코드의 변경 대상이 아닙니다. Storage 업로드나 로컬 그림 파일 추가 저장도 하지 않았습니다.
- 실제 크기: chunks 192KiB, documents 48KiB, images 64KiB, parent_records 112KiB, processing_runs 48KiB, record_images 48KiB. 합계 512KiB.
- 같은 PDF·모델·입력의 완료 표본은 조회·대조해서 재사용하도록 작성했습니다. 재실행 시 다른 기존 작업이나 값 불일치는 덮어쓰지 않고 중단합니다. 같은 명령을 다시 실행하는 별도 실험은 하지 않았습니다.

모델 없이 읽기만 하는 명령:

```powershell
.\.venv\Scripts\python.exe src\car_search_rag\zzong_santafe_lag\db_sample.py inspect --run-id dc327282-8cfd-4eb3-a2b0-1433e0b088ce
```

이 조회도 실행하여 원문 4개·필수 각주 연결·그림 경로/설명 3개와 벡터 크기·숫자·정규화를 확인했습니다. 16번 노트북은 같은 자료를 작은 셀로 읽습니다. `db/03_sample_readback.sql.txt`는 DBeaver에서 사용할 SELECT입니다. parent_records 테이블의 Data에서 새로 고침하면 4개 기록을 볼 수 있습니다.

이미지 local_path는 이 PC의 프로젝트 상대 경로입니다. 다른 PC나 배포된 챗봇에서 그림을 표시하려면 파일 배포 또는 Storage 업로드 작업이 따로 필요합니다. ready는 표본 저장 확인 완료이며 전체 PDF 검토·검색 품질·생성 답변 확인 완료를 뜻하지 않습니다.

## 저장량 계산 — 2026-10-01

현재 PDF에서 준비한 527개 부모 기록과 2,213개 청크를 기준으로 계산했습니다. 전체 임베딩을 다시 계산하거나 DB에 자료를 넣지는 않았습니다.

| 대상 | 용량 | 확인 방법 |
|---|---:|---|
| 768차원 벡터 2,213개 | 6,816,040바이트(약 6.8MB) | pgvector의 벡터당 4 × 차원 + 8바이트 공식 |
| 원문·검색 글·출처·그림 참조 정보 | 4,833,611바이트(약 4.8MB) | UTF-8 글과 압축 공백 없는 JSON의 바이트 합계 |
| 전체 자료 1개 처리 버전의 DB 예상 | 약 15~30MB | 행·JSONB·기본 색인·페이지 할당을 고려한 추정. 저장 후 실측 필요 |
| PDF 원본 | 34,541,652바이트(약 34.5MB) | 로컬 파일 크기. Storage에 업로드할 경우 별도 사용 |
| 이미 꺼내둔 그림 3개 | 63,390바이트(약 63.4KB) | 로컬 파일 크기. 전체 864개 그림의 크기로 일반화할 수 없음 |

MB는 1,000,000바이트 기준입니다. DB 실제 크기는 JSONB 저장 방식, 압축과 색인에 따라 계산한 글·JSON 합계와 달라집니다. 생성 직후 빈 테이블 192KiB, 표본 저장 후 512KiB는 테이블·색인·TOAST를 포함한 관계 크기이며 DB 전체 관리 영역은 제외합니다. 표본의 페이지 할당 크기를 전체 청크 수에 단순 곱해서 전체 용량을 예측하지 않습니다.

- 임베딩 모델 파일은 PC에서 사용하고 Supabase에 올리지 않습니다.
- 초기에는 처리 결과 1개 버전만 저장하고, 원문은 부모 기록에 보관하여 청크마다 전체 원문을 반복 저장하지 않습니다. 기존 버전을 자동 삭제하지 않습니다.
- 그림 파일은 DB에 직접 넣지 않고 경로·설명만 기록합니다. 전체 그림을 꺼낼 때 파일 크기 합계를 확인한 뒤 Storage 업로드 범위를 정합니다.
- 벡터 근사 검색 색인은 현재 만들지 않았습니다. 추후 추가하면 용량을 다시 측정합니다.
- Supabase Free 요금제의 DB 500MB와 Storage 1GB는 서로 다른 한도입니다. 현재 팀 프로젝트의 요금제와 남은 공간은 확인하지 않았습니다.

공식 계산 근거: https://github.com/pgvector/pgvector#vector-type
요금제별 공간 한도: https://supabase.com/pricing

## 공식 근거

- 벡터 차원과 거리 계산: https://supabase.com/docs/guides/ai/vector-columns
- 파일과 Storage 메타데이터의 구분: https://supabase.com/docs/guides/storage/schema/design
- 연결 제약 조건: https://www.postgresql.org/docs/current/ddl-constraints.html

## 전체 컬럼 설명

아래는 실제 등록한 한국어 설명입니다. `id`는 연결용 고유 번호, `JSON`은 이름과 값을 묶어 담는 형식, `NULL`은 값이 비어 있다는 뜻입니다.

### documents — 8개 컬럼

PDF 파일 정보: 파일명·전체 쪽수·중복 확인값·보관 경로

| 컬럼 | 설명 |
|---|---|
| id | PDF 파일의 고유 번호; 다른 테이블의 document_id와 연결 |
| file_name | 원본 PDF 파일 이름 |
| file_sha256 | 파일 내용의 SHA-256 식별값; 같은 PDF의 중복 등록 방지 |
| total_pages | PDF 전체 페이지 수 |
| local_path | 현재 PC에서 PDF를 찾는 프로젝트 상대 경로 |
| storage_bucket | PDF를 업로드한 Supabase Storage 저장소 이름; 미업로드 시 비어 있음 |
| storage_path | Storage 저장소 안의 PDF 파일 경로; 미업로드 시 비어 있음 |
| created_at | 이 PDF 정보를 DB에 등록한 시각 |

### processing_runs — 11개 컬럼

처리 작업 정보: 어느 PDF에 어떤 청킹 규칙·모델·버전을 사용했는지 기록

| 컬럼 | 설명 |
|---|---|
| id | 처리 작업의 고유 번호; 부모 기록과 청크의 run_id와 연결 |
| document_id | 이 작업에서 처리한 PDF 번호; documents.id와 연결 |
| pipeline_version | PDF 정리·청킹·저장 처리 방식의 버전 이름 |
| model_name | 임베딩 모델 이름; 질문과 자료는 같은 모델로 숫자 변환해야 함 |
| model_revision | 실제로 사용한 로컬 모델 스냅샷 버전; 같은 이름의 모델 변경을 구분 |
| embedding_dimension | 청크 벡터 하나의 숫자 개수; 현재 구조는 768차원 |
| token_budget | 모델 입력 글의 최대 토큰 수; 글자 수와 다르며 현재 최대 128 |
| normalized | 벡터 길이를 1로 맞췄는지 여부; 현재 true만 저장 |
| settings | 청킹·CPU·배치·입력 식별값 등 작업 설정을 담은 JSON 객체 |
| status | building: 저장 구성 중 / ready: 저장 확인 완료; 전체 PDF 검토·답변 정확도 완료와 다름 |
| created_at | 이 처리 작업을 DB에 등록한 시각 |

### parent_records — 15개 컬럼

주제별 기록(부모): 보존 원문·검색용 글·PDF 출처·검토 상태

| 컬럼 | 설명 |
|---|---|
| id | 주제별 기록의 DB 고유 번호; chunks.parent_id와 record_images.parent_id가 참조 |
| run_id | 이 주제를 만든 처리 작업 번호; processing_runs.id와 연결 |
| document_id | 이 주제가 속한 PDF 번호; documents.id와 연결 |
| record_id | Python에서 붙인 주제 식별자; 같은 run_id 안에서 고유 |
| title | 주제 제목; 예: 차대번호(VIN), 추천 오일 및 용량 |
| raw_text | PDF에서 추출한 원문을 수정하지 않고 보관한 글 |
| content | 청킹의 기준이 되는 검색용 글; 정리한 본문과 적용된 그림 설명 포함 |
| pdf_page_number | 주제가 시작되는 PDF 뷰어 쪽수; 1부터 시작 |
| manual_page_number | 설명서에 인쇄된 시작 쪽수; 확인할 수 없으면 비어 있음 |
| source_pages | 이 주제 원문이 걸쳐 있는 모든 PDF 쪽수 목록 |
| content_type | 내용 종류; 예: instruction_text(지시 글), figure_with_text(그림과 글), table_with_images(표) |
| verification_status | sample_verified: 예제 확인 / visually_reviewed_source: 원본 화면 대조 / auto_draft_needs_review: 자동 초안으로 추가 검토 필요 |
| review_flags | 검토할 문제나 주의할 항목을 담은 JSON 목록; 빈 목록이 전체 검토 완료를 뜻하지는 않음 |
| metadata | 추가 출처 정보 JSON; 표 행·각주·함께 읽을 주제·원문 구간 등 기존 정보를 보존 |
| created_at | 이 주제 기록을 DB에 등록한 시각 |

### chunks — 13개 컬럼

검색용 청크(작은 글 조각): 실제 모델 입력 글과 768차원 벡터; 부모 주제와 연결

| 컬럼 | 설명 |
|---|---|
| id | 청크의 DB 고유 번호 |
| run_id | 이 청크를 만든 처리 작업 번호; 다른 모델·처리 버전과 분리 검색 |
| parent_id | 이 청크의 전체 주제 번호; parent_records.id와 연결 |
| record_id | Python에서 붙인 청크 식별자; 같은 run_id 안에서 고유 |
| chunk_index | 같은 부모 주제 안에서 청크의 순서; 0부터 시작 |
| content | 제목을 포함해 임베딩 모델에 실제 입력한 짧은 글 |
| content_sha256 | 입력 글의 SHA-256 변경 확인값; 글이 바뀌면 벡터도 다시 계산해야 함 |
| token_count | 실제 모델 입력의 토큰 수; 글자 수가 아니며 현재 최대 128 |
| parent_content_start | 부모 content에서 이 조각의 본문이 시작하는 글자 위치; 0부터 시작, raw_text 위치 아님 |
| parent_content_end | 부모 content에서 이 조각 본문의 끝 위치; 끝 글자 제외, raw_text 위치 아님 |
| embedding | content의 의미를 나타내는 768개 숫자; 그림 자체의 벡터가 아니며 다른 모델 벡터와 섞지 않음 |
| metadata | 청크의 출처·처리 정보를 담은 JSON; 검토 상태는 부모 기록 컬럼을 기준으로 조회 |
| created_at | 이 청크를 DB에 등록한 시각 |

### images — 13개 컬럼

그림 정보: PDF 쪽수·내부 그림 키·크기·파일 경로·업로드 상태

| 컬럼 | 설명 |
|---|---|
| id | 그림의 DB 고유 번호; record_images.image_id와 연결 |
| document_id | 그림이 들어 있는 PDF 번호; documents.id와 연결 |
| pdf_page_number | 그림이 위치한 PDF 뷰어 쪽수; 1부터 시작 |
| pdf_image_key | pypdf가 읽은 실제 PDF 내부 그림 키; 중첩 키는 JSON 배열로 보관 |
| image_key_sha256 | 내부 그림 키를 일정한 JSON으로 바꾼 SHA-256 식별값; 그림 파일 내용의 해시와 다름 |
| file_name | 꺼낸 그림의 파일 이름; 다른 PDF 쪽에도 같은 이름이 있을 수 있음 |
| width | 그림 가로 크기(픽셀); 파일을 꺼내지 않았다면 비어 있을 수 있음 |
| height | 그림 세로 크기(픽셀); 파일을 꺼내지 않았다면 비어 있을 수 있음 |
| local_path | 현재 PC에서 그림을 찾는 프로젝트 상대 경로; 다른 PC에서 바로 접근되는 주소는 아님 |
| storage_bucket | 그림을 업로드한 Supabase Storage 저장소 이름; 미업로드 시 비어 있음 |
| storage_path | Storage 저장소 안의 그림 파일 경로; 미업로드 시 비어 있음 |
| upload_status | reference_only: 참조만 / local_available: PC 파일 있음 / uploaded: Storage 업로드 완료 |
| created_at | 이 그림 정보를 DB에 등록한 시각 |

### record_images — 6개 컬럼

주제와 그림의 연결: 어떤 글에 어떤 그림을 보여 줄지와 그림 설명·연결 검토 상태

| 컬럼 | 설명 |
|---|---|
| document_id | 주제와 그림이 함께 속한 PDF 번호; 다른 PDF의 그림이 섞이지 않게 연결 |
| parent_id | 그림을 연결할 주제 번호; parent_records.id와 연결 |
| image_id | 주제에 연결한 그림 번호; images.id와 연결 |
| description | 이 주제에서 사용하는 그림 설명; 파일 이름만으로 알 수 없는 의미를 기록 |
| linkage_status | unreviewed_page_reference: 페이지 수준 초안 / sample_linked: 예제 연결 확인 / visually_verified: 화면 대조로 연결 확인; 업로드 상태와 별개 |
| metadata | 그림과 주제를 연결한 근거·추가 정보를 담은 JSON 객체 |
