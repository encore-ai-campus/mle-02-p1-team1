# 이미지 상단 제목 기반 image_desc 실험 (seed 20261004)

이 문서는 기존 100개 표본에 대한 오프라인 진단이다. OpenAI/LLM/Vision 호출, DB/Storage 접근, production 코드 변경은 없다.

## 글꼴 크기 분포와 선택 기준

- 분석 표본 페이지 span 수: 4626; 20자 이상 span 수: 1999
- 빈도 상위 font size: `[(9.0, 3060), (10.7, 445), (6.0, 229), (8.5, 194), (9.5, 132), (11.0, 114), (10.0, 113), (8.9, 112), (12.0, 60), (7.0, 53), (26.0, 44), (8.0, 32)]` (pt, span 건수)
- 전체 span 중앙 font size: 9.00 pt; 긴 본문 span 중앙값(본문 기준): 9.00 pt
- 전체 span Q75/Q90: 9.00/10.72 pt; span 길이 P95: 26자
- 큰 제목 기준: max(본문 중앙값 × 4/3, 전체 span Q75) = 12.0 pt. 본문 중앙값은 9pt, 뚜렷한 큰 제목 cluster는 12pt였다.
- 보완 기준: 이미지에서 72pt 이내이고 본문보다 큰 font size이며 Medium/Bold 스타일인 짧은 제목도 후보로 허용했다. 표본에서 실제 제목형 10pt Medium 줄을 포착하고 A타입(7pt 일반체) 같은 라벨은 배제하기 위한 스타일 기준이다.
- PyMuPDF flags의 bit 16 또는 font명에 `Bold` 포함 여부를 bold 추정치로 기록했다.
- 선택은 이미지 위, 같은 column 및 충분한 수평 overlap인 줄만 대상으로 한다. 36→72→112pt로 반경을 단계 확장하고 첫 반경의 제목형 짧은 문구를 고른다. 본문 요약은 하지 않는다.

## 결과 집계

- 제목 추출: 35/100; None: 65/100
- 자동 추출 건수는 정확성 건수와 같지 않다. 정확한 제목/상위 제목/다른 section/놓친 제목 판정은 대표 샘플을 시각 검토한 뒤 확정해야 한다.
- 개별 이미지의 위쪽 text 후보(텍스트, font size, bbox, 이미지와 vertical 거리, overlap, bold 추정)는 JSON에 포함했다.
- 추출 성공 사례 contact sheet: `tmp/IMAGE_DESC_HEADING_CONTACT.png`

- None 사례를 표본 전반에서 균등 추출한 시각 점검 sheet: `tmp/IMAGE_DESC_HEADING_NONE_CONTACT.png`

## 제목 추출 성공 사례(표본)

### p.25 / image 3

- image bbox: `[235.19, 84.0, 399.58, 188.87]`; 선택 description: **타이어 공기압**
- 선택 제목: `타이어 공기압` | font size 14.0 pt (max 14.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4]` | bold 추정 `False`
- 제목 bbox: `[236.14, 62.89, 314.29, 80.0]` | 이미지 위 거리 4.0 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "타이어 공기압", "raw_text": "타이어 공기압", "bbox": [236.14, 62.89, 314.29, 80.0], "font_size": 14.0, "max_font_size": 14.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 7, "distance_pt": 4.0, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}, {"text": "1", "raw_text": "1", "bbox": [391.14, 16.11, 400.39, 46.77], "font_size": 26.0, "max_font_size": 26.0, "font": "HyundaiSansHeadKR", "flags": [4], "bold": false, "source_block_index": 0, "distance_pt": 37.23, "same_column": true, "horizontal_overlap": 0.912, "heading_like": false}]

### p.32 / image 2

- image bbox: `[36.72, 363.34, 201.11, 468.22]`; 선택 description: **유아/어린이의 에어백 관련 주의사항**
- 선택 제목: `유아/어린이의 에어백 관련 주의사항` | font size 12.0 pt (max 12.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4, 4]` | bold 추정 `False`
- 제목 bbox: `[37.58, 306.53, 194.12, 336.18]` | 이미지 위 거리 27.16 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "차량 운전 상태에서 탑승한 아이들을 안전하게보호하기 위해서는 아래의 사항을 지키십시오.", "raw_text": "차량 운전 상태에서 탑승한 아이들을 안전하게보호하기 위해서는 아래의 사항을 지키십시오.", "bbox": [37.37, 340.03, 201.09, 360.95], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansTextKR", "flags": [4, 4], "bold": false, "source_block_index": 5, "distance_pt": 2.39, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}, {"text": "유아/어린이의 에어백 관련 주의사항", "raw_text": "유아/어린이의 에어백 관련 주의 사항", "bbox": [37.58, 306.53, 194.12, 336.18], "font_size": 12.0, "max_font_size": 12.0, "font": "HyundaiSansTextKRMedium", "flags": [4, 4], "bold": false, "source_block_index": 4, "distance_pt": 27.16, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}, {"text": "않도록 적정한 위치로 좌석을 이동하십시오.", "raw_text": "않도록 적정한 위치로 좌석을 이동하십시오. ", "bbox": [45.85, 276.05, 201.65, 286.97], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansTextKR", "flags": [4], "bold": false, "source_block_index": 3, "distance_pt": 76.37, "same_column": true, "horizontal_overlap": 0.997, "heading_like": false}, {"text": "•주행 전 운전자와 탑승자는 에어백과 가깝지", "raw_text": "•주행 전 운전자와 탑승자는 에어백과 가깝지", "bbox": [36.73, 263.87, 200.37, 276.84], "font_size": 9.86, "max_font_size": 10.72, "font": "HyundaiSansHeadKR / HyundaiSansTextKR", "flags": [4, 4], "bold": false, "source_block_index": 3, "distance_pt": 86.5, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}, {"text": "하기 위해 개발된 보조 안전장치입니다. 안전벨트를 착용해야만 충돌이 발생할 때 에어백의 최대 효과를 얻을 수 있고, 그렇지 않으면 실명, 상해, 사망 등의 위험을 당할 수 있습니다.", "raw_text": "하기 위해 개발된 보조 안전장치입니다. 안전벨트를 착용해야만 충돌이 발생할 때 에어백의 최대 효과를 얻을 수 있고, 그렇지 않으면 실명, 상해, 사망 등의 위험을 당할 수 있습니다.", "bbox": [45.85, 211.08, 200.51, 262.0], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansTextKR", "flags": [4, 4, 4, 4, 4], "bold": false, "source_block_index": 3, "distance_pt": 101.34, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}]

### p.69 / image 1

- image bbox: `[234.95, 299.75, 399.58, 404.86]`; 선택 description: **어린이 보조 좌석 설치 금지**
- 선택 제목: `어린이 보조 좌석 설치 금지` | font size 10.0 pt (max 10.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4]` | bold 추정 `False`
- 제목 bbox: `[235.86, 286.11, 343.46, 298.33]` | 이미지 위 거리 1.42 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "어린이 보조 좌석 설치 금지", "raw_text": "어린이 보조 좌석 설치 금지", "bbox": [235.86, 286.11, 343.46, 298.33], "font_size": 10.0, "max_font_size": 10.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 13, "distance_pt": 1.42, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}, {"text": "에어백이 작동하면 스티어링 휠 및 크래시 패드의 에어백 관련 부품이 고온상태가 됩니다. 화상 위험이 있으므로 작동 직후에는 내장 부품을만지지 마십시오.", "raw_text": "에어백이 작동하면 스티어링 휠 및 크래시 패드의 에어백 관련 부품이 고온상태가 됩니다. 화상 위험이 있으므로 작동 직후에는 내장 부품을만지지 마십시오.", "bbox": [235.79, 226.51, 399.04, 267.43], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansTextKR", "flags": [4, 4, 4, 4], "bold": false, "source_block_index": 11, "distance_pt": 32.32, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}, {"text": "Ҋ", "raw_text": "Ҋ", "bbox": [263.77, 210.34, 273.23, 221.6], "font_size": 11.0, "max_font_size": 11.0, "font": "HyundaiSansTextKRMedium-", "flags": [4], "bold": false, "source_block_index": 9, "distance_pt": 78.15, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}, {"text": "에어백이 부풀어 오를 때, 큰 소음과 차량 내부에 연기처럼 보이는 가루가 남겨집니다. 이는정상적인 현상으로 에어백이 팽창할 때 생기는결과입니다. 에어백이 작동한 후에, 연기와 가루뿐만 아니라 안전벨트와 에어백의 압박으로인해 숨을 쉬기 어려울 수 있습니다. 에어백이터지고 난 후에는 창문이나 도어를 열어 차 안을 환기하십시오. 연기와 가루는 무독성이지만피부에는 자극을 줄 수 있습니다. 피부가 가렵거나 따가운 경우 즉시 차가운 물로 닦고, 자극이 오랫동안 없어지지 않으면 의사와 상의하여치료하십시오.", "raw_text": "에어백이 부풀어 오를 때, 큰 소음과 차량 내부에 연기처럼 보이는 가루가 남겨집니다. 이는정상적인 현상으로 에어백이 팽창할 때 생기는결과입니다. 에어백이 작동한 후에, 연기와 가루뿐만 아니라 안전벨트와 에어백의 압박으로인해 숨을 쉬기 어려울 수 있습니다. 에어백이터지고 난 후에는 창문이나 도어를 열어 차 안을 환기하십시오. 연기와 가루는 무독성이지만피부에는 자극을 줄 수 있습니다. 피부가 가렵거나 따가운 경우 즉시 차가운 물로 닦고, 자극이 오랫동안 없어지지 않으면 의사와 상의하여치료하십시오.", "bbox": [235.79, 76.71, 398.97, 197.62], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansTextKR", "flags": [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4], "bold": false, "source_block_index": 8, "distance_pt": 102.13, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}]

### p.90 / image 3

- image bbox: `[220.79, 87.12, 385.66, 200.87]`; 선택 description: **적산 거리계 (ODO)**
- 선택 제목: `적산 거리계 (ODO)` | font size 10.0 pt (max 10.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4]` | bold 추정 `False`
- 제목 bbox: `[221.69, 63.51, 299.36, 75.73]` | 이미지 위 거리 11.39 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "A타입", "raw_text": "A타입", "bbox": [294.74, 77.0, 311.1, 85.5], "font_size": 7.0, "max_font_size": 7.0, "font": "HyundaiSansTextKR", "flags": [4], "bold": false, "source_block_index": 8, "distance_pt": 1.62, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}, {"text": "적산 거리계 (ODO)", "raw_text": "적산 거리계 (ODO)", "bbox": [221.69, 63.51, 299.36, 75.73], "font_size": 10.0, "max_font_size": 10.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 7, "distance_pt": 11.39, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}]

### p.103 / image 1

- image bbox: `[50.88, 87.12, 215.27, 191.99]`; 선택 description: **타이어 공기압이 낮습니다**
- 선택 제목: `타이어 공기압이 낮습니다` | font size 10.0 pt (max 10.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4]` | bold 추정 `False`
- 제목 bbox: `[51.61, 63.51, 154.77, 75.73]` | 이미지 위 거리 11.39 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "A타입", "raw_text": "A타입", "bbox": [124.66, 77.0, 141.02, 85.5], "font_size": 7.0, "max_font_size": 7.0, "font": "HyundaiSansTextKR", "flags": [4], "bold": false, "source_block_index": 3, "distance_pt": 1.62, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}, {"text": "타이어 공기압이 낮습니다", "raw_text": "타이어 공기압이 낮습니다", "bbox": [51.61, 63.51, 154.77, 75.73], "font_size": 10.0, "max_font_size": 10.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 2, "distance_pt": 11.39, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}]

### p.115 / image 2

- image bbox: `[235.19, 107.04, 399.58, 211.91]`; 선택 description: **도어 잠금 해제(2)(세이프티 언락 기능 설정 시)**
- 선택 제목: `도어 잠금 해제(2)(세이프티 언락 기능 설정 시)` | font size 10.0 pt (max 10.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4, 4]` | bold 추정 `False`
- 제목 bbox: `[235.86, 63.51, 396.53, 85.72]` | 이미지 위 거리 21.32 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "버튼 타입", "raw_text": "버튼 타입", "bbox": [235.15, 93.7, 272.3, 104.63], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansTextKR", "flags": [4], "bold": false, "source_block_index": 8, "distance_pt": 2.41, "same_column": true, "horizontal_overlap": 0.999, "heading_like": false}, {"text": "도어 잠금 해제(2)(세이프티 언락 기능 설정 시)", "raw_text": "도어 잠금 해제(2)(세이프티 언락 기능 설정 시)", "bbox": [235.86, 63.51, 396.53, 85.72], "font_size": 10.0, "max_font_size": 10.0, "font": "HyundaiSansTextKRMedium", "flags": [4, 4], "bold": false, "source_block_index": 7, "distance_pt": 21.32, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}, {"text": "5", "raw_text": "5", "bbox": [385.86, 16.11, 400.39, 46.77], "font_size": 26.0, "max_font_size": 26.0, "font": "HyundaiSansHeadKR", "flags": [4], "bold": false, "source_block_index": 0, "distance_pt": 60.27, "same_column": true, "horizontal_overlap": 0.944, "heading_like": false}]

### p.137 / image 2

- image bbox: `[235.19, 333.59, 399.58, 438.46]`; 선택 description: **비상시 도어 잠금 방법**
- 선택 제목: `비상시 도어 잠금 방법` | font size 10.0 pt (max 10.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4]` | bold 추정 `False`
- 제목 bbox: `[235.86, 320.1, 323.24, 332.32]` | 이미지 위 거리 1.27 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "비상시 도어 잠금 방법", "raw_text": "비상시 도어 잠금 방법", "bbox": [235.86, 320.1, 323.24, 332.32], "font_size": 10.0, "max_font_size": 10.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 16, "distance_pt": 1.27, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}, {"text": "가 잠긴 경우, 비상 키로 운전석 도어의 잠금을 해제 할 수 있습니다. 비상 키로 운전석 도어의 잠금을 해제하는 방법은 5장 내 ‘도어’를 참고하십시오.", "raw_text": "가 잠긴 경우, 비상 키로 운전석 도어의 잠금을 해제 할 수 있습니다. 비상 키로 운전석 도어의 잠금을 해제하는 방법은 5장 내 ‘도어’를 참고하십시오.", "bbox": [244.27, 260.49, 399.43, 301.42], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansTextKR", "flags": [4, 4, 4, 4], "bold": false, "source_block_index": 14, "distance_pt": 32.17, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}, {"text": "•차 안에 어린이나 동물이 있는 상태로 도어", "raw_text": "•차 안에 어린이나 동물이 있는 상태로 도어", "bbox": [235.16, 248.31, 398.98, 261.28], "font_size": 9.86, "max_font_size": 10.72, "font": "HyundaiSansHeadKR / HyundaiSansTextKR", "flags": [4, 4], "bold": false, "source_block_index": 14, "distance_pt": 72.31, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}, {"text": "트 키를 가지고 내리십시오. 또한 어린이나동물을 차 안에 혼자 남겨 두지 않도록 주의하십시오. 도어 잠금 버튼을 누르거나 기타장비를 잘못 조작하여 사고가 발생할 수 있습니다.", "raw_text": "트 키를 가지고 내리십시오. 또한 어린이나동물을 차 안에 혼자 남겨 두지 않도록 주의하십시오. 도어 잠금 버튼을 누르거나 기타장비를 잘못 조작하여 사고가 발생할 수 있습니다.", "bbox": [244.25, 195.52, 398.9, 246.45], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansTextKR", "flags": [4, 4, 4, 4, 4], "bold": false, "source_block_index": 14, "distance_pt": 87.14, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}]

### p.167 / image 1

- image bbox: `[50.88, 77.04, 215.27, 181.91]`; 선택 description: **파워 트렁크 열림/닫힘 버튼 (실내)**
- 선택 제목: `파워 트렁크 열림/닫힘 버튼 (실내)` | font size 10.0 pt (max 10.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4]` | bold 추정 `False`
- 제목 bbox: `[51.61, 63.51, 188.6, 75.73]` | 이미지 위 거리 1.31 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "파워 트렁크 열림/닫힘 버튼 (실내)", "raw_text": "파워 트렁크 열림/닫힘 버튼 (실내)", "bbox": [51.61, 63.51, 188.6, 75.73], "font_size": 10.0, "max_font_size": 10.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 2, "distance_pt": 1.31, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}]

### p.181 / image 1

- image bbox: `[50.88, 77.04, 215.27, 181.91]`; 선택 description: **SD 메모리**
- 선택 제목: `SD 메모리` | font size 10.0 pt (max 10.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4]` | bold 추정 `False`
- 제목 bbox: `[50.91, 63.51, 92.0, 75.73]` | 이미지 위 거리 1.31 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "SD 메모리", "raw_text": "SD 메모리", "bbox": [50.91, 63.51, 92.0, 75.73], "font_size": 10.0, "max_font_size": 10.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 2, "distance_pt": 1.31, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}]

### p.183 / image 1

- image bbox: `[50.88, 77.04, 215.27, 181.91]`; 선택 description: **수동 녹화**
- 선택 제목: `수동 녹화` | font size 10.0 pt (max 10.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4]` | bold 추정 `False`
- 제목 bbox: `[51.61, 63.51, 89.55, 75.73]` | 이미지 위 거리 1.31 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "수동 녹화", "raw_text": "수동 녹화", "bbox": [51.61, 63.51, 89.55, 75.73], "font_size": 10.0, "max_font_size": 10.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 2, "distance_pt": 1.31, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}]

### p.198 / image 3

- image bbox: `[221.03, 215.75, 385.42, 320.63]`; 선택 description: **하이빔 보조**
- 선택 제목: `하이빔 보조` | font size 10.0 pt (max 10.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4]` | bold 추정 `False`
- 제목 bbox: `[221.69, 202.16, 271.43, 214.38]` | 이미지 위 거리 1.37 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "하이빔 보조", "raw_text": "하이빔 보조 ", "bbox": [221.69, 202.16, 271.43, 214.38], "font_size": 10.0, "max_font_size": 10.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 16, "distance_pt": 1.37, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}, {"text": "하이빔 보조 설정", "raw_text": "하이빔 보조 설정", "bbox": [221.83, 171.86, 302.28, 186.53], "font_size": 12.0, "max_font_size": 12.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 15, "distance_pt": 29.22, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}, {"text": "을 참고하십시오.", "raw_text": "을 참고하십시오.", "bbox": [221.51, 137.56, 282.93, 148.49], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansTextKR", "flags": [4], "bold": false, "source_block_index": 13, "distance_pt": 67.26, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}, {"text": "하이빔 보조는 전방 카메라를 이용하는 기능으로 그 성능을 최적으로 유지하기 위해서는 전방카메라의 관리에 주의가 필요합니다.전방 카메라에 대한 자세한 주의 사항은 7장 내‘전방 충돌방지 보조 (FCA) (전방 카메라 단독)’", "raw_text": "하이빔 보조는 전방 카메라를 이용하는 기능으로 그 성능을 최적으로 유지하기 위해서는 전방카메라의 관리에 주의가 필요합니다. 전방 카메라에 대한 자세한 주의 사항은 7장 내‘전방 충돌방지 보조 (FCA) (전방 카메라 단독)’", "bbox": [221.62, 84.57, 385.29, 138.49], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansTextKR", "flags": [4, 4, 4, 4, 4], "bold": false, "source_block_index": 12, "distance_pt": 77.26, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}]

### p.199 / image 3

- image bbox: `[234.95, 172.79, 399.58, 277.91]`; 선택 description: **기능 이상**
- 선택 제목: `기능 이상` | font size 10.0 pt (max 10.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4]` | bold 추정 `False`
- 제목 bbox: `[235.86, 159.18, 273.8, 171.4]` | 이미지 위 거리 1.39 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "기능 이상", "raw_text": "기능 이상", "bbox": [235.86, 159.18, 273.8, 171.4], "font_size": 10.0, "max_font_size": 10.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 18, "distance_pt": 1.39, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}, {"text": "하이빔 보조 이상 및 제한 사항", "raw_text": "하이빔 보조 이상 및 제한 사항", "bbox": [236.0, 128.88, 378.44, 143.55], "font_size": 12.0, "max_font_size": 12.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 17, "distance_pt": 29.24, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}, {"text": "클러스터 사양 또는 테마에 따라 클러스터에 표시되는 이미지나 색상이 다를 수 있습니다.", "raw_text": "클러스터 사양 또는 테마에 따라 클러스터에 표시되는 이미지나 색상이 다를 수 있습니다.", "bbox": [235.79, 84.57, 398.95, 105.5], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansTextKR", "flags": [4, 4], "bold": false, "source_block_index": 15, "distance_pt": 67.29, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}, {"text": "ঌইفӝ", "raw_text": "ঌইفӝ", "bbox": [254.21, 69.39, 291.26, 80.64], "font_size": 11.0, "max_font_size": 11.0, "font": "HyundaiSansTextKRMedium-", "flags": [4], "bold": false, "source_block_index": 13, "distance_pt": 92.15, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}]

### p.206 / image 1

- image bbox: `[36.72, 107.28, 385.42, 253.91]`; 선택 description: **히터 및 에어컨 (수동 조절식)**
- 선택 제목: `히터 및 에어컨 (수동 조절식)` | font size 14.0 pt (max 14.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4]` | bold 추정 `False`
- 제목 bbox: `[37.72, 62.89, 198.33, 80.0]` | 이미지 위 거리 27.28 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "A타입", "raw_text": "A타입", "bbox": [202.61, 97.25, 218.97, 105.75], "font_size": 7.0, "max_font_size": 7.0, "font": "HyundaiSansTextKR", "flags": [4], "bold": false, "source_block_index": 3, "distance_pt": 1.53, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}, {"text": "히터 및 에어컨 (수동 조절식)", "raw_text": "히터 및 에어컨 (수동 조절식)", "bbox": [37.72, 62.89, 198.33, 80.0], "font_size": 14.0, "max_font_size": 14.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 2, "distance_pt": 27.28, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}, {"text": "편의 장치", "raw_text": "편의 장치", "bbox": [37.58, 27.73, 72.63, 38.93], "font_size": 9.5, "max_font_size": 9.5, "font": "HyundaiSansHeadKR", "flags": [4], "bold": false, "source_block_index": 0, "distance_pt": 68.35, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}]

### p.211 / image 5

- image bbox: `[235.19, 287.03, 399.58, 391.9]`; 선택 description: **풍량 조절**
- 선택 제목: `풍량 조절` | font size 10.0 pt (max 10.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4]` | bold 추정 `False`
- 제목 bbox: `[235.86, 273.42, 273.8, 285.64]` | 이미지 위 거리 1.39 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "풍량 조절", "raw_text": "풍량 조절", "bbox": [235.86, 273.42, 273.8, 285.64], "font_size": 10.0, "max_font_size": 10.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 23, "distance_pt": 1.39, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}, {"text": "실내 순환 버튼의 표시등이 켜진 상태에서 버튼을 눌러 표시등이 꺼지면 바깥 공기가 들어옵니다. 차 안을 환기할 때 사용하십시오.", "raw_text": "실내 순환 버튼의 표시등이 켜진 상태에서 버튼을 눌러 표시등이 꺼지면 바깥 공기가 들어옵니다. 차 안을 환기할 때 사용하십시오. ", "bbox": [235.79, 228.64, 399.0, 259.57], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansTextKR", "flags": [4, 4, 4], "bold": false, "source_block_index": 22, "distance_pt": 27.46, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}, {"text": "WL_AirconAirIntakeButton", "raw_text": "WL_AirconAirIntakeButton", "bbox": [235.16, 220.09, 305.51, 227.37], "font_size": 6.0, "max_font_size": 6.0, "font": "HyundaiSansTextKR", "flags": [4], "bold": false, "source_block_index": 21, "distance_pt": 59.66, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}]

### p.220 / image 4

- image bbox: `[221.03, 257.03, 385.42, 361.9]`; 선택 description: **풍량 조절**
- 선택 제목: `풍량 조절` | font size 10.0 pt (max 10.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4]` | bold 추정 `False`
- 제목 bbox: `[221.69, 243.54, 259.63, 255.76]` | 이미지 위 거리 1.27 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "풍량 조절", "raw_text": "풍량 조절", "bbox": [221.69, 243.54, 259.63, 255.76], "font_size": 10.0, "max_font_size": 10.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 23, "distance_pt": 1.27, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}, {"text": "실내 순환 버튼의 표시등이 켜진 상태에서 버튼을 눌러 표시등이 꺼지면 바깥 공기가 들어옵니다. 차 안을 환기할 때 사용하십시오.", "raw_text": "실내 순환 버튼의 표시등이 켜진 상태에서 버튼을 눌러 표시등이 꺼지면 바깥 공기가 들어옵니다. 차 안을 환기할 때 사용하십시오.", "bbox": [221.62, 198.76, 384.83, 229.69], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansTextKR", "flags": [4, 4, 4], "bold": false, "source_block_index": 22, "distance_pt": 27.34, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}, {"text": "WL_AirconAirIntakeButton", "raw_text": "WL_AirconAirIntakeButton", "bbox": [220.98, 190.21, 291.34, 197.49], "font_size": 6.0, "max_font_size": 6.0, "font": "HyundaiSansTextKR", "flags": [4], "bold": false, "source_block_index": 21, "distance_pt": 59.54, "same_column": true, "horizontal_overlap": 0.999, "heading_like": false}, {"text": "외기 유입", "raw_text": "외기 유입", "bbox": [220.97, 134.39, 257.88, 145.32], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansTextKR", "flags": [4], "bold": false, "source_block_index": 20, "distance_pt": 111.71, "same_column": true, "horizontal_overlap": 0.998, "heading_like": false}]

### p.224 / image 1

- image bbox: `[221.03, 149.99, 385.42, 254.87]`; 선택 description: **에어컨 냉매 및 압축기 윤활유량 점검**
- 선택 제목: `에어컨 냉매 및 압축기 윤활유량 점검` | font size 12.0 pt (max 12.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4, 4]` | bold 추정 `False`
- 제목 bbox: `[221.83, 63.2, 384.55, 92.85]` | 이미지 위 거리 57.14 pt | 수평 overlap 1.0 | 탐색 반경 72 pt
- 주변 위쪽 후보: [{"text": "냉매량이 부족하면 에어컨의 성능이 저하됩니다. 또한 충전을 지나치게 하는 것도 에어컨에좋지 않은 영향을 주므로 이상이 발견되면 당사직영 하이테크센터나 블루핸즈에서 점검을 받으십시오.", "raw_text": "냉매량이 부족하면 에어컨의 성능이 저하됩니다. 또한 충전을 지나치게 하는 것도 에어컨에좋지 않은 영향을 주므로 이상이 발견되면 당사직영 하이테크센터나 블루핸즈에서 점검을 받으십시오.", "bbox": [221.62, 96.7, 384.77, 147.62], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansTextKR", "flags": [4, 4, 4, 4, 4], "bold": false, "source_block_index": 18, "distance_pt": 2.37, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}, {"text": "에어컨 냉매 및 압축기 윤활유량 점검", "raw_text": "에어컨 냉매 및 압축기 윤활유량 점검", "bbox": [221.83, 63.2, 384.55, 92.85], "font_size": 12.0, "max_font_size": 12.0, "font": "HyundaiSansTextKRMedium", "flags": [4, 4], "bold": false, "source_block_index": 17, "distance_pt": 57.14, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}]

### p.228 / image 1

- image bbox: `[36.72, 77.04, 201.11, 181.91]`; 선택 description: **실외 측 유리 성에 제거 방법**
- 선택 제목: `실외 측 유리 성에 제거 방법` | font size 10.0 pt (max 10.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4]` | bold 추정 `False`
- 제목 bbox: `[37.44, 63.51, 147.02, 75.73]` | 이미지 위 거리 1.31 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "실외 측 유리 성에 제거 방법", "raw_text": "실외 측 유리 성에 제거 방법", "bbox": [37.44, 63.51, 147.02, 75.73], "font_size": 10.0, "max_font_size": 10.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 2, "distance_pt": 1.31, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}, {"text": "편의 장치", "raw_text": "편의 장치", "bbox": [37.58, 27.73, 72.63, 38.93], "font_size": 9.5, "max_font_size": 9.5, "font": "HyundaiSansHeadKR", "flags": [4], "bold": false, "source_block_index": 0, "distance_pt": 38.11, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}]

### p.229 / image 1

- image bbox: `[50.88, 82.08, 215.27, 186.95]`; 선택 description: **뒷유리 서리 제거 (열선)**
- 선택 제목: `뒷유리 서리 제거 (열선)` | font size 12.0 pt (max 12.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4]` | bold 추정 `False`
- 제목 bbox: `[51.75, 63.2, 165.15, 77.86]` | 이미지 위 거리 4.22 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "뒷유리 서리 제거 (열선)", "raw_text": "뒷유리 서리 제거 (열선)", "bbox": [51.75, 63.2, 165.15, 77.86], "font_size": 12.0, "max_font_size": 12.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 2, "distance_pt": 4.22, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}]

### p.230 / image 1

- image bbox: `[36.72, 255.83, 201.11, 360.7]`; 선택 description: **오토 디포그 (자동 김 서림 제거 기능)**
- 선택 제목: `오토 디포그 (자동 김 서림 제거 기능)` | font size 12.0 pt (max 12.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4, 4]` | bold 추정 `False`
- 제목 bbox: `[37.58, 210.84, 197.4, 240.5]` | 이미지 위 거리 15.33 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "오토 디포그 (자동 김 서림 제거 기능)", "raw_text": "오토 디포그 (자동 김 서림 제거 기능)", "bbox": [37.58, 210.84, 197.4, 240.5], "font_size": 12.0, "max_font_size": 12.0, "font": "HyundaiSansTextKRMedium", "flags": [4, 4], "bold": false, "source_block_index": 5, "distance_pt": 15.33, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}, {"text": "이 활성화되어 있습니다. 기능을 사용하지않으시려면 인포테인먼트 시스템의 설정 메뉴에서 기능을 설정하십시오.", "raw_text": "이 활성화되어 있습니다. 기능을 사용하지않으시려면 인포테인먼트 시스템의 설정 메뉴에서 기능을 설정하십시오.", "bbox": [45.83, 156.54, 200.43, 187.46], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansTextKR", "flags": [4, 4, 4], "bold": false, "source_block_index": 3, "distance_pt": 68.37, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}, {"text": "•에어컨 자동 건조 기능은 초기 출고 시 기능", "raw_text": "•에어컨 자동 건조 기능은 초기 출고 시 기능", "bbox": [36.73, 144.36, 200.53, 157.33], "font_size": 9.86, "max_font_size": 10.72, "font": "HyundaiSansHeadKR / HyundaiSansTextKR", "flags": [4, 4], "bold": false, "source_block_index": 3, "distance_pt": 98.5, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}]

### p.304 / image 1

- image bbox: `[36.72, 218.15, 201.11, 323.03]`; 선택 description: **전방 충돌방지 보조 (FCA) (전방 카메라 단독)**
- 선택 제목: `전방 충돌방지 보조 (FCA) (전방 카메라 단독)` | font size 14.0 pt (max 14.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4, 4]` | bold 추정 `False`
- 제목 bbox: `[37.72, 151.87, 200.17, 187.97]` | 이미지 위 거리 30.18 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "기본 기능", "raw_text": "기본 기능", "bbox": [37.36, 205.01, 71.59, 215.62], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansHeadKR", "flags": [4], "bold": false, "source_block_index": 5, "distance_pt": 2.53, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}, {"text": "전방 충돌방지 보조 (FCA) (전방 카메라 단독)", "raw_text": "전방 충돌방지 보조 (FCA) (전방 카메라 단독)", "bbox": [37.72, 151.87, 200.17, 187.97], "font_size": 14.0, "max_font_size": 14.0, "font": "HyundaiSansTextKRMedium", "flags": [4, 4], "bold": false, "source_block_index": 4, "distance_pt": 30.18, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}, {"text": "인포테인먼트 소프트웨어 업데이트로 인해 운전자 보조 시스템의 각 기능의 설명이 취급설명서와 다를 수 있습니다. 이 경우 인포테인먼트시스템 웹 매뉴얼을 참고하십시오.", "raw_text": "인포테인먼트 소프트웨어 업데이트로 인해 운전자 보조 시스템의 각 기능의 설명이 취급설명서와 다를 수 있습니다. 이 경우 인포테인먼트시스템 웹 매뉴얼을 참고하십시오.", "bbox": [37.37, 83.71, 200.52, 124.63], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansTextKR", "flags": [4, 4, 4, 4], "bold": false, "source_block_index": 3, "distance_pt": 93.52, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}]

### p.308 / image 1

- image bbox: `[220.79, 121.91, 385.42, 227.03]`; 선택 description: **기능 이상**
- 선택 제목: `기능 이상` | font size 10.0 pt (max 10.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4]` | bold 추정 `False`
- 제목 bbox: `[221.69, 108.49, 259.63, 120.71]` | 이미지 위 거리 1.2 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "기능 이상", "raw_text": "기능 이상", "bbox": [221.69, 108.49, 259.63, 120.71], "font_size": 10.0, "max_font_size": 10.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 15, "distance_pt": 1.2, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}, {"text": "전방 충돌방지 보조 이상 및 제한 사항", "raw_text": "전방 충돌방지 보조 이상 및 제한 사항", "bbox": [221.83, 63.2, 384.57, 92.85], "font_size": 12.0, "max_font_size": 12.0, "font": "HyundaiSansTextKRMedium", "flags": [4, 4], "bold": false, "source_block_index": 14, "distance_pt": 29.06, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}]

### p.328 / image 1

- image bbox: `[36.72, 107.04, 201.11, 211.91]`; 선택 description: **기능 켜기 및 끄기**
- 선택 제목: `기능 켜기 및 끄기` | font size 10.0 pt (max 10.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4]` | bold 추정 `False`
- 제목 bbox: `[37.44, 93.5, 106.82, 105.72]` | 이미지 위 거리 1.32 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "기능 켜기 및 끄기", "raw_text": "기능 켜기 및 끄기", "bbox": [37.44, 93.5, 106.82, 105.72], "font_size": 10.0, "max_font_size": 10.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 3, "distance_pt": 1.32, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}, {"text": "차로 이탈방지 보조 작동", "raw_text": "차로 이탈방지 보조 작동", "bbox": [37.58, 63.2, 153.09, 77.86], "font_size": 12.0, "max_font_size": 12.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 2, "distance_pt": 29.18, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}, {"text": "운전자 보조", "raw_text": "운전자 보조", "bbox": [37.58, 27.73, 80.79, 38.93], "font_size": 9.5, "max_font_size": 9.5, "font": "HyundaiSansHeadKR", "flags": [4], "bold": false, "source_block_index": 0, "distance_pt": 68.11, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}]

### p.343 / image 1

- image bbox: `[50.88, 107.04, 215.51, 212.15]`; 선택 description: **기능 이상**
- 선택 제목: `기능 이상` | font size 10.0 pt (max 10.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4]` | bold 추정 `False`
- 제목 bbox: `[51.61, 93.5, 89.55, 105.72]` | 이미지 위 거리 1.32 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "기능 이상", "raw_text": "기능 이상", "bbox": [51.61, 93.5, 89.55, 105.72], "font_size": 10.0, "max_font_size": 10.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 3, "distance_pt": 1.32, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}, {"text": "안전 하차 보조 이상 및 제한 사항", "raw_text": "안전 하차 보조 이상 및 제한 사항", "bbox": [51.75, 63.2, 207.65, 77.86], "font_size": 12.0, "max_font_size": 12.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 2, "distance_pt": 29.18, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}]

### p.344 / image 1

- image bbox: `[221.03, 84.0, 385.42, 188.87]`; 선택 description: **수동 속도 제한 보조 (MSLA)**
- 선택 제목: `수동 속도 제한 보조 (MSLA)` | font size 14.0 pt (max 14.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4]` | bold 추정 `False`
- 제목 bbox: `[221.97, 62.89, 381.01, 80.0]` | 이미지 위 거리 4.0 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "수동 속도 제한 보조 (MSLA)", "raw_text": "수동 속도 제한 보조 (MSLA)", "bbox": [221.97, 62.89, 381.01, 80.0], "font_size": 14.0, "max_font_size": 14.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 10, "distance_pt": 4.0, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}]

### p.358 / image 3

- image bbox: `[221.03, 295.67, 385.42, 400.54]`; 선택 description: **일시 해제하기**
- 선택 제목: `일시 해제하기` | font size 12.0 pt (max 12.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4]` | bold 추정 `False`
- 제목 bbox: `[221.83, 228.84, 288.81, 243.5]` | 이미지 위 거리 52.17 pt | 수평 overlap 1.0 | 탐색 반경 72 pt
- 주변 위쪽 후보: [{"text": "수동", "raw_text": "수동", "bbox": [221.69, 282.13, 239.29, 294.35], "font_size": 10.0, "max_font_size": 10.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 18, "distance_pt": 1.32, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}, {"text": "크루즈 컨트롤 작동을 일시적으로 해제할 수 있습니다.", "raw_text": "크루즈 컨트롤 작동을 일시적으로 해제할 수 있습니다. ", "bbox": [221.62, 247.35, 384.77, 268.27], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansTextKR", "flags": [4, 4], "bold": false, "source_block_index": 17, "distance_pt": 27.4, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}, {"text": "일시 해제하기", "raw_text": "일시 해제하기", "bbox": [221.83, 228.84, 288.81, 243.5], "font_size": 12.0, "max_font_size": 12.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 16, "distance_pt": 52.17, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}, {"text": "내리면 크루즈 컨트롤의 설정속도가 현재 클러스터의 속도로 설정됩니다.", "raw_text": "내리면 크루즈 컨트롤의 설정속도가 현재 클러스터의 속도로 설정됩니다.", "bbox": [221.6, 184.53, 384.78, 205.46], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansTextKR", "flags": [4, 4], "bold": false, "source_block_index": 14, "distance_pt": 90.21, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}, {"text": "+ 스위치를 위로 올리거나 – 스위치를 아래로", "raw_text": "+ 스위치를 위로 올리거나 – 스위치를 아래로", "bbox": [220.98, 174.54, 384.87, 185.46], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansHeadKR / HyundaiSansTextKR", "flags": [4, 4, 4, 4], "bold": false, "source_block_index": 13, "distance_pt": 110.21, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}]

### p.359 / image 2

- image bbox: `[50.88, 335.75, 215.27, 440.62]`; 선택 description: **일시 해제 후 다시 켜기**
- 선택 제목: `일시 해제 후 다시 켜기` | font size 12.0 pt (max 12.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4]` | bold 추정 `False`
- 제목 bbox: `[51.75, 316.8, 159.13, 331.47]` | 이미지 위 거리 4.28 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "일시 해제 후 다시 켜기", "raw_text": "일시 해제 후 다시 켜기", "bbox": [51.75, 316.8, 159.13, 331.47], "font_size": 12.0, "max_font_size": 12.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 7, "distance_pt": 4.28, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}, {"text": "위의 상황 이외에 크루즈 컨트롤이 자동으로 일시 해제된 경우에는 당사 직영 하이테크센터나블루핸즈에서 점검을 받으십시오.", "raw_text": "위의 상황 이외에 크루즈 컨트롤이 자동으로 일시 해제된 경우에는 당사 직영 하이테크센터나블루핸즈에서 점검을 받으십시오.", "bbox": [51.54, 262.5, 214.69, 293.42], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansTextKR", "flags": [4, 4, 4], "bold": false, "source_block_index": 5, "distance_pt": 42.33, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}, {"text": "઱੄", "raw_text": "઱੄", "bbox": [70.23, 246.87, 89.15, 258.12], "font_size": 11.0, "max_font_size": 11.0, "font": "HyundaiSansTextKRMedium-", "flags": [4], "bold": false, "source_block_index": 3, "distance_pt": 77.63, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}, {"text": "클러스터의 설정속도가 회색으로 표시되고 크루즈 컨트롤이 일시적으로 해제됩니다.크루즈 표시등(", "raw_text": "클러스터의 설정속도가 회색으로 표시되고 크루즈 컨트롤이 일시적으로 해제됩니다.크루즈 표시등(", "bbox": [51.51, 199.66, 214.63, 233.58], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansTextKR", "flags": [4, 4, 4], "bold": false, "source_block_index": 2, "distance_pt": 102.17, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}, {"text": ")은 계속 켜져 있습니다.", "raw_text": ")은 계속 켜져 있습니다.", "bbox": [131.84, 222.65, 215.21, 233.58], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansTextKR", "flags": [4], "bold": false, "source_block_index": 2, "distance_pt": 102.17, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}]

### p.365 / image 3

- image bbox: `[235.19, 219.59, 399.58, 324.47]`; 선택 description: **일시적 가속**
- 선택 제목: `일시적 가속` | font size 10.0 pt (max 10.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4]` | bold 추정 `False`
- 제목 bbox: `[235.86, 206.15, 282.56, 218.37]` | 이미지 위 거리 1.22 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "일시적 가속", "raw_text": "일시적 가속", "bbox": [235.86, 206.15, 282.56, 218.37], "font_size": 10.0, "max_font_size": 10.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 11, "distance_pt": 1.22, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}, {"text": "표시창에 표시되는 이미지나 색상이 다를 수있습니다.", "raw_text": "표시창에 표시되는 이미지나 색상이 다를 수있습니다.", "bbox": [244.27, 166.53, 398.89, 187.46], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansTextKR", "flags": [4, 4], "bold": false, "source_block_index": 9, "distance_pt": 32.13, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}, {"text": "•클러스터 사양 또는 테마에 따라 클러스터", "raw_text": "•클러스터 사양 또는 테마에 따라 클러스터", "bbox": [235.16, 154.36, 398.86, 167.32], "font_size": 9.86, "max_font_size": 10.72, "font": "HyundaiSansHeadKR / HyundaiSansTextKR", "flags": [4, 4], "bold": false, "source_block_index": 9, "distance_pt": 52.27, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}, {"text": "거리 단계에 따라 달라집니다. 속도가 낮은경우 차간거리 단계를 변경하더라도 목표 차간거리의 변경량이 적을 수 있습니다.", "raw_text": "거리 단계에 따라 달라집니다. 속도가 낮은경우 차간거리 단계를 변경하더라도 목표 차간거리의 변경량이 적을 수 있습니다.", "bbox": [244.27, 121.56, 398.96, 152.48], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansTextKR", "flags": [4, 4, 4], "bold": false, "source_block_index": 9, "distance_pt": 67.11, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}, {"text": "•목표 차간거리는 차량의 속도와 설정된 차간", "raw_text": "•목표 차간거리는 차량의 속도와 설정된 차간", "bbox": [235.16, 109.38, 398.98, 122.35], "font_size": 9.86, "max_font_size": 10.72, "font": "HyundaiSansHeadKR / HyundaiSansTextKR", "flags": [4, 4], "bold": false, "source_block_index": 9, "distance_pt": 97.24, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}]

### p.366 / image 1

- image bbox: `[36.72, 77.04, 201.11, 181.91]`; 선택 description: **자동 일시 해제**
- 선택 제목: `자동 일시 해제` | font size 10.0 pt (max 10.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4]` | bold 추정 `False`
- 제목 bbox: `[37.44, 63.51, 95.36, 75.73]` | 이미지 위 거리 1.31 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "자동 일시 해제", "raw_text": "자동 일시 해제", "bbox": [37.44, 63.51, 95.36, 75.73], "font_size": 10.0, "max_font_size": 10.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 2, "distance_pt": 1.31, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}, {"text": "운전자 보조", "raw_text": "운전자 보조", "bbox": [37.58, 27.73, 80.79, 38.93], "font_size": 9.5, "max_font_size": 9.5, "font": "HyundaiSansHeadKR", "flags": [4], "bold": false, "source_block_index": 0, "distance_pt": 38.11, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}]

### p.378 / image 4

- image bbox: `[36.72, 320.39, 201.11, 425.26]`; 선택 description: **기능 경고 및 제어**
- 선택 제목: `기능 경고 및 제어` | font size 10.0 pt (max 10.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4]` | bold 추정 `False`
- 제목 bbox: `[37.44, 286.85, 106.82, 299.07]` | 이미지 위 거리 21.32 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "차로 유지 보조", "raw_text": "차로 유지 보조", "bbox": [36.72, 307.05, 92.2, 317.98], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansTextKR", "flags": [4], "bold": false, "source_block_index": 6, "distance_pt": 2.41, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}, {"text": "기능 경고 및 제어", "raw_text": "기능 경고 및 제어", "bbox": [37.44, 286.85, 106.82, 299.07], "font_size": 10.0, "max_font_size": 10.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 5, "distance_pt": 21.32, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}, {"text": ")을 누르십시오. 차로 유지 보조가 켜지고 클러스터에 표시등()이 회색 또는 초록색으로 표시됩니다. 차로 유지 보조를 끄려면 차로 주행보조 버튼을 다시 누르십시오.", "raw_text": ")을 누르십시오. 차로 유지 보조가 켜지고 클러스터에 표시등()이 회색 또는 초록색으로 표시됩니다. 차로 유지 보조를 끄려면 차로 주행보조 버튼을 다시 누르십시오. ", "bbox": [198.22, 222.08, 201.13, 273.0], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansTextKR", "flags": [4, 4, 4, 4, 4, 4], "bold": false, "source_block_index": 4, "distance_pt": 47.39, "same_column": true, "horizontal_overlap": 0.993, "heading_like": false}, {"text": "시동 ‘ON’ 상태에서 차로 주행 보조 버튼(", "raw_text": "시동 ‘ON’ 상태에서 차로 주행 보조 버튼(", "bbox": [37.37, 222.08, 186.22, 233.01], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansTextKR", "flags": [4], "bold": false, "source_block_index": 4, "distance_pt": 87.38, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}]

### p.389 / image 3

- image bbox: `[234.95, 270.47, 399.82, 375.58]`; 선택 description: **서라운드 뷰 모니터 자동 켜짐**
- 선택 제목: `서라운드 뷰 모니터 자동 켜짐` | font size 10.0 pt (max 10.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4]` | bold 추정 `False`
- 제목 bbox: `[235.86, 256.84, 355.26, 269.06]` | 이미지 위 거리 1.41 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "서라운드 뷰 모니터 자동 켜짐", "raw_text": "서라운드 뷰 모니터 자동 켜짐 ", "bbox": [235.86, 256.84, 355.26, 269.06], "font_size": 10.0, "max_font_size": 10.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 19, "distance_pt": 1.41, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}, {"text": "후방 뷰 주차 가이드의 가로 가이드라인은 차량으로부터 약 0.5 m, 1 m, 2.3 m 거리를 나타냅니다.", "raw_text": "후방 뷰 주차 가이드의 가로 가이드라인은 차량으로부터 약 0.5 m, 1 m, 2.3 m 거리를 나타냅니다.", "bbox": [235.79, 207.23, 399.05, 238.15], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansTextKR", "flags": [4, 4, 4], "bold": false, "source_block_index": 17, "distance_pt": 32.32, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}, {"text": "ঌইفӝ", "raw_text": "ঌইفӝ", "bbox": [254.21, 192.05, 291.26, 203.3], "font_size": 11.0, "max_font_size": 11.0, "font": "HyundaiSansTextKRMedium-", "flags": [4], "bold": false, "source_block_index": 15, "distance_pt": 67.17, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}, {"text": "후방 주차 가이드라인표시 정보의 후방 주차 가이드라인이 선택되어있는 경우, 좌측 영상에 후방 주차 가이드라인이 표시됩니다.", "raw_text": "후방 주차 가이드라인표시 정보의 후방 주차 가이드라인이 선택되어있는 경우, 좌측 영상에 후방 주차 가이드라인이 표시됩니다.", "bbox": [235.15, 134.39, 398.93, 178.31], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansTextKR / HyundaiSansHeadKR", "flags": [4, 4, 4, 4, 4, 4, 4], "bold": false, "source_block_index": 14, "distance_pt": 92.16, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}]

### p.390 / image 1

- image bbox: `[36.72, 107.04, 201.11, 211.91]`; 선택 description: **주차/뷰 버튼**
- 선택 제목: `주차/뷰 버튼` | font size 10.0 pt (max 10.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4]` | bold 추정 `False`
- 제목 bbox: `[37.44, 93.5, 88.41, 105.72]` | 이미지 위 거리 1.32 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "주차/뷰 버튼", "raw_text": "주차/뷰 버튼", "bbox": [37.44, 93.5, 88.41, 105.72], "font_size": 10.0, "max_font_size": 10.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 3, "distance_pt": 1.32, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}, {"text": "서라운드 뷰 모니터 작동", "raw_text": "서라운드 뷰 모니터 작동", "bbox": [37.58, 63.2, 153.09, 77.86], "font_size": 12.0, "max_font_size": 12.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 2, "distance_pt": 29.18, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}, {"text": "운전자 보조", "raw_text": "운전자 보조", "bbox": [37.58, 27.73, 80.79, 38.93], "font_size": 9.5, "max_font_size": 9.5, "font": "HyundaiSansHeadKR", "flags": [4], "bold": false, "source_block_index": 0, "distance_pt": 68.11, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}]

### p.401 / image 1

- image bbox: `[50.88, 107.04, 215.27, 211.91]`; 선택 description: **경고 방식**
- 선택 제목: `경고 방식` | font size 10.0 pt (max 10.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4]` | bold 추정 `False`
- 제목 bbox: `[51.61, 93.5, 89.55, 105.72]` | 이미지 위 거리 1.32 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "경고 방식", "raw_text": "경고 방식", "bbox": [51.61, 93.5, 89.55, 105.72], "font_size": 10.0, "max_font_size": 10.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 3, "distance_pt": 1.32, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}, {"text": "전방/후방 주차 거리 경고 설정", "raw_text": "전방/후방 주차 거리 경고 설정", "bbox": [51.75, 63.2, 196.65, 77.86], "font_size": 12.0, "max_font_size": 12.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 2, "distance_pt": 29.18, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}]

### p.407 / image 8

- image bbox: `[234.95, 358.54, 399.58, 463.66]`; 선택 description: **인식 센서 가림**
- 선택 제목: `인식 센서 가림` | font size 10.0 pt (max 10.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4]` | bold 추정 `False`
- 제목 bbox: `[235.86, 345.06, 294.02, 357.28]` | 이미지 위 거리 1.26 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "인식 센서 가림", "raw_text": "인식 센서 가림", "bbox": [235.86, 345.06, 294.02, 357.28], "font_size": 10.0, "max_font_size": 10.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 13, "distance_pt": 1.26, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}, {"text": "리티 정보 뷰의 서비스 메시지에서 확인할수 있습니다.", "raw_text": "리티 정보 뷰의 서비스 메시지에서 확인할수 있습니다.", "bbox": [252.75, 310.28, 398.98, 331.21], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansTextKR", "flags": [4, 4], "bold": false, "source_block_index": 12, "distance_pt": 27.33, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}, {"text": "스템 점검 경고 표시-경고 내용은 클러스터의 뷰 모드 중 유틸", "raw_text": "스템 점검 경고 표시-경고 내용은 클러스터의 뷰 모드 중 유틸", "bbox": [244.27, 287.29, 398.95, 311.21], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansTextKR", "flags": [4, 4, 4], "bold": false, "source_block_index": 11, "distance_pt": 47.33, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}, {"text": "•기능에 이상이 있으면 클러스터 표시창에 시", "raw_text": "•기능에 이상이 있으면 클러스터 표시창에 시", "bbox": [235.16, 275.11, 398.92, 288.08], "font_size": 9.86, "max_font_size": 10.72, "font": "HyundaiSansHeadKR / HyundaiSansTextKR", "flags": [4, 4], "bold": false, "source_block_index": 11, "distance_pt": 70.46, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}, {"text": "다음과 같은 현상이 나타나면 초음파센서가 손상되었는지, 외부 물체에 의해 가려졌는지 등을 먼저 확인하십시오. 기능에 이상이 있는 것으로 판단되면 당사 직영 하이테크센터나 블루핸즈에서 점검을 받으십시오.", "raw_text": "다음과 같은 현상이 나타나면 초음파센서가 손상되었는지, 외부 물체에 의해 가려졌는지 등을 먼저 확인하십시오. 기능에 이상이 있는 것으로 판단되면 당사 직영 하이테크센터나 블루핸즈에서 점검을 받으십시오.", "bbox": [235.79, 222.32, 398.92, 273.24], "font_size": 9.0, "max_font_size": 9.0, "font": "HyundaiSansTextKR", "flags": [4, 4, 4, 4, 4], "bold": false, "source_block_index": 11, "distance_pt": 85.3, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}]

### p.424 / image 2

- image bbox: `[36.72, 291.35, 201.11, 410.38]`; 선택 description: **후측방 레이더**
- 선택 제목: `후측방 레이더` | font size 12.0 pt (max 12.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4]` | bold 추정 `False`
- 제목 bbox: `[37.58, 261.2, 104.56, 275.87]` | 이미지 위 거리 15.48 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "후측방 레이더", "raw_text": "후측방 레이더", "bbox": [37.58, 261.2, 104.56, 275.87], "font_size": 12.0, "max_font_size": 12.0, "font": "HyundaiSansTextKRMedium", "flags": [4], "bold": false, "source_block_index": 5, "distance_pt": 15.48, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}]

### p.490 / image 4

- image bbox: `[221.03, 96.96, 385.42, 201.83]`; 선택 description: **선바이저 램프/글로브 박스 램프/트렁크룸 램프(벌브 타입)**
- 선택 제목: `선바이저 램프/글로브 박스 램프/트렁크룸 램프(벌브 타입)` | font size 10.0 pt (max 10.0 pt) | font `HyundaiSansTextKRMedium` | flags `[4, 4]` | bold 추정 `False`
- 제목 bbox: `[221.69, 63.51, 383.41, 85.72]` | 이미지 위 거리 11.24 pt | 수평 overlap 1.0 | 탐색 반경 36 pt
- 주변 위쪽 후보: [{"text": "선바이저 램프", "raw_text": "선바이저 램프", "bbox": [283.61, 87.0, 322.95, 95.5], "font_size": 7.0, "max_font_size": 7.0, "font": "HyundaiSansTextKR", "flags": [4], "bold": false, "source_block_index": 9, "distance_pt": 1.46, "same_column": true, "horizontal_overlap": 1.0, "heading_like": false}, {"text": "선바이저 램프/글로브 박스 램프/트렁크룸 램프(벌브 타입)", "raw_text": "선바이저 램프/글로브 박스 램프/트렁크 룸 램프(벌브 타입)", "bbox": [221.69, 63.51, 383.41, 85.72], "font_size": 10.0, "max_font_size": 10.0, "font": "HyundaiSansTextKRMedium", "flags": [4, 4], "bold": false, "source_block_index": 8, "distance_pt": 11.24, "same_column": true, "horizontal_overlap": 1.0, "heading_like": true}]

## 제목을 찾지 못한 사례

None 65건. None 중 표본 전체에 고르게 뽑은 15건의 contact sheet를 시각 검토했다. 여기서 p.44/i2 `등받이 각도 조절하기`, p.263/i1 `수동 변속 (+, -) 모드`, p.307/i1 `긴급 제동`처럼 제목처럼 보이지만 본문과 같은 9pt 스타일인 사례 3건을 확인했다. 따라서 이 3건은 font/스타일 선택 기준의 false negative다. 65개 None 전체를 육안 판정하지 않았으므로 전체 제목 누락 수는 미확정이다.
- 개별 None 행의 가까운 위쪽 text 후보 및 span font/bbox/거리도 JSON에 기록했다.

## 대표 사례 15개

성공 사례 35건 전체의 page/image, image bbox, 위쪽 후보 text/font size/bbox/거리, 선택 결과와 이유는 바로 아래 개별 사례 목록에 있다. 그중 p.25/i3, p.32/i2, p.69/i1, p.103/i1, p.115/i2, p.137/i2, p.167/i1, p.198/i3, p.206/i1, p.224/i1, p.229/i1, p.304/i1, p.328/i1, p.359/i2, p.424/i2를 대표 15건으로 검토했다. p.424/i2는 `후측방 레이더`로 해당 주제에는 맞지만 인증 표시 이미지 자체 설명으로는 넓은 제목이다.

## 기존 방식과 비교

| 방식 | 설명 생성 | 정확해 보이는 결과 | 잘림/혼입/정보 손실 | LLM/API | 복잡도 |
|---|---:|---|---|---|---|
| A. 규칙 기반 nearby candidate | 57/100 | 전체 이미지 의미의 정확성은 미확정 | 기존 dry-run에서 문장 조각 최소 2건 확인(p.25/i3, p.32/i2); 오연결 전체 수 미확정 | 불필요 | 중간 |
| B. expanded context + Terra | 최종값 57/100(44개 LLM 채택, 13개 candidate fallback) | 변경 36건 중 수동 검토상 25 개선, 7 경미/무의미 | p.69 문맥 혼입 관찰; 정보 손실 우려 4건; input-context 미근거 제안은 fallback | 필요 | 높음 |
| C. 상단 제목 extraction | 제목 35/100, None 65 | 생성 35건 시각 검토: 34건 제목이 대상 이미지/기능과 정합, 1건은 상위·넓은 제목(p.424/i2) | 15개 None 표본에서 제목 누락 3건 확인; 선정 35건 중 다른 section 0, 작은 타입 라벨 오선택 0, p.115 줄바꿈 조각은 결합해 해소 | 불필요 | 중간 |
비교의 정확도 기준은 동일하지 않다. A는 기존 규칙 후보의 정적 점검, B는 문구 변경에 대한 수동 판정, C는 이미지 crop과 추출 제목의 시각 대조다. A/B 전체의 ‘정확해 보이는 건수’나 C의 모든 None 누락 수를 실제로 확인하지 않은 상태에서 숫자로 채우지 않았다.

## 해석

C는 전체 100건 중 35건만 설명으로 채택하고 나머지를 보류하는 보수적인 방식이다. 강한 제목이 있는 이미지에서는 LLM 없이 원문 제목을 그대로 사용할 수 있었고, 다른 이미지 소유 block을 함께 요약하는 확장 문맥의 혼입도 피했다. 다만 본문과 같은 9pt 크기의 독립 제목을 놓치는 사례가 확인됐고, 일부 이미지에는 인증/주의 등 더 좁은 제목 단위가 필요하다. 따라서 이번 결과는 제목 extraction의 유용성을 보여주지만, 100건 전체의 제목 누락과 정합성 검증을 끝낸 결과는 아니다.

## 파일

- 원시 결과: `src/car_search_rag/car_search/docs/IMAGE_DESC_HEADING_100.json`
