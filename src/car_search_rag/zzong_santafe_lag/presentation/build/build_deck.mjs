// 발표 내용 JSON을 읽어 편집 가능한 PPT와 슬라이드별 검사용 PNG를 만듭니다.
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { Presentation, PresentationFile, FileBlob } from 'file:///C:/Users/Playdata/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';
import { FontLibrary } from 'file:///C:/Users/Playdata/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/node_modules/skia-canvas/lib/index.js';

const buildDir=path.dirname(fileURLToPath(import.meta.url));
const presentationDir=path.dirname(buildDir);
const moduleDir=path.dirname(presentationDir);
const workspaceDir=path.resolve(moduleDir,'../../..');
const skillDir='C:/Users/Playdata/.codex/plugins/cache/openai-primary-runtime/presentations/26.904.11930/skills/presentations';
const python='C:/Users/Playdata/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe';
// 검증기가 별도 Node 프로세스에서도 같은 번들 패키지를 읽도록 지정합니다.
process.env.RUNTIME_NODE_MODULES='C:/Users/Playdata/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
const { finalizePresentation, applyPresentationChartFont }=await import(pathToFileURL(path.join(skillDir,'container_tools/artifact_tool_utils.mjs')).href);
FontLibrary.use('Malgun Gothic',['C:/Windows/Fonts/malgun.ttf','C:/Windows/Fonts/malgunbd.ttf']);
const family='Malgun Gothic';
const content=JSON.parse(await fs.readFile(path.join(presentationDir,'content.json'),'utf8'));
const p=Presentation.create({slideSize:{width:1280,height:720}});

function text(slide,value,left,top,width,height,size=32,bold=false,color='#182334') {
  // 텍스트는 이미지로 만들지 않아 PPT에서 직접 수정할 수 있습니다.
  const box=slide.shapes.add({geometry:'textbox',position:{left,top,width,height},fill:'none',line:{fill:'none',width:0}});
  box.text=value;
  box.text.style={typeface:family,fontSize:size,bold,color,autoFit:'none'};
  return box;
}

for (const [i,entry] of content.slides.entries()) {
  const s=p.slides.add();
  const cover=i===0;
  s.background.fill=cover?'#172738':'#F9FAFC';
  const color=cover?'#FFFFFF':'#172738';
  text(s,entry.title,84,cover?140:62,1112,cover?175:110,cover?62:44,true,color);
  if(cover) {
    text(s,entry.subtitle,88,350,1100,60,32,false,'#B8D5EB');
    text(s,entry.body.join('\n'),88,447,1050,140,30,false,'#FFFFFF');
  } else if(entry.image) {
    text(s,entry.body.join('\n\n'),84,207,490,360,28,false,color);
    const bytes=await fs.readFile(path.join(workspaceDir,entry.image));
    s.images.add({blob:bytes,contentType:'image/jpeg',alt:'2026-10-05 차대번호 질문의 실제 답변 화면',
                  fit:'contain',position:{left:610,top:180,width:580,height:440}});
    text(s,'2026-10-05 저장 화면',610,627,580,34,21,false,'#526278');
  } else if(i===10) {
    entry.body.forEach((line,k)=>text(s,line,84,207+k*98,560,84,28,false,color));
    const chart=s.charts.add('bar',{
      position:{left:666,top:200,width:530,height:385},
      title:'기존 30문항 MRR@5',titleTextStyle:{typeface:family,fontSize:25},categories:['보너스 전','보너스 후','OpenAI'],
      // 표시하는 소수 네 자리 값을 넣고 원래 정밀도는 근거 파일에 보관합니다.
      series:[{name:'MRR@5',values:[0.9306,0.9556,0.9389],valuesFormatCode:'0.0000',fill:'#376C94',
               dataLabelOverrides:[0.9306,0.9556,0.9389].map((value,idx)=>({idx,text:value.toFixed(4),position:'outEnd',textStyle:{typeface:family,fontSize:24}}))}],
      barOptions:{direction:'column',grouping:'clustered'},hasLegend:false,
      xAxis:{textStyle:{typeface:family,fontSize:22}},
      yAxis:{min:0,max:1,majorUnit:0.2,numberFormatCode:'0.0',textStyle:{typeface:family,fontSize:22}},
      dataLabels:{showValue:true,position:'outEnd',textStyle:{typeface:family,fontSize:24}},
    });
    applyPresentationChartFont(chart,{fontFamily:family});
    text(s,'보너스 후 = 로컬 임베딩 비교 기준',675,600,510,48,21,false,'#526278');
  } else {
    entry.body.forEach((line,k)=>text(s,line,84,205+k*96,1112,83,34,false,color));
  }
  text(s,`${String(i+1).padStart(2,'0')} / ${content.slides.length}`,1090,664,115,30,20,false,cover?'#B8D5EB':'#526278');
  const localSources=entry.sources.map(source=>path.resolve(moduleDir,source.replace('../../../../data/','../../../data/')));
  s.speakerNotes.textFrame.setText(entry.notes+'\n\n근거 파일:\n'+localSources.join('\n')+'\n\n수업 근거: '+path.join(presentationDir,'lesson_evidence.json'));
}
const candidatePath=path.join(buildDir,'candidate.pptx');
await (await PresentationFile.exportPptx(p)).save(candidatePath);
const finalPath=path.join(presentationDir,'output','santafe_presentation_final.pptx');
const result=await finalizePresentation({
  workspaceDir,candidatePath,finalPath,pythonExecutable:python,
  integrityValidatorPath:path.join(skillDir,'container_tools/inspect_presentation_package_integrity.py'),
  layoutValidatorPath:path.join(skillDir,'container_tools/inspect_presentation_layout_geometry.py'),
  layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit'],
  requiredNativeChartOwnerSlides:[11],materializeLiteralChartWorkbooks:true,
  fontPolicy:{basis:'design',families:[family]},verifyArtifactToolImport:true,
  receiptPath:path.join(buildDir,'validation_final.json'),
});
// 최종 PPT를 다시 읽어 모든 페이지를 렌더링합니다.
const final=await PresentationFile.importPptx(await FileBlob.load(finalPath));
for(let i=0;i<final.slides.items.length;i++) {
  const slide=final.slides.items[i];
  const preview=await final.export({slide,format:'png',scale:1});
  await fs.writeFile(path.join(buildDir,`slide-${String(i+1).padStart(2,'0')}.png`),new Uint8Array(await preview.arrayBuffer()));
}
console.log(JSON.stringify({finalPath,slides:final.slides.items.length,packagePassed:result.packageIntegrity.status,layoutFindings:result.presentationLayout.findingCount,chartPassed:result.nativeChartValidation.passed}));
