매뉴얼 검색, 한눈에 이해하기
========================================

.. container:: hero

   **PDF 매뉴얼에서 질문과 관련된 내용을 찾아주는 프로그램입니다.**

   예를 들어 “커피가 나오지 않아요”라고 질문하면, 등록된 매뉴얼에서
   관련 페이지와 설명을 찾습니다. 현재 Coffee Search 예제를 기준으로 안내합니다.

.. container:: flow

   **질문 입력** → **의미를 숫자로 변환** → **매뉴얼과 비교** → **관련 페이지 반환**

어디부터 보면 될까요?
------------------------------

.. container:: cards

   .. container:: card

      **01 · 처음 실행한다면**

      준비물과 검색 예제부터 확인하세요.

      :doc:`getting_started`

   .. container:: card

      **02 · 동작이 궁금하다면**

      검색과 PDF 등록을 각각 네 단계로 살펴봅니다.

      :doc:`development_guide`

   .. container:: card

      **03 · 기능을 바꾼다면**

      수정할 파일을 찾고 SQL을 연결하세요.

      :doc:`project_structure` · :doc:`sql_mapper_guide`

먼저 알아둘 세 가지
------------------------------

* **검색 결과는 매뉴얼의 관련 내용입니다.** 현재 서비스에는 답변 문장을 새로 생성하는 단계가 없습니다.
* **검색 전에 PDF가 DB에 등록되어 있어야 합니다.** 등록과 검색은 서로 다른 작업입니다.
* **실제 키와 접속주소는 로컬에만 둡니다.** 문서에는 설정 이름과 역할만 설명합니다.

.. important::

   현재 ``coffee_search.py`` 는 검색 후 **Supabase 이미지 업로드도 실행** 합니다.
   검색만 확인하려면 :doc:`getting_started` 의 별도 예제를 사용하세요.
   PDF 재등록은 해당 머신의 기존 상세 데이터를 교체합니다.

낯선 용어, 쉽게 보기
------------------------------

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - 용어
     - 의미
   * - 임베딩 / 벡터
     - 문장의 의미를 비교할 수 있도록 바꾼 숫자 목록
   * - pgvector
     - PostgreSQL에서 벡터를 저장하고 비교하는 확장 기능
   * - Service
     - PDF 처리, 임베딩, DB 조회의 순서를 정하는 코드
   * - SQL Mapper
     - SQL에 이름을 붙여 Python에서 호출하는 방식
   * - 트랜잭션
     - 여러 DB 변경을 함께 성공시키거나 함께 취소하는 작업 단위

.. toctree::
   :maxdepth: 1
   :caption: 사용 가이드

   getting_started
   development_guide
   project_structure
   sql_mapper_guide
   api
   security
