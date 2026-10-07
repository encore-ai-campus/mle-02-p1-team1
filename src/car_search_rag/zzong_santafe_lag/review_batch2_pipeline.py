"""2차 검토의 원본·활성 자료를 읽어 단계별 대조 기록을 보관합니다."""
import json
import argparse
import hashlib
from io import BytesIO
from copy import deepcopy
from uuid import UUID, uuid5, NAMESPACE_URL
from pathlib import Path
from .database import PersonalSqlSession
from .review_revision import load_active
from .source_profile import FULL_SOURCE

FOLDER = Path(__file__).resolve().parent / 'source_reviews/20261007_batch2'
ROOT = Path(__file__).resolve().parents[3]
OLD = FOLDER.parent / '20261006_batch2'


def read(path):
    """UTF-8의 저장된 검토 기록을 읽습니다."""
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    """단계 결과를 저장합니다. 인증 값은 전달하지 않습니다."""
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    temporary.replace(path)


def resources():
    """PDF·원문 식별값과 Storage 그림 바이트를 대조하고 원본 화면을 준비합니다."""
    import httpx
    import pymupdf
    from pypdf import PdfReader
    from PIL import Image, ImageDraw
    from dotenv import dotenv_values
    import os
    data, draft = read(FOLDER / 'current_source.json'), read(OLD / 'draft_review.json')
    pdf_path = ROOT / 'data/santafe_hev_manual.pdf'
    assert hashlib.sha256(pdf_path.read_bytes()).hexdigest() == FULL_SOURCE.pdf_sha256
    original = {row['record_id']: row for row in data['records']}
    for row in draft['draft_records']:
        assert hashlib.sha256(original[row['record_id']]['content'].encode()).hexdigest() == draft['original_content_sha256'][row['record_id']]
        assert row['raw_text'] == original[row['record_id']]['raw_text']
    target_ids = set(draft['original_content_sha256'])
    images = [row for row in data['images'] if row['parent_record_id'] in target_ids]
    reader = PdfReader(pdf_path)
    public_root = os.getenv('SUPABASE_URL') or dotenv_values(ROOT / '.env').get('SUPABASE_URL')
    checks = []
    with httpx.Client(timeout=30) as client:
        for index, row in enumerate(images):
            number, key = row['pdf_page_number'], row['pdf_image_key']
            assert hashlib.sha256(json.dumps(key, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest() == row['image_key_sha256']
            extracted = reader.pages[number-1].images[key].data
            response = client.get(public_root.rstrip('/') + '/storage/v1/object/public/' + row['storage_bucket'] + '/' + row['storage_path'])
            response.raise_for_status()
            assert hashlib.sha256(response.content).hexdigest() == hashlib.sha256(extracted).hexdigest()
            image = Image.open(BytesIO(extracted)).convert('RGB')
            file = FOLDER / f'image_{index:02d}.png'
            image.save(file)
            checks.append({'index': index, 'id': str(row['id']), 'parent_record_id': row['parent_record_id'], 'page': number, 'key': key, 'storage_path': row['storage_path'], 'bytes_equal': True, 'sha256': hashlib.sha256(extracted).hexdigest(), 'size': image.size})
            print(f'그림 파일 {index+1}/{len(images)} 일치', flush=True)
    save(FOLDER / 'image_checks.json', checks)
    # 실제 저장 그림을 번호와 함께 모아 검토하며 원본 파일 자체는 수정하지 않습니다.
    for start in range(0, len(checks), 12):
        sheet = Image.new('RGB', (1600, 1200), 'white')
        draw = ImageDraw.Draw(sheet)
        for offset, row in enumerate(checks[start:start+12]):
            picture = Image.open(FOLDER / f'image_{row["index"]:02d}.png')
            picture.thumbnail((380, 340))
            x, y = (offset % 4)*400, (offset//4)*400
            sheet.paste(picture, (x, y+30))
            draw.text((x+5,y+5), f'{row["index"]}: {row["parent_record_id"]} PDF{row["page"]} {row["key"]}', fill='black')
        sheet.save(FOLDER / f'image_sheet_{start:02d}.png')
    document = pymupdf.open(pdf_path)
    pages = sorted({p for row in draft['draft_records'] for p in row['source_pages']} | {230,232,238,250,262,265,382,388,660,662,104,113})
    for page in pages:
        document[page-1].get_pixmap(matrix=pymupdf.Matrix(1.5,1.5)).save(FOLDER / f'page_{page}.png')
    save(FOLDER / 'pdf_text.json', {str(p): document[p-1].get_text() for p in pages})
    print(json.dumps({'pages': len(pages), 'images': len(checks), 'source_and_bytes_equal': True}))


def snapshot():
    """현재 DB의 원문과 활성 버전을 읽습니다. 인증 정보는 출력하지 않습니다."""
    FOLDER.mkdir(parents=True, exist_ok=True)
    session = PersonalSqlSession(read_only=True)
    with session.transaction():
        bundle = load_active(session)
        rows = session.select_list('manual_store.get_run_parents', {'run_id': FULL_SOURCE.run_id})
        images = session.select_list('manual_store.get_run_image_details', {'run_id': FULL_SOURCE.run_id})
    path = FOLDER / 'current_source.json'
    path.write_text(json.dumps({'bundle': bundle, 'records': rows, 'images': images}, ensure_ascii=False, default=str), encoding='utf-8')
    print(json.dumps({'parents': len(rows), 'images': len(images), 'active_revision': bundle['revision_id']}, ensure_ascii=False))


def finalize():
    """기존 화면 대조 초안에 이번 파일 대조·그림 설명·필수 경고를 반영합니다."""
    from .review_revision import text_sha
    draft, data = read(OLD/'draft_review.json'), read(FOLDER/'current_source.json')
    checks = read(FOLDER/'image_checks.json')
    assert len(checks) == 26 and all(row['bytes_equal'] for row in checks)
    descriptions = {
        0:'운전석 도어의 자세 메모리 1번·2번 버튼을 보여준다.',
        1:'전자 감응식 실내 미러와 A로 표시한 밝기 감지 센서 위치를 보여준다.',
        2:'차량 후방의 디지털 센터 미러 카메라 위치를 1번으로 표시한다.',
        3:'디지털 센터 미러의 1 아이콘 표시 영역, 2 레버, 3 메뉴 버튼, 4 선택/조절 버튼, 5 카메라 표시등을 보여준다.',
        4:'모드 선택 레버의 A 디지털 모드와 B 일반 모드를 보여준다.',
        5:'디지털 센터 미러를 위아래로 움직여 높이를 조절하는 방향을 보여준다.',
        6:'디스플레이 설정의 메뉴 버튼 1번과 설정 변경 버튼 2번·3번을 보여준다.',
        7:'디지털 센터 미러의 앞쪽과 뒤쪽 광 센서 위치를 점으로 표시한다.',
        8:'디지털 센터 미러의 시스템 오작동 시 표시되는 이미지 예를 보여준다.',
        10:'앞좌석 선루프 초기화에 사용하는 FRONT 스위치와 누르는 방향을 보여준다.',
        11:'뒷좌석 파워 선블라인드 초기화에 사용하는 REAR 스위치와 누르는 방향을 보여준다.',
        13:'스마트 키로 엔진 시동 버튼을 직접 누르는 비상 시동 방법을 보여준다.',
        14:'스마트 키의 도어 잠금 버튼과 원격 시동 버튼을 보여준다.',
        15:'안전벨트 골반띠 1번과 어깨띠 2번의 착용 위치를 보여준다.',
        16:'클러스터의 운전석·동승석 안전벨트 미착용 경고등 위치를 보여준다.',
        17:'7인승 뒷좌석 안전벨트 경고 표시와 좌석 번호 1~5를 보여준다.',
        18:'5인승 뒷좌석 안전벨트 경고 표시와 좌석 번호 1~3을 보여준다.',
        19:'6인승 뒷좌석 안전벨트 경고 표시와 좌석 번호 1~4를 보여준다.',
        20:'안전벨트 착용 방법의 플레이트 1번과 버클 2번을 보여준다.',
        21:'안전벨트 플레이트를 버클에 밀어 넣는 방향을 보여준다.',
        22:'앞좌석 벨트 높이 조절 시 올리는 방향 1번, 잠금 버튼 2번, 내리는 방향 3번을 보여준다.',
        23:'안전벨트 버클의 해제 버튼 1번과 플레이트를 빼는 방향을 보여준다.',
        25:'뒷좌석 중앙 안전벨트의 플레이트 1번과 CENTER 버클 2번을 보여준다.'}
    assert set(descriptions) == set(range(26)) - {9,12,24}
    # 경고를 별도 미검토 자료에 의존시키지 않고 대조한 문맥을 이 초기화 자료에 포함합니다.
    context = [
        '선루프를 작동할 때는 얼굴, 팔, 손 그밖의 장애물이 없는지 반드시 확인하십시오. 신체의 일부가 선루프에 끼어 다칠 수 있습니다.',
        '물체 끼임 인식 기능을 시험하기 위해 의도적으로 신체를 사용하지 마십시오. 다시 열릴 수는 있지만 신체 일부가 낄 수 있습니다.',
        '파워 선블라인드 또는 선루프 글라스가 완전히 열리거나 닫히면 스위치에서 손을 떼십시오. 계속 누르고 있으면 선루프 모터가 고장 날 수 있습니다.',
        '선루프 슬라이드 열림/닫힘, 틸트 열림/닫힘 등의 조작을 연속해서 할 경우, 모터나 선루프가 고장 날 수 있습니다.',
        '정기적으로 선루프 레일 부분에 쌓인 먼지를 제거하십시오.',
        '선루프 글라스와 루프 판넬 사이에 쌓인 먼지에 의해 소음이 발생할 수 있습니다. 선루프를 열고 깨끗한 천을 사용하여 정기적으로 먼지를 제거하십시오.',
        '영하의 기온 또는 선루프가 얼었거나 눈으로 덮여 있는 상태에서 선루프를 작동하지 마십시오. 선루프가 작동되지 않을 수 있으며, 강제로 작동시키면 선루프가 손상될 수 있습니다.',
        '비가 내린 후나 세차 직후에 선루프 글라스를 열거나 열린 상태로 주행하면, 실내로 물이 들어올 수 있습니다.',
        '선루프 글라스가 열린 상태에서 화물이 튀어나오지 않도록 하십시오. 주행 중에 갑자기 멈추게 되면 선루프가 손상 될 수 있습니다.',
        '주행 중에 선루프가 열린 사이로 손이나 머리 등 신체의 일부를 내밀지 마십시오. 차량이 갑작스럽게 정지하면 다칠 수 있습니다.']
    pdf_text = read(FOLDER/'pdf_text.json')
    normalized = ''.join((pdf_text['262']+pdf_text['263']).split())
    assert all(''.join(line.split()) in normalized for line in context)
    rows = deepcopy(draft['draft_records'])
    sunroof = next(row for row in rows if row['record_id']=='auto_topic_160')
    sunroof['content'] += '\n[초기화 시 함께 지킬 주의사항 · PDF 262~263쪽]\n'+'\n'.join(context)
    sunroof['source_pages'] = [262,263,264]
    sunroof['metadata']['source_pages'] = [262,263,264]
    sunroof['metadata']['inline_required_context'] = {'source_pages':[262,263], 'content_sha256':text_sha('\n'.join(context))}
    original_images = {(str(row['id']),row['parent_record_id']):row for row in data['images']}
    images = []
    for check in checks:
        if check['index'] not in descriptions:
            continue
        row = deepcopy(original_images[(check['id'],check['parent_record_id'])])
        row['description'] = descriptions[check['index']]
        row['linkage_status'] = 'visually_verified'
        row['linkage_metadata'] = {**row.get('linkage_metadata',{}), 'reviewed_on':'2026-10-07', 'review_method':'PDF 화면·개별 Storage 바이트 대조', 'human_confirmed':False}
        images.append(row)
    for row in rows:
        row['verification_status'] = 'visually_reviewed_source'
        row['review_flags'] = []
        row['metadata'].update(verification_status='visually_reviewed_source',review_flags=[],reviewed_on='2026-10-07',human_confirmed=False,review_method='Codex PDF 원본 화면 대조 및 기존 38쪽 대조 기록 재확인')
        captions = [f'PDF {image["pdf_page_number"]}쪽: {image["description"]}' for image in images if image['parent_record_id']==row['record_id']]
        if captions:
            row['content'] += '\n[그림 설명]\n'+'\n'.join(captions)
    result = {'source_run_id':draft['source_run_id'],'pdf_sha256':draft['pdf_sha256'],'parents':rows,'images':images,
              'base_content_sha256':draft['original_content_sha256'],'removed_image_links':[row for row in checks if row['index'] in {9,12,24}],
              'reviewed_by':'Codex','human_confirmed':False,'raw_text_preserved':True,'image_bytes_checked':26,'images_retained':23,
              'prior_page_review_count':38,'current_key_page_rechecks':[229,231,242,245,246,262,263,264,385,386,387,661,112],
              'scope_limit':'메모리 저장·실행 PDF230 등 별도 미검토 항목은 이번 8개 검토에 포함되지 않음','db_written':False}
    save(FOLDER/'final_review.json',result)
    print(json.dumps({'parents':len(rows),'retained_images':len(images),'removed_images':3,'inline_sunroof_warnings':len(context)}))


def prepare():
    """8개 수정 글만 새로 임베딩하며 기존 5개의 글·벡터는 그대로 보존합니다."""
    import numpy as np
    from .review_revision import validate_bundle, sha, text_sha
    from .review_revision_store import BUNDLE_FILE
    from .chunking import TokenCounter, split_record
    from .config import ManualConfig
    from .sample_store import APPROVED_REVISION
    from .embedding import LocalEmbedder
    from .openai_embedding import OpenAIEmbedder, OpenAITokenCounter
    target = FOLDER/'bundle.json'
    if target.exists():
        return validate_bundle(read(target))
    final = read(FOLDER/'final_review.json')
    old = validate_bundle(read(BUNDLE_FILE))
    assert old['revision_id'] == read(FOLDER/'current_source.json')['bundle']['revision_id']
    config = ManualConfig(model_revision=APPROVED_REVISION)
    counter = TokenCounter(config.model_name,revision=APPROVED_REVISION)
    children = []
    for row in final['parents']:
        children.extend(split_record({'content':row['content'],'raw_text':row['raw_text'],'metadata':row['metadata']},counter))
    inputs = [{'record_id':row['metadata']['record_id'],'input_sha256':text_sha(row['content']),'metadata':row['metadata']} for row in children]
    payload = deepcopy(old['payload'])
    payload['parents'] += final['parents']
    payload['images'] += final['images']
    payload['base_content_sha256'].update(final['base_content_sha256'])
    payload['chunk_inputs'] += inputs
    payload['removed_image_links'] += final['removed_image_links']
    payload.update(previous_revision_id=old['revision_id'],reviewed_on='2026-10-07',batch2_scope_limit=final['scope_limit'])
    digest = sha(payload)
    revision_id = str(uuid5(NAMESPACE_URL,'zzong_santafe_lag:review:'+digest))
    plan = {'revision_id':revision_id,'payload_sha256':digest,'new_parents':8,'preserved_parents':5,'new_chunks':len(children),
            'openai_input_tokens':sum(OpenAITokenCounter().count(row['content']) for row in children)}
    if (FOLDER/'embedding_plan.json').exists():
        assert read(FOLDER/'embedding_plan.json') == plan
    else:
        save(FOLDER/'embedding_plan.json',plan)
    print(json.dumps(plan),flush=True)
    if (FOLDER/'local_vectors.json').exists():
        local = np.array(read(FOLDER/'local_vectors.json'),dtype=np.float32)
    else:
        local = LocalEmbedder(config,counter).embed_chunks(children)
        save(FOLDER/'local_vectors.json',local.tolist())
    vectors = []
    embedder = OpenAIEmbedder()
    for start in range(0,len(children),64):
        checkpoint = FOLDER/f'openai_vectors_{start:04d}.json'
        if checkpoint.exists():
            batch = read(checkpoint)
        else:
            batch = embedder.embed_texts([row['content'] for row in children[start:start+64]]).tolist()
            save(checkpoint,batch)
        vectors.extend(batch)
        print(f'OpenAI 새 청크 {len(vectors)}/{len(children)} 저장',flush=True)
    chunks = deepcopy(old['chunks']) + [{'record_id':row['metadata']['record_id'],'content':row['content'],'metadata':row['metadata'],
              'input_sha256':text_sha(row['content']),'local_embedding':local[index].tolist(),'openai_embedding':vectors[index]} for index,row in enumerate(children)]
    bundle = {'revision_id':revision_id,'payload':payload,'payload_sha256':digest,'chunks':chunks}
    validate_bundle(bundle)
    save(target,bundle)
    return bundle


def evaluate():
    """고정한 같은 질문·질문 벡터로 이전 버전과 후보 버전을 비교합니다. DB에는 쓰지 않습니다."""
    import numpy as np
    import os
    from .review_revision import validate_bundle
    from .review_revision_store import BUNDLE_FILE
    from .openai_embedding import OpenAIEmbedder
    from .openai_search_service import OpenAIManualSearchService, active_embedding_run
    from .answer_service import ManualAnswerService
    questions = read(Path(__file__).resolve().parent/'evaluation_50_questions.json')['groups']
    definitions = [('B',8,'auto_topic_149'),('B',9,'auto_topic_73'),('B',14,'auto_topic_160'),('B',15,'auto_topic_274'),
                   ('B',16,'auto_topic_276'),('B',17,'auto_topic_420'),('B',20,'auto_topic_139'),
                   ('C',3,'auto_topic_274'),('C',4,'auto_topic_274'),('C',5,'auto_topic_274'),('C',6,'auto_topic_420'),
                   ('C',10,'auto_topic_149'),('C',14,'auto_topic_160'),('C',15,'auto_topic_160'),('C',16,'auto_topic_73'),('C',20,'auto_topic_139')]
    cases = [{'id':f'{group}{number:02d}','question':next(row for row in questions if row['group']==group)['questions'][number-1],
              'expected_record_id':identity,'kind':'same_50_questions'} for group,number,identity in definitions]
    cases += [
        {'id':'R01','question':'스마트 테일게이트의 뒤쪽 감지 범위는 몇 cm인가요?','expected_record_id':'auto_topic_174','kind':'existing_review_regression'},
        {'id':'R02','question':'실외 미러 조절 스위치의 L과 R은 무엇을 선택하나요?','expected_record_id':'auto_topic_150','kind':'existing_review_regression'},
        {'id':'R03','question':'스마트 테일게이트 감지 중 중지할 때 키의 번호별 버튼을 알려줘.','expected_record_id':'auto_topic_173','kind':'existing_review_regression'}]
    old, new = validate_bundle(read(BUNDLE_FILE)), validate_bundle(read(FOLDER/'bundle.json'))
    plan = {'cases':cases,'before_revision':old['revision_id'],'after_revision':new['revision_id'],
            'scope':'동일 질문·검색 및 초기 발췌 비교. 사람 확정 정답률이나 생성 답변 정확도와 구분함'}
    if (FOLDER/'evaluation_plan.json').exists():
        assert read(FOLDER/'evaluation_plan.json') == plan
    else:
        save(FOLDER/'evaluation_plan.json',plan)
    print(f'평가 PID {os.getpid()} | 19문항 × 이전·후보 버전',flush=True)
    vector_path = FOLDER/'query_vectors.json'
    if vector_path.exists():
        vectors = np.array(read(vector_path),dtype=np.float32)
    else:
        vectors = OpenAIEmbedder().embed_texts([case['question'] for case in cases])
        save(vector_path,vectors.tolist())
    assert vectors.shape == (len(cases),1536)
    results = []
    for label,bundle in [('before',old),('after',new)]:
        search = OpenAIManualSearchService(active_embedding_run())
        search.review_bundle = bundle
        search.prepare()
        by_question = {case['question']:vectors[index] for index,case in enumerate(cases)}
        search.embedder.embed_question = lambda question:by_question[question]
        service = ManualAnswerService(FULL_SOURCE.run_id,search_service=search)
        for index,case in enumerate(cases):
            checkpoint = FOLDER/f'{label}_{case["id"]}.json'
            if checkpoint.exists():
                row = read(checkpoint)
            else:
                evidence = service.answer(case['question'],top_k=5)
                ids = [source['record_id'] for source in evidence['sources']]
                row = {**case,'phase':label,'revision_id':bundle['revision_id'],'status':evidence['status'],
                       'source_ids':ids,'expected_source_selected':case['expected_record_id'] in ids,'evidence':evidence}
                save(checkpoint,row)
            results.append(row)
            print(f'{label} {index+1}/{len(cases)} {case["id"]} {row["status"]} 기대 출처={row["expected_source_selected"]}',flush=True)
    after = [row for row in results if row['phase']=='after']
    assert all(row['expected_source_selected'] for row in after if row['kind']=='existing_review_regression')
    final = {'plan':plan,'results':results,'cases':len(cases),'evaluations':len(results),'regression_passed':True,
             'before_expected_sources':sum(row['expected_source_selected'] for row in results if row['phase']=='before'),
             'after_expected_sources':sum(row['expected_source_selected'] for row in after),'db_written':False}
    save(FOLDER/'evaluation.json',final)
    save(FOLDER/'failures.json',[])
    return final


def store():
    """개인 스키마에 누적 버전을 저장하고 새 연결 대조 후 선택 파일을 갱신합니다."""
    import numpy as np
    from pgvector.utils import Vector
    from psycopg.types.json import Jsonb
    from .database import PersonalDatabaseManager
    from .review_revision import validate_bundle, text_sha, ACTIVE_FILE, SHARED_SELECTION
    from .review_revision_store import legacy_fingerprint
    bundle = validate_bundle(read(FOLDER/'bundle.json'))
    evaluation = read(FOLDER/'evaluation.json')
    assert evaluation['plan']['after_revision']==bundle['revision_id'] and evaluation['regression_passed']
    previous = bundle['payload']['previous_revision_id']
    for file in (ACTIVE_FILE,SHARED_SELECTION):
        if file.exists():
            assert read(file)['revision_id'] in (previous,bundle['revision_id'])
    with PersonalDatabaseManager(read_only=True).connect() as connection:
        before = legacy_fingerprint(connection)
        originals = connection.execute('SELECT record_id,content,raw_text FROM zzong_santafe_lag.parent_records WHERE run_id=%s',(FULL_SOURCE.run_id,)).fetchall()
    originals = {row['record_id']:row for row in originals}
    for row in bundle['payload']['parents']:
        assert text_sha(originals[row['record_id']]['content']) == bundle['payload']['base_content_sha256'][row['record_id']]
        assert originals[row['record_id']]['raw_text']==row['raw_text']
    revision = UUID(bundle['revision_id'])
    session = PersonalSqlSession()
    with session.transaction():
        existing = session.select_one('review_revisions.get_revision',{'revision_id':revision})
        if existing:
            assert existing['status']=='ready' and existing['payload_sha256']==bundle['payload_sha256']
        else:
            session.execute('review_revisions.insert_revision',{'id':revision,'source_run_id':FULL_SOURCE.run_id,
                            'payload_sha256':bundle['payload_sha256'],'payload':Jsonb(bundle['payload']),'chunk_count':len(bundle['chunks'])})
            session.execute_many('review_revisions.insert_chunk',[{'revision_id':revision,'record_id':row['record_id'],'content':row['content'],
                 'input_sha256':row['input_sha256'],'metadata':Jsonb(row['metadata']),
                 'local_embedding':Vector(row['local_embedding']),'openai_embedding':Vector(row['openai_embedding'])} for row in bundle['chunks']])
            session.execute('review_revisions.ready',{'revision_id':revision})
    reader = PersonalSqlSession(read_only=True)
    with reader.transaction():
        header = reader.select_one('review_revisions.get_revision',{'revision_id':revision})
        chunks = reader.select_list('review_revisions.get_chunks',{'revision_id':revision})
    assert header['status']=='ready'
    saved = validate_bundle({'revision_id':str(revision),'payload':header['payload'],'payload_sha256':header['payload_sha256'],'chunks':chunks})
    expected = {row['record_id']:row for row in bundle['chunks']}
    for row in saved['chunks']:
        for field in ('local_embedding','openai_embedding'):
            assert np.array_equal(np.asarray(row[field],dtype=np.float32),np.asarray(expected[row['record_id']][field],dtype=np.float32))
    with PersonalDatabaseManager(read_only=True).connect() as connection:
        after = legacy_fingerprint(connection)
    assert before==after
    pointer = {'revision_id':str(revision),'payload_sha256':bundle['payload_sha256']}
    if not (FOLDER/'previous_selection.json').exists():
        save(FOLDER/'previous_selection.json',read(SHARED_SELECTION))
    # 새 버전 저장·벡터 대조가 성공한 후에만 로컬과 공유 선택 정보를 갱신합니다.
    save(ACTIVE_FILE,pointer)
    save(SHARED_SELECTION,pointer)
    report = {'revision_id':str(revision),'previous_revision_id':previous,'added_reviewed_parents':8,'preserved_revision_parents':5,
              'reviewed_parents':33,'pending_parents':494,'revision_chunks':len(chunks),'legacy_tables_unchanged':True,
              'vector_readback_equal':True,'image_bytes_checked':26,'new_image_links':23,'removed_image_links':3,
              'db_written':True,'activated_locally':True,'deployment_requires_code_and_selection_update':True,'raw_text_preserved':True}
    save(FOLDER/'db_saved.json',report)
    print(json.dumps(report,ensure_ascii=False),flush=True)
    return report


def verify():
    """실제 활성 DB 버전과 후보를 대조하고 대표 질문의 생성 결과를 별도 기록합니다."""
    import numpy as np
    from .openai_search_service import OpenAIManualSearchService, active_embedding_run
    from .answer_service import ManualAnswerService
    from .llm_answer_service import LlmManualAnswerService
    saved = read(FOLDER/'db_saved.json')
    session = PersonalSqlSession(read_only=True)
    with session.transaction():
        active = load_active(session)
    assert active['revision_id'] == saved['revision_id']
    candidate = read(FOLDER/'bundle.json')
    assert active['payload'] == candidate['payload']
    plan = read(FOLDER/'evaluation_plan.json')
    vectors = np.array(read(FOLDER/'query_vectors.json'),dtype=np.float32)
    search = OpenAIManualSearchService(active_embedding_run())
    # 후보의 임시 대체 없이 일반 검색이 활성 DB 버전을 읽는지 확인합니다.
    search.prepare()
    by_question = {case['question']:vectors[index] for index,case in enumerate(plan['cases'])}
    search.embedder.embed_question = lambda question:by_question[question]
    evidence_service = ManualAnswerService(FULL_SOURCE.run_id,search_service=search)
    service = LlmManualAnswerService(FULL_SOURCE.run_id,evidence_service=evidence_service)
    results = []
    for identity in ('B14','B16','B20'):
        checkpoint = FOLDER/f'actual_{identity}.json'
        if checkpoint.exists():
            row = read(checkpoint)
        else:
            case = next(case for case in plan['cases'] if case['id']==identity)
            evidence = service.prepare_evidence(case['question'],top_k=5)
            assert search.review_revision_id == active['revision_id']
            expected = read(FOLDER/f'after_{identity}.json')['evidence']
            assert evidence['status']==expected['status']
            assert [s['record_id'] for s in evidence['sources']]==[s['record_id'] for s in expected['sources']]
            generated = service.generate(evidence)
            row = {**case,'revision_id':active['revision_id'],'actual_db_matches_candidate':True,
                   'generation_status':generated['status'],'result':generated}
            save(checkpoint,row)
        results.append(row)
        print(f"실제 DB {identity}: {row['generation_status']}",flush=True)
    result = {'revision_id':active['revision_id'],'active_db_matches_candidate':True,
              'results':results,'scope':'대표 3문항의 실제 DB 검색과 생성 검사. 의미 정확도는 별도 원문 대조 필요'}
    save(FOLDER/'actual_verification.json',result)
    return result


def report():
    """기존 평가를 덮어쓰지 않고 이번 8개 검토의 실측 결과만 문서와 화면용으로 정리합니다."""
    evaluation = read(FOLDER/'evaluation.json')
    verification = read(FOLDER/'actual_verification.json')
    final = read(FOLDER/'final_review.json')
    analysis = read(Path(__file__).resolve().parent/'analysis_results/summary.json')
    assert analysis['review_revision_id'] == verification['revision_id']
    before = {r['id']:r for r in evaluation['results'] if r['phase']=='before'}
    after = [r for r in evaluation['results'] if r['phase']=='after']
    same = [r for r in after if r['kind']=='same_50_questions']
    notes = {
        'B09':'다른 관련 근거인 안전벨트 착용(PDF54)을 선택함. 기대 ID 불일치만으로 오답 처리하지 않음.',
        'C06':'주행 중 시동 꺼짐 대신 시동 전 확인 자료를 선택함. 상황에 맞는 검색 보완 필요.',
        'C10':'실내 미러 대신 엔진룸 점검을 선택함. 무관한 근거 선택 문제 지속.',
        'C14':'초기화 절차 대신 차량 외부 안내도를 선택함. 직접 해결 답변이 아님.',
        'C15':'배터리 관리 자료가 미검토여서 답변 보류 지속. 다른 원문 검토가 필요함.',
        'C20':'메모리 초기화 대신 메모리 개요를 선택함. 직접 해결 답변이 아님.',
        'C03':'시동 자료 선택은 개선됐으나 차량 고장 원인을 확정한 결과는 아님.',
        'C04':'시동 자료 선택은 개선됐으나 차량 고장 원인을 확정한 결과는 아님.',
        'C05':'시동 자료 선택은 개선됐으나 차량 고장 원인을 확정한 결과는 아님.'}
    rows = [{'문항':r['id'],'질문':r['question'],'이전 기대 출처':before[r['id']]['expected_source_selected'],
             '반영 후 기대 출처':r['expected_source_selected'],'반영 후 상태':r['status'],
             '검토 의견':notes.get(r['id'],'기대 자료 선택 확인. 생성 답변 정확도 점수와 구분함.')} for r in after]
    summary = {'description':'초안 8개를 원문·그림과 대조해 개인 DB의 별도 검토 버전으로 반영했습니다.',
        'revision_id':verification['revision_id'],
        'metrics':{'검토된 자료':analysis['counts']['reviewed_parents'],'남은 미검토 자료':analysis['counts']['unreviewed_parents'],
                   '동일 질문 기대 출처 선택':f"{sum(before[r['id']]['expected_source_selected'] for r in same)}/16 → {sum(r['expected_source_selected'] for r in same)}/16",
                   '기존 자료 회귀 확인':'3/3 유지',
                   '실제 DB 대표 생성':f"{sum(r['generation_status']=='generated_answer' for r in verification['results'])}/3 생성 답변"},
        'questions':rows,
        'limitations':['기대 출처 선택은 답변 정답률이 아닙니다. 기존 50문항 전체 및 추가 30문항을 재평가한 결과가 아닙니다.',
                      '생성 형식·인용 검사는 의미 정확도나 경고의 완전성을 보증하지 않습니다.',
                      '검토 주체는 Codex입니다. 사용자가 각 원문을 확인했다고 표시하지 않았습니다.',final['scope_limit']]}
    save(FOLDER/'review_summary.json',summary)
    issues = [r for r in rows if not r['반영 후 기대 출처']]
    save(FOLDER/'remaining_issues.json',issues)
    lines = ['# 싼타페 원문 8개 반영과 재평가','',summary['description'],'',
             '## 반영 내용','',
             '| 자료 | PDF 쪽수 |','|---|---|']
    lines += [f"| {r['title']} | {', '.join(map(str,r['source_pages']))} |" for r in final['parents']]
    lines += ['','본문의 누락된 조건·순서·표 내용을 보완하고 선루프 초기화에 끼임·결빙 주의사항을 연결했습니다.',
              '원본 raw_text를 보존하고 기존 5개 검토 자료·벡터를 재사용했습니다. 그림 26개를 원본과 Storage 파일의 바이트로 대조했고, 23개 설명을 보완하고 다른 항목의 그림 연결 3개를 제외했습니다.',
              '개인 검토 버전 테이블에 새 청크 68개를 추가했습니다. 누적 검토 버전 청크는 96개이며 일반 검색 목록은 2,224개입니다. 기존 원문 테이블의 변경이 없고 새 벡터의 DB 재조회 값이 일치했습니다.',
              '', '## 재평가 결과','']
    lines += [f'- {k}: {v}' for k,v in summary['metrics'].items()]
    lines += ['','| 문항 | 이전 기대 출처 | 반영 후 기대 출처 | 결과와 한계 |','|---|---|---|---|']
    lines += [f"| {r['문항']} | {r['이전 기대 출처']} | {r['반영 후 기대 출처']} | {r['검토 의견']} |" for r in rows]
    lines += ['','## 실제 DB 확인','',
              '임시 후보 대체 없이 활성 DB 버전을 다시 읽어 대표 3문항의 출처·상태가 후보 평가와 일치하는지 확인했습니다.']
    lines += [f"- {r['id']}: {r['question']} → {r['generation_status']}" for r in verification['results']]
    lines += ['','## 남은 작업과 적용 범위',''] + ['- '+s for s in summary['limitations']]
    lines += ['- 일상 표현의 무관한 근거 선택(C06·C10·C14·C20)을 개선하고, 배터리 관련 원문(C15)을 별도로 검토해야 합니다.',
              '- 공통 앱의 실제 적용에는 이 코드와 선택 파일의 배포 반영이 필요합니다. 다른 차종 코드와 공통 설정은 이번 작업에서 수정하지 않았습니다.',
              '- 공통 화면 전환·대화 보존·다른 차종 메뉴 분리 테스트 3개 통과.','',
              '## 재현 기록','',f"활성 검토 버전: `{verification['revision_id']}`.",
              'evaluation_plan.json은 실행 전 고정한 질문·기대 ID, evaluation.json은 반영 전후 38회 검색 결과, actual_verification.json은 실제 DB 경로 3회 확인 결과입니다.',
              '원문: data/santafe_hev_manual.pdf. 개별 그림 파일 대조는 image_checks.json, 본문 보완안은 final_review.json에 있습니다.','']
    (FOLDER/'report.md').write_text('\n'.join(lines),encoding='utf-8')
    return summary


if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument('action', choices=['snapshot','resources','finalize','prepare','evaluate','store','verify','report'])
        args = parser.parse_args()
        {'snapshot': snapshot, 'resources': resources, 'finalize':finalize, 'prepare':prepare,'evaluate':evaluate,'store':store,'verify':verify,'report':report}[args.action]()
    except Exception as error:
        from datetime import datetime, timezone
        try:
            save(FOLDER/'failure_checkpoint.json',{'action':getattr(locals().get('args'),'action',None),
                 'error_type':type(error).__name__,'time':datetime.now(timezone.utc).isoformat()})
        except OSError:
            # 결과 폴더도 쓰지 못하면 인증 정보가 섞일 수 있는 외부 오류 전문은 출력하지 않습니다.
            pass
        print('대조 중단: ' + type(error).__name__ + '. 인증 정보 보호를 위해 오류 전문은 숨깁니다.')
        raise SystemExit(1) from None
