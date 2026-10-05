# 자동차 설명서 챗봇 배포

Streamlit UI와 Supabase에 저장한 IONIQ 5 설명서 검색을 연결합니다. 현재 IONIQ 5만 대화할 수 있으며, 다른 차량 카드는 팀원별 백엔드 연결 후 활성화합니다. 관리자 모드는 비활성화되어 있습니다.

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
2. IONIQ 5를 선택해 질문을 입력하고 답변, 출처, 관련 그림을 확인합니다.
3. PDF 다운로드와 뒤로 가기를 확인합니다.
4. 새 브라우저 세션에서 이전 사용자 대화가 표시되지 않는지 확인합니다.

공식 배포 안내: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
