API Reference
==========================

현재 공통 클래스의 docstring과 메서드 시그니처를 소스에서 가져옵니다. 호출 순서는 :doc:`development_guide`, Mapper 예시는 :doc:`sql_mapper_guide` 를 참고하세요. ``coffee_search.py`` 는 import 시 검색 테스트를 실행하는 구조이므로 이 페이지에서 autodoc으로 import하지 않습니다.

SqlSession
--------------------

``SqlSession`` 은 Mapper 등록, 조회·변경, 배치, 트랜잭션, 로그와 PGEngine 접근을 제공합니다. 현재 Coffee Search에서는 ``get_pg_engine()`` 대신 psycopg 기반 Mapper 호출을 사용합니다.

.. autoclass:: group_project.common.sql_session.SqlSession
   :members: register_mappers, select_list, select_one, execute, execute_many, transaction, get_pg_engine
   :member-order: bysource

DatabaseManager
------------------------------

``connect()`` 는 호출마다 새 연결을 생성하고 pgvector 타입을 등록합니다. ``SqlSession`` 이 연결의 사용 범위를 관리합니다.

.. autoclass:: group_project.common.database_manager.DatabaseManager
   :members: connect
   :member-order: bysource

DocumentReader
----------------------------

Coffee Search는 아래 두 메서드를 순서대로 호출한 뒤 ``doc_list`` 를 읽습니다. ``set_pdf_chunk_doc_list()`` 는 현재 구현 예정 표시만 있으므로 API 목록에서 제외합니다.

.. autoclass:: group_project.common.document_reader.DocumentReader
   :members: set_pdf_reader, set_pdf_doc_list
   :member-order: bysource

CoffeeSearchService
--------------------------------------

서비스는 PDF 한국어 구간 필터, 등록, 상세 배치, 질문 검색을 구현합니다. 각 메서드의 호출 순서와 SQL statement는 :doc:`development_guide` 에 정리했습니다.

.. autoclass:: group_project.car_search_rag.car_search.coffee_search_service.CoffeeSearchService
   :members: pdf_filter, insert_pdf_docs, insert_machine_details, search_machine_manual
   :member-order: bysource

결과 키 변환 함수
--------------------

.. autofunction:: group_project.common.database_manager.snake_to_camel

.. autofunction:: group_project.common.database_manager.camel_dict_row

``common/vector_store_manager.py`` 에는 현재 공개할 클래스나 함수가 없습니다.
