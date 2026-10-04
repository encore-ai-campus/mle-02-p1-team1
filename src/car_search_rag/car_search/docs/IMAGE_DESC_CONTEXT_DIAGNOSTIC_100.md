# Sonata image_desc 입력 문맥 진단 및 확대 실험

- 표본: seed 20261004, 100개 중 description 후보가 있는 57개만 비교 대상으로 삼음.
- 모델: `gpt-5.6-terra`; A는 기존 실행 결과, B는 확대 문맥 실험. DB/Storage/production 경로는 호출하지 않음.
- PDF text block 길이 분포(57개 대상 페이지): p50=33, p90=175, p95=244자.
- B 문맥 상한: 600자 / 이미지당 최대 10 blocks / 동일 column 최대 수직 간격 240pt. 문장 전체를 무제한 포함하지 않고 한 페이지 인접 문맥의 p95를 넘지 않도록 제한.
- 확장 선택 순서: 같은 열의 바로 위/아래, 가까운 제목 후보, 이후 거리순. 다른 이미지 쪽 block은 제외.

## A/B 요약

| 지표 | A 기존 context + validator | B 확장 context + source-grounded validator |
|---|---:|---:|
| None skip | 43 | 43 |
| LLM 대상 | 57 | 57 |
| 평균 context 글자수 | 158.8 | 181.5 |
| 평균 API input tokens/대상 (context+prompt+JSON) | 194.7 | 207.5 |
| 정적 검사 통과 | 39 | 44 |
| fallback | 18 | 13 |
| candidate와 동일 | 30 | 8 |
| 실제 문구 변경 | 9 | 36 |
| 명확한 개선 | 3 (이전 수동 판정) | 수동 검토 필요 |
| 의미 없는 변경 | 6 (이전 수동 판정) | 수동 검토 필요 |
| 잘못된 설명 | 미측정; 추가 어휘 18건은 fallback | 13 source/candidate 어휘 미지지 → fallback |
| source context에 근거한 새로운 표현 | 해당 없음(기존 검증은 candidate 전용) | 수동 판정 필요 |
| source context에도 없는 hallucination | 해당 없음 | 13 어휘 수준 미지지 제안 |
| input/output tokens | 11,096 / 1,324 | 11829 / 1523 |
| 실행 시간 | 14.907초 | 16.170초 |

## 기존 Terra 입력 상세 그룹

### A. Terra가 실제로 문구를 변경한 기존 9건

#### p.90 / image 3

- image bbox: `[220.79, 87.12, 385.66, 200.87]`; candidate: `적산 거리계 (ODO)`
- 기존 실제 전달 context 필드: ['A타입', 'B타입', '적산 거리계 (ODO)']
- Terra 원응답: '적산 거리계(ODO)'; 최종값: '적산 거리계(ODO)'; disposition: llm_accepted / accepted
- 선택된 text blocks:
  - bbox `[294.7366943359375, 77.00442504882812, 311.0984802246094, 85.50242614746094]`, distance=1.6pt, hgap=0.0pt, vgap=1.6pt, same_column=True: 'A타입'
  - bbox `[220.98480224609375, 203.90560913085938, 311.1439514160156, 221.25282287597656]`, distance=3.6pt, hgap=0.0pt, vgap=3.0pt, same_column=True: '2C_Odometer\nB타입'
  - bbox `[221.68719482421875, 63.507598876953125, 299.356201171875, 75.72760009765625]`, distance=12.0pt, hgap=0.0pt, vgap=11.4pt, same_column=True: '적산 거리계 (ODO)'
- 확장 context blocks:
  - bbox `[221.69, 63.51, 299.36, 75.73]`, distance=11.4pt, hgap=0.0pt, vgap=11.4pt, same_column=True: '적산 거리계 (ODO)'
  - bbox `[294.74, 77.0, 311.1, 85.5]`, distance=1.6pt, hgap=0.0pt, vgap=1.6pt, same_column=True: 'A타입'
  - bbox `[220.98, 203.91, 311.14, 221.25]`, distance=3.0pt, hgap=0.0pt, vgap=3.0pt, same_column=True: '2C_Odometer\nB타입'
- 확대 문맥 원응답: '적산 거리계(ODO)'
- 검증 결과: source_supported; 채택값: '적산 거리계(ODO)'

#### p.167 / image 1

- image bbox: `[50.88, 77.04, 215.27, 181.91]`; candidate: `파워 트렁크 열림/닫힘 버튼 (실내)`
- 기존 실제 전달 context 필드: ['파워 트렁크 열림/닫힘 버튼 (실내)', '트렁크가 닫힌 상태에서 버튼을 짧게 누르면 경\n고음과 함께 트렁크가 열립니다. 열리는 도중\n에 버튼을 짧게 누르면 원하는 위치에 트렁크를\n정지할 수 있습니다.\n트렁크가 열린 상태에서 버튼을 길게 누르면 트\n렁크가 닫힙니다. 트렁크가 닫히는 도중에 버\n튼에서 손을 떼면, 작동을 멈추고 약 5초 동안\n경고음이 울립니다.']
- Terra 원응답: '파워 트렁크 열림/닫힘 버튼(실내)'; 최종값: '파워 트렁크 열림/닫힘 버튼(실내)'; disposition: llm_accepted / accepted
- 선택된 text blocks:
  - bbox `[51.60919952392578, 63.507598876953125, 188.59922790527344, 75.72760009765625]`, distance=1.5pt, hgap=0.0pt, vgap=1.3pt, same_column=True: '파워 트렁크 열림/닫힘 버튼 (실내)'
  - bbox `[50.906898498535156, 183.53030395507812, 214.7357635498047, 276.00067138671875]`, distance=1.6pt, hgap=0.0pt, vgap=1.6pt, same_column=True: '2C_CrushPadTrunkOpenButton\n트렁크가 닫힌 상태에서 버튼을 짧게 누르면 경\n고음과 함께 트렁크가 열립니다. 열리는 도중\n에 버튼을 짧게 누르면 원하는 위치에 트렁크를\n정지할 수 있습니다. \n트렁크가 열린 상태에서 버튼을 길게 누르면 트\n렁크가 닫힙니다. 트렁크가 닫히는 도중에 버\n튼에서 손을 떼면, 작동을 멈추고 약 5초 동안\n경고음이 울립니다.'
- 확장 context blocks:
  - bbox `[51.61, 63.51, 188.6, 75.73]`, distance=1.3pt, hgap=0.0pt, vgap=1.3pt, same_column=True: '파워 트렁크 열림/닫힘 버튼 (실내)'
  - bbox `[50.91, 183.53, 214.74, 276.0]`, distance=1.6pt, hgap=0.0pt, vgap=1.6pt, same_column=True: '2C_CrushPadTrunkOpenButton\n트렁크가 닫힌 상태에서 버튼을 짧게 누르면 경\n고음과 함께 트렁크가 열립니다. 열리는 도중\n에 버튼을 짧게 누르면 원하는 위치에 트렁크를\n정지할 수 있습니다. \n트렁크가 열린 상태에서 버튼을 길게 누르면 트\n렁크가 닫힙니다. 트렁크가 닫히는 도중에 버\n튼에서 손을 떼면, 작동을 멈추고 약 5초 동안\n경고음이 울립니다.'
- 확대 문맥 원응답: '실내 파워 트렁크 열림/닫힘 버튼'
- 검증 결과: source_supported; 채택값: '실내 파워 트렁크 열림/닫힘 버튼'

#### p.180 / image 3

- image bbox: `[221.03, 77.04, 385.42, 181.91]`; candidate: `휴대폰 앱 연결을 위한 Wi-Fi 를 활성화 하거`
- 기존 실제 전달 context 필드: ['앱 연결', 'Wi-Fi 설정', '휴대폰 앱 연결을 위한 Wi-Fi 를 활성화 하거\n나, Wi-Fi 비밀번호를 설정할 수 있습니다.']
- Terra 원응답: '휴대폰 앱 연결을 위한 Wi-Fi 활성화'; 최종값: '휴대폰 앱 연결을 위한 Wi-Fi 활성화'; disposition: llm_accepted / accepted
- 선택된 text blocks:
  - bbox `[221.68719482421875, 63.507598876953125, 250.38720703125, 75.72760009765625]`, distance=2.3pt, hgap=0.0pt, vgap=1.3pt, same_column=True: '앱 연결'
  - bbox `[220.34092712402344, 199.08473205566406, 262.1089172363281, 210.01072692871094]`, distance=18.1pt, hgap=0.0pt, vgap=17.2pt, same_column=True: 'Wi-Fi 설정'
  - bbox `[221.5751953125, 212.07960510253906, 384.7865295410156, 233.0045928955078]`, distance=30.2pt, hgap=0.0pt, vgap=30.2pt, same_column=True: '휴대폰 앱 연결을 위한 Wi-Fi 를 활성화 하거\n나, Wi-Fi 비밀번호를 설정할 수 있습니다.'
- 확장 context blocks:
  - bbox `[221.69, 63.51, 250.39, 75.73]`, distance=1.3pt, hgap=0.0pt, vgap=1.3pt, same_column=True: '앱 연결'
  - bbox `[220.34, 199.08, 262.11, 210.01]`, distance=17.2pt, hgap=0.0pt, vgap=17.2pt, same_column=True: 'Wi-Fi 설정'
  - bbox `[221.58, 212.08, 384.79, 233.0]`, distance=30.2pt, hgap=0.0pt, vgap=30.2pt, same_column=True: '휴대폰 앱 연결을 위한 Wi-Fi 를 활성화 하거\n나, Wi-Fi 비밀번호를 설정할 수 있습니다.'
- 확대 문맥 원응답: '휴대폰 앱 연결을 위한 Wi-Fi 활성화 및 비밀번호 설정'
- 검증 결과: outside_candidate_and_source:및; 채택값: '휴대폰 앱 연결을 위한 Wi-Fi 를 활성화 하거'

#### p.206 / image 1

- image bbox: `[36.72, 107.28, 385.42, 253.91]`; candidate: `히터 및 에어컨 (수동 조절식) · 편의 장치`
- 기존 실제 전달 context 필드: ['A타입', 'B타입', '히터 및 에어컨 (수동 조절식)', '편의 장치']
- Terra 원응답: '히터 및 에어컨(수동 조절식) · 편의 장치'; 최종값: '히터 및 에어컨(수동 조절식) · 편의 장치'; disposition: llm_accepted / accepted
- 선택된 text blocks:
  - bbox `[202.61109924316406, 97.25222778320312, 218.972900390625, 105.75022888183594]`, distance=1.5pt, hgap=0.0pt, vgap=1.5pt, same_column=True: 'A타입'
  - bbox `[36.733699798583984, 256.9447937011719, 219.0185089111328, 274.2921142578125]`, distance=4.3pt, hgap=0.0pt, vgap=3.0pt, same_column=True: '1C_Aircon_2_TypeA\nB타입'
  - bbox `[37.71699905395508, 62.89384078979492, 198.32501220703125, 80.00183868408203]`, distance=28.7pt, hgap=0.0pt, vgap=27.3pt, same_column=True: '히터 및 에어컨 (수동 조절식)'
  - bbox `[37.58409881591797, 27.730823516845703, 72.6333999633789, 38.93132400512695]`, distance=70.7pt, hgap=0.0pt, vgap=68.3pt, same_column=True: '편의 장치'
- 확장 context blocks:
  - bbox `[37.58, 27.73, 72.63, 38.93]`, distance=68.3pt, hgap=0.0pt, vgap=68.3pt, same_column=True: '편의 장치'
  - bbox `[37.72, 62.89, 198.33, 80.0]`, distance=27.3pt, hgap=0.0pt, vgap=27.3pt, same_column=True: '히터 및 에어컨 (수동 조절식)'
  - bbox `[202.61, 97.25, 218.97, 105.75]`, distance=1.5pt, hgap=0.0pt, vgap=1.5pt, same_column=True: 'A타입'
  - bbox `[36.73, 256.94, 219.02, 274.29]`, distance=3.0pt, hgap=0.0pt, vgap=3.0pt, same_column=True: '1C_Aircon_2_TypeA\nB타입'
- 확대 문맥 원응답: '히터 및 에어컨 수동 조절식'
- 검증 결과: source_supported; 채택값: '히터 및 에어컨 수동 조절식'

#### p.229 / image 1

- image bbox: `[50.88, 82.08, 215.27, 186.95]`; candidate: `뒷유리 서리 제거 (열선)`
- 기존 실제 전달 context 필드: ['시동이 걸린 상태에서 뒷유리 서리 제거 버튼을\n누르면 버튼 내 표시등이 켜지고, 해당 기능이\n작동합니다. 버튼을 한 번 더 누르면 작동이 멈\n춥니다. 기능이 작동한 후 약 20분이 지나면 자\n동으로 멈춥니다.\n또한 작동 중에 시동을 껐다가 시동을 다시 걸\n면 뒷유리 서리 제거 기능은 꺼집니다.', '뒷유리 서리 제거 (열선)']
- Terra 원응답: '뒷유리 서리 제거(열선)'; 최종값: '뒷유리 서리 제거(열선)'; disposition: llm_accepted / accepted
- 선택된 text blocks:
  - bbox `[50.906898498535156, 188.52920532226562, 214.62240600585938, 271.00054931640625]`, distance=1.6pt, hgap=0.0pt, vgap=1.6pt, same_column=True: '2C_RearWindowDefrost\n시동이 걸린 상태에서 뒷유리 서리 제거 버튼을\n누르면 버튼 내 표시등이 켜지고, 해당 기능이\n작동합니다. 버튼을 한 번 더 누르면 작동이 멈\n춥니다. 기능이 작동한 후 약 20분이 지나면 자\n동으로 멈춥니다.\n또한 작동 중에 시동을 껐다가 시동을 다시 걸\n면 뒷유리 서리 제거 기능은 꺼집니다.'
  - bbox `[51.749698638916016, 63.20071792602539, 165.14967346191406, 77.86471557617188]`, distance=4.6pt, hgap=0.0pt, vgap=4.2pt, same_column=True: '뒷유리 서리 제거 (열선)'
- 확장 context blocks:
  - bbox `[51.75, 63.2, 165.15, 77.86]`, distance=4.2pt, hgap=0.0pt, vgap=4.2pt, same_column=True: '뒷유리 서리 제거 (열선)'
  - bbox `[50.91, 188.53, 214.62, 271.0]`, distance=1.6pt, hgap=0.0pt, vgap=1.6pt, same_column=True: '2C_RearWindowDefrost\n시동이 걸린 상태에서 뒷유리 서리 제거 버튼을\n누르면 버튼 내 표시등이 켜지고, 해당 기능이\n작동합니다. 버튼을 한 번 더 누르면 작동이 멈\n춥니다. 기능이 작동한 후 약 20분이 지나면 자\n동으로 멈춥니다.\n또한 작동 중에 시동을 껐다가 시동을 다시 걸\n면 뒷유리 서리 제거 기능은 꺼집니다.'
  - bbox `[51.54, 284.84, 214.75, 318.97]`, distance=97.9pt, hgap=0.0pt, vgap=97.9pt, same_column=True: '실외 미러 서리 제거(열선) \n뒷유리 서리 제거 기능이 작동하면 동시에 실외\n미러 서리 제거 기능도 작동합니다.'
- 확대 문맥 원응답: '뒷유리 서리 제거(열선)'
- 검증 결과: source_supported; 채택값: '뒷유리 서리 제거(열선)'

#### p.267 / image 1

- image bbox: `[50.88, 77.04, 215.27, 181.91]`; candidate: `R (Reverse): 후진`
- 기존 실제 전달 context 필드: ["차를 후진할 때 사용합니다.\n브레이크 페달을 밟은 상태에서 R 위치로 돌\n리십시오.\n차량이 'R'(후진) 상태에서 정차해 있을 때 안\n전벨트를 풀고 운전석 도어를 열면 자동으로\n'P'(주차)로 변속됩니다. 차량이 움직이고 있", 'R (Reverse): 후진']
- Terra 원응답: 'R(Reverse): 후진'; 최종값: 'R(Reverse): 후진'; disposition: llm_accepted / accepted
- 선택된 text blocks:
  - bbox `[50.906898498535156, 183.53091430664062, 214.6842803955078, 264.9871826171875]`, distance=1.6pt, hgap=0.0pt, vgap=1.6pt, same_column=True: "2C_ShiftButtonRPosition\n• 차를 후진할 때 사용합니다.\n• 브레이크 페달을 밟은 상태에서 R 위치로 돌\n리십시오.\n• 차량이 'R'(후진) 상태에서 정차해 있을 때 안\n전벨트를 풀고 운전석 도어를 열면 자동으로\n'P'(주차)로 변속됩니다. 차량이 움직이고 있"
  - bbox `[50.26302719116211, 63.71509552001953, 118.98600006103516, 74.64109802246094]`, distance=3.1pt, hgap=0.0pt, vgap=2.4pt, same_column=True: 'R (Reverse): 후진'
- 확장 context blocks:
  - bbox `[50.26, 63.72, 118.99, 74.64]`, distance=2.4pt, hgap=0.0pt, vgap=2.4pt, same_column=True: 'R (Reverse): 후진'
  - bbox `[50.91, 183.53, 214.68, 264.99]`, distance=1.6pt, hgap=0.0pt, vgap=1.6pt, same_column=True: "2C_ShiftButtonRPosition\n• 차를 후진할 때 사용합니다.\n• 브레이크 페달을 밟은 상태에서 R 위치로 돌\n리십시오.\n• 차량이 'R'(후진) 상태에서 정차해 있을 때 안\n전벨트를 풀고 운전석 도어를 열면 자동으로\n'P'(주차)로 변속됩니다. 차량이 움직이고 있"
  - bbox `[50.91, 264.06, 215.29, 310.54]`, distance=82.1pt, hgap=0.0pt, vgap=82.1pt, same_column=True: "는 경우 더블 클러치 변속기 보호를 위해 'P'(\n주차)로 변속되지 않을 수 있습니다.\n• 변속 다이얼의 회전 방향은 바퀴의 회전 방\n향과 동일합니다҃"
  - bbox `[51.51, 338.89, 214.6, 359.81]`, distance=157.0pt, hgap=0.0pt, vgap=157.0pt, same_column=True: "반드시 차를 정지시킨 후 'R'(후진)로 변속하십\n시오."
- 확대 문맥 원응답: 'R(Reverse) 후진'
- 검증 결과: source_supported; 채택값: 'R(Reverse) 후진'

#### p.304 / image 1

- image bbox: `[36.72, 218.15, 201.11, 323.03]`; candidate: `전방 충돌방지 보조 (FCA) (전 · 기본 기능`
- 기존 실제 전달 context 필드: ['전방의 차량, 이륜차, 보행자 및 자전거 탑승자\n를 인식하여 전방 충돌 위험이 판단되면 경고문\n과 경고음 등으로 운전자에게 알려주고, 충돌\n경감 또는 회피하도록 제동을 도와줍니다.', '기본 기능', '전방 충돌방지 보조 (FCA) (전\n방 카메라 단독)', 'FCA는\nForward\nCollision-Avoidance\nAssist의 약자입니다.']
- Terra 원응답: '전방 충돌방지 보조(FCA) 기본 기능'; 최종값: '전방 충돌방지 보조(FCA) 기본 기능'; disposition: llm_accepted / accepted
- 선택된 text blocks:
  - bbox `[36.733699798583984, 324.7377014160156, 200.5355682373047, 374.215087890625]`, distance=1.7pt, hgap=0.0pt, vgap=1.7pt, same_column=True: '2C_FCABasicFunction_Frontcamera\n전방의 차량, 이륜차, 보행자 및 자전거 탑승자\n를 인식하여 전방 충돌 위험이 판단되면 경고문\n과 경고음 등으로 운전자에게 알려주고, 충돌\n경감 또는 회피하도록 제동을 도와줍니다.'
  - bbox `[37.364601135253906, 205.0119171142578, 71.58800506591797, 215.62290954589844]`, distance=3.5pt, hgap=0.0pt, vgap=2.5pt, same_column=True: '기본 기능'
  - bbox `[37.71699905395508, 151.86610412597656, 200.17295837402344, 187.96641540527344]`, distance=30.2pt, hgap=0.0pt, vgap=30.2pt, same_column=True: '전방 충돌방지 보조 (FCA) (전\n방 카메라 단독)'
  - bbox `[36.733699798583984, 401.1623840332031, 201.12498474121094, 424.05419921875]`, distance=78.1pt, hgap=0.0pt, vgap=78.1pt, same_column=True: 'FCA는 \nForward \nCollision-Avoidance\nAssist의 약자입니다.'
- 확장 context blocks:
  - bbox `[37.58, 27.73, 80.79, 38.93]`, distance=179.2pt, hgap=0.0pt, vgap=179.2pt, same_column=True: '운전자 보조'
  - bbox `[37.72, 151.87, 200.17, 187.97]`, distance=30.2pt, hgap=0.0pt, vgap=30.2pt, same_column=True: '전방 충돌방지 보조 (FCA) (전\n방 카메라 단독)'
  - bbox `[37.36, 205.01, 71.59, 215.62]`, distance=2.5pt, hgap=0.0pt, vgap=2.5pt, same_column=True: '기본 기능'
  - bbox `[36.73, 324.74, 200.54, 374.22]`, distance=1.7pt, hgap=0.0pt, vgap=1.7pt, same_column=True: '2C_FCABasicFunction_Frontcamera\n전방의 차량, 이륜차, 보행자 및 자전거 탑승자\n를 인식하여 전방 충돌 위험이 판단되면 경고문\n과 경고음 등으로 운전자에게 알려주고, 충돌\n경감 또는 회피하도록 제동을 도와줍니다.'
  - bbox `[36.73, 401.16, 201.12, 424.05]`, distance=78.1pt, hgap=0.0pt, vgap=78.1pt, same_column=True: 'FCA는 \nForward \nCollision-Avoidance\nAssist의 약자입니다.'
- 확대 문맥 원응답: '전방 충돌방지 보조(FCA) 기본 기능'
- 검증 결과: source_supported; 채택값: '전방 충돌방지 보조(FCA) 기본 기능'

#### p.343 / image 1

- image bbox: `[50.88, 107.04, 215.51, 212.15]`; candidate: `안전 하차 보조 이상 및 제한 사항 · 기능 이상`
- 기존 실제 전달 context 필드: ['안전 하차 보조에 이상이 있으면 클러스터에 경\n고문이 일정시간 표시되며 통합 경고등( )이\n켜집니다. 당사 직영 하이테크센터나 블루핸즈\n에서 점검을 받으십시오.\n경고 대상 기능은 클러스터 표시창 중 유틸\n리티 정보 뷰의 서비스 메시지에서 확인할\n수 있습니다.', '기능 이상', '안전 하차 보조 이상 및 제한 사항']
- Terra 원응답: '안전 하차 보조 이상 및 제한 사항'; 최종값: '안전 하차 보조 이상 및 제한 사항'; disposition: llm_accepted / accepted
- 선택된 text blocks:
  - bbox `[50.906898498535156, 213.76321411132812, 214.7256622314453, 298.219970703125]`, distance=1.6pt, hgap=0.0pt, vgap=1.6pt, same_column=True: '2C_ForwardSafetyMalfunctionInfo\n안전 하차 보조에 이상이 있으면 클러스터에 경\n고문이 일정시간 표시되며 통합 경고등( )이\n켜집니다. 당사 직영 하이테크센터나 블루핸즈\n에서 점검을 받으십시오.\n• 경고 대상 기능은 클러스터 표시창 중 유틸\n리티 정보 뷰의 서비스 메시지에서 확인할\n수 있습니다.'
  - bbox `[51.60919952392578, 93.50091552734375, 89.54918670654297, 105.72091674804688]`, distance=2.3pt, hgap=0.0pt, vgap=1.3pt, same_column=True: '기능 이상'
  - bbox `[51.749698638916016, 63.20071792602539, 207.65362548828125, 77.86471557617188]`, distance=29.2pt, hgap=0.0pt, vgap=29.2pt, same_column=True: '안전 하차 보조 이상 및 제한 사항'
- 확장 context blocks:
  - bbox `[51.75, 63.2, 207.65, 77.86]`, distance=29.2pt, hgap=0.0pt, vgap=29.2pt, same_column=True: '안전 하차 보조 이상 및 제한 사항'
  - bbox `[51.61, 93.5, 89.55, 105.72]`, distance=1.3pt, hgap=0.0pt, vgap=1.3pt, same_column=True: '기능 이상'
  - bbox `[50.91, 213.76, 214.73, 298.22]`, distance=1.6pt, hgap=0.0pt, vgap=1.6pt, same_column=True: '2C_ForwardSafetyMalfunctionInfo\n안전 하차 보조에 이상이 있으면 클러스터에 경\n고문이 일정시간 표시되며 통합 경고등( )이\n켜집니다. 당사 직영 하이테크센터나 블루핸즈\n에서 점검을 받으십시오.\n• 경고 대상 기능은 클러스터 표시창 중 유틸\n리티 정보 뷰의 서비스 메시지에서 확인할\n수 있습니다.'
- 확대 문맥 원응답: '안전 하차 보조 기능 이상'
- 검증 결과: source_supported; 채택값: '안전 하차 보조 기능 이상'

#### p.344 / image 1

- image bbox: `[221.03, 84.0, 385.42, 188.87]`; candidate: `수동 속도 제한 보조 (MSLA)`
- 기존 실제 전달 context 필드: ['(1) 속도 제한 표시등', '수동 속도 제한 보조 (MSLA)', '(2) 설정속도', '특정 속도 이상으로 주행하는 것을 원하지 않을\n때 속도 제한 기능을 실행할 수 있습니다. 제한\n속도를 초과하여 주행할 경우 주행속도가 제한\n속도 이하가 될 때까지 경고음이 울립니다.']
- Terra 원응답: '수동 속도 제한 보조(MSLA)'; 최종값: '수동 속도 제한 보조(MSLA)'; disposition: llm_accepted / accepted
- 선택된 text blocks:
  - bbox `[220.98480224609375, 190.52810668945312, 282.6552429199219, 208.94190979003906]`, distance=2.4pt, hgap=0.0pt, vgap=1.7pt, same_column=True: '2C_MSLAOverviewInfo\n(1) 속도 제한 표시등'
  - bbox `[221.9680938720703, 62.89384078979492, 381.0080261230469, 80.00183868408203]`, distance=4.0pt, hgap=0.0pt, vgap=4.0pt, same_column=True: '수동 속도 제한 보조 (MSLA)'
  - bbox `[220.98480224609375, 212.22190856933594, 259.6719970703125, 221.9339141845703]`, distance=24.3pt, hgap=0.0pt, vgap=23.4pt, same_column=True: '(2) 설정속도'
  - bbox `[221.53919982910156, 225.07362365722656, 384.83148193359375, 265.99658203125]`, distance=36.2pt, hgap=0.0pt, vgap=36.2pt, same_column=True: '특정 속도 이상으로 주행하는 것을 원하지 않을\n때 속도 제한 기능을 실행할 수 있습니다. 제한\n속도를 초과하여 주행할 경우 주행속도가 제한\n속도 이하가 될 때까지 경고음이 울립니다.'
- 확장 context blocks:
  - bbox `[221.97, 62.89, 381.01, 80.0]`, distance=4.0pt, hgap=0.0pt, vgap=4.0pt, same_column=True: '수동 속도 제한 보조 (MSLA)'
  - bbox `[220.98, 190.53, 282.66, 208.94]`, distance=1.7pt, hgap=0.0pt, vgap=1.7pt, same_column=True: '2C_MSLAOverviewInfo\n(1) 속도 제한 표시등'
  - bbox `[220.98, 212.22, 259.67, 221.93]`, distance=23.3pt, hgap=0.0pt, vgap=23.3pt, same_column=True: '(2) 설정속도'
  - bbox `[221.54, 225.07, 384.83, 266.0]`, distance=36.2pt, hgap=0.0pt, vgap=36.2pt, same_column=True: '특정 속도 이상으로 주행하는 것을 원하지 않을\n때 속도 제한 기능을 실행할 수 있습니다. 제한\n속도를 초과하여 주행할 경우 주행속도가 제한\n속도 이하가 될 때까지 경고음이 울립니다.'
  - bbox `[220.98, 292.94, 384.82, 305.84]`, distance=104.1pt, hgap=0.0pt, vgap=104.1pt, same_column=True: 'MSLA는 Manual Speed Limit Assist의 약자'
  - bbox `[221.61, 304.91, 248.52, 315.84]`, distance=116.0pt, hgap=0.0pt, vgap=116.0pt, same_column=True: '입니다.'
- 확대 문맥 원응답: '수동 속도 제한 보조(MSLA)'
- 검증 결과: source_supported; 채택값: '수동 속도 제한 보조(MSLA)'

### B. 기존 candidate 밖 어휘로 거부된 18건

#### p.25 / image 3

- image bbox: `[235.19, 84.0, 399.58, 188.87]`; candidate: `옆 센터 필러에 부착된 라벨 안에 표기되어 있`
- 기존 실제 전달 context 필드: ['본 차량의 권장 타이어 공기압 정보는 운전석\n옆 센터 필러에 부착된 라벨 안에 표기되어 있\n습니다.', '타이어 공기압']
- Terra 원응답: '옆 센터 필러에 부착된 라벨에 표기되어 있습니다.'; 최종값: '옆 센터 필러에 부착된 라벨 안에 표기되어 있'; disposition: fallback_candidate / new_tokens:라벨에,있습니다
- 선택된 text blocks:
  - bbox `[235.1580047607422, 190.52810668945312, 399.06488037109375, 230.00648498535156]`, distance=1.7pt, hgap=0.0pt, vgap=1.7pt, same_column=True: '2C_TireLabel\n본 차량의 권장 타이어 공기압 정보는 운전석\n옆 센터 필러에 부착된 라벨 안에 표기되어 있\n습니다.'
  - bbox `[236.14129638671875, 62.89384078979492, 314.2878723144531, 80.00183868408203]`, distance=4.6pt, hgap=0.0pt, vgap=4.0pt, same_column=True: '타이어 공기압'
- 확장 context blocks:
  - bbox `[236.14, 62.89, 314.29, 80.0]`, distance=4.0pt, hgap=0.0pt, vgap=4.0pt, same_column=True: '타이어 공기압'
  - bbox `[235.16, 190.53, 399.06, 230.01]`, distance=1.7pt, hgap=0.0pt, vgap=1.7pt, same_column=True: '2C_TireLabel\n본 차량의 권장 타이어 공기압 정보는 운전석\n옆 센터 필러에 부착된 라벨 안에 표기되어 있\n습니다.'
- 확대 문맥 원응답: '운전석 옆 센터 필러의 권장 타이어 공기압 라벨'
- 검증 결과: outside_candidate_and_source:필러의; 채택값: '옆 센터 필러에 부착된 라벨 안에 표기되어 있'

#### p.32 / image 2

- image bbox: `[36.72, 363.34, 201.11, 468.22]`; candidate: `차량 운전 상태에서 탑승한 아이들을 안전하게`
- 기존 실제 전달 context 필드: ['차량 운전 상태에서 탑승한 아이들을 안전하게\n보호하기 위해서는 아래의 사항을 지키십시오.', '유아/어린이의 에어백 관련 주의\n사항']
- Terra 원응답: '차량 운전 상태에서 탑승한 아이들을 안전하게 보호하기 위해'; 최종값: '차량 운전 상태에서 탑승한 아이들을 안전하게'; disposition: fallback_candidate / new_tokens:보호하기,위해
- 선택된 text blocks:
  - bbox `[37.342098236083984, 340.027099609375, 201.08815002441406, 360.95208740234375]`, distance=2.4pt, hgap=0.0pt, vgap=2.4pt, same_column=True: '차량 운전 상태에서 탑승한 아이들을 안전하게\n보호하기 위해서는 아래의 사항을 지키십시오.'
  - bbox `[37.576499938964844, 306.5260925292969, 194.11648559570312, 336.1781005859375]`, distance=27.2pt, hgap=0.0pt, vgap=27.2pt, same_column=True: '유아/어린이의 에어백 관련 주의 \n사항'
- 확장 context blocks:
  - bbox `[37.58, 306.53, 194.12, 336.18]`, distance=27.2pt, hgap=0.0pt, vgap=27.2pt, same_column=True: '유아/어린이의 에어백 관련 주의 \n사항'
  - bbox `[37.34, 340.03, 201.09, 360.95]`, distance=2.4pt, hgap=0.0pt, vgap=2.4pt, same_column=True: '차량 운전 상태에서 탑승한 아이들을 안전하게\n보호하기 위해서는 아래의 사항을 지키십시오.'
- 확대 문맥 원응답: '탑승한 아이들의 안전한 보호'
- 검증 결과: outside_candidate_and_source:안전한,아이들의; 채택값: '차량 운전 상태에서 탑승한 아이들을 안전하게'

#### p.77 / image 3

- image bbox: `[50.88, 369.82, 215.27, 474.7]`; candidate: `노트북이나 DVD 등 전자 장비나 다량의 물`
- 기존 실제 전달 context 필드: ['노트북이나 DVD 등 전자 장비나 다량의 물\n통 등 전도성 물체를 동승석 시트 위에 올려\n놓지 마십시오.']
- Terra 원응답: '노트북이나 DVD 등 전자 장비나 다량의 물통'; 최종값: '노트북이나 DVD 등 전자 장비나 다량의 물'; disposition: fallback_candidate / new_tokens:물통
- 선택된 text blocks:
  - bbox `[50.906898498535156, 325.8938903808594, 214.7076416015625, 367.3673095703125]`, distance=2.5pt, hgap=0.0pt, vgap=2.5pt, same_column=True: '2C_OCSWarning_6\n• 노트북이나 DVD 등 전자 장비나 다량의 물\n통 등 전도성 물체를 동승석 시트 위에 올려\n놓지 마십시오.'
- 확장 context blocks:
  - bbox `[50.91, 325.89, 214.71, 367.37]`, distance=2.5pt, hgap=0.0pt, vgap=2.5pt, same_column=True: '2C_OCSWarning_6\n• 노트북이나 DVD 등 전자 장비나 다량의 물\n통 등 전도성 물체를 동승석 시트 위에 올려\n놓지 마십시오.'
- 확대 문맥 원응답: '동승석 시트 위 전자 장비 및 전도성 물체'
- 검증 결과: outside_candidate_and_source:및; 채택값: '노트북이나 DVD 등 전자 장비나 다량의 물'

#### p.82 / image 4

- image bbox: `[221.03, 275.27, 385.42, 380.14]`; candidate: `사면 충돌이나 추돌 사고(앞 방향에서 비스듬`
- 기존 실제 전달 context 필드: ['정면에서 전해지는 충격은 정면충돌이나 추돌\n한 경우보다 약하여 에어백이 작동하지 않을 수\n있습니다.', '사면 충돌이나 추돌 사고(앞 방향에서 비스듬\n히 충돌)']
- Terra 원응답: '사면 충돌이나 추돌 사고(앞 방향에서 비스듬히 충돌)'; 최종값: '사면 충돌이나 추돌 사고(앞 방향에서 비스듬'; disposition: fallback_candidate / new_tokens:비스듬히,충돌
- 선택된 text blocks:
  - bbox `[220.98480224609375, 381.8712158203125, 384.7954406738281, 421.349609375]`, distance=1.7pt, hgap=0.0pt, vgap=1.7pt, same_column=True: '2C_AirbagNonOperatingConditionSidlingCrash\n정면에서 전해지는 충격은 정면충돌이나 추돌\n한 경우보다 약하여 에어백이 작동하지 않을 수\n있습니다.'
  - bbox `[220.97183227539062, 252.06031799316406, 383.00396728515625, 272.98529052734375]`, distance=2.3pt, hgap=0.0pt, vgap=2.3pt, same_column=True: '사면 충돌이나 추돌 사고(앞 방향에서 비스듬\n히 충돌)'
- 확장 context blocks:
  - bbox `[220.97, 252.06, 383.0, 272.99]`, distance=2.3pt, hgap=0.0pt, vgap=2.3pt, same_column=True: '사면 충돌이나 추돌 사고(앞 방향에서 비스듬\n히 충돌)'
  - bbox `[220.98, 381.87, 384.8, 421.35]`, distance=1.7pt, hgap=0.0pt, vgap=1.7pt, same_column=True: '2C_AirbagNonOperatingConditionSidlingCrash\n정면에서 전해지는 충격은 정면충돌이나 추돌\n한 경우보다 약하여 에어백이 작동하지 않을 수\n있습니다.'
- 확대 문맥 원응답: '사면 충돌이나 추돌 사고(앞 방향에서 비스듬히 충돌)'
- 검증 결과: source_supported; 채택값: '사면 충돌이나 추돌 사고(앞 방향에서 비스듬히 충돌)'

#### p.115 / image 2

- image bbox: `[235.19, 107.04, 399.58, 211.91]`; candidate: `도어 잠금 해제(2)(세이프티 언락 기능 설 · 버튼 타입`
- 기존 실제 전달 context 필드: ['1. 모든 도어가 잠금 상태일 때 스마트 키를 휴\n대하고 앞좌석 도어의 바깥쪽 도어 핸들에\n있는 도어 잠금/잠금 해제 버튼을 누르거나\n스마트 키의 도어 잠금 해제 버튼을 누르십\n시오.\n2. 운전석 도어가 잠금 해제 상태가 됐는지 확\n인하십시오.\n3. 4초 이내에 다시 한 번 도어 잠금/잠금 해제\n버튼을 누르거나 스마트 키의 도어 잠금 해\n제 버튼을 누르면 도어가 잠금 해제됩니다.\n이 때 비상 경고등이 2회 깜빡이고 알림음이\n울립니다.', '버튼 타입', '도어 잠금 해제(2)(세이프티 언락 기능 설\n정 시)']
- Terra 원응답: '도어 잠금 해제(2)(세이프티 언락 기능 설정 시) · 버튼 타입'; 최종값: '도어 잠금 해제(2)(세이프티 언락 기능 설 · 버튼 타입'; disposition: fallback_candidate / new_tokens:설정,시
- 선택된 text blocks:
  - bbox `[235.00502014160156, 213.51980590820312, 399.3448486328125, 348.983154296875]`, distance=1.6pt, hgap=0.0pt, vgap=1.6pt, same_column=True: '2C_OutsideDoorHandleTouch\n1. 모든 도어가 잠금 상태일 때 스마트 키를 휴\n대하고 앞좌석 도어의 바깥쪽 도어 핸들에\n있는 도어 잠금/잠금 해제 버튼을 누르거나\n스마트 키의 도어 잠금 해제 버튼을 누르십\n시오.\n2. 운전석 도어가 잠금 해제 상태가 됐는지 확\n인하십시오.\n3. 4초 이내에 다시 한 번 도어 잠금/잠금 해제\n버튼을 누르거나 스마트 키의 도어 잠금 해\n제 버튼을 누르면 도어가 잠금 해제됩니다.\n이 때 비상 경고등이 2회 깜빡이고 알림음이\n울립니다.'
  - bbox `[235.14501953125, 93.70401763916016, 272.2959899902344, 104.63002014160156]`, distance=3.4pt, hgap=0.0pt, vgap=2.4pt, same_column=True: '버튼 타입'
  - bbox `[235.8603057861328, 63.507598876953125, 396.5303955078125, 85.71759033203125]`, distance=21.3pt, hgap=0.0pt, vgap=21.3pt, same_column=True: '도어 잠금 해제(2)(세이프티 언락 기능 설\n정 시)'
- 확장 context blocks:
  - bbox `[235.86, 63.51, 396.53, 85.72]`, distance=21.3pt, hgap=0.0pt, vgap=21.3pt, same_column=True: '도어 잠금 해제(2)(세이프티 언락 기능 설\n정 시)'
  - bbox `[235.15, 93.7, 272.3, 104.63]`, distance=2.4pt, hgap=0.0pt, vgap=2.4pt, same_column=True: '버튼 타입'
  - bbox `[235.01, 213.52, 399.34, 348.98]`, distance=1.6pt, hgap=0.0pt, vgap=1.6pt, same_column=True: '2C_OutsideDoorHandleTouch\n1. 모든 도어가 잠금 상태일 때 스마트 키를 휴\n대하고 앞좌석 도어의 바깥쪽 도어 핸들에\n있는 도어 잠금/잠금 해제 버튼을 누르거나\n스마트 키의 도어 잠금 해제 버튼을 누르십\n시오.\n2. 운전석 도어가 잠금 해제 상태가 됐는지 확\n인하십시오.\n3. 4초 이내에 다시 한 번 도어 잠금/잠금 해제\n버튼을 누르거나 스마트 키의 도어 잠금 해\n제 버튼을 누르면 도어가 잠금 해제됩니다.\n이 때 비상 경고등이 2회 깜빡이고 알림음이\n울립니다.'
- 확대 문맥 원응답: '세이프티 언락 기능 설정 시 도어 잠금 해제 버튼 타입'
- 검증 결과: source_supported; 채택값: '세이프티 언락 기능 설정 시 도어 잠금 해제 버튼 타입'

#### p.123 / image 1

- image bbox: `[50.88, 149.99, 215.27, 254.87]`; candidate: `[B] 스마트폰 뒷면에 있는 NFC 안테나(스마트폰 마`
- 기존 실제 전달 context 필드: ['삼성 스마트폰', '[A] 도어 핸들 인증 패드\n[B] 스마트폰 뒷면에 있는 NFC 안테나(스마트폰 마', '터치 제어\n스마트폰을 차량 도어 손잡이에 터치하여 도어\n잠금/잠금 해제가 가능하며, 차량 내 실내 인증\n패드(무선 충전 패드) 위에 올려놓고 시동을 걸\n수 있습니다.', '디지털 키(스마트폰) 사용하기']
- Terra 원응답: '[B] 스마트폰 뒷면 NFC 안테나'; 최종값: '[B] 스마트폰 뒷면에 있는 NFC 안테나(스마트폰 마'; disposition: fallback_candidate / new_tokens:뒷면
- 선택된 text blocks:
  - bbox `[113.53489685058594, 139.97952270507812, 152.75241088867188, 148.47752380371094]`, distance=1.5pt, hgap=0.0pt, vgap=1.5pt, same_column=True: '삼성 스마트폰'
  - bbox `[50.906898498535156, 258.0016174316406, 211.9629364013672, 287.4073181152344]`, distance=3.2pt, hgap=0.0pt, vgap=3.1pt, same_column=True: '2C_OutsideDoorHandleTouchBySmartPhone\n[A] 도어 핸들 인증 패드\n[B] 스마트폰 뒷면에 있는 NFC 안테나(스마트폰 마'
  - bbox `[50.89392852783203, 83.70948028564453, 214.72679138183594, 137.6274871826172]`, distance=12.4pt, hgap=0.0pt, vgap=12.4pt, same_column=True: '터치 제어\n스마트폰을 차량 도어 손잡이에 터치하여 도어\n잠금/잠금 해제가 가능하며, 차량 내 실내 인증\n패드(무선 충전 패드) 위에 올려놓고 시동을 걸\n수 있습니다.'
  - bbox `[51.60919952392578, 63.507598876953125, 170.0681915283203, 75.72760009765625]`, distance=74.6pt, hgap=0.0pt, vgap=74.3pt, same_column=True: '디지털 키(스마트폰) 사용하기'
- 확장 context blocks:
  - bbox `[51.61, 63.51, 170.07, 75.73]`, distance=74.3pt, hgap=0.0pt, vgap=74.3pt, same_column=True: '디지털 키(스마트폰) 사용하기'
  - bbox `[50.89, 83.71, 214.73, 137.63]`, distance=12.4pt, hgap=0.0pt, vgap=12.4pt, same_column=True: '터치 제어\n스마트폰을 차량 도어 손잡이에 터치하여 도어\n잠금/잠금 해제가 가능하며, 차량 내 실내 인증\n패드(무선 충전 패드) 위에 올려놓고 시동을 걸\n수 있습니다.'
  - bbox `[113.53, 139.98, 152.75, 148.48]`, distance=1.5pt, hgap=0.0pt, vgap=1.5pt, same_column=True: '삼성 스마트폰'
  - bbox `[50.91, 258.0, 211.96, 287.41]`, distance=3.1pt, hgap=0.0pt, vgap=3.1pt, same_column=True: '2C_OutsideDoorHandleTouchBySmartPhone\n[A] 도어 핸들 인증 패드\n[B] 스마트폰 뒷면에 있는 NFC 안테나(스마트폰 마'
- 확대 문맥 원응답: '스마트폰 뒷면 NFC 안테나'
- 검증 결과: source_supported; 채택값: '스마트폰 뒷면 NFC 안테나'

#### p.174 / image 2

- image bbox: `[221.03, 191.75, 385.42, 296.63]`; candidate: `아닌 다른 부분을 누르면 연료 주입구 커버`
- 기존 실제 전달 context 필드: ['3. 연료 주입구 커버가 열립니다.\n추운 날씨에 커버 주변이 얼어서 연료 주입\n구 커버가 열리지 않으면, 커버 주위를 가볍\n게 두드리거나 누르십시오.\n만일 과충전이 되었을 경우 가까운 당사 직\n영 하이테크센터에 문의 후 조치 바랍니다(\n과충전 방지 장치: 80 % 충전 시 연료 자동\n차단).', '연료 주입구 커버의 오른쪽 끝 중앙 부분이\n아닌 다른 부분을 누르면 연료 주입구 커버\n가 열리지 않을 수 있습니다.', '1. 엔진에 시동을 반드시 끄십시오.\n2. 연료 주입구 커버의 오른쪽 끝 중앙 부분(1)\n을 누르십시오.']
- Terra 원응답: '다른 부분을 누르면 연료 주입구 커버가 열리지 않을 수 있음'; 최종값: '아닌 다른 부분을 누르면 연료 주입구 커버'; disposition: fallback_candidate / new_tokens:수,않을,열리지,있음,커버가
- 선택된 text blocks:
  - bbox `[220.98480224609375, 298.1899108886719, 385.2166442871094, 393.65728759765625]`, distance=1.6pt, hgap=0.0pt, vgap=1.6pt, same_column=True: '2C_FuelInletDoor\n3. 연료 주입구 커버가 열립니다.\n추운 날씨에 커버 주변이 얼어서 연료 주입\n구 커버가 열리지 않으면, 커버 주위를 가볍\n게 두드리거나 누르십시오.\n만일 과충전이 되었을 경우 가까운 당사 직\n영 하이테크센터에 문의 후 조치 바랍니다(\n과충전 방지 장치: 80 % 충전 시 연료 자동\n차단).'
  - bbox `[230.0701141357422, 136.5838165283203, 384.8636474609375, 169.47450256347656]`, distance=22.3pt, hgap=0.0pt, vgap=22.3pt, same_column=True: '연료 주입구 커버의 오른쪽 끝 중앙 부분이\n아닌 다른 부분을 누르면 연료 주입구 커버\n가 열리지 않을 수 있습니다.'
  - bbox `[220.9578094482422, 81.70838165283203, 385.47137451171875, 115.62937927246094]`, distance=76.1pt, hgap=0.0pt, vgap=76.1pt, same_column=True: '1. 엔진에 시동을 반드시 끄십시오.\n2. 연료 주입구 커버의 오른쪽 끝 중앙 부분(1)\n을 누르십시오.'
- 확장 context blocks:
  - bbox `[221.83, 63.2, 378.92, 77.86]`, distance=113.9pt, hgap=0.0pt, vgap=113.9pt, same_column=True: '연료 주입구 여는 방법 (LPI 차량)'
  - bbox `[220.96, 81.71, 385.47, 115.63]`, distance=76.1pt, hgap=0.0pt, vgap=76.1pt, same_column=True: '1. 엔진에 시동을 반드시 끄십시오.\n2. 연료 주입구 커버의 오른쪽 끝 중앙 부분(1)\n을 누르십시오.'
  - bbox `[230.07, 136.58, 384.86, 169.47]`, distance=22.3pt, hgap=0.0pt, vgap=22.3pt, same_column=True: '연료 주입구 커버의 오른쪽 끝 중앙 부분이\n아닌 다른 부분을 누르면 연료 주입구 커버\n가 열리지 않을 수 있습니다.'
  - bbox `[220.98, 298.19, 385.22, 393.66]`, distance=1.6pt, hgap=0.0pt, vgap=1.6pt, same_column=True: '2C_FuelInletDoor\n3. 연료 주입구 커버가 열립니다.\n추운 날씨에 커버 주변이 얼어서 연료 주입\n구 커버가 열리지 않으면, 커버 주위를 가볍\n게 두드리거나 누르십시오.\n만일 과충전이 되었을 경우 가까운 당사 직\n영 하이테크센터에 문의 후 조치 바랍니다(\n과충전 방지 장치: 80 % 충전 시 연료 자동\n차단).'
- 확대 문맥 원응답: '연료 주입구 커버 오른쪽 끝 중앙 부분'
- 검증 결과: source_supported; 채택값: '연료 주입구 커버 오른쪽 끝 중앙 부분'

#### p.201 / image 5

- image bbox: `[234.95, 241.91, 399.58, 346.79]`; candidate: `버튼을 누르면 램프가 켜지고 다시 한번 누`
- 기존 실제 전달 context 필드: ['퍼스널 램프(사양 적용 시)', ': 버튼을 누르면 램프가 켜지고 다시 한번 누\n르면 꺼집니다.']
- Terra 원응답: '버튼을 누르면 램프가 켜지고 다시 누르면 꺼집니다.'; 최종값: '버튼을 누르면 램프가 켜지고 다시 한번 누'; disposition: fallback_candidate / new_tokens:꺼집니다
- 선택된 text blocks:
  - bbox `[281.279296875, 231.867919921875, 353.9252014160156, 240.3659210205078]`, distance=1.5pt, hgap=0.0pt, vgap=1.5pt, same_column=True: '퍼스널 램프(사양 적용 시)'
  - bbox `[235.1580047607422, 349.889892578125, 398.91278076171875, 379.37261962890625]`, distance=3.1pt, hgap=0.0pt, vgap=3.1pt, same_column=True: '2C_RoomLamp_2\n : 버튼을 누르면 램프가 켜지고 다시 한번 누\n르면 꺼집니다.'
- 확장 context blocks:
  - bbox `[281.28, 231.87, 353.93, 240.37]`, distance=1.5pt, hgap=0.0pt, vgap=1.5pt, same_column=True: '퍼스널 램프(사양 적용 시)'
  - bbox `[235.16, 349.89, 398.91, 379.37]`, distance=3.1pt, hgap=0.0pt, vgap=3.1pt, same_column=True: '2C_RoomLamp_2\n : 버튼을 누르면 램프가 켜지고 다시 한번 누\n르면 꺼집니다.'
- 확대 문맥 원응답: '퍼스널 램프 버튼'
- 검증 결과: source_supported; 채택값: '퍼스널 램프 버튼'

#### p.224 / image 1

- image bbox: `[221.03, 149.99, 385.42, 254.87]`; candidate: `에어컨 냉매 및 압축기 윤활유량 점`
- 기존 실제 전달 context 필드: ['이 차량은 친환경적인 신냉매 R-1234yf가 적\n용되어 있습니다. 신냉매는 기존에 적용되어\n있던 구냉매 R-134a와 대비하여 지구온난화\n현상을 크게 줄일 수 있습니다. 실제 차량에 사\n용된 냉매 종류와 용량을 알 수 있도록 엔진룸\n에 사양 라벨이 붙어 있습니다.', '냉매량이 부족하면 에어컨의 성능이 저하됩니\n다. 또한 충전을 지나치게 하는 것도 에어컨에\n좋지 않은 영향을 주므로 이상이 발견되면 당사\n직영 하이테크센터나 블루핸즈에서 점검을 받\n으십시오.', '에어컨 냉매 및 압축기 윤활유량 점']
- Terra 원응답: '에어컨 냉매 및 압축기 윤활유량 점검'; 최종값: '에어컨 냉매 및 압축기 윤활유량 점'; disposition: fallback_candidate / new_tokens:점검
- 선택된 text blocks:
  - bbox `[220.98480224609375, 256.4977111816406, 384.7568359375, 325.97308349609375]`, distance=1.6pt, hgap=0.0pt, vgap=1.6pt, same_column=True: '2C_RefrigerantTypeLabel\n이 차량은 친환경적인 신냉매 R-1234yf가 적\n용되어 있습니다. 신냉매는 기존에 적용되어\n있던 구냉매 R-134a와 대비하여 지구온난화\n현상을 크게 줄일 수 있습니다. 실제 차량에 사\n용된 냉매 종류와 용량을 알 수 있도록 엔진룸\n에 사양 라벨이 붙어 있습니다.'
  - bbox `[221.52120971679688, 96.70182037353516, 384.76849365234375, 147.62379455566406]`, distance=2.4pt, hgap=0.0pt, vgap=2.4pt, same_column=True: '냉매량이 부족하면 에어컨의 성능이 저하됩니\n다. 또한 충전을 지나치게 하는 것도 에어컨에\n좋지 않은 영향을 주므로 이상이 발견되면 당사\n직영 하이테크센터나 블루핸즈에서 점검을 받\n으십시오.'
  - bbox `[221.81561279296875, 63.20071792602539, 384.5476989746094, 92.85269165039062]`, distance=57.1pt, hgap=0.0pt, vgap=57.1pt, same_column=True: '에어컨 냉매 및 압축기 윤활유량 점\n검'
- 확장 context blocks:
  - bbox `[221.82, 63.2, 384.55, 92.85]`, distance=57.1pt, hgap=0.0pt, vgap=57.1pt, same_column=True: '에어컨 냉매 및 압축기 윤활유량 점\n검'
  - bbox `[221.52, 96.7, 384.77, 147.62]`, distance=2.4pt, hgap=0.0pt, vgap=2.4pt, same_column=True: '냉매량이 부족하면 에어컨의 성능이 저하됩니\n다. 또한 충전을 지나치게 하는 것도 에어컨에\n좋지 않은 영향을 주므로 이상이 발견되면 당사\n직영 하이테크센터나 블루핸즈에서 점검을 받\n으십시오.'
  - bbox `[220.98, 256.5, 384.76, 325.97]`, distance=1.6pt, hgap=0.0pt, vgap=1.6pt, same_column=True: '2C_RefrigerantTypeLabel\n이 차량은 친환경적인 신냉매 R-1234yf가 적\n용되어 있습니다. 신냉매는 기존에 적용되어\n있던 구냉매 R-134a와 대비하여 지구온난화\n현상을 크게 줄일 수 있습니다. 실제 차량에 사\n용된 냉매 종류와 용량을 알 수 있도록 엔진룸\n에 사양 라벨이 붙어 있습니다.'
- 확대 문맥 원응답: '에어컨 냉매 및 압축기 윤활유량 점검'
- 검증 결과: source_supported; 채택값: '에어컨 냉매 및 압축기 윤활유량 점검'

#### p.230 / image 1

- image bbox: `[36.72, 255.83, 201.11, 360.7]`; candidate: `오토 디포그 (자동 김 서림 제거 기`
- 기존 실제 전달 context 필드: ['히터나 에어컨 작동 상태일 때, 차 앞유리창의\n습기가 감지되면 자동으로 습기를 제거하여 운\n전자의 시야를 확보함으로써 안전 운전을 가능\n하게 하는 기능입니다.', '오토 디포그 (자동 김 서림 제거 기\n능)', '에어컨 자동 건조 기능은 에어컨 냄새를 감\n소시키는 기능으로 약간의 냄새가 남을 수\n있습니다.\n에어컨 자동 건조 기능 작동 중에는 후석 감\n지 기능이 작동하지 않습니다.\n에어컨 자동 건조 기능은 초기 출고 시 기능\n이 활성화되어 있습니다. 기능을 사용하지\n않으시려면 인포테인먼트 시스템의 설정 메\n뉴에서 기능을 설정하십시오.']
- Terra 원응답: '오토 디포그(자동 김 서림 제거 기능)'; 최종값: '오토 디포그 (자동 김 서림 제거 기'; disposition: fallback_candidate / new_tokens:기능
- 선택된 text blocks:
  - bbox `[36.733699798583984, 362.41510009765625, 200.50856018066406, 463.0604248046875]`, distance=1.7pt, hgap=0.0pt, vgap=1.7pt, same_column=True: '2C_AutoDefogSensor\n히터나 에어컨 작동 상태일 때, 차 앞유리창의\n습기가 감지되면 자동으로 습기를 제거하여 운\n전자의 시야를 확보함으로써 안전 운전을 가능\n하게 하는 기능입니다.\nÈ'
  - bbox `[37.576499938964844, 210.84320068359375, 197.40444946289062, 240.5006103515625]`, distance=15.3pt, hgap=0.0pt, vgap=15.3pt, same_column=True: '오토 디포그 (자동 김 서림 제거 기\n능)'
  - bbox `[36.733699798583984, 82.60533142089844, 200.534423828125, 187.4631805419922]`, distance=68.4pt, hgap=0.0pt, vgap=68.4pt, same_column=True: '• 에어컨 자동 건조 기능은 에어컨 냄새를 감\n소시키는 기능으로 약간의 냄새가 남을 수\n있습니다.\n• 에어컨 자동 건조 기능 작동 중에는 후석 감\n지 기능이 작동하지 않습니다.\n• 에어컨 자동 건조 기능은 초기 출고 시 기능\n이 활성화되어 있습니다. 기능을 사용하지\n않으시려면 인포테인먼트 시스템의 설정 메\n뉴에서 기능을 설정하십시오.'
- 확장 context blocks:
  - bbox `[37.58, 27.73, 72.63, 38.93]`, distance=216.9pt, hgap=0.0pt, vgap=216.9pt, same_column=True: '편의 장치'
  - bbox `[36.73, 82.61, 200.53, 187.46]`, distance=68.4pt, hgap=0.0pt, vgap=68.4pt, same_column=True: '• 에어컨 자동 건조 기능은 에어컨 냄새를 감\n소시키는 기능으로 약간의 냄새가 남을 수\n있습니다.\n• 에어컨 자동 건조 기능 작동 중에는 후석 감\n지 기능이 작동하지 않습니다.\n• 에어컨 자동 건조 기능은 초기 출고 시 기능\n이 활성화되어 있습니다. 기능을 사용하지\n않으시려면 인포테인먼트 시스템의 설정 메\n뉴에서 기능을 설정하십시오.'
  - bbox `[37.58, 210.84, 197.4, 240.5]`, distance=15.3pt, hgap=0.0pt, vgap=15.3pt, same_column=True: '오토 디포그 (자동 김 서림 제거 기\n능)'
  - bbox `[36.73, 362.42, 200.51, 463.06]`, distance=1.7pt, hgap=0.0pt, vgap=1.7pt, same_column=True: '2C_AutoDefogSensor\n히터나 에어컨 작동 상태일 때, 차 앞유리창의\n습기가 감지되면 자동으로 습기를 제거하여 운\n전자의 시야를 확보함으로써 안전 운전을 가능\n하게 하는 기능입니다.\nÈ'
  - bbox `[37.35, 471.95, 200.56, 502.87]`, distance=111.2pt, hgap=0.0pt, vgap=111.2pt, same_column=True: '습기가 감지되어 자동 김 서림 제거 장치가 작\n동하면 공조 정보 화면에서 자동 김 서림 제거\n장치가 작동 중임을 확인할 수 있습니다.'
- 확대 문맥 원응답: '오토 디포그(자동 김 서림 제거 기능)'
- 검증 결과: source_supported; 채택값: '오토 디포그(자동 김 서림 제거 기능)'

#### p.271 / image 1

- image bbox: `[50.88, 87.84, 215.27, 192.71]`; candidate: `변속기 냉각 중 안전한 곳에 00분 간 정차하십`
- 기존 실제 전달 context 필드: ["안전한 곳으로 차량을 이동한 후 기어를 'P'(주\n차)로 변속하여 시동이 걸린 상태로 정차하면\n해당 경고문이 클러스터 표시창에 표시됩니다.\n변속기가 충분히 냉각될 때까지 기다리십시\n오.", '변속기 냉각 중 안전한 곳에 00분 간 정차하십\n시오']
- Terra 원응답: '변속기 냉각 중 안전한 곳에 00분간 정차하십시오.'; 최종값: '변속기 냉각 중 안전한 곳에 00분 간 정차하십'; disposition: fallback_candidate / new_tokens:분간,정차하십시오
- 선택된 text blocks:
  - bbox `[50.906898498535156, 193.52590942382812, 215.20736694335938, 257.98541259765625]`, distance=0.8pt, hgap=0.0pt, vgap=0.8pt, same_column=True: "2C_DCTWarningMessageInCluster_3\n안전한 곳으로 차량을 이동한 후 기어를 'P'(주\n차)로 변속하여 시동이 걸린 상태로 정차하면\n해당 경고문이 클러스터 표시창에 표시됩니다.\n• 변속기가 충분히 냉각될 때까지 기다리십시\n오."
  - bbox `[50.89392852783203, 63.71509552001953, 216.912353515625, 84.64012145996094]`, distance=3.2pt, hgap=0.0pt, vgap=3.2pt, same_column=True: '변속기 냉각 중 안전한 곳에 00분 간 정차하십\n시오'
- 확장 context blocks:
  - bbox `[50.89, 63.72, 216.91, 84.64]`, distance=3.2pt, hgap=0.0pt, vgap=3.2pt, same_column=True: '변속기 냉각 중 안전한 곳에 00분 간 정차하십\n시오'
  - bbox `[50.91, 193.53, 215.21, 257.99]`, distance=0.8pt, hgap=0.0pt, vgap=0.8pt, same_column=True: "2C_DCTWarningMessageInCluster_3\n안전한 곳으로 차량을 이동한 후 기어를 'P'(주\n차)로 변속하여 시동이 걸린 상태로 정차하면\n해당 경고문이 클러스터 표시창에 표시됩니다.\n• 변속기가 충분히 냉각될 때까지 기다리십시\n오."
- 확대 문맥 원응답: '변속기 냉각 중 정차 경고'
- 검증 결과: source_supported; 채택값: '변속기 냉각 중 정차 경고'

#### p.308 / image 1

- image bbox: `[220.79, 121.91, 385.42, 227.03]`; candidate: `전방 충돌방지 보조 이상 및 제한 사 · 기능 이상`
- 기존 실제 전달 context 필드: ['전방 충돌방지 보조에 이상이 있으면 클러스터\n등에 경고문이 표시되고 통합 경고등( ), 전방\n안전 경고등(\n)이 켜집니다. 당사 직영 하이테\n크센터나 블루핸즈에서 점검을 받으십시오.\n경고 내용은 클러스터의 뷰 모드 중 유틸리\n티 정보 뷰의 서비스 메시지에서 확인할 수\n있습니다.', '기능 이상', '전방 충돌방지 보조 이상 및 제한 사']
- Terra 원응답: '전방 충돌방지 보조 이상 및 제한 사항'; 최종값: '전방 충돌방지 보조 이상 및 제한 사 · 기능 이상'; disposition: fallback_candidate / new_tokens:사항
- 선택된 text blocks:
  - bbox `[220.98480224609375, 228.75650024414062, 384.8636169433594, 313.2166748046875]`, distance=1.7pt, hgap=0.0pt, vgap=1.7pt, same_column=True: '2C_ForwardSafetyMalfunctionInfo\n전방 충돌방지 보조에 이상이 있으면 클러스터\n등에 경고문이 표시되고 통합 경고등( ), 전방\n안전 경고등(\n)이 켜집니다. 당사 직영 하이테\n크센터나 블루핸즈에서 점검을 받으십시오.\n• 경고 내용은 클러스터의 뷰 모드 중 유틸리\n티 정보 뷰의 서비스 메시지에서 확인할 수\n있습니다.'
  - bbox `[221.68719482421875, 108.49432373046875, 259.627197265625, 120.71432495117188]`, distance=2.1pt, hgap=0.0pt, vgap=1.2pt, same_column=True: '기능 이상'
  - bbox `[221.82760620117188, 63.20071792602539, 384.5717468261719, 92.85269165039062]`, distance=29.1pt, hgap=0.0pt, vgap=29.1pt, same_column=True: '전방 충돌방지 보조 이상 및 제한 사\n항'
- 확장 context blocks:
  - bbox `[221.83, 63.2, 384.57, 92.85]`, distance=29.1pt, hgap=0.0pt, vgap=29.1pt, same_column=True: '전방 충돌방지 보조 이상 및 제한 사\n항'
  - bbox `[221.69, 108.49, 259.63, 120.71]`, distance=1.2pt, hgap=0.0pt, vgap=1.2pt, same_column=True: '기능 이상'
  - bbox `[220.98, 228.76, 384.86, 313.22]`, distance=1.7pt, hgap=0.0pt, vgap=1.7pt, same_column=True: '2C_ForwardSafetyMalfunctionInfo\n전방 충돌방지 보조에 이상이 있으면 클러스터\n등에 경고문이 표시되고 통합 경고등( ), 전방\n안전 경고등(\n)이 켜집니다. 당사 직영 하이테\n크센터나 블루핸즈에서 점검을 받으십시오.\n• 경고 내용은 클러스터의 뷰 모드 중 유틸리\n티 정보 뷰의 서비스 메시지에서 확인할 수\n있습니다.'
- 확대 문맥 원응답: '전방 충돌방지 보조 기능 이상'
- 검증 결과: source_supported; 채택값: '전방 충돌방지 보조 기능 이상'

#### p.328 / image 4

- image bbox: `[221.03, 160.07, 385.42, 264.95]`; candidate: `차로이탈 경고`
- 기존 실제 전달 context 필드: ['좌측', '우측', '차로이탈 경고', '기능 경고 및 제어\n차로 이탈방지 보조는 다음의 동작으로 경고하\n고 제어합니다.\n차로 이탈 경고\n차로 이탈방지 보조']
- Terra 원응답: '차로 이탈 경고'; 최종값: '차로이탈 경고'; disposition: fallback_candidate / new_tokens:이탈,차로
- 선택된 text blocks:
  - bbox `[297.0340881347656, 149.97732543945312, 309.35406494140625, 158.47532653808594]`, distance=1.6pt, hgap=0.0pt, vgap=1.6pt, same_column=True: '좌측'
  - bbox `[220.98480224609375, 267.9992980957031, 309.35406494140625, 285.3465881347656]`, distance=3.6pt, hgap=0.0pt, vgap=3.1pt, same_column=True: '2C_LaneDepartureWarningInfo\n우측'
  - bbox `[220.97183227539062, 136.6874237060547, 274.32281494140625, 147.61341857910156]`, distance=13.3pt, hgap=0.0pt, vgap=12.5pt, same_column=True: '차로이탈 경고'
  - bbox `[220.98480224609375, 63.507598876953125, 384.8646545410156, 127.47761535644531]`, distance=32.6pt, hgap=0.0pt, vgap=32.6pt, same_column=True: '기능 경고 및 제어 \n차로 이탈방지 보조는 다음의 동작으로 경고하\n고 제어합니다.\n• 차로 이탈 경고\n• 차로 이탈방지 보조'
- 확장 context blocks:
  - bbox `[220.98, 63.51, 384.86, 127.48]`, distance=32.6pt, hgap=0.0pt, vgap=32.6pt, same_column=True: '기능 경고 및 제어 \n차로 이탈방지 보조는 다음의 동작으로 경고하\n고 제어합니다.\n• 차로 이탈 경고\n• 차로 이탈방지 보조'
  - bbox `[220.97, 136.69, 274.32, 147.61]`, distance=12.5pt, hgap=0.0pt, vgap=12.5pt, same_column=True: '차로이탈 경고'
  - bbox `[297.03, 149.98, 309.35, 158.48]`, distance=1.6pt, hgap=0.0pt, vgap=1.6pt, same_column=True: '좌측'
  - bbox `[220.98, 268.0, 309.35, 285.35]`, distance=3.1pt, hgap=0.0pt, vgap=3.1pt, same_column=True: '2C_LaneDepartureWarningInfo\n우측'
- 확대 문맥 원응답: '차로이탈 경고'
- 검증 결과: source_supported; 채택값: '차로이탈 경고'

#### p.329 / image 1

- image bbox: `[50.88, 77.04, 215.27, 181.91]`; candidate: `일정 시간 동안 스티어링 휠을 잡지 않으면 단`
- 기존 실제 전달 context 필드: ['일정 시간 동안 스티어링 휠을 잡지 않으면 단\n계적으로 핸즈오프 경고문이 표시되고 경고음\n이 울립니다.҃', '핸즈오프 경고']
- Terra 원응답: '일정 시간 동안 스티어링 휠을 잡지 않으면 단계적으로 핸즈오프 경고문이 표시되고 경고음이 울립니다.'; 최종값: '일정 시간 동안 스티어링 휠을 잡지 않으면 단'; disposition: fallback_candidate / new_tokens:경고문이,경고음이,단계적으로,울립니다,표시되고,핸즈오프
- 선택된 text blocks:
  - bbox `[50.906898498535156, 183.53091430664062, 214.6853790283203, 223.58740234375]`, distance=1.6pt, hgap=0.0pt, vgap=1.6pt, same_column=True: '2C_HandOffWarningInfo\n일정 시간 동안 스티어링 휠을 잡지 않으면 단\n계적으로 핸즈오프 경고문이 표시되고 경고음\n이 울립니다.҃'
  - bbox `[50.89392852783203, 63.71509552001953, 104.00548553466797, 74.64109802246094]`, distance=3.2pt, hgap=0.0pt, vgap=2.4pt, same_column=True: '핸즈오프 경고'
- 확장 context blocks:
  - bbox `[50.89, 63.72, 104.01, 74.64]`, distance=2.4pt, hgap=0.0pt, vgap=2.4pt, same_column=True: '핸즈오프 경고'
  - bbox `[50.91, 183.53, 214.69, 223.59]`, distance=1.6pt, hgap=0.0pt, vgap=1.6pt, same_column=True: '2C_HandOffWarningInfo\n일정 시간 동안 스티어링 휠을 잡지 않으면 단\n계적으로 핸즈오프 경고문이 표시되고 경고음\n이 울립니다.҃'
- 확대 문맥 원응답: '핸즈오프 경고'
- 검증 결과: source_supported; 채택값: '핸즈오프 경고'

#### p.332 / image 2

- image bbox: `[36.72, 388.3, 201.11, 493.18]`; candidate: `후측방에서 빠른 속도로 접근하는 차량을 인식`
- 기존 실제 전달 context 필드: ['후측방에서 빠른 속도로 접근하는 차량을 인식\n하여 알려줍니다.', '위험을 알려주는 시점은 고속으로 접근하는 차\n량의 속도에 따라 다를 수 있습니다.', '경고 영역은 자차의 속도에 따라 변경됩니다.\n단, 사각 지대에 차량이 있더라도 자차가 빠른\n속도로 추월할 경우 경고를 하지 않습니다.']
- Terra 원응답: '후측방에서 빠른 속도로 접근하는 차량을 인식하여 알려줍니다.'; 최종값: '후측방에서 빠른 속도로 접근하는 차량을 인식'; disposition: fallback_candidate / new_tokens:알려줍니다,인식하여
- 선택된 text blocks:
  - bbox `[37.342098236083984, 364.9732971191406, 200.55355834960938, 385.8983154296875]`, distance=2.4pt, hgap=0.0pt, vgap=2.4pt, same_column=True: '후측방에서 빠른 속도로 접근하는 차량을 인식\n하여 알려줍니다.'
  - bbox `[37.342098236083984, 530.1956176757812, 200.49415588378906, 551.12060546875]`, distance=37.0pt, hgap=0.0pt, vgap=37.0pt, same_column=True: '위험을 알려주는 시점은 고속으로 접근하는 차\n량의 속도에 따라 다를 수 있습니다.'
  - bbox `[37.33309555053711, 315.1546936035156, 201.1241455078125, 346.07867431640625]`, distance=42.2pt, hgap=0.0pt, vgap=42.2pt, same_column=True: '경고 영역은 자차의 속도에 따라 변경됩니다.\n단, 사각 지대에 차량이 있더라도 자차가 빠른\n속도로 추월할 경우 경고를 하지 않습니다.'
- 확장 context blocks:
  - bbox `[37.33, 315.15, 201.12, 346.08]`, distance=42.2pt, hgap=0.0pt, vgap=42.2pt, same_column=True: '경고 영역은 자차의 속도에 따라 변경됩니다.\n단, 사각 지대에 차량이 있더라도 자차가 빠른\n속도로 추월할 경우 경고를 하지 않습니다.'
  - bbox `[37.34, 364.97, 200.55, 385.9]`, distance=2.4pt, hgap=0.0pt, vgap=2.4pt, same_column=True: '후측방에서 빠른 속도로 접근하는 차량을 인식\n하여 알려줍니다.'
  - bbox `[37.34, 530.2, 200.49, 551.12]`, distance=37.0pt, hgap=0.0pt, vgap=37.0pt, same_column=True: '위험을 알려주는 시점은 고속으로 접근하는 차\n량의 속도에 따라 다를 수 있습니다.'
- 확대 문맥 원응답: '후측방에서 빠른 속도로 접근하는 차량 인식'
- 검증 결과: source_supported; 채택값: '후측방에서 빠른 속도로 접근하는 차량 인식'

#### p.359 / image 3

- image bbox: `[50.88, 485.02, 62.16, 492.22]`; candidate: `내리면 현재 클러스터의 속도로 크루즈 컨트롤`
- 기존 실제 전달 context 필드: ['일시 해제된 크루즈 컨트롤 기능을\n버튼을\n눌러 재설정하는 경우 주행속도가 해제 직전의\n설정속도로 빠르게 증가하거나 감소할 수 있습\n니다.\n버튼을 사용하기 전에 도로 상황 및\n직전의 설정속도를 확인하십시오.', '일시 해제된 크루즈 컨트롤 기능을\n버튼을\n눌러 재설정하는 경우 주행속도가 해제 직전의\n설정속도로 빠르게 증가하거나 감소할 수 있습\n니다.\n버튼을 사용하기 전에 도로 상황 및\n직전의 설정속도를 확인하십시오.', '버튼을 누르면 직전에 설정했던 속도로 크\n루즈 컨트롤이 작동합니다.\n단, 차량 속도가 30 km/h 미만일 경우에는 작\n동하지 않습니다.', '내리면 현재 클러스터의 속도로 크루즈 컨트롤\n이 작동합니다.']
- Terra 원응답: '내리면 현재 클러스터 속도로 크루즈 컨트롤 작동'; 최종값: '내리면 현재 클러스터의 속도로 크루즈 컨트롤'; disposition: fallback_candidate / new_tokens:작동,클러스터
- 선택된 text blocks:
  - bbox `[235.7034149169922, 84.57538604736328, 399.0289306640625, 135.4973602294922]`, distance=0.7pt, hgap=0.0pt, vgap=0.0pt, same_column=True: '일시 해제된 크루즈 컨트롤 기능을\n 버튼을\n눌러 재설정하는 경우 주행속도가 해제 직전의\n설정속도로 빠르게 증가하거나 감소할 수 있습\n니다. \n 버튼을 사용하기 전에 도로 상황 및\n직전의 설정속도를 확인하십시오.'
  - bbox `[235.7034149169922, 84.57538604736328, 399.0289306640625, 135.4973602294922]`, distance=0.8pt, hgap=0.0pt, vgap=0.0pt, same_column=True: '일시 해제된 크루즈 컨트롤 기능을\n 버튼을\n눌러 재설정하는 경우 주행속도가 해제 직전의\n설정속도로 빠르게 증가하거나 감소할 수 있습\n니다. \n 버튼을 사용하기 전에 도로 상황 및\n직전의 설정속도를 확인하십시오.'
  - bbox `[51.40189743041992, 483.6812744140625, 214.59896850585938, 527.601318359375]`, distance=1.1pt, hgap=0.0pt, vgap=0.0pt, same_column=True: '버튼을 누르면 직전에 설정했던 속도로 크\n루즈 컨트롤이 작동합니다.\n단, 차량 속도가 30 km/h 미만일 경우에는 작\n동하지 않습니다.'
  - bbox `[51.49189758300781, 460.686279296875, 214.52337646484375, 481.611328125]`, distance=4.6pt, hgap=0.0pt, vgap=3.4pt, same_column=True: '내리면 현재 클러스터의 속도로 크루즈 컨트롤\n이 작동합니다.'
- 확장 context blocks:
  - bbox `[235.7, 84.58, 399.03, 135.5]`, distance=0.0pt, hgap=0.0pt, vgap=0.0pt, same_column=True: '일시 해제된 크루즈 컨트롤 기능을\n 버튼을\n눌러 재설정하는 경우 주행속도가 해제 직전의\n설정속도로 빠르게 증가하거나 감소할 수 있습\n니다. \n 버튼을 사용하기 전에 도로 상황 및\n직전의 설정속도를 확인하십시오.'
  - bbox `[51.49, 460.69, 214.52, 481.61]`, distance=3.4pt, hgap=0.0pt, vgap=3.4pt, same_column=True: '내리면 현재 클러스터의 속도로 크루즈 컨트롤\n이 작동합니다.'
  - bbox `[51.4, 483.68, 214.6, 527.6]`, distance=0.0pt, hgap=0.0pt, vgap=0.0pt, same_column=True: '버튼을 누르면 직전에 설정했던 속도로 크\n루즈 컨트롤이 작동합니다.\n단, 차량 속도가 30 km/h 미만일 경우에는 작\n동하지 않습니다.'
- 확대 문맥 원응답: '– 스위치를 아래로 내려 현재 속도로 크루즈 컨트롤 작동'
- 검증 결과: outside_candidate_and_source:스위치를,내려,아래로; 채택값: '내리면 현재 클러스터의 속도로 크루즈 컨트롤'

#### p.390 / image 1

- image bbox: `[36.72, 107.04, 201.11, 211.91]`; candidate: `주차/뷰 버튼(1)을 누르면 서라운드 뷰 모니터`
- 기존 실제 전달 context 필드: ['주차/뷰 버튼', '주차/뷰 버튼(1)을 누르면 서라운드 뷰 모니터\n를 켜거나 끌 수 있습니다.', '서라운드 뷰 모니터 작동', '운전자 보조']
- Terra 원응답: '주차/뷰 버튼(1)을 누르면 서라운드 뷰 모니터 작동'; 최종값: '주차/뷰 버튼(1)을 누르면 서라운드 뷰 모니터'; disposition: fallback_candidate / new_tokens:작동
- 선택된 text blocks:
  - bbox `[37.436100006103516, 93.50091552734375, 88.40609741210938, 105.72091674804688]`, distance=2.2pt, hgap=0.0pt, vgap=1.3pt, same_column=True: '주차/뷰 버튼'
  - bbox `[36.733699798583984, 215.02371215820312, 200.37355041503906, 244.5030059814453]`, distance=3.1pt, hgap=0.0pt, vgap=3.1pt, same_column=True: '2C_ParkingViewButton\n주차/뷰 버튼(1)을 누르면 서라운드 뷰 모니터\n를 켜거나 끌 수 있습니다.'
  - bbox `[37.576499938964844, 63.20071792602539, 153.0885009765625, 77.86471557617188]`, distance=29.5pt, hgap=0.0pt, vgap=29.2pt, same_column=True: '서라운드 뷰 모니터 작동'
  - bbox `[37.58409881591797, 27.730823516845703, 80.79295349121094, 38.93132400512695]`, distance=69.0pt, hgap=0.0pt, vgap=68.1pt, same_column=True: '운전자 보조'
- 확장 context blocks:
  - bbox `[37.58, 27.73, 80.79, 38.93]`, distance=68.1pt, hgap=0.0pt, vgap=68.1pt, same_column=True: '운전자 보조'
  - bbox `[37.58, 63.2, 153.09, 77.86]`, distance=29.2pt, hgap=0.0pt, vgap=29.2pt, same_column=True: '서라운드 뷰 모니터 작동'
  - bbox `[37.44, 93.5, 88.41, 105.72]`, distance=1.3pt, hgap=0.0pt, vgap=1.3pt, same_column=True: '주차/뷰 버튼'
  - bbox `[36.73, 215.02, 200.37, 244.5]`, distance=3.1pt, hgap=0.0pt, vgap=3.1pt, same_column=True: '2C_ParkingViewButton\n주차/뷰 버튼(1)을 누르면 서라운드 뷰 모니터\n를 켜거나 끌 수 있습니다.'
- 확대 문맥 원응답: '주차/뷰 버튼으로 서라운드 뷰 모니터 켜기 및 끄기'
- 검증 결과: outside_candidate_and_source:끄기,및,켜기; 채택값: '주차/뷰 버튼(1)을 누르면 서라운드 뷰 모니터'

#### p.476 / image 3

- image bbox: `[36.72, 315.59, 107.52, 386.38]`; candidate: `배터리 내부에는 점화율이 매우 높은 수소가 항`
- 기존 실제 전달 context 필드: ['배터리 내부에는 점화율이 매우 높은 수소가 항\n상 존재하여 불꽃이 점화되면 폭발할 수 있습니\n다.', '배터리가 어린이의 손에 닿지 않게 하십시오.']
- Terra 원응답: '배터리 내부에는 점화율이 매우 높은 수소가 항상 존재합니다.'; 최종값: '배터리 내부에는 점화율이 매우 높은 수소가 항'; disposition: fallback_candidate / new_tokens:존재합니다,항상
- 선택된 text blocks:
  - bbox `[37.36909866333008, 282.279296875, 200.52117919921875, 313.20330810546875]`, distance=3.1pt, hgap=0.0pt, vgap=2.4pt, same_column=True: '배터리 내부에는 점화율이 매우 높은 수소가 항\n상 존재하여 불꽃이 점화되면 폭발할 수 있습니\n다.'
  - bbox `[37.36909866333008, 396.55902099609375, 198.47544860839844, 407.48504638671875]`, distance=10.9pt, hgap=0.0pt, vgap=10.2pt, same_column=True: '배터리가 어린이의 손에 닿지 않게 하십시오.'
- 확장 context blocks:
  - bbox `[37.37, 282.28, 200.52, 313.2]`, distance=2.4pt, hgap=0.0pt, vgap=2.4pt, same_column=True: '배터리 내부에는 점화율이 매우 높은 수소가 항\n상 존재하여 불꽃이 점화되면 폭발할 수 있습니\n다.'
  - bbox `[37.37, 396.56, 198.48, 407.49]`, distance=10.2pt, hgap=0.0pt, vgap=10.2pt, same_column=True: '배터리가 어린이의 손에 닿지 않게 하십시오.'
- 확대 문맥 원응답: '배터리 내부 수소 폭발 경고'
- 검증 결과: outside_candidate_and_source:경고; 채택값: '배터리 내부에는 점화율이 매우 높은 수소가 항'

### C. 후보와 동일하게 반환한 대표 사례 10건

#### p.44 / image 2

- image bbox: `[221.03, 77.04, 385.42, 181.91]`; candidate: `등받이 각도 조절하기`
- 기존 실제 전달 context 필드: ['1. 좌석에 앉아 등을 약간 앞으로 숙인 상태에\n서 좌석 바깥쪽에 위치한 좌석 각도 조절 레\n버를 위로 당기십시오.\n2. 조심해서 좌석에 기대어 원하는 위치로 조절\n하십시오.\n3. 조절 레버를 놓으면 고정됩니다.\n4. 등받이가 확실하게 고정됐는지 확인하십시\n오.', '등받이 각도 조절하기']
- Terra 원응답: '등받이 각도 조절하기'; 최종값: '등받이 각도 조절하기'; disposition: llm_accepted / accepted
- 선택된 text blocks:
  - bbox `[220.83181762695312, 183.53091430664062, 384.8593444824219, 281.99530029296875]`, distance=1.6pt, hgap=0.0pt, vgap=1.6pt, same_column=True: '2C_AdjustSeatBackmanual\n1. 좌석에 앉아 등을 약간 앞으로 숙인 상태에\n서 좌석 바깥쪽에 위치한 좌석 각도 조절 레\n버를 위로 당기십시오.\n2. 조심해서 좌석에 기대어 원하는 위치로 조절\n하십시오.\n3. 조절 레버를 놓으면 고정됩니다.\n4. 등받이가 확실하게 고정됐는지 확인하십시\n오.'
  - bbox `[220.97183227539062, 63.71509552001953, 300.62615966796875, 74.64109802246094]`, distance=3.0pt, hgap=0.0pt, vgap=2.4pt, same_column=True: '등받이 각도 조절하기'
- 확장 context blocks:
  - bbox `[220.97, 63.72, 300.63, 74.64]`, distance=2.4pt, hgap=0.0pt, vgap=2.4pt, same_column=True: '등받이 각도 조절하기'
  - bbox `[220.83, 183.53, 384.86, 282.0]`, distance=1.6pt, hgap=0.0pt, vgap=1.6pt, same_column=True: '2C_AdjustSeatBackmanual\n1. 좌석에 앉아 등을 약간 앞으로 숙인 상태에\n서 좌석 바깥쪽에 위치한 좌석 각도 조절 레\n버를 위로 당기십시오.\n2. 조심해서 좌석에 기대어 원하는 위치로 조절\n하십시오.\n3. 조절 레버를 놓으면 고정됩니다.\n4. 등받이가 확실하게 고정됐는지 확인하십시\n오.'
- 확대 문맥 원응답: '등받이 각도 조절하기'
- 검증 결과: source_supported; 채택값: '등받이 각도 조절하기'

#### p.106 / image 1

- image bbox: `[36.72, 77.04, 201.35, 182.15]`; candidate: `주유 후 정보 · 클러스터`
- 기존 실제 전달 context 필드: ['주유 이후의 주행 거리, 주행 시간, 주행 연비가\n표시됩니다.\n정보를 초기화하려면 스티어링 휠의 OK 버튼\n을 길게 누르십시오.\n기계식 주차 타워 이용 등으로 주차 후 연료가\n과도하게 출렁인 경우에는 주유 후 정보가 초기\n화될 수 있습니다.', '주유 후 정보', '클러스터']
- Terra 원응답: '주유 후 정보 · 클러스터'; 최종값: '주유 후 정보 · 클러스터'; disposition: llm_accepted / accepted
- 선택된 text blocks:
  - bbox `[36.733699798583984, 183.53091430664062, 200.52651977539062, 268.999267578125]`, distance=1.4pt, hgap=0.0pt, vgap=1.4pt, same_column=True: '2C_InfoAfterRefuel\n주유 이후의 주행 거리, 주행 시간, 주행 연비가\n표시됩니다.\n정보를 초기화하려면 스티어링 휠의 OK 버튼\n을 길게 누르십시오.\n기계식 주차 타워 이용 등으로 주차 후 연료가\n과도하게 출렁인 경우에는 주유 후 정보가 초기\n화될 수 있습니다.'
  - bbox `[36.72072982788086, 63.71509552001953, 83.85629272460938, 74.64109802246094]`, distance=3.3pt, hgap=0.0pt, vgap=2.4pt, same_column=True: '주유 후 정보'
  - bbox `[37.58409881591797, 27.730823516845703, 70.23275756835938, 38.93132400512695]`, distance=39.1pt, hgap=0.0pt, vgap=38.1pt, same_column=True: '클러스터'
- 확장 context blocks:
  - bbox `[37.58, 27.73, 70.23, 38.93]`, distance=38.1pt, hgap=0.0pt, vgap=38.1pt, same_column=True: '클러스터'
  - bbox `[36.72, 63.72, 83.86, 74.64]`, distance=2.4pt, hgap=0.0pt, vgap=2.4pt, same_column=True: '주유 후 정보'
  - bbox `[36.73, 183.53, 200.53, 269.0]`, distance=1.4pt, hgap=0.0pt, vgap=1.4pt, same_column=True: '2C_InfoAfterRefuel\n주유 이후의 주행 거리, 주행 시간, 주행 연비가\n표시됩니다.\n정보를 초기화하려면 스티어링 휠의 OK 버튼\n을 길게 누르십시오.\n기계식 주차 타워 이용 등으로 주차 후 연료가\n과도하게 출렁인 경우에는 주유 후 정보가 초기\n화될 수 있습니다.'
- 확대 문맥 원응답: '주유 후 정보'
- 검증 결과: source_supported; 채택값: '주유 후 정보'

#### p.141 / image 1

- image bbox: `[50.88, 107.04, 215.27, 211.91]`; candidate: `스티어링 휠(A타입) · 클러스터`
- 기존 실제 전달 context 필드: ['클러스터', '스티어링 휠(A타입)', '다.', '이 표시될 때 스티어링 휠에 있는 OK 버튼\n[A]을 누르십시오. 2차 알림이 1회 해제됩니']
- Terra 원응답: '스티어링 휠(A타입) · 클러스터'; 최종값: '스티어링 휠(A타입) · 클러스터'; disposition: llm_accepted / accepted
- 선택된 text blocks:
  - bbox `[120.65609741210938, 96.99502563476562, 145.45570373535156, 105.49302673339844]`, distance=1.5pt, hgap=0.0pt, vgap=1.5pt, same_column=True: '클러스터'
  - bbox `[50.906898498535156, 215.01712036132812, 160.7431182861328, 232.3643035888672]`, distance=3.5pt, hgap=0.0pt, vgap=3.1pt, same_column=True: '2C_CheckRearSeat\n스티어링 휠(A타입)'
  - bbox `[60.01920700073242, 83.71314239501953, 70.72920989990234, 94.63914489746094]`, distance=13.4pt, hgap=0.0pt, vgap=12.4pt, same_column=True: '다.'
  - bbox `[59.38920593261719, 63.71509552001953, 214.72561645507812, 84.64012145996094]`, distance=22.5pt, hgap=0.0pt, vgap=22.4pt, same_column=True: '이 표시될 때 스티어링 휠에 있는 OK 버튼\n[A]을 누르십시오. 2차 알림이 1회 해제됩니'
- 확장 context blocks:
  - bbox `[59.39, 63.72, 214.73, 84.64]`, distance=22.4pt, hgap=0.0pt, vgap=22.4pt, same_column=True: '이 표시될 때 스티어링 휠에 있는 OK 버튼\n[A]을 누르십시오. 2차 알림이 1회 해제됩니'
  - bbox `[60.02, 83.71, 70.73, 94.64]`, distance=12.4pt, hgap=0.0pt, vgap=12.4pt, same_column=True: '다.'
  - bbox `[120.66, 97.0, 145.46, 105.49]`, distance=1.5pt, hgap=0.0pt, vgap=1.5pt, same_column=True: '클러스터'
  - bbox `[50.91, 215.02, 160.74, 232.36]`, distance=3.1pt, hgap=0.0pt, vgap=3.1pt, same_column=True: '2C_CheckRearSeat\n스티어링 휠(A타입)'
- 확대 문맥 원응답: '스티어링 휠(A타입) 및 클러스터'
- 검증 결과: outside_candidate_and_source:및; 채택값: '스티어링 휠(A타입) · 클러스터'

#### p.228 / image 1

- image bbox: `[36.72, 77.04, 201.11, 181.91]`; candidate: `실외 측 유리 성에 제거 방법 · 편의 장치`
- 기존 실제 전달 context 필드: ['실외 측 유리 성에 제거 방법', '(1) 풍량 조절 버튼을 눌러 풍량을 최대로 설정', '하십시오.\n(2) 온도 조절 노브를 돌려 최대 온도로 설정하', '편의 장치', '십시오.\n(3) 앞유리 서리 제거 버튼을 누르십시오.\n(4) 외기 유입이 자동으로 선택되며 외부 온도']
- Terra 원응답: '실외 측 유리 성에 제거 방법 · 편의 장치'; 최종값: '실외 측 유리 성에 제거 방법 · 편의 장치'; disposition: llm_accepted / accepted
- 선택된 text blocks:
  - bbox `[37.436100006103516, 63.507598876953125, 147.01608276367188, 75.72760009765625]`, distance=1.7pt, hgap=0.0pt, vgap=1.3pt, same_column=True: '실외 측 유리 성에 제거 방법'
  - bbox `[36.733699798583984, 200.08473205566406, 197.65016174316406, 211.01072692871094]`, distance=18.2pt, hgap=0.0pt, vgap=18.2pt, same_column=True: '(1) 풍량 조절 버튼을 눌러 풍량을 최대로 설정'
  - bbox `[36.688697814941406, 210.08372497558594, 198.83815002441406, 234.00572204589844]`, distance=28.2pt, hgap=0.0pt, vgap=28.2pt, same_column=True: '하십시오.\n(2) 온도 조절 노브를 돌려 최대 온도로 설정하'
  - bbox `[37.58409881591797, 27.730823516845703, 72.6333999633789, 38.93132400512695]`, distance=39.1pt, hgap=0.0pt, vgap=38.1pt, same_column=True: '편의 장치'
  - bbox `[36.62569808959961, 233.07872009277344, 197.31715393066406, 269.9967041015625]`, distance=51.2pt, hgap=0.0pt, vgap=51.2pt, same_column=True: '십시오.\n(3) 앞유리 서리 제거 버튼을 누르십시오. \n(4) 외기 유입이 자동으로 선택되며 외부 온도'
- 확장 context blocks:
  - bbox `[37.58, 27.73, 72.63, 38.93]`, distance=38.1pt, hgap=0.0pt, vgap=38.1pt, same_column=True: '편의 장치'
  - bbox `[37.44, 63.51, 147.02, 75.73]`, distance=1.3pt, hgap=0.0pt, vgap=1.3pt, same_column=True: '실외 측 유리 성에 제거 방법'
  - bbox `[36.73, 200.08, 197.65, 211.01]`, distance=18.2pt, hgap=0.0pt, vgap=18.2pt, same_column=True: '(1) 풍량 조절 버튼을 눌러 풍량을 최대로 설정'
  - bbox `[36.69, 210.08, 198.84, 234.01]`, distance=28.2pt, hgap=0.0pt, vgap=28.2pt, same_column=True: '하십시오.\n(2) 온도 조절 노브를 돌려 최대 온도로 설정하'
  - bbox `[36.63, 233.08, 197.32, 270.0]`, distance=51.2pt, hgap=0.0pt, vgap=51.2pt, same_column=True: '십시오.\n(3) 앞유리 서리 제거 버튼을 누르십시오. \n(4) 외기 유입이 자동으로 선택되며 외부 온도'
- 확대 문맥 원응답: '실외 측 유리 성에 제거 방법'
- 검증 결과: source_supported; 채택값: '실외 측 유리 성에 제거 방법'

#### p.325 / image 1

- image bbox: `[50.88, 208.07, 215.27, 434.86]`; candidate: `[B] 차로변경 차량 및 이륜차`
- 기존 실제 전달 context 필드: ['[A] 자차\n[B] 차로변경 차량 및 이륜차', '오르막길이나 내리막길에서는 전방에 있는\n차량, 이륜차, 보행자 및 자전거 탑승자를 인\n식하지 못하여 경고, 제동을 도와주지 않을\n수 있습니다.\n또한 선행 차량, 이륜차, 보행자 및 자전거 탑\n승자를 갑자기 인식하여 속도가 빠르게 감속\n할 수 있습니다.\n오르막길이나 내리막길에서는 전방 도로 상\n황 및 주행 상태를 확인하고 주의하여 운전\n하십시오. 필요하면 브레이크 페달을 밟아\n직접 속도를 조절하거나 스티어링 휠을 조작\n하십시오.\n차로변경 시', '옆 차로의 차량 및 이륜차[B]가 자차[A]와 같\n은 차로로 차로를 변경할 때 센서의 감지 범\n위 안으로 들어올 때까지 차량 및 이륜차[B]\n를 인식하지 못할 수 있습니다. 갑자기 끼어\n드는 차량 및 이륜차는 센서가 늦게 인식할\n수 있습니다. 항상 전방 도로 상황 및 주행 상\n태를 확인하고 주의하여 운전하십시오. 필요\n하면 브레이크 페달을 밟아 직접 속도를 조\n절하거나 스티어링 휠을 조작하십시오.']
- Terra 원응답: '[B] 차로변경 차량 및 이륜차'; 최종값: '[B] 차로변경 차량 및 이륜차'; disposition: llm_accepted / accepted
- 선택된 text blocks:
  - bbox `[50.906898498535156, 436.389404296875, 139.7540740966797, 465.7951965332031]`, distance=2.1pt, hgap=0.0pt, vgap=1.5pt, same_column=True: '2C_FCAChangingLane\n[A] 자차\n[B] 차로변경 차량 및 이륜차'
  - bbox `[50.906898498535156, 63.71509552001953, 214.72567749023438, 205.4395294189453]`, distance=2.6pt, hgap=0.0pt, vgap=2.6pt, same_column=True: '오르막길이나 내리막길에서는 전방에 있는\n차량, 이륜차, 보행자 및 자전거 탑승자를 인\n식하지 못하여 경고, 제동을 도와주지 않을\n수 있습니다. \n또한 선행 차량, 이륜차, 보행자 및 자전거 탑\n승자를 갑자기 인식하여 속도가 빠르게 감속\n할 수 있습니다.\n오르막길이나 내리막길에서는 전방 도로 상\n황 및 주행 상태를 확인하고 주의하여 운전\n하십시오. 필요하면 브레이크 페달을 밟아\n직접 속도를 조절하거나 스티어링 휠을 조작\n하십시오. \n• 차로변경 시'
  - bbox `[59.8302001953125, 466.9349060058594, 215.25396728515625, 557.8529663085938]`, distance=32.1pt, hgap=0.0pt, vgap=32.1pt, same_column=True: '옆 차로의 차량 및 이륜차[B]가 자차[A]와 같\n은 차로로 차로를 변경할 때 센서의 감지 범\n위 안으로 들어올 때까지 차량 및 이륜차[B]\n를 인식하지 못할 수 있습니다. 갑자기 끼어\n드는 차량 및 이륜차는 센서가 늦게 인식할\n수 있습니다. 항상 전방 도로 상황 및 주행 상\n태를 확인하고 주의하여 운전하십시오. 필요\n하면 브레이크 페달을 밟아 직접 속도를 조\n절하거나 스티어링 휠을 조작하십시오.'
- 확장 context blocks:
  - bbox `[50.91, 63.72, 214.73, 205.44]`, distance=2.6pt, hgap=0.0pt, vgap=2.6pt, same_column=True: '오르막길이나 내리막길에서는 전방에 있는\n차량, 이륜차, 보행자 및 자전거 탑승자를 인\n식하지 못하여 경고, 제동을 도와주지 않을\n수 있습니다. \n또한 선행 차량, 이륜차, 보행자 및 자전거 탑\n승자를 갑자기 인식하여 속도가 빠르게 감속\n할 수 있습니다.\n오르막길이나 내리막길에서는 전방 도로 상\n황 및 주행 상태를 확인하고 주의하여 운전\n하십시오. 필요하면 브레이크 페달을 밟아\n직접 속도를 조절하거나 스티어링 휠을 조작\n하십시오. \n• 차로변경 시'
  - bbox `[50.91, 436.39, 139.75, 465.8]`, distance=1.5pt, hgap=0.0pt, vgap=1.5pt, same_column=True: '2C_FCAChangingLane\n[A] 자차\n[B] 차로변경 차량 및 이륜차'
  - bbox `[59.83, 466.93, 215.25, 557.85]`, distance=32.1pt, hgap=0.0pt, vgap=32.1pt, same_column=True: '옆 차로의 차량 및 이륜차[B]가 자차[A]와 같\n은 차로로 차로를 변경할 때 센서의 감지 범\n위 안으로 들어올 때까지 차량 및 이륜차[B]\n를 인식하지 못할 수 있습니다. 갑자기 끼어\n드는 차량 및 이륜차는 센서가 늦게 인식할\n수 있습니다. 항상 전방 도로 상황 및 주행 상\n태를 확인하고 주의하여 운전하십시오. 필요\n하면 브레이크 페달을 밟아 직접 속도를 조\n절하거나 스티어링 휠을 조작하십시오.'
- 확대 문맥 원응답: '차로변경 차량 및 이륜차'
- 검증 결과: source_supported; 채택값: '차로변경 차량 및 이륜차'

#### p.359 / image 2

- image bbox: `[50.88, 335.75, 215.27, 440.62]`; candidate: `일시 해제 후 다시 켜기`
- 기존 실제 전달 context 필드: ['+ 스위치를 위로 올리거나 – 스위치를 아래로', '일시 해제 후 다시 켜기', '위의 상황 이외에 크루즈 컨트롤이 자동으로 일\n시 해제된 경우에는 당사 직영 하이테크센터나\n블루핸즈에서 점검을 받으십시오.']
- Terra 원응답: '일시 해제 후 다시 켜기'; 최종값: '일시 해제 후 다시 켜기'; disposition: llm_accepted / accepted
- 선택된 text blocks:
  - bbox `[50.906898498535156, 442.1329040527344, 214.5503387451172, 461.61334228515625]`, distance=1.5pt, hgap=0.0pt, vgap=1.5pt, same_column=True: '2C_SpeedControlResuming\n+ 스위치를 위로 올리거나 – 스위치를 아래로'
  - bbox `[51.749698638916016, 316.8044128417969, 159.12567138671875, 331.4684143066406]`, distance=4.7pt, hgap=0.0pt, vgap=4.3pt, same_column=True: '일시 해제 후 다시 켜기'
  - bbox `[51.51530075073242, 262.5002136230469, 214.69436645507812, 293.4241943359375]`, distance=42.3pt, hgap=0.0pt, vgap=42.3pt, same_column=True: '위의 상황 이외에 크루즈 컨트롤이 자동으로 일\n시 해제된 경우에는 당사 직영 하이테크센터나\n블루핸즈에서 점검을 받으십시오.'
- 확장 context blocks:
  - bbox `[51.52, 262.5, 214.69, 293.42]`, distance=42.3pt, hgap=0.0pt, vgap=42.3pt, same_column=True: '위의 상황 이외에 크루즈 컨트롤이 자동으로 일\n시 해제된 경우에는 당사 직영 하이테크센터나\n블루핸즈에서 점검을 받으십시오.'
  - bbox `[51.75, 316.8, 159.13, 331.47]`, distance=4.3pt, hgap=0.0pt, vgap=4.3pt, same_column=True: '일시 해제 후 다시 켜기'
  - bbox `[50.91, 442.13, 214.55, 461.61]`, distance=1.5pt, hgap=0.0pt, vgap=1.5pt, same_column=True: '2C_SpeedControlResuming\n+ 스위치를 위로 올리거나 – 스위치를 아래로'
- 확대 문맥 원응답: '크루즈 컨트롤 일시 해제 후 다시 켜기'
- 검증 결과: source_supported; 채택값: '크루즈 컨트롤 일시 해제 후 다시 켜기'

#### p.378 / image 4

- image bbox: `[36.72, 320.39, 201.11, 425.26]`; candidate: `차로 유지 보조`
- 기존 실제 전달 context 필드: ['양쪽 차선 또는 선행 차량을 인식하고 차량의\n속도가 200 km/h 이하인 경우 차로 중앙을 유\n지하며 주행하도록 조향을 도와줍니다. 클러스\n터 표시창에 표시등( )이 초록색으로 표시됩\n니다.', '차로 유지 보조', '기능 경고 및 제어']
- Terra 원응답: '차로 유지 보조'; 최종값: '차로 유지 보조'; disposition: llm_accepted / accepted
- 선택된 text blocks:
  - bbox `[36.733699798583984, 426.8699951171875, 200.50318908691406, 486.3463134765625]`, distance=1.6pt, hgap=0.0pt, vgap=1.6pt, same_column=True: '2C_LKALaneDetectInfo\n양쪽 차선 또는 선행 차량을 인식하고 차량의\n속도가 200 km/h 이하인 경우 차로 중앙을 유\n지하며 주행하도록 조향을 도와줍니다. 클러스\n터 표시창에 표시등( )이 초록색으로 표시됩\n니다.'
  - bbox `[36.72072982788086, 307.0541076660156, 92.19569396972656, 317.9801025390625]`, distance=3.2pt, hgap=0.0pt, vgap=2.4pt, same_column=True: '차로 유지 보조'
  - bbox `[37.436100006103516, 286.8523254394531, 106.81608581542969, 299.07232666015625]`, distance=22.0pt, hgap=0.0pt, vgap=21.3pt, same_column=True: '기능 경고 및 제어'
- 확장 context blocks:
  - bbox `[37.44, 286.85, 106.82, 299.07]`, distance=21.3pt, hgap=0.0pt, vgap=21.3pt, same_column=True: '기능 경고 및 제어'
  - bbox `[36.72, 307.05, 92.2, 317.98]`, distance=2.4pt, hgap=0.0pt, vgap=2.4pt, same_column=True: '차로 유지 보조'
  - bbox `[36.73, 426.87, 200.5, 486.35]`, distance=1.6pt, hgap=0.0pt, vgap=1.6pt, same_column=True: '2C_LKALaneDetectInfo\n양쪽 차선 또는 선행 차량을 인식하고 차량의\n속도가 200 km/h 이하인 경우 차로 중앙을 유\n지하며 주행하도록 조향을 도와줍니다. 클러스\n터 표시창에 표시등( )이 초록색으로 표시됩\n니다.'
- 확대 문맥 원응답: '차로 유지 보조'
- 검증 결과: source_supported; 채택값: '차로 유지 보조'

#### p.406 / image 6

- image bbox: `[83.76, 184.07, 103.68, 203.99]`; candidate: `삐-삐-삐`
- 기존 실제 전달 context 필드: ['60 cm\n삐-삐-삐-']
- Terra 원응답: '삐-삐-삐'; 최종값: '삐-삐-삐'; disposition: llm_accepted / accepted
- 선택된 text blocks:
  - bbox `[42.01079559326172, 182.55343627929688, 195.9712677001953, 204.36444091796875]`, distance=0.4pt, hgap=0.0pt, vgap=0.0pt, same_column=True: '30 – \n60 cm\n삐-삐-삐-'
- 확장 context blocks:
  - bbox `[42.01, 182.55, 195.97, 204.36]`, distance=0.0pt, hgap=0.0pt, vgap=0.0pt, same_column=True: '30 – \n60 cm\n삐-삐-삐-'
- 확대 문맥 원응답: '60 cm 거리의 삐-삐-삐- 경고음'
- 검증 결과: outside_candidate_and_source:거리의,경고음; 채택값: '삐-삐-삐'

#### p.412 / image 1

- image bbox: `[36.72, 84.96, 201.11, 189.83]`; candidate: `운전자 보조`
- 기존 실제 전달 context 필드: ['주차 충돌방지 보조가 작동 중일 때 기능 이상\n이나 초음파센서의 가림이 발생하면 대상 방향\n에 통합 경고등( )이 표시 됩니다. 클러스터 표\n시창 중 유틸리티 정보 뷰의 서비스 메시지에서\n확인할 수 있습니다.', '운전자 보조']
- Terra 원응답: '운전자 보조'; 최종값: '운전자 보조'; disposition: llm_accepted / accepted
- 선택된 text blocks:
  - bbox `[36.733699798583984, 191.39291381835938, 200.57156372070312, 250.86927795410156]`, distance=1.6pt, hgap=0.0pt, vgap=1.6pt, same_column=True: '2C_PCAInfo\n주차 충돌방지 보조가 작동 중일 때 기능 이상\n이나 초음파센서의 가림이 발생하면 대상 방향\n에 통합 경고등( )이 표시 됩니다. 클러스터 표\n시창 중 유틸리티 정보 뷰의 서비스 메시지에서\n확인할 수 있습니다.'
  - bbox `[37.58409881591797, 27.730823516845703, 80.79295349121094, 38.93132400512695]`, distance=46.9pt, hgap=0.0pt, vgap=46.0pt, same_column=True: '운전자 보조'
- 확장 context blocks:
  - bbox `[37.58, 27.73, 80.79, 38.93]`, distance=46.0pt, hgap=0.0pt, vgap=46.0pt, same_column=True: '운전자 보조'
  - bbox `[36.73, 191.39, 200.57, 250.87]`, distance=1.6pt, hgap=0.0pt, vgap=1.6pt, same_column=True: '2C_PCAInfo\n주차 충돌방지 보조가 작동 중일 때 기능 이상\n이나 초음파센서의 가림이 발생하면 대상 방향\n에 통합 경고등( )이 표시 됩니다. 클러스터 표\n시창 중 유틸리티 정보 뷰의 서비스 메시지에서\n확인할 수 있습니다.'
- 확대 문맥 원응답: '운전자 보조 통합 경고등'
- 검증 결과: source_supported; 채택값: '운전자 보조 통합 경고등'

#### p.490 / image 4

- image bbox: `[221.03, 96.96, 385.42, 201.83]`; candidate: `선바이저 램프/글로브 박스 램프/트렁크`
- 기존 실제 전달 context 필드: ['선바이저 램프', '글로브 박스 램프', '선바이저 램프/글로브 박스 램프/트렁크\n룸 램프(벌브 타입)']
- Terra 원응답: '선바이저 램프/글로브 박스 램프/트렁크'; 최종값: '선바이저 램프/글로브 박스 램프/트렁크'; disposition: llm_accepted / accepted
- 선택된 text blocks:
  - bbox `[283.61279296875, 86.99893188476562, 322.9505920410156, 95.49693298339844]`, distance=1.5pt, hgap=0.0pt, vgap=1.5pt, same_column=True: '선바이저 램프'
  - bbox `[220.98480224609375, 205.02090454101562, 326.6773986816406, 222.3682098388672]`, distance=3.6pt, hgap=0.0pt, vgap=3.2pt, same_column=True: '2C_SunvisorLampChange\n글로브 박스 램프'
  - bbox `[221.68719482421875, 63.507598876953125, 383.4073181152344, 85.71759033203125]`, distance=11.2pt, hgap=0.0pt, vgap=11.2pt, same_column=True: '선바이저 램프/글로브 박스 램프/트렁크 \n룸 램프(벌브 타입)'
- 확장 context blocks:
  - bbox `[221.69, 63.51, 383.41, 85.72]`, distance=11.2pt, hgap=0.0pt, vgap=11.2pt, same_column=True: '선바이저 램프/글로브 박스 램프/트렁크 \n룸 램프(벌브 타입)'
  - bbox `[283.61, 87.0, 322.95, 95.5]`, distance=1.5pt, hgap=0.0pt, vgap=1.5pt, same_column=True: '선바이저 램프'
  - bbox `[220.98, 205.02, 326.68, 222.37]`, distance=3.2pt, hgap=0.0pt, vgap=3.2pt, same_column=True: '2C_SunvisorLampChange\n글로브 박스 램프'
- 확대 문맥 원응답: '선바이저 램프 및 글로브 박스 램프'
- 검증 결과: outside_candidate_and_source:및; 채택값: '선바이저 램프/글로브 박스 램프/트렁크'

## 57건 전체 상세 block 로그

### p.25 / image 3

- image bbox: `[235.19, 84.0, 399.58, 188.87]`; candidate: 옆 센터 필러에 부착된 라벨 안에 표기되어 있
- A LLM 전달 context 필드: ['본 차량의 권장 타이어 공기압 정보는 운전석\n옆 센터 필러에 부착된 라벨 안에 표기되어 있\n습니다.', '타이어 공기압']
- B LLM 전달 text (63자): '타이어 공기압\n본 차량의 권장 타이어 공기압 정보는 운전석 옆 센터 필러에 부착된 라벨 안에 표기되어 있 습니다.'
- A 결과: '옆 센터 필러에 부착된 라벨에 표기되어 있습니다.' → '옆 센터 필러에 부착된 라벨 안에 표기되어 있' (fallback_candidate / new_tokens:라벨에,있습니다)
- B 결과: '운전석 옆 센터 필러의 권장 타이어 공기압 라벨' → '옆 센터 필러에 부착된 라벨 안에 표기되어 있' (outside_candidate_and_source:필러의)
- blocks (current/expanded/excluded):
  - expanded; bbox `[235.16, 190.53, 399.06, 230.01]`; distance=1.7pt; vgap=1.7pt; same_column=True; owner=True; reason=None; raw='2C_TireLabel\n본 차량의 권장 타이어 공기압 정보는 운전석\n옆 센터 필러에 부착된 라벨 안에 표기되어 있\n습니다.'
  - expanded; bbox `[236.14, 62.89, 314.29, 80.0]`; distance=4.0pt; vgap=4.0pt; same_column=True; owner=True; reason=None; raw='타이어 공기압'
  - excluded-nearby; bbox `[50.9, 190.53, 215.3, 220.01]`; distance=37.5pt; vgap=1.7pt; same_column=False; owner=False; reason=다른 column; raw='2C_VINPosition\n차대번호(VIN: \nVehicle \nIdentification\nNumber)는 차량 등록, 차량 소유권 유지 등 모'
  - excluded-nearby; bbox `[51.45, 219.08, 214.69, 286.0]`; distance=67.1pt; vgap=30.2pt; same_column=False; owner=False; reason=다른 column; raw='든 법적인 사항에 사용되는 차량의 고유 번호입\n니다.\n차체에 타각된 차대번호와 차량 등록증에 기록\n된 차대번호는 일치해야 합니다.\n동승석 시트 아래 바닥에 있는 커버를 열면 차\n대번호를 확인할 수 있습니다.'

### p.32 / image 2

- image bbox: `[36.72, 363.34, 201.11, 468.22]`; candidate: 차량 운전 상태에서 탑승한 아이들을 안전하게
- A LLM 전달 context 필드: ['차량 운전 상태에서 탑승한 아이들을 안전하게\n보호하기 위해서는 아래의 사항을 지키십시오.', '유아/어린이의 에어백 관련 주의\n사항']
- B LLM 전달 text (70자): '유아/어린이의 에어백 관련 주의 사항\n차량 운전 상태에서 탑승한 아이들을 안전하게 보호하기 위해서는 아래의 사항을 지키십시오.'
- A 결과: '차량 운전 상태에서 탑승한 아이들을 안전하게 보호하기 위해' → '차량 운전 상태에서 탑승한 아이들을 안전하게' (fallback_candidate / new_tokens:보호하기,위해)
- B 결과: '탑승한 아이들의 안전한 보호' → '차량 운전 상태에서 탑승한 아이들을 안전하게' (outside_candidate_and_source:안전한,아이들의)
- blocks (current/expanded/excluded):
  - expanded; bbox `[37.34, 340.03, 201.09, 360.95]`; distance=2.4pt; vgap=2.4pt; same_column=True; owner=True; reason=None; raw='차량 운전 상태에서 탑승한 아이들을 안전하게\n보호하기 위해서는 아래의 사항을 지키십시오.'
  - expanded; bbox `[37.58, 306.53, 194.12, 336.18]`; distance=27.2pt; vgap=27.2pt; same_column=True; owner=True; reason=None; raw='유아/어린이의 에어백 관련 주의 \n사항'
  - excluded-nearby; bbox `[220.98, 285.57, 384.79, 399.21]`; distance=35.8pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='• 약 10-15세 정도(신장에 따라 다름)의 어린\n이를 동승석에 앉혀야 할 경우 반드시 안전\n벨트를 착용시키고 가능한 한 좌석을 뒤쪽으\n로 밀어 에어백과 거리를 멀리하도록 하십시\n오.\n• 아이를 안고 타지 마십시오. 특히 에어백이\n장착된 차량에서 동승석에 아이를 안고 탑승\n하면 더욱 위험합니다. \n• 유아는 반드시 뒷좌석에 유아용 보호장치를\n장착하여 앉히십시오.҃'
  - excluded-nearby; bbox `[221.51, 427.55, 384.85, 488.47]`; distance=36.7pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='어린이나 유아 및 임산부, 노약자는 동승석 에\n어백이 장착된 차량의 동승석에는 절대 앉히지\n마십시오. 또한 유아용 보조 시트도 장착하여\n운전하지 마십시오. 사고가 나면 에어백 팽창\n충격으로 얼굴을 다치거나 사망할 수 있습니\n다.'
  - excluded-nearby; bbox `[36.73, 190.53, 201.65, 286.97]`; distance=76.4pt; vgap=76.4pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='2C_DriverAirbagDeployment\n• 에어백은 안전벨트의 충격 보호 기능을 보조\n하기 위해 개발된 보조 안전장치입니다. 안\n전벨트를 착용해야만 충돌이 발생할 때 에어\n백의 최대 효과를 얻을 수 있고, 그렇지 않으\n면 실명, 상해, 사망 등의 위험을 당할 수 있\n습니다.\n• 주행 전 운전자와 탑승자는 에어백과 가깝지\n않도록 적정한 위치로 좌석을 이동하십시오.'
  - excluded-nearby; bbox `[230.03, 213.97, 384.79, 266.86]`; distance=148.5pt; vgap=96.5pt; same_column=False; owner=False; reason=다른 column; raw='동승석 에어백이 장착된 차량은 동승석에 유\n아용 보호장치를 설치하지 마십시오. 특히\n차량 진행 방향의 반대 방향으로 설치하면\n에어백이 작동할 때 심하게 다치거나 사망할\n수 있습니다.(그림 참고)'
  - excluded-nearby; bbox `[220.98, 171.54, 362.72, 192.87]`; distance=206.2pt; vgap=170.5pt; same_column=False; owner=False; reason=다른 column; raw='2C_DontChildStayFront_2\n• 아이들은 항상 뒷좌석에 앉히십시오.'

### p.44 / image 2

- image bbox: `[221.03, 77.04, 385.42, 181.91]`; candidate: 등받이 각도 조절하기
- A LLM 전달 context 필드: ['1. 좌석에 앉아 등을 약간 앞으로 숙인 상태에\n서 좌석 바깥쪽에 위치한 좌석 각도 조절 레\n버를 위로 당기십시오.\n2. 조심해서 좌석에 기대어 원하는 위치로 조절\n하십시오.\n3. 조절 레버를 놓으면 고정됩니다.\n4. 등받이가 확실하게 고정됐는지 확인하십시\n오.', '등받이 각도 조절하기']
- B LLM 전달 text (158자): '등받이 각도 조절하기\n1. 좌석에 앉아 등을 약간 앞으로 숙인 상태에 서 좌석 바깥쪽에 위치한 좌석 각도 조절 레 버를 위로 당기십시오. 2. 조심해서 좌석에 기대어 원하는 위치로 조절 하십시오. 3. 조절 레버를 놓으면 고정됩니다. 4. 등받이가 확실하게 고정됐는지 확인하십시 오.'
- A 결과: '등받이 각도 조절하기' → '등받이 각도 조절하기' (llm_accepted / accepted)
- B 결과: '등받이 각도 조절하기' → '등받이 각도 조절하기' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[220.83, 183.53, 384.86, 282.0]`; distance=1.6pt; vgap=1.6pt; same_column=True; owner=True; reason=None; raw='2C_AdjustSeatBackmanual\n1. 좌석에 앉아 등을 약간 앞으로 숙인 상태에\n서 좌석 바깥쪽에 위치한 좌석 각도 조절 레\n버를 위로 당기십시오.\n2. 조심해서 좌석에 기대어 원하는 위치로 조절\n하십시오.\n3. 조절 레버를 놓으면 고정됩니다.\n4. 등받이가 확실하게 고정됐는지 확인하십시\n오.'
  - expanded; bbox `[220.97, 63.72, 300.63, 74.64]`; distance=2.4pt; vgap=2.4pt; same_column=True; owner=True; reason=None; raw='등받이 각도 조절하기'
  - excluded-nearby; bbox `[36.73, 82.61, 201.1, 157.47]`; distance=35.9pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='• 가죽이 물기에 젖었다면 마른 천으로 물기를\n제거하고 그늘에 건조하십시오.\n• 가죽 표면에 스크래치가 날 수 있으니 날카\n로운 물체와 마찰하지 않도록 주의하십시오.\n• 밝은 색상의 가죽은 오염이나 이염에 주의하\n십시오.'
  - excluded-nearby; bbox `[220.97, 291.05, 331.46, 301.97]`; distance=109.1pt; vgap=109.1pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='좌석 높낮이 조절하기(운전석)'
  - excluded-nearby; bbox `[36.63, 362.43, 200.47, 427.9]`; distance=217.5pt; vgap=180.5pt; same_column=False; owner=False; reason=다른 column; raw='2C_AdjustSeatForwardBackwardmanual\n1. 좌석 쿠션의 앞쪽 레버를 당긴 채 좌석을 원\n하는 앞뒤 위치로 조절하십시오. \n2. 조절 레버를 놓으면 고정됩니다.\n3. 좌석을 가볍게 흔들어 확실하게 고정됐는지\n확인하십시오.'
  - excluded-nearby; bbox `[220.91, 410.86, 384.8, 463.34]`; distance=228.9pt; vgap=228.9pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='2C_AdjustSeatHeightmanual\n1. 높낮이 조절 레버를 위로 당길 때마다 좌석\n이 조금씩 올라가고 아래로 누를 때마다 좌\n석이 조금씩 내려갑니다.\n2. 조절이 끝나면 레버에서 손을 떼십시오.'

### p.69 / image 1

- image bbox: `[234.95, 299.75, 399.58, 404.86]`; candidate: 어린이 보조 좌석 설치 금지
- A LLM 전달 context 필드: ['승객 구분 센서의 유무와 상관없이 동승석에는\n어린이 보조 좌석을 설치하지 마십시오. 동승\n석 에어백이 팽창할 때 보조 좌석이 적정한 위\n치에서 벗어나거나 제대로 고정되지 못해 어린\n이가 큰 부상을 입을 수 있습니다.', '어린이 보조 좌석 설치 금지', '에어백이 작동하면 스티어링 휠 및 크래시 패드\n의 에어백 관련 부품이 고온상태가 됩니다. 화\n상 위험이 있으므로 작동 직후에는 내장 부품을\n만지지 마십시오.']
- B LLM 전달 text (522자): '소음과 연기 에어백이 부풀어 오를 때, 큰 소음과 차량 내부 에 연기처럼 보이는 가루가 남겨집니다. 이는 정상적인 현상으로 에어백이 팽창할 때 생기는 결과입니다. 에어백이 작동한 후에, 연기와 가 루뿐만 아니라 안전벨트와 에어백의 압박으로 인해 숨을 쉬기 어려울 수 있습니다. 에어백이 터지고 난 후에는 창문이나 도어를 열어 차 안 을 환기하십시오. 연기와 가루는 무독성이지만 피부에는 자극을 줄 수 있습니다. 피부가 가렵 거나 따가운 경우 즉시 차가운 물로 닦고, 자극 이 오랫동안 없어지지 않으면 의사와 상의하여 치료하십시오.҃\n에어백이 작동하면 스티어링 휠 및 크래시 패드 의 에어백 관련 부품이 고온상태가 됩니다. 화 상 위험이 있으므로 작동 직후에는 내장 부품을 만지지 마십시오.\n어린이 보조 좌석 설치 금지\n승객 구분 센서의 유무와 상관없이 동승석에는 어린이 보조 좌석을 설치하지 마십시오. 동승 석 에어백이 팽창할 때 보조 좌석이 적정한 위 치에서 벗어나거나 제대로 고정되지 못해 어린 이가 큰 부상을 입을 수 있습니다.'
- A 결과: '어린이 보조 좌석 설치 금지' → '어린이 보조 좌석 설치 금지' (llm_accepted / accepted)
- B 결과: '동승석 어린이 보조 좌석 설치 금지' → '동승석 어린이 보조 좌석 설치 금지' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[235.86, 286.11, 343.46, 298.33]`; distance=1.4pt; vgap=1.4pt; same_column=True; owner=True; reason=None; raw='어린이 보조 좌석 설치 금지'
  - expanded; bbox `[235.16, 406.38, 398.96, 465.85]`; distance=1.5pt; vgap=1.5pt; same_column=True; owner=True; reason=None; raw='2C_AirbagPartsWarning\n승객 구분 센서의 유무와 상관없이 동승석에는\n어린이 보조 좌석을 설치하지 마십시오. 동승\n석 에어백이 팽창할 때 보조 좌석이 적정한 위\n치에서 벗어나거나 제대로 고정되지 못해 어린\n이가 큰 부상을 입을 수 있습니다.'
  - expanded; bbox `[235.77, 226.51, 399.04, 267.43]`; distance=32.3pt; vgap=32.3pt; same_column=True; owner=True; reason=None; raw='에어백이 작동하면 스티어링 휠 및 크래시 패드\n의 에어백 관련 부품이 고온상태가 됩니다. 화\n상 위험이 있으므로 작동 직후에는 내장 부품을\n만지지 마십시오.'
  - excluded-nearby; bbox `[50.91, 63.72, 215.31, 305.12]`; distance=35.4pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw="에어백 제어 모듈은 시동 'ON'일 때 모든 에어\n백 부품을 항상 모니터링합니다. 충돌이 발생\n하면 충돌의 세기를 판단해 에어백과 프리텐셔\n너의 작동 여부를 결정합니다.\n• 에어백은 차량 전원 'ON' 상태, 시동 'ON' 상\n태 또는 시동 'OFF' 이후 약 3분 동안 작동합\n니다.\n• 정면이나 측면에 심각한 충돌이 있을 경우,\n에어백이 순간적으로 팽창하여 다치는 것을\n줄여줍니다.\n• 에어백은 차량의 속도가 아닌 충돌의 세기와\n방향에 따라서 작동합니다.\n• 사고가 날 때 에어백이 팽창하는 순간을 볼\n수는 없습니다. 사후에 에어백이 밖으로 나\n와 공기가 빠진 상태를 볼 가능성이 큽니다.\n• 강한 충돌이 일어나면 에어백이 큰 힘으로\n빠르게 팽창하여, 이에 의해 안면 마찰, 타박\n상, 골절과 같은 상해를 입을 수 있습니다.\n• 스티어링 휠과 너무 가까우면 에어백이 작동\n할 때 치명적인 부상을 입을 수 있으니 평소\n에 적절한 거리를 유지하십시오.҃"
  - excluded-nearby; bbox `[51.5, 333.46, 214.75, 374.38]`; distance=36.4pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='운전자는 차량 운전에 방해가 되지 않는 범위\n안에서 스티어링 휠로부터 가능한 멀리 앉아야\n합니다. 동승석에서는 가능한 좌석을 뒤로 이\n동시켜 바른 자세로 앉으십시오.'
  - excluded-nearby; bbox `[50.91, 393.07, 214.71, 538.0]`; distance=36.4pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='에어백 작동 시 2차 피해\n에어백 제어 모듈은 사고 시 발생하는 충격의\n세기를 감지하여 에어백이 작동되도록 신호를\n보냅니다.\n이 신호에 의해 에어백 모듈(에어백 공기주머\n니)에 내장된 화약이 폭발하여 에어백을 짧은\n시간 내에 부풀려 탑승자를 보호합니다. \n이때 다음의 피해를 입을 수 있습니다.\n• 동반되는 소음, 섬광, 연기로 인한 피해\n• 팽창한 에어백 천 때문에 입을 수 있는 타박\n상, 찰과상, 안경 파손\n• 화약 폭발로 인한 화상'
  - expanded; bbox `[235.45, 63.51, 398.97, 198.2]`; distance=101.5pt; vgap=101.5pt; same_column=True; owner=True; reason=None; raw='소음과 연기\n에어백이 부풀어 오를 때, 큰 소음과 차량 내부\n에 연기처럼 보이는 가루가 남겨집니다. 이는\n정상적인 현상으로 에어백이 팽창할 때 생기는\n결과입니다. 에어백이 작동한 후에, 연기와 가\n루뿐만 아니라 안전벨트와 에어백의 압박으로\n인해 숨을 쉬기 어려울 수 있습니다. 에어백이\n터지고 난 후에는 창문이나 도어를 열어 차 안\n을 환기하십시오. 연기와 가루는 무독성이지만\n피부에는 자극을 줄 수 있습니다. 피부가 가렵\n거나 따가운 경우 즉시 차가운 물로 닦고, 자극\n이 오랫동안 없어지지 않으면 의사와 상의하여\n치료하십시오.҃'

### p.77 / image 3

- image bbox: `[50.88, 369.82, 215.27, 474.7]`; candidate: 노트북이나 DVD 등 전자 장비나 다량의 물
- A LLM 전달 context 필드: ['노트북이나 DVD 등 전자 장비나 다량의 물\n통 등 전도성 물체를 동승석 시트 위에 올려\n놓지 마십시오.']
- B LLM 전달 text (58자): '노트북이나 DVD 등 전자 장비나 다량의 물 통 등 전도성 물체를 동승석 시트 위에 올려 놓지 마십시오.'
- A 결과: '노트북이나 DVD 등 전자 장비나 다량의 물통' → '노트북이나 DVD 등 전자 장비나 다량의 물' (fallback_candidate / new_tokens:물통)
- B 결과: '동승석 시트 위 전자 장비 및 전도성 물체' → '노트북이나 DVD 등 전자 장비나 다량의 물' (outside_candidate_and_source:및)
- blocks (current/expanded/excluded):
  - expanded; bbox `[50.91, 325.89, 214.71, 367.37]`; distance=2.5pt; vgap=2.5pt; same_column=True; owner=True; reason=None; raw='2C_OCSWarning_6\n• 노트북이나 DVD 등 전자 장비나 다량의 물\n통 등 전도성 물체를 동승석 시트 위에 올려\n놓지 마십시오.'
  - excluded-nearby; bbox `[235.16, 240.5, 398.98, 291.98]`; distance=113.6pt; vgap=77.8pt; same_column=False; owner=False; reason=다른 column; raw='2C_OCSWarning_9\n• 동승석에 실수로 다량의 음료수 또는 물을\n쏟았을 때, 에어백 경고등이 켜지거나 오작\n동을 일으킬 수 있으니 시트를 완전히 말리\n고 주행하십시오.'
  - excluded-nearby; bbox `[50.91, 195.52, 200.68, 216.86]`; distance=153.0pt; vgap=153.0pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='2C_OCSWarning_5\n• 좌석의 한쪽으로 치우쳐 앉지 마십시오.'
  - excluded-nearby; bbox `[235.16, 63.53, 399.05, 131.62]`; distance=274.0pt; vgap=238.2pt; same_column=False; owner=False; reason=다른 column; raw='• 인버터 충전기(inverter charger)를 사용하\n는 전자 기기(노트북, 위성 라디오 등)를 사\n용하지 마십시오.\n• 동승석에 두꺼운 모포나 방석 등 시트 쿠션\n표면을 덮는 시트 액세서리는 사용하지 마십\n시오.'

### p.82 / image 4

- image bbox: `[221.03, 275.27, 385.42, 380.14]`; candidate: 사면 충돌이나 추돌 사고(앞 방향에서 비스듬
- A LLM 전달 context 필드: ['정면에서 전해지는 충격은 정면충돌이나 추돌\n한 경우보다 약하여 에어백이 작동하지 않을 수\n있습니다.', '사면 충돌이나 추돌 사고(앞 방향에서 비스듬\n히 충돌)']
- B LLM 전달 text (86자): '사면 충돌이나 추돌 사고(앞 방향에서 비스듬 히 충돌)\n정면에서 전해지는 충격은 정면충돌이나 추돌 한 경우보다 약하여 에어백이 작동하지 않을 수 있습니다.'
- A 결과: '사면 충돌이나 추돌 사고(앞 방향에서 비스듬히 충돌)' → '사면 충돌이나 추돌 사고(앞 방향에서 비스듬' (fallback_candidate / new_tokens:비스듬히,충돌)
- B 결과: '사면 충돌이나 추돌 사고(앞 방향에서 비스듬히 충돌)' → '사면 충돌이나 추돌 사고(앞 방향에서 비스듬히 충돌)' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[220.98, 381.87, 384.8, 421.35]`; distance=1.7pt; vgap=1.7pt; same_column=True; owner=True; reason=None; raw='2C_AirbagNonOperatingConditionSidlingCrash\n정면에서 전해지는 충격은 정면충돌이나 추돌\n한 경우보다 약하여 에어백이 작동하지 않을 수\n있습니다.'
  - expanded; bbox `[220.97, 252.06, 383.0, 272.99]`; distance=2.3pt; vgap=2.3pt; same_column=True; owner=True; reason=None; raw='사면 충돌이나 추돌 사고(앞 방향에서 비스듬\n히 충돌)'
  - excluded-nearby; bbox `[220.98, 183.53, 384.81, 243.01]`; distance=32.3pt; vgap=32.3pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='2C_AirbagNonOperatingConditionSideCrash\n사이드 에어백이나 커튼 에어백이 장착되었다\n면 충돌 세기에 따라 사이드 에어백이나 커튼\n에어백이 작동할 수 있습니다. 탑승자는 충돌\n한 방향으로 움직이므로 정면 에어백은 작동하\n지 않을 수 있습니다.'
  - excluded-nearby; bbox `[36.73, 391.87, 200.46, 431.35]`; distance=48.8pt; vgap=11.7pt; same_column=False; owner=False; reason=다른 column; raw='2C_AirbagNonOperatingConditionRearCrash\n충돌 반력에 의해 탑승자가 좌석 등받이 쪽으로\n밀려서 정면 에어백의 보호를 받을 수 없으므로\n작동하지 않을 수 있습니다.'
  - excluded-nearby; bbox `[36.73, 213.52, 200.54, 263.0]`; distance=49.2pt; vgap=12.3pt; same_column=False; owner=False; reason=다른 column; raw='2C_AirbagNonOperatingConditionMinorCrash\n에어백이 작동해도 큰 도움이 되지 않으며, 오\n히려 에어백 작동으로 2차 피해(가벼운 찰과\n상, 안경 파손, 화상 등)가 날 수 있으므로 에어\n백이 작동하지 않을 수 있습니다.'
  - excluded-nearby; bbox `[220.97, 63.72, 276.45, 74.64]`; distance=200.6pt; vgap=200.6pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='측면 충돌 사고'
  - excluded-nearby; bbox `[36.72, 83.71, 202.88, 104.63]`; distance=203.3pt; vgap=170.6pt; same_column=False; owner=False; reason=다른 column; raw='안전벨트만으로 탑승자를 보호할 수 있는 경미\n한 사고'

### p.90 / image 3

- image bbox: `[220.79, 87.12, 385.66, 200.87]`; candidate: 적산 거리계 (ODO)
- A LLM 전달 context 필드: ['A타입', 'B타입', '적산 거리계 (ODO)']
- B LLM 전달 text (20자): '적산 거리계 (ODO)\nA타입\nB타입'
- A 결과: '적산 거리계(ODO)' → '적산 거리계(ODO)' (llm_accepted / accepted)
- B 결과: '적산 거리계(ODO)' → '적산 거리계(ODO)' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[294.74, 77.0, 311.1, 85.5]`; distance=1.6pt; vgap=1.6pt; same_column=True; owner=True; reason=None; raw='A타입'
  - expanded; bbox `[220.98, 203.91, 311.14, 221.25]`; distance=3.0pt; vgap=3.0pt; same_column=True; owner=True; reason=None; raw='2C_Odometer\nB타입'
  - expanded; bbox `[221.69, 63.51, 299.36, 75.73]`; distance=11.4pt; vgap=11.4pt; same_column=True; owner=True; reason=None; raw='적산 거리계 (ODO)'
  - excluded-nearby; bbox `[220.98, 339.66, 384.88, 386.12]`; distance=138.8pt; vgap=138.8pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='2C_Odometer_2\n• 주행한 총거리가 km 단위로 표시됩니다.\n• 차량 출고 시 적산 거리계가 90 km 미만으\n로 표시되면 정상입니다.'
  - excluded-nearby; bbox `[36.73, 339.42, 200.39, 358.9]`; distance=175.3pt; vgap=138.5pt; same_column=False; owner=False; reason=다른 column; raw='2C_ATPosition_2\nP 버튼 및 변속 다이얼 또는 변속 레버를 조작하'
  - excluded-nearby; bbox `[37.35, 357.97, 143.48, 368.9]`; distance=296.3pt; vgap=157.1pt; same_column=False; owner=False; reason=다른 column; raw='면 변속된 위치가 표시됩니다.'

### p.103 / image 1

- image bbox: `[50.88, 87.12, 215.27, 191.99]`; candidate: 타이어 공기압이 낮습니다
- A LLM 전달 context 필드: ['A타입', 'B타입', '타이어 공기압이 낮습니다']
- B LLM 전달 text (21자): '타이어 공기압이 낮습니다\nA타입\nB타입'
- A 결과: '타이어 공기압이 낮습니다' → '타이어 공기압이 낮습니다' (llm_accepted / accepted)
- B 결과: '타이어 공기압이 낮습니다' → '타이어 공기압이 낮습니다' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[124.66, 77.0, 141.02, 85.5]`; distance=1.6pt; vgap=1.6pt; same_column=True; owner=True; reason=None; raw='A타입'
  - expanded; bbox `[50.91, 195.03, 141.31, 212.37]`; distance=3.0pt; vgap=3.0pt; same_column=True; owner=True; reason=None; raw='2C_TireLowPressureWarning_2\nB타입'
  - expanded; bbox `[51.61, 63.51, 154.77, 75.73]`; distance=11.4pt; vgap=11.4pt; same_column=True; owner=True; reason=None; raw='타이어 공기압이 낮습니다'
  - excluded-nearby; bbox `[235.75, 63.51, 399.07, 117.63]`; distance=36.9pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='엔진이 과열되었습니다\n냉각수 온도가 적정 범위를 벗어나면 이 경고문\n이 표시됩니다. 엔진 과열의 가능성이 있으므\n로 주행을 중지하고 당사 직영 하이테크센터나\n블루핸즈에서 점검을 받으십시오.'
  - excluded-nearby; bbox `[235.75, 155.93, 399.04, 196.86]`; distance=36.9pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='방향지시등에 이상이 있거나 규격에 맞지 않는\n타입이나 용량의 전구로 교체된 경우 이 경고문\n이 표시됩니다. 당사 직영 하이테크센터나 블\n루핸즈에서 정비를 받으십시오.'
  - excluded-nearby; bbox `[235.86, 131.48, 345.8, 143.7]`; distance=37.1pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='방향지시등을 점검하십시오'
  - excluded-nearby; bbox `[235.86, 210.71, 356.91, 222.93]`; distance=55.8pt; vgap=18.7pt; same_column=False; owner=False; reason=다른 column; raw='헤드램프 LED를 점검하십시오'
  - excluded-nearby; bbox `[235.16, 235.16, 398.99, 246.08]`; distance=79.0pt; vgap=43.2pt; same_column=False; owner=False; reason=다른 column; raw='LED 타입 전조등에 이상이 있거나 규격에 맞지'
  - excluded-nearby; bbox `[235.75, 245.16, 398.96, 276.08]`; distance=90.0pt; vgap=53.2pt; same_column=False; owner=False; reason=다른 column; raw='않는 타입이나 용량의 전구로 교체된 경우 이\n경고문이 표시됩니다. 당사 직영 하이테크센터\n나 블루핸즈에서 정비를 받으십시오.'
  - excluded-nearby; bbox `[50.91, 321.9, 214.74, 384.37]`; distance=129.9pt; vgap=129.9pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw="2C_TireLowPressureWarning\n시동 'ON' 상태에서 타이어 공기압이 일정량\n이하이면 이 경고문과 함께 공기압이 낮은 타이\n어 위치가 이미지로 표시됩니다.\n자세한 내용은 8장 내 '타이어 공기압 경보 시\n스템 (TPMS)'을 참고하십시오."
  - excluded-nearby; bbox `[235.86, 289.93, 395.73, 312.15]`; distance=135.0pt; vgap=97.9pt; same_column=False; owner=False; reason=다른 column; raw='배터리 점검! 즉시 안전한 곳에 정차 하십\n시오.'
  - excluded-nearby; bbox `[235.16, 324.38, 398.94, 365.3]`; distance=168.2pt; vgap=132.4pt; same_column=False; owner=False; reason=다른 column; raw='12 V 리튬 보조 배터리에 높은 온도나 과충전 등\n의 이상이 감지될 경우 이 경고문이 표시됩니\n다. 당사 직영 하이테크센터나 블루핸즈에서\n정비를 받으십시오.'
  - excluded-nearby; bbox `[51.61, 398.22, 146.78, 410.44]`; distance=206.2pt; vgap=206.2pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='와셔액을 보충하십시오.'
  - excluded-nearby; bbox `[51.52, 422.67, 215.29, 443.6]`; distance=230.7pt; vgap=230.7pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='와셔액이 부족하면 이 경고문이 표시됩니다.\n즉시 와셔액을 보충하십시오.'

### p.106 / image 1

- image bbox: `[36.72, 77.04, 201.35, 182.15]`; candidate: 주유 후 정보 · 클러스터
- A LLM 전달 context 필드: ['주유 이후의 주행 거리, 주행 시간, 주행 연비가\n표시됩니다.\n정보를 초기화하려면 스티어링 휠의 OK 버튼\n을 길게 누르십시오.\n기계식 주차 타워 이용 등으로 주차 후 연료가\n과도하게 출렁인 경우에는 주유 후 정보가 초기\n화될 수 있습니다.', '주유 후 정보', '클러스터']
- B LLM 전달 text (147자): '클러스터\n주유 후 정보\n주유 이후의 주행 거리, 주행 시간, 주행 연비가 표시됩니다. 정보를 초기화하려면 스티어링 휠의 OK 버튼 을 길게 누르십시오. 기계식 주차 타워 이용 등으로 주차 후 연료가 과도하게 출렁인 경우에는 주유 후 정보가 초기 화될 수 있습니다.'
- A 결과: '주유 후 정보 · 클러스터' → '주유 후 정보 · 클러스터' (llm_accepted / accepted)
- B 결과: '주유 후 정보' → '주유 후 정보' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[36.73, 183.53, 200.53, 269.0]`; distance=1.4pt; vgap=1.4pt; same_column=True; owner=True; reason=None; raw='2C_InfoAfterRefuel\n주유 이후의 주행 거리, 주행 시간, 주행 연비가\n표시됩니다.\n정보를 초기화하려면 스티어링 휠의 OK 버튼\n을 길게 누르십시오.\n기계식 주차 타워 이용 등으로 주차 후 연료가\n과도하게 출렁인 경우에는 주유 후 정보가 초기\n화될 수 있습니다.'
  - expanded; bbox `[36.72, 63.72, 83.86, 74.64]`; distance=2.4pt; vgap=2.4pt; same_column=True; owner=True; reason=None; raw='주유 후 정보'
  - excluded-nearby; bbox `[220.34, 63.72, 306.13, 74.64]`; distance=36.6pt; vgap=2.4pt; same_column=False; owner=False; reason=다른 column; raw='AUTO STOP 누적 시간'
  - excluded-nearby; bbox `[220.98, 183.77, 384.81, 233.25]`; distance=36.9pt; vgap=1.6pt; same_column=False; owner=False; reason=다른 column; raw='2C_ISGAcuumInfo\n공회전 제한(ISG)시스템에 의해 엔진이 꺼진\n뒤 지난 시간이 표시됩니다. 자세한 내용은 6장\n내 ‘공회전 제한 (ISG) 시스템’을 참고하십시\n오.'
  - expanded; bbox `[37.58, 27.73, 70.23, 38.93]`; distance=38.1pt; vgap=38.1pt; same_column=True; owner=True; reason=None; raw='클러스터'
  - excluded-nearby; bbox `[220.97, 242.3, 335.85, 266.23]`; distance=95.5pt; vgap=60.1pt; same_column=False; owner=False; reason=다른 column; raw='서비스 메시지\n통합 경고등 정보가 표시됩니다.'
  - excluded-nearby; bbox `[36.72, 278.05, 73.87, 288.98]`; distance=95.9pt; vgap=95.9pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='누적 정보'
  - excluded-nearby; bbox `[221.69, 280.09, 279.85, 292.31]`; distance=134.5pt; vgap=97.9pt; same_column=False; owner=False; reason=다른 column; raw='기타 정보 표시'
  - excluded-nearby; bbox `[220.97, 300.29, 257.88, 311.22]`; distance=153.5pt; vgap=118.1pt; same_column=False; owner=False; reason=다른 column; raw='주행 정보'
  - excluded-nearby; bbox `[36.73, 397.87, 200.54, 450.34]`; distance=215.7pt; vgap=215.7pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='2C_AccumulatedInfo\n수동으로 정보를 초기화한 이후의 누적 주행 거\n리, 주행 시간, 주행 연비가 표시됩니다.\n정보를 초기화하려면 스티어링 휠의 OK 버튼\n을 길게 누르십시오.'
  - excluded-nearby; bbox `[220.98, 420.11, 384.72, 449.58]`; distance=273.3pt; vgap=238.0pt; same_column=False; owner=False; reason=다른 column; raw='2C_DrivingInfo\n시동을 건 후 시동을 끄면 주행 정보가 4초 동\n안 표시됩니다.'

### p.115 / image 1

- image bbox: `[50.88, 77.04, 215.27, 181.91]`; candidate: 터치 센서 타입
- A LLM 전달 context 필드: ['1. 모든 도어(후드 및 트렁크 포함)를 닫으십시\n오.\n2. 스마트 키의 도어 잠금 버튼을 누르십시오.\n도어 잠금 버튼을 누르면 도어가 잠깁니\n다. 이 때 비상 경고등이 1회 깜빡이고, 알\n림음이 울립니다.\n스마트 키를 휴대한 상태로 앞좌석 바깥쪽\n도어 핸들의 잠금 센서부를 터치하면 모든\n도어가 잠금 상태가 됩니다.\n3. 도어의 바깥쪽 도어 핸들을 잡아 당겨 잠겼\n는지 확인하십시오.', '터치 센서 타입']
- B LLM 전달 text (546자): "터치 센서 타입\n1. 모든 도어(후드 및 트렁크 포함)를 닫으십시 오. 2. 스마트 키의 도어 잠금 버튼을 누르십시오. 도어 잠금 버튼을 누르면 도어가 잠깁니 다. 이 때 비상 경고등이 1회 깜빡이고, 알 림음이 울립니다. 스마트 키를 휴대한 상태로 앞좌석 바깥쪽 도어 핸들의 잠금 센서부를 터치하면 모든 도어가 잠금 상태가 됩니다. 3. 도어의 바깥쪽 도어 핸들을 잡아 당겨 잠겼 는지 확인하십시오.\n인포테인먼트 시스템에서 설정 > 차량 > 편 의 > 웰컴 미러/라이트 > 도어 잠금 해제 시를 선택하면 도어를 잠글 때 사이드 미러도 동 시에 접힙니다. 자세한 내용은 5장 내 '미러'를 참고하십시 오. 차량의 도어 잠금/잠금 해제 장치는 스마트 키가 앞좌석 도어의 바깥쪽 도어 핸들과 1 m 이내에 있어야 작동합니다. 다음 상황에서 도어 잠금/잠금 해제 버튼을 누르거나 도어 잠금 센서부를 터치해 도어 잠금을 시도하면, 경고음이 잠시 울리면서 도어가 잠기지 않습니다. 스마트 키가 차 안에 있을 때 시동 'ACC' 또는 'ON' 상태일 때 하나 이상의 도어가 열려 있을 때"
- A 결과: '터치 센서 타입' → '터치 센서 타입' (llm_accepted / accepted)
- B 결과: '터치 센서 타입' → '터치 센서 타입' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[50.83, 183.53, 214.7, 318.97]`; distance=1.6pt; vgap=1.6pt; same_column=True; owner=True; reason=None; raw='2C_OutsideDoorHandleTouch_3\n1. 모든 도어(후드 및 트렁크 포함)를 닫으십시\n오.\n2. 스마트 키의 도어 잠금 버튼을 누르십시오.\n• 도어 잠금 버튼을 누르면 도어가 잠깁니\n다. 이 때 비상 경고등이 1회 깜빡이고, 알\n림음이 울립니다.\n• 스마트 키를 휴대한 상태로 앞좌석 바깥쪽\n도어 핸들의 잠금 센서부를 터치하면 모든\n도어가 잠금 상태가 됩니다.\n3. 도어의 바깥쪽 도어 핸들을 잡아 당겨 잠겼\n는지 확인하십시오.'
  - expanded; bbox `[50.89, 63.72, 106.37, 74.64]`; distance=2.4pt; vgap=2.4pt; same_column=True; owner=True; reason=None; raw='터치 센서 타입'
  - excluded-nearby; bbox `[235.15, 93.7, 272.3, 104.63]`; distance=35.8pt; vgap=0.0pt; same_column=False; owner=False; reason=다른 column; raw='버튼 타입'
  - excluded-nearby; bbox `[235.86, 63.51, 396.53, 85.72]`; distance=37.1pt; vgap=0.0pt; same_column=False; owner=False; reason=다른 column; raw='도어 잠금 해제(2)(세이프티 언락 기능 설\n정 시)'
  - excluded-nearby; bbox `[235.01, 213.52, 399.34, 348.98]`; distance=67.1pt; vgap=31.6pt; same_column=False; owner=False; reason=다른 column; raw='2C_OutsideDoorHandleTouch\n1. 모든 도어가 잠금 상태일 때 스마트 키를 휴\n대하고 앞좌석 도어의 바깥쪽 도어 핸들에\n있는 도어 잠금/잠금 해제 버튼을 누르거나\n스마트 키의 도어 잠금 해제 버튼을 누르십\n시오.\n2. 운전석 도어가 잠금 해제 상태가 됐는지 확\n인하십시오.\n3. 4초 이내에 다시 한 번 도어 잠금/잠금 해제\n버튼을 누르거나 스마트 키의 도어 잠금 해\n제 버튼을 누르면 도어가 잠금 해제됩니다.\n이 때 비상 경고등이 2회 깜빡이고 알림음이\n울립니다.'
  - expanded; bbox `[50.91, 345.92, 215.19, 532.74]`; distance=164.0pt; vgap=164.0pt; same_column=True; owner=True; reason=None; raw="• 인포테인먼트 시스템에서 설정 > 차량 > 편\n의 > 웰컴 미러/라이트 > 도어 잠금 해제 시를\n선택하면 도어를 잠글 때 사이드 미러도 동\n시에 접힙니다.\n자세한 내용은 5장 내 '미러'를 참고하십시\n오.\n• 차량의 도어 잠금/잠금 해제 장치는 스마트\n키가 앞좌석 도어의 바깥쪽 도어 핸들과 1 m\n이내에 있어야 작동합니다.\n• 다음 상황에서 도어 잠금/잠금 해제 버튼을\n누르거나 도어 잠금 센서부를 터치해 도어\n잠금을 시도하면, 경고음이 잠시 울리면서\n도어가 잠기지 않습니다.\n- 스마트 키가 차 안에 있을 때\n- 시동 'ACC' 또는 'ON' 상태일 때\n- 하나 이상의 도어가 열려 있을 때"

### p.115 / image 2

- image bbox: `[235.19, 107.04, 399.58, 211.91]`; candidate: 도어 잠금 해제(2)(세이프티 언락 기능 설 · 버튼 타입
- A LLM 전달 context 필드: ['1. 모든 도어가 잠금 상태일 때 스마트 키를 휴\n대하고 앞좌석 도어의 바깥쪽 도어 핸들에\n있는 도어 잠금/잠금 해제 버튼을 누르거나\n스마트 키의 도어 잠금 해제 버튼을 누르십\n시오.\n2. 운전석 도어가 잠금 해제 상태가 됐는지 확\n인하십시오.\n3. 4초 이내에 다시 한 번 도어 잠금/잠금 해제\n버튼을 누르거나 스마트 키의 도어 잠금 해\n제 버튼을 누르면 도어가 잠금 해제됩니다.\n이 때 비상 경고등이 2회 깜빡이고 알림음이\n울립니다.', '버튼 타입', '도어 잠금 해제(2)(세이프티 언락 기능 설\n정 시)']
- B LLM 전달 text (280자): '도어 잠금 해제(2)(세이프티 언락 기능 설 정 시)\n버튼 타입\n1. 모든 도어가 잠금 상태일 때 스마트 키를 휴 대하고 앞좌석 도어의 바깥쪽 도어 핸들에 있는 도어 잠금/잠금 해제 버튼을 누르거나 스마트 키의 도어 잠금 해제 버튼을 누르십 시오. 2. 운전석 도어가 잠금 해제 상태가 됐는지 확 인하십시오. 3. 4초 이내에 다시 한 번 도어 잠금/잠금 해제 버튼을 누르거나 스마트 키의 도어 잠금 해 제 버튼을 누르면 도어가 잠금 해제됩니다. 이 때 비상 경고등이 2회 깜빡이고 알림음이 울립니다.'
- A 결과: '도어 잠금 해제(2)(세이프티 언락 기능 설정 시) · 버튼 타입' → '도어 잠금 해제(2)(세이프티 언락 기능 설 · 버튼 타입' (fallback_candidate / new_tokens:설정,시)
- B 결과: '세이프티 언락 기능 설정 시 도어 잠금 해제 버튼 타입' → '세이프티 언락 기능 설정 시 도어 잠금 해제 버튼 타입' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[235.01, 213.52, 399.34, 348.98]`; distance=1.6pt; vgap=1.6pt; same_column=True; owner=True; reason=None; raw='2C_OutsideDoorHandleTouch\n1. 모든 도어가 잠금 상태일 때 스마트 키를 휴\n대하고 앞좌석 도어의 바깥쪽 도어 핸들에\n있는 도어 잠금/잠금 해제 버튼을 누르거나\n스마트 키의 도어 잠금 해제 버튼을 누르십\n시오.\n2. 운전석 도어가 잠금 해제 상태가 됐는지 확\n인하십시오.\n3. 4초 이내에 다시 한 번 도어 잠금/잠금 해제\n버튼을 누르거나 스마트 키의 도어 잠금 해\n제 버튼을 누르면 도어가 잠금 해제됩니다.\n이 때 비상 경고등이 2회 깜빡이고 알림음이\n울립니다.'
  - expanded; bbox `[235.15, 93.7, 272.3, 104.63]`; distance=2.4pt; vgap=2.4pt; same_column=True; owner=True; reason=None; raw='버튼 타입'
  - expanded; bbox `[235.86, 63.51, 396.53, 85.72]`; distance=21.3pt; vgap=21.3pt; same_column=True; owner=True; reason=None; raw='도어 잠금 해제(2)(세이프티 언락 기능 설\n정 시)'
  - excluded-nearby; bbox `[50.83, 183.53, 214.7, 318.97]`; distance=36.9pt; vgap=0.0pt; same_column=False; owner=False; reason=다른 column; raw='2C_OutsideDoorHandleTouch_3\n1. 모든 도어(후드 및 트렁크 포함)를 닫으십시\n오.\n2. 스마트 키의 도어 잠금 버튼을 누르십시오.\n• 도어 잠금 버튼을 누르면 도어가 잠깁니\n다. 이 때 비상 경고등이 1회 깜빡이고, 알\n림음이 울립니다.\n• 스마트 키를 휴대한 상태로 앞좌석 바깥쪽\n도어 핸들의 잠금 센서부를 터치하면 모든\n도어가 잠금 상태가 됩니다.\n3. 도어의 바깥쪽 도어 핸들을 잡아 당겨 잠겼\n는지 확인하십시오.'
  - excluded-nearby; bbox `[50.91, 345.92, 215.19, 532.74]`; distance=170.0pt; vgap=134.0pt; same_column=False; owner=True; reason=다른 column; raw="• 인포테인먼트 시스템에서 설정 > 차량 > 편\n의 > 웰컴 미러/라이트 > 도어 잠금 해제 시를\n선택하면 도어를 잠글 때 사이드 미러도 동\n시에 접힙니다.\n자세한 내용은 5장 내 '미러'를 참고하십시\n오.\n• 차량의 도어 잠금/잠금 해제 장치는 스마트\n키가 앞좌석 도어의 바깥쪽 도어 핸들과 1 m\n이내에 있어야 작동합니다.\n• 다음 상황에서 도어 잠금/잠금 해제 버튼을\n누르거나 도어 잠금 센서부를 터치해 도어\n잠금을 시도하면, 경고음이 잠시 울리면서\n도어가 잠기지 않습니다.\n- 스마트 키가 차 안에 있을 때\n- 시동 'ACC' 또는 'ON' 상태일 때\n- 하나 이상의 도어가 열려 있을 때"

### p.123 / image 1

- image bbox: `[50.88, 149.99, 215.27, 254.87]`; candidate: [B] 스마트폰 뒷면에 있는 NFC 안테나(스마트폰 마
- A LLM 전달 context 필드: ['삼성 스마트폰', '[A] 도어 핸들 인증 패드\n[B] 스마트폰 뒷면에 있는 NFC 안테나(스마트폰 마', '터치 제어\n스마트폰을 차량 도어 손잡이에 터치하여 도어\n잠금/잠금 해제가 가능하며, 차량 내 실내 인증\n패드(무선 충전 패드) 위에 올려놓고 시동을 걸\n수 있습니다.', '디지털 키(스마트폰) 사용하기']
- B LLM 전달 text (164자): '디지털 키(스마트폰) 사용하기\n터치 제어 스마트폰을 차량 도어 손잡이에 터치하여 도어 잠금/잠금 해제가 가능하며, 차량 내 실내 인증 패드(무선 충전 패드) 위에 올려놓고 시동을 걸 수 있습니다.\n삼성 스마트폰\n[A] 도어 핸들 인증 패드 [B] 스마트폰 뒷면에 있는 NFC 안테나(스마트폰 마'
- A 결과: '[B] 스마트폰 뒷면 NFC 안테나' → '[B] 스마트폰 뒷면에 있는 NFC 안테나(스마트폰 마' (fallback_candidate / new_tokens:뒷면)
- B 결과: '스마트폰 뒷면 NFC 안테나' → '스마트폰 뒷면 NFC 안테나' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[113.53, 139.98, 152.75, 148.48]`; distance=1.5pt; vgap=1.5pt; same_column=True; owner=True; reason=None; raw='삼성 스마트폰'
  - expanded; bbox `[50.91, 258.0, 211.96, 287.41]`; distance=3.1pt; vgap=3.1pt; same_column=True; owner=True; reason=None; raw='2C_OutsideDoorHandleTouchBySmartPhone\n[A] 도어 핸들 인증 패드\n[B] 스마트폰 뒷면에 있는 NFC 안테나(스마트폰 마'
  - expanded; bbox `[50.89, 83.71, 214.73, 137.63]`; distance=12.4pt; vgap=12.4pt; same_column=True; owner=True; reason=None; raw='터치 제어\n스마트폰을 차량 도어 손잡이에 터치하여 도어\n잠금/잠금 해제가 가능하며, 차량 내 실내 인증\n패드(무선 충전 패드) 위에 올려놓고 시동을 걸\n수 있습니다.'
  - excluded-nearby; bbox `[62.81, 285.69, 105.4, 295.4]`; distance=30.8pt; vgap=30.8pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='다 위치 다름)'
  - excluded-nearby; bbox `[235.16, 205.52, 398.91, 252.99]`; distance=35.8pt; vgap=0.0pt; same_column=False; owner=False; reason=다른 column; raw='2C_SmartPhoneSample\n• 도어 잠금/잠금 해제\nUWB 미지원 스마트폰의 경우\n- 등록된 스마트폰의 뒷면에 있는 NFC 안'
  - excluded-nearby; bbox `[123.81, 296.84, 142.37, 305.34]`; distance=42.0pt; vgap=42.0pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='아이폰'
  - excluded-nearby; bbox `[243.59, 252.06, 399.46, 295.98]`; distance=51.0pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='테나를 운전석 또는 동승석 도어 핸들 인\n증 패드에 2초 이상 접촉하면 도어가 잠금\n또는 잠금 해제됩니다.\n- 세이프티 언락(2회 눌러 전체 잠금 해제)'
  - expanded; bbox `[51.61, 63.51, 170.07, 75.73]`; distance=74.3pt; vgap=74.3pt; same_column=True; owner=True; reason=None; raw='디지털 키(스마트폰) 사용하기'
  - excluded-nearby; bbox `[235.16, 63.53, 399.03, 96.63]`; distance=89.2pt; vgap=53.4pt; same_column=False; owner=False; reason=다른 column; raw='• Apple iphone의 NFC 안테나는 기기 뒷면\n최상단[B], Apple WATCH의 NFC 안테나\n는 화면 중앙[C]에 위치합니다.'
  - excluded-nearby; bbox `[252.04, 295.05, 398.87, 315.98]`; distance=106.4pt; vgap=40.2pt; same_column=False; owner=False; reason=다른 column; raw='이 설정된 경우, 디지털 키(스마트폰 또는\nNFC 카드)를 도어핸들 인증 패드에 접촉'
  - excluded-nearby; bbox `[243.4, 315.05, 399.39, 371.97]`; distance=110.8pt; vgap=60.2pt; same_column=False; owner=False; reason=다른 column; raw='할 경우 운전석 도어만 잠금 해제됩니다.\n이 상태에서 4초 이내에 한번 더 접촉하면\n모든 도어가 잠금 해제됩니다.\nUWB 지원 스마트폰의 경우\n- 스마트폰을 휴대하고 도어 손잡이에 있는'
  - excluded-nearby; bbox `[50.91, 414.86, 214.73, 456.33]`; distance=160.0pt; vgap=160.0pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='2C_OutsideDoorHandleTouchByIPhone\n[A] 도어 핸들 인증 패드\n[B] 기기 뒷면 최상단에 있는 NFC 안테나\nNFC 안테나 위치가 스마트폰 기종별로 다를'
  - excluded-nearby; bbox `[243.91, 371.04, 399.25, 467.9]`; distance=167.7pt; vgap=116.2pt; same_column=False; owner=False; reason=다른 column; raw='도어 핸들 잠금/ 잠금 해제 센서부(음각)\n을 터치하면 도어가 잠금/ 잠금 해제 됩니\n다.\n도어 잠금 후 반드시 잠금 상태를 확인하십\n시오. 도어 잠금 해제 후, 30초 이내에 도어\n를 열지 않으면 다시 잠금 상태가 됩니다.\n디지털 키가 작동 안 된 경우, 스마트폰을 도\n어 핸들 인증 패드로부터 10 cm 이상 떨어뜨\n린 후 다시 접촉하십시오.'
  - excluded-nearby; bbox `[50.91, 455.4, 214.69, 511.31]`; distance=200.5pt; vgap=200.5pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='수 있습니다. 자세한 내용은 스마트폰 제조사\n에 문의하십시오.\n• 삼성 스마트폰의 NFC 안테나 위치는 설정\n앱 > 연결 > NFC 및 비접촉 결제 항목에서 확\n인할 수 있습니다.'

### p.137 / image 2

- image bbox: `[235.19, 333.59, 399.58, 438.46]`; candidate: 비상시 도어 잠금 방법
- A LLM 전달 context 필드: ['비상시(배터리 방전 등) 비상 키를 사용하여 수\n동으로 도어를 잠글 수 있습니다.\n다음 지시에 따라 비상 키를 사용하여 수동으로\n도어를 잠그십시오. 모든 도어를 각각 잠가야\n합니다.\n1. 도어를 여십시오.\n2. 도어의 뒤쪽에 위치한 비상 잠금 장치에 비\n상 키를 넣고 수평 방향으로 돌리십시오.\n3. 도어를 닫으십시오.', '비상시 도어 잠금 방법', '차량 출발 전에 운전석에서 중앙 도어 잠금\n버튼을 이용하여 모든 도어를 잠그십시오.\n특히 어린이를 태웠을 때는 반드시 잠금 상\n태로 주행하십시오. 운전 중 실수로 차량의\n도어가 열리게 되면 매우 위험합니다.\n차에서 내릴 때는 반드시 시동을 끄고, 스마\n트 키를 가지고 내리십시오. 또한 어린이나\n동물을 차 안에 혼자 남겨 두지 않도록 주의\n하십시오. 도어 잠금 버튼을 누르거나 기타\n장비를 잘못 조작하여 사고가 발생할 수 있\n습니다.\n차 안에 어린이나 동물이 있는 상태로 도어\n가 잠긴 경우, 비상 키로 운전석 도어의 잠금\n을 해제 할 수 있습니다. 비상 키로 운전석 도\n어의 잠금을 해제하는 방법은 5장 내 ‘도어’\n를 참고하십시오.']
- B LLM 전달 text (600자): '도어 잠금 해제(2) 운전석에 있는 잠금 해제 버튼(2)을 누르면 모든 도어가 잠금 해제됩니다.҃\n차량 출발 전에 운전석에서 중앙 도어 잠금 버튼을 이용하여 모든 도어를 잠그십시오. 특히 어린이를 태웠을 때는 반드시 잠금 상 태로 주행하십시오. 운전 중 실수로 차량의 도어가 열리게 되면 매우 위험합니다. 차에서 내릴 때는 반드시 시동을 끄고, 스마 트 키를 가지고 내리십시오. 또한 어린이나 동물을 차 안에 혼자 남겨 두지 않도록 주의 하십시오. 도어 잠금 버튼을 누르거나 기타 장비를 잘못 조작하여 사고가 발생할 수 있 습니다. 차 안에 어린이나 동물이 있는 상태로 도어 가 잠긴 경우, 비상 키로 운전석 도어의 잠금 을 해제 할 수 있습니다. 비상 키로 운전석 도 어의 잠금을 해제하는 방법은 5장 내 ‘도어’ 를 참고하십시오.\n비상시 도어 잠금 방법\n비상시(배터리 방전 등) 비상 키를 사용하여 수 동으로 도어를 잠글 수 있습니다. 다음 지시에 따라 비상 키를 사용하여 수동으로 도어를 잠그십시오. 모든 도어를 각각 잠가야 합니다. 1. 도어를 여십시오. 2. 도어의 뒤쪽에 위치한 비상 잠금 장치에 비 상 키를 넣고 수평 방향으로 돌리십시오. 3. 도어를 닫으십시'
- A 결과: '비상시 도어 잠금 방법' → '비상시 도어 잠금 방법' (llm_accepted / accepted)
- B 결과: '비상시 비상 키를 사용한 수동 도어 잠금 방법' → '비상시 도어 잠금 방법' (outside_candidate_and_source:사용한)
- blocks (current/expanded/excluded):
  - expanded; bbox `[235.86, 320.1, 323.24, 332.32]`; distance=1.3pt; vgap=1.3pt; same_column=True; owner=True; reason=None; raw='비상시 도어 잠금 방법'
  - expanded; bbox `[235.01, 440.12, 399.0, 551.58]`; distance=1.7pt; vgap=1.7pt; same_column=True; owner=True; reason=None; raw='2C_HowToLockDoorInEmergency\n비상시(배터리 방전 등) 비상 키를 사용하여 수\n동으로 도어를 잠글 수 있습니다.\n다음 지시에 따라 비상 키를 사용하여 수동으로\n도어를 잠그십시오. 모든 도어를 각각 잠가야\n합니다.\n1. 도어를 여십시오.\n2. 도어의 뒤쪽에 위치한 비상 잠금 장치에 비\n상 키를 넣고 수평 방향으로 돌리십시오.\n3. 도어를 닫으십시오.'
  - expanded; bbox `[235.16, 126.59, 399.52, 301.42]`; distance=32.2pt; vgap=32.2pt; same_column=True; owner=True; reason=None; raw='• 차량 출발 전에 운전석에서 중앙 도어 잠금\n버튼을 이용하여 모든 도어를 잠그십시오.\n특히 어린이를 태웠을 때는 반드시 잠금 상\n태로 주행하십시오. 운전 중 실수로 차량의\n도어가 열리게 되면 매우 위험합니다.\n• 차에서 내릴 때는 반드시 시동을 끄고, 스마\n트 키를 가지고 내리십시오. 또한 어린이나\n동물을 차 안에 혼자 남겨 두지 않도록 주의\n하십시오. 도어 잠금 버튼을 누르거나 기타\n장비를 잘못 조작하여 사고가 발생할 수 있\n습니다.\n• 차 안에 어린이나 동물이 있는 상태로 도어\n가 잠긴 경우, 비상 키로 운전석 도어의 잠금\n을 해제 할 수 있습니다. 비상 키로 운전석 도\n어의 잠금을 해제하는 방법은 5장 내 ‘도어’\n를 참고하십시오.'
  - excluded-nearby; bbox `[51.53, 322.17, 214.74, 343.09]`; distance=36.8pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='도어 및 도어 핸들에 무리한 힘을 가하지 마십\n시오. 그렇지 않으면 파손될 수 있습니다.'
  - excluded-nearby; bbox `[51.61, 361.78, 201.58, 374.0]`; distance=60.5pt; vgap=0.0pt; same_column=False; owner=False; reason=다른 column; raw='도어 잠금/잠금 해제 버튼을 사용할 때'
  - excluded-nearby; bbox `[50.91, 82.61, 214.71, 282.42]`; distance=88.0pt; vgap=51.2pt; same_column=False; owner=True; reason=다른 column; raw='• 차에서 내릴 때는 뒤에서 오는 차량이나 오\n토바이, 자전거, 보행자 등에 주의하여 도어\n를 여십시오. 갑자기 도어를 열면 위험합니\n다.\n• 차량을 주행하기 전에 도어가 확실히 닫혔는\n지 확인하십시오. 주행 중에 도어가 열리면\n매우 위험합니다.\n• 혼자 힘으로 차 밖으로 나올 수 없는 어린이\n나 동물을 차 안에 남겨 두지 마십시오. 밀폐\n된 차 안은 외부 기온에 따라 급격하게 기온\n이 변할 뿐만 아니라 질식의 위험이 있어 장\n시간 차 안에 있을 경우 심각한 상해 또는 사\n망으로 이어질 수 있습니다.\n• 도어가 잠겨있는 경우에도 운전석 도어는 실\n내측 도어 핸들을 당기면 열립니다. 운전 중\n차량의 도어가 열리면 매우 위험하므로 도어\n를 열지 마십시오. 부상 또는 사망사고의 원\n인이 될 수 있습니다.'
  - excluded-nearby; bbox `[50.91, 501.8, 214.71, 546.27]`; distance=100.2pt; vgap=63.3pt; same_column=False; owner=False; reason=다른 column; raw='2C_CentralDoorLockButton\n• 도어 잠금(1)\n운전석에 있는 잠금 버튼(1)을 누르면 모든\n도어가 잠깁니다.'
  - excluded-nearby; bbox `[50.89, 381.99, 162.61, 392.91]`; distance=130.6pt; vgap=0.0pt; same_column=False; owner=False; reason=다른 column; raw='중앙 도어 잠금/잠금 해제 버튼'
  - expanded; bbox `[235.16, 63.53, 399.04, 100.21]`; distance=233.4pt; vgap=233.4pt; same_column=True; owner=True; reason=None; raw='• 도어 잠금 해제(2)\n운전석에 있는 잠금 해제 버튼(2)을 누르면\n모든 도어가 잠금 해제됩니다.҃'

### p.141 / image 1

- image bbox: `[50.88, 107.04, 215.27, 211.91]`; candidate: 스티어링 휠(A타입) · 클러스터
- A LLM 전달 context 필드: ['클러스터', '스티어링 휠(A타입)', '다.', '이 표시될 때 스티어링 휠에 있는 OK 버튼\n[A]을 누르십시오. 2차 알림이 1회 해제됩니']
- B LLM 전달 text (71자): '이 표시될 때 스티어링 휠에 있는 OK 버튼 [A]을 누르십시오. 2차 알림이 1회 해제됩니\n다.\n클러스터\n스티어링 휠(A타입)'
- A 결과: '스티어링 휠(A타입) · 클러스터' → '스티어링 휠(A타입) · 클러스터' (llm_accepted / accepted)
- B 결과: '스티어링 휠(A타입) 및 클러스터' → '스티어링 휠(A타입) · 클러스터' (outside_candidate_and_source:및)
- blocks (current/expanded/excluded):
  - expanded; bbox `[120.66, 97.0, 145.46, 105.49]`; distance=1.5pt; vgap=1.5pt; same_column=True; owner=True; reason=None; raw='클러스터'
  - expanded; bbox `[50.91, 215.02, 160.74, 232.36]`; distance=3.1pt; vgap=3.1pt; same_column=True; owner=True; reason=None; raw='2C_CheckRearSeat\n스티어링 휠(A타입)'
  - expanded; bbox `[60.02, 83.71, 70.73, 94.64]`; distance=12.4pt; vgap=12.4pt; same_column=True; owner=True; reason=None; raw='다.'
  - expanded; bbox `[59.39, 63.72, 214.73, 84.64]`; distance=22.4pt; vgap=22.4pt; same_column=True; owner=True; reason=None; raw='이 표시될 때 스티어링 휠에 있는 OK 버튼\n[A]을 누르십시오. 2차 알림이 1회 해제됩니'
  - excluded-nearby; bbox `[235.16, 190.53, 399.06, 303.0]`; distance=35.8pt; vgap=0.0pt; same_column=False; owner=False; reason=다른 column; raw='2C_TheftAlarmSystem\n도난 경보 장치는 시동이 꺼진 상태에서 스마트\n키를 사용하거나 바깥쪽 도어 핸들의 도어 잠금\n버튼(버튼 타입)을 누르거나 센서부(터치 센서\n타입)를 터치하여 도어를 잠그면 작동합니다.\n도난 경고 장치가 작동하는 상태에서 스마트 키\n를 사용하지 않거나 바깥쪽 도어 핸들의 도어\n잠금 버튼을 누르지 않거나 도어 잠금 센서부를\n터치하지 않고 임의로 도어, 트렁크 또는 후드\n를 열면 비상 경고등이 깜빡이고 경고음이 울립\n니다.'
  - excluded-nearby; bbox `[236.14, 62.89, 317.52, 80.0]`; distance=64.6pt; vgap=27.0pt; same_column=False; owner=False; reason=다른 column; raw='도난 경보 장치'
  - excluded-nearby; bbox `[50.91, 341.89, 160.79, 359.24]`; distance=130.0pt; vgap=130.0pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='2C_SteeringWheelOkButton\n스티어링 휠(B타입)'
  - excluded-nearby; bbox `[236.0, 322.52, 281.38, 337.18]`; distance=147.9pt; vgap=110.6pt; same_column=False; owner=False; reason=다른 column; raw='경계 상태'
  - excluded-nearby; bbox `[235.16, 340.84, 398.98, 488.9]`; distance=164.7pt; vgap=128.9pt; same_column=False; owner=False; reason=다른 column; raw='• 스마트 키가 차 안에 있지 않은 상태에서 후\n드와 모든 도어(트렁크 포함)를 닫은 후 스마\n트 키를 사용하거나 바깥쪽 도어 핸들의 도\n어 잠금 버튼을 누르거나 도어 잠금 센서부\n를 터치하여 도어를 잠그십시오. 차량의 비\n상 경고등이 1회 깜빡이고 확인 음이 1회 울\n려 차가 경계 상태에 들어갔음을 알려줍니\n다.\n• 스마트 키의 도어 잠금 버튼( )을 눌러 잠금\n을 할 때 비상 경고등이 깜빡이지 않거나 경\n고음이 울리지 않으면 차가 경계 상태로 들\n어가지 못한 것입니다. 열린 도어가 없는지\n확인 후 닫으면 비상 경고등이 깜빡이면서\n자동으로 경계 상태에 들어갑니다.'

### p.167 / image 1

- image bbox: `[50.88, 77.04, 215.27, 181.91]`; candidate: 파워 트렁크 열림/닫힘 버튼 (실내)
- A LLM 전달 context 필드: ['파워 트렁크 열림/닫힘 버튼 (실내)', '트렁크가 닫힌 상태에서 버튼을 짧게 누르면 경\n고음과 함께 트렁크가 열립니다. 열리는 도중\n에 버튼을 짧게 누르면 원하는 위치에 트렁크를\n정지할 수 있습니다.\n트렁크가 열린 상태에서 버튼을 길게 누르면 트\n렁크가 닫힙니다. 트렁크가 닫히는 도중에 버\n튼에서 손을 떼면, 작동을 멈추고 약 5초 동안\n경고음이 울립니다.']
- B LLM 전달 text (198자): '파워 트렁크 열림/닫힘 버튼 (실내)\n트렁크가 닫힌 상태에서 버튼을 짧게 누르면 경 고음과 함께 트렁크가 열립니다. 열리는 도중 에 버튼을 짧게 누르면 원하는 위치에 트렁크를 정지할 수 있습니다. 트렁크가 열린 상태에서 버튼을 길게 누르면 트 렁크가 닫힙니다. 트렁크가 닫히는 도중에 버 튼에서 손을 떼면, 작동을 멈추고 약 5초 동안 경고음이 울립니다.'
- A 결과: '파워 트렁크 열림/닫힘 버튼(실내)' → '파워 트렁크 열림/닫힘 버튼(실내)' (llm_accepted / accepted)
- B 결과: '실내 파워 트렁크 열림/닫힘 버튼' → '실내 파워 트렁크 열림/닫힘 버튼' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[51.61, 63.51, 188.6, 75.73]`; distance=1.3pt; vgap=1.3pt; same_column=True; owner=True; reason=None; raw='파워 트렁크 열림/닫힘 버튼 (실내)'
  - expanded; bbox `[50.91, 183.53, 214.74, 276.0]`; distance=1.6pt; vgap=1.6pt; same_column=True; owner=True; reason=None; raw='2C_CrushPadTrunkOpenButton\n트렁크가 닫힌 상태에서 버튼을 짧게 누르면 경\n고음과 함께 트렁크가 열립니다. 열리는 도중\n에 버튼을 짧게 누르면 원하는 위치에 트렁크를\n정지할 수 있습니다. \n트렁크가 열린 상태에서 버튼을 길게 누르면 트\n렁크가 닫힙니다. 트렁크가 닫히는 도중에 버\n튼에서 손을 떼면, 작동을 멈추고 약 5초 동안\n경고음이 울립니다.'
  - excluded-nearby; bbox `[235.16, 183.53, 399.05, 223.01]`; distance=37.4pt; vgap=1.6pt; same_column=False; owner=False; reason=다른 column; raw='2C_TrunkTrimTrunkOpenButton\n버튼을 누르면 트렁크가 닫힙니다. 닫히는 도\n중에 버튼을 짧게 누르면 원하는 위치에 트렁크\n를 정지할 수 있습니다.'
  - excluded-nearby; bbox `[235.86, 63.51, 323.24, 75.73]`; distance=38.4pt; vgap=1.3pt; same_column=False; owner=False; reason=다른 column; raw='파워 트렁크 닫힘 버튼'
  - excluded-nearby; bbox `[235.86, 236.86, 323.24, 249.08]`; distance=92.0pt; vgap=54.9pt; same_column=False; owner=False; reason=다른 column; raw='파워 트렁크 잠금 버튼'
  - excluded-nearby; bbox `[51.61, 289.84, 138.99, 302.06]`; distance=107.9pt; vgap=107.9pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='파워 트렁크 열림 버튼'
  - excluded-nearby; bbox `[235.16, 356.89, 398.97, 416.36]`; distance=210.8pt; vgap=175.0pt; same_column=False; owner=False; reason=다른 column; raw='2C_TrunkTrimTrunkLockButton\n스마트 키를 휴대한 상태에서 버튼을 누르면트\n렁크가 닫히고, 모든 도어가 잠깁니다. 모든 도\n어가 닫혀 있고, 시동 ‘OFF’ 상태에서만 버튼을\n사용하여 트렁크를 닫고, 모든 도어를 잠글 수\n있습니다.'
  - excluded-nearby; bbox `[50.91, 409.86, 214.71, 469.34]`; distance=227.9pt; vgap=227.9pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='2C_OutsideTrunkOpenButton\n트렁크가 닫힌 상태에서 버튼(1)을 누르면 트렁\n크가 열립니다. 차량이 잠긴 상태에서 트렁크\n를 열려면 스마트 키를 휴대하고 버튼을 누르십\n시오. 열리는 도중에 버튼을 짧게 누르면 원하\n는 위치에 트렁크를 정지할 수 있습니다.'

### p.174 / image 2

- image bbox: `[221.03, 191.75, 385.42, 296.63]`; candidate: 아닌 다른 부분을 누르면 연료 주입구 커버
- A LLM 전달 context 필드: ['3. 연료 주입구 커버가 열립니다.\n추운 날씨에 커버 주변이 얼어서 연료 주입\n구 커버가 열리지 않으면, 커버 주위를 가볍\n게 두드리거나 누르십시오.\n만일 과충전이 되었을 경우 가까운 당사 직\n영 하이테크센터에 문의 후 조치 바랍니다(\n과충전 방지 장치: 80 % 충전 시 연료 자동\n차단).', '연료 주입구 커버의 오른쪽 끝 중앙 부분이\n아닌 다른 부분을 누르면 연료 주입구 커버\n가 열리지 않을 수 있습니다.', '1. 엔진에 시동을 반드시 끄십시오.\n2. 연료 주입구 커버의 오른쪽 끝 중앙 부분(1)\n을 누르십시오.']
- B LLM 전달 text (309자): '연료 주입구 여는 방법 (LPI 차량)\n1. 엔진에 시동을 반드시 끄십시오. 2. 연료 주입구 커버의 오른쪽 끝 중앙 부분(1) 을 누르십시오.\n연료 주입구 커버의 오른쪽 끝 중앙 부분이 아닌 다른 부분을 누르면 연료 주입구 커버 가 열리지 않을 수 있습니다.\n3. 연료 주입구 커버가 열립니다. 추운 날씨에 커버 주변이 얼어서 연료 주입 구 커버가 열리지 않으면, 커버 주위를 가볍 게 두드리거나 누르십시오. 만일 과충전이 되었을 경우 가까운 당사 직 영 하이테크센터에 문의 후 조치 바랍니다( 과충전 방지 장치: 80 % 충전 시 연료 자동 차단).'
- A 결과: '다른 부분을 누르면 연료 주입구 커버가 열리지 않을 수 있음' → '아닌 다른 부분을 누르면 연료 주입구 커버' (fallback_candidate / new_tokens:수,않을,열리지,있음,커버가)
- B 결과: '연료 주입구 커버 오른쪽 끝 중앙 부분' → '연료 주입구 커버 오른쪽 끝 중앙 부분' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[220.98, 298.19, 385.22, 393.66]`; distance=1.6pt; vgap=1.6pt; same_column=True; owner=True; reason=None; raw='2C_FuelInletDoor\n3. 연료 주입구 커버가 열립니다.\n추운 날씨에 커버 주변이 얼어서 연료 주입\n구 커버가 열리지 않으면, 커버 주위를 가볍\n게 두드리거나 누르십시오.\n만일 과충전이 되었을 경우 가까운 당사 직\n영 하이테크센터에 문의 후 조치 바랍니다(\n과충전 방지 장치: 80 % 충전 시 연료 자동\n차단).'
  - expanded; bbox `[230.07, 136.58, 384.86, 169.47]`; distance=22.3pt; vgap=22.3pt; same_column=True; owner=True; reason=None; raw='연료 주입구 커버의 오른쪽 끝 중앙 부분이\n아닌 다른 부분을 누르면 연료 주입구 커버\n가 열리지 않을 수 있습니다.'
  - excluded-nearby; bbox `[36.73, 84.57, 200.56, 280.42]`; distance=36.8pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='주유하기 전에 반드시 엔진을 끄십시오. 엔진\n의 전기장치에 의한 스파크로 인해 기화된 연료\n에 불이 붙을 수도 있습니다. 주유하기 전에 엔\n진을 끄고, 주유가 끝난 뒤에는 연료 주입구 캡\n을 완전히 잠그고, 주입구 커버를 닫은 후 시동\n을 거십시오.\n• 주유소 근처에서 담배를 피우거나 라이터를\n켜는 등 화재의 위험이 있는 행동을 삼가십\n시오. 자동차 연료는 인화성 물질이므로 불\n꽃에 의해 폭발할 수도 있습니다. \n• 만약 주유 중 화재가 발생하게 되면, 차에서\n멀리 떨어져 안전을 확보한 후 즉시 주유소\n관리자 및 소방서에 알려 지시를 받으십시\n오.\n• 전기적 결함이 있을 때 등 특정상황에서 연\n료도어 동작이 되지 않는 경우, 당사 직영 하\n이테크 센터나 블루핸즈에서 점검 및 정비를\n받으십시오.'
  - excluded-nearby; bbox `[36.73, 318.2, 200.56, 563.01]`; distance=58.4pt; vgap=21.6pt; same_column=False; owner=False; reason=다른 column; raw='• 지정된 연료 외 다른 연료(등유, 알코올, 항공\n유 등)와 혼합하여 사용하지 마십시오.\n• 불량 연료나 미검증된 연료(첨가제) 등을 사\n용하면, 연료 탱크 오염, 연료 펌프 손상 및\n연료필터의 조기 막힘 등으로 인해 엔진과\n배출가스 점화장치가 손상될 수 있습니다.\n• 연료 주입구 캡을 교체해야 할 때는, 품질과\n성능이 적합한 부품을 사용하십시오. 품질이\n나 성능이 부적합한 캡을 사용하면 연료 장\n치 또는 배기제어 장치에 심각한 고장이 발\n생할 수 있습니다. 순정부품은 품질과 성능\n을 당사가 보증하는 부품입니다.\n• 차량의 바깥 표면에 연료를 떨어뜨리지 마십\n시오. 도장 표면에 연료가 떨어지면 도장이\n손상될 수 있습니다.\n• 연료 주입구 캡을 완전히 잠그지 않을 경우\n엔진 경고등(\n )이 켜질 수 있으나 이는 차\n량이나 부품의 고장이 아니므로 연료 주입구\n캡을 “딸깍” 소리가 나도록 다시 잠그십시\n오. 다시 장착한 후에도 엔진 경고등이 켜질\n경우 당사 직영 하이테크센터나 블루핸즈에\n서 점검을 받으십시오.'
  - expanded; bbox `[220.96, 81.71, 385.47, 115.63]`; distance=76.1pt; vgap=76.1pt; same_column=True; owner=True; reason=None; raw='1. 엔진에 시동을 반드시 끄십시오.\n2. 연료 주입구 커버의 오른쪽 끝 중앙 부분(1)\n을 누르십시오.'
  - expanded; bbox `[221.83, 63.2, 378.92, 77.86]`; distance=113.9pt; vgap=113.9pt; same_column=True; owner=True; reason=None; raw='연료 주입구 여는 방법 (LPI 차량)'

### p.180 / image 3

- image bbox: `[221.03, 77.04, 385.42, 181.91]`; candidate: 휴대폰 앱 연결을 위한 Wi-Fi 를 활성화 하거
- A LLM 전달 context 필드: ['앱 연결', 'Wi-Fi 설정', '휴대폰 앱 연결을 위한 Wi-Fi 를 활성화 하거\n나, Wi-Fi 비밀번호를 설정할 수 있습니다.']
- B LLM 전달 text (68자): '앱 연결\nWi-Fi 설정\n휴대폰 앱 연결을 위한 Wi-Fi 를 활성화 하거 나, Wi-Fi 비밀번호를 설정할 수 있습니다.'
- A 결과: '휴대폰 앱 연결을 위한 Wi-Fi 활성화' → '휴대폰 앱 연결을 위한 Wi-Fi 활성화' (llm_accepted / accepted)
- B 결과: '휴대폰 앱 연결을 위한 Wi-Fi 활성화 및 비밀번호 설정' → '휴대폰 앱 연결을 위한 Wi-Fi 를 활성화 하거' (outside_candidate_and_source:및)
- blocks (current/expanded/excluded):
  - expanded; bbox `[221.69, 63.51, 250.39, 75.73]`; distance=1.3pt; vgap=1.3pt; same_column=True; owner=True; reason=None; raw='앱 연결'
  - expanded; bbox `[220.34, 199.08, 262.11, 210.01]`; distance=17.2pt; vgap=17.2pt; same_column=True; owner=True; reason=None; raw='Wi-Fi 설정'
  - expanded; bbox `[221.58, 212.08, 384.79, 233.0]`; distance=30.2pt; vgap=30.2pt; same_column=True; owner=True; reason=None; raw='휴대폰 앱 연결을 위한 Wi-Fi 를 활성화 하거\n나, Wi-Fi 비밀번호를 설정할 수 있습니다.'
  - excluded-nearby; bbox `[36.73, 183.53, 200.52, 243.01]`; distance=38.5pt; vgap=1.6pt; same_column=False; owner=False; reason=다른 column; raw='2C_BuiltInCamEventDetectionSensitivityAVN\n주행 및 주차 중 이벤트 녹화 여부의 기준이 되\n는 충격 감지 민감도를 선택할 수 있습니다. 1단\n계(매우 둔감), 2단계(둔감), 3단계(보통), 4단\n계(민감), 5단계(매우 민감) 중에 원하는 감지\n조건을 선택하십시오.'
  - excluded-nearby; bbox `[220.97, 242.07, 384.89, 315.99]`; distance=60.2pt; vgap=60.2pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='주차 중 이벤트 휴대폰 알림\n차량을 잠근 후 도난 경보 장치가 작동 중인 상\n태에서 주차 중 이벤트 영상이 저장되면 마이현\n대 앱으로 메시지와 동영상을 전송하여 충격 감\n지를 알립니다. 주차 후 최대 5회까지만 서비스\n가 제공되며, 알림 서비스를 사용하려면 주차\n중 이벤트 휴대폰 알림을 선택하십시오.'
  - excluded-nearby; bbox `[220.98, 342.93, 384.86, 457.78]`; distance=161.0pt; vgap=161.0pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='• 주차 중 이벤트 휴대폰 알림은 블루링크 서\n비스에 가입한 경우에만 사용할 수 있습니\n다. \n• 주차 후 휴대폰 알림 횟수(5회)가 초과되어\n알림이 오지 않더라도 녹화는 작동하고 있습\n니다.\n• 주차 중 이벤트 휴대폰 알림 기능을 사용할\n경우 차량의 배터리 전력이 소모되어, 예상\n했던 주차 녹화 가능 시간 이전에 녹화가 종\n료될 수 있습니다.'
  - excluded-nearby; bbox `[36.73, 376.88, 200.38, 416.35]`; distance=232.1pt; vgap=195.0pt; same_column=False; owner=False; reason=다른 column; raw='2C_BuiltInCamDisplaySettings\n전/후방 녹화 영상의 높이를 조절할 수 있습니\n다. 영상 화면을 보고 원하는 높이를 선택하십\n시오.'

### p.181 / image 1

- image bbox: `[50.88, 77.04, 215.27, 181.91]`; candidate: SD 메모리
- A LLM 전달 context 필드: ['녹화 영상 저장을 위한 SD 메모리의 수명 상태,\nSD 메모리 단자 위치를 확인할 수 있습니다.\nSD 메모리를 안전하게 제거하지 않는 경우 저', 'SD 메모리', '장된 파일 또는 파일 시스템이 손상될 수 있습\n니다. 연결 해제 버튼을 누른 후 메모리를 안전\n하게 제거하십시오.\nSD 메모리를 초기화 할 경우 저장된 모든 파일']
- B LLM 전달 text (277자): 'SD 메모리\n녹화 영상 저장을 위한 SD 메모리의 수명 상태, SD 메모리 단자 위치를 확인할 수 있습니다. SD 메모리를 안전하게 제거하지 않는 경우 저\n장된 파일 또는 파일 시스템이 손상될 수 있습 니다. 연결 해제 버튼을 누른 후 메모리를 안전 하게 제거하십시오. SD 메모리를 초기화 할 경우 저장된 모든 파일\n이 삭제되니, 초기화 이전에 보관이 필요한 파 일은 필히 백업해 주십시오.\n정품 SD 메모리를 사용하지 않는 경우 SD 메모 리의 수명 상태 정보는 표시되지 않을 수 있습 니다.'
- A 결과: 'SD 메모리' → 'SD 메모리' (llm_accepted / accepted)
- B 결과: '녹화 영상 저장용 SD 메모리' → 'SD 메모리' (outside_candidate_and_source:저장용)
- blocks (current/expanded/excluded):
  - expanded; bbox `[50.91, 63.51, 92.0, 75.73]`; distance=1.3pt; vgap=1.3pt; same_column=True; owner=True; reason=None; raw='SD 메모리'
  - expanded; bbox `[50.88, 183.53, 215.32, 226.01]`; distance=1.6pt; vgap=1.6pt; same_column=True; owner=True; reason=None; raw='2C_BuiltInCamSDMemory\n녹화 영상 저장을 위한 SD 메모리의 수명 상태,\nSD 메모리 단자 위치를 확인할 수 있습니다. \nSD 메모리를 안전하게 제거하지 않는 경우 저'
  - excluded-nearby; bbox `[235.86, 93.5, 360.06, 105.72]`; distance=37.1pt; vgap=0.0pt; same_column=False; owner=False; reason=다른 column; raw='빌트인 캠 SD 메모리 제거/삽입'
  - excluded-nearby; bbox `[236.0, 63.2, 309.15, 77.86]`; distance=37.3pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='빌트인 캠 작동'
  - expanded; bbox `[50.83, 225.08, 214.7, 269.0]`; distance=43.2pt; vgap=43.2pt; same_column=True; owner=True; reason=None; raw='장된 파일 또는 파일 시스템이 손상될 수 있습\n니다. 연결 해제 버튼을 누른 후 메모리를 안전\n하게 제거하십시오.\nSD 메모리를 초기화 할 경우 저장된 모든 파일'
  - excluded-nearby; bbox `[235.16, 213.52, 398.99, 263.0]`; distance=67.4pt; vgap=31.6pt; same_column=False; owner=False; reason=다른 column; raw='2C_BuiltInCamUSBPort\n차량이 출고될 때 SD 메모리는 메모리 카드 단\n자에 삽입되어 있습니다. SD 메모리 제거/삽입\n방법을 확인하신 후 안전하게 메모리를 제거하\n거나 삽입하십시오.'
  - expanded; bbox `[51.42, 268.07, 214.57, 289.0]`; distance=86.2pt; vgap=86.2pt; same_column=True; owner=True; reason=None; raw='이 삭제되니, 초기화 이전에 보관이 필요한 파\n일은 필히 백업해 주십시오.'
  - excluded-nearby; bbox `[234.51, 272.06, 399.54, 305.98]`; distance=124.8pt; vgap=90.1pt; same_column=False; owner=False; reason=다른 column; raw='SD 메모리 제거\nSD 메모리를 탈거하려면 먼저 빌트인 캠 설정 >\nSD 메모리 메뉴의 연결 해제 버튼을 누른 후 메'
  - expanded; bbox `[51.51, 317.9, 214.73, 348.82]`; distance=136.0pt; vgap=136.0pt; same_column=True; owner=True; reason=None; raw='정품 SD 메모리를 사용하지 않는 경우 SD 메모\n리의 수명 상태 정보는 표시되지 않을 수 있습\n니다.'
  - excluded-nearby; bbox `[235.72, 305.05, 398.95, 345.97]`; distance=159.9pt; vgap=123.1pt; same_column=False; owner=False; reason=다른 column; raw='모리를 손톱으로 눌러 메모리 카드 단자에서 제\n거하십시오. 메모리를 안전하게 제거하지 않고\n작동 중에 제거하는 경우 저장된 파일 또는 파\n일 시스템이 손상될 수 있습니다.'

### p.198 / image 3

- image bbox: `[221.03, 215.75, 385.42, 320.63]`; candidate: 하이빔 보조
- A LLM 전달 context 필드: ["시동 'ON' 상태에서 인포테인먼트 시스템의 설\n정 > 차량 > 라이트 > 하이빔 보조를 선택하면\n하이빔 보조가 켜지고 선택을 해제할 경우 꺼집\n니다.҃", '하이빔 보조', '하이빔 보조 설정']
- B LLM 전달 text (102자): "하이빔 보조 설정\n하이빔 보조\n시동 'ON' 상태에서 인포테인먼트 시스템의 설 정 > 차량 > 라이트 > 하이빔 보조를 선택하면 하이빔 보조가 켜지고 선택을 해제할 경우 꺼집 니다.҃"
- A 결과: '하이빔 보조' → '하이빔 보조' (llm_accepted / accepted)
- B 결과: '하이빔 보조 설정' → '하이빔 보조 설정' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[221.69, 202.16, 271.43, 214.38]`; distance=1.4pt; vgap=1.4pt; same_column=True; owner=True; reason=None; raw='하이빔 보조'
  - expanded; bbox `[220.98, 322.18, 384.8, 372.24]`; distance=1.6pt; vgap=1.6pt; same_column=True; owner=True; reason=None; raw="2C_HBASetInfo\n시동 'ON' 상태에서 인포테인먼트 시스템의 설\n정 > 차량 > 라이트 > 하이빔 보조를 선택하면\n하이빔 보조가 켜지고 선택을 해제할 경우 꺼집\n니다.҃"
  - expanded; bbox `[221.83, 171.86, 302.28, 186.53]`; distance=29.2pt; vgap=29.2pt; same_column=True; owner=True; reason=None; raw='하이빔 보조 설정'
  - excluded-nearby; bbox `[36.73, 190.53, 200.58, 230.01]`; distance=36.8pt; vgap=0.0pt; same_column=False; owner=False; reason=다른 column; raw='2C_HBASwitch\n마주 오는 차량 또는 선행 차량의 램프 등 주변\n광원 및 조도를 인식하여 전조등을 자동으로 상\n향 또는 하향으로 전환하도록 도와줍니다.'
  - excluded-nearby; bbox `[36.73, 256.96, 186.84, 269.85]`; distance=61.5pt; vgap=0.0pt; same_column=False; owner=False; reason=다른 column; raw='HBA는 High Beam Assist의 약자입니다.'
  - excluded-nearby; bbox `[221.51, 137.56, 282.93, 148.49]`; distance=67.3pt; vgap=67.3pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='을 참고하십시오.'
  - excluded-nearby; bbox `[220.89, 84.57, 385.29, 138.49]`; distance=77.3pt; vgap=77.3pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='하이빔 보조는 전방 카메라를 이용하는 기능으\n로 그 성능을 최적으로 유지하기 위해서는 전방\n카메라의 관리에 주의가 필요합니다. \n전방 카메라에 대한 자세한 주의 사항은 7장 내\n‘전방 충돌방지 보조 (FCA) (전방 카메라 단독)’'
  - excluded-nearby; bbox `[221.62, 400.58, 384.77, 421.5]`; distance=80.0pt; vgap=80.0pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='하이빔 보조를 설정할 때에는 반드시 안전한 곳\n에 정차한 후 조작하십시오.'
  - excluded-nearby; bbox `[37.32, 430.12, 200.57, 484.04]`; distance=146.3pt; vgap=109.5pt; same_column=False; owner=False; reason=다른 column; raw='주행 중 주변의 광원 및 조도를 인식하기 위해\n서 인식 센서로 전방 카메라를 인식 센서로 사\n용합니다.\n인식 센서의 상세 위치는 그림을 참고하십시\n오.'
  - excluded-nearby; bbox `[37.72, 62.89, 144.1, 80.0]`; distance=274.2pt; vgap=135.8pt; same_column=False; owner=False; reason=다른 column; raw='하이빔 보조 (HBA)'

### p.199 / image 3

- image bbox: `[234.95, 172.79, 399.58, 277.91]`; candidate: 하이빔 보조 이상 및 제한 사항 · 기능 이상
- A LLM 전달 context 필드: ['하이빔 보조에 이상이 있으면 클러스터에 경고\n문이 표시되고 경고등이 켜집니다.\n당사 직영 하이테크센터나 블루핸즈에서 점검\n을 받으십시오.\n경고 내용은 클러스터의 뷰 모드 중 유틸리\n티 정보 뷰의 서비스 메시지에서 확인할 수\n있습니다.', '기능 이상', '하이빔 보조 이상 및 제한 사항', '클러스터 사양 또는 테마에 따라 클러스터에 표\n시되는 이미지나 색상이 다를 수 있습니다.']
- B LLM 전달 text (204자): '클러스터 사양 또는 테마에 따라 클러스터에 표 시되는 이미지나 색상이 다를 수 있습니다.\n하이빔 보조 이상 및 제한 사항\n기능 이상\n하이빔 보조에 이상이 있으면 클러스터에 경고 문이 표시되고 경고등이 켜집니다. 당사 직영 하이테크센터나 블루핸즈에서 점검 을 받으십시오. 경고 내용은 클러스터의 뷰 모드 중 유틸리 티 정보 뷰의 서비스 메시지에서 확인할 수 있습니다.'
- A 결과: '하이빔 보조 이상 및 제한 사항 · 기능 이상' → '하이빔 보조 이상 및 제한 사항 · 기능 이상' (llm_accepted / accepted)
- B 결과: '하이빔 보조 기능 이상' → '하이빔 보조 기능 이상' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[235.86, 159.18, 273.8, 171.4]`; distance=1.4pt; vgap=1.4pt; same_column=True; owner=True; reason=None; raw='기능 이상'
  - expanded; bbox `[235.16, 279.44, 399.04, 366.9]`; distance=1.5pt; vgap=1.5pt; same_column=True; owner=True; reason=None; raw='2C_ForwardSafetyMalfunctionInfo\n하이빔 보조에 이상이 있으면 클러스터에 경고\n문이 표시되고  경고등이 켜집니다. \n당사 직영 하이테크센터나 블루핸즈에서 점검\n을 받으십시오.\n• 경고 내용은 클러스터의 뷰 모드 중 유틸리\n티 정보 뷰의 서비스 메시지에서 확인할 수\n있습니다.'
  - expanded; bbox `[236.0, 128.88, 378.44, 143.55]`; distance=29.2pt; vgap=29.2pt; same_column=True; owner=True; reason=None; raw='하이빔 보조 이상 및 제한 사항'
  - excluded-nearby; bbox `[50.91, 159.69, 214.73, 248.57]`; distance=36.4pt; vgap=0.0pt; same_column=False; owner=False; reason=다른 column; raw='다. 상향등이 켜지면 클러스터에 전조등\n상향 표시등( )이 켜집니다. 속도를 줄여\n20 km/h 미만으로 주행하면 상향등이 켜\n지지 않고 하이빔 보조 표시등( )이 흰색\n으로 표시됩니다.\n• 하이빔 보조 작동 중에 조명 스위치를 조작\n하면 아래와 같이 작동합니다.\n- 상향등이 켜지지 않은 상태에서 조명 스위'
  - excluded-nearby; bbox `[59.27, 247.65, 214.65, 291.57]`; distance=36.5pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='치를 당길 경우 상향등이 켜집니다. 이후\n조명 스위치를 놓을 경우 하이빔 보조가\n다시 작동합니다.\n- 하이빔 보조에 의해 상향등이 켜진 상태에'
  - excluded-nearby; bbox `[67.77, 149.69, 214.42, 160.62]`; distance=49.1pt; vgap=12.2pt; same_column=False; owner=False; reason=다른 column; raw='km/h 이상이면 상향등이 켜질 수 있습니'
  - excluded-nearby; bbox `[59.2, 290.64, 214.51, 324.56]`; distance=49.5pt; vgap=12.7pt; same_column=False; owner=True; reason=다른 column; raw='서 조명 스위치를 당기면 하향등이 켜지고\n하이빔 보조가 해제됩니다. \n- 조명 스위치를 클러스터 쪽으로 밀면 상시'
  - excluded-nearby; bbox `[59.28, 116.7, 215.16, 150.62]`; distance=57.8pt; vgap=22.2pt; same_column=False; owner=False; reason=다른 column; raw='돌리고 클러스터 방향으로 밀면 클러스터\n에 하이빔 보조 표시등( )이 켜집니다.\n- 하이빔 보조 작동 상태에서 차속이 30'
  - expanded; bbox `[235.79, 84.57, 398.95, 105.5]`; distance=67.3pt; vgap=67.3pt; same_column=True; owner=True; reason=None; raw='클러스터 사양 또는 테마에 따라 클러스터에 표\n시되는 이미지나 색상이 다를 수 있습니다.'
  - excluded-nearby; bbox `[59.15, 323.63, 214.46, 357.55]`; distance=82.6pt; vgap=45.7pt; same_column=False; owner=True; reason=다른 column; raw='상향등이 켜지고 하이빔 보조가 해제됩니\n다.\n- 조명 스위치를 AUTO에서 다른 위치(하향'
  - excluded-nearby; bbox `[50.91, 81.52, 214.73, 117.62]`; distance=91.6pt; vgap=55.2pt; same_column=False; owner=False; reason=다른 column; raw='• 설정 메뉴에서 하이빔 보조를 선택하고 아래\n와 같이 조작하면 작동 상태가 됩니다.\n- 조명 스위치를 AUTO(자동 켜짐) 위치로'
  - excluded-nearby; bbox `[50.91, 356.63, 214.73, 471.49]`; distance=115.1pt; vgap=78.7pt; same_column=False; owner=True; reason=다른 column; raw='등/미등/OFF)로 돌리면 해당 등이 켜지고\n하이빔 보조가 해제됩니다. \n• 하이빔 보조가 작동하여 상향등이 켜진 상태\n에서 다음과 같은 상황이 발생하면 하향등\n상태로 자동 전환될 수 있습니다. 다양한 운\n전 환경을 고려하여 상황에 맞게 기을 사용\n하십시오.\n- 다가오는 차량의 전조등을 감지할 경우\n- 앞서가는 차량의 후미등을 감지할 경우\n- 자전거 및 이륜차의 전조등 또는 후미등을'
  - excluded-nearby; bbox `[59.23, 470.56, 214.7, 494.48]`; distance=229.1pt; vgap=192.7pt; same_column=False; owner=True; reason=다른 column; raw='감지할 경우\n- 상향등을 켜지 않아도 될 만큼 주위가 밝'
  - excluded-nearby; bbox `[59.41, 493.53, 214.72, 517.46]`; distance=252.0pt; vgap=215.6pt; same_column=False; owner=True; reason=다른 column; raw='을 경우\n- 전방에 가로등이나 기타 광원이 있을 경우'

### p.201 / image 5

- image bbox: `[234.95, 241.91, 399.58, 346.79]`; candidate: 버튼을 누르면 램프가 켜지고 다시 한번 누
- A LLM 전달 context 필드: ['퍼스널 램프(사양 적용 시)', ': 버튼을 누르면 램프가 켜지고 다시 한번 누\n르면 꺼집니다.']
- B LLM 전달 text (50자): '퍼스널 램프(사양 적용 시)\n: 버튼을 누르면 램프가 켜지고 다시 한번 누 르면 꺼집니다.'
- A 결과: '버튼을 누르면 램프가 켜지고 다시 누르면 꺼집니다.' → '버튼을 누르면 램프가 켜지고 다시 한번 누' (fallback_candidate / new_tokens:꺼집니다)
- B 결과: '퍼스널 램프 버튼' → '퍼스널 램프 버튼' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[281.28, 231.87, 353.93, 240.37]`; distance=1.5pt; vgap=1.5pt; same_column=True; owner=True; reason=None; raw='퍼스널 램프(사양 적용 시)'
  - expanded; bbox `[235.16, 349.89, 398.91, 379.37]`; distance=3.1pt; vgap=3.1pt; same_column=True; owner=True; reason=None; raw='2C_RoomLamp_2\n : 버튼을 누르면 램프가 켜지고 다시 한번 누\n르면 꺼집니다.'
  - excluded-nearby; bbox `[235.16, 200.03, 398.91, 229.51]`; distance=12.4pt; vgap=12.4pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='2C_RoomLamp\n : 버튼을 누르면 램프가 켜지고 다시 한번 누\n르면 꺼집니다.'
  - excluded-nearby; bbox `[50.91, 188.53, 214.73, 339.97]`; distance=36.4pt; vgap=0.0pt; same_column=False; owner=False; reason=다른 column; raw="2C_MapLampButton\n• 렌즈를 누르면 해당 맵 램프가 켜지고 다시\n한번 누르면 꺼집니다.\n•\n : 버튼을 누르면 앞좌석과 뒷좌석 램프가\n켜지고 다시 한번 누르면 꺼집니다.\n•\n : 도어를 열면 앞좌석과 뒷좌석 램프가 켜\n지고 닫으면 약 30초간 켜진 후 꺼집니다. 또\n한 스마트 키로 도어 잠금을 해제하면 앞좌\n석과 뒷좌석 램프가 약 30초 동안 켜진 후 꺼\n집니다. 실내등이 켜진 상태를 유지하는 동\n안, 시동을 켜거나 모든 도어를 잠그면 꺼집\n니다. 시동 'OFF' 또는 'ACC' 상태에서 도어\n가 열리면 실내등이 최대 20분 동안 켜진 후\n꺼집니다."
  - excluded-nearby; bbox `[236.0, 398.92, 306.49, 413.59]`; distance=52.1pt; vgap=52.1pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='선바이저 램프'
  - excluded-nearby; bbox `[287.58, 82.0, 347.63, 90.5]`; distance=151.4pt; vgap=151.4pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='룸 램프(사양 적용 시)'
  - excluded-nearby; bbox `[236.0, 63.2, 305.65, 77.86]`; distance=164.0pt; vgap=164.0pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='뒷좌석 룸 램프'
  - excluded-nearby; bbox `[235.16, 524.25, 399.57, 553.98]`; distance=177.5pt; vgap=177.5pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='2C_SunvisorLamp\n선바이저를 열고 \n에 두면 램프가 켜지고,\n에 두면 램프가 꺼집니다.'

### p.206 / image 1

- image bbox: `[36.72, 107.28, 385.42, 253.91]`; candidate: 히터 및 에어컨 (수동 조절식) · 편의 장치
- A LLM 전달 context 필드: ['A타입', 'B타입', '히터 및 에어컨 (수동 조절식)', '편의 장치']
- B LLM 전달 text (31자): '편의 장치\n히터 및 에어컨 (수동 조절식)\nA타입\nB타입'
- A 결과: '히터 및 에어컨(수동 조절식) · 편의 장치' → '히터 및 에어컨(수동 조절식) · 편의 장치' (llm_accepted / accepted)
- B 결과: '히터 및 에어컨 수동 조절식' → '히터 및 에어컨 수동 조절식' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[202.61, 97.25, 218.97, 105.75]`; distance=1.5pt; vgap=1.5pt; same_column=True; owner=True; reason=None; raw='A타입'
  - expanded; bbox `[36.73, 256.94, 219.02, 274.29]`; distance=3.0pt; vgap=3.0pt; same_column=True; owner=True; reason=None; raw='1C_Aircon_2_TypeA\nB타입'
  - expanded; bbox `[37.72, 62.89, 198.33, 80.0]`; distance=27.3pt; vgap=27.3pt; same_column=True; owner=True; reason=None; raw='히터 및 에어컨 (수동 조절식)'
  - expanded; bbox `[37.58, 27.73, 72.63, 38.93]`; distance=68.3pt; vgap=68.3pt; same_column=True; owner=True; reason=None; raw='편의 장치'
  - excluded-nearby; bbox `[36.69, 442.04, 131.75, 543.94]`; distance=188.1pt; vgap=188.1pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='(1) 풍량 조절\n(2) 온도 조절\n(3) 바람 방향 선택\n(4) 앞유리 서리 제거\n(5) 뒷유리(열선) 서리 제거\n(6) 에어컨 선택\n(7) 내기/외기 선택\n(8) 최대 냉방 선택'

### p.224 / image 1

- image bbox: `[221.03, 149.99, 385.42, 254.87]`; candidate: 에어컨 냉매 및 압축기 윤활유량 점
- A LLM 전달 context 필드: ['이 차량은 친환경적인 신냉매 R-1234yf가 적\n용되어 있습니다. 신냉매는 기존에 적용되어\n있던 구냉매 R-134a와 대비하여 지구온난화\n현상을 크게 줄일 수 있습니다. 실제 차량에 사\n용된 냉매 종류와 용량을 알 수 있도록 엔진룸\n에 사양 라벨이 붙어 있습니다.', '냉매량이 부족하면 에어컨의 성능이 저하됩니\n다. 또한 충전을 지나치게 하는 것도 에어컨에\n좋지 않은 영향을 주므로 이상이 발견되면 당사\n직영 하이테크센터나 블루핸즈에서 점검을 받\n으십시오.', '에어컨 냉매 및 압축기 윤활유량 점']
- B LLM 전달 text (274자): '에어컨 냉매 및 압축기 윤활유량 점\n냉매량이 부족하면 에어컨의 성능이 저하됩니 다. 또한 충전을 지나치게 하는 것도 에어컨에 좋지 않은 영향을 주므로 이상이 발견되면 당사 직영 하이테크센터나 블루핸즈에서 점검을 받 으십시오.\n이 차량은 친환경적인 신냉매 R-1234yf가 적 용되어 있습니다. 신냉매는 기존에 적용되어 있던 구냉매 R-134a와 대비하여 지구온난화 현상을 크게 줄일 수 있습니다. 실제 차량에 사 용된 냉매 종류와 용량을 알 수 있도록 엔진룸 에 사양 라벨이 붙어 있습니다.'
- A 결과: '에어컨 냉매 및 압축기 윤활유량 점검' → '에어컨 냉매 및 압축기 윤활유량 점' (fallback_candidate / new_tokens:점검)
- B 결과: '에어컨 냉매 및 압축기 윤활유량 점검' → '에어컨 냉매 및 압축기 윤활유량 점검' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[220.98, 256.5, 384.76, 325.97]`; distance=1.6pt; vgap=1.6pt; same_column=True; owner=True; reason=None; raw='2C_RefrigerantTypeLabel\n이 차량은 친환경적인 신냉매 R-1234yf가 적\n용되어 있습니다. 신냉매는 기존에 적용되어\n있던 구냉매 R-134a와 대비하여 지구온난화\n현상을 크게 줄일 수 있습니다. 실제 차량에 사\n용된 냉매 종류와 용량을 알 수 있도록 엔진룸\n에 사양 라벨이 붙어 있습니다.'
  - expanded; bbox `[221.52, 96.7, 384.77, 147.62]`; distance=2.4pt; vgap=2.4pt; same_column=True; owner=True; reason=None; raw='냉매량이 부족하면 에어컨의 성능이 저하됩니\n다. 또한 충전을 지나치게 하는 것도 에어컨에\n좋지 않은 영향을 주므로 이상이 발견되면 당사\n직영 하이테크센터나 블루핸즈에서 점검을 받\n으십시오.'
  - excluded-nearby; bbox `[36.71, 81.71, 201.01, 156.2]`; distance=36.0pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw="품질과 성능이 적합한 공조 장치용 에어필터를\n12개월마다 교체하십시오. 순정 부품은 품질과\n성능을 당사가 보증하는 부품입니다. 혼잡하거\n나 먼지가 많은 도로를 운전할 때는 정해진 교\n체 주기보다 더 자주 교체하십시오.\n자세한 내용은 9장 내 '공조 장치용 에어필터'\n을 참고하십시오.҃"
  - excluded-nearby; bbox `[36.71, 184.53, 200.58, 215.45]`; distance=36.8pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='분사형 탈취제는 엔진이 완전히 냉각된 후 개방\n된 공간에서 사용하십시오. 탈취제에 들어있는\nLP가스와 에탄올이 엔진실로 들어가 불꽃을 일'
  - excluded-nearby; bbox `[37.33, 265.2, 200.42, 306.12]`; distance=47.4pt; vgap=10.3pt; same_column=False; owner=True; reason=다른 column; raw='공조 장치용 에어필터를 주기적으로 교체하지\n않으면 먼지 등 이물질이 쌓여 풍량이 약해져\n냉난방 성능이 나빠질 수 있으며 악취가 발생할\n수 있습니다.'
  - expanded; bbox `[221.82, 63.2, 384.55, 92.85]`; distance=57.1pt; vgap=57.1pt; same_column=True; owner=True; reason=None; raw='에어컨 냉매 및 압축기 윤활유량 점\n검'
  - excluded-nearby; bbox `[37.33, 214.53, 153.67, 225.45]`; distance=121.2pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='으켜 화재가 발생할 수 있습니다.'
  - excluded-nearby; bbox `[37.32, 345.87, 200.56, 406.79]`; distance=127.8pt; vgap=91.0pt; same_column=False; owner=True; reason=다른 column; raw='에어컨/히터 사용 시 송풍구에서 나는 에어컨\n냄새는 고장이 아니며, 에어컨의 잘못된 사용\n에 따른 현상입니다. 이를 방지하기 위해서는\n여름철에 에어컨을 사용한 후에 송풍(에어컨\n버튼 OFF)으로 약 5분 동안 작동하여 에어컨\n내부를 건조하십시오.'

### p.228 / image 1

- image bbox: `[36.72, 77.04, 201.11, 181.91]`; candidate: 실외 측 유리 성에 제거 방법 · 편의 장치
- A LLM 전달 context 필드: ['실외 측 유리 성에 제거 방법', '(1) 풍량 조절 버튼을 눌러 풍량을 최대로 설정', '하십시오.\n(2) 온도 조절 노브를 돌려 최대 온도로 설정하', '편의 장치', '십시오.\n(3) 앞유리 서리 제거 버튼을 누르십시오.\n(4) 외기 유입이 자동으로 선택되며 외부 온도']
- B LLM 전달 text (141자): '편의 장치\n실외 측 유리 성에 제거 방법\n(1) 풍량 조절 버튼을 눌러 풍량을 최대로 설정\n하십시오. (2) 온도 조절 노브를 돌려 최대 온도로 설정하\n십시오. (3) 앞유리 서리 제거 버튼을 누르십시오. (4) 외기 유입이 자동으로 선택되며 외부 온도'
- A 결과: '실외 측 유리 성에 제거 방법 · 편의 장치' → '실외 측 유리 성에 제거 방법 · 편의 장치' (llm_accepted / accepted)
- B 결과: '실외 측 유리 성에 제거 방법' → '실외 측 유리 성에 제거 방법' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[37.44, 63.51, 147.02, 75.73]`; distance=1.3pt; vgap=1.3pt; same_column=True; owner=True; reason=None; raw='실외 측 유리 성에 제거 방법'
  - expanded; bbox `[36.73, 200.08, 197.65, 211.01]`; distance=18.2pt; vgap=18.2pt; same_column=True; owner=True; reason=None; raw='(1) 풍량 조절 버튼을 눌러 풍량을 최대로 설정'
  - expanded; bbox `[36.69, 210.08, 198.84, 234.01]`; distance=28.2pt; vgap=28.2pt; same_column=True; owner=True; reason=None; raw='하십시오.\n(2) 온도 조절 노브를 돌려 최대 온도로 설정하'
  - excluded-nearby; bbox `[220.98, 179.27, 384.89, 342.1]`; distance=35.8pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='• 스티커 및 선팅 필름을 뒷유리에 붙일 때 유\n리 열선이 손상되지 않도록 유의하십시오.\n칼 또는 선팅 필름을 붙일 때 사용하는 용액\n에 의해 열선이 손상될 경우 열선이 작동되\n지 않거나 전기 충격으로 뒷유리가 손상될\n수 있습니다.\n• 유리창 부근에 날카로운 물건을 놓아두면 차\n가 진동할 때 날카로운 물건에 의해 열선이\n손상될 수 있습니다.\n• 유리창을 청소할 때는 부드러운 천을 사용하\n여 닦고 열선이 손상되는 휘발성 물질은 사\n용하지 마십시오.\n• 뒷유리의 교체가 필요할 경우에는 당사 직영\n하이테크센터나 블루핸즈에서 받으십시오.'
  - excluded-nearby; bbox `[221.59, 110.56, 385.37, 141.49]`; distance=36.9pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='서리가 제거되면 반드시 작동을 멈추십시오.\n서리가 제거된 후에도 작동을 멈추지 않으면 고\n열로 인한 화재의 위험이 있습니다.'
  - excluded-nearby; bbox `[221.97, 62.89, 313.36, 80.0]`; distance=37.5pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='서리 제거 (열선)҃'
  - expanded; bbox `[37.58, 27.73, 72.63, 38.93]`; distance=38.1pt; vgap=38.1pt; same_column=True; owner=True; reason=None; raw='편의 장치'
  - expanded; bbox `[36.63, 233.08, 197.32, 270.0]`; distance=51.2pt; vgap=51.2pt; same_column=True; owner=True; reason=None; raw='십시오.\n(3) 앞유리 서리 제거 버튼을 누르십시오. \n(4) 외기 유입이 자동으로 선택되며 외부 온도'
  - excluded-nearby; bbox `[48.54, 269.07, 197.24, 289.99]`; distance=87.2pt; vgap=87.2pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='에 따라 에어컨도 자동으로 작동합니다(유\n리창 습기 방지 기능이 설정된 경우).'
  - excluded-nearby; bbox `[37.58, 309.53, 142.29, 324.19]`; distance=127.6pt; vgap=127.6pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='유리창 습기 방지 기능'
  - excluded-nearby; bbox `[36.6, 328.04, 200.57, 483.94]`; distance=146.1pt; vgap=146.1pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='유리창 습기 발생을 최소화하기 위하여  위치\n선택 등 일정 조건에 따라 외기 유입 및 에어컨\n작동이 자동으로 선택됩니다.\n이러한 유리창 습기 방지 기능을 해제하거나 다\n시 설정하고자 할 때는 다음과 같이 하십시오.\n1. 시동을 거십시오.\n2. 앞유리 서리 제거 버튼을 누르거나 바람 방\n향을 \n 위치로 선택하십시오.\n3. 내기 선택 버튼을 3초 이내에 5회 이상 누르\n십시오.\n내기 선택 버튼 내 표시등이 3회 깜빡이면 유리\n창 습기 방지 기능이 해제 또는 설정됩니다. 초\n기 배터리가 연결되면 유리창 습기 방지 기능이\n자동으로 설정됩니다.'

### p.229 / image 1

- image bbox: `[50.88, 82.08, 215.27, 186.95]`; candidate: 뒷유리 서리 제거 (열선)
- A LLM 전달 context 필드: ['시동이 걸린 상태에서 뒷유리 서리 제거 버튼을\n누르면 버튼 내 표시등이 켜지고, 해당 기능이\n작동합니다. 버튼을 한 번 더 누르면 작동이 멈\n춥니다. 기능이 작동한 후 약 20분이 지나면 자\n동으로 멈춥니다.\n또한 작동 중에 시동을 껐다가 시동을 다시 걸\n면 뒷유리 서리 제거 기능은 꺼집니다.', '뒷유리 서리 제거 (열선)']
- B LLM 전달 text (241자): '뒷유리 서리 제거 (열선)\n시동이 걸린 상태에서 뒷유리 서리 제거 버튼을 누르면 버튼 내 표시등이 켜지고, 해당 기능이 작동합니다. 버튼을 한 번 더 누르면 작동이 멈 춥니다. 기능이 작동한 후 약 20분이 지나면 자 동으로 멈춥니다. 또한 작동 중에 시동을 껐다가 시동을 다시 걸 면 뒷유리 서리 제거 기능은 꺼집니다.\n실외 미러 서리 제거(열선) 뒷유리 서리 제거 기능이 작동하면 동시에 실외 미러 서리 제거 기능도 작동합니다.'
- A 결과: '뒷유리 서리 제거(열선)' → '뒷유리 서리 제거(열선)' (llm_accepted / accepted)
- B 결과: '뒷유리 서리 제거(열선)' → '뒷유리 서리 제거(열선)' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[50.91, 188.53, 214.62, 271.0]`; distance=1.6pt; vgap=1.6pt; same_column=True; owner=True; reason=None; raw='2C_RearWindowDefrost\n시동이 걸린 상태에서 뒷유리 서리 제거 버튼을\n누르면 버튼 내 표시등이 켜지고, 해당 기능이\n작동합니다. 버튼을 한 번 더 누르면 작동이 멈\n춥니다. 기능이 작동한 후 약 20분이 지나면 자\n동으로 멈춥니다.\n또한 작동 중에 시동을 껐다가 시동을 다시 걸\n면 뒷유리 서리 제거 기능은 꺼집니다.'
  - expanded; bbox `[51.75, 63.2, 165.15, 77.86]`; distance=4.2pt; vgap=4.2pt; same_column=True; owner=True; reason=None; raw='뒷유리 서리 제거 (열선)'
  - excluded-nearby; bbox `[235.73, 127.56, 399.0, 158.48]`; distance=36.8pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='인포테인먼트 시스템은 업데이트로 변경될 수\n있습니다. 자세한 내용은 인포테인먼트 시스템\n웹 매뉴얼을 참고하십시오.'
  - excluded-nearby; bbox `[236.0, 181.86, 395.26, 196.52]`; distance=37.3pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='애프터 블로우 (에어컨 자동 건조)'
  - excluded-nearby; bbox `[236.14, 62.89, 398.39, 97.0]`; distance=37.6pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='주요 기능 및 기타 설정 (히터 \n및 에어컨)'
  - excluded-nearby; bbox `[235.54, 200.37, 399.5, 354.28]`; distance=49.9pt; vgap=13.4pt; same_column=False; owner=True; reason=다른 column; raw='시동을 끄면 30분 후에 자동으로 블로워 모터\n를 작동시켜 에어컨 내 물기를 건조하여 에어컨\n냄새를 감소시켜 줍니다.\n인포테인먼트 시스템의 설정 > 차량 > 공조 >\n에어컨 자동 건조에서 기능을 켜거나 끌 수 있습\n니다. 설정 후 작동 조건 만족 시, 시동을 끄면\n에어컨 자동 건조 작동 예정 화면을 10초 동안\n표시하여 작동 조건 만족 여부를 표시합니다.\n자동으로 블로워 모터 작동 시, 에어컨 자동 건\n조 작동 여부를 화면에 표시합니다. 에어컨 자\n동 건조 작동 예정 화면을 표시하더라도 배터리\n충전량 등 차량 상태에 따라 작동이 되지 않을\n수 있습니다. 에어컨 자동 건조 기능이 작동하\n면 에어컨은 3단 바람 세기 및 외기 순환 모드로\n작동되고 상향으로 바람이 나옵니다.'
  - expanded; bbox `[51.54, 284.84, 214.75, 318.97]`; distance=97.9pt; vgap=97.9pt; same_column=True; owner=True; reason=None; raw='실외 미러 서리 제거(열선) \n뒷유리 서리 제거 기능이 작동하면 동시에 실외\n미러 서리 제거 기능도 작동합니다.'
  - excluded-nearby; bbox `[235.78, 368.09, 399.0, 412.21]`; distance=218.1pt; vgap=181.1pt; same_column=False; owner=True; reason=다른 column; raw='작동 조건\n에어컨을 일정 시간 작동 후 시동을 끄면 배터\n리 잔량이 충분하거나 외기온이 일정 이상인 경\n우 작동합니다.'
  - excluded-nearby; bbox `[235.16, 426.07, 399.02, 512.17]`; distance=274.9pt; vgap=239.1pt; same_column=False; owner=True; reason=다른 column; raw='작동 정지\n• 에어컨 자동 건조 기능이 10분 동안 작동한\n후 정지합니다.\n• 시동 버튼을 누르거나 차량 시동이 걸려 있\n으면 에어컨 자동 건조 기능은 정지합니다.\n• 원격 공조가 작동되면 에어컨 자동 건조 기\n능은 정지합니다.'

### p.230 / image 1

- image bbox: `[36.72, 255.83, 201.11, 360.7]`; candidate: 오토 디포그 (자동 김 서림 제거 기
- A LLM 전달 context 필드: ['히터나 에어컨 작동 상태일 때, 차 앞유리창의\n습기가 감지되면 자동으로 습기를 제거하여 운\n전자의 시야를 확보함으로써 안전 운전을 가능\n하게 하는 기능입니다.', '오토 디포그 (자동 김 서림 제거 기\n능)', '에어컨 자동 건조 기능은 에어컨 냄새를 감\n소시키는 기능으로 약간의 냄새가 남을 수\n있습니다.\n에어컨 자동 건조 기능 작동 중에는 후석 감\n지 기능이 작동하지 않습니다.\n에어컨 자동 건조 기능은 초기 출고 시 기능\n이 활성화되어 있습니다. 기능을 사용하지\n않으시려면 인포테인먼트 시스템의 설정 메\n뉴에서 기능을 설정하십시오.']
- B LLM 전달 text (375자): '편의 장치\n에어컨 자동 건조 기능은 에어컨 냄새를 감 소시키는 기능으로 약간의 냄새가 남을 수 있습니다. 에어컨 자동 건조 기능 작동 중에는 후석 감 지 기능이 작동하지 않습니다. 에어컨 자동 건조 기능은 초기 출고 시 기능 이 활성화되어 있습니다. 기능을 사용하지 않으시려면 인포테인먼트 시스템의 설정 메 뉴에서 기능을 설정하십시오.\n오토 디포그 (자동 김 서림 제거 기 능)\n히터나 에어컨 작동 상태일 때, 차 앞유리창의 습기가 감지되면 자동으로 습기를 제거하여 운 전자의 시야를 확보함으로써 안전 운전을 가능 하게 하는 기능입니다.\n습기가 감지되어 자동 김 서림 제거 장치가 작 동하면 공조 정보 화면에서 자동 김 서림 제거 장치가 작동 중임을 확인할 수 있습니다.'
- A 결과: '오토 디포그(자동 김 서림 제거 기능)' → '오토 디포그 (자동 김 서림 제거 기' (fallback_candidate / new_tokens:기능)
- B 결과: '오토 디포그(자동 김 서림 제거 기능)' → '오토 디포그(자동 김 서림 제거 기능)' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[36.73, 362.42, 200.51, 463.06]`; distance=1.7pt; vgap=1.7pt; same_column=True; owner=True; reason=None; raw='2C_AutoDefogSensor\n히터나 에어컨 작동 상태일 때, 차 앞유리창의\n습기가 감지되면 자동으로 습기를 제거하여 운\n전자의 시야를 확보함으로써 안전 운전을 가능\n하게 하는 기능입니다.\nÈ'
  - expanded; bbox `[37.58, 210.84, 197.4, 240.5]`; distance=15.3pt; vgap=15.3pt; same_column=True; owner=True; reason=None; raw='오토 디포그 (자동 김 서림 제거 기\n능)'
  - excluded-nearby; bbox `[220.97, 207.66, 384.77, 340.54]`; distance=35.7pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw="히터 및 에어컨 스위치\n• 기능 설정\n1. 시동 'ON' 상태에서 앞유리 서리 제거 버\n튼을 3초 동안 누르십시오.\n2. 앞 유리 서리 제거 버튼 표시등이 6회 깜빡\n인 후 꺼집니다. \n• 기능 해제\n1. 시동 'ON' 상태에서 앞 유리 서리 제거 버\n튼을 3초 동안 누르십시오.\n2. 앞 유리 서리 제거 버튼 표시등이 3회 깜빡\n인 후 켜집니다."
  - excluded-nearby; bbox `[220.97, 349.6, 384.76, 403.52]`; distance=35.7pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw="인포테인먼트 시스템\n시동 'ON' 상태에서 인포테인먼트 시스템의 설\n정 > 차량 > 공조 > 창문 습기 방지 > 앞유리 습\n기 발생 방지에서 기능을 선택하거나 해제할 수\n있습니다."
  - expanded; bbox `[36.73, 82.61, 200.53, 187.46]`; distance=68.4pt; vgap=68.4pt; same_column=True; owner=True; reason=None; raw='• 에어컨 자동 건조 기능은 에어컨 냄새를 감\n소시키는 기능으로 약간의 냄새가 남을 수\n있습니다.\n• 에어컨 자동 건조 기능 작동 중에는 후석 감\n지 기능이 작동하지 않습니다.\n• 에어컨 자동 건조 기능은 초기 출고 시 기능\n이 활성화되어 있습니다. 기능을 사용하지\n않으시려면 인포테인먼트 시스템의 설정 메\n뉴에서 기능을 설정하십시오.'
  - excluded-nearby; bbox `[221.69, 187.46, 311.29, 199.68]`; distance=93.2pt; vgap=56.1pt; same_column=False; owner=True; reason=다른 column; raw='기능 설정 및 해제 방법'
  - excluded-nearby; bbox `[220.98, 430.47, 384.8, 520.33]`; distance=105.5pt; vgap=69.8pt; same_column=False; owner=True; reason=다른 column; raw='• 오토 디포그가 작동 중일 때 내기/외기 또는\n에어컨, 바람 방향 버튼 중 하나를 선택하면\n오토 디포그 작동이 중지됩니다. 안전한 시\n야 확보를 위해서 오토 디포그가 작동 중에\n는 조작을 삼가십시오.\n• 앞유리 상단에 있는 센서 커버를 강제로 떼\n어내지 마십시오. 관련 부품이 손상될 수 있\n습니다.'
  - expanded; bbox `[37.35, 471.95, 200.56, 502.87]`; distance=111.2pt; vgap=111.2pt; same_column=True; owner=True; reason=None; raw='습기가 감지되어 자동 김 서림 제거 장치가 작\n동하면 공조 정보 화면에서 자동 김 서림 제거\n장치가 작동 중임을 확인할 수 있습니다.'
  - excluded-nearby; bbox `[220.74, 63.73, 385.31, 173.64]`; distance=117.5pt; vgap=82.2pt; same_column=False; owner=True; reason=다른 column; raw='차 앞유리의 습도가 높아질수록 자동 김 서림\n제거 기능은 단계별로 작동합니다. 예를 들어,\n1단계의 에어컨 작동 및 외기 유입 모드 전환만\n으로 습도 조절이 되지 않을 경우 2-3 단계에서\n송풍으로 작동하고 송풍량을 늘려 습도를 조절\n합니다.\n1단계 - 에어컨 작동, 외기 유입 모드 전환(외부\n온도가 낮을 경우)\n2단계 - 앞유리 송풍\n3단계 - 앞유리 송풍량 늘림'
  - expanded; bbox `[37.58, 27.73, 72.63, 38.93]`; distance=216.9pt; vgap=216.9pt; same_column=True; owner=True; reason=None; raw='편의 장치'

### p.261 / image 1

- image bbox: `[50.88, 66.96, 399.58, 344.63]`; candidate: [B] 변속 레버 버튼
- A LLM 전달 context 필드: ['[A] 변속 레버\n[B] 변속 레버 버튼']
- B LLM 전달 text (22자): '[A] 변속 레버 [B] 변속 레버 버튼'
- A 결과: '[B] 변속 레버 버튼' → '[B] 변속 레버 버튼' (llm_accepted / accepted)
- B 결과: '변속 레버 버튼' → '변속 레버 버튼' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[50.91, 344.33, 110.27, 373.74]`; distance=0.0pt; vgap=0.0pt; same_column=True; owner=True; reason=None; raw='1C_ShiftleverOverview\n[A] 변속 레버\n[B] 변속 레버 버튼'
  - excluded-nearby; bbox `[51.42, 374.88, 332.19, 425.38]`; distance=30.3pt; vgap=30.3pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='브레이크 페달을 밟고 변속 레버 버튼을 눌러야 변속 가능\n변속 레버 버튼을 눌러야 변속 가능\n변속 레버 버튼 조작 없이 변속 가능\n변속할 때는 반드시 브레이크 페달을 밟은 상태에서 변속 레버를 조작하십시오.҃'
  - excluded-nearby; bbox `[51.54, 453.73, 399.0, 474.65]`; distance=109.1pt; vgap=109.1pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='변속할 때는 클러스터의 변속 단 표시 또는 변속 레버의 변속 단 표시등이 원하는 변속 단으로 표시\n됐는지 반드시 확인하십시오.'

### p.263 / image 1

- image bbox: `[50.88, 77.04, 215.27, 181.91]`; candidate: 수동 변속(+, -) 모드
- A LLM 전달 context 필드: ['[A] + (UP)\n[B] - (DOWN)\n+ (UP)\n수동 변속기처럼 변속 레버를 + 방향으로 한\n번 밀어줄 때마다 1속씩 상승하여 6속까지\n변속할 수 있습니다. 가속 페달을 밟으면서\n작동시킬 수 있습니다.\n(DOWN)\n브레이크 페달을 밟으면 속도에 따라 6속-1\n속까지 자동으로 변속합니다. 또한 레버를 –\n방향으로 한 번 밀어줄 때마다 1속씩 내려갑\n니다. 엔진 브레이크를 사용하려면 브레이크\n페달을 밟으면서 변속 레버를 – 방향으로 밀\n어 1속씩 내리십시오.҃', '수동 변속(+, -) 모드']
- B LLM 전달 text (338자): '수동 변속(+, -) 모드\n[A] + (UP) [B] - (DOWN) + (UP) 수동 변속기처럼 변속 레버를 + 방향으로 한 번 밀어줄 때마다 1속씩 상승하여 6속까지 변속할 수 있습니다. 가속 페달을 밟으면서 작동시킬 수 있습니다. (DOWN) 브레이크 페달을 밟으면 속도에 따라 6속-1 속까지 자동으로 변속합니다. 또한 레버를 – 방향으로 한 번 밀어줄 때마다 1속씩 내려갑 니다. 엔진 브레이크를 사용하려면 브레이크 페달을 밟으면서 변속 레버를 – 방향으로 밀 어 1속씩 내리십시오.҃\n주행 중 잠시 정차할 경우, 브레이크 페달을 확 실히 밟으십시오. 그렇지 않으면 차량이 움직 일 수 있습니다.'
- A 결과: '수동 변속(+, -) 모드' → '수동 변속(+, -) 모드' (llm_accepted / accepted)
- B 결과: '수동 변속(+, -) 모드' → '수동 변속(+, -) 모드' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[50.91, 183.53, 215.41, 348.54]`; distance=1.6pt; vgap=1.6pt; same_column=True; owner=True; reason=None; raw='2C_ShiftButtonOverview_2\n[A] + (UP)\n[B] - (DOWN)\n• + (UP)\n수동 변속기처럼 변속 레버를 + 방향으로 한\n번 밀어줄 때마다 1속씩 상승하여 6속까지\n변속할 수 있습니다. 가속 페달을 밟으면서\n작동시킬 수 있습니다.\n• - (DOWN)\n브레이크 페달을 밟으면 속도에 따라 6속-1\n속까지 자동으로 변속합니다. 또한 레버를 –\n방향으로 한 번 밀어줄 때마다 1속씩 내려갑\n니다. 엔진 브레이크를 사용하려면 브레이크\n페달을 밟으면서 변속 레버를 – 방향으로 밀\n어 1속씩 내리십시오.҃'
  - expanded; bbox `[50.89, 63.72, 125.16, 74.64]`; distance=2.4pt; vgap=2.4pt; same_column=True; owner=True; reason=None; raw='수동 변속(+, -) 모드'
  - excluded-nearby; bbox `[235.16, 63.53, 399.0, 96.63]`; distance=35.8pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='• 엔진의 과도한 회전을 방지하기 위해 차량\n속도에 따라 변속 레버를 - 방향으로 밀어도\n변속되지 않을 수 있습니다.'
  - excluded-nearby; bbox `[235.16, 123.59, 399.48, 233.44]`; distance=35.8pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='• 수동 변속 모드에서는 가속 페달을 밟으면\n속도에 따라 자동으로 1-6속(또는 8속)까지\n올라가게 되나, ‘D’(주행)에서 주행할 때 보\n다 높은 엔진 회전수(RPM)에서 변속되므로,\n클러스터의 엔진 회전계를 보며 변속하십시\n오. 그렇지 않으면 변속기에 손상을 줄 수 있\n습니다. \n• 수동 변속 모드로 주행 중 고단으로 변속할\n경우, 도로 조건에 맞추어 엔진 회전수\n(RPM)가 회전계의 빨간색 범위에 들어가지'
  - excluded-nearby; bbox `[235.16, 232.51, 399.04, 278.42]`; distance=86.4pt; vgap=50.6pt; same_column=False; owner=True; reason=다른 column; raw='않도록 주의하여 변속하십시오. \n• 급격한 엔진 브레이크 및 급가속은 고장의\n원인이 됩니다. 도로 상태 및 주행 속도에 따\n라 적절한 변속을 하십시오.'
  - excluded-nearby; bbox `[235.16, 297.11, 297.89, 309.33]`; distance=151.0pt; vgap=115.2pt; same_column=False; owner=True; reason=다른 column; raw='N(중립) 단 주차'
  - excluded-nearby; bbox `[234.99, 310.31, 399.49, 410.22]`; distance=163.9pt; vgap=128.4pt; same_column=False; owner=True; reason=다른 column; raw="주차 후에도 외부에서 차량을 밀어 움직일 수\n있게 N단 주차하려면 다음과 같이 하십시오.\n1. 시동 'ON' 또는 시동이 걸린 상태에서 브레\n이크 페달을 밟고 'P'(주차)로 변속하십시오.\n2. 브레이크 페달을 밟은 상태에서 전자식 파킹\n브레이크 스위치를 눌러 파킹 브레이크를 수\n동으로 해제한 후 시동을 끄십시오.\n3. 자동 정차(Auto Hold) 기능이 작동 중이면\nAUTO HOLD 버튼을 눌러 끄고 시동을 끄십"
  - expanded; bbox `[51.47, 376.87, 214.68, 407.8]`; distance=195.0pt; vgap=195.0pt; same_column=True; owner=True; reason=None; raw='주행 중 잠시 정차할 경우, 브레이크 페달을 확\n실히 밟으십시오. 그렇지 않으면 차량이 움직\n일 수 있습니다.'
  - excluded-nearby; bbox `[234.96, 409.29, 398.93, 483.74]`; distance=262.8pt; vgap=227.4pt; same_column=False; owner=True; reason=다른 column; raw="시오.\n4. 브레이크 페달을 밟은 상태에서 변속 레버를\nN 위치로 이동하십시오. \n• 변속 단이 'N'(중립)으로 변속됩니다.\n• 시동을 끈 후 3분 이내에만 'N'(중립)과\n'P'(주차) 간 변속이 가능합니다.҃"

### p.267 / image 1

- image bbox: `[50.88, 77.04, 215.27, 181.91]`; candidate: R (Reverse): 후진
- A LLM 전달 context 필드: ["차를 후진할 때 사용합니다.\n브레이크 페달을 밟은 상태에서 R 위치로 돌\n리십시오.\n차량이 'R'(후진) 상태에서 정차해 있을 때 안\n전벨트를 풀고 운전석 도어를 열면 자동으로\n'P'(주차)로 변속됩니다. 차량이 움직이고 있", 'R (Reverse): 후진']
- B LLM 전달 text (256자): "R (Reverse): 후진\n차를 후진할 때 사용합니다. 브레이크 페달을 밟은 상태에서 R 위치로 돌 리십시오. 차량이 'R'(후진) 상태에서 정차해 있을 때 안 전벨트를 풀고 운전석 도어를 열면 자동으로 'P'(주차)로 변속됩니다. 차량이 움직이고 있\n는 경우 더블 클러치 변속기 보호를 위해 'P'( 주차)로 변속되지 않을 수 있습니다. 변속 다이얼의 회전 방향은 바퀴의 회전 방 향과 동일합니다҃\n반드시 차를 정지시킨 후 'R'(후진)로 변속하십 시오."
- A 결과: 'R(Reverse): 후진' → 'R(Reverse): 후진' (llm_accepted / accepted)
- B 결과: 'R(Reverse) 후진' → 'R(Reverse) 후진' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[50.91, 183.53, 214.68, 264.99]`; distance=1.6pt; vgap=1.6pt; same_column=True; owner=True; reason=None; raw="2C_ShiftButtonRPosition\n• 차를 후진할 때 사용합니다.\n• 브레이크 페달을 밟은 상태에서 R 위치로 돌\n리십시오.\n• 차량이 'R'(후진) 상태에서 정차해 있을 때 안\n전벨트를 풀고 운전석 도어를 열면 자동으로\n'P'(주차)로 변속됩니다. 차량이 움직이고 있"
  - expanded; bbox `[50.26, 63.72, 118.99, 74.64]`; distance=2.4pt; vgap=2.4pt; same_column=True; owner=True; reason=None; raw='R (Reverse): 후진'
  - excluded-nearby; bbox `[234.51, 63.72, 301.55, 74.64]`; distance=37.0pt; vgap=2.4pt; same_column=False; owner=False; reason=다른 column; raw='N (Neutral): 중립'
  - excluded-nearby; bbox `[235.16, 183.53, 399.04, 228.0]`; distance=37.4pt; vgap=1.6pt; same_column=False; owner=False; reason=다른 column; raw='2C_ShiftButtonNPosition\n• 브레이크 페달을 밟은 상태에서 변속 다이얼\n을 N 위치로 돌리십시오.\n- 현재 단이 ‘D’(주행)일 경우 변속 다이얼을'
  - expanded; bbox `[50.91, 264.06, 215.29, 310.54]`; distance=82.1pt; vgap=82.1pt; same_column=True; owner=True; reason=None; raw="는 경우 더블 클러치 변속기 보호를 위해 'P'(\n주차)로 변속되지 않을 수 있습니다.\n• 변속 다이얼의 회전 방향은 바퀴의 회전 방\n향과 동일합니다҃"
  - excluded-nearby; bbox `[243.54, 227.07, 398.99, 270.99]`; distance=96.0pt; vgap=45.2pt; same_column=False; owner=False; reason=다른 column; raw='아래로 살짝 돌리면 ‘N’(중립)으로 변속됩\n니다. (위로 돌릴 경우 ‘N’(중립)으로 변속\n되지 않음)\n- 현재 단이 ‘R’(후진)일 경우 변속 다이얼을'
  - excluded-nearby; bbox `[235.16, 270.07, 399.0, 380.94]`; distance=124.0pt; vgap=88.2pt; same_column=False; owner=False; reason=다른 column; raw="위로 살짝 돌리면 ‘N’(중립)으로 변속됩니\n다. (아래로 돌릴 경우 ‘N’(중립)으로 변속\n되지 않음)\n• 'N'(중립) 상태에서 시동을 끄면 자동으로\n'P'(주차)로 변속됩니다.\n• N단 유지 모드: 변속 단이 'N'(중립)인 상태\n에서 시동을 꺼도 'N'(중립) 상태가 유지되며\n시동 ACC 상태가 됩니다. 시동 ACC 상태에\n서 3분 이내로 운전석 도어를 열면 자동으로\n'P'(주차)로 변속되고 시동이 꺼집니다."
  - expanded; bbox `[51.51, 338.89, 214.6, 359.81]`; distance=157.0pt; vgap=157.0pt; same_column=True; owner=True; reason=None; raw="반드시 차를 정지시킨 후 'R'(후진)로 변속하십\n시오."
  - excluded-nearby; bbox `[235.72, 409.85, 398.96, 450.78]`; distance=264.7pt; vgap=227.9pt; same_column=False; owner=False; reason=다른 column; raw='이중 주차 또는 자동 세차기 사용 목적으로 시\n동을 끈 상태에서 ‘N’(중립)을 유지하고 싶은\n경우 ‘N(중립) 단 주차’ 또는 ‘N단 유지 모드’를\n참고하십시오'

### p.271 / image 1

- image bbox: `[50.88, 87.84, 215.27, 192.71]`; candidate: 변속기 냉각 중 안전한 곳에 00분 간 정차하십
- A LLM 전달 context 필드: ["안전한 곳으로 차량을 이동한 후 기어를 'P'(주\n차)로 변속하여 시동이 걸린 상태로 정차하면\n해당 경고문이 클러스터 표시창에 표시됩니다.\n변속기가 충분히 냉각될 때까지 기다리십시\n오.", '변속기 냉각 중 안전한 곳에 00분 간 정차하십\n시오']
- B LLM 전달 text (133자): "변속기 냉각 중 안전한 곳에 00분 간 정차하십 시오\n안전한 곳으로 차량을 이동한 후 기어를 'P'(주 차)로 변속하여 시동이 걸린 상태로 정차하면 해당 경고문이 클러스터 표시창에 표시됩니다. 변속기가 충분히 냉각될 때까지 기다리십시 오."
- A 결과: '변속기 냉각 중 안전한 곳에 00분간 정차하십시오.' → '변속기 냉각 중 안전한 곳에 00분 간 정차하십' (fallback_candidate / new_tokens:분간,정차하십시오)
- B 결과: '변속기 냉각 중 정차 경고' → '변속기 냉각 중 정차 경고' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[50.91, 193.53, 215.21, 257.99]`; distance=0.8pt; vgap=0.8pt; same_column=True; owner=True; reason=None; raw="2C_DCTWarningMessageInCluster_3\n안전한 곳으로 차량을 이동한 후 기어를 'P'(주\n차)로 변속하여 시동이 걸린 상태로 정차하면\n해당 경고문이 클러스터 표시창에 표시됩니다.\n• 변속기가 충분히 냉각될 때까지 기다리십시\n오."
  - expanded; bbox `[50.89, 63.72, 216.91, 84.64]`; distance=3.2pt; vgap=3.2pt; same_column=True; owner=True; reason=None; raw='변속기 냉각 중 안전한 곳에 00분 간 정차하십\n시오'
  - excluded-nearby; bbox `[235.16, 183.53, 399.01, 236.0]`; distance=35.8pt; vgap=0.0pt; same_column=False; owner=False; reason=다른 column; raw='2C_PressureBreakPadalToChangeGearInfo\n브레이크 페달을 밟지 않은 상태에서 변속하려\n하면 해당 경고문이 클러스터 표시창에 표시됩\n니다.\n브레이크 페달을 밟고 변속하십시오.'
  - excluded-nearby; bbox `[235.86, 63.51, 395.24, 75.73]`; distance=49.2pt; vgap=12.1pt; same_column=False; owner=False; reason=다른 column; raw='브레이크를 밟은 상태에서 변속하십시오'
  - excluded-nearby; bbox `[50.89, 267.05, 175.36, 277.98]`; distance=74.3pt; vgap=74.3pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='변속기 냉각 완료 주행 가능합니다'
  - excluded-nearby; bbox `[235.86, 249.86, 365.06, 262.08]`; distance=94.2pt; vgap=57.1pt; same_column=False; owner=False; reason=다른 column; raw='정차 후에 P단으로 이동하십시오'
  - excluded-nearby; bbox `[50.91, 387.11, 214.67, 416.59]`; distance=194.4pt; vgap=194.4pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='2C_ShiftOverheatCanDriveInfo\n해당 경고문이 클러스터 표시창에 표시되면 정\n상적으로 주행할 수 있습니다.'
  - excluded-nearby; bbox `[235.16, 369.88, 398.96, 432.35]`; distance=213.0pt; vgap=177.2pt; same_column=False; owner=False; reason=다른 column; raw="2C_ShiftToPAfterStoppingInfo\n기어를 'P'(주차)로 변속할 때 차량 속도가 높으\n면 해당 경고문이 클러스터 표시창에 표시됩니\n다.\n차량을 정차한 후에 ‘P’(주차)단으로 변속하십\n시오."

### p.304 / image 1

- image bbox: `[36.72, 218.15, 201.11, 323.03]`; candidate: 전방 충돌방지 보조 (FCA) (전 · 기본 기능
- A LLM 전달 context 필드: ['전방의 차량, 이륜차, 보행자 및 자전거 탑승자\n를 인식하여 전방 충돌 위험이 판단되면 경고문\n과 경고음 등으로 운전자에게 알려주고, 충돌\n경감 또는 회피하도록 제동을 도와줍니다.', '기본 기능', '전방 충돌방지 보조 (FCA) (전\n방 카메라 단독)', 'FCA는\nForward\nCollision-Avoidance\nAssist의 약자입니다.']
- B LLM 전달 text (191자): '운전자 보조\n전방 충돌방지 보조 (FCA) (전 방 카메라 단독)\n기본 기능\n전방의 차량, 이륜차, 보행자 및 자전거 탑승자 를 인식하여 전방 충돌 위험이 판단되면 경고문 과 경고음 등으로 운전자에게 알려주고, 충돌 경감 또는 회피하도록 제동을 도와줍니다.\nFCA는 Forward Collision-Avoidance Assist의 약자입니다.'
- A 결과: '전방 충돌방지 보조(FCA) 기본 기능' → '전방 충돌방지 보조(FCA) 기본 기능' (llm_accepted / accepted)
- B 결과: '전방 충돌방지 보조(FCA) 기본 기능' → '전방 충돌방지 보조(FCA) 기본 기능' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[36.73, 324.74, 200.54, 374.22]`; distance=1.7pt; vgap=1.7pt; same_column=True; owner=True; reason=None; raw='2C_FCABasicFunction_Frontcamera\n전방의 차량, 이륜차, 보행자 및 자전거 탑승자\n를 인식하여 전방 충돌 위험이 판단되면 경고문\n과 경고음 등으로 운전자에게 알려주고, 충돌\n경감 또는 회피하도록 제동을 도와줍니다.'
  - expanded; bbox `[37.36, 205.01, 71.59, 215.62]`; distance=2.5pt; vgap=2.5pt; same_column=True; owner=True; reason=None; raw='기본 기능'
  - expanded; bbox `[37.72, 151.87, 200.17, 187.97]`; distance=30.2pt; vgap=30.2pt; same_column=True; owner=True; reason=None; raw='전방 충돌방지 보조 (FCA) (전\n방 카메라 단독)'
  - excluded-nearby; bbox `[220.98, 242.97, 384.88, 467.77]`; distance=35.8pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='• 인식 센서 및 주변부를 임의로 분리하거나\n충격을 가하지 마십시오.\n• 인식 센서를 교체하거나 분리했다가 다시 장\n착할 때는 당사 직영 하이테크센터나 블루핸\n즈에서 전방 충돌방지 보조 점검을 받으십시\n오.\n• 전방 카메라 렌즈 앞유리에 액세서리, 선팅\n필름 및 스티커 등을 붙이지 마십시오.\n• 전방 카메라에 수분이 유입되지 않도록 주의\n하십시오.\n• 빛이 반사되는 물질(흰색 종이나 거울 등)을\n크래시 패드 위에 놓지 마십시오. \n• 앞유리 가까이 물건을 놓거나 구조물 등을\n장착하지 마십시오. 공조 장치 작동 시 습기\n및 성에 제거 성능이 떨어져 운전자 보조 시\n스템이 작동하지 않을 수 있습니다.\n• 트레일러, 캐리어 또는 기타 장비를 거치한\n경우 전방 충돌방지 보조 작동이 제한될 수\n있습니다.'
  - excluded-nearby; bbox `[221.62, 205.08, 380.56, 216.01]`; distance=39.1pt; vgap=2.1pt; same_column=False; owner=False; reason=다른 column; raw='인식 센서의 위치는 위 그림을 참고하십시오.'
  - excluded-nearby; bbox `[220.98, 183.53, 278.83, 201.94]`; distance=52.0pt; vgap=16.2pt; same_column=False; owner=False; reason=다른 column; raw='2C_FrontViewCamera\n(1) 전방 카메라'
  - expanded; bbox `[36.73, 401.16, 201.12, 424.05]`; distance=78.1pt; vgap=78.1pt; same_column=True; owner=True; reason=None; raw='FCA는 \nForward \nCollision-Avoidance\nAssist의 약자입니다.'
  - excluded-nearby; bbox `[37.31, 83.71, 200.52, 124.63]`; distance=93.5pt; vgap=93.5pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='인포테인먼트 소프트웨어 업데이트로 인해 운\n전자 보조 시스템의 각 기능의 설명이 취급설명\n서와 다를 수 있습니다. 이 경우 인포테인먼트\n시스템 웹 매뉴얼을 참고하십시오.'
  - excluded-nearby; bbox `[37.72, 62.89, 160.86, 80.0]`; distance=138.2pt; vgap=138.2pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='운전자 보조 알아두기'
  - expanded; bbox `[37.58, 27.73, 80.79, 38.93]`; distance=179.2pt; vgap=179.2pt; same_column=True; owner=True; reason=None; raw='운전자 보조'
  - excluded-nearby; bbox `[221.69, 63.51, 262.43, 75.73]`; distance=179.5pt; vgap=142.4pt; same_column=False; owner=False; reason=다른 column; raw='인식 센서'

### p.308 / image 1

- image bbox: `[220.79, 121.91, 385.42, 227.03]`; candidate: 전방 충돌방지 보조 이상 및 제한 사 · 기능 이상
- A LLM 전달 context 필드: ['전방 충돌방지 보조에 이상이 있으면 클러스터\n등에 경고문이 표시되고 통합 경고등( ), 전방\n안전 경고등(\n)이 켜집니다. 당사 직영 하이테\n크센터나 블루핸즈에서 점검을 받으십시오.\n경고 내용은 클러스터의 뷰 모드 중 유틸리\n티 정보 뷰의 서비스 메시지에서 확인할 수\n있습니다.', '기능 이상', '전방 충돌방지 보조 이상 및 제한 사']
- B LLM 전달 text (182자): '전방 충돌방지 보조 이상 및 제한 사\n기능 이상\n전방 충돌방지 보조에 이상이 있으면 클러스터 등에 경고문이 표시되고 통합 경고등( ), 전방 안전 경고등( )이 켜집니다. 당사 직영 하이테 크센터나 블루핸즈에서 점검을 받으십시오. 경고 내용은 클러스터의 뷰 모드 중 유틸리 티 정보 뷰의 서비스 메시지에서 확인할 수 있습니다.'
- A 결과: '전방 충돌방지 보조 이상 및 제한 사항' → '전방 충돌방지 보조 이상 및 제한 사 · 기능 이상' (fallback_candidate / new_tokens:사항)
- B 결과: '전방 충돌방지 보조 기능 이상' → '전방 충돌방지 보조 기능 이상' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[221.69, 108.49, 259.63, 120.71]`; distance=1.2pt; vgap=1.2pt; same_column=True; owner=True; reason=None; raw='기능 이상'
  - expanded; bbox `[220.98, 228.76, 384.86, 313.22]`; distance=1.7pt; vgap=1.7pt; same_column=True; owner=True; reason=None; raw='2C_ForwardSafetyMalfunctionInfo\n전방 충돌방지 보조에 이상이 있으면 클러스터\n등에 경고문이 표시되고 통합 경고등( ), 전방\n안전 경고등(\n)이 켜집니다. 당사 직영 하이테\n크센터나 블루핸즈에서 점검을 받으십시오.\n• 경고 내용은 클러스터의 뷰 모드 중 유틸리\n티 정보 뷰의 서비스 메시지에서 확인할 수\n있습니다.'
  - expanded; bbox `[221.83, 63.2, 384.57, 92.85]`; distance=29.1pt; vgap=29.1pt; same_column=True; owner=True; reason=None; raw='전방 충돌방지 보조 이상 및 제한 사\n항'
  - excluded-nearby; bbox `[36.73, 63.53, 200.48, 218.97]`; distance=36.6pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='• 다른 시스템의 경고문이 표시되거나 경고음\n이 울리는 동안에는 전방 충돌방지 보조의\n경고문이 표시되지 않거나 경고음이 울리지\n않을 수 있습니다. \n• 차량 내부 및 외부 소리로 인해 전방 충돌방\n지 보조의 경고음이 들리지 않을 수 있습니\n다. 차량 내부 음량을 적절하게 조절하고 항\n상 주의를 기울이십시오.\n• 전방 충돌방지 보조에 이상이 있어도 브레이\n크 페달 조작에 의한 제동 기능은 정상적으\n로 작동합니다.\n• 긴급 제동 중 가속 페달을 과하게 밟거나 스\n티어링 휠을 급격하게 조작하면 제동 제어가\n해제됩니다.'
  - excluded-nearby; bbox `[36.73, 252.56, 200.55, 387.4]`; distance=62.0pt; vgap=25.5pt; same_column=False; owner=False; reason=다른 column; raw='• 전방의 차량, 이륜차, 보행자 및 자전거 탑승\n자의 상태 및 주변 환경에 따라 기능이 작동\n할 수 있는 속도의 범위 또는 인식 가능 거리\n가 줄어들어 기능 작동이 제한되거나 작동하\n지 않을 수 있습니다.\n• 전방 충돌방지 보조는 상대 차량 및 이륜차\n의 상태, 주행 방향, 속도 및 주변 환경에 따\n라 위험도를 판단하여 특정 조건에서만 작동\n합니다.\n• 주행 속도가 너무 높거나 상대 차량 및 이륜\n차와의 속도 차이가 큰 경우에는 기능 작동\n이 제한되거나 작동하지 않을 수 있습니다.'
  - excluded-nearby; bbox `[221.69, 327.07, 279.85, 339.29]`; distance=100.0pt; vgap=100.0pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='인식 센서 가림'
  - excluded-nearby; bbox `[220.98, 447.1, 384.72, 559.57]`; distance=220.1pt; vgap=220.1pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='2C_LKADisableInfo\n전방 카메라의 렌즈 앞유리 또는 센서에 눈, 비\n등 이물질이 묻거나 안개, 폭우 등의 기상 상황\n으로 인식 성능이 저하되어 전방 충돌방지 보조\n가 일시적으로 제한되거나 작동하지 않을 수 있\n습니다.\n이때 클러스터 등에 경고문이 표시되고 통합 경\n고등( ), 전방 안전 경고등(\n)이 켜지지만, 전\n방 충돌방지 보조 고장이 아닙니다. 이물질을\n제거하면 전방 충돌방지 보조는 다시 정상적으\n로 작동합니다. 항상 깨끗하게 유지하십시오.'
  - excluded-nearby; bbox `[36.73, 421.19, 200.55, 491.06]`; distance=230.6pt; vgap=194.2pt; same_column=False; owner=False; reason=다른 column; raw='• 충돌 위험 상황에서 운전자가 브레이크 페달\n을 밟았음에도 제동력이 부족하다고 판단될\n경우, 전방 충돌방지 보조가 추가적인 제동\n을 발생시킬 수 있습니다.\n• 클러스터 사양 및 테마 설정에 따라 표시되\n는 이미지나 색상이 다를 수 있습니다.'

### p.325 / image 1

- image bbox: `[50.88, 208.07, 215.27, 434.86]`; candidate: [B] 차로변경 차량 및 이륜차
- A LLM 전달 context 필드: ['[A] 자차\n[B] 차로변경 차량 및 이륜차', '오르막길이나 내리막길에서는 전방에 있는\n차량, 이륜차, 보행자 및 자전거 탑승자를 인\n식하지 못하여 경고, 제동을 도와주지 않을\n수 있습니다.\n또한 선행 차량, 이륜차, 보행자 및 자전거 탑\n승자를 갑자기 인식하여 속도가 빠르게 감속\n할 수 있습니다.\n오르막길이나 내리막길에서는 전방 도로 상\n황 및 주행 상태를 확인하고 주의하여 운전\n하십시오. 필요하면 브레이크 페달을 밟아\n직접 속도를 조절하거나 스티어링 휠을 조작\n하십시오.\n차로변경 시', '옆 차로의 차량 및 이륜차[B]가 자차[A]와 같\n은 차로로 차로를 변경할 때 센서의 감지 범\n위 안으로 들어올 때까지 차량 및 이륜차[B]\n를 인식하지 못할 수 있습니다. 갑자기 끼어\n드는 차량 및 이륜차는 센서가 늦게 인식할\n수 있습니다. 항상 전방 도로 상황 및 주행 상\n태를 확인하고 주의하여 운전하십시오. 필요\n하면 브레이크 페달을 밟아 직접 속도를 조\n절하거나 스티어링 휠을 조작하십시오.']
- B LLM 전달 text (496자): '오르막길이나 내리막길에서는 전방에 있는 차량, 이륜차, 보행자 및 자전거 탑승자를 인 식하지 못하여 경고, 제동을 도와주지 않을 수 있습니다. 또한 선행 차량, 이륜차, 보행자 및 자전거 탑 승자를 갑자기 인식하여 속도가 빠르게 감속 할 수 있습니다. 오르막길이나 내리막길에서는 전방 도로 상 황 및 주행 상태를 확인하고 주의하여 운전 하십시오. 필요하면 브레이크 페달을 밟아 직접 속도를 조절하거나 스티어링 휠을 조작 하십시오. 차로변경 시\n[A] 자차 [B] 차로변경 차량 및 이륜차\n옆 차로의 차량 및 이륜차[B]가 자차[A]와 같 은 차로로 차로를 변경할 때 센서의 감지 범 위 안으로 들어올 때까지 차량 및 이륜차[B] 를 인식하지 못할 수 있습니다. 갑자기 끼어 드는 차량 및 이륜차는 센서가 늦게 인식할 수 있습니다. 항상 전방 도로 상황 및 주행 상 태를 확인하고 주의하여 운전하십시오. 필요 하면 브레이크 페달을 밟아 직접 속도를 조 절하거나 스티어링 휠을 조작하십시오.'
- A 결과: '[B] 차로변경 차량 및 이륜차' → '[B] 차로변경 차량 및 이륜차' (llm_accepted / accepted)
- B 결과: '차로변경 차량 및 이륜차' → '차로변경 차량 및 이륜차' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[50.91, 436.39, 139.75, 465.8]`; distance=1.5pt; vgap=1.5pt; same_column=True; owner=True; reason=None; raw='2C_FCAChangingLane\n[A] 자차\n[B] 차로변경 차량 및 이륜차'
  - expanded; bbox `[50.91, 63.72, 214.73, 205.44]`; distance=2.6pt; vgap=2.6pt; same_column=True; owner=True; reason=None; raw='오르막길이나 내리막길에서는 전방에 있는\n차량, 이륜차, 보행자 및 자전거 탑승자를 인\n식하지 못하여 경고, 제동을 도와주지 않을\n수 있습니다. \n또한 선행 차량, 이륜차, 보행자 및 자전거 탑\n승자를 갑자기 인식하여 속도가 빠르게 감속\n할 수 있습니다.\n오르막길이나 내리막길에서는 전방 도로 상\n황 및 주행 상태를 확인하고 주의하여 운전\n하십시오. 필요하면 브레이크 페달을 밟아\n직접 속도를 조절하거나 스티어링 휠을 조작\n하십시오. \n• 차로변경 시'
  - expanded; bbox `[59.83, 466.93, 215.25, 557.85]`; distance=32.1pt; vgap=32.1pt; same_column=True; owner=True; reason=None; raw='옆 차로의 차량 및 이륜차[B]가 자차[A]와 같\n은 차로로 차로를 변경할 때 센서의 감지 범\n위 안으로 들어올 때까지 차량 및 이륜차[B]\n를 인식하지 못할 수 있습니다. 갑자기 끼어\n드는 차량 및 이륜차는 센서가 늦게 인식할\n수 있습니다. 항상 전방 도로 상황 및 주행 상\n태를 확인하고 주의하여 운전하십시오. 필요\n하면 브레이크 페달을 밟아 직접 속도를 조\n절하거나 스티어링 휠을 조작하십시오.'
  - excluded-nearby; bbox `[235.16, 293.46, 326.18, 333.85]`; distance=35.8pt; vgap=0.0pt; same_column=False; owner=False; reason=다른 column; raw='2C_FCAChangingLane_2\n[A] 자차\n[B] 차로변경 차량\n[C] 같은 차로 차량 및 이륜차'
  - excluded-nearby; bbox `[243.59, 335.0, 398.98, 365.92]`; distance=51.0pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='바로 앞에 있는 차량[B]이 옆 차로로 빠져 나\n갔을 때 같은 차로에 있는 앞 차량 및 이륜차\n[C]를 인지하지 못하여 충돌 위험이 있을 수'
  - excluded-nearby; bbox `[244.16, 364.99, 398.96, 405.92]`; distance=52.0pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='있습니다.항상 전방 도로 상황 및 주행 상태\n를 확인하고 주의하여 운전하십시오. 필요하\n면 브레이크 페달을 밟아 직접 속도를 조절\n하거나 스티어링 휠을 조작하십시오.'

### p.328 / image 1

- image bbox: `[36.72, 107.04, 201.11, 211.91]`; candidate: 기능 켜기 및 끄기
- A LLM 전달 context 필드: ['시동 ‘ON’ 상태에서 차로 주행 보조 버튼(\n을 길게 눌러 차로 이탈 방지를 끄고 켤 수 있습\n니다. 차로 이탈방지 보조가 켜지면 클러스터\n표시창의 (\n) 표시등이 회색 또는 초록색으로\n켜집니다.\n차로 이탈방지 보조가 꺼지면 클러스터 표시창\n의 (\n) 표시등이 황색으로 켜집니다.', '기능 켜기 및 끄기', '차로 이탈방지 보조 작동', '운전자 보조']
- B LLM 전달 text (189자): '운전자 보조\n차로 이탈방지 보조 작동\n기능 켜기 및 끄기\n시동 ‘ON’ 상태에서 차로 주행 보조 버튼( 을 길게 눌러 차로 이탈 방지를 끄고 켤 수 있습 니다. 차로 이탈방지 보조가 켜지면 클러스터 표시창의 ( ) 표시등이 회색 또는 초록색으로 켜집니다. 차로 이탈방지 보조가 꺼지면 클러스터 표시창 의 ( ) 표시등이 황색으로 켜집니다.'
- A 결과: '기능 켜기 및 끄기' → '기능 켜기 및 끄기' (llm_accepted / accepted)
- B 결과: '차로 이탈방지 보조 기능 켜기 및 끄기' → '차로 이탈방지 보조 기능 켜기 및 끄기' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[37.44, 93.5, 106.82, 105.72]`; distance=1.3pt; vgap=1.3pt; same_column=True; owner=True; reason=None; raw='기능 켜기 및 끄기'
  - expanded; bbox `[36.73, 213.52, 201.13, 296.0]`; distance=1.6pt; vgap=1.6pt; same_column=True; owner=True; reason=None; raw='2C_LKAButton\n시동 ‘ON’ 상태에서 차로 주행 보조 버튼(\n)\n을 길게 눌러 차로 이탈 방지를 끄고 켤 수 있습\n니다. 차로 이탈방지 보조가 켜지면 클러스터\n표시창의 (\n) 표시등이 회색 또는 초록색으로\n켜집니다.\n차로 이탈방지 보조가 꺼지면 클러스터 표시창\n의 (\n) 표시등이 황색으로 켜집니다.'
  - expanded; bbox `[37.58, 63.2, 153.09, 77.86]`; distance=29.2pt; vgap=29.2pt; same_column=True; owner=True; reason=None; raw='차로 이탈방지 보조 작동'
  - excluded-nearby; bbox `[220.97, 136.69, 274.32, 147.61]`; distance=35.7pt; vgap=0.0pt; same_column=False; owner=False; reason=다른 column; raw='차로이탈 경고'
  - excluded-nearby; bbox `[220.98, 63.51, 384.86, 127.48]`; distance=35.8pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='기능 경고 및 제어 \n차로 이탈방지 보조는 다음의 동작으로 경고하\n고 제어합니다.\n• 차로 이탈 경고\n• 차로 이탈방지 보조'
  - expanded; bbox `[37.58, 27.73, 80.79, 38.93]`; distance=68.1pt; vgap=68.1pt; same_column=True; owner=True; reason=None; raw='운전자 보조'
  - excluded-nearby; bbox `[220.98, 268.0, 309.35, 285.35]`; distance=91.9pt; vgap=56.1pt; same_column=False; owner=False; reason=다른 column; raw='2C_LaneDepartureWarningInfo\n우측'
  - excluded-nearby; bbox `[36.73, 322.94, 200.55, 382.81]`; distance=111.0pt; vgap=111.0pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='• 차로 주행 보조 버튼(\n)을 길게 눌러 차로\n이탈방지 보조를 끄면, 차로 안전 설정이 해\n제됩니다.\n• 시동을 껐다가 걸어도 차로 이탈방지 보조\n설정은 유지됩니다.'
  - excluded-nearby; bbox `[220.98, 394.87, 384.86, 472.19]`; distance=218.7pt; vgap=183.0pt; same_column=False; owner=False; reason=다른 column; raw='2C_LaneDepartureWarningInfo_2\n클러스터 표시창에 초록색 \n표시등과 이탈한\n방향의 차선 깜빡임 표시, 경고음, 스터어링 휠\n을 통하여 차로 이탈 경고를 알립니다.\n차로 이탈 경고는 다음의 조건에서 작동합니\n다.\n• 자차 속도: 약 60-200 km/h'

### p.328 / image 4

- image bbox: `[221.03, 160.07, 385.42, 264.95]`; candidate: 차로이탈 경고
- A LLM 전달 context 필드: ['좌측', '우측', '차로이탈 경고', '기능 경고 및 제어\n차로 이탈방지 보조는 다음의 동작으로 경고하\n고 제어합니다.\n차로 이탈 경고\n차로 이탈방지 보조']
- B LLM 전달 text (78자): '기능 경고 및 제어 차로 이탈방지 보조는 다음의 동작으로 경고하 고 제어합니다. 차로 이탈 경고 차로 이탈방지 보조\n차로이탈 경고\n좌측\n우측'
- A 결과: '차로 이탈 경고' → '차로이탈 경고' (fallback_candidate / new_tokens:이탈,차로)
- B 결과: '차로이탈 경고' → '차로이탈 경고' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[297.03, 149.98, 309.35, 158.48]`; distance=1.6pt; vgap=1.6pt; same_column=True; owner=True; reason=None; raw='좌측'
  - expanded; bbox `[220.98, 268.0, 309.35, 285.35]`; distance=3.1pt; vgap=3.1pt; same_column=True; owner=True; reason=None; raw='2C_LaneDepartureWarningInfo\n우측'
  - expanded; bbox `[220.97, 136.69, 274.32, 147.61]`; distance=12.5pt; vgap=12.5pt; same_column=True; owner=True; reason=None; raw='차로이탈 경고'
  - expanded; bbox `[220.98, 63.51, 384.86, 127.48]`; distance=32.6pt; vgap=32.6pt; same_column=True; owner=True; reason=None; raw='기능 경고 및 제어 \n차로 이탈방지 보조는 다음의 동작으로 경고하\n고 제어합니다.\n• 차로 이탈 경고\n• 차로 이탈방지 보조'
  - excluded-nearby; bbox `[36.73, 213.52, 201.13, 296.0]`; distance=35.8pt; vgap=0.0pt; same_column=False; owner=False; reason=다른 column; raw='2C_LKAButton\n시동 ‘ON’ 상태에서 차로 주행 보조 버튼(\n)\n을 길게 눌러 차로 이탈 방지를 끄고 켤 수 있습\n니다. 차로 이탈방지 보조가 켜지면 클러스터\n표시창의 (\n) 표시등이 회색 또는 초록색으로\n켜집니다.\n차로 이탈방지 보조가 꺼지면 클러스터 표시창\n의 (\n) 표시등이 황색으로 켜집니다.'
  - excluded-nearby; bbox `[36.73, 322.94, 200.55, 382.81]`; distance=94.9pt; vgap=58.0pt; same_column=False; owner=False; reason=다른 column; raw='• 차로 주행 보조 버튼(\n)을 길게 눌러 차로\n이탈방지 보조를 끄면, 차로 안전 설정이 해\n제됩니다.\n• 시동을 껐다가 걸어도 차로 이탈방지 보조\n설정은 유지됩니다.'
  - excluded-nearby; bbox `[220.98, 394.87, 384.86, 472.19]`; distance=129.9pt; vgap=129.9pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='2C_LaneDepartureWarningInfo_2\n클러스터 표시창에 초록색 \n표시등과 이탈한\n방향의 차선 깜빡임 표시, 경고음, 스터어링 휠\n을 통하여 차로 이탈 경고를 알립니다.\n차로 이탈 경고는 다음의 조건에서 작동합니\n다.\n• 자차 속도: 약 60-200 km/h'
  - excluded-nearby; bbox `[37.58, 63.2, 153.09, 77.86]`; distance=204.5pt; vgap=82.2pt; same_column=False; owner=False; reason=다른 column; raw='차로 이탈방지 보조 작동'
  - excluded-nearby; bbox `[220.97, 481.4, 384.87, 563.15]`; distance=216.5pt; vgap=216.5pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='차로 이탈방지 보조\n클러스터 표시창에 초록색(\n) 표시등이 깜빡\n이고, 차로를 벗어나지 않도록 조향을 도와줍\n니다.\n차로 이탈방지 보조는 다음의 조건에서 작동합\n니다.\n• 자차 속도: 약 60-200 km/h'

### p.329 / image 1

- image bbox: `[50.88, 77.04, 215.27, 181.91]`; candidate: 일정 시간 동안 스티어링 휠을 잡지 않으면 단
- A LLM 전달 context 필드: ['일정 시간 동안 스티어링 휠을 잡지 않으면 단\n계적으로 핸즈오프 경고문이 표시되고 경고음\n이 울립니다.҃', '핸즈오프 경고']
- B LLM 전달 text (66자): '핸즈오프 경고\n일정 시간 동안 스티어링 휠을 잡지 않으면 단 계적으로 핸즈오프 경고문이 표시되고 경고음 이 울립니다.҃'
- A 결과: '일정 시간 동안 스티어링 휠을 잡지 않으면 단계적으로 핸즈오프 경고문이 표시되고 경고음이 울립니다.' → '일정 시간 동안 스티어링 휠을 잡지 않으면 단' (fallback_candidate / new_tokens:경고문이,경고음이,단계적으로,울립니다,표시되고,핸즈오프)
- B 결과: '핸즈오프 경고' → '핸즈오프 경고' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[50.91, 183.53, 214.69, 223.59]`; distance=1.6pt; vgap=1.6pt; same_column=True; owner=True; reason=None; raw='2C_HandOffWarningInfo\n일정 시간 동안 스티어링 휠을 잡지 않으면 단\n계적으로 핸즈오프 경고문이 표시되고 경고음\n이 울립니다.҃'
  - expanded; bbox `[50.89, 63.72, 104.01, 74.64]`; distance=2.4pt; vgap=2.4pt; same_column=True; owner=True; reason=None; raw='핸즈오프 경고'
  - excluded-nearby; bbox `[235.16, 82.61, 399.02, 152.48]`; distance=35.8pt; vgap=0.0pt; same_column=False; owner=False; reason=다른 column; raw='• 클러스터 설정과 관련된 자세한 내용은 4장\n내 ‘클러스터 메뉴 설정’을 참고하십시오.\n• 차선이 인식된 경우, 클러스터 표시창에 차\n선 색상이 회색에서 흰색으로 바뀌고, 차로\n이탈방지 보조가 작동 가능한 경우 초록색\n(\n) 표시등이 표시됩니다.'
  - excluded-nearby; bbox `[50.91, 249.96, 214.73, 434.78]`; distance=68.0pt; vgap=68.0pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='• 차로 이탈방지 보조가 작동 중일 때 스티어\n링 휠을 고정하거나 일정 수준 이상으로 조\n작할 경우 조향을 도와주지 않을 수 있습니\n다.\n• 차로 이탈방지 보조는 모든 상황에서 작동하\n지는 않습니다. 항상 스티어링 휠을 잡고 주\n행하십시오.\n• 주행 상황에 따라 핸즈오프 경고문이 늦게\n표시될 수 있습니다. 항상 스티어링 휠을 잡\n고 주행하십시오.\n• 스티어링 휠을 약하게 잡으면 잡지 않은 것\n으로 판단하여 핸즈오프 경고문이 표시될 수\n있습니다.\n• 스티어링 휠에 물체를 붙일 경우 핸즈오프\n경고문이 정상적으로 표시되지 않을 수 있습\n니다.'
  - excluded-nearby; bbox `[280.39, 154.84, 356.46, 163.34]`; distance=117.2pt; vgap=0.0pt; same_column=False; owner=False; reason=다른 column; raw='차선이 인식되지 않은 경우'
  - excluded-nearby; bbox `[235.16, 272.86, 344.0, 290.21]`; distance=126.7pt; vgap=90.9pt; same_column=False; owner=False; reason=다른 column; raw='2C_LaneDetectionInfo\n차선이 인식된 경우'
  - excluded-nearby; bbox `[235.16, 399.73, 399.04, 511.18]`; distance=253.6pt; vgap=217.8pt; same_column=False; owner=False; reason=다른 column; raw='2C_LaneDetectionInfo_2\n• 클러스터 사양 또는 테마에 따라 클러스터\n표시창에 표시되는 이미지나 색상이 다를 수\n있습니다.\n• 차로 이탈방지 보조가 작동 중이어도 스티어\n링 휠을 직접 조작하여 조향을 제어할 수 있\n습니다.\n• 차로 이탈방지 보조가 조향을 보조할 때는\n스티어링 휠이 무겁거나 가볍게 느껴질 수\n있습니다.'

### p.332 / image 2

- image bbox: `[36.72, 388.3, 201.11, 493.18]`; candidate: 후측방에서 빠른 속도로 접근하는 차량을 인식
- A LLM 전달 context 필드: ['후측방에서 빠른 속도로 접근하는 차량을 인식\n하여 알려줍니다.', '위험을 알려주는 시점은 고속으로 접근하는 차\n량의 속도에 따라 다를 수 있습니다.', '경고 영역은 자차의 속도에 따라 변경됩니다.\n단, 사각 지대에 차량이 있더라도 자차가 빠른\n속도로 추월할 경우 경고를 하지 않습니다.']
- B LLM 전달 text (155자): '경고 영역은 자차의 속도에 따라 변경됩니다. 단, 사각 지대에 차량이 있더라도 자차가 빠른 속도로 추월할 경우 경고를 하지 않습니다.\n후측방에서 빠른 속도로 접근하는 차량을 인식 하여 알려줍니다.\n위험을 알려주는 시점은 고속으로 접근하는 차 량의 속도에 따라 다를 수 있습니다.'
- A 결과: '후측방에서 빠른 속도로 접근하는 차량을 인식하여 알려줍니다.' → '후측방에서 빠른 속도로 접근하는 차량을 인식' (fallback_candidate / new_tokens:알려줍니다,인식하여)
- B 결과: '후측방에서 빠른 속도로 접근하는 차량 인식' → '후측방에서 빠른 속도로 접근하는 차량 인식' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[37.34, 364.97, 200.55, 385.9]`; distance=2.4pt; vgap=2.4pt; same_column=True; owner=True; reason=None; raw='후측방에서 빠른 속도로 접근하는 차량을 인식\n하여 알려줍니다.'
  - excluded-nearby; bbox `[220.98, 398.57, 274.02, 416.98]`; distance=35.8pt; vgap=0.0pt; same_column=False; owner=False; reason=다른 column; raw='2C_RearRadar\n(1) 후측방 레이더'
  - excluded-nearby; bbox `[221.62, 420.12, 380.56, 431.05]`; distance=36.9pt; vgap=0.0pt; same_column=False; owner=False; reason=다른 column; raw='인식 센서의 위치는 위 그림을 참고하십시오.'
  - expanded; bbox `[37.34, 530.2, 200.49, 551.12]`; distance=37.0pt; vgap=37.0pt; same_column=True; owner=True; reason=None; raw='위험을 알려주는 시점은 고속으로 접근하는 차\n량의 속도에 따라 다를 수 있습니다.'
  - expanded; bbox `[37.33, 315.15, 201.12, 346.08]`; distance=42.2pt; vgap=42.2pt; same_column=True; owner=True; reason=None; raw='경고 영역은 자차의 속도에 따라 변경됩니다.\n단, 사각 지대에 차량이 있더라도 자차가 빠른\n속도로 추월할 경우 경고를 하지 않습니다.'
  - excluded-nearby; bbox `[221.69, 278.55, 259.63, 290.77]`; distance=134.6pt; vgap=97.5pt; same_column=False; owner=False; reason=다른 column; raw='인식 센서'
  - excluded-nearby; bbox `[220.98, 236.97, 385.5, 259.86]`; distance=164.2pt; vgap=128.4pt; same_column=False; owner=False; reason=다른 column; raw='BCA는 Blind-Spot Collision-Avoidance\nAssist의 약자입니다.'
  - excluded-nearby; bbox `[37.23, 96.96, 200.55, 170.87]`; distance=217.4pt; vgap=217.4pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='일정 속도 이상으로 주행 중 후측방의 차량을\n인식하여 충돌 위험이 판단되면 경고등과 경고\n음 등으로 알려줍니다. 또한 전진 출차 시 충돌\n위험이 높아지면 충돌하지 않도록 제동을 도와\n줍니다. \n사각 지대에 위치한 차량을 인식하여 알려줍니\n다.'

### p.343 / image 1

- image bbox: `[50.88, 107.04, 215.51, 212.15]`; candidate: 안전 하차 보조 이상 및 제한 사항 · 기능 이상
- A LLM 전달 context 필드: ['안전 하차 보조에 이상이 있으면 클러스터에 경\n고문이 일정시간 표시되며 통합 경고등( )이\n켜집니다. 당사 직영 하이테크센터나 블루핸즈\n에서 점검을 받으십시오.\n경고 대상 기능은 클러스터 표시창 중 유틸\n리티 정보 뷰의 서비스 메시지에서 확인할\n수 있습니다.', '기능 이상', '안전 하차 보조 이상 및 제한 사항']
- B LLM 전달 text (170자): '안전 하차 보조 이상 및 제한 사항\n기능 이상\n안전 하차 보조에 이상이 있으면 클러스터에 경 고문이 일정시간 표시되며 통합 경고등( )이 켜집니다. 당사 직영 하이테크센터나 블루핸즈 에서 점검을 받으십시오. 경고 대상 기능은 클러스터 표시창 중 유틸 리티 정보 뷰의 서비스 메시지에서 확인할 수 있습니다.'
- A 결과: '안전 하차 보조 이상 및 제한 사항' → '안전 하차 보조 이상 및 제한 사항' (llm_accepted / accepted)
- B 결과: '안전 하차 보조 기능 이상' → '안전 하차 보조 기능 이상' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[51.61, 93.5, 89.55, 105.72]`; distance=1.3pt; vgap=1.3pt; same_column=True; owner=True; reason=None; raw='기능 이상'
  - expanded; bbox `[50.91, 213.76, 214.73, 298.22]`; distance=1.6pt; vgap=1.6pt; same_column=True; owner=True; reason=None; raw='2C_ForwardSafetyMalfunctionInfo\n안전 하차 보조에 이상이 있으면 클러스터에 경\n고문이 일정시간 표시되며 통합 경고등( )이\n켜집니다. 당사 직영 하이테크센터나 블루핸즈\n에서 점검을 받으십시오.\n• 경고 대상 기능은 클러스터 표시창 중 유틸\n리티 정보 뷰의 서비스 메시지에서 확인할\n수 있습니다.'
  - expanded; bbox `[51.75, 63.2, 207.65, 77.86]`; distance=29.2pt; vgap=29.2pt; same_column=True; owner=True; reason=None; raw='안전 하차 보조 이상 및 제한 사항'
  - excluded-nearby; bbox `[235.16, 183.53, 399.4, 384.52]`; distance=35.4pt; vgap=0.0pt; same_column=False; owner=False; reason=다른 column; raw='2C_SCCDisabledInfo\n후측방 레이더 또는 뒷범퍼 주변에 눈, 비 등 이\n물질이 묻거나, 트레일러, 캐리어 및 기타 장비\n를 거치하면 인식 성능이 저하되어 안전 하차\n보조가 일시적으로 제한되거나 작동하지 않을\n수 있습니다.\n이때 클러스터에 경고문과 통합 경고등( )이\n표시되지만 안전 하차 보조 고장이 아닙니다.\n이물질을 제거하거나 트레일러, 캐리어, 또는\n기타 장비를 제거한 후 시동을 걸면 안전 하차\n보조는 다시 정상적으로 작동합니다. 항상 깨\n끗하게 유지하십시오. \n• 인식 센서 가림 경고 내용은 클러스터 표시\n창 중 유틸리티 정보 뷰의 서비스 메시지에\n서 확인할 수 있습니다.\n차량 후방 짐칸, 기타 장비 또는 이물질을 제거\n해도 안전 하차 보조가 정상적으로 작동하지 않\n으면 당사 직영 하이테크센터나 블루핸즈에서\n점검을 받으십시오.҃'
  - excluded-nearby; bbox `[235.86, 63.51, 294.02, 75.73]`; distance=67.9pt; vgap=31.3pt; same_column=False; owner=False; reason=다른 column; raw='인식 센서 가림'
  - excluded-nearby; bbox `[50.91, 407.11, 214.74, 456.58]`; distance=195.0pt; vgap=195.0pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='2C_CheckSideViewMirrorWarningLightInfo\n사이드 미러(실외 미러) 경고등에 이상이 있으\n면 클러스터에 경고문이 일정시간 표시되며 통\n합 경고등( )이 켜집니다. 당사 직영 하이테크\n센터나 블루핸즈에서 점검을 받으십시오.'
  - excluded-nearby; bbox `[235.16, 410.89, 399.04, 490.76]`; distance=234.1pt; vgap=198.7pt; same_column=False; owner=False; reason=다른 column; raw='• 인식 센서 경고문이 표시되지 않거나 경고등\n이 켜지지 않더라도 안전 하차 보조가 정상\n적으로 작동하지 않을 수 있습니다.\n• 시동을 건 직후에 인식 센서가 오염되었거나\n차량 주변에 물체가 존재하지 않는 경우(앞\n이 막힘 없이 트인 장소 등) 안전 하차 보조가\n정상적으로 작동하지 않을 수 있습니다.'

### p.344 / image 1

- image bbox: `[221.03, 84.0, 385.42, 188.87]`; candidate: 수동 속도 제한 보조 (MSLA)
- A LLM 전달 context 필드: ['(1) 속도 제한 표시등', '수동 속도 제한 보조 (MSLA)', '(2) 설정속도', '특정 속도 이상으로 주행하는 것을 원하지 않을\n때 속도 제한 기능을 실행할 수 있습니다. 제한\n속도를 초과하여 주행할 경우 주행속도가 제한\n속도 이하가 될 때까지 경고음이 울립니다.']
- B LLM 전달 text (184자): '수동 속도 제한 보조 (MSLA)\n(1) 속도 제한 표시등\n(2) 설정속도\n특정 속도 이상으로 주행하는 것을 원하지 않을 때 속도 제한 기능을 실행할 수 있습니다. 제한 속도를 초과하여 주행할 경우 주행속도가 제한 속도 이하가 될 때까지 경고음이 울립니다.\nMSLA는 Manual Speed Limit Assist의 약자\n입니다.'
- A 결과: '수동 속도 제한 보조(MSLA)' → '수동 속도 제한 보조(MSLA)' (llm_accepted / accepted)
- B 결과: '수동 속도 제한 보조(MSLA)' → '수동 속도 제한 보조(MSLA)' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[220.98, 190.53, 282.66, 208.94]`; distance=1.7pt; vgap=1.7pt; same_column=True; owner=True; reason=None; raw='2C_MSLAOverviewInfo\n(1) 속도 제한 표시등'
  - expanded; bbox `[221.97, 62.89, 381.01, 80.0]`; distance=4.0pt; vgap=4.0pt; same_column=True; owner=True; reason=None; raw='수동 속도 제한 보조 (MSLA)'
  - expanded; bbox `[220.98, 212.22, 259.67, 221.93]`; distance=23.3pt; vgap=23.3pt; same_column=True; owner=True; reason=None; raw='(2) 설정속도'
  - expanded; bbox `[221.54, 225.07, 384.83, 266.0]`; distance=36.2pt; vgap=36.2pt; same_column=True; owner=True; reason=None; raw='특정 속도 이상으로 주행하는 것을 원하지 않을\n때 속도 제한 기능을 실행할 수 있습니다. 제한\n속도를 초과하여 주행할 경우 주행속도가 제한\n속도 이하가 될 때까지 경고음이 울립니다.'
  - excluded-nearby; bbox `[36.73, 63.51, 200.58, 163.18]`; distance=36.8pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='제한 사항\n다음과 같은 경우에는 안전 하차 보조가 제대로\n반응하지 않거나 예기치 않은 기능 작동이 발생\n할 수 있습니다. 주의하여 운전하십시오.\n• 나무나 풀이 무성한 곳에서 하차할 경우\n• 젖은 도로에서 하차할 경우\n• 상대 차량이 빠르게 또는 느리게 접근할 경\n우҃'
  - excluded-nearby; bbox `[36.73, 189.56, 200.55, 294.42]`; distance=37.6pt; vgap=0.7pt; same_column=False; owner=True; reason=다른 column; raw='• 강한 전자파에 의해 안전 하차 보조가 순간\n적으로 해제될 수 있습니다.\n• 엔진 시동 중 또는 후측방 레이더 초기화(재\n부팅 등) 중에는 약 3초 동안 기능이 작동하\n지 않을 수 있습니다.\n• 가림 및 고장 상태에서 시동을 껐다 다시 걸\n면 가림 및 고장 상태가 유지 되어 안전 하차\n보조가 정상적으로 작동하지 않을 수 있습니\n다.'
  - expanded; bbox `[220.98, 292.94, 384.82, 305.84]`; distance=104.1pt; vgap=104.1pt; same_column=True; owner=True; reason=None; raw='MSLA는 Manual Speed Limit Assist의 약자'
  - expanded; bbox `[221.61, 304.91, 248.52, 315.84]`; distance=116.0pt; vgap=116.0pt; same_column=True; owner=True; reason=None; raw='입니다.'
  - excluded-nearby; bbox `[37.32, 334.17, 200.49, 365.09]`; distance=182.3pt; vgap=145.3pt; same_column=False; owner=True; reason=다른 column; raw='후측방 레이더 센서의 자세한 제한 사항은 ‘후\n측방 충돌방지 보조 (BCA)’의 제한 사항을 참\n고하십시오.'

### p.354 / image 3

- image bbox: `[221.03, 78.96, 385.42, 183.83]`; candidate: [B] 전방 차량
- A LLM 전달 context 필드: ['[A] 자차\n[B] 전방 차량', '전방 차량이 급격하게 조향할 경우']
- B LLM 전달 text (35자): '전방 차량이 급격하게 조향할 경우\n[A] 자차 [B] 전방 차량'
- A 결과: '[B] 전방 차량' → '[B] 전방 차량' (llm_accepted / accepted)
- B 결과: '전방 차량' → '전방 차량' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[220.98, 185.53, 314.53, 214.94]`; distance=1.7pt; vgap=1.7pt; same_column=True; owner=True; reason=None; raw='2C_DAWVehicleAheadSharplySteer\n[A] 자차\n[B] 전방 차량'
  - expanded; bbox `[220.98, 63.53, 351.65, 76.5]`; distance=2.5pt; vgap=2.5pt; same_column=True; owner=True; reason=None; raw='• 전방 차량이 급격하게 조향할 경우'
  - excluded-nearby; bbox `[220.98, 216.08, 384.86, 261.84]`; distance=32.2pt; vgap=32.2pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='전방 차량이 좌회전, 우회전, 유턴 등 급격한\n조향으로 이동할 경우 전방 차량 출발 알림\n이 정상적으로 작동하지 않을 수 있습니다.\n• 전방 차량이 급출발할 경우'
  - excluded-nearby; bbox `[36.73, 63.51, 200.52, 177.46]`; distance=36.9pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='작동 제한 사항 \n다음과 같은 상황에서는 운전자 주의 경고가 제\n한되거나 정상적으로 작동하지 않을 수 있습니\n다.\n• 과격하게 운전할 경우\n• 빈번하게 차선을 침범할 경우\n• 차로 이탈방지 보조 등 다른 운전자 보조에\n의해 차량이 제어될 경우\n• 차선이 흐릿하거나 지워진 경우'
  - excluded-nearby; bbox `[220.98, 370.88, 384.84, 410.35]`; distance=187.0pt; vgap=187.0pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='2C_DAWVehicleAheadAbruptlyDeparture\n전방 차량이 급출발할 경우 전방 차량 출발\n알림이 정상적으로 작동하지 않을 수 있습니\n다.'

### p.359 / image 2

- image bbox: `[50.88, 335.75, 215.27, 440.62]`; candidate: 일시 해제 후 다시 켜기
- A LLM 전달 context 필드: ['+ 스위치를 위로 올리거나 – 스위치를 아래로', '일시 해제 후 다시 켜기', '위의 상황 이외에 크루즈 컨트롤이 자동으로 일\n시 해제된 경우에는 당사 직영 하이테크센터나\n블루핸즈에서 점검을 받으십시오.']
- B LLM 전달 text (108자): '위의 상황 이외에 크루즈 컨트롤이 자동으로 일 시 해제된 경우에는 당사 직영 하이테크센터나 블루핸즈에서 점검을 받으십시오.\n일시 해제 후 다시 켜기\n+ 스위치를 위로 올리거나 – 스위치를 아래로'
- A 결과: '일시 해제 후 다시 켜기' → '일시 해제 후 다시 켜기' (llm_accepted / accepted)
- B 결과: '크루즈 컨트롤 일시 해제 후 다시 켜기' → '크루즈 컨트롤 일시 해제 후 다시 켜기' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[50.91, 442.13, 214.55, 461.61]`; distance=1.5pt; vgap=1.5pt; same_column=True; owner=True; reason=None; raw='2C_SpeedControlResuming\n+ 스위치를 위로 올리거나 – 스위치를 아래로'
  - expanded; bbox `[51.75, 316.8, 159.13, 331.47]`; distance=4.3pt; vgap=4.3pt; same_column=True; owner=True; reason=None; raw='일시 해제 후 다시 켜기'
  - excluded-nearby; bbox `[51.49, 460.69, 214.52, 481.61]`; distance=20.1pt; vgap=20.1pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='내리면 현재 클러스터의 속도로 크루즈 컨트롤\n이 작동합니다.'
  - excluded-nearby; bbox `[235.16, 350.63, 399.04, 543.46]`; distance=35.8pt; vgap=0.0pt; same_column=False; owner=False; reason=다른 column; raw='• 크루즈 컨트롤이 의도치 않게 작동하는 것을\n방지 하기 위해 사용하지 않을 때는 반드시\n기능을 끄십시오. 크루즈 컨트롤을 끌 때 크\n루즈 표시등(\n)이 꺼지는 것을 확인하\n십시오.\n• 설정속도는 반드시 규정 속도 이내로 하십시\n오.\n• 다음의 상황에서 크루즈 컨트롤 기능을 사용\n하면 사고가 발생할 수 있습니다. 반드시 주\n행이 원활한 도로에서만 사용하십시오.\n- 고속도로 인터체인지, 톨게이트 부근\n- 정체된 고속도로\n- 비, 눈, 얼음 등으로 미끄러워진 도로\n- 급커브길\n- 경사가 급한 내리막길이나 오르막길\n- 안개, 눈, 비, 모래바람 등으로 기상 상태가'
  - expanded; bbox `[51.52, 262.5, 214.69, 293.42]`; distance=42.3pt; vgap=42.3pt; same_column=True; owner=True; reason=None; raw='위의 상황 이외에 크루즈 컨트롤이 자동으로 일\n시 해제된 경우에는 당사 직영 하이테크센터나\n블루핸즈에서 점검을 받으십시오.'
  - excluded-nearby; bbox `[51.4, 483.68, 214.6, 527.6]`; distance=43.1pt; vgap=43.1pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='버튼을 누르면 직전에 설정했던 속도로 크\n루즈 컨트롤이 작동합니다.\n단, 차량 속도가 30 km/h 미만일 경우에는 작\n동하지 않습니다.'
  - excluded-nearby; bbox `[235.16, 284.2, 398.95, 324.26]`; distance=47.3pt; vgap=11.5pt; same_column=False; owner=False; reason=다른 column; raw='2C_SpeedControlButton\n크루즈 컨트롤을 끄려면 \n 버튼을 누르십시\n오. 클러스터의 크루즈 표시등(\n)이 꺼지\n고, 크루즈 컨트롤 기능이 해제됩니다. ҃'
  - excluded-nearby; bbox `[50.91, 63.51, 215.21, 233.58]`; distance=102.2pt; vgap=102.2pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='자동\n작동 중인 크루즈 컨트롤은 다음의 조건에서 자\n동으로 일시 해제됩니다.\n• ‘N’(중립)으로 변속할 경우\n• 주행 중 파킹 브레이크를 사용할 경우\n• 주행속도가 설정속도보다 20 km/h 낮아질\n경우 \n• 주행속도가 25 km/h 이하로 낮아진 경우 \n• 약 185 km/h 이상으로 가속한 경우\n• 차체 자세 제어(ESC)가 작동할 경우\n클러스터의 설정속도가 회색으로 표시되고 크\n루즈 컨트롤이 일시적으로 해제됩니다.\n크루즈 표시등(\n)은 계속 켜져 있습니다.'
  - excluded-nearby; bbox `[252.63, 542.53, 387.04, 553.46]`; distance=169.2pt; vgap=101.9pt; same_column=False; owner=False; reason=다른 column; raw='좋지 않거나 시야 확보가 어려운 경우'
  - excluded-nearby; bbox `[236.0, 158.87, 281.38, 173.54]`; distance=199.5pt; vgap=162.2pt; same_column=False; owner=False; reason=다른 column; raw='기능 끄기'
  - excluded-nearby; bbox `[235.7, 84.58, 399.03, 135.5]`; distance=237.0pt; vgap=200.2pt; same_column=False; owner=False; reason=다른 column; raw='일시 해제된 크루즈 컨트롤 기능을\n 버튼을\n눌러 재설정하는 경우 주행속도가 해제 직전의\n설정속도로 빠르게 증가하거나 감소할 수 있습\n니다. \n 버튼을 사용하기 전에 도로 상황 및\n직전의 설정속도를 확인하십시오.'

### p.359 / image 3

- image bbox: `[50.88, 485.02, 62.16, 492.22]`; candidate: 내리면 현재 클러스터의 속도로 크루즈 컨트롤
- A LLM 전달 context 필드: ['일시 해제된 크루즈 컨트롤 기능을\n버튼을\n눌러 재설정하는 경우 주행속도가 해제 직전의\n설정속도로 빠르게 증가하거나 감소할 수 있습\n니다.\n버튼을 사용하기 전에 도로 상황 및\n직전의 설정속도를 확인하십시오.', '일시 해제된 크루즈 컨트롤 기능을\n버튼을\n눌러 재설정하는 경우 주행속도가 해제 직전의\n설정속도로 빠르게 증가하거나 감소할 수 있습\n니다.\n버튼을 사용하기 전에 도로 상황 및\n직전의 설정속도를 확인하십시오.', '버튼을 누르면 직전에 설정했던 속도로 크\n루즈 컨트롤이 작동합니다.\n단, 차량 속도가 30 km/h 미만일 경우에는 작\n동하지 않습니다.', '내리면 현재 클러스터의 속도로 크루즈 컨트롤\n이 작동합니다.']
- B LLM 전달 text (225자): '일시 해제된 크루즈 컨트롤 기능을 버튼을 눌러 재설정하는 경우 주행속도가 해제 직전의 설정속도로 빠르게 증가하거나 감소할 수 있습 니다. 버튼을 사용하기 전에 도로 상황 및 직전의 설정속도를 확인하십시오.\n내리면 현재 클러스터의 속도로 크루즈 컨트롤 이 작동합니다.\n버튼을 누르면 직전에 설정했던 속도로 크 루즈 컨트롤이 작동합니다. 단, 차량 속도가 30 km/h 미만일 경우에는 작 동하지 않습니다.'
- A 결과: '내리면 현재 클러스터 속도로 크루즈 컨트롤 작동' → '내리면 현재 클러스터의 속도로 크루즈 컨트롤' (fallback_candidate / new_tokens:작동,클러스터)
- B 결과: '– 스위치를 아래로 내려 현재 속도로 크루즈 컨트롤 작동' → '내리면 현재 클러스터의 속도로 크루즈 컨트롤' (outside_candidate_and_source:스위치를,내려,아래로)
- blocks (current/expanded/excluded):
  - expanded; bbox `[235.7, 84.58, 399.03, 135.5]`; distance=0.0pt; vgap=0.0pt; same_column=True; owner=True; reason=None; raw='일시 해제된 크루즈 컨트롤 기능을\n 버튼을\n눌러 재설정하는 경우 주행속도가 해제 직전의\n설정속도로 빠르게 증가하거나 감소할 수 있습\n니다. \n 버튼을 사용하기 전에 도로 상황 및\n직전의 설정속도를 확인하십시오.'
  - expanded; bbox `[51.4, 483.68, 214.6, 527.6]`; distance=0.0pt; vgap=0.0pt; same_column=True; owner=True; reason=None; raw='버튼을 누르면 직전에 설정했던 속도로 크\n루즈 컨트롤이 작동합니다.\n단, 차량 속도가 30 km/h 미만일 경우에는 작\n동하지 않습니다.'
  - expanded; bbox `[51.49, 460.69, 214.52, 481.61]`; distance=3.4pt; vgap=3.4pt; same_column=True; owner=True; reason=None; raw='내리면 현재 클러스터의 속도로 크루즈 컨트롤\n이 작동합니다.'
  - excluded-nearby; bbox `[50.91, 442.13, 214.55, 461.61]`; distance=23.4pt; vgap=23.4pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='2C_SpeedControlResuming\n+ 스위치를 위로 올리거나 – 스위치를 아래로'
  - excluded-nearby; bbox `[236.0, 158.87, 281.38, 173.54]`; distance=35.8pt; vgap=35.8pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='기능 끄기'
  - excluded-nearby; bbox `[50.91, 63.51, 215.21, 233.58]`; distance=76.1pt; vgap=0.0pt; same_column=False; owner=False; reason=다른 column; raw='자동\n작동 중인 크루즈 컨트롤은 다음의 조건에서 자\n동으로 일시 해제됩니다.\n• ‘N’(중립)으로 변속할 경우\n• 주행 중 파킹 브레이크를 사용할 경우\n• 주행속도가 설정속도보다 20 km/h 낮아질\n경우 \n• 주행속도가 25 km/h 이하로 낮아진 경우 \n• 약 185 km/h 이상으로 가속한 경우\n• 차체 자세 제어(ESC)가 작동할 경우\n클러스터의 설정속도가 회색으로 표시되고 크\n루즈 컨트롤이 일시적으로 해제됩니다.\n크루즈 표시등(\n)은 계속 켜져 있습니다.'
  - excluded-nearby; bbox `[51.75, 316.8, 159.13, 331.47]`; distance=153.5pt; vgap=153.5pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='일시 해제 후 다시 켜기'
  - excluded-nearby; bbox `[235.16, 284.2, 398.95, 324.26]`; distance=161.1pt; vgap=161.1pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='2C_SpeedControlButton\n크루즈 컨트롤을 끄려면 \n 버튼을 누르십시\n오. 클러스터의 크루즈 표시등(\n)이 꺼지\n고, 크루즈 컨트롤 기능이 해제됩니다. ҃'
  - excluded-nearby; bbox `[51.52, 262.5, 214.69, 293.42]`; distance=191.6pt; vgap=191.6pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='위의 상황 이외에 크루즈 컨트롤이 자동으로 일\n시 해제된 경우에는 당사 직영 하이테크센터나\n블루핸즈에서 점검을 받으십시오.'
  - excluded-nearby; bbox `[235.16, 350.63, 399.04, 543.46]`; distance=227.5pt; vgap=227.5pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='• 크루즈 컨트롤이 의도치 않게 작동하는 것을\n방지 하기 위해 사용하지 않을 때는 반드시\n기능을 끄십시오. 크루즈 컨트롤을 끌 때 크\n루즈 표시등(\n)이 꺼지는 것을 확인하\n십시오.\n• 설정속도는 반드시 규정 속도 이내로 하십시\n오.\n• 다음의 상황에서 크루즈 컨트롤 기능을 사용\n하면 사고가 발생할 수 있습니다. 반드시 주\n행이 원활한 도로에서만 사용하십시오.\n- 고속도로 인터체인지, 톨게이트 부근\n- 정체된 고속도로\n- 비, 눈, 얼음 등으로 미끄러워진 도로\n- 급커브길\n- 경사가 급한 내리막길이나 오르막길\n- 안개, 눈, 비, 모래바람 등으로 기상 상태가'

### p.365 / image 3

- image bbox: `[235.19, 219.59, 399.58, 324.47]`; candidate: 일시적 가속
- A LLM 전달 context 필드: ['스마트 크루즈 컨트롤이 켜진 상태에서 가속 페\n달을 밟으면 설정속도를 변경하지 않고 일시적\n으로 가속할 수 있습니다. 가속하는 동안에는\n클러스터 표시창의 설정속도, 차간거리 단계\n및 목표 차간거리가 깜빡입니다. 단, 가속 페달\n밟음 정도가 부족한 경우 차량이 감속될 수 있\n습니다.҃', '일시적 가속', '전방 차량은 자차와 전방 차량과의 실제 거\n리를 반영하여 표시됩니다.\n목표 차간거리는 차량의 속도와 설정된 차간\n거리 단계에 따라 달라집니다. 속도가 낮은\n경우 차간거리 단계를 변경하더라도 목표 차\n간거리의 변경량이 적을 수 있습니다.\n클러스터 사양 또는 테마에 따라 클러스터\n표시창에 표시되는 이미지나 색상이 다를 수\n있습니다.']
- B LLM 전달 text (417자): '전방 차량은 자차와 전방 차량과의 실제 거 리를 반영하여 표시됩니다. 목표 차간거리는 차량의 속도와 설정된 차간 거리 단계에 따라 달라집니다. 속도가 낮은 경우 차간거리 단계를 변경하더라도 목표 차 간거리의 변경량이 적을 수 있습니다. 클러스터 사양 또는 테마에 따라 클러스터 표시창에 표시되는 이미지나 색상이 다를 수 있습니다.\n일시적 가속\n스마트 크루즈 컨트롤이 켜진 상태에서 가속 페 달을 밟으면 설정속도를 변경하지 않고 일시적 으로 가속할 수 있습니다. 가속하는 동안에는 클러스터 표시창의 설정속도, 차간거리 단계 및 목표 차간거리가 깜빡입니다. 단, 가속 페달 밟음 정도가 부족한 경우 차량이 감속될 수 있 습니다.҃\n가속 페달로 일시적으로 가속할 때는 전방에 차 량이 있어도 속도와 차간거리가 자동으로 조절 되지 않으므로 주의하십시오.'
- A 결과: '일시적 가속' → '일시적 가속' (llm_accepted / accepted)
- B 결과: '스마트 크루즈 컨트롤 일시적 가속' → '스마트 크루즈 컨트롤 일시적 가속' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[235.86, 206.15, 282.56, 218.37]`; distance=1.2pt; vgap=1.2pt; same_column=True; owner=True; reason=None; raw='일시적 가속'
  - expanded; bbox `[235.16, 326.17, 399.04, 406.23]`; distance=1.7pt; vgap=1.7pt; same_column=True; owner=True; reason=None; raw='2C_SCCAcceleratingTemporarilyInfo\n스마트 크루즈 컨트롤이 켜진 상태에서 가속 페\n달을 밟으면 설정속도를 변경하지 않고 일시적\n으로 가속할 수 있습니다. 가속하는 동안에는\n클러스터 표시창의 설정속도, 차간거리 단계\n및 목표 차간거리가 깜빡입니다. 단, 가속 페달\n밟음 정도가 부족한 경우 차량이 감속될 수 있\n습니다.҃'
  - expanded; bbox `[235.16, 82.61, 398.98, 187.46]`; distance=32.1pt; vgap=32.1pt; same_column=True; owner=True; reason=None; raw='• 전방 차량은 자차와 전방 차량과의 실제 거\n리를 반영하여 표시됩니다.\n• 목표 차간거리는 차량의 속도와 설정된 차간\n거리 단계에 따라 달라집니다. 속도가 낮은\n경우 차간거리 단계를 변경하더라도 목표 차\n간거리의 변경량이 적을 수 있습니다.\n• 클러스터 사양 또는 테마에 따라 클러스터\n표시창에 표시되는 이미지나 색상이 다를 수\n있습니다.'
  - excluded-nearby; bbox `[50.91, 364.88, 214.61, 409.21]`; distance=77.5pt; vgap=40.4pt; same_column=False; owner=False; reason=다른 column; raw='2C_SCCTemporaryCancelIndicatorInfo\n스마트 크루즈 컨트롤의 상태에 따라 클러스터\n표시창에 표시되는 항목은 다음과 같습니다.\n• 작동 상태'
  - expanded; bbox `[235.77, 434.55, 398.98, 465.47]`; distance=110.1pt; vgap=110.1pt; same_column=True; owner=True; reason=None; raw='가속 페달로 일시적으로 가속할 때는 전방에 차\n량이 있어도 속도와 차간거리가 자동으로 조절\n되지 않으므로 주의하십시오.'
  - excluded-nearby; bbox `[51.51, 63.51, 214.72, 117.63]`; distance=138.8pt; vgap=102.0pt; same_column=False; owner=False; reason=다른 column; raw="작동 상태 표시\n스마트 크루즈 컨트롤의 상태 표시를 보려면 클\n러스터에서 주행 보조 뷰를 선택하십시오. 주\n행 보조 뷰 선택 방법은 4장 내 '클러스터 메뉴\n설정'을 참고하십시오."
  - excluded-nearby; bbox `[50.87, 419.41, 203.48, 471.19]`; distance=152.0pt; vgap=94.9pt; same_column=False; owner=False; reason=다른 column; raw='(1) 전방 차량 유무 및 설정된 차간거리 단계\n(2) 설정속도\n(3) 전방 차량 유무 및 목표 차간거리\n• 일시 해제 상태'

### p.366 / image 1

- image bbox: `[36.72, 77.04, 201.11, 181.91]`; candidate: 자동 일시 해제
- A LLM 전달 context 필드: ['아래와 같은 상황에서는 스마트 크루즈 컨트롤\n이 자동으로 일시 해제됩니다.\n210 km/h 이상으로 가속할 경우\n일정시간 이상 정차할 경우\n가속 페달을 일정 시간 이상 지속해서 밟을\n경우\n스마트 크루즈 컨트롤 작동 조건을 만족하지\n않는 경우\n스마트 크루즈 컨트롤이 자동으로 일시 해제되\n면 경고문과 경고음을 통해 자동 일시 해제를\n알립니다.҃', '자동 일시 해제', '운전자 보조']
- B LLM 전달 text (207자): '운전자 보조\n자동 일시 해제\n아래와 같은 상황에서는 스마트 크루즈 컨트롤 이 자동으로 일시 해제됩니다. 210 km/h 이상으로 가속할 경우 일정시간 이상 정차할 경우 가속 페달을 일정 시간 이상 지속해서 밟을 경우 스마트 크루즈 컨트롤 작동 조건을 만족하지 않는 경우 스마트 크루즈 컨트롤이 자동으로 일시 해제되 면 경고문과 경고음을 통해 자동 일시 해제를 알립니다.҃'
- A 결과: '자동 일시 해제' → '자동 일시 해제' (llm_accepted / accepted)
- B 결과: '스마트 크루즈 컨트롤 자동 일시 해제' → '스마트 크루즈 컨트롤 자동 일시 해제' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[37.44, 63.51, 95.36, 75.73]`; distance=1.3pt; vgap=1.3pt; same_column=True; owner=True; reason=None; raw='자동 일시 해제'
  - expanded; bbox `[36.73, 183.53, 200.55, 326.54]`; distance=1.6pt; vgap=1.6pt; same_column=True; owner=True; reason=None; raw='2C_SCCAutoTemporaryCancelingInfo\n아래와 같은 상황에서는 스마트 크루즈 컨트롤\n이 자동으로 일시 해제됩니다.\n• 210 km/h 이상으로 가속할 경우\n• 일정시간 이상 정차할 경우\n• 가속 페달을 일정 시간 이상 지속해서 밟을\n경우\n• 스마트 크루즈 컨트롤 작동 조건을 만족하지\n않는 경우\n스마트 크루즈 컨트롤이 자동으로 일시 해제되\n면 경고문과 경고음을 통해 자동 일시 해제를\n알립니다.҃'
  - excluded-nearby; bbox `[220.98, 183.53, 384.89, 243.01]`; distance=37.4pt; vgap=1.6pt; same_column=False; owner=False; reason=다른 column; raw='2C_SCCOpeartingConditionNotMetInfo\n스마트 크루즈 컨트롤이 작동할 수 있는 조건이\n아닐 때 기능을 사용하기 위해 주행 보조 버튼\n이나 + 또는 - 스위치,\n 스위치를 누르면 경고\n문과 경고음을 통해 스마트 크루즈 컨트롤 작동\n조건이 아님을 알립니다.'
  - expanded; bbox `[37.58, 27.73, 80.79, 38.93]`; distance=38.1pt; vgap=38.1pt; same_column=True; owner=True; reason=None; raw='운전자 보조'
  - excluded-nearby; bbox `[221.69, 63.51, 356.05, 75.73]`; distance=38.3pt; vgap=1.3pt; same_column=False; owner=False; reason=다른 column; raw='스마트 크루즈 컨트롤 비작동 알림'
  - excluded-nearby; bbox `[221.69, 256.86, 311.29, 269.08]`; distance=112.0pt; vgap=74.9pt; same_column=False; owner=False; reason=다른 column; raw='정차 후 다시 출발 안내'
  - excluded-nearby; bbox `[37.32, 354.88, 200.53, 395.81]`; distance=173.0pt; vgap=173.0pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='스마트 크루즈 컨트롤이 해제되면 전방 차량과\n의 간격이 유지되지 않습니다. 전방 도로 상황\n및 주행 상태를 확인하고 필요하면 브레이크 페\n달을 밟아 차량 속도를 직접 조절하십시오.'
  - excluded-nearby; bbox `[220.98, 376.88, 384.89, 469.35]`; distance=230.7pt; vgap=195.0pt; same_column=False; owner=False; reason=다른 column; raw='2C_SCCReStartInfo\n스마트 크루즈 컨트롤 작동 중에는 전방 차량이\n정차하면 따라서 정차합니다. 일정 시간 내에\n전방 차량이 출발하면 자동으로 출발합니다.\n정차 후 일정 시간이 지나면 클러스터 표시창에\n위 그림과 같이 안내문이 표시됩니다. 다시 출\n발하려면 가속 페달을 밟거나, + 또는 - 스위치\n를 위아래로 누르거나 \n 스위치를 누르십시\n오.'

### p.378 / image 4

- image bbox: `[36.72, 320.39, 201.11, 425.26]`; candidate: 차로 유지 보조
- A LLM 전달 context 필드: ['양쪽 차선 또는 선행 차량을 인식하고 차량의\n속도가 200 km/h 이하인 경우 차로 중앙을 유\n지하며 주행하도록 조향을 도와줍니다. 클러스\n터 표시창에 표시등( )이 초록색으로 표시됩\n니다.', '차로 유지 보조', '기능 경고 및 제어']
- B LLM 전달 text (127자): '기능 경고 및 제어\n차로 유지 보조\n양쪽 차선 또는 선행 차량을 인식하고 차량의 속도가 200 km/h 이하인 경우 차로 중앙을 유 지하며 주행하도록 조향을 도와줍니다. 클러스 터 표시창에 표시등( )이 초록색으로 표시됩 니다.'
- A 결과: '차로 유지 보조' → '차로 유지 보조' (llm_accepted / accepted)
- B 결과: '차로 유지 보조' → '차로 유지 보조' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[36.73, 426.87, 200.5, 486.35]`; distance=1.6pt; vgap=1.6pt; same_column=True; owner=True; reason=None; raw='2C_LKALaneDetectInfo\n양쪽 차선 또는 선행 차량을 인식하고 차량의\n속도가 200 km/h 이하인 경우 차로 중앙을 유\n지하며 주행하도록 조향을 도와줍니다. 클러스\n터 표시창에 표시등( )이 초록색으로 표시됩\n니다.'
  - expanded; bbox `[36.72, 307.05, 92.2, 317.98]`; distance=2.4pt; vgap=2.4pt; same_column=True; owner=True; reason=None; raw='차로 유지 보조'
  - expanded; bbox `[37.44, 286.85, 106.82, 299.07]`; distance=21.3pt; vgap=21.3pt; same_column=True; owner=True; reason=None; raw='기능 경고 및 제어'
  - excluded-nearby; bbox `[220.98, 361.88, 384.81, 391.94]`; distance=35.8pt; vgap=0.0pt; same_column=False; owner=False; reason=다른 column; raw='2C_DisableLFAInfo\n계속해서 스티어링 휠을 잡지 않을 경우, 차로\n유지 보조가 자동으로 꺼집니다.҃'
  - excluded-nearby; bbox `[220.98, 418.31, 384.85, 558.15]`; distance=35.8pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='• 차로 유지 보조가 작동 중일 때 스티어링 휠\n을 고정하거나 일정 수준 이상으로 조작할\n경우 조향을 보조하지 않을 수 있습니다.\n• 차로 유지 보조는 모든 상황에서 작동하지는\n않습니다. 항상 스티어링 휠을 잡고 주행하\n십시오.\n• 주행 상황에 따라 핸즈오프 경고문이 늦게\n표시될 수 있습니다. 항상 스티어링 휠을 잡\n고 주행하십시오.\n• 스티어링 휠을 약하게 잡으면 잡지 않은 것\n으로 판단하여 핸즈오프 경고문이 표시될 수\n있습니다.'
  - excluded-nearby; bbox `[36.73, 213.52, 201.13, 273.0]`; distance=47.4pt; vgap=47.4pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='2C_LKAButton\n시동 ‘ON’ 상태에서 차로 주행 보조 버튼(\n)\n을 누르십시오. 차로 유지 보조가 켜지고 클러\n스터에 표시등( )이 회색 또는 초록색으로 표\n시됩니다. 차로 유지 보조를 끄려면 차로 주행\n보조 버튼을 다시 누르십시오.'
  - excluded-nearby; bbox `[37.32, 515.26, 200.53, 536.19]`; distance=90.0pt; vgap=90.0pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='조향을 보조 하지 않을 때는 표시등( )이 흰색\n으로 깜빡인 후 회색으로 바뀝니다.'
  - excluded-nearby; bbox `[220.98, 183.53, 384.87, 252.85]`; distance=103.3pt; vgap=67.5pt; same_column=False; owner=False; reason=다른 column; raw='2C_HandOffWarningInfo\n일정 시간 동안 스티어링 휠을 잡지 않으면 단\n계적으로 핸즈오프 경고문이 표시되고 경고음\n이 울립니다.\n• 1단계: 경고문 \n• 2단계: 경고문(빨간색 스티어링 휠) + 경고음'
  - excluded-nearby; bbox `[37.44, 93.5, 106.82, 105.72]`; distance=214.7pt; vgap=214.7pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='기능 켜기 및 끄기'

### p.383 / image 1

- image bbox: `[50.88, 77.04, 215.27, 181.91]`; candidate: 주행속도 제한
- A LLM 전달 context 필드: ['핸즈오프에 의해 고속도로 주행 보조가 꺼지면\n주행속도가 제한됩니다. 주행속도 제한 기능이\n작동하는 중에는 지속해서 경고문이 표시되고\n경고음이 울립니다.', '주행속도 제한', '대기 상태\n스마트 크루즈 컨트롤이 일시적으로 해제되면\n고속도로 주행 보조는 대기 상태가 됩니다. 차\n로 유지 보조는 정상적으로 작동합니다.']
- B LLM 전달 text (170자): '주행속도 제한\n핸즈오프에 의해 고속도로 주행 보조가 꺼지면 주행속도가 제한됩니다. 주행속도 제한 기능이 작동하는 중에는 지속해서 경고문이 표시되고 경고음이 울립니다.\n대기 상태 스마트 크루즈 컨트롤이 일시적으로 해제되면 고속도로 주행 보조는 대기 상태가 됩니다. 차 로 유지 보조는 정상적으로 작동합니다.'
- A 결과: '주행속도 제한' → '주행속도 제한' (llm_accepted / accepted)
- B 결과: '핸즈오프에 따른 주행속도 제한' → '주행속도 제한' (outside_candidate_and_source:따른)
- blocks (current/expanded/excluded):
  - expanded; bbox `[50.91, 183.53, 214.55, 233.01]`; distance=1.6pt; vgap=1.6pt; same_column=True; owner=True; reason=None; raw='2C_HDADeactivatedDuetoHandOffInfo\n핸즈오프에 의해 고속도로 주행 보조가 꺼지면\n주행속도가 제한됩니다. 주행속도 제한 기능이\n작동하는 중에는 지속해서 경고문이 표시되고\n경고음이 울립니다.'
  - expanded; bbox `[50.89, 63.72, 104.01, 74.64]`; distance=2.4pt; vgap=2.4pt; same_column=True; owner=True; reason=None; raw='주행속도 제한'
  - excluded-nearby; bbox `[235.86, 108.49, 276.6, 120.71]`; distance=37.1pt; vgap=0.0pt; same_column=False; owner=False; reason=다른 column; raw='기능 이상'
  - excluded-nearby; bbox `[236.0, 63.2, 398.74, 92.85]`; distance=37.3pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='고속도로 주행 보조 이상 및 제한 사\n항'
  - expanded; bbox `[50.89, 242.07, 214.63, 285.98]`; distance=60.2pt; vgap=60.2pt; same_column=True; owner=True; reason=None; raw='대기 상태\n스마트 크루즈 컨트롤이 일시적으로 해제되면\n고속도로 주행 보조는 대기 상태가 됩니다. 차\n로 유지 보조는 정상적으로 작동합니다.'
  - excluded-nearby; bbox `[235.16, 228.76, 399.04, 323.79]`; distance=82.6pt; vgap=46.8pt; same_column=False; owner=False; reason=다른 column; raw='2C_ForwardSafetyMalfunctionInfo\n고속도로 주행 보조나 고속도로 차로변경 보조\n에 이상이 있으면 클러스터 표시창에 경고문이\n일정시간 표시되며 통합 경고등( )이 켜집니\n다. 당사 직영 하이테크센터나 블루핸즈에서\n점검을 받으십시오.\n• 경고 내용은 클러스터의 뷰 모드 중 유틸리\n티 정보 뷰의 서비스 메시지에서 확인할 수\n있습니다.҃'
  - excluded-nearby; bbox `[50.91, 312.94, 215.41, 431.79]`; distance=131.0pt; vgap=131.0pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='• 주행속도 제한 기능은 주행속도를 60 km/h\n이하로 제한합니다. 앞 차량을 따라 감속은\n하지만 가속하지 않습니다.\n• 다음과 같은 경우에는 주행속도 제한 기능이\n해제됩니다.\n- 다시 스티어링 휠을 잡을 경우\n- 차로 주행 보조(\n) 버튼을 눌러 차로 유\n지 보조 기능을 켤 경우\n- +, -, \n 스위치 또는 \n버튼, 가속 페달,\n브레이크 페달을 조작할 경우'
  - excluded-nearby; bbox `[235.16, 350.16, 399.55, 554.98]`; distance=204.0pt; vgap=168.2pt; same_column=False; owner=False; reason=다른 column; raw='• 모든 상황에서 운전자의 조작이 우선합니다.\n• 항상 스티어링 휠을 잡고 주행하십시오.\n• 고속도로 주행 보조는 주행을 보조하는 편의\n기능입니다. 완전한 자율 주행 시스템이 아\n니므로 사고가 발생하면 그 책임은 운전자에\n게 있습니다. 항상 교통 상황을 확인하고 필\n요한 경우 직접 적절한 조치를 취하십시오.\n• 운전자는 항상 전방 및 주변 상황을 주시하\n며 안전하게 운전해야 하고, 도로교통법을\n준수해야 합니다. 차량 제조사는 운전자의\n도로교통법 위반 행위나 사고에 대하여 어떠\n한 책임도 지지 않습니다.\n• 고속도로 주행 보조는 모든 교통 상황을 판\n단할 수는 없습니다. 자동차, 모터사이클, 자\n전거, 보행자, 가드레일, 톨게이트와 같은 불\n특정 물체 및 구조물 등 주변의 충돌 가능한\n대상이 감지되지 않을 수 있으므로 기능 한\n계를 유의하여 사용하십시오.'

### p.389 / image 3

- image bbox: `[234.95, 270.47, 399.82, 375.58]`; candidate: 서라운드 뷰 모니터 자동 켜짐
- A LLM 전달 context 필드: ['서라운드 뷰 모니터 자동 켜짐', "서라운드 뷰 모니터의 자동 켜짐 기능을 설정하\n려면 시동 'ON' 상태에서 인포테인먼트 시스템\n의 설정 > 차량 > 운전자 보조 > 주차 안전 > 서\n라운드 뷰 모니터 자동 켜짐을 차례로 선택하십\n시오.", '후방 뷰 주차 가이드의 가로 가이드라인은 차량\n으로부터 약 0.5 m, 1 m, 2.3 m 거리를 나타냅\n니다.']
- B LLM 전달 text (265자): "후방 뷰 주차 가이드의 가로 가이드라인은 차량 으로부터 약 0.5 m, 1 m, 2.3 m 거리를 나타냅 니다.\n서라운드 뷰 모니터 자동 켜짐\n서라운드 뷰 모니터의 자동 켜짐 기능을 설정하 려면 시동 'ON' 상태에서 인포테인먼트 시스템 의 설정 > 차량 > 운전자 보조 > 주차 안전 > 서 라운드 뷰 모니터 자동 켜짐을 차례로 선택하십 시오.\n서라운드 뷰 모니터 자동 켜짐에 대한 자세한 내용은 ‘서라운드 뷰 모니터 작동’의 서라운드 뷰 모니터 자동 켜짐을 참고하십시오."
- A 결과: '서라운드 뷰 모니터 자동 켜짐' → '서라운드 뷰 모니터 자동 켜짐' (llm_accepted / accepted)
- B 결과: '서라운드 뷰 모니터 자동 켜짐' → '서라운드 뷰 모니터 자동 켜짐' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[235.86, 256.84, 355.26, 269.06]`; distance=1.4pt; vgap=1.4pt; same_column=True; owner=True; reason=None; raw='서라운드 뷰 모니터 자동 켜짐'
  - expanded; bbox `[235.16, 379.5, 399.07, 439.58]`; distance=3.9pt; vgap=3.9pt; same_column=True; owner=True; reason=None; raw="2C_SVMAuto\n서라운드 뷰 모니터의 자동 켜짐 기능을 설정하\n려면 시동 'ON' 상태에서 인포테인먼트 시스템\n의 설정 > 차량 > 운전자 보조 > 주차 안전 > 서\n라운드 뷰 모니터 자동 켜짐을 차례로 선택하십\n시오."
  - expanded; bbox `[235.78, 207.23, 399.05, 238.15]`; distance=32.3pt; vgap=32.3pt; same_column=True; owner=True; reason=None; raw='후방 뷰 주차 가이드의 가로 가이드라인은 차량\n으로부터 약 0.5 m, 1 m, 2.3 m 거리를 나타냅\n니다.'
  - excluded-nearby; bbox `[50.91, 185.93, 215.31, 325.96]`; distance=35.4pt; vgap=0.0pt; same_column=False; owner=False; reason=다른 column; raw="2C_SVMParkingDistanceWarningInfo\n서라운드 뷰 모니터 작동 중에 화면의 설정 버\n튼( )을 누르거나, 시동 'ON' 상태에서 인포테\n인먼트 시스템의 설정 > 운전자 보조 > 주차 안\n전 > 카메라 설정을 차례로 선택하십시오. 서라\n운드 뷰 모니터의 표시 정보 변경할 수 있습니\n다.\n• 표시 정보: 탑 뷰 주차 가이드라인, 후방 주차\n가이드라인, 주차 거리 경고 기능을 설정할\n수 있습니다.\n• 화면 설정: 카메라 영상의 밝기(주간/야간)\n와 대비를 설정할 수 있습니다. (사양 적용\n시)"
  - excluded-nearby; bbox `[51.53, 354.88, 214.74, 375.81]`; distance=36.4pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='차량 사양에 따라 화면 설정 메뉴가 없을 수도\n있습니다.'
  - excluded-nearby; bbox `[50.89, 394.71, 214.76, 448.62]`; distance=55.5pt; vgap=19.1pt; same_column=False; owner=True; reason=다른 column; raw='주차 거리 경고\n표시 정보의 주차 거리 경고가 선택되어 있는\n경우, 주차 거리 경고 작동 시 서라운드 뷰 모니\n터 화면 우측의 탑 뷰에 주차 거리 경고 이미지\n가 표시됩니다.'
  - excluded-nearby; bbox `[235.15, 134.39, 398.93, 178.31]`; distance=92.2pt; vgap=92.2pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='후방 주차 가이드라인\n표시 정보의 후방 주차 가이드라인이 선택되어\n있는 경우, 좌측 영상에 후방 주차 가이드라인\n이 표시됩니다.'
  - expanded; bbox `[235.78, 468.49, 399.06, 499.41]`; distance=92.9pt; vgap=92.9pt; same_column=True; owner=True; reason=None; raw='서라운드 뷰 모니터 자동 켜짐에 대한 자세한\n내용은 ‘서라운드 뷰 모니터 작동’의 서라운드\n뷰 모니터 자동 켜짐을 참고하십시오.'
  - excluded-nearby; bbox `[50.89, 457.68, 214.68, 511.6]`; distance=118.6pt; vgap=82.1pt; same_column=False; owner=True; reason=다른 column; raw='탑 뷰 주차 가이드라인\n표시 정보의 탑 뷰 주차 가이드라인이 선택되어\n있는 경우, 전방 탑 뷰 또는 후방 탑 뷰 작동 시\n서라운드 뷰 모니터 화면 우측 탑 뷰에 탑 뷰 주\n차 가이드가 표시됩니다.'
  - excluded-nearby; bbox `[235.78, 84.57, 399.0, 115.5]`; distance=155.0pt; vgap=155.0pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='후방 탑 뷰 주차 가이드의 가로 가이드라인은\n차량으로부터 약 0.5 m, 2 m 거리를 나타냅니\n다.'

### p.390 / image 1

- image bbox: `[36.72, 107.04, 201.11, 211.91]`; candidate: 주차/뷰 버튼(1)을 누르면 서라운드 뷰 모니터
- A LLM 전달 context 필드: ['주차/뷰 버튼', '주차/뷰 버튼(1)을 누르면 서라운드 뷰 모니터\n를 켜거나 끌 수 있습니다.', '서라운드 뷰 모니터 작동', '운전자 보조']
- B LLM 전달 text (71자): '운전자 보조\n서라운드 뷰 모니터 작동\n주차/뷰 버튼\n주차/뷰 버튼(1)을 누르면 서라운드 뷰 모니터 를 켜거나 끌 수 있습니다.'
- A 결과: '주차/뷰 버튼(1)을 누르면 서라운드 뷰 모니터 작동' → '주차/뷰 버튼(1)을 누르면 서라운드 뷰 모니터' (fallback_candidate / new_tokens:작동)
- B 결과: '주차/뷰 버튼으로 서라운드 뷰 모니터 켜기 및 끄기' → '주차/뷰 버튼(1)을 누르면 서라운드 뷰 모니터' (outside_candidate_and_source:끄기,및,켜기)
- blocks (current/expanded/excluded):
  - expanded; bbox `[37.44, 93.5, 88.41, 105.72]`; distance=1.3pt; vgap=1.3pt; same_column=True; owner=True; reason=None; raw='주차/뷰 버튼'
  - expanded; bbox `[36.73, 215.02, 200.37, 244.5]`; distance=3.1pt; vgap=3.1pt; same_column=True; owner=True; reason=None; raw='2C_ParkingViewButton\n주차/뷰 버튼(1)을 누르면 서라운드 뷰 모니터\n를 켜거나 끌 수 있습니다.'
  - expanded; bbox `[37.58, 63.2, 153.09, 77.86]`; distance=29.2pt; vgap=29.2pt; same_column=True; owner=True; reason=None; raw='서라운드 뷰 모니터 작동'
  - excluded-nearby; bbox `[220.97, 63.72, 385.46, 245.03]`; distance=35.7pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw="주행 중\n주행 중에 서라운드 뷰 모니터의 전방 뷰는 다\n음의 경우 켜집니다.\n• ‘N’(중립) 또는 ‘D’(주행) 상태이고 차량 속도\n가 10 km/h 보다  빠른 경우, 주차/뷰 버튼(1)\n을 누름\n서라운드 뷰 모니터 화면의 뷰 전환 버튼(2)을\n눌러  전방 뷰 또는 와이드 뷰를 선택할 수 있습\n니다.\n주행 중 서라운드 뷰 모니터의 전방 뷰는 다음\n의 경우 꺼집니다.\n• 'P'(주차) 또는 'R'(후진)로 변속\n• 주차/뷰 버튼(1)을 누름\n• 서라운드 뷰 모니터 화면의 ŷ 버튼(3)을 누름\n• 인포테인먼트 시스템 작동 버튼(4)을 누름"
  - excluded-nearby; bbox `[37.44, 258.36, 89.4, 270.58]`; distance=46.4pt; vgap=46.4pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='전방 뷰 기능'
  - expanded; bbox `[37.58, 27.73, 80.79, 38.93]`; distance=68.1pt; vgap=68.1pt; same_column=True; owner=True; reason=None; raw='운전자 보조'
  - excluded-nearby; bbox `[220.98, 271.93, 385.36, 346.79]`; distance=95.8pt; vgap=60.0pt; same_column=False; owner=False; reason=다른 column; raw='• 주행 중 전방 뷰를 켜면 마지막으로 사용한\n뷰가 표시됩니다.\n• 주행 중 전방 뷰를 켜고 차량 속도가 10\nkm/h 보다 느려져도 전방 뷰가 유지됩니다.\n• 주행 중 전방 뷰를 켜면 모든 속도에서 전방\n탑 뷰, 전방 사이드 뷰는 비활성화 됩니다.'
  - excluded-nearby; bbox `[36.73, 378.38, 201.12, 457.86]`; distance=166.5pt; vgap=166.5pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw="2C_SVMFrontViewInfo\n서라운드 뷰 모니터의 전방 뷰 기능은 'N'(중립)\n또는 'D'(주행) 상태에서 전방 영상을 표시하\n여, 안전하게 주차할 수 있도록 도와줍니다. 전\n방 뷰에는 탑 뷰, 전방 뷰, 사이드 뷰, 3D 뷰가\n있으며, 서라운드 뷰 모니터 화면의 뷰 전환 버\n튼(2)을 눌러 원하는 뷰 모드로 전환할 수 있습\n니다."
  - excluded-nearby; bbox `[220.97, 361.69, 385.51, 503.57]`; distance=185.5pt; vgap=149.8pt; same_column=False; owner=False; reason=다른 column; raw="작동 조건\n서라운드 뷰 모니터의 전방 뷰 기능은 다음의\n조건에서 작동합니다.\n• 'R'(후진)에서 'N'(중립) 또는 'D'(주행)로 10\nkm/h 이하로 주행\n• 'P'(주차), 'N'(중립) 또는 'D'(주행) 상태이고\n차량 속도가 10 km/h 이하로 주행 중 주차/\n뷰 버튼(1)을 누름\n• 'D'(주행)로 주행 중 전방 주차 거리 경고의\n경고 발생\n(인포테인먼트 시스템의 설정 > 운전자 보조\n> 주차 안전 > 서라운드 뷰 모니터 자동 켜짐"

### p.401 / image 1

- image bbox: `[50.88, 107.04, 215.27, 211.91]`; candidate: 전방/후방 주차 거리 경고 설정 · 경고 방식
- A LLM 전달 context 필드: ["시동 'ON' 상태에서 인포테인먼트 시스템의 설\n정 > 차량 > 운전자 보조 > 경고 방식을 차례로\n선택하십시오.\n경고 음량: 경고 음량을 0-3단계로 조절할\n수 있습니다.\n경고 음량을 ‘0’으로 변경해도 경고음은 ‘1’\n로 설정했을 때의 음량으로 울립니다.", '경고 방식', '전방/후방 주차 거리 경고 설정']
- B LLM 전달 text (262자): "전방/후방 주차 거리 경고 설정\n경고 방식\n시동 'ON' 상태에서 인포테인먼트 시스템의 설 정 > 차량 > 운전자 보조 > 경고 방식을 차례로 선택하십시오. 경고 음량: 경고 음량을 0-3단계로 조절할 수 있습니다. 경고 음량을 ‘0’으로 변경해도 경고음은 ‘1’ 로 설정했을 때의 음량으로 울립니다.\n경고 방식을 변경하면 다른 운전자 보조 시 스템의 경고 방식도 같이 변경될 수 있습니 다. 고려하여 변경하십시오. 시동을 껐다가 걸어도 경고 방식 설정은 유 지됩니다."
- A 결과: '전방/후방 주차 거리 경고 설정 · 경고 방식' → '전방/후방 주차 거리 경고 설정 · 경고 방식' (llm_accepted / accepted)
- B 결과: '전방/후방 주차 거리 경고의 경고 방식 설정' → '전방/후방 주차 거리 경고의 경고 방식 설정' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[51.61, 93.5, 89.55, 105.72]`; distance=1.3pt; vgap=1.3pt; same_column=True; owner=True; reason=None; raw='경고 방식'
  - expanded; bbox `[50.91, 213.52, 215.27, 300.98]`; distance=1.6pt; vgap=1.6pt; same_column=True; owner=True; reason=None; raw="2C_WarningTypeSetInfo_4\n시동 'ON' 상태에서 인포테인먼트 시스템의 설\n정  > 차량  > 운전자 보조  > 경고 방식을 차례로\n선택하십시오.\n• 경고 음량: 경고 음량을 0-3단계로 조절할\n수 있습니다.\n경고 음량을 ‘0’으로 변경해도 경고음은 ‘1’\n로 설정했을 때의 음량으로 울립니다."
  - expanded; bbox `[51.75, 63.2, 196.65, 77.86]`; distance=29.2pt; vgap=29.2pt; same_column=True; owner=True; reason=None; raw='전방/후방 주차 거리 경고 설정'
  - excluded-nearby; bbox `[235.86, 93.5, 294.02, 105.72]`; distance=38.4pt; vgap=1.3pt; same_column=False; owner=False; reason=다른 column; raw='주차 안전 버튼'
  - excluded-nearby; bbox `[235.16, 215.92, 398.96, 315.97]`; distance=39.8pt; vgap=4.0pt; same_column=False; owner=False; reason=다른 column; raw='2C_ParkingSafetyButton\n주차 안전 버튼(\n)을 누르면 주차 거리 경고 기\n능을 켜거나 끌 수 있습니다. \n• 기능이 꺼져있는 상태(버튼 내 표시등 꺼져\n있음)에서 ‘R’(후진)로 변속하면 자동으로 기\n능이 켜집니다. \n• ‘R’(후진) 상태에서는 안전한 주차를 위해 주\n차 안전 버튼(\n)을 눌러도 기능이 꺼지지 않\n습니다.'
  - excluded-nearby; bbox `[236.0, 63.2, 329.91, 77.86]`; distance=66.5pt; vgap=29.2pt; same_column=False; owner=False; reason=다른 column; raw='주차 거리 경고 작동'
  - expanded; bbox `[50.91, 327.93, 214.67, 387.8]`; distance=116.0pt; vgap=116.0pt; same_column=True; owner=True; reason=None; raw='• 경고 방식을 변경하면 다른 운전자 보조 시\n스템의 경고 방식도 같이 변경될 수 있습니\n다. 고려하여 변경하십시오.\n• 시동을 껐다가 걸어도 경고 방식 설정은 유\n지됩니다.'
  - excluded-nearby; bbox `[235.16, 329.83, 399.04, 453.92]`; distance=153.7pt; vgap=117.9pt; same_column=False; owner=False; reason=다른 column; raw="전방 주차 거리 경고 \n전방 주차 거리 경고 기능은 다음의 조건에서\n켜집니다.\n• 'R'(후진)에서 'D'(주행)로 변속\n• 'D'(주행)에서 주차 안전 버튼(\n) 을 눌러서\n표시등을 켬\n• 주차 안전 버튼(\n) 표시등이 켜진 상태에서\n‘D’(주행)로 변속\n• 주차 거리 경고 자동 켜짐을 선택한 상태에서\n‘D’(주행)로 변속"
  - excluded-nearby; bbox `[50.86, 406.5, 214.73, 460.62]`; distance=194.6pt; vgap=194.6pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='주차 거리 경고 자동 켜짐 \n저속에서 주차 거리 경고가 항상 켜져 있도록\n설정 할 수 있습니다. 시동 ‘ON’ 상태에서 인포\n테인먼트 시스템의 설정 > 차량 > 운전자 보조\n> 주차 안전 > 주차 거리 경고 자동 켜짐을 차례'

### p.406 / image 6

- image bbox: `[83.76, 184.07, 103.68, 203.99]`; candidate: 삐-삐-삐
- A LLM 전달 context 필드: ['60 cm\n삐-삐-삐-']
- B LLM 전달 text (12자): '60 cm 삐-삐-삐-'
- A 결과: '삐-삐-삐' → '삐-삐-삐' (llm_accepted / accepted)
- B 결과: '60 cm 거리의 삐-삐-삐- 경고음' → '삐-삐-삐' (outside_candidate_and_source:거리의,경고음)
- blocks (current/expanded/excluded):
  - expanded; bbox `[42.01, 182.55, 195.97, 204.36]`; distance=0.0pt; vgap=0.0pt; same_column=True; owner=True; reason=None; raw='30 – \n60 cm\n삐-삐-삐-'
  - excluded-nearby; bbox `[42.21, 213.17, 67.48, 234.98]`; distance=38.5pt; vgap=9.2pt; same_column=False; owner=True; reason=다른 column; raw='30 cm \n이내'
  - excluded-nearby; bbox `[36.73, 243.23, 200.53, 381.28]`; distance=39.2pt; vgap=39.2pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='• 각 초음파센서가 사람 또는 물체를 감지하면\n클러스터 표시창 또는 인포테인먼트 시스템\n화면에 거리별 표시등이 표시되고 경고음이\n울립니다.\n• 둘 이상의 영역을 동시에 경고하는 경우 더\n가까운 물체가 있는 영역의 경고음이 울립니\n다.\n• 물체와의 거리가 60 cm 이상일 때 전방 외\n측 단독 경고 시에는 클러스터에 표시하지\n않습니다.\n• 경고 표시 형상은 실제 차량과 다를 수 있습\n니다.'
  - excluded-nearby; bbox `[40.77, 141.27, 67.21, 163.08]`; distance=50.8pt; vgap=21.0pt; same_column=False; owner=False; reason=다른 column; raw='60 – \n120 cm'
  - excluded-nearby; bbox `[77.5, 98.28, 190.28, 117.34]`; distance=66.7pt; vgap=66.7pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='경고음\n클러스터\n인포테인'
  - excluded-nearby; bbox `[97.87, 84.28, 130.16, 94.6]`; distance=89.5pt; vgap=89.5pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='경고 표시'
  - excluded-nearby; bbox `[41.68, 93.03, 66.33, 113.85]`; distance=101.6pt; vgap=70.2pt; same_column=False; owner=False; reason=다른 column; raw='물체와\n의 거리'
  - excluded-nearby; bbox `[127.89, 112.28, 142.85, 122.59]`; distance=105.1pt; vgap=61.5pt; same_column=False; owner=False; reason=다른 column; raw='먼트'
  - excluded-nearby; bbox `[36.72, 63.72, 110.34, 74.64]`; distance=109.4pt; vgap=109.4pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='경고 표시 및 경고음'
  - excluded-nearby; bbox `[166.27, 213.17, 191.67, 223.49]`; distance=121.8pt; vgap=9.2pt; same_column=False; owner=False; reason=다른 column; raw='삐(연속'
  - excluded-nearby; bbox `[165.1, 141.26, 192.21, 163.07]`; distance=131.6pt; vgap=21.0pt; same_column=False; owner=False; reason=다른 column; raw='---\n(전방 내'
  - excluded-nearby; bbox `[173.92, 164.24, 184.58, 174.56]`; distance=136.0pt; vgap=9.5pt; same_column=False; owner=False; reason=다른 column; raw='측)'
  - excluded-nearby; bbox `[173.92, 224.66, 184.58, 234.98]`; distance=147.1pt; vgap=20.7pt; same_column=False; owner=False; reason=다른 column; raw='음)'
  - excluded-nearby; bbox `[37.58, 27.73, 80.79, 38.93]`; distance=150.5pt; vgap=145.1pt; same_column=False; owner=False; reason=다른 column; raw='운전자 보조'
  - excluded-nearby; bbox `[166.36, 129.77, 191.54, 140.09]`; distance=156.8pt; vgap=44.0pt; same_column=False; owner=False; reason=다른 column; raw='삐---삐'
  - excluded-nearby; bbox `[36.73, 395.14, 200.46, 519.22]`; distance=191.1pt; vgap=191.1pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw="측방 주차 거리 경고\n측방 주차 거리 경고 기능은 다음의 조건에서\n켜집니다.\n• 'R'(후진)로 변속 \n• 'D'(주행)에서 주차 안전 버튼(\n) 을 눌러서\n표시등을 켬\n• 주차 안전 버튼(\n) 표시등이 켜진 상태에서\n'D'(주행)로 변속\n• 주차 거리 경고 자동 켜짐을 선택한 상태에서\n'D'(주행)로 변속"

### p.406 / image 8

- image bbox: `[83.76, 214.55, 103.68, 234.47]`; candidate: 삐-삐-삐
- A LLM 전달 context 필드: ['각 초음파센서가 사람 또는 물체를 감지하면\n클러스터 표시창 또는 인포테인먼트 시스템\n화면에 거리별 표시등이 표시되고 경고음이\n울립니다.\n둘 이상의 영역을 동시에 경고하는 경우 더\n가까운 물체가 있는 영역의 경고음이 울립니\n다.\n물체와의 거리가 60 cm 이상일 때 전방 외\n측 단독 경고 시에는 클러스터에 표시하지\n않습니다.\n경고 표시 형상은 실제 차량과 다를 수 있습\n니다.', '60 cm\n삐-삐-삐-']
- B LLM 전달 text (223자): '60 cm 삐-삐-삐-\n각 초음파센서가 사람 또는 물체를 감지하면 클러스터 표시창 또는 인포테인먼트 시스템 화면에 거리별 표시등이 표시되고 경고음이 울립니다. 둘 이상의 영역을 동시에 경고하는 경우 더 가까운 물체가 있는 영역의 경고음이 울립니 다. 물체와의 거리가 60 cm 이상일 때 전방 외 측 단독 경고 시에는 클러스터에 표시하지 않습니다. 경고 표시 형상은 실제 차량과 다를 수 있습 니다.'
- A 결과: '삐-삐-삐' → '삐-삐-삐' (llm_accepted / accepted)
- B 결과: '60 cm 거리 경고음' → '60 cm 거리 경고음' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[36.73, 243.23, 200.53, 381.28]`; distance=8.8pt; vgap=8.8pt; same_column=True; owner=True; reason=None; raw='• 각 초음파센서가 사람 또는 물체를 감지하면\n클러스터 표시창 또는 인포테인먼트 시스템\n화면에 거리별 표시등이 표시되고 경고음이\n울립니다.\n• 둘 이상의 영역을 동시에 경고하는 경우 더\n가까운 물체가 있는 영역의 경고음이 울립니\n다.\n• 물체와의 거리가 60 cm 이상일 때 전방 외\n측 단독 경고 시에는 클러스터에 표시하지\n않습니다.\n• 경고 표시 형상은 실제 차량과 다를 수 있습\n니다.'
  - expanded; bbox `[42.01, 182.55, 195.97, 204.36]`; distance=10.2pt; vgap=10.2pt; same_column=True; owner=True; reason=None; raw='30 – \n60 cm\n삐-삐-삐-'
  - excluded-nearby; bbox `[42.21, 213.17, 67.48, 234.98]`; distance=29.3pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='30 cm \n이내'
  - excluded-nearby; bbox `[40.77, 141.27, 67.21, 163.08]`; distance=81.3pt; vgap=51.5pt; same_column=False; owner=False; reason=다른 column; raw='60 – \n120 cm'
  - excluded-nearby; bbox `[77.5, 98.28, 190.28, 117.34]`; distance=97.2pt; vgap=97.2pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='경고음\n클러스터\n인포테인'
  - excluded-nearby; bbox `[166.27, 213.17, 191.67, 223.49]`; distance=112.7pt; vgap=0.0pt; same_column=False; owner=False; reason=다른 column; raw='삐(연속'
  - excluded-nearby; bbox `[97.87, 84.28, 130.16, 94.6]`; distance=120.0pt; vgap=120.0pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='경고 표시'
  - excluded-nearby; bbox `[173.92, 224.66, 184.58, 234.98]`; distance=126.4pt; vgap=0.0pt; same_column=False; owner=False; reason=다른 column; raw='음)'
  - excluded-nearby; bbox `[41.68, 93.03, 66.33, 113.85]`; distance=132.1pt; vgap=100.7pt; same_column=False; owner=False; reason=다른 column; raw='물체와\n의 거리'
  - excluded-nearby; bbox `[127.89, 112.28, 142.85, 122.59]`; distance=135.5pt; vgap=92.0pt; same_column=False; owner=False; reason=다른 column; raw='먼트'
  - excluded-nearby; bbox `[36.72, 63.72, 110.34, 74.64]`; distance=139.9pt; vgap=139.9pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='경고 표시 및 경고음'
  - excluded-nearby; bbox `[36.73, 395.14, 200.46, 519.22]`; distance=160.7pt; vgap=160.7pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw="측방 주차 거리 경고\n측방 주차 거리 경고 기능은 다음의 조건에서\n켜집니다.\n• 'R'(후진)로 변속 \n• 'D'(주행)에서 주차 안전 버튼(\n) 을 눌러서\n표시등을 켬\n• 주차 안전 버튼(\n) 표시등이 켜진 상태에서\n'D'(주행)로 변속\n• 주차 거리 경고 자동 켜짐을 선택한 상태에서\n'D'(주행)로 변속"
  - excluded-nearby; bbox `[165.1, 141.26, 192.21, 163.07]`; distance=162.0pt; vgap=51.5pt; same_column=False; owner=False; reason=다른 column; raw='---\n(전방 내'
  - excluded-nearby; bbox `[173.92, 164.24, 184.58, 174.56]`; distance=166.4pt; vgap=40.0pt; same_column=False; owner=False; reason=다른 column; raw='측)'
  - excluded-nearby; bbox `[37.58, 27.73, 80.79, 38.93]`; distance=181.0pt; vgap=175.6pt; same_column=False; owner=False; reason=다른 column; raw='운전자 보조'
  - excluded-nearby; bbox `[166.36, 129.77, 191.54, 140.09]`; distance=187.3pt; vgap=74.5pt; same_column=False; owner=False; reason=다른 column; raw='삐---삐'

### p.407 / image 8

- image bbox: `[234.95, 358.54, 399.58, 463.66]`; candidate: 인식 센서 가림
- A LLM 전달 context 필드: ['클러스터 표시창에 작동 제한 경고가 표시되면\n초음파센서 표면이 깨끗한지 확인하십시오. 초\n음파센서 표면에 눈, 비, 이물질 등이 묻으면 주\n차 거리 경고 기능이 정상적으로 작동하지 않을\n수 있습니다. 항상 초음파센서 표면을 깨끗하\n게 유지하십시오.\n인식 센서 가림 경고 내용은 클러스터의 뷰\n모드 중 유틸리티 정보 뷰의 서비스 메시지\n에서 확인할 수 있습니다.', '인식 센서 가림', '리티 정보 뷰의 서비스 메시지에서 확인할\n수 있습니다.']
- B LLM 전달 text (241자): '리티 정보 뷰의 서비스 메시지에서 확인할 수 있습니다.\n인식 센서 가림\n클러스터 표시창에 작동 제한 경고가 표시되면 초음파센서 표면이 깨끗한지 확인하십시오. 초 음파센서 표면에 눈, 비, 이물질 등이 묻으면 주 차 거리 경고 기능이 정상적으로 작동하지 않을 수 있습니다. 항상 초음파센서 표면을 깨끗하 게 유지하십시오. 인식 센서 가림 경고 내용은 클러스터의 뷰 모드 중 유틸리티 정보 뷰의 서비스 메시지 에서 확인할 수 있습니다.'
- A 결과: '인식 센서 가림' → '인식 센서 가림' (llm_accepted / accepted)
- B 결과: '인식 센서 가림 경고' → '인식 센서 가림 경고' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[235.86, 345.06, 294.02, 357.28]`; distance=1.3pt; vgap=1.3pt; same_column=True; owner=True; reason=None; raw='인식 센서 가림'
  - expanded; bbox `[235.16, 465.32, 399.01, 569.77]`; distance=1.7pt; vgap=1.7pt; same_column=True; owner=True; reason=None; raw='2C_PDWDisabledInfo\n클러스터 표시창에 작동 제한 경고가 표시되면\n초음파센서 표면이 깨끗한지 확인하십시오. 초\n음파센서 표면에 눈, 비, 이물질 등이 묻으면 주\n차 거리 경고 기능이 정상적으로 작동하지 않을\n수 있습니다. 항상 초음파센서 표면을 깨끗하\n게 유지하십시오.\n• 인식 센서 가림 경고 내용은 클러스터의 뷰\n모드 중 유틸리티 정보 뷰의 서비스 메시지\n에서 확인할 수 있습니다.'
  - expanded; bbox `[252.72, 310.28, 398.98, 331.21]`; distance=27.3pt; vgap=27.3pt; same_column=True; owner=True; reason=None; raw='리티 정보 뷰의 서비스 메시지에서 확인할\n수 있습니다.'
  - excluded-nearby; bbox `[50.91, 339.52, 214.71, 442.59]`; distance=36.4pt; vgap=0.0pt; same_column=False; owner=False; reason=다른 column; raw='• 각 초음파센서가 사람 또는 물체를 감지하면\n클러스터 표시창 또는 인포테인먼트 시스템\n화면에 거리별 표시등이 표시되고 경고음이\n울립니다.\n• 둘 이상의 영역을 동시에 경고하는 경우 더\n가까운 물체가 있는 영역의 경고음이 울립니\n다.\n• 경고 표시 형상은 실제 차량과 다를 수 있습\n니다.'
  - excluded-nearby; bbox `[235.16, 213.76, 398.95, 311.21]`; distance=47.3pt; vgap=47.3pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='2C_ForwardSafetyMalfunctionInfo\n다음과 같은 현상이 나타나면 초음파센서가 손\n상되었는지, 외부 물체에 의해 가려졌는지 등\n을 먼저 확인하십시오. 기능에 이상이 있는 것\n으로 판단되면 당사 직영 하이테크센터나 블루\n핸즈에서 점검을 받으십시오.\n• 기능에 이상이 있으면 클러스터 표시창에 시\n스템 점검 경고 표시\n- 경고 내용은 클러스터의 뷰 모드 중 유틸'
  - excluded-nearby; bbox `[184.21, 309.48, 209.6, 319.8]`; distance=84.4pt; vgap=38.7pt; same_column=False; owner=False; reason=다른 column; raw='삐(연속'
  - excluded-nearby; bbox `[191.86, 320.97, 202.51, 331.29]`; distance=85.6pt; vgap=27.3pt; same_column=False; owner=False; reason=다른 column; raw='음)'
  - excluded-nearby; bbox `[191.52, 290.35, 202.84, 300.67]`; distance=115.7pt; vgap=57.9pt; same_column=False; owner=False; reason=다른 column; raw='삐-'
  - excluded-nearby; bbox `[185.99, 278.86, 208.36, 289.18]`; distance=117.2pt; vgap=69.4pt; same_column=False; owner=False; reason=다른 column; raw='삐-삐-'
  - excluded-nearby; bbox `[184.28, 248.24, 209.47, 258.56]`; distance=145.8pt; vgap=100.0pt; same_column=False; owner=False; reason=다른 column; raw='삐---삐'
  - excluded-nearby; bbox `[95.96, 215.94, 208.2, 235.0]`; distance=171.7pt; vgap=123.5pt; same_column=False; owner=False; reason=다른 column; raw='경고음\n클러스터\n인포테인먼'
  - excluded-nearby; bbox `[51.52, 141.55, 215.27, 162.48]`; distance=231.5pt; vgap=196.1pt; same_column=False; owner=False; reason=다른 column; raw='후방 주차 거리 경고는 차량 속도가 10 km/h\n미만일 때만 작동합니다.'

### p.412 / image 1

- image bbox: `[36.72, 84.96, 201.11, 189.83]`; candidate: 운전자 보조
- A LLM 전달 context 필드: ['주차 충돌방지 보조가 작동 중일 때 기능 이상\n이나 초음파센서의 가림이 발생하면 대상 방향\n에 통합 경고등( )이 표시 됩니다. 클러스터 표\n시창 중 유틸리티 정보 뷰의 서비스 메시지에서\n확인할 수 있습니다.', '운전자 보조']
- B LLM 전달 text (123자): '운전자 보조\n주차 충돌방지 보조가 작동 중일 때 기능 이상 이나 초음파센서의 가림이 발생하면 대상 방향 에 통합 경고등( )이 표시 됩니다. 클러스터 표 시창 중 유틸리티 정보 뷰의 서비스 메시지에서 확인할 수 있습니다.'
- A 결과: '운전자 보조' → '운전자 보조' (llm_accepted / accepted)
- B 결과: '운전자 보조 통합 경고등' → '운전자 보조 통합 경고등' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[36.73, 191.39, 200.57, 250.87]`; distance=1.6pt; vgap=1.6pt; same_column=True; owner=True; reason=None; raw='2C_PCAInfo\n주차 충돌방지 보조가 작동 중일 때 기능 이상\n이나 초음파센서의 가림이 발생하면 대상 방향\n에 통합 경고등( )이 표시 됩니다. 클러스터 표\n시창 중 유틸리티 정보 뷰의 서비스 메시지에서\n확인할 수 있습니다.'
  - expanded; bbox `[37.58, 27.73, 80.79, 38.93]`; distance=46.0pt; vgap=46.0pt; same_column=True; owner=True; reason=None; raw='운전자 보조'
  - excluded-nearby; bbox `[228.98, 168.7, 384.4, 212.62]`; distance=50.2pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='소리, 트럭 에어 브레이크 소리 등 과도한\n소음을 발생하는 물체가 차량 주변에 있는\n경우\n- 유사한 주파수를 사용하는 초음파센서가'
  - excluded-nearby; bbox `[229.03, 145.71, 384.36, 169.63]`; distance=50.3pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='퍼에 수직으로 부는 경우\n- 차량 경적 소리, 시끄러운 오토바이 엔진'
  - excluded-nearby; bbox `[229.08, 96.72, 384.34, 146.64]`; distance=50.3pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='하여 후방 영상이 잘 보이지 않는 경우\n- 주변이 너무 밝거나 너무 어두운 경우\n- 차량 외부의 기온이 높거나 낮은 경우\n- 바람이 강하게 불거나(20 km/h 이상) 범'
  - excluded-nearby; bbox `[229.23, 73.73, 384.47, 97.65]`; distance=50.6pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='을 장착한 경우\n- 역광이나 폭우, 안개, 눈 등의 악천후로 인'
  - excluded-nearby; bbox `[220.98, 211.65, 384.75, 276.55]`; distance=57.6pt; vgap=21.8pt; same_column=False; owner=True; reason=다른 column; raw='근처에 있는 경우\n- 도로가 미끄럽거나 기울어진 경우\n• 보행자나 물체 문제의 경우\n- 보행자가 인식되기 어려운 상태인 경우\n- 보행자가 차량과 다른 높이의 지면에 있는'
  - excluded-nearby; bbox `[229.28, 63.73, 385.15, 74.65]`; distance=61.0pt; vgap=10.3pt; same_column=False; owner=True; reason=다른 column; raw='- 차량 후방에 짐칸(트레일러 또는 캐리어)'
  - excluded-nearby; bbox `[36.73, 269.55, 200.52, 331.66]`; distance=79.7pt; vgap=79.7pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='작동 제한 사항\n다음과 같은 경우에는 주차 충돌방지 보조의 성\n능이 저하되거나 오작동 할 수 있습니다.\n• 차량 문제의 경우\n- 범퍼에 인가 받지 않은 장비 또는 액세서'
  - excluded-nearby; bbox `[229.4, 275.63, 384.78, 299.55]`; distance=136.7pt; vgap=85.8pt; same_column=False; owner=True; reason=다른 column; raw='경우 \n- 전방위 카메라 영상에서 보행자와 배경이'
  - excluded-nearby; bbox `[45.19, 330.73, 200.5, 367.65]`; distance=140.9pt; vgap=140.9pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='리를 설치한 경우\n- 브레이크를 튜닝한 경우\n- 사고나 다른 원인으로 차량의 상태가 불안'
  - excluded-nearby; bbox `[229.3, 298.62, 384.67, 348.54]`; distance=159.5pt; vgap=108.8pt; same_column=False; owner=True; reason=다른 column; raw='잘 구분 되지 않는 경우\n- 보행자가 차량 후방 가장자리에 있는 경우\n- 보행자가 똑바로 서 있지 않은 경우\n- 보행자가 인식하기에 너무 크거나 작은 경'
  - excluded-nearby; bbox `[45.15, 366.72, 200.28, 390.65]`; distance=176.9pt; vgap=176.9pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='정한 경우\n- 범퍼 높이 또는 초음파센서 장착 위치가'
  - excluded-nearby; bbox `[45.12, 389.72, 200.44, 413.64]`; distance=199.9pt; vgap=199.9pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='달라진 경우\n- 타이어 공기압 이상, 화물칸의 과다 적재'
  - excluded-nearby; bbox `[229.24, 347.61, 384.58, 384.53]`; distance=208.4pt; vgap=157.8pt; same_column=False; owner=True; reason=다른 column; raw='우\n- 보행자가 인식하기 어려운 복장을 한 경우\n- 보행자가 초음파를 잘 반사하지 않는 옷을'
  - excluded-nearby; bbox `[45.08, 412.71, 200.33, 436.64]`; distance=222.9pt; vgap=222.9pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='등으로 차고가 심하게 변할 경우\n- 광각 카메라 또는 초음파센서가 파손된 경'
  - excluded-nearby; bbox `[229.21, 383.6, 384.58, 407.52]`; distance=244.3pt; vgap=193.8pt; same_column=False; owner=True; reason=다른 column; raw='입은 경우\n- 물체가 크기, 두께, 높이, 형상으로 인하여'
  - excluded-nearby; bbox `[229.05, 406.59, 385.04, 473.51]`; distance=267.0pt; vgap=216.8pt; same_column=False; owner=True; reason=다른 column; raw='초음파를 잘 반사하지 않는 경우(높이가\n낮은 장애물, 폭이 좁은 장애물, 원형 기둥,\n작은 기둥, 사각 기둥의 모서리, 덤불, 카\n트, 벽의 가장자리 등)\n- 보행자나 물체가 빠르게 이동하는 경우\n- 보행자나 물체가 차량의 주변에 매우 가까'

### p.424 / image 2

- image bbox: `[36.72, 291.35, 201.11, 410.38]`; candidate: 후측방 레이더
- A LLM 전달 context 필드: ['후측방 레이더']
- B LLM 전달 text (7자): '후측방 레이더'
- A 결과: '후측방 레이더' → '후측방 레이더' (llm_accepted / accepted)
- B 결과: '후측방 레이더' → '후측방 레이더' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[37.58, 261.2, 104.56, 275.87]`; distance=15.5pt; vgap=15.5pt; same_column=True; owner=True; reason=None; raw='후측방 레이더'
  - excluded-nearby; bbox `[37.58, 101.19, 93.76, 115.86]`; distance=175.5pt; vgap=175.5pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='전방 레이더'
  - excluded-nearby; bbox `[37.72, 62.89, 90.54, 80.0]`; distance=211.3pt; vgap=211.3pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='단품 인증'

### p.476 / image 3

- image bbox: `[36.72, 315.59, 107.52, 386.38]`; candidate: 배터리 내부에는 점화율이 매우 높은 수소가 항
- A LLM 전달 context 필드: ['배터리 내부에는 점화율이 매우 높은 수소가 항\n상 존재하여 불꽃이 점화되면 폭발할 수 있습니\n다.', '배터리가 어린이의 손에 닿지 않게 하십시오.']
- B LLM 전달 text (79자): '배터리 내부에는 점화율이 매우 높은 수소가 항 상 존재하여 불꽃이 점화되면 폭발할 수 있습니 다.\n배터리가 어린이의 손에 닿지 않게 하십시오.'
- A 결과: '배터리 내부에는 점화율이 매우 높은 수소가 항상 존재합니다.' → '배터리 내부에는 점화율이 매우 높은 수소가 항' (fallback_candidate / new_tokens:존재합니다,항상)
- B 결과: '배터리 내부 수소 폭발 경고' → '배터리 내부에는 점화율이 매우 높은 수소가 항' (outside_candidate_and_source:경고)
- blocks (current/expanded/excluded):
  - expanded; bbox `[37.37, 282.28, 200.52, 313.2]`; distance=2.4pt; vgap=2.4pt; same_column=True; owner=True; reason=None; raw='배터리 내부에는 점화율이 매우 높은 수소가 항\n상 존재하여 불꽃이 점화되면 폭발할 수 있습니\n다.'
  - expanded; bbox `[37.37, 396.56, 198.48, 407.49]`; distance=10.2pt; vgap=10.2pt; same_column=True; owner=True; reason=None; raw='배터리가 어린이의 손에 닿지 않게 하십시오.'
  - excluded-nearby; bbox `[37.34, 168.0, 200.46, 198.92]`; distance=116.7pt; vgap=116.7pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='담뱃불과 모든 기타 화염 또는 불꽃을 멀리하십\n시오. 배터리 셀에 인화성이 높은 수소 가스가\n있어서 불이 붙으면 폭발할 수 있습니다.'
  - excluded-nearby; bbox `[37.36, 63.72, 200.51, 84.64]`; distance=230.9pt; vgap=230.9pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='배터리를 다룰 때 항상 다음의 지시 사항을 따\n르십시오.'

### p.484 / image 1

- image bbox: `[36.72, 198.95, 201.11, 303.83]`; candidate: 블레이드 타입
- A LLM 전달 context 필드: ['블레이드 타입', '카트리지 타입', '블레이드 타입/카트리지 타입 퓨즈\n1. 시동을 끄십시오.\n2. 모든 전기 장치 스위치를 끄십시오.\n3. 잠금쇠를 누른 후 커버를 분리하십시오.\n4. 작동하지 않는 전기 장치의 퓨즈를 점검하여\n단선 되었으면 엔진룸 퓨즈 박스에 설치된\n퓨즈 교체용 클립(퓨즈 뽑개)으로 제거하십\n시오.']
- B LLM 전달 text (188자): '정기 점검\n엔진룸 퓨즈박스\n블레이드 타입/카트리지 타입 퓨즈 1. 시동을 끄십시오. 2. 모든 전기 장치 스위치를 끄십시오. 3. 잠금쇠를 누른 후 커버를 분리하십시오. 4. 작동하지 않는 전기 장치의 퓨즈를 점검하여 단선 되었으면 엔진룸 퓨즈 박스에 설치된 퓨즈 교체용 클립(퓨즈 뽑개)으로 제거하십 시오.\n블레이드 타입\n카트리지 타입'
- A 결과: '블레이드 타입' → '블레이드 타입' (llm_accepted / accepted)
- B 결과: '블레이드 타입 퓨즈' → '블레이드 타입 퓨즈' (source_supported)
- blocks (current/expanded/excluded):
  - expanded; bbox `[99.36, 188.96, 138.46, 197.46]`; distance=1.5pt; vgap=1.5pt; same_column=True; owner=True; reason=None; raw='블레이드 타입'
  - expanded; bbox `[36.73, 306.98, 138.46, 324.33]`; distance=3.2pt; vgap=3.2pt; same_column=True; owner=True; reason=None; raw='2C_EngineRoomFuseReplacement_2\n카트리지 타입'
  - expanded; bbox `[36.64, 93.5, 200.34, 186.61]`; distance=12.3pt; vgap=12.3pt; same_column=True; owner=True; reason=None; raw='블레이드 타입/카트리지 타입 퓨즈\n1. 시동을 끄십시오. \n2. 모든 전기 장치 스위치를 끄십시오.\n3. 잠금쇠를 누른 후 커버를 분리하십시오.\n4. 작동하지 않는 전기 장치의 퓨즈를 점검하여\n단선 되었으면 엔진룸 퓨즈 박스에 설치된\n퓨즈 교체용 클립(퓨즈 뽑개)으로 제거하십\n시오.'
  - excluded-nearby; bbox `[220.98, 183.53, 384.83, 253.01]`; distance=35.8pt; vgap=0.0pt; same_column=False; owner=False; reason=다른 column; raw='2C_MultiTypeMainFuse\n멀티 타입 퓨즈는 볼트나 너트로 고정되어 있습\n니다. 임의로 분해 또는 조립하지 말고 당사 직\n영 하이테크센터나 블루핸즈에서 정비를 받으\n십시오. 불완전한 체결 및 잘못된 조립 토크는\n전자 장치의 오작동이나 화재를 일으킬 수 있습\n니다.'
  - excluded-nearby; bbox `[221.57, 281.91, 384.74, 322.83]`; distance=36.8pt; vgap=0.0pt; same_column=False; owner=True; reason=다른 column; raw='엔진룸 퓨즈 박스 커버는 “딸깍” 소리가 날 때\n까지 닫아 확실하게 장착하십시오. 커버가 바\n르게 장착되지 않으면 수분이 유입되어 전자 장\n치 작동에 이상이 생길 수 있습니다.'
  - expanded; bbox `[37.58, 63.2, 115.36, 77.86]`; distance=121.1pt; vgap=121.1pt; same_column=True; owner=True; reason=None; raw='엔진룸 퓨즈박스'
  - excluded-nearby; bbox `[36.7, 433.86, 200.49, 519.32]`; distance=130.0pt; vgap=130.0pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='2C_EngineRoomFuseReplacement_3\n5. 동일한 용량의 예비 퓨즈를 손으로 단단히\n꽂으십시오.\n6. 커버를 다시 장착하십시오.\n블레이드 타입의 예비 퓨즈는 엔진룸 퓨즈\n박스에 일부 설치되어 있으나, 없는 경우에\n는 차량 작동과 관계 없는 장치(오디오 등)에\n꽂힌 동일 용량의 퓨즈를 사용하십시오.'
  - expanded; bbox `[37.58, 27.73, 72.63, 38.93]`; distance=160.0pt; vgap=160.0pt; same_column=True; owner=True; reason=None; raw='정기 점검'
  - excluded-nearby; bbox `[221.69, 63.51, 299.83, 75.73]`; distance=160.3pt; vgap=123.2pt; same_column=False; owner=False; reason=다른 column; raw='멀티 타입 메인 퓨즈'

### p.490 / image 4

- image bbox: `[221.03, 96.96, 385.42, 201.83]`; candidate: 선바이저 램프/글로브 박스 램프/트렁크
- A LLM 전달 context 필드: ['선바이저 램프', '글로브 박스 램프', '선바이저 램프/글로브 박스 램프/트렁크\n룸 램프(벌브 타입)']
- B LLM 전달 text (51자): '선바이저 램프/글로브 박스 램프/트렁크 룸 램프(벌브 타입)\n선바이저 램프\n글로브 박스 램프'
- A 결과: '선바이저 램프/글로브 박스 램프/트렁크' → '선바이저 램프/글로브 박스 램프/트렁크' (llm_accepted / accepted)
- B 결과: '선바이저 램프 및 글로브 박스 램프' → '선바이저 램프/글로브 박스 램프/트렁크' (outside_candidate_and_source:및)
- blocks (current/expanded/excluded):
  - expanded; bbox `[283.61, 87.0, 322.95, 95.5]`; distance=1.5pt; vgap=1.5pt; same_column=True; owner=True; reason=None; raw='선바이저 램프'
  - expanded; bbox `[220.98, 205.02, 326.68, 222.37]`; distance=3.2pt; vgap=3.2pt; same_column=True; owner=True; reason=None; raw='2C_SunvisorLampChange\n글로브 박스 램프'
  - expanded; bbox `[221.69, 63.51, 383.41, 85.72]`; distance=11.2pt; vgap=11.2pt; same_column=True; owner=True; reason=None; raw='선바이저 램프/글로브 박스 램프/트렁크 \n룸 램프(벌브 타입)'
  - excluded-nearby; bbox `[37.44, 93.5, 196.59, 105.72]`; distance=44.0pt; vgap=0.0pt; same_column=False; owner=False; reason=다른 column; raw='맵 램프/룸 램프/퍼스널 램프(LED 타입)'
  - excluded-nearby; bbox `[220.98, 331.89, 323.53, 349.24]`; distance=130.1pt; vgap=130.1pt; same_column=True; owner=False; reason=다른 이미지에 더 가까움; raw='2C_GloveBoxLamp\n트렁크 룸 램프'

## 대표 사례 평가

사람 검토는 생성 description과 candidate/source 원문을 대조한 표본 수준 판정이다. 자동 source-grounded 검사는 어휘 근거를 확인하며 단어 간 관계나 이미지 내용의 진실성을 완전히 증명하지 않는다.


## 수동 비교 결과 및 해석

### A/B 요약

| 지표 | A: 기존 문맥 + 기존 candidate-only 검사 | B: 확장 문맥 + candidate/source 검사 |
|---|---:|---:|
| 동일 평가셋 | seed 20261004, 100건 | 동일 100건 |
| 규칙 후보 None / skip | 43 | 43 |
| LLM 대상 | 57 | 57 |
| 평균 제출 문맥 길이 | 158.8자 | 181.5자 |
| 문맥 길이 증가 | - | +22.7자 (+14.3%) |
| 평균 API input token/대상 | 194.7 | 207.5 |
| 검사 통과 / 채택 | 39 | 44 |
| fallback | 18 | 13 |
| 채택 후 candidate와 동일 | 30 | 8 |
| 채택 후 실제 문구 변경 | 9 | 36 |
| 명확한 개선(변경 문구 수동 판정) | 3 | 25 |
| 의미가 거의 같은 표현/형식 변경 | 6 | 7 |
| 정보 손실 우려 변경 | 확인된 사례 없음 | 4 |
| API input / output tokens | 11,096 / 1,324 | 11,829 / 1,523 |
| API 요청 / 실행 시간 | 6 / 14.907초 | 6 / 16.170초 |
| API 오류 / 재시도 | 0 / 0 | 0 / 0 |

토큰/시간은 실제 API 사용량이다. 평균 input token은 프롬프트와 JSON 구조를 포함한 전체 요청 사용량을 57건으로 나눈 값이며, 문맥 텍스트만의 token 수는 분리하지 못했다. tokenizer 데이터 다운로드가 불가능해 임의 산출하지 않았다.

수동 품질 판정은 문구가 실제로 바뀐 36건에 대한 표본 수준 검토다. “명확한 개선”은 candidate보다 검색 metadata로 구체적이거나 읽기 쉬워진 사례를 말하며, 이미지 정합성이나 정답률을 자동 입증하지 않는다. 정보 손실 우려 4건은 p.261/i1, p.325/i1, p.354/i3에서 그림 식별자 `[B]`가 빠진 경우와 p.271/i1에서 정차 시간/안전 장소 정보가 축약된 경우다.

### 대표 사례

#### 문맥이 늘어 유용하게 구체화 — p.174 / image 2

- [규칙 후보] `아닌 다른 부분을 누르면 연료 주입구 커버`
- [기존 주변 원문] `아닌 다른 부분을 누르면 연료 주입구 커버가 열리지 않을 수 있음`처럼 후보 중심의 짧은 문맥
- [확대된 주변 원문] 연료 주입구 커버의 오른쪽 끝 중앙 부분을 누르는 조작 설명
- [기존 LLM 결과] `다른 부분을 누르면 연료 주입구 커버가 열리지 않을 수 있음` — candidate 밖 표현이라는 이유로 기존 검사에서 fallback
- [새 LLM 결과] `연료 주입구 커버 오른쪽 끝 중앙 부분`
- [채택/거부 이유] 확대 원문에 위치 근거가 있어 B에서 source-supported로 채택. 후보에 없다는 이유만으로 버리던 문구를 원문 근거로 판단할 수 있었다.

#### 확장 문맥에 별도 주제가 섞임 — p.69 / image 1

- [규칙 후보] `어린이 보조 좌석 설치 금지`
- [기존 주변 원문] 어린이 보조 좌석 설치 금지 관련 짧은 텍스트
- [확대된 주변 원문] 해당 안내와 위쪽의 별도 `소음과 연기` 관련 block이 함께 포함됨
- [기존 LLM 결과] candidate 중심 문구
- [새 LLM 결과] `동승석 어린이 보조 좌석 설치 금지`
- [채택/거부 이유] 생성 문구는 이번에는 맞았지만 다른 주제 block까지 모델에 전달됐다. 현재 선택 방식은 문맥 혼입 위험이 있다.

#### 기존 검사가 거부한 source-supported 완성 — p.201 / image 5

- [규칙 후보] `버튼을 누르면 램프가 켜지고 다시 한번 누`
- [기존 주변 원문] 문장이 중간에서 끊긴 후보 중심 문맥
- [확대된 주변 원문] 버튼을 한 번 누르면 켜지고 다시 누르면 꺼진다는 설명
- [기존 LLM 결과] 꺼짐 동작을 완성하는 표현을 제안했으나 candidate-only 검사에서 거부
- [새 LLM 결과] `스위치 램프 버튼`
- [채택/거부 이유] A의 거부는 source 근거 부족이 아니라 candidate-only 검증 때문이었다. B는 이 건에서 더 나은 문구를 만들지 못했다. 문맥 확대만으로 품질 개선이 보장되지는 않는다.

#### 관련 block이 확대 문맥에서도 제외됨 — p.359 / image 3

- [규칙 후보] `내리면 현재 클러스터의 속도로 크루즈 컨트롤`
- [기존 주변 원문] 클러스터 속도에 따른 크루즈 컨트롤 동작 문구
- [확대된 주변 원문] `+ 스위치를 위로 올리거나 – 스위치를 아래로` block은 다른 이미지 소유로 판정되어 모델 입력에서 제외
- [기존 LLM 결과] 조작 방향을 추가한 확장 표현은 candidate-only 검사에서 거부
- [새 LLM 결과] `– 스위치를 아래로 내려 현재 속도로 크루즈 컨트롤 작동` 제안, 입력 source에 근거가 없어 fallback
- [채택/거부 이유] 방향 문구는 PDF의 가까운 제외 block에는 있으나 실제 모델 입력에는 없으므로 B의 입력 기준 거부는 타당하다. 이는 전체 PDF 기준 hallucination은 아니지만 input-grounding 실패다. block 소유권 규칙이 유용한 문맥도 놓칠 수 있다.

#### candidate를 유지하는 편이 나음 — p.271 / image 1

- [규칙 후보] 변속기 냉각 중 안전한 장소에서 `00분` 정차하라는 문구
- [기존 주변 원문] 정차 시간과 안전 장소를 포함
- [확대된 주변 원문] 경고/정차 상황의 인접 문장 추가
- [기존 LLM 결과] candidate에 가까운 설명
- [새 LLM 결과] `변속기 냉각 중 정차 경고`
- [채택/거부 이유] 짧아졌지만 시간과 안전 장소 조건이 빠졌다. 정보 보존 관점에서 candidate가 더 낫다.

#### 원문 어휘는 있으나 의미가 빗나감 — p.32 / image 2

- [규칙 후보] 주행 상태에서 아이를 태운 경우의 보조 좌석 설치 금지 안내
- [기존 주변 원문] 어린이 보조 좌석과 아이 안전/금지 조건에 관한 설명
- [확대된 주변 원문] 같은 어린이 안전 안내 문맥
- [기존 LLM 결과] candidate 중심의 금지 조건
- [새 LLM 결과] `탑승한 아이들의 안전한 보호`
- [채택/거부 이유] 단어는 원문과 겹치지만 핵심 금지 지침이 사라진 의미 드리프트다. 어휘 포함 여부만 보는 자동 검사는 의미 충실성을 보장하지 못한다.

### 검증 기준의 한계

B의 lexical source checker는 44건을 통과시키고 13건을 fallback 처리했다. 수동 대조상 13건에는 한국어 조사/활용형 차이 및 연결어 차이처럼 source 의미가 유지된 제안도 있었고, p.32처럼 어휘는 근거가 있지만 의미가 빗나간 제안도 있었다. p.359는 실제 입력에 없는 방향 표현이라 fallback이 맞다. 따라서 source 어휘 포함은 의미 충실성의 충분조건이 아니며, candidate 밖 어휘도 그 자체로 오류라고 볼 수 없다.

A/B는 context뿐 아니라 prompt/검증도 달랐다. A는 candidate-only 제약을 유지했고, B는 source에 명시된 표현의 활용을 허용했다. 따라서 이는 context 단독의 순수 비교가 아니라 `문맥 확장 + source-grounded prompt/validation` 패키지 비교다.

## 결론

**판정 B — 일부 개선됐지만 잘못된 문맥 혼입과 정보 손실 위험도 있어 이득은 제한적이다.** B에서는 문구 변경과 수동 개선 사례가 늘었고, source에 있는 표현을 candidate에 없다는 이유로 거부하던 문제도 일부 줄었다. 반면 p.69에서 다른 주제 block이 선택됐고 p.359에서 관련 block이 ownership 규칙으로 제외됐다. p.271 및 그림 식별자 사례에서는 요약이 조건 정보를 잃었다.

이번 결과만으로 Text LLM을 production에 연결하지 않는다. 추가 실험이 필요하다면 이미지별 문맥 관련성 확인과 정보 보존 검사를 먼저 보강해야 한다. 이 작업에서는 production 코드, DB, Storage를 변경하지 않았고 동일한 100개 표본만 사용했다.