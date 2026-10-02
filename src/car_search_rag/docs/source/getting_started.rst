처음 검색해 보기
==============================

**목표: 등록된 매뉴얼을 검색하고, 결과 건수만 확인합니다.**

1. 준비물을 확인하세요
--------------------------------

* Python 3.12 이상과 프로젝트 의존성 설치 환경
* pgvector가 준비된 PostgreSQL
* ``CFF_MACH``, ``CFF_MACH_DTL`` 테이블과 ``FN_GEN_BIZ_ID`` 함수
* 검색할 브랜드·모델의 매뉴얼 데이터
* 임베딩 API를 사용할 수 있는 키

저장소 루트에서 프로젝트 의존성을 설치합니다.

.. code-block:: console

   uv sync

2. 설정은 로컬에 보관하세요
--------------------------------

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - 환경변수 이름
     - 용도
   * - ``DB_URL``
     - PostgreSQL 연결 설정
   * - ``OPENAI_API_KEY``
     - 질문과 문서를 임베딩하는 API 인증

실제 값은 로컬 환경변수 또는 버전 관리에서 제외한 ``.env`` 에 설정합니다.
``DatabaseManager`` 는 환경설정 파일을 읽습니다. 값은 터미널 출력이나 문서에 복사하지 마세요.
파일을 쓰기 전에 :doc:`security` 의 Git 제외 확인을 따라 주세요.

3. 검색 전용 예제를 실행하세요
--------------------------------------

다음 내용을 저장소 루트의 ``search_manual_local.py`` 에 저장합니다.
이 예제는 등록과 이미지 업로드를 호출하지 않으며, 결과 건수만 출력합니다.
질문 임베딩 API 호출에는 비용이 발생할 수 있습니다.

.. code-block:: python

   import logging
   import sys
   from pathlib import Path

   sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

   from car_search_rag.common.sql_session import SqlSession
   from car_search_rag.car_search.coffee_search_service import CoffeeSearchService

   # SQL 파라미터와 결과 원문이 INFO 로그에 나타나지 않게 설정합니다.
   logging.getLogger("car_search_rag.sql").disabled = True
   session = SqlSession(sql_log_mode="none", result_log=False)
   service = CoffeeSearchService(sql_session=session)
   results = service.search_machine_manual(
       brand="네스프레소",
       machine_name="에센자 미니",
       question="커피가 나오지 않을 때 어떻게 해야 하나요?",
       limit=5,
   )
   print(f"검색 결과: {len(results)}건")

.. code-block:: console

   uv run python search_manual_local.py

**예상 결과:** ``검색 결과: N건``. 위 예제에서 N은 0~5입니다.
0건이면 해당 브랜드·모델의 등록 여부와 이름이 정확히 일치하는지 확인하세요.
결과에는 관련 페이지 번호, 매뉴얼 텍스트, 유사도 등이 들어 있습니다.

막혔을 때 확인할 곳
--------------------------------

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - 증상
     - 확인할 내용
   * - 모듈을 찾지 못함
     - 루트에 예제를 저장했는지, ``uv sync`` 가 완료됐는지 확인
   * - DB 연결 실패
     - 로컬 연결 설정과 네트워크 접근 권한 확인
   * - 테이블·vector 타입 오류
     - DB 스키마와 pgvector 준비 상태 확인
   * - API 인증 실패
     - 로컬 키 설정과 해당 키의 사용 권한 확인
   * - 결과가 0건
     - 매뉴얼 등록 여부, 브랜드명, 모델명 확인

오류를 공유할 때는 접속주소·인증값·개인정보를 먼저 제거하세요.
다음으로 :doc:`development_guide` 에서 검색과 등록의 차이를 살펴보세요.
