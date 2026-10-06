@echo off
chcp 65001 >nul
setlocal
rem 개인 통합 화면은 대시보드와 작업 Document 메뉴가 있는 integrated_app.py로 실행합니다.
set "SANTAFE_PROJECT=%~dp0..\..\.."
set "SANTAFE_PYTHON=%SANTAFE_PROJECT%\.venv\Scripts\python.exe"
if not exist "%SANTAFE_PYTHON%" (
    echo 프로젝트의 .venv Python을 찾지 못했습니다. deployment_guide.md의 설치 안내를 확인하세요.
    pause
    exit /b 1
)
echo 싼타페 개인 통합 화면: http://localhost:8504
echo 종료하려면 Ctrl+C를 누르세요.
rem 저장된 자료 화면은 API를 호출하지 않습니다. 실제 질문은 기존 환경 설정이 필요합니다.
"%SANTAFE_PYTHON%" -m streamlit run "%~dp0integrated_app.py" --server.address=127.0.0.1 --server.port=8504 --server.headless=true --browser.gatherUsageStats=false --server.fileWatcherType=none
endlocal
