"""캐스퍼 RAG의 이미지 정보를 공통 말풍선 안에 표시합니다."""
from urllib.parse import urlsplit

import streamlit as st


def casper_result(packet):
    # 현재 연결부는 원본 응답을 native_result에 보존합니다.
    # 원본 형식으로 직접 전달하는 연결부도 같은 표시 함수를 사용할 수 있습니다.
    return packet.get('native_result') or packet


def collect_casper_images(result):
    """같은 그림은 한 번만 표시하되, 원래 그림 번호와 모든 근거 번호를 보존합니다."""
    gallery = {}
    for source in result.get('sources') or ():
        citation = source.get('citation_id', source.get('label'))
        for image in source.get('images') or ():
            if not isinstance(image, dict):
                continue
            image_id = image.get('image_id')
            url = image.get('url')
            key = ('id', image_id) if image_id is not None else ('url', url)
            if key == ('url', None):
                continue
            entry = gallery.setdefault(key, {
                'image_id': image_id, 'url': None, 'caption': '', 'pdf_page': None,
                'answer_image_labels': [], 'used_in_answer': False, 'citation_ids': [],
            })
            # 일부 출처에 빠진 정보를 같은 그림의 다른 출처에서 보완합니다.
            # 서명 URL이 달라도 image_id가 같으면 같은 그림으로 취급합니다.
            if isinstance(url, str):
                try:
                    parsed = urlsplit(url)
                    if parsed.scheme in {'https', 'http'} and parsed.netloc and not entry['url']:
                        entry['url'] = url
                except ValueError:
                    pass
            for field in ('caption', 'pdf_page'):
                if entry[field] in (None, '') and image.get(field) is not None:
                    entry[field] = image[field]
            label = image.get('answer_image_label')
            if label and label not in entry['answer_image_labels']:
                entry['answer_image_labels'].append(label)
            entry['used_in_answer'] = entry['used_in_answer'] or bool(image.get('used_in_answer'))
            if citation is not None and citation not in entry['citation_ids']:
                entry['citation_ids'].append(citation)
    return list(gallery.values())


def render_casper_images(packet):
    result = casper_result(packet)
    count = result.get('image_input_count', 0)
    if count:
        st.caption(f'답변 모델에 전달한 매뉴얼 그림 {count}개')
    if result.get('image_notice'):
        st.caption(result['image_notice'])

    images = collect_casper_images(result)
    if not images:
        return
    st.caption('설명서의 연결된 그림입니다. 그림 설명은 자동 생성 자료이므로 원문과 함께 확인하세요.')
    for image in images:
        # 화면 순서로 번호를 새로 매기면 답변의 [그림 N]과 달라질 수 있습니다.
        # 중복 출처에 서로 다른 번호가 있더라도 모두 원문 그대로 보존합니다.
        labels = ' · '.join(str(label) for label in image['answer_image_labels'])
        role = '답변 모델에 전달' if image['used_in_answer'] else '참고 그림'
        refs = ' · '.join(f'[{ref}]' for ref in image['citation_ids'])
        page = f"PDF {image['pdf_page']}페이지" if image['pdf_page'] is not None else ''
        st.caption(' · '.join(part for part in (labels, role, f'검색 근거 {refs}' if refs else '', page) if part))
        if not image['url']:
            st.caption('이 그림의 주소를 확인하지 못했어요. 답변과 설명서 출처를 확인해 주세요.')
            continue
        try:
            st.image(image['url'], caption=image['caption'] or None,
                     alt=image['caption'] or labels or '캐스퍼 사용설명서 이미지')
        except Exception:
            # 그림 표시 실패가 이미 완성된 답변이나 출처 표시를 막지 않게 합니다.
            st.caption('이 그림을 표시하지 못했어요. 답변과 설명서 출처는 확인할 수 있어요.')
