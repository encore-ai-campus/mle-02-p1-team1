자주 쓰는 API
==============================

**호출할 메서드를 빠르게 찾는 참고표입니다.**
자동 import로 가져오는 대신, 필요한 API만 명시적으로 정리했습니다.
상세 구현은 :doc:`project_structure` 의 파일에서 확인하세요.

SqlSession · SQL 실행
------------------------------

.. code-block:: python

   SqlSession(
       camel_case_keys=True,
       database_manager=None,
       sql_log_mode="combined",
       result_log=False,
       result_log_limit=100,
   )

기본 결과 키는 camelCase입니다. ``result_log_limit`` 은 상세 로그의 행 수 제한이며
검색 결과 개수 제한과는 다릅니다. SQL 호출 예제는 :doc:`sql_mapper_guide` 를 참고하세요.

* ``select_list(statement_id, parameters=None)`` → 조회 결과 목록
* ``select_one(statement_id, parameters=None)`` → 첫 행 또는 ``None``
* ``execute(statement_id, parameters=None)`` → 단건 실행 결과
* ``execute_many(statement_id, parameters_list)`` → 배치 처리 행 수
* ``transaction()`` → 여러 SQL의 반영·취소를 묶는 컨텍스트
* ``register_mappers()`` → SQL 파일 등록
* ``get_pg_engine()`` → 지연 생성한 PGEngine; 현재 Coffee Search 검색에서는 사용하지 않음

CoffeeSearchService · 매뉴얼 처리
----------------------------------------

* ``CoffeeSearchService(sql_session)`` → 검색·등록 서비스 생성
* ``pdf_filter(pdf_docs)`` → 페이지에서 한국어 구간 추출
* ``insert_pdf_docs(brand, machine_name, pdf_filter_docs)`` → 임베딩 생성 후 DB 등록
* ``search_machine_manual(brand, machine_name, question, limit=5)`` → 관련 매뉴얼 목록

등록은 기존 상세를 교체합니다. :doc:`development_guide` 에서 변경 범위를 확인하세요.

공통 도구
------------------------------

* ``DatabaseManager.connect(camel_case_keys=True)`` → 새 PostgreSQL 연결과 벡터 어댑터 준비
* ``DocumentReader(file_path)`` → 읽을 PDF 지정
* ``set_pdf_reader()`` → PDF 리더 준비
* ``set_pdf_doc_list()`` → 페이지별 텍스트를 ``doc_list`` 에 저장

PDF 청크 설정 메서드는 구현 예정이며 현재 등록 흐름에는 쓰이지 않습니다.
