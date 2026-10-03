# 소나타 RAG 프로젝트 제출 현황

## 분석 범위

대상은 data/DN8_2026_ko_KR.pdf 한 개이며 핵심 코드 실행 예제의 차량 매핑은 hyundai / sonata / 2026이다. 측정·평가 실행 기록에서 소나타에 귀속되는 결과만 사용했다. 확인되지 않은 수치는 미측정 또는 결과 없음으로 표시한다.

## 1. PDF → RAG 파이프라인 현황

| 항목 | 현재 구현 상태 | 근거 파일 / 클래스 / 메서드 | 소나타 기준 확인 내용 | 부족한 부분 |
|---|---|---|---|---|
| PDF 확보 | 일부 구현 | data/DN8_2026_ko_KR.pdf; car_manual.py 실행 예제 | 로컬 PDF를 Sonata 2026 차량값으로 등록한다. | 제조사 원본 URL·수집 이력은 확인되지 않는다. |
| PDF 읽기 | 완료 | common/document_reader.py DocumentReader.set_pdf_reader | pypdf PdfReader 사용 | — |
| 페이지 텍스트 추출 | 완료 | DocumentReader.set_pdf_doc_list | 페이지별 page.extract_text() 사용 | OCR 결과는 없음. |
| 빈 문자열·불필요 데이터 처리 | 일부 구현 | DocumentReader.set_pdf_doc_list | 추출 텍스트를 페이지 문서로 구성한다. 빈 문자열·머리말·꼬리말 제거는 확인되지 않는다. | 소나타 빈 페이지·텍스트 품질 측정 필요. |
| Chunk 분할 | 완료 | CarManualRegisterService._extract_and_split_chunks | RecursiveCharacterTextSplitter 사용 | 소나타 실처리 통계 없음. |
| chunk_size / overlap | 완료 | _extract_and_split_chunks | chunk_size=800, chunk_overlap=150 | 실제 소나타 chunk 분포 미측정. |
| metadata | 일부 구현 | _extract_and_split_chunks; CarManualRepository.insert_car_manual_chunks | page_no, chunk_no, 차량·chapter 연결 필드를 저장한다. | 소나타 DB row metadata 분포 미측정. |
| PDF 재등록 중복 처리 | 일부 구현 | car_manual.sql merge_car; _insert_car_manual_data | 차량 row merge가 있다. PDF/chunk hash 중복 방지는 확인되지 않는다. | 소나타 중복 등록 방지 정책 없음. |
| Embedding | 완료 | _create_chunk_embeddings; CarManualSearchService | text-embedding-3-small, 코드 상수 차원 1536 | 소나타 적재 실행 건수 미확인. |
| Vector DB·저장 구조 | 완료 | CarManualRepository; car_manual.sql; 제공 DDL | PostgreSQL/pgvector, 차량·chapter·chunk·image 테이블 구조 | 운영 DB 적용 상태 및 소나타 row 수 미확인. |
| 유사도 검색 | 완료 | CarManualSearchService.search_manual; search_car_manual | pgvector <=> 거리, 1-distance similarity, 차량 필터 | 소나타 score 분포 미측정. |
| top-k / limit | 완료 | search_manual; app_kbj.py | 서비스 기본 5, 앱 호출 10 | — |
| 검색 문맥 LLM 전달 | 완료 | CarManualSearchService.ask_manual, generate_manual_answer | 검색 문서·질문·대화 이력을 답변 생성에 전달 | 소나타 답변 평가 결과 없음. |
| 근거 밖 답변 억제 | 일부 구현 | generate_manual_answer | 매뉴얼 근거 사용 지시와 무결과 응답이 있다. | 소나타 답변 근거 자동 검증 결과 없음. |
| conversation_history | 완료 | CarManual.car_manual_search; rewrite_search_question; ask_manual | 현재 질문 이전 user/assistant 이력을 검색 재작성·답변에 전달 | — |
| 정량 검색 평가 | 미구현 | CarManualSearchService.search_manual | 소나타 평가 결과 없음 | 정답 평가셋과 실행 결과 필요. |

## 2. 제출 요구사항 현황

| 항목 | 현재 구현 상태 | 근거 | 소나타 기준 확인 내용 | 부족한 부분 |
|---|---|---|---|---|
| 데이터셋 | 일부 구현 | data/DN8_2026_ko_KR.pdf; car_manual.py | 단일 대상 PDF와 Sonata 차량 매핑 확인 | 원본 수집 이력·평가 label 없음. |
| 데이터 명세서 | 일부 구현 | docs/DATA_SPEC.md; 제공 DDL | 저장 컬럼·타입·NULL 정의를 정리 | 소나타 DB row 결측률 미측정. |
| 전처리 명세서 | 완료 | docs/PREPROCESSING_SPEC.md | 핵심 PDF 처리 코드와 설정 문서화 | 실제 소나타 처리 통계 없음. |
| EDA | 일부 구현 | notebooks/01_pdf_inspection.ipynb; docs/EDA_REPORT.md | 노트북 존재, 소나타 대상 수치 출력은 확인되지 않음 | 소나타 PDF EDA 실행 필요. |
| 통계 검정 (필수) | 미구현 | docs/STATISTICAL_TEST_PLAN.md | 실행 결과 및 p-value 없음 | 동일 소나타 질의 결과로 검정 실행 필요. |
| TF-IDF | 미구현 | car_search 검색 코드; docs/TFIDF_ANALYSIS.md | 현재 소나타 핵심 프로젝트에는 TF-IDF 구현 및 실행 결과 없음 | 소나타 기준 결과 없음. |
| 실행 결과 포함 Markdown 보고서 | 일부 구현 | car_search/docs/ | 현재 코드·상태 문서 작성됨 | 실제 소나타 실행 결과를 추가해야 한다. |
| 인덱싱·적재 로그 | 일부 구현 | CarManualRegisterService._insert_car_manual_data | logger 호출 코드 있음 | 소나타 적재 실행 요약·건수 없음. |
| 검색 평가 데이터셋 | 미구현 | 저장된 소나타 평가 자료 확인 | 소나타 정답 근거 질의셋 없음 | 평가셋 구축 필요. |
| 검색 평가 결과 | 미구현 | docs/RAG_EVALUATION_REPORT.md | 소나타 기준 검색 품질 평가 결과 없음 | Hit@k/MRR 등 실행 필요. |
| 개선 전·후 비교 | 미구현 | 저장된 소나타 비교 결과 확인 | 결과 없음 | 동일 질의 비교 실행 필요. |
| Streamlit | 일부 구현 | app_kbj.py | 앱 코드가 있다. 소나타 질의 시연 결과는 확인되지 않는다. | 실제 앱 실행·시연 필요. |
| README | 일부 구현 | README.md; docs/README_DRAFT.md | 루트 안내는 간략하고 제출 초안 작성됨 | 실행 확인 후 절차 보완 필요. |
| .env 제외 | 완료 | .gitignore | .env ignore 규칙과 미추적 확인 | — |
| KPT | 일부 구현 | docs/KPT_TEMPLATE.md | 기술 사실 기반 후보 템플릿 작성됨 | 작성자의 실제 개인 회고 보완 필요. |
| GitHub PR·리뷰 이력 | 확인 불가 | 현재 소나타 범위의 제출 자료 | PR·리뷰 증거 미확인 | 제출 요구 시 PR 링크와 리뷰 기록 첨부 필요. |

## 3. 소나타 기준 추가 실행 필요

1. 소나타 PDF 페이지 수·추출 텍스트·빈 페이지·페이지 텍스트 길이·chunk 길이와 수를 측정한다.
2. Sonata car_id로 DB 행을 필터링해 컬럼 결측률과 실제 적재 건수를 측정한다.
3. 소나타 정답 검색 질의셋을 만들고 Hit@k·MRR을 실행한다.
4. 동일 소나타 질의에 baseline 및 변경 후 검색을 수행하고 통계 검정을 실행한다.
5. 핵심 Streamlit 앱의 소나타 질문·검색·답변 흐름을 실제 시연한다.
