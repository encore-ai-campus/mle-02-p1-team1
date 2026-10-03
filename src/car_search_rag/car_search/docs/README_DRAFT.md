# 소나타 매뉴얼 PDF 기반 RAG

제출용 README 초안이다. 설명 범위는 소나타 핵심 프로젝트와 data/DN8_2026_ko_KR.pdf로 한정한다.

## 1. 프로젝트 소개

자동차 사용자가 소나타 매뉴얼에 대해 질문하면 차량 매뉴얼 검색 결과를 바탕으로 답변하는 Python 프로젝트다. 핵심 Streamlit 진입 파일은 app_kbj.py이며 검색·등록 코드는 src/car_search_rag/car_search에 있다.

## 2. 프로젝트 목적

hyundai / sonata / 2026에 해당하는 매뉴얼 정보를 검색해 차량 기능·사용·점검 질문에 문서 근거 기반 답변을 제공한다.

## 3. 자동차 PDF 기반 RAG 구조

소나타 PDF → pypdf 페이지 텍스트 추출 → page_no metadata → RecursiveCharacterTextSplitter (800 / overlap 150) → text-embedding-3-small → PostgreSQL·pgvector 저장 → query embedding과 cosine distance 기반 검색 → 검색 문서·질문·대화 이력을 LLM에 전달.

페이지 이미지 처리에는 pymupdf와 Supabase Storage를 사용한다.

## 4. 주요 기술 스택

Python 3.12 이상, Streamlit, pypdf, pymupdf, LangChain, OpenAI embeddings/chat model, PostgreSQL, pgvector, psycopg, Supabase Storage.

## 5. 핵심 데이터 흐름

PDF 등록:

DocumentReader → CarManualRegisterService → CarManualRepository → PostgreSQL / pgvector

질문 검색:

CarManual → CarManualSearchService → CarManualRepository → PostgreSQL / pgvector

## 6. PDF 등록 과정

CarManualRegisterService.insert_pdf_docs(file_path, car_brand_nm, car_brand_eng_nm, car_nm, car_eng_nm, car_model_yr)가 등록 진입점이다. car_manual.py의 실행 예제는 data/DN8_2026_ko_KR.pdf를 hyundai / sonata / 2026으로 등록한다. splitter 값은 chunk_size 800, chunk_overlap 150이다. 실제 소나타 처리 건수는 현재 확인된 실행 결과가 없다.

## 7. 검색 및 RAG 과정

CarManualSearchService.ask_manual은 대화 이력을 고려해 검색 질문을 재작성하고 search_manual을 호출한다. 검색은 text-embedding-3-small query vector와 pgvector <=> 거리로 정렬한다. 기본 limit은 5이고 app_kbj.py의 호출 limit은 10이다. 검색 결과와 사용자 질문은 답변 생성 메서드에 전달된다.

## 8. 대화 이력 처리

app_kbj.py는 기존 Streamlit messages를 복사해 conversation_history로 전달한다. CarManual.car_manual_search는 Agent runtime messages에서 현재 질문 앞의 user/assistant 메시지를 구성해 검색 서비스에 전달한다. 대화 이력은 검색 질문 재작성과 답변 생성에 사용된다.

## 9. 실행 방법 및 환경 변수

저장소에서 핵심 앱을 실행해 성공한 명령 및 절차를 확인할 수 있는 기록은 없다. app_kbj.py가 Streamlit 앱 파일이라는 점은 확인되지만 실제 실행 명령은 검증 필요로 남긴다.

코드에서 DB_URL, SUPABASE_URL, SUPABASE_SECRET_KEY 환경 변수를 확인할 수 있고 루트 앱은 dotenv load_dotenv()를 호출한다. 모델 API 인증 설정도 필요하다. 비밀 값은 문서에 기록하지 않는다.

## 10. Streamlit 시연 상태

app_kbj.py가 핵심 앱 진입 파일이다. 소나타 매뉴얼 질문에 대해 실제 검색·답변이 성공하는 시연 결과는 현재 확인되지 않았다.

## 11. 데이터 및 전처리

DATA_SPEC.md, PREPROCESSING_SPEC.md, EDA_REPORT.md에 소나타 데이터·스키마·전처리와 측정 상태를 기록한다. 소나타 PDF의 페이지·텍스트·chunk 통계와 결측률은 현재 미측정이다.

## 12. 검색 품질 평가

소나타 기준 평가 데이터셋, Hit@k/MRR 실행 결과 및 개선 전·후 비교는 현재 없다. RAG_EVALUATION_REPORT.md는 상태와 추가 실행 절차를 기록한다. STATISTICAL_TEST_PLAN.md에는 검정 계획만 있으며 실행 결과는 없다.

## 13. 현재 한계 및 향후 개선

소나타 PDF의 페이지·텍스트·chunk 통계와 DB 결측률을 측정해야 한다. 소나타 정답 평가셋을 구축해 검색 성능을 측정하고, 동일 질의의 baseline 및 변경 후 결과와 통계 검정을 기록해야 한다. PDF hash 기반 중복 방지, 빈 페이지·머리말 정제, OCR 필요성도 검토할 항목이다. 핵심 앱의 실제 시연 절차를 확인해 README에 보완해야 한다.
