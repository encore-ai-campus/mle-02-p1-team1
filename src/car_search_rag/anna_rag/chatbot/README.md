# 자동차 설명서 챗봇 배포

Streamlit UI에서 IONIQ 5와 SONATA 2026 설명서를 선택해 대화할 수 있습니다. SANTA FE와 CASPER는 연결하지 않았습니다. 관리자 모드는 비활성화되어 있습니다.

## SONATA 연결

`sonata_backend.py`는 팀원의 `car_search/chat_runtime.py`를 호출합니다. 개인 실행 화면 `app_kbj.py`도 같은 runtime을 호출합니다. runtime은 `CarManual` Agent와 검색·대화 다운로드 도구를 사용합니다. Agent의 최종 답변을 표시하며 검색 도구를 UI에서 강제로 호출하지 않습니다. 제조사·차종·연식은 `hyundai / sonata / 2026`이며 도구가 다른 차량을 조회하려 하면 거부합니다. 현재 차량 ID도 DB에서 확인합니다. 추가 비밀키나 재임베딩은 필요 없습니다.

호출 경로:

```text
app_kbj.py ────────────────────────┐
                                  ├→ car_search/chat_runtime.py → CarManual Agent → 도구
anna_rag/chatbot/app.py            │
  → sonata_backend.py ────────────┘
```

수정 위치:
- 화면 디자인: 개인 테스트 화면은 `app_kbj.py`, 배포 화면은 `anna_rag/chatbot/app.py`.
- 대화 흐름·이력 범위·검색 개수·다운로드 분기: `car_search/chat_runtime.py` 한 곳.
- Agent 프롬프트·도구: `car_search/car_manual.py`.
- 검색·재정렬·답변 프롬프트: `car_search/car_manual_search_service.py`.

`app_kbj.py`에 새로운 동작을 직접 추가하면 공통 화면에는 전파되지 않습니다. 공유할 동작은 runtime/Agent에 추가해야 합니다. 화면 파일을 통째로 실행하거나 복사하는 방식은 아닙니다.

대화 이력은 첫 접속 때 생성하는 `anna_rag.sonata_chat_sessions`와 `anna_rag.sonata_chat_turns`에 저장합니다. 기존 IONIQ 5 이력과 팀원의 설명서 테이블은 변경하지 않습니다. 새 테이블은 RLS를 활성화하고 공개 API의 접근 권한을 제거합니다. 서버의 DB_URL 계정에는 테이블 생성 및 읽기·쓰기 권한이 필요합니다.

같은 세션의 최근 6개 메시지(최대 3문답)를 Agent에 전달하고 검색 개수는 개인 화면과 동일한 10개로 설정합니다. 전체 대화 및 연결 이미지는 팀원의 HTML 다운로드 기능에 전달합니다. 뒤로 가기는 세션을 종료하고 다시 입장하면 새 세션을 만듭니다. 같은 요청 ID의 재시도는 저장된 답변을 반환하며, 다른 질문에 같은 ID를 재사용하면 거부합니다. runtime이 반환한 오류 상태도 답변과 구분해 기록하며, 실행 자체가 예외로 끝난 요청은 롤백합니다. 이 이력은 기존 IONIQ 전용 품질 대시보드 집계에는 아직 포함되지 않습니다.

Sonata 답변은 팀원 코드처럼 페이지 번호로 출처를 안내합니다. 하단의 ‘검색에 사용한 설명서’는 검색 근거 목록이며 모든 항목이 답변에서 인용됐다는 뜻은 아닙니다. 다운로드는 저장소의 `data/DN8_2026_ko_KR.pdf`를 사용합니다.

## Streamlit Community Cloud 설정

- Repository: `encore-ai-campus/mle-02-p1-team1`
- Branch: `main`
- Main file path: `src/car_search_rag/anna_rag/chatbot/app.py`
- Python: `3.12`
- Advanced settings → Secrets: `secrets.example.toml`의 네 항목을 실제 값으로 입력합니다. 루트 Secrets 값은 환경변수로 제공됩니다.
- 공개 링크로 공유하려면 앱의 열람 범위를 공개로 설정합니다.

비밀키와 DB 비밀번호는 GitHub에 올리지 않습니다. 기존 Supabase의 `anna_rag` 테이블과 `images` 버킷을 사용하므로 배포 시 노트북을 다시 실행하거나 재임베딩할 필요가 없습니다. DB_URL은 배포 서버에서 접속 가능한 Supabase 연결 문자열을 사용합니다.

엔트리포인트 폴더의 requirements.txt에는 웹 앱 실행에 필요한 패키지만 고정했습니다. 루트의 학습용 의존성 대신 이 파일을 사용합니다. PDF 다운로드에 사용하는 설명서와 차량 이미지, Pretendard 글꼴은 앱 폴더에 포함되어 있습니다.

## 로컬 실행

저장소 루트에서 실행합니다.

```sh
python -m pip install -r src/car_search_rag/anna_rag/chatbot/requirements.txt
python -m streamlit run src/car_search_rag/anna_rag/chatbot/app.py
```

로컬에서는 루트 `.env`를 사용합니다. 실제 질문은 OpenAI API를 호출하며 대화/실행 기록은 Supabase에 저장됩니다. 현재 데모 세션은 `is_test=True`로 기록합니다. 대화 화면에서 뒤로 가면 세션을 종료하고 새 차종 선택 화면으로 돌아갑니다.

## 배포 확인

1. 첫 화면의 차량 카드와 비활성 관리자 버튼을 확인합니다.
2. IONIQ 5와 SONATA를 각각 선택해 질문을 입력하고 답변, 출처, 관련 그림을 확인합니다.
3. PDF 다운로드와 뒤로 가기를 확인합니다.
4. 새 브라우저 세션에서 이전 사용자 대화가 표시되지 않는지 확인합니다.

공식 배포 안내: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
