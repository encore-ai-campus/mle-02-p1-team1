"""답변을 내용 삭제 없이 주제별 블록으로 표시합니다."""
import re
import streamlit as st


def heading_icon(title):
    if '경고등' in title:
        return '🚨'
    if any(word in title for word in ('경고', '주의', '금지')):
        return '⚠️'
    if any(word in title for word in ('시작', '확인', '준비')):
        return '✅'
    if any(word in title for word in ('안 되', '안되', '해결', '점검', '문의')):
        return '🔧'
    return '📋'


def answer_sections(text):
    """Markdown 제목/짧은 안내 제목을 기준으로 나눕니다. 원문·출처는 보존합니다."""
    sections, title, lines = [], None, []
    plain_titles = {'시작하기 전에', '사용 방법', '사용방법', '주의하세요', '주의사항',
                    '경고', '경고등', '그래도 안 되면', '확인해 주세요'}
    for line in text.splitlines():
        match = re.match(r'^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$', line)
        candidate = re.sub(r'^\*\*|\*\*$', '', line.strip()).rstrip(':. ')
        # 제목처럼 보이는 짧은 문장만 인식합니다. 일반 본문을 임의로 제목으로 바꾸지 않습니다.
        is_plain = candidate in plain_titles
        if match or is_plain:
            if title is not None or any(s.strip() for s in lines):
                sections.append((title, '\n'.join(lines).strip()))
            title, lines = (match.group(1) if match else candidate), []
        else:
            lines.append(line)
    if title is not None or any(s.strip() for s in lines):
        sections.append((title, '\n'.join(lines).strip()))
    return sections


def format_answer(text):
    """스트리밍/완료/대화 기록에 동일한 서식을 사용해 완료 시 레이아웃이 바뀌지 않습니다."""
    def heading(match):
        title = re.sub(r'^[✅📋⚠️🚨🔧🔌]+\s*', '', match.group(1)).strip()
        return f'#### {heading_icon(title)} {title}'
    # 줄바꿈이 도착한 제목만 꾸며, 타이핑 중인 제목의 아이콘이 바뀌지 않게 합니다.
    return re.sub(r'^#{1,6} +([^\n]+)(?=\n)', heading, text, flags=re.MULTILINE)


def render_answer(text):
    st.markdown(format_answer(text))
