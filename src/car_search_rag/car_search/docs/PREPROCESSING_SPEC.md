# PDF 전처리 명세서

## 대상과 범위

핵심 입력은 data/DN8_2026_ko_KR.pdf 한 개다. car_manual.py의 실행 예제는 이를 hyundai / sonata / 2026으로 등록한다. 이 문서는 소나타 핵심 car_search 코드만 설명한다.

## 소나타 PDF 처리 파이프라인

| 단계 | 소나타 핵심 구현 | 근거 및 설정 |
|---|---|---|
| PDF 확보 | 로컬 파일 경로를 등록 메서드에 전달한다. 자동 수집·다운로드는 확인되지 않는다. | CarManualRegisterService.insert_pdf_docs; data/DN8_2026_ko_KR.pdf |
| PDF 읽기 | pypdf PdfReader로 연다. | common/document_reader.py, DocumentReader.set_pdf_reader |
| 페이지 텍스트 | 각 페이지에서 page.extract_text()를 호출해 페이지 번호와 텍스트를 수집한다. | DocumentReader.set_pdf_doc_list |
| 텍스트 정제 | 빈 페이지 제거, 머리말·꼬리말 제거 및 OCR은 확인되지 않는다. | DocumentReader.set_pdf_doc_list |
| 목차 metadata | pymupdf의 1단계 PDF 목차로 장 이름과 페이지 범위를 구성한다. | CarManualRegisterService._extract_pdf_chapters |
| Chunk | RecursiveCharacterTextSplitter를 사용한다. chunk_size=800, chunk_overlap=150이며 페이지 문서 metadata에 page_no, 분할 결과에 chunk_no를 기록한다. | CarManualRegisterService._extract_and_split_chunks |
| Embedding | OpenAI text-embedding-3-small을 사용한다. 서비스 코드 상수 dimension은 1536이다. | _create_chunk_embeddings; car_manual_search_service.py |
| 이미지 | pymupdf로 내장 이미지를 추출해 Supabase Storage에 올리고 URL·페이지·순번을 저장한다. 설명은 현재 None으로 전달된다. | _extract_and_upload_images, _upload_single_image; common/storage_manager.py |
| DB 적재 | 차량·chapter·chunk·image를 transaction으로 적재한다. | _insert_car_manual_data; car_manual.sql |
| 검색 | query embedding과 pgvector <=> 거리를 이용해 검색 순위를 정하고 1-distance를 similarity로 반환한다. | CarManualSearchService.search_manual; car_manual.sql search_car_manual |

## 등록 정책 확인

| 항목 | 소나타 핵심 코드 상태 |
|---|---|
| 빈 페이지 | 현재 미구현: page.extract_text 결과의 빈 문자열 제거 단계가 확인되지 않음 |
| 머리말·꼬리말 | 현재 미구현 |
| OCR | 현재 미구현 |
| PDF hash 저장 | 현재 미구현 |
| 동일 PDF 중복 등록 방지 | 현재 미구현: 차량 정보 merge는 있으나 PDF/chunk/image 중복 판별은 확인되지 않음 |
| chunk 중복 제거 | 현재 미구현 |
| PDF별 source/version metadata | 현재 미구현 |
| 이미지 추출 및 URL 저장 | 구현됨; 소나타 PDF에 대한 실제 건수는 현재 미측정 |

## 실행 결과 상태

소나타 PDF의 실제 페이지 수, 텍스트 추출 건수, chunk 수, embedding 적재 건수 및 이미지 건수는 현재 실행 결과에서 확인되지 않는다. 설정값 800/150은 소나타 실행 결과 통계가 아니다.
