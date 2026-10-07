# 싼타페 개인 화면 실행과 배포

대시보드와 작업 Document는 싼타페 개인 `integrated_app.py`와 팀 공통 진입 파일 `src/car_search_rag/anna_rag/chatbot/app.py`의 싼타페 메뉴에 연결합니다. 공통 앱에서 싼타페를 선택한 뒤 메뉴를 열면 개인 폴더의 저장 자료 화면을 표시합니다. 다른 차종 메뉴와 검색·답변 구현은 유지합니다. GitHub 변경이 배포 서비스에 반영되어야 원격 화면도 갱신됩니다.

## 공통 메뉴 연결 확인 — 2026-10-07

- `test_shared_material_views.py`의 3개 테스트 통과: 저장 대시보드·작업 문서 표시, 챗봇 복귀와 대화 보존, 자료 조회 시 백엔드 생성 없음, 다른 3개 차종 메뉴 분리.
- 기존 팀 테스트 32개 중 26개 통과, 6개 오류. 싼타페 4개는 가짜 서비스의 URL 설정 형식, 소나타 2개는 가짜 응답의 `verified_images` 누락 문제입니다. 해당 팀원 구현과 기존 테스트 파일은 수정하지 않았습니다. 전체 테스트 통과로 표시하지 않습니다.
- 화면 테스트는 실제 저장 자료와 가짜 백엔드를 사용합니다. 실제 DB·생성 API 응답 및 모든 팀원 기능을 보장하는 검증은 아닙니다.

## 다른 데스크톱에서 이어서 작업

기존 저장소와 Python 3.12 환경이 있는 PC는 먼저 작업 내용을 확인하고 main의 최신 변경을 받습니다. 로컬 수정이 있으면 보관한 뒤 갱신합니다.

```powershell
git status --short
git pull --ff-only origin main
uv sync
uv pip install --python .venv/Scripts/python.exe -r src/car_search_rag/zzong_santafe_lag/requirements.txt
```

처음 받는 PC는 저장소를 clone한 뒤 같은 설치 명령을 실행합니다. 설치·동기화는 네트워크와 시간이 필요할 수 있습니다. `.env`와 `.venv`는 Git으로 전달하지 않습니다.

실행 파일 `src/car_search_rag/zzong_santafe_lag/run_integrated_app.bat`를 열거나 저장소 루트에서 다음 명령을 실행합니다.

```powershell
.venv/Scripts/python.exe -m streamlit run src/car_search_rag/zzong_santafe_lag/integrated_app.py --server.port=8504 --server.address=127.0.0.1 --server.fileWatcherType=none --browser.gatherUsageStats=false
```

`http://localhost:8504`에서 싼타페를 선택하고 메뉴의 데이터 대시보드·작업 Document를 엽니다. 이 자료 화면은 저장 파일을 읽으며 실제 검색과 생성은 별도 설정을 사용합니다. 기존 `run_app.bat`는 `app.py`를 실행하므로 발표 메뉴를 확인할 때는 새 실행 파일을 사용합니다.

## Streamlit Community Cloud 설정

별도 개인 앱을 기존 저장소에서 배포할 때의 진입 설정입니다. 공통 앱의 진입점을 개인 파일로 바꾸지 말고, 개인 배포를 별도로 구분합니다.

|항목|설정|
|---|---|
|Repository|encore-ai-campus/mle-02-p1-team1|
|Branch|main|
|Main file path|src/car_search_rag/zzong_santafe_lag/integrated_app.py|
|Python|3.12|
|Dependencies|진입 파일과 같은 폴더의 requirements.txt|

공식 안내는 저장소·브랜치·진입 파일과 Secrets를 지정하도록 설명합니다. 배포된 앱이 해당 브랜치와 파일을 실행하고 있으면 코드 변경을 반영합니다. Git push 자체가 새 개인 배포를 생성하지는 않습니다. [Streamlit 배포 안내](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy), [Secrets 설정](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management).

실제 질문·그림 확인에는 팀 DB·Storage·API의 기존 권한과 설정이 필요합니다. 루트 Secrets 또는 환경변수에 `DB_URL`, `OPENAI_API_KEY`, `SUPABASE_URL`을 준비하고, 기존 서비스에서 사용하는 `SUPABASE_SECRET_KEY`도 필요한 경우 설정합니다. 명시적인 `ZZONG_EMBEDDING_RUN_ID`·`ZZONG_SUPABASE_URL`이 있으면 기존 코드의 우선순위를 따릅니다. 인증 값은 GitHub에 넣지 않습니다.

원본 `data/santafe_hev_manual.pdf`는 Git에서 제외합니다. 다른 PC나 서버에 원본이 없으면 해당 PDF 다운로드는 제공하지 못합니다. 저장된 발표 PPT·대본·데이터 분석·평가 화면은 GitHub에 포함한 파일로 표시합니다. 실제 질문의 DB·API 접근과 원본 PDF 배치는 따로 확인해야 합니다.

## 확인 범위

- 개인 화면 변경 파일과 발표자료만 커밋합니다. 공통 앱·팀원 코드·공통 의존성은 이번 변경에서 수정하지 않습니다.
- 자료 화면 전환, 대화 보존, PPT·대본 다운로드와 저장된 비교 결과 표시는 AppTest로 확인합니다.
- 현재 로컬 환경에서 실행을 검증하더라도 Linux 배포 서버의 새 패키지 설치·메모리·DB 연결까지 보장하는 결과는 아닙니다.
- 실제 개인 앱의 배포 URL과 관리 화면의 진입 설정·실행 로그가 확인돼야 원격 배포 완료로 표시할 수 있습니다.
