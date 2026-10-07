"""저장된 아이오닉 자료를 pandas로 집계하고 M3에 넣을 그래프를 만듭니다.

DB/API를 호출하지 않습니다. 저장소 루트에서 실행:
  python src/car_search_rag/anna_rag/analysis/build_m3_analysis.py
분석 환경에 pandas, matplotlib, fonttools, brotli가 필요합니다.
웹페이지에서는 생성된 그림만 읽습니다.
"""
from pathlib import Path
import base64
import hashlib
import html
import json
import tempfile

import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import StrMethodFormatter
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/full_manual/NE1_2027_ko_KR_4525f59eb857'
OUT = ROOT / 'analysis/m3_eda'
PURPLE, GRAY = '#5b43c4', '#a9a6b0'


def load_data():
    """JSON의 각 테이블을 엑셀 표처럼 다룰 수 있는 DataFrame으로 변환합니다."""
    records = json.loads((DATA / 'records.json').read_text())
    sections = pd.DataFrame(records['sections'])
    chunks = pd.DataFrame(records['chunks'])
    images = pd.DataFrame(records['images'])
    audit = pd.DataFrame(json.loads((DATA / 'chunk_audit.json').read_text()))
    sections['chapter'] = sections['section_path'].str[0]
    sections['body_chars'] = sections['full_text'].str.len()
    return sections, chunks, images, audit


def setup_plot():
    """문서에 포함된 Pretendard를 그래프에도 사용합니다. OS 글꼴에 의존하지 않습니다."""
    source_font = ROOT / 'chatbot/assets/PretendardVariable.woff2'
    font_hash = hashlib.sha256(source_font.read_bytes()).hexdigest()[:16]
    # Matplotlib용으로 WOFF2 압축만 풉니다. 원본 글꼴과 디자인은 바꾸지 않습니다.
    plot_font = Path(tempfile.gettempdir()) / f'ioniq5-pretendard-{font_hash}.ttf'
    if not plot_font.exists():
        with TTFont(source_font) as font:
            font.flavor = None
            font.save(plot_font)
    font_manager.fontManager.addfont(str(plot_font))
    font_name = font_manager.FontProperties(fname=str(plot_font)).get_name()
    # SVG 글자를 경로로 저장하므로 다른 PC에서 열어도 같은 글꼴로 보입니다.
    plt.rcParams.update({'font.family': font_name, 'font.weight': 'normal',
                         'font.size': 12, 'axes.unicode_minus': False,
                         'svg.fonttype': 'path', 'svg.hashsalt': 'ioniq5-m3',
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.labelcolor': '#555555', 'xtick.color': '#555555',
                         'ytick.color': '#555555', 'axes.edgecolor': '#dddddd',
                         'figure.facecolor': 'white', 'axes.facecolor': 'white'})


def chart_chapters(sections):
    # 같은 최상위 목차를 가진 부모 섹션을 세어 큰 순서대로 비교합니다.
    counts = sections.groupby('chapter').size().sort_values()
    fig, ax = plt.subplots(figsize=(10, 5.7), layout='constrained')
    counts.plot.barh(ax=ax, color=[PURPLE if v == counts.max() else GRAY for v in counts], width=.65)
    ax.bar_label(ax.containers[0], padding=7, fontsize=11)
    ax.set(xlabel='소제목별 설명 묶음 수 (개)', ylabel='', xlim=(0, counts.max() * 1.15))
    ax.xaxis.grid(True, color='#eeeeee'); ax.set_axisbelow(True)
    return fig


def chart_types(chunks):
    counts = chunks['chunk_type'].value_counts().reindex(['text', 'image'])
    counts.index = ['텍스트 본문', '이미지 설명']
    fig, ax = plt.subplots(figsize=(10, 3), layout='constrained')
    counts.iloc[::-1].plot.barh(ax=ax, color=[PURPLE, GRAY], width=.5)
    labels = [f'{v:,}개 · {v / len(chunks):.1%}' for v in counts.iloc[::-1]]
    ax.bar_label(ax.containers[0], labels=labels, padding=9)
    ax.set(xlabel='검색용 조각 수 (개)', ylabel='', xlim=(0, counts.max() * 1.3))
    ax.xaxis.grid(True, color='#eeeeee'); ax.set_axisbelow(True)
    return fig


def chart_children(audit):
    # 목차 접두어를 제외한 실제 청크 본문 길이입니다. 단위는 토큰이 아니라 글자입니다.
    lengths = audit['body_length']
    fig, ax = plt.subplots(figsize=(10, 4), layout='constrained')
    lengths.plot.hist(bins=list(range(0, 451, 50)), ax=ax, color=PURPLE, edgecolor='white', label='검색용 글 조각')
    ax.axvline(lengths.median(), color='#292929', linestyle='--', label=f'길이순으로 가운데: {lengths.median():,.0f}자')
    ax.set(xlabel='글 조각 하나의 길이 (글자 수)', ylabel='해당 길이의 조각 수 (개)', xlim=(0, 450))
    ax.yaxis.grid(True, color='#eeeeee'); ax.set_axisbelow(True); ax.legend(frameon=False)
    return fig


def chart_parents(sections):
    # 전체 범위를 그대로 보여 줍니다. 긴 본문을 제거하거나 축을 자르지 않습니다.
    lengths = sections['body_chars']
    fig, axes = plt.subplots(2, 1, figsize=(10, 5.8), height_ratios=[3, 1], layout='constrained', sharex=True)
    lengths.plot.hist(bins=list(range(0, 11001, 500)), ax=axes[0], color=GRAY, edgecolor='white', label='소제목별 설명 묶음')
    axes[0].axvline(lengths.median(), color=PURPLE, linewidth=2, label=f'길이순으로 가운데: {lengths.median():,.1f}자')
    axes[0].axvline(lengths.mean(), color='#292929', linestyle='--', label=f'평균 {lengths.mean():,.1f}자')
    axes[0].set(ylabel='해당 길이의 설명 묶음 수 (개)'); axes[0].legend(frameon=False)
    axes[0].yaxis.grid(True, color='#eeeeee'); axes[0].set_axisbelow(True)
    axes[1].boxplot(lengths, orientation='horizontal', patch_artist=True,
                    boxprops={'facecolor': '#eee9ff', 'edgecolor': PURPLE},
                    medianprops={'color': PURPLE, 'linewidth': 2},
                    flierprops={'marker': 'o', 'markersize': 4, 'markeredgecolor': GRAY})
    axes[1].set(yticks=[], xlabel='설명 묶음 하나의 길이 (글자 수)', xlim=(0, 11000))
    axes[1].xaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
    return fig


def inspect_data(sections, chunks, images, audit):
    """비어 있으면 안 되는 필드만 검사합니다. image_id의 정상 NULL은 오류가 아닙니다."""
    checks = []
    for label, frame, key, text in [('부모 섹션', sections, 'section_id', 'full_text'),
                                   ('검색 청크', chunks, 'chunk_id', 'page_content'),
                                   ('이미지', images, 'image_id', 'caption')]:
        checks.append([label, len(frame), int(frame[key].isna().sum()),
                       int(frame[text].isna().sum()), int(frame[text].fillna('').str.strip().eq('').sum()),
                       int(frame[key].duplicated().sum())])
    assert set(audit.chunk_id) == set(chunks.loc[chunks.chunk_type.eq('text'), 'chunk_id'])
    assert len(audit) == len(set(audit.chunk_id))
    assert set(chunks.section_id) <= set(sections.section_id)
    assert (audit.end - audit.start).eq(audit.body_length).all()
    return checks


def table(headers, rows):
    return '<div class="table-wrap"><table><thead><tr>' + ''.join(f'<th>{html.escape(str(x))}</th>' for x in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join(f'<td>{html.escape(str(x))}</td>' for x in row) + '</tr>' for row in rows) + '</tbody></table></div>'


def code(text):
    return '<details><summary>pandas 분석 코드 보기</summary><pre class="code-excerpt">' + html.escape(text) + '</pre></details>'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    setup_plot()
    sections, chunks, images, audit = load_data()
    checks = inspect_data(sections, chunks, images, audit)
    figures = [chart_chapters(sections), chart_types(chunks), chart_children(audit), chart_parents(sections)]
    names = ['chapter_sections', 'chunk_types', 'child_lengths', 'parent_lengths']
    for name, fig in zip(names, figures):
        fig.savefig(OUT / f'{name}.svg', metadata={'Date': None}, bbox_inches='tight')
        fig.savefig(OUT / f'{name}.png', dpi=160, bbox_inches='tight')
        plt.close(fig)
    parent, child = sections.body_chars, audit.body_length
    summary = {'scope': 'saved preprocessing records, not live DB or user conversations',
               'records_sha256': hashlib.sha256((DATA / 'records.json').read_bytes()).hexdigest(),
               'audit_sha256': hashlib.sha256((DATA / 'chunk_audit.json').read_bytes()).hexdigest(),
               'versions': {'pandas': pd.__version__, 'matplotlib': matplotlib.__version__},
               'sections': len(sections), 'chunks': len(chunks), 'images': len(images),
               'represented_pdf_pages': int(chunks.pdf_pages.explode().nunique()),
               'chapter_sections': sections.groupby('chapter').size().sort_values(ascending=False).to_dict(),
               'chunk_types': chunks.chunk_type.value_counts().to_dict(),
               'parent_chars': parent.describe().to_dict(), 'child_chars': child.describe().to_dict(),
               'caption_sources': images.caption_source.value_counts().to_dict(),
               'required_field_checks': checks, 'short_children_under_50': int(child.lt(50).sum()),
               'parent_iqr_upper': float(parent.quantile(.75) + 1.5 * (parent.quantile(.75) - parent.quantile(.25)))}
    summary['parents_above_iqr_upper'] = int(parent.gt(summary['parent_iqr_upper']).sum())
    (OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    descriptions = [
        ('1. 편의 장치에 관한 설명이 가장 많습니다', '막대가 길수록 그 주제에 속한 설명 묶음이 많습니다. 페이지 수나 글자 수를 센 그래프는 아닙니다.',
         '전체 설명 묶음 552개 중 167개가 편의 장치에 관한 내용입니다. 약 10개 중 3개예요. 운전자 보조 기능까지 합치면 전체의 약 절반(46.2%)입니다.',
         '자료가 많은 주제만 시험하면 다른 주제의 문제를 놓칠 수 있습니다. 챗봇을 평가할 때 충전·안전·정비처럼 여러 주제의 질문을 골고루 넣을 필요가 있습니다. 설명이 많다고 사람들이 더 많이 묻는다는 뜻은 아닙니다.',
         "sections['chapter'] = sections['section_path'].str[0]\ncounts = sections.groupby('chapter').size().sort_values()\ncounts.plot.barh(xlabel='부모 섹션 수 (개)')"),
        ('2. 검색 자료 10개 중 약 3개는 그림 설명입니다', '회색 막대는 본문에서 나눈 글, 보라색 막대는 그림에 붙인 설명입니다.',
         '검색용 조각 2,338개는 본문에서 나눈 글 1,670개와 그림 설명 668개로 구성됩니다. 그림 설명도 검색 대상에 들어갑니다.',
         '예를 들어 버튼 위치를 물으면 관련 그림 설명을 찾고, 연결된 원본 그림을 답변에 보여줄 수 있습니다. 다만 지금은 그림 자체의 모양이 아니라 붙어 있는 글로 검색합니다. 668개 중 666개는 그림 주변의 글을 가져온 설명이라, 그림을 정확히 설명하는지도 따로 확인해야 합니다.',
         "counts = chunks['chunk_type'].value_counts()\nratio = counts.div(counts.sum()).mul(100)\ncounts.plot.barh(xlabel='검색 청크 수 (개)')"),
        ('3. 텍스트 청크의 본문을 최대 400자로 나눴습니다', '가로축은 글 조각의 길이, 세로축은 그 길이에 해당하는 조각 수입니다. 막대가 높을수록 그 길이의 조각이 많습니다.',
         f'텍스트 청크 본문은 최대 {child.max():,}자, 중앙값은 {child.median():,.0f}자입니다. 최소 길이 제한은 없으며 목차를 붙인 최종 검색용 텍스트는 400자를 넘을 수 있습니다.',
         f'50자 미만 청크 {child.lt(50).sum():,}개는 의미가 충분한지 검토할 대상입니다. 50자는 최소 길이나 불량 판정 기준이 아니며, 짧아도 핵심 정보가 있으면 유효합니다. 답변 생성에는 연결된 부모 본문도 함께 사용합니다.',
         "lengths = audit['body_length']\nlengths.describe()\nlengths.plot.hist(bins=range(0, 451, 50))\n# 구간은 왼쪽 포함·오른쪽 제외, 마지막 구간은 양 끝 포함\n# 400자 청크는 400–450 구간에 포함"),
        ('4. 전체 설명을 가져오면 읽을 양이 크게 늘기도 합니다', '위 그래프는 왼쪽일수록 짧은 설명, 오른쪽일수록 긴 설명입니다. 아래 상자와 점은 같은 자료를 간단히 요약한 그림입니다.',
         f'설명 묶음을 길이순으로 줄 세우면 가운데 값은 약 {parent.median():,.0f}자입니다. 그런데 가장 긴 설명은 {parent.max():,}자예요. 일부 긴 설명 때문에 평균은 약 {parent.mean():,.0f}자로 올라갑니다.',
         '그래서 검색 결과가 5개라고 읽을 양도 항상 비슷한 것은 아닙니다. 짧은 설명 5개와 긴 설명 5개는 분량이 크게 달라요. 챗봇은 같은 설명을 두 번 가져오지 않도록 하고, 한 번에 읽을 전체 설명의 양에도 제한을 둡니다.',
         "sections['body_chars'] = sections['full_text'].str.len()\nlengths = sections['body_chars']\nlengths.describe()\nlengths.plot.hist(bins=range(0, 11001, 500))\nplt.figure()\nlengths.plot.box(vert=False)"),
    ]
    blocks = []
    for name, (title, subtitle, finding, decision, snippet) in zip(names, descriptions):
        svg64 = base64.b64encode((OUT / f'{name}.svg').read_bytes()).decode()
        extra = ''
        if name == 'child_lengths':
            extra = '<p class="small muted">여기서 센 길이는 본문만의 글자 수입니다. 검색할 때 덧붙이는 목차는 제외했고, 공백과 줄바꿈은 포함했습니다.</p>'
        if name == 'parent_lengths':
            extra = ('<details><summary>아래 상자와 점 읽는 방법</summary>'
                     '<p>상자는 길이순으로 가운데에 있는 절반의 설명을 모아 놓은 범위입니다. 상자 안의 선은 가운데 값(중앙값)이고, 오른쪽의 점들은 유독 긴 설명입니다. 점으로 표시됐다고 잘못된 자료라는 뜻은 아닙니다.</p>'
                     f'<p>자세한 기준: 상자는 {parent.quantile(.25):,.0f}~{parent.quantile(.75):,.2f}자입니다. 상자 길이의 1.5배를 오른쪽 끝에 더한 {summary["parent_iqr_upper"]:,.3f}자를 넘는 설명은 {summary["parents_above_iqr_upper"]}개입니다. 통계에서는 이 기준을 Q3 + 1.5×IQR이라고 부릅니다.</p></details>')
        blocks.append(f'<section class="space card"><h2>{title}</h2><p>{finding}</p><p class="muted"><b>그래프 읽기</b> · {subtitle}</p>'
                      f'<figure class="eda-figure"><img src="data:image/svg+xml;base64,{svg64}" alt="{title}. {finding}"></figure>'
                      f'<div class="detail"><h3>분석 결과의 활용</h3><p>{decision}</p></div>{extra}{code(snippet)}</section>')
    stats = [(len(sections), '소제목별 설명 묶음'), (len(chunks), '검색용 조각'), (len(images), '원본 그림')]
    content = '<p>챗봇이 읽을 설명서를 살펴본 과정입니다. <b>어떤 내용이 많은지, 글과 그림이 얼마나 있는지, 설명이 얼마나 긴지</b>를 확인했습니다.</p>'
    content += '<section class="space card"><h2>설명 묶음과 검색용 조각</h2><p><b>설명 묶음(부모)</b>은 소제목 하나 아래의 전체 설명입니다. <b>검색용 조각(청크)</b>은 그 안에서 필요한 부분을 찾기 위해 작게 나눈 글이나 그림 설명입니다.</p><div class="flow"><div class="node"><b>전체 설명을 보관</b><small>소제목 아래 내용을 한 묶음으로 저장합니다.</small></div><div class="node"><b>작은 조각으로 검색</b><small>질문과 관련된 부분을 골라 찾습니다.</small></div><div class="node"><b>전체 설명도 함께 읽기</b><small>찾은 부분의 앞뒤 조건과 주의사항을 확인합니다.</small></div></div><p>예를 들어 충전 설명에서 ‘케이블 분리’ 부분을 찾았다면, 그 부분이 속한 전체 설명도 함께 읽는 방식입니다.</p></section>'
    content += '<div class="stats" style="margin-top:28px">' + ''.join(f'<div class="stat"><b>{n:,}</b><span>{label}</span></div>' for n,label in stats) + '</div>'
    content += ''.join(blocks)
    content += '<section class="space card"><h2>5. 빈 내용과 중복된 번호도 확인했습니다</h2><p>확인한 자료에서는 <b>꼭 필요한 내용이 비어 있거나, 같은 자료 번호가 두 번 저장된 경우가 없었습니다.</b> 다만 이 점검만으로 설명 내용까지 모두 정확하다고 판단할 수는 없습니다.</p>'
    friendly_checks = [[{'부모 섹션':'설명 묶음','검색 청크':'검색용 조각','이미지':'그림 설명'}[row[0]], *row[1:]] for row in checks]
    content += '<details><summary>점검 건수 자세히 보기</summary>' + table(['자료','개수','자료 번호 없음','내용 누락','빈 글만 있음','번호 중복'], friendly_checks)
    content += '<p>자료 번호(ID)는 자료를 구분하는 이름표입니다. 글만 있는 조각에는 그림 번호가 없어도 정상이에요. 그림 번호가 없다는 이유로 글을 삭제하지 않았습니다. 각 검색 조각이 원래 설명 묶음과 연결되는지도 확인했습니다.</p></details>'
    content += code("chunks['chunk_id'].isna().sum()  # 필수 ID 누락\nchunks['page_content'].isna().sum()  # 본문 누락\nchunks['page_content'].fillna('').str.strip().eq('').sum()  # 빈 문자열\nchunks['chunk_id'].duplicated().sum()  # 같은 ID 중복") + '</section>'
    content += '<section class="space card"><h2>데이터를 살펴보고 정한 방향</h2>' + table(['확인한 특징','챗봇에서의 처리'], [
        ['글과 그림 설명이 함께 있음','관련 그림을 찾으면 원본 그림도 함께 표시'],
        ['짧게 자른 글은 앞뒤 설명이 부족할 수 있음','작은 조각으로 찾고, 전체 설명도 함께 읽기'],
        ['전체 설명 중에는 아주 긴 것도 있음','같은 설명은 한 번만 가져오고, 읽을 양에 한도 두기'],
        ['주제마다 설명의 양이 다름','평가할 때 여러 주제의 질문을 포함할 필요가 있음']])
    content += '<p>여기까지는 <b>챗봇에 넣은 자료를 살펴본 결과</b>입니다. 질문에 맞는 자료를 잘 찾는지는 M6 검색 품질 평가에서 확인합니다.</p></section>'
    # 실행 가능한 노트북: 코드와 실제 그래프 출력을 함께 보존합니다.
    cells = [{'cell_type':'markdown','metadata':{},'source':['# 아이오닉 데이터 분석 · M3\n저장된 전처리 결과를 pandas로 집계합니다. DB/API를 호출하지 않습니다.\n필요 패키지: pandas, matplotlib, fonttools, brotli / 글꼴: 프로젝트에 포함된 Pretendard.']}]
    init = "from pathlib import Path\nimport sys\n# 노트북 폴더 또는 저장소 루트에서 실행할 수 있습니다.\nroot = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / 'src/car_search_rag/anna_rag/analysis').exists())\nsys.path.insert(0, str(root / 'src/car_search_rag/anna_rag/analysis'))\nfrom build_m3_analysis import *\nsetup_plot()\nsections, chunks, images, audit = load_data()\nprint(inspect_data(sections, chunks, images, audit))"
    cells.append({'cell_type':'code','metadata':{},'source':init.splitlines(True),'execution_count':None,'outputs':[]})
    for name,desc,call in zip(names,descriptions,['chart_chapters(sections)','chart_types(chunks)','chart_children(audit)','chart_parents(sections)']):
        title,subtitle,finding,decision,snippet=desc
        cells.append({'cell_type':'markdown','metadata':{},'source':[f'## {title}\n{subtitle}\n\n{finding}\n\n{decision}\n\n```python\n{snippet}\n```']})
        cells.append({'cell_type':'code','metadata':{},'source':[f'fig = {call}\ndisplay(fig)\nplt.close(fig)'],'execution_count':None,'outputs':[{'output_type':'display_data','metadata':{},'data':{'image/png':base64.b64encode((OUT/f'{name}.png').read_bytes()).decode(),'text/plain':['저장된 전처리 결과로 생성한 그래프']}}]})
    nb={'cells':cells,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python','version':'3.12'}},'nbformat':4,'nbformat_minor':5}
    for i,cell in enumerate(cells):cell['id']=f'm3-{i:02}'
    nb_path=ROOT/'2_데이터_분석_M3.ipynb'
    nb_path.write_text(json.dumps(nb,ensure_ascii=False,indent=1))
    content += '<details class="space"><summary>분석 자료·수업 연결·실행 방법</summary><p>아이오닉 설명서의 저장된 <code>records.json</code>과 <code>chunk_audit.json</code>을 pandas로 집계했습니다. 검색 조각이 연결된 PDF 페이지는 556개입니다. 사용자 대화나 실시간 DB 통계는 포함하지 않습니다.</p><p><code>2_데이터_분석_M3.ipynb</code>에서 그래프와 코드를 함께 볼 수 있습니다. 저장소 루트에서 아래 명령으로 다시 계산할 수 있습니다.</p><pre class="code-excerpt">python src/car_search_rag/anna_rag/analysis/build_m3_analysis.py</pre><p>집계·그림: <code>analysis/m3_eda/summary.json</code> 및 SVG·PNG. 웹페이지는 미리 계산한 결과를 보여줍니다.</p>'
    content += '<div class="source">수업 연결 · 7_EDA및통계_1차.pdf: 26쪽 결측·중복, 27쪽 차트 선택, 47쪽 describe, 48·53쪽 히스토그램, 55·60쪽 박스플롯, 58쪽 삭제 전 확인.<br>수업의 분석 방식을 아이오닉 데이터에 적용한 결과입니다.<br>원본 SHA-256 · records.json: ' + summary['records_sha256'] + '<br>분석 환경 · pandas ' + pd.__version__ + ' / Matplotlib ' + matplotlib.__version__ + '</div></details>'
    # 고정된 M3 영역만 바꿉니다. 다른 메뉴와 실험 결과는 유지합니다.
    doc=ROOT/'chatbot/assets/ioniq5-work-document.html'
    text=doc.read_text(); start=text.index('pages.m3='); end=text.index('pages.m4=',start)
    block="pages.m3=()=>head('M3','데이터 분석','설명서의 내용과 길이를 살펴보고, 챗봇이 자료를 찾아 읽는 방식에 연결했습니다.')+" + json.dumps(content,ensure_ascii=False).replace('</','<\\/') + ';\n'
    text=text[:start]+block+text[end:]
    css='.eda-figure{margin:22px 0 24px;border:1px solid var(--line);border-radius:6px;padding:16px;background:white}.eda-figure img{display:block;width:100%;height:auto}@media(max-width:700px){.eda-figure{overflow-x:auto;padding:10px}.eda-figure img{min-width:600px}}'
    if '.eda-figure{' not in text:text=text.replace('</style>',css+'\n</style>',1)
    doc.write_text(text)
    print(json.dumps({k:summary[k] for k in ['sections','chunks','images','short_children_under_50','parents_above_iqr_upper','required_field_checks']},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
