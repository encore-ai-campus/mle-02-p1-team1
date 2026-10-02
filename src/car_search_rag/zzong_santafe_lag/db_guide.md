# 개인 Supabase 테이블 준비와 DBeaver 사용

## 현재 상태 — 2026-10-02

- 개인 브랜치: zzong/santafe-lag.
- DBeaver의 zzong 연결에서 postgres DB와 기존 public 테이블을 확인했습니다.
- 읽기 전용 SQL이 1행을 반환했습니다. DB 사용자 postgres, vector 0.8.0, 확장 위치 public.
- 사용자 승인 후 개인 스키마 zzong_santafe_lag와 빈 테이블 6개를 DBeaver에서 생성했습니다. 생성 SQL은 개인 스키마에만 적용했습니다.
- 승인한 표본 23개 행을 개인 SQL Mapper로 저장했습니다. PDF·처리 설정 각각 1개, 원문 4개, 청크 11개, 이미지·연결 각각 3개입니다. 처리 상태 ready.
- 저장 확정 후 새 읽기 전용 연결에서 원문·출처·각주·이미지 경로와 벡터를 대조했습니다. 저장 전후 벡터 값은 float32 기준으로 정확히 일치합니다.
- 테이블·기본 색인의 실제 할당 용량은 524,288바이트(512KiB, 약 0.5MB)입니다. 빈 구조의 192KiB에서 320KiB 증가했습니다. DB 전체 관리 영역·WAL·Storage는 제외한 값입니다.
- Storage 업로드·전체 PDF 기록 저장·DB 검색 재구성은 아직 하지 않았습니다.
- 개인 연결 변수는 src/car_search_rag/zzong_santafe_lag/.env의 ZZONG_DB_URL에 분리했습니다. 기존 연결 설정을 읽기 전용으로 대조한 뒤 복사했으며 팀 .env는 수정하지 않았습니다. 개인 .env의 Git 제외도 확인했습니다.
- DBeaver에 연결해도 Python 연결 설정이 자동으로 생기는 것은 아닙니다.

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
현재 노트북 딕셔너리를 그대로 전달하는 전체 저장 기능은 아직 없습니다.
여러 테이블을 저장할 때는 session.transaction() 안에서 묶어 성공 시 함께 확정해야 합니다.
DB 행 변환·ID 연결·참조 검증·토큰/벡터 검증·저장 건수 확인 후에만 run을 ready로 바꿉니다.

## 다음 작업

1. 표본 저장·조회는 완료했습니다. 16번 노트북과 DBeaver에서 저장된 내용을 살펴봅니다.
2. 저장한 표본으로 질문 벡터와 DB 의미 검색을 연결합니다. 기존 결합 검색과 결과 차이를 확인하는 단계는 별도입니다.
3. 전체 527개 부모·2,213개 청크로 확대할 때는 같은 PDF 재사용·이미지 참조·처리 버전 및 저장 범위를 먼저 정리합니다. 현재 저장 서비스는 표본 23개 행 전용입니다.

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
