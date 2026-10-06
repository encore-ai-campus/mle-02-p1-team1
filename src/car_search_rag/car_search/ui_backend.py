"""쏘나타 전용 로직과 접속별 메모리 대화를 공통 화면에 연결합니다."""
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from car_search_rag.car_search.chat_runtime import prepare_reply

VEHICLE = ('hyundai', 'sonata', 2026)


def answer_question(question, history, on_event=None):
    # 개인 테스트 화면과 똑같은 Agent·도구·검색 개수·대화 범위를 사용합니다.
    reply = prepare_reply(question, history, vehicle=VEHICLE)
    for token in reply.chunks:
        if on_event:
            on_event('token', token)
    sources = [dict(
        label=f'R{i}', title='SONATA 2026 사용설명서',
        source_file='DN8_2026_ko_KR.pdf', pdf_pages=[source['page_no']],
    ) for i, source in enumerate(reply.sources, 1)]
    return dict(
        answer=dict(text=reply.answer, status='error' if reply.error else 'answered', cited_labels=[]),
        sources=sources, source_display='retrieved', vehicle_id='sonata',
        images=reply.images, download_html=reply.download_html,
    )


def get_related_images(packet):
    if packet.get('vehicle_id') != 'sonata':
        return []
    # runtime에서 이미 선택한 결과를 표시 형식으로 바꿀 뿐, 다시 검색하지 않습니다.
    return [dict(data=image['url'], pdf_page=image['page_no'],
                 caption=image.get('description', '')) for image in packet.get('images', [])]


class SonataBackend:
    """브라우저 접속별로 생성합니다. DB나 다른 차량의 대화는 사용하지 않습니다."""

    def __init__(self):
        self.sessions = {}
        self.lock = Lock()

    def start_session(self, is_test=False):
        sid = str(uuid4())
        self.sessions[sid] = {'session_id': sid, 'ended_at': None,
            'last_activity_at': datetime.now(timezone.utc), 'pending_request_id': None,
            'expires_after_minutes': None, 'history': [], 'requests': {}}
        return sid

    def get_session(self, session_id):
        return self.sessions.get(session_id)

    def is_session_active(self, session_id):
        # 쏘나타는 접속 종료 전까지 대화를 유지하며 시간 만료를 적용하지 않습니다.
        return session_id in self.sessions

    def end_session(self, session_id):
        # 차량 선택 화면으로 돌아갈 때 이 접속의 대화 메모리를 비웁니다.
        self.sessions.pop(session_id, None)

    def chat(self, session_id, question, request_id=None, on_event=None):
        question = question.strip()
        if not question:
            raise ValueError('질문을 입력해 주세요.')
        request_id = request_id or str(uuid4())
        with self.lock:
            session = self.sessions.get(session_id)
            if session is None:
                raise ValueError('종료된 대화입니다. 차량을 다시 선택해 주세요.')
            cached = session['requests'].get(request_id)
            if cached:
                if cached[0] != question:
                    raise ValueError('같은 요청 ID에 다른 질문을 사용할 수 없습니다.')
                return cached[1]
            packet = answer_question(question, list(session['history']), on_event)
            session['history'].extend([
                {'role': 'user', 'content': question},
                {'role': 'assistant', 'content': packet['answer']['text'],
                 'images': packet.get('images', [])},
            ])
            session['requests'][request_id] = (question, packet)
            session['last_activity_at'] = datetime.now(timezone.utc)
            return packet

    get_related_images = staticmethod(get_related_images)


def create_backend():
    """현재 접속에서만 사용할 쏘나타 구현을 만듭니다."""
    return SonataBackend()
