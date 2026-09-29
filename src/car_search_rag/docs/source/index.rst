SQL Mapper / Coffee Search 개발 문서
================================================================

이 사이트는 현재 ``src/group_project`` 소스를 기준으로 공통 DB 모듈과 Coffee Search 프로그램의 구조, 실행, 확장 방법을 설명합니다. 진입점은 ``car_search_rag/car_search/coffee_search.py`` 이고 SQL은 같은 디렉터리의 ``coffee_search.sql`` 에 있습니다.

빠른 시작
----------

* 처음 실행할 때: :doc:`getting_started` — 환경, DB 조건, 실행 명령
* 전체 호출 흐름을 볼 때: :doc:`development_guide` — PDF 등록과 질문 검색
* SQL을 추가하거나 연결을 묶을 때: :doc:`sql_mapper_guide` — Mapper, 로그, Transaction
* 파일을 찾을 때: :doc:`project_structure` — 현재 디렉터리와 변경 위치
* 메서드 시그니처를 볼 때: :doc:`api` — 공통 클래스와 서비스 API

주요 구성
----------

``common/`` 의 ``SqlSession`` 은 SQL Mapper 등록·실행·트랜잭션을 담당하고 ``DatabaseManager`` 를 통해 필요할 때 PostgreSQL 연결을 만듭니다. ``DocumentReader`` 는 PDF를 페이지별 문서 목록으로 바꿉니다. ``CoffeeSearchService`` 는 한국어 구간 필터링, OpenAI 임베딩, ``CFF_MACH``/``CFF_MACH_DTL`` 등록과 pgvector 유사도 검색을 조합합니다. ``common/vector_store_manager.py`` 는 현재 빈 파일입니다.

.. important::

   현재 기본 실행은 **검색 테스트** 입니다. PDF 등록 호출은 ``coffee_search.py`` 에서 주석 처리되어 있습니다. 등록을 활성화하면 기존 머신 상세 데이터를 삭제·재등록하고 OpenAI 임베딩 API를 호출합니다.

문서 목차
----------

.. toctree::
   :maxdepth: 2
   :caption: 개발 문서

   getting_started
   development_guide
   sql_mapper_guide
   project_structure
   api

문서와 코드가 다르면 현재 소스를 우선합니다. 이 사이트의 원본은 ``docs/source/`` 이며 ``docs/build_html.bat`` 로 ``docs/build/html/`` 을 다시 생성합니다.
