"""수업 노트북을 실행하지 않고 관련 셀과 모델 사용 근거를 저장합니다."""
import hashlib
import json
from pathlib import Path

ROOT = Path('C:/study-with-ai/src/study_with_ai')
SPECS = [
 ('TF-IDF','5_자연어처리/4_TF_IDF.ipynb',['TfidfVectorizer']),
 ('임베딩','5_자연어처리/6_임베딩_벡터.ipynb',['SentenceTransformer','MiniLM','BGE']),
 ('OpenAI 임베딩','5_자연어처리/8_로컬_openai_임베딩.ipynb',['text-embedding-3-small']),
 ('청킹','8_RAG파이프라인구축/1_문서로드_청킹.ipynb',['RecursiveCharacterTextSplitter']),
 ('LCEL','8_RAG파이프라인구축/4_LCEL_실습.ipynb',['ChatOpenAI','ChatPromptTemplate','StrOutputParser']),
 ('pgvector','9_관계형DB_pgvector/3_pgvector.ipynb',['CREATE EXTENSION','register_vector','<=>']),
 ('기술 통계','4_통계및-EDA/1_기초통계.ipynb',['describe()','median()']),
 ('분포','4_통계및-EDA/2_분포시각화-이상치.ipynb',['hist(','histplot','boxplot']),
 ('상관분석','4_통계및-EDA/3_상관분석.ipynb',['.corr(']),
]


def collect():
    """수업 파일 식별값과 1부터 세는 셀 순번을 보관합니다."""
    lessons=[]
    for concept,relative,terms in SPECS:
        p=ROOT/relative
        cells=json.loads(p.read_text(encoding='utf-8'))['cells']
        matches=[{'cell':i,'excerpt':line.strip()} for i,c in enumerate(cells,1)
                 for line in ''.join(c.get('source',[])).splitlines() if any(t in line for t in terms)]
        lessons.append({'concept':concept,'path':str(p),'relative':relative,
                        'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'matches':matches})
    files=[p for folder in ROOT.iterdir() if folder.name.startswith(('5_','6.','7_','8_','9_'))
           for p in folder.rglob('*.ipynb')]
    models={name:[] for name in ['jhgan/ko-sroberta-multitask-mrl','gpt-6-luna']}
    for p in files:
        for i,c in enumerate(json.loads(p.read_text(encoding='utf-8'))['cells'],1):
            for name in models:
                if name in ''.join(c.get('source',[])):
                    models[name].append({'path':str(p),'cell':i})
    report={'checked_date':'2026-10-07','cell_numbering':'1-based notebook cell order',
            'lessons':lessons,'additional_model_scan':{'notebook_count':len(files),'matches':models},
            'scope':'현재 컴퓨터의 수업 파일. Notion 수업 원본의 최신 변경까지 대조한 결과는 아님.'}
    out=Path(__file__).resolve().parents[1]/'lesson_evidence.json'
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'lessons':len(lessons),'scan_count':len(files),'model_matches':models},ensure_ascii=False))


if __name__=='__main__':
    collect()
