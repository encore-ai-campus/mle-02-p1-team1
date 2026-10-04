# car_search 작업 규칙

## 작업 디렉터리 범위

- 이 AGENTS.md는 `src/car_search_rag/car_search/` 모듈 작업을 위한 규칙이다.
- 기본 수정 대상은 `src/car_search_rag/car_search/` 내부 파일이다.
- Sonata/car_search 작업과 직접 관련이 없는 다른 팀원 모듈은 수정하지 않는다. 예를 들면 `src/car_search_rag/anna_rag/`, `src/car_search_rag/zzong_santafe_lag/` 및 그 밖의 팀원 전용 디렉터리가 해당한다.
- 공용 모듈인 `src/car_search_rag/common/`은 car_search 기능 구현이나 버그 수정에 실제로 필요한 경우에만 수정할 수 있다.
- `common/` 수정 전에는 다음을 확인한다.
  1. car_search가 해당 공용 코드를 실제로 사용하는지 확인한다.
  2. 기존의 다른 호출부에 영향을 줄 가능성을 확인한다.
  3. 가능한 최소 범위로 변경한다.
  4. 다른 차량이나 팀원 기능을 car_search 전용 동작으로 바꾸지 않는다.
- `common/` 수정이 필요하지 않으면 car_search 내부에서 해결하는 것을 우선한다.
- 저장소 루트 설정, 다른 사람의 디렉터리, 다른 차량 데이터는 명시적으로 요청받지 않는 한 변경하지 않는다.

## 1. 프로젝트 범위

- 대상 차량은 Hyundai Sonata 2026이며 project code는 DN8이다.
- 원본 PDF는 저장소 루트 기준 `data/DN8_2026_ko_KR.pdf`이다.
- 분석, 검색 품질 평가, 성능 측정, 문서화에는 Sonata 데이터만 사용한다.
- DB는 여러 차량과 사용자가 함께 쓰는 공용 환경일 수 있다. Sonata의 범위가 확인되지 않은 다른 차량·사용자 데이터는 분석에 섞지 말고, 수정하거나 삭제하지 않는다.
- DB 작업 전 현재 Sonata의 `car_id`를 실행 시점에 조회해 확인한다. 문서나 이전 실행 로그에 적힌 ID를 현재 ID로 간주하지 않는다.

## 2. Notebook 위치

현재 개인 Sonata Notebook은 다음 두 파일이다. README, docs, Notion 링크 및 재현 안내에는 이 경로를 기준으로 쓴다.

- `src/car_search_rag/car_search/notebook/sonata_pdf_eda.ipynb`
- `src/car_search_rag/car_search/notebook/sonata_tfidf_analysis.ipynb`

저장소 루트의 `notebooks/kbj_*` 경로는 현재 개인 Notebook 기준 경로로 사용하지 않는다. 기존 문서에서 이전 Notebook 경로를 발견해도 이 지침만으로 해당 문서를 자동 변경하거나 Notebook을 이동·삭제하지 않는다.

## 3. 문서 위치

- Sonata 분석, EDA, 실험, M6/M7 결과 문서는 `src/car_search_rag/car_search/docs/`를 기준으로 확인한다.
- 작업 전 관련 기존 문서와 코드·SQL을 함께 확인하고, 확인되지 않은 값이나 실행하지 않은 결과를 문서에 사실처럼 쓰지 않는다.

## 4. M6 / M7 평가 규칙

- 기존 M6 공식 Retrieval 결과는 M7의 **Before baseline**으로 보존한다.
- `docs/M6_RETRIEVAL_EVALUATION.md`와 `docs/M6_RETRIEVAL_RESULTS.csv`의 기존 결과를 덮어쓰거나 소급 수정하지 않는다.
- M7 개선 실험은 **After** 결과로 별도 기록한다. 현재 파일 기준 결과 위치는 `docs/M7_IMPROVEMENT_EVALUATION.md`와 `docs/M7_AFTER_RESULTS.csv`이다.
- 과거 평가의 실행 당시 `car_id`는 historical 값으로 보존하고 현재 ID와 혼동하지 않는다.
- `image_desc` 개선 결과는 텍스트 Retrieval 지표(Hit@K, MRR 등)와 이미지 관련성 평가를 구분한다. 이미지 metadata 생성만으로 검색 품질이 개선됐다고 단정하지 않는다.

## 5. image_desc

- `image_desc`는 검색·이미지 선택을 돕는 metadata이며 이미지의 완전한 자연어 caption으로 간주하지 않는다.
- 현재 production 생성 방식은 PDF layout의 위치 정보와 주변 텍스트를 이용하는 deterministic extraction이다.
- Text LLM 및 Vision 실험 결과는 실험 기록으로 보존한다. 이를 production 로직으로 임의 복원하거나 연결하지 않는다.
- 실제 검색에서 확인된 실패 사례를 근거로 개선하며, 전체 데이터의 의미 적합성을 확인하지 않은 채 검증 완료라고 기록하지 않는다.

## 6. 데이터 및 등록 주의

- Sonata 데이터를 조회·수정하는 작업은 Sonata의 현재 `car_id`를 먼저 확인하고, 가능한 한 그 ID로 범위를 제한한다.
- 과거 문서와 실험 로그의 historical `car_id`는 현재 ID로 일괄 치환하지 않는다.
- DB 또는 Supabase Storage 삭제·재등록·업로드는 사용자가 해당 작업을 명시적으로 요청한 경우에만 수행한다. 공유 범위가 불명확하면 작업을 중단하고 확인한다.
- 등록 시 car row 생성·변경과 하위 chapter/chunk/image 적재 경로를 구분하고, 요청된 범위 밖 데이터는 건드리지 않는다.

## 7. 작업 방식

- 수정 전에 대상 파일과 호출 경로를 확인하고, 요청 범위의 최소 변경만 한다.
- 추정한 건수, 결측률, 성능, 평가 결과를 사실처럼 작성하지 않는다. 확인할 수 없는 정보는 확인 필요로 표시한다.
- 실패하거나 보류된 실험 기록도 삭제하지 않고 history로 보존한다.
- 별도 요청이 없으면 Notion의 상태, 속성, 완료 체크박스를 변경하지 않는다.
