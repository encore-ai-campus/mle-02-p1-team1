# CASPER 앱 산출물 페이지 추가

## 반영할 파일

- src/chatbot_project/app2.py: 공통 메뉴·디자인과 챗봇 화면
- src/chatbot_project/rag.py: Secrets/환경변수를 같은 설정으로 검사·연결
- src/chatbot_project/project_portal.py: 개요와 1~4단계 페이지
- src/chatbot_project/portal_theme.py: 모든 화면의 공통 디자인
- src/chatbot_project/portal_charts.py: 실제 평가 결과로 차트 계산
- src/chatbot_project/project_assets/: 핵심 자료와 다운로드 ZIP
- .streamlit/config.toml: 밝은 배경·녹색 강조색

ZIP 안의 폴더 구조를 유지해 저장소에 합칩니다. Streamlit 실행 파일은 기존 src/chatbot_project/app2.py입니다. 새 차트 라이브러리 설치는 필요하지 않습니다.

## 화면 구성

질문하기 / 프로젝트 한눈에 / 데이터·전처리 / 데이터 분석 / 검색·답변 구조 / 검색 품질 평가.
자료 화면은 모델·DB·API 없이 열립니다. 질문 화면에서는 기존처럼 질문 전에 모델을 준비합니다.
기본 검색 방식은 그대로입니다. 질문 분해나 ReAct를 추가한 버전이 아닙니다.

## 자료 기준

평가는 2026-10-02에 수집한 30개 고정 기록입니다. 팀 DB·답변 모델 사용은 사용자 확인 정보입니다. 라이브 서버를 조회하는 대시보드는 아닙니다.
HTML 차트와 SVG는 project_assets/charts에 있습니다. 다운로드 자료의 설명은 기존 제출용 자료이며, 앱의 요약과 구분됩니다.
API 키와 DB 덤프는 이 패키지에 포함하지 않습니다.

## 배포

새 파이썬 파일과 project_assets 폴더, .streamlit/config.toml도 함께 GitHub에 올려야 합니다. app2.py만 올리면 페이지 자료를 찾을 수 없습니다.
로컬 수정과 GitHub push, Streamlit 배포는 각각 별도입니다. 이번 작업은 교체 파일 제작입니다. 프로젝트 폴더 쓰기 권한이 승인되지 않아 원본 앱에 반영하지 못했습니다. ZIP을 덮어쓴 뒤 GitHub에 올려야 배포 앱에 적용됩니다.
앱 실행·실제 검색 재시험은 이 변경 작업에서 수행하지 않았습니다.

