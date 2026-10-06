import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const root = path.resolve(process.cwd());
const skillDir = process.env.SKILL_DIR;
const tmpDir = process.env.TMP_DIR || path.join(root, "src", "car_search_rag", "car_search", "docs", "tmp", "pptx_car_search_final");
const outPptx = process.env.FINAL_PPTX;
const outMd = process.env.FINAL_MD || path.join(path.dirname(outPptx), "CAR_MANUAL_RAG_PRESENTATION_FINAL.md");
const { resolvePresentationFont } = await import(pathToFileURL(path.join(skillDir, "container_tools/artifact_tool_utils.mjs")).href);
const FONT = resolvePresentationFont({ fontFamily: "Noto Sans KR" });
const C = { ink:"#12233F", muted:"#5E6E83", blue:"#2357D8", teal:"#008A91", orange:"#D87527", pale:"#F3F6FA", paleBlue:"#EAF0FF", paleTeal:"#E7F5F3", line:"#D9E1EC", white:"#FFFFFF", red:"#B94D45", paleRed:"#F9ECEA", green:"#167B63" };
const W=1280,H=720;
const ppt=Presentation.create({slideSize:{width:W,height:H}});
const summaries=[];

function box(slide,x,y,w,h,fill=C.pale,line="none",radius=0){
 const s=slide.shapes.add({geometry:radius?"roundRect":"rect",position:{left:x,top:y,width:w,height:h},fill,line:line==="none"?{style:"solid",fill:"none",width:0}:{style:"solid",fill:line,width:1},...(radius?{borderRadius:radius}:{})}); return s;
}
function txt(slide,text,x,y,w,h,size=26,color=C.ink,bold=false,align="left",opts={}){
 const s=slide.shapes.add({geometry:"textbox",position:{left:x,top:y,width:w,height:h},fill:"none",line:{style:"solid",fill:"none",width:0}});
 s.text=text;
 s.text.style={typeface:FONT,fontSize:size,bold,color,alignment:align,verticalAlignment:opts.valign||"top",wrap:"square",autoFit:"shrinkText",insets:{top:0,right:0,bottom:0,left:0},...(opts.italic?{italic:true}:{})};
 return s;
}
function rule(slide,x,y,w,color=C.line,h=2){ box(slide,x,y,w,h,color); }
function addSlide(title, notes, slideText, evidence, assets=[]){
 const slide=ppt.slides.add(); slide.background.fill=C.white;
 slide.shapes.add({geometry:"rect",position:{left:0,top:0,width:14,height:H},fill:C.blue,line:{style:"solid",fill:"none",width:0}});
 txt(slide,title,64,46,1150,62,44,C.ink,true);
 rule(slide,64,124,1152,C.line,2);
 txt(slide,"SONATA 2026  |  CAR MANUAL RAG",64,683,700,18,14,C.muted,false);
 txt(slide,String(ppt.slides.items.length).padStart(2,"0"),1170,680,45,20,15,C.muted,true,"right");
 slide.speakerNotes.textFrame.setText(`${notes}\n\n근거: ${evidence.join("; ")}`);
 summaries.push({title,screen:slideText,talk:notes,evidence,assets});
 return slide;
}
function flowNode(slide,x,y,w,h,kicker,label,accent=C.blue){
 box(slide,x,y,w,h,C.white,C.line,16); box(slide,x,y,7,h,accent);
 txt(slide,kicker,x+18,y+18,w-32,23,16,C.muted,true);
 txt(slide,label,x+18,y+52,w-32,h-62,23,C.ink,true);
}
function arrow(slide,x,y,w=34,color=C.blue){
 slide.shapes.add({geometry:"rightArrow",position:{left:x,top:y,width:w,height:26},fill:color,line:{style:"solid",fill:"none",width:0}});
}
async function addImage(slide,file,x,y,w,h,alt){
 const blob=new Uint8Array(await fs.readFile(file));
 slide.images.add({blob,contentType:"image/png",alt,fit:"contain",position:{left:x,top:y,width:w,height:h}});
}

// 1. Cover
{
 const s=addSlide("Hyundai Sonata 2026\n차량 매뉴얼 RAG", "Sonata 2026 국문 취급설명서를 대상으로 자연어 질문에 매뉴얼 근거를 연결하는 검색·답변 서비스를 만들었습니다. 이 발표는 검색 점수, 실제 UI에서 본 이미지 문제, 그리고 PDF 레이아웃을 이용한 이미지 설명 메타데이터 개선 과정을 따라갑니다.", "Hyundai Sonata 2026 차량 매뉴얼 RAG / 검색 결과 이미지 관련성 개선", ["SONATA_PROJECT_SCOPE.md", "M7_IMPROVEMENT_EVALUATION.md"]);
 txt(s,"검색 결과 이미지 관련성 개선",68,260,680,52,31,C.muted,false);
 rule(s,68,344,520,C.line,2);
 txt(s,"0%",720,235,210,95,76,C.muted,true,"center");
 txt(s,"→",930,251,95,64,48,C.blue,true,"center");
 txt(s,"93.2%",1010,235,220,95,76,C.blue,true,"center");
 txt(s,"초기 설명 확보율",698,336,270,32,19,C.muted,false,"center");
 txt(s,"최종 설명 확보율",990,336,255,32,19,C.muted,false,"center");
 txt(s,"PDF 레이아웃을 이용한 규칙형 추출",702,424,520,34,23,C.ink,true,"center");
 txt(s,"508 pages   /   947 chunks   /   955 images",68,592,690,36,24,C.ink,true);
}

// 2. Problem
{
 const s=addSlide("긴 매뉴얼에서 필요한 근거를 찾는 문제", "차량 매뉴얼은 수백 페이지에 걸쳐 사용, 안전, 정비 정보를 담고 있습니다. 사용자는 정확한 부품 명칭이나 페이지를 몰라도 자연어로 질문하고, 답변이 어느 설명에 근거하는지 확인하고 싶어 합니다. Sonata 프로젝트는 이 탐색 과정을 RAG 검색으로 연결했습니다.", "508페이지의 차량 매뉴얼 / 사용자가 자연어로 질문 / 관련 근거를 찾아 답변", ["EDA_REPORT.md", "Notion M0 · 주제·API 확정", "사용자 제공 PROJECT BRIEF / PRD"]);
 txt(s,"508",72,182,330,145,116,C.blue,true);
 txt(s,"페이지",395,232,150,52,33,C.muted,true);
 txt(s,"질문 표현과 매뉴얼 표현은 다를 수 있다",72,366,560,72,31,C.ink,true);
 rule(s,72,468,545,C.line,2);
 txt(s,"“차가운 타이어는 어떤 상태인가요?”",690,214,500,100,36,C.ink,true);
 txt(s,"자연어 질문",690,328,200,32,20,C.blue,true);
 txt(s,"→ 관련 페이지와 chunk를 검색",690,387,500,38,28,C.ink,false);
 txt(s,"→ 근거 기반 답변과 이미지 표시",690,442,500,38,28,C.ink,false);
}

// 3. Data and EDA
{
 const s=addSlide("원본 508페이지를 검색 단위로 구성", "원본 PDF에서 508페이지 모두 텍스트 추출 성공으로 기록되어 있습니다. 등록 코드는 RecursiveCharacterTextSplitter의 chunk_size 800, overlap 150 설정으로 검색 chunk를 만들고, 페이지와 이미지를 별도 metadata로 DB에 적재합니다. 초기 EDA에서는 이미지 955건 모두 설명 metadata가 없었습니다.", "PDF 508p / 텍스트 추출 508p / DB chunk 947 / image 955 / 초기 이미지 설명 메타데이터 없음 955/955", ["EDA_REPORT.md", "DATASET_SPEC.md", "sonata_pdf_eda.ipynb", "M7_IMPROVEMENT_EVALUATION.md"], ["src/car_search_rag/car_search/docs/figures/sonata_pdf_text_histogram.png"]);
 txt(s,"508",76,161,165,76,62,C.blue,true); txt(s,"PDF pages",76,235,165,30,20,C.muted,false);
 txt(s,"508 / 508",255,161,220,68,39,C.ink,true); txt(s,"텍스트 추출 성공",255,235,220,30,20,C.muted,false);
 txt(s,"947",492,161,165,76,62,C.teal,true); txt(s,"chunks",492,235,165,30,20,C.muted,false);
 txt(s,"955",678,161,165,76,62,C.orange,true); txt(s,"images",678,235,165,30,20,C.muted,false);
 await addImage(s,path.join(root,"src/car_search_rag/car_search/docs/figures/sonata_pdf_text_histogram.png"),72,300,670,325,"Sonata PDF 페이지별 추출 텍스트 길이 histogram");
 txt(s,"초기 이미지 설명 메타데이터 없음",810,332,400,54,21,C.muted,true);
 txt(s,"955 / 955",810,397,360,72,48,C.red,true);
 txt(s,"텍스트 추출과 이미지 설명 메타데이터는\n별도 문제로 점검",810,535,380,65,22,C.muted,false);
}

// 4. Pipeline
{
 const s=addSlide("Embedding 검색 결과를 답변과 이미지에 연결", "적재 시 PDF 페이지 텍스트를 800자 단위, 150자 overlap으로 분할하고 text-embedding-3-small로 1536차원 벡터를 저장합니다. 질문 때는 같은 embedding 모델로 query vector를 만들고, search_car_manual이 PostgreSQL + pgvector의 cosine distance 연산자로 chunk를 정렬합니다. ChatOpenAI가 검색 근거를 받아 답변을 만들고 Streamlit이 결과를 보여줍니다. HNSW index는 존재하지만 개별 실행계획에서 선택 여부는 별도로 봐야 합니다.", "적재: PDF → page text → RecursiveCharacterTextSplitter 800/150 → embedding / 질문: Streamlit → embedding → pgvector SQL → chunk → ChatOpenAI → 답변", ["SONATA_PROJECT_SCOPE.md", "car_manual_register_service.py", "car_manual_search_service.py", "car_manual.sql", "app_kbj.py", "M4 실행계획 EXPERIMENT_LOG.md"]);
 txt(s,"적재",72,156,120,28,20,C.blue,true);
 txt(s,"PDF page text  →  chunk 800 / overlap 150  →  text-embedding-3-small  →  PostgreSQL + pgvector",72,193,1138,40,24,C.ink,true);
 rule(s,72,251,1136,C.line,2);
 txt(s,"질문·답변",72,278,170,28,20,C.blue,true);
 const nodes=[
  [70,"질문","자연어"],[268,"Embedding","1536차원"],[466,"SQL 검색","`<=>` cosine"],[664,"검색 chunk","Top-K"],[862,"ChatOpenAI","근거 문맥"],[1060,"Streamlit","답변·이미지"]
 ];
 for(let i=0;i<nodes.length;i++){
  const [x,k,l]=nodes[i]; flowNode(s,x,350,155,126,k,l,i===2?C.teal:C.blue);
  if(i<nodes.length-1) arrow(s,x+161,399,30,C.blue);
 }
 txt(s,"HNSW / vector_cosine_ops 인덱스 존재 · 실제 planner 사용 여부는 실행계획에 따라 다름",72,550,1120,32,20,C.muted,false);
 txt(s,"현재 chat model 설정: gpt-6-luna",72,592,500,28,19,C.muted,false);
}

// 5. M6 official baseline
{
 const s=addSlide("M6 공식 Retrieval baseline", "실제 앱은 검색 결과를 Top-10까지 조회합니다. 공식 M6 평가는 더 엄격하게 Top-5를 기준으로 Hit@5와 MRR@5를 계산했습니다. Hit@5는 9/11(81.8%), MRR@5는 0.5333입니다. M6-05 정답 근거는 6위, M6-11은 10위입니다. 따라서 정답 근거 11개는 모두 실제 앱의 Top-10 범위 안에 포함됐습니다. 11/11은 앱 조회 범위를 설명하는 보조 정보이며 공식 평가 지표를 대체하지 않습니다. 브라우저 UI 관찰과도 별도입니다.", "실제 앱 retrieval Top-10 / 공식 평가 Hit@5·MRR@5 / Hit@5 9/11 = 81.8% / MRR@5 0.5333 / M6-05 rank 6 · M6-11 rank 10 / 정답 근거 Top-10 포함 11/11 (보조 정보)", ["M6_RETRIEVAL_EVALUATION.md", "M6_RETRIEVAL_RESULTS.csv", "M6 Notion page"]);
 txt(s,"공식 Retrieval-only",72,163,430,30,22,C.muted,true);
 txt(s,"81.8%",72,215,520,118,100,C.blue,true);
 txt(s,"Hit@5   9 / 11",78,340,390,38,27,C.ink,true);
 rule(s,640,182,2,C.line,250);
 txt(s,"0.5333",702,232,470,88,78,C.teal,true);
 txt(s,"MRR@5",710,332,380,36,27,C.ink,true);
 txt(s,"실제 앱 retrieval: Top-10  /  공식 평가: Hit@5",72,466,1080,34,22,C.ink,true);
 txt(s,"Top-5 밖 정답: M6-05 6위  ·  M6-11 10위",72,510,1080,34,22,C.red,true);
 txt(s,"정답 근거 11개 모두 Top-10 포함 (11/11) · 앱 범위 설명용",72,553,1080,34,22,C.teal,true);
 txt(s,"공식 Hit@5 / MRR@5는 유지 · 브라우저 UI 관찰과 별도",72,601,1080,28,18,C.muted,false);
}

// 6. UI problem
{
 const s=addSlide("검색 답변과 이미지 관련성은 별도 품질 축", "초기 Streamlit 시연에서 텍스트 답변은 질문을 다루더라도, 같은 페이지에 연결된 이미지가 질문과 직접 관련이 낮은 경우가 관찰됐습니다. 예를 들어 와이퍼 교체 질문에 타이어 이미지가 함께 보였고, 비상 경고등 질문에도 주차 경고 관련 이미지가 섞였습니다. 이는 텍스트 Hit@5만으로 화면의 이미지 관련성을 평가할 수 없다는 점을 보여줬습니다.", "초기 UI 관찰 / 와이퍼 교체 질문 → 타이어 이미지 / 비상등 질문 → 주차 경고 이미지", ["M6_BROWSER_E2E_RESULT.md", "M7_IMPROVEMENT_EVALUATION.md", "원본 PDF physical p.236"] , ["src/car_search_rag/car_search/docs/tmp/pptx_car_search_final/assets/manual_page_236.png"]);
 txt(s,"초기 Streamlit UI 관찰",72,160,550,30,22,C.muted,true);
 txt(s,"와이퍼 블레이드\n교체 질문",72,220,355,92,37,C.ink,true);
 txt(s,"타이어 교체 이미지가 함께 노출",72,331,490,38,25,C.red,true);
 rule(s,72,402,490,C.line,2);
 txt(s,"비상 경고등\n기능 질문",72,434,355,82,37,C.ink,true);
 txt(s,"주차 경고 이미지도 섞임",72,534,470,38,25,C.red,true);
 await addImage(s,path.join(tmpDir,"assets/manual_page_236.png"),770,154,350,492,"원본 Sonata PDF p.236, USB 충전 단자와 앞좌석·뒷좌석 이미지");
 txt(s,"원본 p.236 · USB 단자와 2개 위치 그림",758,646,380,22,16,C.muted,false,"center");
}

// 7. Experiments
{
 const s=addSlide("모델 교체만으로는 해결되지 않았다", "초기에는 주변 문맥 규칙을 production에 적용했지만 955개 중 9개만 설명이 생성됐습니다. 동일 100건 표본의 텍스트 LLM 실험에서도 더 큰 모델이 규칙 후보를 실질적으로 더 좋게 다듬는 사례는 제한적이었습니다. context를 늘리면 개선 후보는 늘었지만 다른 주제의 문맥이 섞이는 문제가 생겼습니다. 그래서 모델 비교를 멈추고 PDF의 실제 레이아웃을 분석했습니다.", "초기 규칙형 방식은 보수적 / 텍스트 LLM 문구 개선은 제한적 / 문맥을 넓히면 다른 설명 혼입 / 다음 단계: PDF 레이아웃 분석", ["M7_IMPROVEMENT_EVALUATION.md", "IMAGE_DESC_TEXT_LLM_100.md", "IMAGE_DESC_TEXT_LLM_100_GPT56_LUNA.md", "IMAGE_DESC_TEXT_LLM_100_GPT56_TERRA.md", "IMAGE_DESC_CONTEXT_DIAGNOSTIC_100.md"]);
 txt(s,"초기 주변 문맥 규칙",72,168,280,34,20,C.muted,true);
 txt(s,"9 / 955",72,211,300,58,43,C.red,true);
 txt(s,"설명 확보율 0.94%",72,276,300,28,18,C.ink,true);
 rule(s,414,170,2,C.line,390);
 txt(s,"문구 다듬기 실험 · 100건 표본 (세부 수치는 참고)",462,168,700,34,19,C.muted,true);
 txt(s,"gpt-4.1-mini",462,223,250,28,18,C.ink,true); txt(s,"7 / 57 문구 채택",770,223,350,28,18,C.blue,true);
 txt(s,"gpt-5.6-luna",462,281,250,28,18,C.ink,true); txt(s,"44 통과 · 37 동일 문구",770,281,400,28,17,C.blue,true);
 txt(s,"gpt-5.6-terra",462,339,250,28,18,C.ink,true); txt(s,"39 통과 · 뚜렷한 개선 3",770,339,420,28,17,C.blue,true);
 rule(s,462,407,700,C.line,2);
 txt(s,"주변 문맥 확대",462,445,250,34,21,C.ink,true);
 txt(s,"개선 후보 3 → 25",770,445,400,34,21,C.teal,true);
 txt(s,"다른 이미지·주제 문맥이 섞이고 필요한 정보가 빠지기도 함",462,495,710,60,20,C.red,true);
 txt(s,"실험 입력은 제한된 표본이며 production은 LLM을 사용하지 않음",72,601,1100,30,19,C.muted,false);
}

// 8. Layout insight
{
 const s=addSlide("PDF 레이아웃이 이미지의 검색 문맥을 제공했다", "문서 페이지를 확인하면서 제목 또는 기능명, 짧은 타입 label, 이미지가 일정한 공간 관계로 배치된다는 점을 확인했습니다. 예를 들어 ‘앞좌석 열선 시트 사용’ 아래에 A타입·B타입 label이 있고 각 그림이 이어집니다. 최종 방식은 이미지 바로 위 텍스트를 중심으로 같은 column, 수평 겹침, 거리 순으로 연결합니다. font 크기는 후보 순위 신호로만 사용하며 9pt도 버리지 않습니다.", "문서 구조: 제목/소제목 → 직전 기능·타입 label → 이미지 / 예: 앞좌석 열선 시트 사용 / A타입", ["IMAGE_DESC_HEADING_100.md", "M7_IMPROVEMENT_EVALUATION.md", "car_manual_register_service.py", "원본 PDF physical p.463"] , ["src/car_search_rag/car_search/docs/tmp/pptx_car_search_final/assets/manual_page_463.png"]);
 txt(s,"이미지를 새로 묘사하지 않고 PDF 제목을 그대로 연결",72,158,700,31,21,C.muted,true);
 const yy=[226,343,460];
 const labels=[["상위 제목","엔진 오일량 점검 및 보충"],["직전 설명","레벨 게이지의 F-L 사이 확인"],["이미지 위치","페이지 내 같은 column의 그림"]];
 for(let i=0;i<3;i++){
   txt(s,labels[i][0],82,yy[i],155,28,18,i===2?C.teal:C.blue,true);
   txt(s,labels[i][1],248,yy[i]-3,465,40,25,C.ink,i<2);
   if(i<2){rule(s,108,yy[i]+67,2,C.line,42);txt(s,"↓",95,yy[i]+63,26,24,19,C.muted,true,"center");}
 }
 await addImage(s,path.join(tmpDir,"assets/manual_page_463.png"),795,151,335,480,"원본 Sonata PDF p.463, 엔진 오일량 점검 설명과 관련 페이지 이미지");
 txt(s,"PDF p.463 · 인쇄 페이지 9-17",785,641,355,24,16,C.muted,false,"center");
}

// 9. Final image desc coverage
{
 const s=addSlide("최종 이미지 설명 확보율은 93.2%", "최종 등록된 이미지 설명 metadata는 문서에 실제 있는 제목·기능명·절차명과 필요한 A/B 타입 label을 추출해 구성합니다. 955개 중 890개에 설명이 저장됐고 65개에는 설명이 없습니다. 400개는 제목만, 490개는 제목과 label 조합입니다. 설명 확보율은 metadata 저장 비율이지 이미지 설명의 정확도 점수가 아닙니다.", "이미지 955개 / 설명 저장 890개 (93.2%) / 제목만 400 / 제목+구분 label 490 / 설명 없음 65", ["M7_IMPROVEMENT_EVALUATION.md", "M7_AFTER_RESULTS.csv", "Notion M7 · 개선 실험 1회"]);
 txt(s,"이미지 설명 확보율",72,166,400,35,24,C.muted,true);
 txt(s,"0%",72,238,190,110,88,C.muted,true);
 txt(s,"→",264,252,85,74,58,C.blue,true,"center");
 txt(s,"93.2%",360,226,520,120,100,C.blue,true);
 txt(s,"890 / 955",368,339,300,35,25,C.ink,true);
 txt(s,"설명 메타데이터 구성",72,427,340,29,21,C.muted,true);
 const bx=72, by=483, bw=1040, bh=56;
 box(s,bx,by,bw,bh,C.pale,C.line,8);
 box(s,bx,by,bw*400/955,bh,C.blue,"none",8);
 box(s,bx+bw*400/955,by,bw*490/955,bh,C.teal,"none",0);
 box(s,bx+bw*890/955,by,bw*65/955,bh,"#C9D2DF","none",8);
 txt(s,"제목만 400",84,553,340,31,22,C.blue,true);
 txt(s,"제목 + 구분 표시 490",430,553,400,31,21,C.teal,true);
 txt(s,"설명 없음 65",856,553,235,31,20,C.muted,true,"right");
 txt(s,"93.2%는 이미지 설명의 정확도나 관련성 점수가 아님",72,618,1080,30,20,C.red,true);
}

// 10. before/after retrieval
{
 const s=addSlide("M7은 이미지 선택을 바꾸고 텍스트 Retrieval 점수는 유지", "M7은 텍스트 검색 SQL, embedding, Top-K를 바꾸지 않았습니다. 검색 결과 페이지 안에서 이미지 설명 metadata를 이용해 표시할 이미지를 별도로 선택했습니다. 실제 앱은 Top-10까지 조회하고 공식 평가는 Hit@5/MRR@5를 사용합니다. 정답 근거 11개는 모두 Top-10 안에 있었지만, 11/11은 앱 범위를 설명하는 보조 정보입니다. 동일 11개 질문의 M6/M7 공식 Retrieval-only 결과는 Hit@5 9/11, MRR@5 0.5333으로 유지됐습니다.", "M6 Before / M7 After: Hit@5 81.8%, MRR@5 0.5333 유지 / 실제 앱 retrieval Top-10 / 공식 평가 Hit@5 / Top-10 근거 포함 11/11은 보조 정보", ["M6_RETRIEVAL_EVALUATION.md", "M6_RETRIEVAL_RESULTS.csv", "M7_IMPROVEMENT_EVALUATION.md", "M7_AFTER_RESULTS.csv"]);
 txt(s,"M6 Before",100,173,390,38,25,C.muted,true,"center");
 txt(s,"M7 After",790,173,390,38,25,C.muted,true,"center");
 rule(s,632,222,2,C.line,300);
 txt(s,"81.8%",100,230,390,82,70,C.blue,true,"center");
 txt(s,"81.8%",790,230,390,82,70,C.blue,true,"center");
 txt(s,"Hit@5  ·  9/11",100,324,390,34,24,C.ink,true,"center");
 txt(s,"Hit@5  ·  9/11",790,324,390,34,24,C.ink,true,"center");
 txt(s,"MRR@5  ·  0.5333",100,377,390,34,24,C.teal,true,"center");
 txt(s,"MRR@5  ·  0.5333",790,377,390,34,24,C.teal,true,"center");
 rule(s,72,480,1136,C.line,2);
 txt(s,"텍스트 검색 지표는 유지",100,522,480,36,24,C.ink,true,"center");
 txt(s,"이미지 선택 방식은 개선",700,522,480,36,24,C.blue,true,"center");
 txt(s,"실제 앱 retrieval: Top-10  /  공식 평가: Hit@5",72,586,1100,28,19,C.muted,true,"center");
 txt(s,"정답 근거 Top-10 포함 11/11은 보조 정보 · 공식 Hit@5/MRR@5 유지",72,619,1100,25,17,C.muted,false,"center");
}

// 11. Browser result
{
 const s=addSlide("실제 Streamlit에서 관련 이미지 노출은 나아졌지만 남은 사례가 있다", "사용자가 실제 Streamlit 브라우저에서 M6 질문들을 확인한 결과를 이미지 관련성으로 별도 분류했습니다. 직접 적합 사례는 M6-01, 04, 07, 11, 부분 적합은 M6-06, 08, 09입니다. M6-03, 05에는 무관 이미지가 일부 섞였습니다. 이는 정성적 UI 관찰이며 image_desc coverage와 같은 정량 지표가 아니고, 완전한 이미지 정합성의 증명도 아닙니다.", "실제 브라우저 관찰 / 직접 적합 M6-01·04·07·11 / 부분 적합 M6-06·08·09 / 무관 이미지 일부 M6-03·05", ["M7_IMPROVEMENT_EVALUATION.md", "M6_BROWSER_E2E_RESULT.md", "Notion M7 · 개선 실험 1회"]);
 txt(s,"localhost:8501 실제 브라우저 · M6 질문 UI 관찰",72,164,800,32,21,C.muted,true);
 rule(s,72,223,1136,C.line,2);
 txt(s,"직접 적합",74,257,260,34,23,C.green,true);
 txt(s,"4개 관찰 사례",74,301,290,66,48,C.green,true);
 txt(s,"M6-01  ·  M6-04  ·  M6-07  ·  M6-11",74,374,525,33,20,C.ink,false);
 rule(s,72,432,550,C.line,2);
 txt(s,"부분 적합",74,461,260,34,23,C.orange,true);
 txt(s,"3개 관찰 사례",74,504,290,60,44,C.orange,true);
 txt(s,"M6-06  ·  M6-08  ·  M6-09",74,571,470,31,20,C.ink,false);
 rule(s,655,240,2,C.line,360);
 txt(s,"무관 이미지 일부",708,276,420,34,23,C.red,true);
 txt(s,"M6-03  ·  M6-05",708,333,420,50,35,C.red,true);
 txt(s,"완전 해결이 아니라\n질문과 관련된 이미지가 더 잘 노출되는 방향",708,423,442,90,25,C.ink,true);
 txt(s,"정성 관찰 · 공식 Hit@5/MRR와 별도",708,554,430,32,19,C.muted,false);
}

// 12. Conclusion
{
 const s=addSlide("검색 품질 개선은 데이터와 문서 구조를 이해하는 데서 시작", "텍스트 검색 점수와 이미지 관련성을 별도 지표로 살펴봤습니다. 강한 모델을 연속해서 시험했지만 문구 개선은 제한적이었고, PDF 제목과 이미지 배치를 이용한 규칙형 추출이 더 실용적이었습니다. 실제 UI에서 관찰한 관련·부분 관련·무관 이미지 사례를 구분해 다음 개선 근거로 남깁니다.", "데이터와 검색 평가 → UI 문제 관찰 → PDF 레이아웃 분석 → 이미지 설명 metadata 개선", ["PROJECT_PROGRESS_REPORT.md", "M6_RETRIEVAL_EVALUATION.md", "M7_IMPROVEMENT_EVALUATION.md", "Notion M7 · 개선 실험 1회", "Notion M9 · 시연·회고"]);
 const steps=[[72,"데이터","508p / 947 chunks"],[300,"평가","M6 baseline"],[528,"문제 발견","이미지 관련성"],[756,"레이아웃 분석","PDF 텍스트 배치"],[984,"결과","설명 확보율 93.2%"]];
 for(let i=0;i<steps.length;i++){
  const [x,a,b]=steps[i]; txt(s,a,x,211,188,32,21,i===4?C.blue:C.muted,true,"center");
  txt(s,b,x-2,257,190,58,25,C.ink,true,"center");
  if(i<steps.length-1) arrow(s,x+190,268,30,C.blue);
 }
 rule(s,72,364,1136,C.line,2);
 txt(s,"이번 결과가 말해주는 것",72,405,400,31,22,C.muted,true);
 txt(s,"텍스트 검색 지표는 유지",72,463,500,45,29,C.ink,true);
 txt(s,"질문과 관련된 이미지 노출은 개선",610,463,590,65,27,C.blue,true);
 txt(s,"강한 모델보다 데이터 구조 이해가 중요했다",72,578,1100,38,27,C.ink,true);
}

const buildDir=tmpDir;
await fs.mkdir(buildDir,{recursive:true});
await fs.mkdir(path.dirname(outPptx),{recursive:true});
const candidate=path.join(buildDir,"candidate.pptx");
await (await PresentationFile.exportPptx(ppt)).save(candidate);
for(let i=0;i<ppt.slides.items.length;i++){
 const blob=await ppt.export({slide:ppt.slides.items[i],format:"png",scale:1});
 await fs.writeFile(path.join(buildDir,`slide-${String(i+1).padStart(2,"0")}.png`),new Uint8Array(await blob.arrayBuffer()));
}
const montage=await ppt.export({format:"webp",montage:true,scale:1});
await fs.writeFile(path.join(buildDir,"montage.webp"),new Uint8Array(await montage.arrayBuffer()));

const md=["# Hyundai Sonata 2026 차량 매뉴얼 RAG 발표 자료", "", "> 최신 Notion M0–M9 내용, car_search 문서·코드·Notebook을 확인해 새 흐름으로 구성했다. M6 공식 Retrieval-only 결과와 브라우저 UI 관찰은 별도 지표로 유지한다.", ""];
for(let i=0;i<summaries.length;i++){
 const z=summaries[i];
 md.push(`## ${i+1}. ${z.title}`,"","### 화면에 표시되는 내용",z.screen,"","### 발표 멘트",z.talk,"","### 사용 근거 문서",...z.evidence.map(e=>`- ${e}`),"","### 사용한 이미지/그래프 경로",...(z.assets.length?z.assets.map(a=>`- \`${a}\``):["- 없음 (해당 슬라이드의 도형·흐름도는 편집 가능한 PowerPoint 도형)"]),"");
}
md.push("## 수치 해석 주의", "", "- M6의 Hit@5 81.8%와 MRR@5 0.5333은 11문항 공식 Retrieval-only 평가다.", "- M7의 텍스트 Retrieval 결과는 M6와 동일했다. image_desc coverage 93.2%는 metadata 저장률이지 이미지 정확도/관련성 점수가 아니다.", "- 브라우저의 직접/부분/무관 분류는 실제 Streamlit UI에 대한 정성 관찰이며 공식 M6 Retrieval 수치에 합산하지 않았다.", "- 저장소에 실제 Streamlit 화면 캡처가 없어 PPT에 임의의 앱 화면 이미지를 만들지 않았다.", "");
await fs.writeFile(outMd,md.join("\n"),"utf8");

const { finalizePresentation } = await import(pathToFileURL(path.join(skillDir,"container_tools/artifact_tool_utils.mjs")).href);
const staging=path.join(buildDir,"finalizer_v6"); await fs.mkdir(staging,{recursive:true});
const result=await finalizePresentation({
 workspaceDir:root,candidatePath:candidate,finalPath:outPptx,
 pythonExecutable:process.env.RUNTIME_PYTHON,
 integrityValidatorPath:path.join(skillDir,"container_tools/inspect_presentation_package_integrity.py"),
 layoutValidatorPath:path.join(skillDir,"container_tools/inspect_presentation_layout_geometry.py"),
 layoutArgs:["--expected-slide-size-emu","12192000,6858000","--validate-heading-fit"],
 requiredNativeTableOwnerSlides:[],fontPolicy:{basis:"design",families:[FONT]},
 verifyArtifactToolImport:true,receiptPath:path.join(staging,"validation.json")
});
console.log(JSON.stringify({pptx:outPptx,markdown:outMd,slideCount:ppt.slides.items.length,font:FONT,finalize:result},null,2));
