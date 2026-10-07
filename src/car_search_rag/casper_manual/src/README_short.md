# CASPER 매뉴얼 RAG · 짧은 안내

캐스퍼 일렉트릭 매뉴얼에서 필요한 글을 찾아, 본문과 연결 그림을 근거로 답하는 프로젝트입니다.

## 핵심

**질문 → 벡터·키워드 검색 → 순위 결합 → 본문·그림 전달 → LLM 답변**

DB 함수 `match_manual_chunks_hybrid`가 근거를 선택하고 `rag.py`가 답변 입력을 준비합니다. 이미지는 별도 벡터 검색이 아니라 검색한 청크와 연결된 그림을 가져옵니다.

## 산출물 페이지

01 데이터·전처리 / 02 데이터 분석 / 03 검색·답변 구조 / 04 검색 품질 평가 / 05 최종 결과 요약 / 06 DB 검색 함수 이해하기

06 페이지에는 단계별 탐색과 가중치 체험이 있습니다. 가상 예시이며 실제 DB 설정을 바꾸지 않습니다. 질문 화면은 `app2.py`의 메뉴 설정에 따라 표시됩니다.

## 실행

팀 저장소의 `src/car_search_rag/casper_manual/`에서:

```powershell
uv sync
uv run streamlit run src/chatbot_project/app2.py
```

Python 3.12 이상이 필요합니다. Secrets 또는 환경변수에 `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `OPENAI_API_KEY`를 설정합니다. `OPENAI_MODEL`은 선택 항목입니다. 실제 키는 GitHub에 올리지 않습니다.

## 주요 파일

- `app2.py`: 앱 실행·메뉴
- `rag.py`: 검색·이미지 조회·답변 생성
- `project_portal.py`: 산출물·체험 페이지
- `portal_charts.py`, `portal_theme.py`: 그래프·공통 디자인
- `project_assets/`: 분석·평가·다운로드 자료. ZIP은 압축된 상태로 유지합니다.

시각화는 Streamlit + Vega-Lite를 사용합니다. Plotly는 사용하지 않습니다.

상세 설정·DB 구조·배포 경로·평가 해석은 [README.md](README.md)를 참고하세요.
