# Sonata Streamlit E2E Test

## 테스트 목적

`app_kbj.py`의 실제 질문 처리 흐름이 Sonata 2026 데이터에서 Embedding API → PostgreSQL/pgvector 검색 → Chat API → 답변 화면 출력까지 연결되는지 확인했다. PDF 재등록이나 데이터 변경은 실행하지 않았다.

## 테스트 환경

- Windows 프로젝트 가상환경 `.venv`
- Python 문법 검사: `app_kbj.py` 및 검색/DB 관련 모듈 `py_compile` 통과
- import 확인: Streamlit 1.64.0, psycopg 3.3.6, `psycopg_pool`, `pgvector`, `langchain_openai` import 통과
- Streamlit 서버: `streamlit run app_kbj.py --server.port 8517 --server.headless true`
- 포트/검증 경로 구분: 8517은 자동 검증 때 별도로 실행해 시작/health를 확인한 Streamlit 서버다. 질문 입력과 timing은 `AppTest` 실행에서 수집했으며, AppTest가 8517 서버의 브라우저 화면을 조작했다는 뜻은 아니다. 사용자가 직접 브라우저에서 확인하는 앱은 `http://localhost:8501`이고 8517과는 별도 인스턴스다.
- 서버 시작 메시지 확인, `/_stcore/health` 응답 `ok`
- 이 실행 환경에는 브라우저 surface가 없어 질문 입력과 화면 검증은 Streamlit `AppTest`로 `app_kbj.py`를 실제 실행해 진행했다. 별도 브라우저에서의 수동 시연은 검증하지 않았다.
- DB 연결 문자열, 비밀번호, API key 등 secret은 출력하거나 기록하지 않았다.

## 테스트 대상

- 앱: `app_kbj.py`
- 차량: Hyundai Sonata 2026 (`hyundai / sonata / 2026`)
- `car_id`: `20261003_000014`
- SQL의 차량 조건을 기준으로 수행한 사전 읽기 전용 SELECT 결과, 해당 조건에 일치한 차량은 이 `car_id` 한 건이었다.

## E2E 흐름

```text
Streamlit chat_input
→ CarManual.ask()
→ Agent가 car_manual_search tool 호출
→ CarManualSearchService.ask_manual()
→ 검색 질문 embedding (text-embedding-3-small, 1536차원)
→ CarManualRepository.search_manual()
→ SqlSession.select_list("car_manual.search_car_manual")
→ Sonata 조건 + pgvector <=> 검색 (SELECT)
→ 검색 문맥으로 Chat API 답변 생성
→ Streamlit st.markdown 출력
```

첫 질문에서는 대화 이력이 비어 있어 검색 질문 재작성 LLM 호출 없이 원문 질문이 embedding 검색에 사용됐다. `CarManual.ask()`의 agent tool 선택과 검색 결과 기반 답변 생성은 실제로 실행됐다.

## 테스트 질문

> 엔진 오일량을 확인할 때 레벨 게이지를 다시 뽑기 전에 무엇을 해야 하나요?

기대 근거: PDF p.463 / chunk_no 866.

## 검색 결과

Embedding API 호출은 성공했고 query embedding의 길이는 1536이었다. 실제 반환 10건의 모든 row에 `car_id=20261003_000014`가 확인됐다.

| 순위 | PDF page | chunk_no | similarity | 검색 row의 image URL |
|---:|---:|---:|---:|---|
| 1 | 464 | 868 | 0.545748 | 있음 |
| 2 | 463 | 867 | 0.542926 | 있음 |
| 3 | 463 | 866 | 0.527330 | 있음 |
| 4 | 465 | 870 | 0.502378 | 있음 |
| 5 | 447 | 840 | 0.489750 | 없음 |
| 6 | 465 | 869 | 0.486186 | 있음 |
| 7 | 447 | 839 | 0.460510 | 없음 |
| 8 | 430 | 810 | 0.456525 | 없음 |
| 9 | 7 | 10 | 0.449182 | 없음 |
| 10 | 29 | 52 | 0.446110 | 있음 |

기대 chunk 866은 3위로 검색되어 Top-5에 포함됐다. 이는 M6 전체 평가가 아닌 단일 E2E 질문 결과다.

## 답변 결과

Chat API 호출이 성공했고 Streamlit 답변 영역에 다음 답변이 출력됐다.

> 레벨 게이지를 뽑아 깨끗한 헝겊으로 닦은 뒤, 다시 꽂으세요. 그다음 다시 뽑아 엔진 오일량을 확인하면 됩니다.

앱 실행 중 예외는 없었다.

## 이미지 포함 검색 추가 확인

추가 질문: “차량 usb 위치 알려줘”. 이 질문은 이미지 정보가 검색·응답에 어떻게 나타나는지 확인하기 위한 보조 점검이며, 정답 page/chunk를 사전에 지정한 평가셋 문항은 아니다.

| 순위 | PDF page | chunk_no | similarity | image URL 존재 |
|---:|---:|---:|---:|---|
| 1 | 236 | 429 | 0.500236 | 있음 |
| 2 | 12 | 22 | 0.459431 | 있음 |
| 3 | 243 | 442 | 0.455442 | 있음 |
| 4 | 113 | 218 | 0.447184 | 없음 |
| 5 | 12 | 21 | 0.435682 | 있음 |
| 6 | 237 | 430 | 0.433532 | 있음 |
| 7 | 13 | 24 | 0.413843 | 없음 |
| 8 | 242 | 440 | 0.412585 | 있음 |
| 9 | 13 | 23 | 0.389675 | 없음 |
| 10 | 14 | 26 | 0.388995 | 있음 |

검색 결과에는 image URL이 포함된 row가 반환됐다. Chat 답변에는 앞좌석·뒷좌석 USB 위치 설명과 USB 포트/기능 전환 그림 링크가 포함됐다. 다만 답변에 inline image 문법은 없고 app은 `st.markdown(answer)`로 출력하므로 이미지 자체를 삽입한 것이 아니라 링크를 제공한 것이다. 이 보조 질문의 검색 적합성은 사전 정답 근거가 없으므로 평가 점수를 매기지 않았다.

## 출처 표시 결과

- 검색 결과 row에 page, chunk 번호, similarity, image URL이 반환됐다.
- 검색 문맥에는 page 번호, chunk 본문, image URL이 포함된다.
- 엔진오일 질문의 실제 답변 문구에는 page 출처나 image URL이 표시되지 않았다. 보조 USB 질문 답변은 그림 링크 markdown을 포함했지만 PDF page 인용은 없었다.
- `app_kbj.py`는 답변을 `st.markdown(answer)`로 출력하며 검색 결과를 별도 citation 컴포넌트나 `st.image`로 표시하지 않는다.
- 따라서 검색 데이터에 image URL이 있고 prompt에 전달되는 것과, 사용자가 화면에서 출처/이미지를 확인할 수 있는 것은 구분해야 한다. page citation은 충족하지 못했고, image preview나 실제 링크 클릭은 브라우저 surface 부재로 확인하지 못했다.

## 성능 측정

`@st.cache_resource` 초기화 경로에서 `DatabaseManager.warmup()`이 실행됐고 로그에 `DB POOL created min_size=1 max_size=5`가 나타났다. 같은 질문 3회에서 아래 `select_list()` 로그를 수집했다.

| 회차 | connect_ms | sql_log_ms | query_fetch_ms | total_ms |
|---:|---:|---:|---:|---:|
| 1 | 0.1 | 2.9 | 769.7 | 810.0 |
| 2 | 0.1 | 3.6 | 119.7 | 162.1 |
| 3 | 0.0 | 3.5 | 254.1 | 653.6 |

비교용 과거 값(사용자 제공, pool/warm-up 전 기록)은 `connect_ms=577.1`, `sql_log_ms=5.5`, `query_fetch_ms=115.1`, `total_ms=729.5`다. 과거와 이번 측정은 동일한 반복 환경이 통제됐다고 확인되지 않아 성능 개선률로 일반화하지 않는다. 이번 세 회에서 connect 시간이 0.0–0.1ms로 낮고 pool 생성 로그가 확인된 것은 warm-up된 pool 대여 경로가 동작한 근거다. query/fetch와 total은 회차 간 변동이 있어 추가 원인 분석은 이번 범위에서 하지 않았다.

앱 최초 resource 생성/warm-up 시간은 `select_list()`의 각 query timing과 별도로 로그되지 않았다. 따라서 표의 `total_ms`는 질문 전체(embedding 및 Chat API 포함) 시간이 아니라 `select_list()` 내부 시간이다.

성능 표는 같은 엔진오일 질문의 첫 3회에서만 집계했다. 검색 메타데이터와 답변 표시를 확인하기 위해 같은 질문을 2회 더 실행했고, 이미지 동작을 확인하기 위해 USB 질문을 1회 실행했다. 이 3회는 timing 비교에 포함하지 않았다.

## PASS / FAIL

| 항목 | 결과 | 근거 |
|---|---|---|
| Streamlit 실행 | PASS | 서버 시작, health `ok`, AppTest에서 앱 초기 화면 실행 |
| Sonata 선택 | PASS | 앱 selectbox에서 `hyundai / sonata / 2026`; 읽기 전용 DB 확인에서 해당 조건은 car_id 한 건 |
| Embedding API | PASS | 실제 query embedding 생성, 길이 1536 |
| pgvector 검색 | PASS | `search_car_manual` SELECT가 10행 반환 |
| 기대 근거 검색 | PASS | chunk 866이 3위, Top-5 포함 |
| Chat API | PASS | 검색 문맥 기반 답변 생성 및 화면 출력 |
| 최종 답변 표시 | PASS | Streamlit chat 답변 markdown에 표시 |
| 페이지 출처 표시 | FAIL | 두 답변 모두 PDF page citation UI가 나타나지 않음 |
| 이미지 표시 | 부분 성공 | USB 답변에 그림 링크는 표시됐지만 image preview/component는 없음 |
| 전체 E2E | 부분 성공 | 실제 API·DB 검색·답변 경로는 통과. page citation은 미충족, 그림은 링크만 확인했고 브라우저 직접 조작은 환경상 미검증 |

## 발견한 문제

- 검색된 근거의 page와 image URL은 LLM 문맥에 들어가지만, 엔진오일 답변에는 page 출처가 없었다. USB 답변은 그림 링크를 제공했지만 실제 이미지 preview는 표시하지 않았다.
- UI는 답변만 markdown으로 보여주며 page/chunk 메타데이터와 image URL을 구조화해 노출하지 않는다.
- 이 실행 환경에 브라우저가 없어 일반 브라우저에서의 직접 입력/렌더링은 확인하지 못했다. `AppTest`로 동일 Streamlit 앱 스크립트의 widget 입력과 rerun을 검증했다.
- 성능 세 회에서 pool connect 구간은 낮게 관찰됐으나 query/fetch와 total 변동이 있었다. 이번 작업에서는 성능 원인을 추가로 튜닝하거나 장시간 분석하지 않았다.

## 사용자 브라우저 수동 확인 상태

- UI 변경 전 사용자가 실제 앱 `http://localhost:8501`에서 수동 확인했다. 이 앱은 자동 검증용 8517 서버와 별개다.
- 변경 전 결과: 두 질문/답변과 대화 이력은 정상, 엔진오일 답변에 page/chunk/별도 출처 영역은 없었다. USB 답변에는 page_0236이 포함된 그림 링크가 있었고 클릭 후 새 탭에서 이미지가 열렸지만 채팅 내부 preview는 없었다. 레이아웃에서 잘림/겹침은 눈에 띄지 않았다고 보고했다.
- UI 변경 후 실제 브라우저 재검증은 아직 대기 중이다. 이 세션에서 사용자의 브라우저 화면을 직접 캡처하지 않았으며, 변경 후 브라우저 최종 검증 완료로 기록하지 않는다.

## 검색 metadata 전달 및 UI 자동 회귀 검증

- 원인: SQL 결과의 page/chunk/image/similarity는 `search_docs`에 있었지만 `generate_manual_answer()`가 답변 문자열만 반환했고, Agent tool 및 `CarManual.ask()`도 최종 텍스트만 반환했다.
- 호환 방식: 기존 `CarManual.ask()`와 `CarManualSearchService.ask_manual()`은 계속 문자열을 반환한다. 새 `ask_with_sources()` / `ask_manual_with_sources()` 결과 객체를 추가했다. 검색 tool은 답변 문자열을 기존처럼 모델에 전달하고, 검색 row metadata는 LangChain `content_and_artifact`의 현재 `ToolMessage` artifact로 보존한다.
- 격리: 요청 결과를 cached service의 전역/공유 mutable 필드에 저장하지 않는다. 각 `agent.invoke()` 결과에서 그 호출의 artifact만 모아 immutable result로 반환하므로 다음 질문 및 동시 Streamlit session과 공유되지 않는다. UI도 각 assistant session message에 화면 표시용 출처/이미지만 저장한다.
- 출처 UI: 실제 검색 순서에서 page/chunk 쌍 중복을 제거해 최대 5개를 `출처 · 검색된 근거 chunk`로 표시한다. similarity는 사용자 화면에서 숨긴다.
- 이미지 UI: 비어 있지 않은 image URL을 순서대로 중복 제거하고 최대 3개를 `st.image()` preview와 원본 링크로 표시한다. 해당 검색 결과가 없으면 이미지 영역을 만들지 않는다. 답변에 이미 있던 그림 링크 문장은 유지한다.
- 실제 Sonata DB/API AppTest 두 질문 연속 실행: 두 답변 성공, 예외 0, 총 메시지 4개, 각 assistant 결과에 검색 metadata가 담겼고 두 질문의 source 목록이 분리됐다. USB 질문은 상위 5개 metadata로 p.12/chunk 22, p.236/chunk 429, p.237/chunk 430, p.243/chunk 442, p.113/chunk 218을 반환했고 image URL 3개를 확보했다. 2개 대화 turn을 다시 렌더링했을 때 Streamlit image element 6개가 생성됐다.
- 엔진오일 질문의 이번 재실행에서는 상위 5개가 p.488/chunk 908, p.448/chunk 850, p.448/chunk 845, p.448/chunk 846, p.141/chunk 277이었다. 이번 결과에는 기대 p.463/chunk 866이 없었다. 이전 별도 검색 기록에는 p.463/chunk 866이 3위였으므로 검색 질문 재작성/검색 결과가 실행 간 달라질 수 있음을 함께 기록한다. UI는 각 실행의 실제 검색 결과를 표시하며, 누락된 기대 chunk를 임의로 출처에 추가하지 않는다.
- 별도 mock AppTest로 p.463/chunk 866 및 USB metadata 표시, 동일 page/chunk와 image URL 중복 제거, 이미지 preview·원본 링크 렌더링, 두 assistant turn 간 metadata 독립성을 확인했다. 검색 결과가 없는 세 번째 요청은 빈 source/image로 남고 이전 metadata를 이어받지 않았으며 예외는 없었다.
- `CarManual.ask()`와 `CarManualSearchService.ask_manual()`의 문자열 반환 호환은 stub 테스트에서 확인했다. import 및 `py_compile`도 통과했다. 실제 브라우저에서 변경 후 UI 확인은 사용자가 다시 수행해야 한다.

## M0 / M5 / M8 완료 기준과의 관계

- **M0:** 실제 E2E에서 `text-embedding-3-small` embedding과 `gpt-6-luna` Chat API 경로가 동작했다. 데이터 수집은 Sonata PDF 직접 다운로드이며 데이터 수집 API 호출로 해석하지 않는다. API 독립 호출 기록은 별도 제출 기준이라면 추가할 수 있다.
- **M5:** 질문 → embedding → pgvector → 근거 chunk → Chat 답변 경로와 metadata 기반 출처/이미지 UI를 AppTest로 확인했다. 실제 브라우저의 수정 후 확인은 대기 중이며, 검색 결과 없음은 코드 기준으로만 확인했다.
- **M8:** Streamlit AppTest에서 Sonata 질문/답변, warm-up, 출처·image preview 요소를 확인했다. 사용자는 수정 전 8501 브라우저에서 수동 시연했으며 수정 후 실제 브라우저 확인, 분석 화면 통합, README 실행 절차 검증은 남아 있다.

## 기존 문서 충돌 확인

- `README_DRAFT.md`의 “실제 검색·답변 시연 결과는 확인되지 않았다”는 문구는 이번 AppTest E2E로 오래된 상태가 됐다.
- `PPT_DRAFT.md`의 warm-up 후 성능이 미측정이라거나 3회 timing이 추가로 필요하다는 문구도 이번 측정 결과로 갱신이 필요하다.
- 요청 범위에 따라 이 두 초안은 이번 작업에서 수정하지 않았다.

## 남은 작업

- [ ] 사용자 화면에 page/chunk 출처와 가능한 경우 image link/preview를 명확히 표시
- [ ] metadata UI 변경 후 8501 실제 사용자 앱에서 page/chunk 출처, 이미지 preview와 링크 클릭, 레이아웃, 대화 이력을 재확인
- [ ] M6 전체 11문항 평가에서 Hit@5 / MRR@5 및 실패 사례를 별도로 측정
- [ ] 필요하면 API 호출/응답 구조를 M0 기록용으로 별도 정리
- [ ] 성능 비교를 제출물에 반영할 때는 동일 앱/질문/조건의 반복 측정임을 명시
