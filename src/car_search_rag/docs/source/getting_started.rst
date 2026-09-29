시작하기
========

환경 변수와 DB
------------------

실행 환경에 ``DB_URL`` 과 ``OPENAI_API_KEY`` 를 설정합니다. ``.env`` 파일을 사용할 수도 있습니다. ``DatabaseManager`` 는 생성 시 ``load_dotenv()`` 를 호출하고, ``connect()`` 에서 ``DB_URL`` 로 psycopg 연결을 만듭니다. ``OpenAIEmbeddings`` 는 문서 등록과 질문 검색에서 API 키를 사용합니다. 키와 접속 문자열을 소스나 문서에 직접 넣지 마세요.

DB에는 PostgreSQL의 pgvector 타입, ``CFF_MACH`` 및 ``CFF_MACH_DTL`` 테이블, ``FN_GEN_BIZ_ID`` 함수가 필요합니다. 연결 직후 ``DatabaseManager`` 가 pgvector 어댑터를 등록합니다. SQL의 실제 테이블·컬럼·함수 이름은 :doc:`development_guide` 와 ``coffee_search.sql`` 을 참고하세요. PDF 등록에 쓰는 파일은 ``src/group_project/data/에센자미니_c30.pdf`` 입니다.

실행
----

현재 검색 테스트는 다음 명령으로 실행합니다.

.. code-block:: powershell

   python src/group_project/car_search_rag/car_search/coffee_search.py

스크립트는 ``sys.path`` 에 ``src`` 와 ``src/group_project`` 를 추가하고 ``SqlSession(result_log=True)`` 및 ``CoffeeSearchService`` 를 생성합니다.

등록과 검색의 차이
--------------------

현재 활성 코드는 ``search_machine_manual()`` 에 브랜드 ``네스프레소 ``, 모델 `` 에센자 미니 ``, 질문 `` 커피가 나오지 않을 때 어떻게 해야 하나요?``, ``limit=5`` 를 전달합니다. 실행 시 질문 임베딩 API와 DB 검색이 수행됩니다. 기존 매뉴얼 데이터가 없으면 검색 결과는 비어 있을 수 있습니다.

``coffee_machine_register()`` 와 ``CoffeeSearch`` 의 PDF 읽기 경로는 구현되어 있지만 파일 하단의 등록 호출 예시는 **주석 처리** 되어 있습니다. 등록을 활성화하면 PDF 텍스트 임베딩과 DB 쓰기가 발생하고 대상 머신의 기존 ``CFF_MACH_DTL`` 을 삭제한 뒤 다시 넣습니다. 실행 전에 :doc:`development_guide` 의 등록 흐름을 확인하세요.

정상 실행 확인
----------------

기본 검색 실행에서는 터미널에 ``질문 :`` 과 입력 질문이 표시됩니다. ``SqlSession`` 의 ``QUERY [coffee_search.search_machine_manual]`` 및 ``RESULT`` 로그로 실행 SQL과 결과 건수를 확인할 수 있습니다. 현재 메인 스크립트는 ``search_docs`` 를 변수에 받지만 검색 결과의 행 자체는 별도 ``print`` 로 출력하지 않습니다. 조회 행을 확인하려면 ``result_log=True`` 의 ``RESULT DATA`` 로그를 봅니다. 오류가 나면 DB 연결, pgvector 타입, API 키, 필요한 테이블을 먼저 확인하세요.
