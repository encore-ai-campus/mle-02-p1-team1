프로젝트 구조
==============

경로 기준
----------

다음 트리는 ``src/group_project/`` 에서 시작합니다. 저장소 루트에는 ``pyproject.toml``, ``uv.lock``, ``requirements.txt`` 와 ``.env`` 가 있습니다. ``__pycache__`` 와 HTML 빌드 산출물은 생략했습니다.

.. code-block:: text

   group_project/
   ├─ AGENTS.md
   ├─ common/
   │  ├─ database_manager.py
   │  ├─ document_reader.py
   │  ├─ sql_session.py
   │  └─ vector_store_manager.py
   ├─ data/
   │  └─ 에센자미니_c30.pdf
   ├─ car_search_rag/
   │  ├─ AGENTS.md
   │  ├─ run_car_search.bat
   │  └─ car_search/
   │     ├─ coffee_search.py
   │     ├─ coffee_search_service.py
   │     ├─ coffee_search.sql
   │     ├─ document.py / document_service.py / document.sql
   │     ├─ query_examples.py / query_examples_service.py / query_examples.sql
   │     └─ transaction_sample.py / transaction_sample_service.py / transaction_sample.sql
   └─ docs/
      ├─ source/               (이 HTML 사이트의 원본 RST와 _static 이미지)
      ├─ build_html.bat
      ├─ development_guide.md
      ├─ sql_mapper.md
      ├─ coffee_search_structure.png
      ├─ sql_mapper_structure.png
      └─ sql_mapper_structure_simple.png

파일별 책임
------------

``coffee_search.py`` 는 실행 진입점과 PDF 읽기용 ``CoffeeSearch`` 를 정의합니다. ``coffee_search_service.py`` 는 등록·검색의 업무 순서와 임베딩 호출을 담당합니다. ``coffee_search.sql`` 은 데이터 조회·등록·삭제·유사도 검색 SQL을 담습니다. 이 세 파일이 Coffee Search 기능 세트입니다. 다른 ``document``, ``query_examples``, ``transaction_sample`` 세트도 같은 디렉터리에 있으며 별도의 실행 예제를 제공합니다.

``common/sql_session.py`` 는 ``group_project/`` 아래의 모든 ``*.sql`` 을 재귀적으로 읽습니다. 별도의 ``mapper/`` 디렉터리나 ``__init__.py`` 를 요구하지 않습니다. ``database_manager.py`` 는 PostgreSQL 연결과 pgvector 타입 등록, ``document_reader.py`` 는 PDF 페이지 텍스트 추출을 담당합니다. ``vector_store_manager.py`` 는 **현재 빈 파일** 입니다.

``docs/source/`` 는 이 사이트의 편집 대상이고 ``docs/build/html/`` 은 생성 결과입니다. 루트의 ``docs/development_guide.md`` 는 Markdown 참고본입니다. 사이트 내용을 바꾸려면 해당 RST도 수정하고 빌드해야 합니다. 구조 그림에는 현재 없는 예시 파일명과 메서드가 있으므로 실제 경로와 동작은 이 문서와 소스를 우선합니다.

변경 위치를 고를 때
----------------------

* SQL statement: 해당 기능의 ``.sql`` 파일에 ``-- name:`` 추가
* Coffee Search 업무 순서·필터·검색: ``coffee_search_service.py``
* 실행 시 입력과 출력: ``coffee_search.py``
* PDF 읽기 공통 처리: ``common/document_reader.py``
* SQL 실행·트랜잭션 공통 기능: ``common/sql_session.py``
* DB 연결 설정·타입 등록: ``common/database_manager.py``

Mapper 호출 규칙과 트랜잭션 경계는 :doc:`sql_mapper_guide`, 실제 호출 흐름은 :doc:`development_guide` 를 참고하세요.
