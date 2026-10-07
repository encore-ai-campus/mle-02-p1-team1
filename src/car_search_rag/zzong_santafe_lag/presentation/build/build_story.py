"""화면과 PPT에서 사용하는 동일 JSON으로 발표 대본과 코드 근거표를 만듭니다."""
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1]
MODULE = FOLDER.parent


def link(value):
    """저장소 코드와 로컬 수업 파일을 바로 열 수 있는 절대 링크를 만듭니다."""
    relative = value.replace('../../../../data/', '../../../data/')
    path = (MODULE / relative).resolve()
    return f'[{value}]({path.as_posix()})'


def build():
    """설계 이유·대본·시연·질의응답을 하나의 문서로 보관합니다."""
    content = json.loads((FOLDER / 'content.json').read_text(encoding='utf-8'))
    audit = json.loads((FOLDER / 'lesson_evidence.json').read_text(encoding='utf-8'))
    out = [f"# {content['title']} 발표 대본과 근거", '', content['thesis'], '',
           '약 12~15분 발표용 16장 구성. 데이터 분석은 2026-10-06 저장 스냅샷 기준입니다. '
           '발표 자료 정리일은 2026-10-07입니다.', '', '## 싼타페 구현 구조', '',
           content['architecture'], '',
           '현재 통합 화면은 OpenAI 임베딩을 사용합니다. 의미·키워드 점수와 목적·구체 표현 규칙을 '
           '결합하며, 기본 경로는 DB에서 읽은 저장 벡터를 NumPy로 정렬합니다. '
           'pgvector는 저장과 의미 검색 기준 경로에 사용합니다. 모든 결합 계산을 SQL에서 '
           '실행한다고 설명하지 않습니다.', '',
           '## M0부터 M9까지의 진행', '',
           '|단계|수업 개념의 적용|프로젝트 구현|상태와 해석 범위|', '|---|---|---|---|']
    for row in content['milestones']:
        out.append(f"|{row['stage']} {row['name']}|{row['lesson']}|{row['implementation']}|{row['status']}|")
    out.extend(['', 'M0~M9 명칭은 기존 합의 계획의 단계입니다. 현재 수업 노트북과 개념·코드를 대조했으며, '
                '접근되지 않았던 Notion 수업 순서 원본의 최신 내용까지 확인했다는 뜻은 아닙니다.', '',
                '## 수업 근거', '', '셀 번호는 Markdown 셀을 포함한 전체 노트북 순서이며 1부터 시작합니다.', ''])
    for row in audit['lessons']:
        cells=', '.join(str(i) for i in sorted({hit['cell'] for hit in row['matches']}))
        out += [f"### {row['concept']}", '', f"[{row['relative']}]({Path(row['path']).as_posix()}) · 셀 {cells}", '']
        excerpts='\n'.join(hit['excerpt'] for hit in row['matches'][:4])
        out += ['```python', excerpts, '```', '']
    out += [f"현재 NLP·LLM·RAG·DB 수업 노트북 {audit['additional_model_scan']['notebook_count']}개에서 "
            '`jhgan/ko-sroberta-multitask-mrl`과 `gpt-6-luna` 사용을 찾지 못했습니다. '
            '확인 범위 밖 자료에까지 이 결론을 확대하지 않습니다.', '',
            'TF-IDF 수업의 명사 토큰과 프로젝트의 글자 2~4그램을 구분합니다. '
            '상관분석 개념은 수업 적용, Spearman 선택은 프로젝트 구현입니다. '
            'Hit@5·MRR@5와 Streamlit 자체가 수업에서 실습됐다는 주장은 별도 근거 없이 하지 않습니다.', '',
            '## 모델 선택 이유와 역할', '']
    for row in content['models']:
        out += [f"### {row['name']}", '', row['category'], '', '**역할:** '+row['role'], '',
                '**선택 이유:** '+row['why'], '', '**목적:** '+row['purpose'], '',
                '**해석 범위:** '+row['limit'], '', '**코드 근거:** '+row['evidence'], '']
    out += ['## 추가 코드의 이유와 목적', '']
    for row in content['extensions']:
        out += [f"### {row['item']}", '', row['why']+'. '+row['purpose']+'.', '',
                '**코드:** '+row['code'], '', row['boundary'], '']
    out += ['## 슬라이드별 발표 대본', '']
    for index, slide in enumerate(content['slides'], 1):
        out += [f"### {index:02d} {slide['title'].replace(chr(10),' ')}", '']
        out += ['- '+line for line in slide['body']]
        out += ['', '**발표 대본**', '', slide['notes'], '', '**근거**', '']
        out += ['- '+link(source.split(':')[0]) for source in slide['sources']]
        out.append('')
    out += ['## 시연 순서', '']
    for row in content['demo']:
        out += [f"### {row['step']} {row['question']}", '', row['show']+'. '+row['message'], '']
    out += ['발표 전 개인 앱을 열어 차종 선택과 위 사례의 현재 출력을 확인합니다. '
            '미검토 자료이면 보류 동작을 설명하고 저장된 평가 결과를 제시합니다. '
            '자료 화면 방문만으로 API를 호출하지 않지만 실제 질문·생성은 기존 API 설정을 사용합니다.', '',
            '## 예상 질문과 답변', '']
    for row in content['qa']:
        out += ['### '+row['q'], '', row['a'], '']
    out += ['## 발표에서 수치를 설명하는 기준', '',
            '- 기본 저장: 부모 527, 청크 2,213, 그림 864, 그림 연결 1,157. 활성 검토 반영 분석: 부모 527, 청크 2,216, 그림 연결 1,155. 서로 다른 버전을 한 수치로 섞지 않습니다.',
            '- 기존 30문항 Hit@5 1.0은 기대 출처 검색 지표입니다. 사용자 질문 전체의 답변 정확도 100%로 표현하지 않습니다.',
            '- 50문항 초기 응답, 사용자 캡처 50개, 추가 30문항은 조건과 판정 범위가 다릅니다. 통과율을 단순한 성능 전후 비교로 표현하지 않습니다.',
            '- 추가 30문항의 B/C는 구체 목적에 답해야 통과합니다. A의 주제 질문 통과가 구체 답변 성능을 보장하지 않습니다.',
            '- 평가 기록은 평가 시점의 결과입니다. 이후 수정된 코드의 개선 효과는 같은 조건 재평가가 필요합니다.',
            '- 25/527 검토 비율, 원문 빈 값 점검 0건, 그림 파일 일치는 의미 정확성·전체 검토 완료를 뜻하지 않습니다.', '']
    (FOLDER / 'storyline.md').write_text('\n'.join(out), encoding='utf-8')
    print('발표 대본과 근거 저장 완료')


if __name__ == '__main__':
    build()
