"""팀원의 Sonata RAG를 공통 챗봇의 세션·스트리밍 형식으로 연결합니다."""
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from psycopg.types.json import Jsonb

from car_search_rag.common.database_manager import DatabaseManager
from car_search_rag.common.sql_session import SqlSession
from car_search_rag.car_search.car_manual_search_service import CarManualSearchService


load_dotenv(Path(__file__).resolve().parents[4] / '.env')
db = DatabaseManager()
VEHICLE = ('hyundai', 'sonata', 2026)


def new_service():
    # 요청마다 서비스 객체를 분리하며 팀원의 검색·재정렬 설정을 그대로 사용합니다.
    return CarManualSearchService(SqlSession(database_manager=db, sql_log_mode='none'))


@lru_cache(maxsize=1)
def prepare_history():
    """IONIQ 5의 설명서 FK와 섞이지 않도록 별도 이력 테이블을 준비합니다."""
    with db.connect(camel_case_keys=False) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS anna_rag.sonata_chat_sessions (
            session_id uuid PRIMARY KEY, car_id text NOT NULL,
            vehicle_id text NOT NULL DEFAULT 'sonata' CHECK (vehicle_id = 'sonata'),
            is_test boolean NOT NULL DEFAULT false,
            created_at timestamptz NOT NULL DEFAULT now(),
            last_activity_at timestamptz NOT NULL DEFAULT now(),
            ended_at timestamptz
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS anna_rag.sonata_chat_turns (
            session_id uuid NOT NULL REFERENCES anna_rag.sonata_chat_sessions(session_id),
            request_id uuid NOT NULL, question text NOT NULL, packet jsonb NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (session_id, request_id)
        )''')
        # 이력은 서버 DB 연결에서만 읽고 쓰며 공개 Supabase API에는 노출하지 않습니다.
        for table in ('sonata_chat_sessions', 'sonata_chat_turns'):
            conn.execute(f'ALTER TABLE anna_rag.{table} ENABLE ROW LEVEL SECURITY')
            conn.execute(f'REVOKE ALL ON anna_rag.{table} FROM PUBLIC, anon, authenticated')


def start_session(is_test=False):
    # 현재 DB의 Sonata ID를 확인합니다. 과거 실행에서 사용한 ID를 하드코딩하지 않습니다.
    car_id = new_service().repository.find_car_id(*VEHICLE)
    prepare_history()
    session_id = str(uuid4())
    with db.connect(camel_case_keys=False) as conn:
        conn.execute('''INSERT INTO anna_rag.sonata_chat_sessions
            (session_id, car_id, is_test) VALUES (%s, %s, %s)''',
            (session_id, str(car_id), is_test))
    return session_id


def get_session(session_id):
    with db.connect(camel_case_keys=False) as conn:
        return conn.execute('''SELECT *, NULL AS pending_request_id
            FROM anna_rag.sonata_chat_sessions WHERE session_id=%s''', (session_id,)).fetchone()


def end_session(session_id):
    with db.connect(camel_case_keys=False) as conn:
        conn.execute('''UPDATE anna_rag.sonata_chat_sessions SET ended_at=now()
            WHERE session_id=%s AND ended_at IS NULL''', (session_id,))


def answer_question(service, question, history, on_event=None):
    def stream_writer(event):
        if on_event and event.get('type') == 'answer_token' and event.get('text'):
            on_event('token', event['text'])

    # 차종은 사용자 질문이나 LLM이 정하지 않고 선택 카드에 맞춰 고정합니다.
    result = service.ask_manual_with_sources(
        *VEHICLE, question=question, conversation_history=history,
        limit=5, stream_writer=stream_writer,
    )
    rows = result.search_results
    sources = [dict(
        label=f'R{i}', title='SONATA 2026 사용설명서',
        source_file='DN8_2026_ko_KR.pdf',
        pdf_pages=[row['carManualChunkPageNo']],
        page_content=row.get('carManualChunkTxt', ''),
    ) for i, row in enumerate(rows, 1)]
    # Sonata는 페이지로 출처를 안내합니다. 검색 근거를 실제 인용 라벨로 꾸미지 않습니다.
    return dict(
        answer=dict(text=result.answer, status='answered' if rows else 'no_evidence', cited_labels=[]),
        sources=sources, source_display='retrieved', vehicle_id='sonata',
        image_question=question, image_search_results=list(rows),
    )


def chat(session_id, question, request_id=None, on_event=None):
    question = question.strip()
    if not question:
        raise ValueError('질문을 입력해 주세요.')
    request_id = request_id or str(uuid4())
    service = new_service()
    current_car_id = str(service.repository.find_car_id(*VEHICLE))
    # 세션 행을 잠가 같은 질문의 중복 요청을 직렬화합니다. 실패하면 저장도 롤백됩니다.
    with db.connect(camel_case_keys=False) as conn:
        session = conn.execute('''SELECT * FROM anna_rag.sonata_chat_sessions
            WHERE session_id=%s FOR UPDATE''', (session_id,)).fetchone()
        if not session or session['ended_at'] or session['car_id'] != current_car_id:
            raise ValueError('종료되었거나 다른 차량의 세션입니다. 차량을 다시 선택해 주세요.')
        cached = conn.execute('''SELECT question, packet FROM anna_rag.sonata_chat_turns
            WHERE session_id=%s AND request_id=%s''', (session_id, request_id)).fetchone()
        if cached:
            if cached['question'] != question:
                raise ValueError('같은 요청 ID에 다른 질문을 사용할 수 없습니다.')
            return cached['packet']
        if datetime.now(timezone.utc) - session['last_activity_at'] > timedelta(minutes=30):
            raise ValueError('대화가 만료됐어요. 차량을 다시 선택해 주세요.')
        turns = conn.execute('''SELECT question, packet FROM anna_rag.sonata_chat_turns
            WHERE session_id=%s ORDER BY created_at DESC LIMIT 6''', (session_id,)).fetchall()
        history = []
        for turn in reversed(turns):
            history.extend([
                {'role': 'user', 'content': turn['question']},
                {'role': 'assistant', 'content': turn['packet']['answer']['text']},
            ])
        packet = answer_question(service, question, history, on_event)
        conn.execute('''INSERT INTO anna_rag.sonata_chat_turns
            (session_id, request_id, question, packet) VALUES (%s,%s,%s,%s)''',
            (session_id, request_id, question, Jsonb(packet)))
        conn.execute('''UPDATE anna_rag.sonata_chat_sessions SET last_activity_at=now()
            WHERE session_id=%s''', (session_id,))
        return packet


def get_related_images(packet):
    if packet.get('vehicle_id') != 'sonata':
        return []
    images = new_service().select_relevant_images(
        packet['image_question'], packet.get('image_search_results', []),
        limit=3, answer=packet['answer']['text'],
    )
    return [dict(data=image['url'], pdf_page=image['page_no'],
                 caption=image.get('description', '')) for image in images]
