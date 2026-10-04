# Hyundai Sonata 2026 차량 매뉴얼 RAG 발표 자료

> 최신 Notion M0–M9 내용, car_search 문서·코드·Notebook을 확인해 새 흐름으로 구성했다. M6 공식 Retrieval-only 결과와 브라우저 UI 관찰은 별도 지표로 유지한다.

## 1. Hyundai Sonata 2026
차량 매뉴얼 RAG

### 화면에 표시되는 내용
Hyundai Sonata 2026 차량 매뉴얼 RAG / 검색 결과 이미지 관련성 개선

### 발표 멘트
Sonata 2026 국문 취급설명서를 대상으로 자연어 질문에 매뉴얼 근거를 연결하는 검색·답변 서비스를 만들었습니다. 이 발표는 검색 점수, 실제 UI에서 본 이미지 문제, 그리고 PDF 레이아웃을 이용한 이미지 설명 메타데이터 개선 과정을 따라갑니다.

### 사용 근거 문서
- SONATA_PROJECT_SCOPE.md
- M7_IMPROVEMENT_EVALUATION.md

### 사용한 이미지/그래프 경로
- 없음 (해당 슬라이드의 도형·흐름도는 편집 가능한 PowerPoint 도형)

## 2. 긴 매뉴얼에서 필요한 근거를 찾는 문제

### 화면에 표시되는 내용
508페이지의 차량 매뉴얼 / 사용자가 자연어로 질문 / 관련 근거를 찾아 답변

### 발표 멘트
차량 매뉴얼은 수백 페이지에 걸쳐 사용, 안전, 정비 정보를 담고 있습니다. 사용자는 정확한 부품 명칭이나 페이지를 몰라도 자연어로 질문하고, 답변이 어느 설명에 근거하는지 확인하고 싶어 합니다. Sonata 프로젝트는 이 탐색 과정을 RAG 검색으로 연결했습니다.

### 사용 근거 문서
- EDA_REPORT.md
- Notion M0 · 주제·API 확정
- 사용자 제공 PROJECT BRIEF / PRD

### 사용한 이미지/그래프 경로
- 없음 (해당 슬라이드의 도형·흐름도는 편집 가능한 PowerPoint 도형)

## 3. 원본 508페이지를 검색 단위로 구성

### 화면에 표시되는 내용
PDF 508p / 텍스트 추출 508p / DB chunk 947 / image 955 / 초기 이미지 설명 메타데이터 없음 955/955

### 발표 멘트
원본 PDF에서 508페이지 모두 텍스트 추출 성공으로 기록되어 있습니다. 등록 코드는 RecursiveCharacterTextSplitter의 chunk_size 800, overlap 150 설정으로 검색 chunk를 만들고, 페이지와 이미지를 별도 metadata로 DB에 적재합니다. 초기 EDA에서는 이미지 955건 모두 설명 metadata가 없었습니다.

### 사용 근거 문서
- EDA_REPORT.md
- DATASET_SPEC.md
- sonata_pdf_eda.ipynb
- M7_IMPROVEMENT_EVALUATION.md

### 사용한 이미지/그래프 경로
- `src/car_search_rag/car_search/docs/figures/sonata_pdf_text_histogram.png`

## 4. Embedding 검색 결과를 답변과 이미지에 연결

### 화면에 표시되는 내용
적재: PDF → page text → RecursiveCharacterTextSplitter 800/150 → embedding / 질문: Streamlit → embedding → pgvector SQL → chunk → ChatOpenAI → 답변

### 발표 멘트
적재 시 PDF 페이지 텍스트를 800자 단위, 150자 overlap으로 분할하고 text-embedding-3-small로 1536차원 벡터를 저장합니다. 질문 때는 같은 embedding 모델로 query vector를 만들고, search_car_manual이 PostgreSQL + pgvector의 cosine distance 연산자로 chunk를 정렬합니다. ChatOpenAI가 검색 근거를 받아 답변을 만들고 Streamlit이 결과를 보여줍니다. HNSW index는 존재하지만 개별 실행계획에서 선택 여부는 별도로 봐야 합니다.

### 사용 근거 문서
- SONATA_PROJECT_SCOPE.md
- car_manual_register_service.py
- car_manual_search_service.py
- car_manual.sql
- app_kbj.py
- M4 실행계획 EXPERIMENT_LOG.md

### 사용한 이미지/그래프 경로
- 없음 (해당 슬라이드의 도형·흐름도는 편집 가능한 PowerPoint 도형)

## 5. M6 공식 Retrieval baseline

### 화면에 표시되는 내용
실제 앱 retrieval Top-10 / 공식 평가 Hit@5·MRR@5 / Hit@5 9/11 = 81.8% / MRR@5 0.5333 / M6-05 rank 6 · M6-11 rank 10 / 정답 근거 Top-10 포함 11/11 (보조 정보)

### 발표 멘트
실제 앱은 검색 결과를 Top-10까지 조회합니다. 공식 M6 평가는 더 엄격하게 Top-5를 기준으로 Hit@5와 MRR@5를 계산했습니다. Hit@5는 9/11(81.8%), MRR@5는 0.5333입니다. M6-05 정답 근거는 6위, M6-11은 10위입니다. 따라서 정답 근거 11개는 모두 실제 앱의 Top-10 범위 안에 포함됐습니다. 11/11은 앱 조회 범위를 설명하는 보조 정보이며 공식 평가 지표를 대체하지 않습니다. 브라우저 UI 관찰과도 별도입니다.

### 사용 근거 문서
- M6_RETRIEVAL_EVALUATION.md
- M6_RETRIEVAL_RESULTS.csv
- M6 Notion page

### 사용한 이미지/그래프 경로
- 없음 (해당 슬라이드의 도형·흐름도는 편집 가능한 PowerPoint 도형)

## 6. 검색 답변과 이미지 관련성은 별도 품질 축

### 화면에 표시되는 내용
초기 UI 관찰 / 와이퍼 교체 질문 → 타이어 이미지 / 비상등 질문 → 주차 경고 이미지

### 발표 멘트
초기 Streamlit 시연에서 텍스트 답변은 질문을 다루더라도, 같은 페이지에 연결된 이미지가 질문과 직접 관련이 낮은 경우가 관찰됐습니다. 예를 들어 와이퍼 교체 질문에 타이어 이미지가 함께 보였고, 비상 경고등 질문에도 주차 경고 관련 이미지가 섞였습니다. 이는 텍스트 Hit@5만으로 화면의 이미지 관련성을 평가할 수 없다는 점을 보여줬습니다.

### 사용 근거 문서
- M6_BROWSER_E2E_RESULT.md
- M7_IMPROVEMENT_EVALUATION.md
- 원본 PDF physical p.236

### 사용한 이미지/그래프 경로
- `src/car_search_rag/car_search/docs/tmp/pptx_car_search_final/assets/manual_page_236.png`

## 7. 모델 교체만으로는 해결되지 않았다

### 화면에 표시되는 내용
초기 규칙형 방식은 보수적 / 텍스트 LLM 문구 개선은 제한적 / 문맥을 넓히면 다른 설명 혼입 / 다음 단계: PDF 레이아웃 분석

### 발표 멘트
초기에는 주변 문맥 규칙을 production에 적용했지만 955개 중 9개만 설명이 생성됐습니다. 동일 100건 표본의 텍스트 LLM 실험에서도 더 큰 모델이 규칙 후보를 실질적으로 더 좋게 다듬는 사례는 제한적이었습니다. context를 늘리면 개선 후보는 늘었지만 다른 주제의 문맥이 섞이는 문제가 생겼습니다. 그래서 모델 비교를 멈추고 PDF의 실제 레이아웃을 분석했습니다.

### 사용 근거 문서
- M7_IMPROVEMENT_EVALUATION.md
- IMAGE_DESC_TEXT_LLM_100.md
- IMAGE_DESC_TEXT_LLM_100_GPT56_LUNA.md
- IMAGE_DESC_TEXT_LLM_100_GPT56_TERRA.md
- IMAGE_DESC_CONTEXT_DIAGNOSTIC_100.md

### 사용한 이미지/그래프 경로
- 없음 (해당 슬라이드의 도형·흐름도는 편집 가능한 PowerPoint 도형)

## 8. PDF 레이아웃이 이미지의 검색 문맥을 제공했다

### 화면에 표시되는 내용
문서 구조: 제목/소제목 → 직전 기능·타입 label → 이미지 / 예: 앞좌석 열선 시트 사용 / A타입

### 발표 멘트
문서 페이지를 확인하면서 제목 또는 기능명, 짧은 타입 label, 이미지가 일정한 공간 관계로 배치된다는 점을 확인했습니다. 예를 들어 ‘앞좌석 열선 시트 사용’ 아래에 A타입·B타입 label이 있고 각 그림이 이어집니다. 최종 방식은 이미지 바로 위 텍스트를 중심으로 같은 column, 수평 겹침, 거리 순으로 연결합니다. font 크기는 후보 순위 신호로만 사용하며 9pt도 버리지 않습니다.

### 사용 근거 문서
- IMAGE_DESC_HEADING_100.md
- M7_IMPROVEMENT_EVALUATION.md
- car_manual_register_service.py
- 원본 PDF physical p.463

### 사용한 이미지/그래프 경로
- `src/car_search_rag/car_search/docs/tmp/pptx_car_search_final/assets/manual_page_463.png`

## 9. 최종 이미지 설명 확보율은 93.2%

### 화면에 표시되는 내용
이미지 955개 / 설명 저장 890개 (93.2%) / 제목만 400 / 제목+구분 label 490 / 설명 없음 65

### 발표 멘트
최종 등록된 이미지 설명 metadata는 문서에 실제 있는 제목·기능명·절차명과 필요한 A/B 타입 label을 추출해 구성합니다. 955개 중 890개에 설명이 저장됐고 65개에는 설명이 없습니다. 400개는 제목만, 490개는 제목과 label 조합입니다. 설명 확보율은 metadata 저장 비율이지 이미지 설명의 정확도 점수가 아닙니다.

### 사용 근거 문서
- M7_IMPROVEMENT_EVALUATION.md
- M7_AFTER_RESULTS.csv
- Notion M7 · 개선 실험 1회

### 사용한 이미지/그래프 경로
- 없음 (해당 슬라이드의 도형·흐름도는 편집 가능한 PowerPoint 도형)

## 10. M7은 이미지 선택을 바꾸고 텍스트 Retrieval 점수는 유지

### 화면에 표시되는 내용
M6 Before / M7 After: Hit@5 81.8%, MRR@5 0.5333 유지 / 실제 앱 retrieval Top-10 / 공식 평가 Hit@5 / Top-10 근거 포함 11/11은 보조 정보

### 발표 멘트
M7은 텍스트 검색 SQL, embedding, Top-K를 바꾸지 않았습니다. 검색 결과 페이지 안에서 이미지 설명 metadata를 이용해 표시할 이미지를 별도로 선택했습니다. 실제 앱은 Top-10까지 조회하고 공식 평가는 Hit@5/MRR@5를 사용합니다. 정답 근거 11개는 모두 Top-10 안에 있었지만, 11/11은 앱 범위를 설명하는 보조 정보입니다. 동일 11개 질문의 M6/M7 공식 Retrieval-only 결과는 Hit@5 9/11, MRR@5 0.5333으로 유지됐습니다.

### 사용 근거 문서
- M6_RETRIEVAL_EVALUATION.md
- M6_RETRIEVAL_RESULTS.csv
- M7_IMPROVEMENT_EVALUATION.md
- M7_AFTER_RESULTS.csv

### 사용한 이미지/그래프 경로
- 없음 (해당 슬라이드의 도형·흐름도는 편집 가능한 PowerPoint 도형)

## 11. 실제 Streamlit에서 관련 이미지 노출은 나아졌지만 남은 사례가 있다

### 화면에 표시되는 내용
실제 브라우저 관찰 / 직접 적합 M6-01·04·07·11 / 부분 적합 M6-06·08·09 / 무관 이미지 일부 M6-03·05

### 발표 멘트
사용자가 실제 Streamlit 브라우저에서 M6 질문들을 확인한 결과를 이미지 관련성으로 별도 분류했습니다. 직접 적합 사례는 M6-01, 04, 07, 11, 부분 적합은 M6-06, 08, 09입니다. M6-03, 05에는 무관 이미지가 일부 섞였습니다. 이는 정성적 UI 관찰이며 image_desc coverage와 같은 정량 지표가 아니고, 완전한 이미지 정합성의 증명도 아닙니다.

### 사용 근거 문서
- M7_IMPROVEMENT_EVALUATION.md
- M6_BROWSER_E2E_RESULT.md
- Notion M7 · 개선 실험 1회

### 사용한 이미지/그래프 경로
- 없음 (해당 슬라이드의 도형·흐름도는 편집 가능한 PowerPoint 도형)

## 12. 검색 품질 개선은 데이터와 문서 구조를 이해하는 데서 시작

### 화면에 표시되는 내용
데이터와 검색 평가 → UI 문제 관찰 → PDF 레이아웃 분석 → 이미지 설명 metadata 개선

### 발표 멘트
텍스트 검색 점수와 이미지 관련성을 별도 지표로 살펴봤습니다. 강한 모델을 연속해서 시험했지만 문구 개선은 제한적이었고, PDF 제목과 이미지 배치를 이용한 규칙형 추출이 더 실용적이었습니다. 실제 UI에서 관찰한 관련·부분 관련·무관 이미지 사례를 구분해 다음 개선 근거로 남깁니다.

### 사용 근거 문서
- PROJECT_PROGRESS_REPORT.md
- M6_RETRIEVAL_EVALUATION.md
- M7_IMPROVEMENT_EVALUATION.md
- Notion M7 · 개선 실험 1회
- Notion M9 · 시연·회고

### 사용한 이미지/그래프 경로
- 없음 (해당 슬라이드의 도형·흐름도는 편집 가능한 PowerPoint 도형)

## 수치 해석 주의

- M6의 Hit@5 81.8%와 MRR@5 0.5333은 11문항 공식 Retrieval-only 평가다.
- M7의 텍스트 Retrieval 결과는 M6와 동일했다. image_desc coverage 93.2%는 metadata 저장률이지 이미지 정확도/관련성 점수가 아니다.
- 브라우저의 직접/부분/무관 분류는 실제 Streamlit UI에 대한 정성 관찰이며 공식 M6 Retrieval 수치에 합산하지 않았다.
- 저장소에 실제 Streamlit 화면 캡처가 없어 PPT에 임의의 앱 화면 이미지를 만들지 않았다.
