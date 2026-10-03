@echo off
chcp 65001 >nul
setlocal
rem [프로젝트 추가] 개인 실행 파일 위치에서 프로젝트의 가상환경을 찾습니다.
set "SANTAFE_PROJECT=%~dp0..\..\.."
set "SANTAFE_PYTHON=%SANTAFE_PROJECT%\.venv\Scripts\python.exe"
if not exist "%SANTAFE_PYTHON%" (
    echo 프로젝트의 .venv Python을 찾지 못했습니다. README의 설치 안내를 확인하세요.
    pause
    exit /b 1
)
rem [프로젝트 추가] localhost에만 열고 사용 통계 수집을 끕니다. 실행 자체는 API를 호출하지 않습니다.
rem [프로젝트 추가] 파일 감시가 Transformers의 불필요한 모듈을 불러오지 않게 끕니다.
rem 코드를 수정한 뒤에는 이 실행 창을 종료하고 다시 실행해야 새 코드가 반영됩니다.
echo 싼타페 설명서 화면 주소: http://localhost:8502
echo 종료하려면 이 창에서 Ctrl+C를 누르세요.
"%SANTAFE_PYTHON%" -m streamlit run "%~dp0app.py" --server.address=localhost --server.port=8502 --server.headless=true --browser.gatherUsageStats=false --server.fileWatcherType=none
endlocal
