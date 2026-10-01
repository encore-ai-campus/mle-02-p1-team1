# 개인 Supabase 테이블 준비와 DBeaver 사용

## 현재 상태 — 2026-10-01

- 개인 브랜치: zzong/santafe-lag.
- DBeaver의 zzong 연결에서 postgres DB와 기존 public 테이블을 확인했습니다.
- 읽기 전용 SQL이 1행을 반환했습니다. DB 사용자 postgres, vector 0.8.0, 확장 위치 public.
- 사용자 승인 후 개인 스키마 zzong_santafe_lag와 빈 테이블 6개를 DBeaver에서 생성했습니다. 생성 SQL은 개인 스키마에만 적용했습니다.
- 테이블·기본 색인의 실제 할당 용량 합계는 196,608바이트(192KiB, 약 0.2MB)입니다. DBeaver의 테이블 목록과 용량 조회 결과를 확인했습니다.
- DB 자료 삽입과 Storage 업로드는 하지 않았습니다.
- Python의 개인 SQL Mapper로 읽기 전용 연결과 여섯 테이블 조회를 실행했습니다. read_only=on, 여섯 테이블 모두 0행입니다. INSERT·벡터 DB 저장·DB 검색은 아직 실행하지 않았습니다.
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

1. 준비한 표본 청크 11개의 글·출처·각주·그림 연결을 검토하고 같은 로컬 모델 버전으로 임베딩합니다.
2. 글 식별값·벡터 차원·정규화·참조 연결을 확인한 뒤, 실제 저장할 내용과 건수를 사용자에게 보여드립니다.
3. 승인 후 표본을 한 트랜잭션에 저장하고 원문·각주·그림 조회 및 실제 용량을 확인합니다.
4. 전체 527개 부모·2,213개 청크의 행 변환·저장 단계로 확대.
5. 기존 TF-IDF·질문 목적 검색을 DB 자료에서 재구성하고 같은 질문으로 비교.

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

## 저장량 계산 — 2026-10-01

현재 PDF에서 준비한 527개 부모 기록과 2,213개 청크를 기준으로 계산했습니다. 전체 임베딩을 다시 계산하거나 DB에 자료를 넣지는 않았습니다.

| 대상 | 용량 | 확인 방법 |
|---|---:|---|
| 768차원 벡터 2,213개 | 6,816,040바이트(약 6.8MB) | pgvector의 벡터당 4 × 차원 + 8바이트 공식 |
| 원문·검색 글·출처·그림 참조 정보 | 4,833,611바이트(약 4.8MB) | UTF-8 글과 압축 공백 없는 JSON의 바이트 합계 |
| 전체 자료 1개 처리 버전의 DB 예상 | 약 15~30MB | 행·JSONB·기본 색인·페이지 할당을 고려한 추정. 저장 후 실측 필요 |
| PDF 원본 | 34,541,652바이트(약 34.5MB) | 로컬 파일 크기. Storage에 업로드할 경우 별도 사용 |
| 이미 꺼내둔 그림 3개 | 63,390바이트(약 63.4KB) | 로컬 파일 크기. 전체 864개 그림의 크기로 일반화할 수 없음 |

MB는 1,000,000바이트 기준입니다. DB 실제 크기는 JSONB 저장 방식, 압축과 색인에 따라 계산한 글·JSON 합계와 달라집니다. 현재 빈 테이블 192KiB는 테이블·색인·TOAST를 포함한 관계 크기이며 DB 전체 관리 영역은 제외합니다.

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
