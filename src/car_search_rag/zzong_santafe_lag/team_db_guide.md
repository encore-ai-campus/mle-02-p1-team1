# 팀 DB 형식으로 싼타페 자료 추가하기

## 실제 저장 결과 — 2026-10-06

- 싼타페 전용 `car_id`: **`20261006_000018`**.
- 검토 완료 주제 25개 → 차량 1개, 장 4개(1·2·5·6장), 청크 72개, 그림 주소 18개.
- 최초 저장 후 자식 청크 10번이 2번 앞에 놓이는 문자열 정렬을 발견해, 이 차량의 청크 순번 11개만 숫자 순서로 보정했습니다. 본문·벡터·그림 주소는 변경하지 않았습니다.
- 별도 연결에서 본문·벡터·주소·순서·장 연결을 다시 대조했습니다. 다른 작성자의 차량 1개, 장 10개, 청크 947개, 그림 행 955개의 저장 전후 내용 식별값과 건수는 같았습니다.
- 추가 칼럼 데이터 크기 합계: **490,607바이트(약 0.49MB)**. 인덱스·행 헤더·WAL 등은 제외합니다. 그림 파일 재업로드 0개.
- 최종 대응표: `data/zzong_santafe_lag/team_exports/santafe_hev_2024_8f5952174245.plan.json` 및 같은 이름의 `.result.json`. 최초 순번을 담은 `2dc9958c408e` 결과는 작업 이력입니다.

## 연결 및 범위

- `team_export.py`는 **프로젝트 루트 `.env`의 `DB_URL`**을 직접 사용합니다. 비밀번호는 출력하지 않습니다.
- 현재 개인 원문 저장 DB와 팀 `DB_URL`이 같은지 확인한 뒤 공통 저장본을 추가합니다. 서로 다른 DB로 바뀌면 자동 이관하지 않고 중단합니다.
- 작성자: `zzong_santafe_lag`. 차량 조건: `hyundai / santafe_hev / 2024`.
- 2024는 사용자가 알려준 **2024년 이후 생산형의 기준 연도**입니다. PDF의 정확한 모델 연식이 확인됐다는 뜻은 아닙니다. 다른 연식까지 포함하는 범위 조회는 구현하지 않았습니다.
- 공통 테이블에 검토 상태 칼럼이 없어 **검토 완료 주제만** 추가합니다. 미검토 자료는 개인 테이블에 남깁니다.

## 저장 구조

| 기존 개인 자료 | 팀 공통 저장본 |
|---|---|
| 싼타페 HEV PDF | `public.car`의 싼타페 전용 차량 ID |
| PDF 장 번호 | `public.car_manual_chapter`의 장 번호·제목 |
| 검토 완료 부모의 자식 청크 | `public.car_manual_chunk`의 본문·순서·대표 PDF 쪽수 |
| OpenAI 임베딩 | `text-embedding-3-small`의 기존 1536차원 벡터 복사 |
| 검토·업로드 완료 그림 | `public.car_manual_image`의 설명·공개 주소·PDF 쪽수 |

새 임베딩 API 호출과 그림 파일 재업로드는 하지 않습니다. 같은 장의 같은 그림은 한 번 등록합니다. ID는 팀의 `public.fn_get_biz_id`로 발급하므로 공통 ID 시퀀스가 정상적으로 증가합니다.

## 기존 챗봇과의 관계

기존 챗봇은 `zzong_santafe_lag` 스키마에서 부모 전체 설명, 각주·주의사항, 검토 상태를 읽습니다. 공통 테이블에는 그 연결 정보와 전체 출처 페이지 목록을 담는 칼럼이 없습니다.

이번 작업은 **팀 구조로 검색 자료를 추가 저장**하는 작업입니다. 기존 챗봇의 DB 조회 코드를 공통 테이블로 바꾸지는 않습니다. 팀 통합 챗봇에서 같은 원문·필수 각주 연결을 사용하려면 개인 원문과 대응표를 함께 조회하는 처리가 필요합니다. 같은 장·페이지에 있다는 이유만으로 그림과 청크가 정확히 대응한다고 판단하지 않습니다.

원본 청크 ID → 공통 청크 ID, 부모 주제, 전체 PDF 페이지, 필수 각주 연결은 `data/zzong_santafe_lag/team_exports/`의 계획·결과 JSON에 기록합니다. 검토 버전이나 본문이 바뀌면 공통 저장본의 갱신 방식을 먼저 검토해야 합니다.

## 실행

프로젝트 루트에서 실행합니다. `plan`은 읽기와 개인 대응표 저장만 수행합니다.

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.venv\Scripts\python.exe -m car_search_rag.zzong_santafe_lag.team_export plan --year 2024
.\.venv\Scripts\python.exe -m car_search_rag.zzong_santafe_lag.team_export save --year 2024
```

`save`는 새 차량에 INSERT만 실행하고, COMMIT 후 새 연결에서 글·벡터·그림 주소를 대조합니다. 같은 차량이 이미 있으면 작성자와 전체 내용을 대조해 재사용합니다. 내용이 다르거나 다른 작성자의 차량이면 중단하며, 기존 행을 자동 수정·삭제하지 않습니다. 위 최초 순번 보정은 자기 차량만 대상으로 별도 수행한 작업입니다.

다른 작성자의 공통 행은 저장 전후 건수와 내용 식별값을 비교합니다. 팀원의 동시 수정이 감지돼도 이번 거래를 취소합니다. 팀원 폴더, 공통 테이블 정의, 인덱스, 권한은 변경하지 않습니다.

## DBeaver에서 확인

### 원본 PDF 보관 (2026-10-06 추가)

원본 PDF 779쪽, 34,541,652바이트를 `images` 버킷의 싼타페 개인 경로에 별도로 업로드했습니다. 공통 청크 내보내기 때 그림 재업로드 없이 저장한 작업과는 별도입니다. 실제 원격 파일의 크기·SHA-256과 DB 경로를 확인했습니다.

`zzong_santafe_lag.documents`에는 원본 파일 자체 대신 `storage_bucket`과 `storage_path`가 기록됩니다. 이 두 값으로 Storage 파일을 찾습니다. 공통 `public.car`에는 PDF 경로 칼럼이 없어 구조를 변경하지 않았습니다. 결과는 `data/zzong_santafe_lag/reports/original_pdf_storage_result.json`에 있습니다.

```sql
SELECT file_name, total_pages, storage_bucket, storage_path
FROM zzong_santafe_lag.documents
WHERE file_name = 'santafe_hev_manual.pdf';
```

현재 공통 화면의 사이드바 PDF 다운로드는 계속 로컬 파일을 읽습니다. 이번 보관 작업은 화면 코드를 변경하지 않았습니다.

팀 연결 → `Schemas` → `public` → `Tables`에서 네 테이블을 확인합니다.

```sql
SELECT car_id, car_nm, car_eng_nm, car_model_yr, create_user_id
FROM public.car
WHERE create_user_id = 'zzong_santafe_lag'
  AND car_eng_nm = 'santafe_hev';
```

나온 `car_id`로 `car_manual_chapter`, `car_manual_chunk`, `car_manual_image`를 필터링합니다. `db/10_inspect_team_export.sql.txt`에서 연결 건수도 확인할 수 있습니다.

결과 JSON의 `logical_total_bytes`는 자기 칼럼 값의 저장 크기 합계입니다. 행 헤더·인덱스·페이지 여유·WAL을 제외하므로 Supabase 전체 사용량과 같지 않습니다. 그림은 기존 주소를 재사용하여 이번 내보내기의 Storage 추가 용량은 0바이트입니다.
