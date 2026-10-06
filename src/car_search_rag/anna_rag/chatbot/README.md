# 자동차 설명서 챗봇 배포

Streamlit UI에서 IONIQ 5와 SONATA 2026 설명서를 선택해 대화할 수 있습니다. SANTA FE는 별도 설정이 필요하며 CASPER는 연결하지 않았습니다. 관리자 모드는 비활성화되어 있습니다.

## SONATA 연결 및 팀원 수정 위치

쏘나타는 기존 `app_kbj.py`와 `src/car_search_rag/car_search/` 폴더에서 작업합니다.
제가 추가했던 `chat_runtime.py`, `ui_backend.py`는 제거했습니다.

```text
공통 UI → registry → app_kbj.py의 create_backend / SonataBackend
                          ↓
                     prepare_reply
                          ↓
            car_search/car_manual.py → 검색 서비스

개인 실행: streamlit run app_kbj.py → main → 같은 prepare_reply
```

- `app_kbj.py`의 `prepare_reply`: 쏘나타 검색 개수, 전달할 대화 범위, 다운로드 분기.
- `app_kbj.py`의 `SonataBackend`: 배포된 쏘나타의 접속별 메모리 대화 관리.
- `app_kbj.py`의 `main`: 개인 테스트 화면. 공통 UI가 import할 때 실행되지 않습니다.
- `car_search/car_manual.py`: 팀원의 기존 Agent 지침 및 도구.
- `car_search/car_manual_search_service.py`: 팀원의 기존 검색·재정렬·답변 생성.

UI와 동작이 뒤섞이지 않도록 기존 파일 안에 함수 경계만 두었습니다. 동작 변경은
`prepare_reply` 또는 Agent/서비스에 작성하면 두 화면에 적용됩니다.
`main` 안에만 추가한 동작은 개인 테스트 화면에만 적용됩니다.

아이오닉의 Agent·검색 설정·DB 기록은 독립적입니다. 쏘나타는 현재 접속 기록만 메모리에
보관하고 나가면 비웁니다. 과거 연결에서 생성된 `anna_rag.sonata_chat_*` 테이블은
더 이상 읽거나 쓰지 않으며 기존 데이터는 삭제하지 않았습니다.

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


## SANTA FE 연결

기존 `zzong_santafe_lag/app.py`의 `create_backend`로 연결합니다. 아이오닉·쏘나타 로직은 호출하지 않습니다.
개인 화면처럼 검색 후 발췌를 보여주고 별도 **답변 정리하기** 버튼으로 생성합니다.
검색 개수 5개, 최근 질문 10개 보관, 부모 근거·각주·검토·그림 정책은 팀원 코드 기준입니다.

Streamlit Secrets에 팀원이 준비해야 할 값:
- `ZZONG_DB_URL`: 산타페 개인 DB 연결. 기존 팀 DB_URL을 바꾸지 않습니다.
- `ZZONG_EMBEDDING_RUN_ID`: 개인 active_run.json의 embedding_run_id. 원문 run_id와 다릅니다.
- `ZZONG_SUPABASE_URL`: 산타페 DB와 같은 프로젝트의 Storage URL.
- 기존 `OPENAI_API_KEY`: 질문 임베딩·답변 생성용.

개인 파일 active_run.json이 배포 저장소에 있으면 버전 ID 환경변수 대신 기존 파일을 사용해도 됩니다.
없는 설정을 임의로 추정하거나 로컬 모델로 자동 전환하지 않습니다. 설정 전에는 화면에서 준비 필요 안내를 표시합니다.
실 DB 검색·생성 확인은 설정 완료 후 필요합니다.
