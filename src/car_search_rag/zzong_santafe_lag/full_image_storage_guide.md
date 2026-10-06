# 전체 그림 업로드와 용량 확인

## 완료 결과 — 2026-10-03

- 기존 3개 + 이번에 추가한 861개 = **864개**. 모든 공개 파일을 PDF 추출 바이트와 대조했으며 최종 실패는 0개입니다.
- 그림 파일 **32.41MB**, 개인 DB **16.50MB**, 측정 합계 **48.91MB**입니다. 각각 32,406,621 / 16,498,688 / 48,905,309바이트입니다.
- DB의 그림 경로·업로드 상태만 861행 연결했습니다. 기존 원문·벡터·설명·검토 상태·그림 연결은 보존했습니다. 팀원 파일과 다른 스키마는 수정하지 않았습니다.
- 첫 실행의 진행 기록 파일 접근 오류 후 재개했습니다. 파일 업로드는 이미 완료되어 재개 실행에서는 864개를 재사용했고, 개인 DB 연결을 완료했습니다. 첫 실행의 마지막 기록 155개는 전체 업로드 완료 건수가 아닙니다.
- 최종 요약은 `data/zzong_santafe_lag/reports/full_images_upload_summary_20261003.json`입니다. 실행별 추가 파일 수와 이번 요청 전체의 추가 파일 수를 구분합니다.

## 어떤 자료를 어디에 보관하나요?

| 자료 | 보관 위치 | 역할 |
|---|---|---|
| 원본 PDF | PC의 `data/santafe_hev_manual.pdf` | 원본 대조·그림 추출 |
| 부모 글·검색 청크·벡터·그림 연결 | Supabase의 `zzong_santafe_lag` 스키마 | 검색과 출처·주제 연결 |
| 그림 파일 | `images` 버킷의 `cars/hyundai/santafe_hev/zzong_santafe_lag/<PDF 식별값>/` | 실제 그림 표시 |
| 실행·용량 보고서 | PC의 `data/zzong_santafe_lag/reports/` | 건수·파일 크기·원본 식별값·오류 확인 |

**그림 파일과 임베딩 벡터는 다른 자료입니다.** 이번 작업은 PDF 내부 그림 바이트를 보관하고 DB 경로를 연결하는 작업입니다. 이미지 픽셀 임베딩이나 모델 실행을 추가하지 않습니다.

파일 이름은 `page_0033_image_01.jpg`처럼 **PDF 쪽수와 해당 페이지의 그림 순번**입니다. 원본 그림 이름 `I1.jpg`는 여러 페이지에서 반복되므로 저장 경로에 쪽수를 넣어 구분합니다. PNG는 `.png`로 보관하며 재압축하지 않습니다. 이미 올린 예제 3개의 이름과 내용은 유지합니다.

## 실행 순서

1. 현재 PDF SHA-256, 전체 처리 버전, 864개 그림의 내부 키를 DB와 비교합니다.
2. PDF에서 실제 파일 바이트를 꺼내 추가할 크기를 계산합니다.
3. 같은 개인 경로의 파일이 있으면 내용을 확인해 재사용합니다. 다른 내용이면 중단합니다.
4. 새 파일만 최대 4개씩 추가합니다. 업로드 옵션은 덮어쓰기 금지입니다.
5. 공개 주소로 실제 파일을 읽어 바이트 수와 SHA-256을 원본과 비교합니다.
6. 확인된 파일만 개인 `images` 테이블의 `storage_bucket`, `storage_path`, `upload_status` 세 컬럼에 연결합니다.
7. 새 읽기 전용 DB 연결에서 전체 건수·경로·용량·보존 대상 식별값을 확인합니다.

**원문·벡터·설명·그림의 주제 연결·검토 상태는 변경하지 않습니다.** 팀원 파일·공통 설정·다른 스키마에 쓰는 명령도 없습니다. 자동 참조의 기존 `file_name`, `width`, `height`가 NULL이면 그대로 보존합니다. 실제 추출 이름과 픽셀 크기는 결과 보고서에서 확인할 수 있습니다.

Storage와 DB는 하나의 트랜잭션이 아닙니다. 중단되면 이미 올라간 파일을 삭제하지 않고, 다음 실행에서 원본과 비교해 재사용합니다. 그림 확인에 실패하면 DB 연결을 확정하지 않습니다. Windows 보고서 파일의 일시적 접근 오류는 짧게 재시도하고 진행 알림 오류와 원격 파일 오류를 구분합니다.

## DBeaver에서 확인하기

1. 현재 연결에서 `Schemas → zzong_santafe_lag → Tables`를 새로고침합니다.
2. `images`를 열고 `Data`에서 `upload_status`와 `storage_path`를 봅니다.
3. [조회 SQL](./db/05_inspect_image_storage.sql.txt)을 SQL 편집기에 붙이고 문장 하나씩 선택해 실행합니다. 상태별 그림 수, 내 파일 용량, 개인 DB 용량, 설명 검토 상태를 보여줍니다. 조회만 실행합니다.

Supabase 화면에서는 `Storage → images → cars → hyundai → santafe_hev → zzong_santafe_lag → PDF 식별값 폴더`를 엽니다. DBeaver의 개인 스키마는 DB 자료, 이 Storage 폴더는 실제 그림 파일입니다.

## 노트북으로 결과 확인하기

[개인 확인 노트북](./full_image_storage_result.ipynb)의 첫 셀은 저장된 JSON에서 건수와 용량을 읽습니다. 다음 셀의 PDF 쪽수를 바꾸면 해당 그림의 파일 이름·크기·주소를 봅니다. 마지막 셀은 공개 파일을 표시합니다. 업로드·DB 쓰기·유료 모델 호출은 실행하지 않습니다.

현재 챗봇은 **파일 주소와 검토된 설명 연결이 함께 있는 그림**만 표시합니다. 864개를 보관해도 미검토 그림까지 답변 근거로 자동 승격하지 않습니다. 전체 그림 설명과 정확한 소제목 연결 검토는 다음 작업입니다.

## 다시 사용할 때

프로젝트 루트에서 아래 명령을 실행합니다. 보고서는 기존 파일을 덮어쓰지 않으므로 새 이름을 지정합니다.

```powershell
# 준비 확인: 개인 DB·Storage 조회와 PDF 대조만 실행합니다.
.\.venv\Scripts\python.exe src\car_search_rag\zzong_santafe_lag\full_image_storage.py check --report data\zzong_santafe_lag\reports\full_images_check_NEW.json

# 실제 추가: 같은 파일은 원본 확인 후 재사용합니다. 변경 요청·승인 뒤 사용합니다.
.\.venv\Scripts\python.exe src\car_search_rag\zzong_santafe_lag\full_image_storage.py upload --confirm-upload --report data\zzong_santafe_lag\reports\full_images_upload_NEW.json
```

코드 흐름은 `full_image_storage.py`(실행·보고서) → `full_image_storage_service.py`(파일 확인·추가·결과) → `mappers/full_image_storage.sql.txt`(개인 조회·경로 UPDATE)입니다. 기존 표본 3개 도구는 당시 범위를 유지합니다.

## 용량 수치를 읽는 방법

- Storage 용량: 내 경로의 실제 파일 바이트 합계입니다. 전체 버킷·다른 팀원 파일 용량은 포함하지 않습니다.
- DB 용량: 개인 여섯 테이블의 테이블·색인·TOAST 할당 합계입니다. 경로 UPDATE로 빈 공간·이전 행 버전이 남을 수 있습니다.
- 두 수치의 합은 이번에 측정한 개인 자료 합계입니다. Supabase 요금 청구량이나 공유 프로젝트 전체 사용량은 아닙니다. WAL·공통 관리 영역·네트워크 전송량은 제외합니다.
- `MB`는 1,000,000바이트, `MiB`는 1,048,576바이트 단위입니다.
