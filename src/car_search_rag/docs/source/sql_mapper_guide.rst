SQL 추가하고 호출하기
================================

**SQL 파일에 이름을 붙이고, Python에서 그 이름으로 호출합니다.**

1. SQL에 이름을 붙입니다
--------------------------------

``coffee_search.sql`` 에 정의된 조회 예제입니다.

.. code-block:: sql

   -- name: select_machine
   SELECT CFF_MACH_ID AS ID
   FROM PUBLIC.CFF_MACH
   WHERE CFF_MACH_BRAND = :BRAND
     AND CFF_MACH_NM = :MACHINE_NAME
   ORDER BY CFF_MACH_ID
   LIMIT 1;

2. 파일명.쿼리명으로 호출합니다
----------------------------------------

.. code-block:: python

   machine = session.select_one(
       "coffee_search.select_machine",
       {"BRAND": brand, "MACHINE_NAME": machine_name},
   )

``coffee_search`` 는 확장자를 뺀 파일명, ``select_machine`` 은 SQL 이름입니다.
``:BRAND`` 같은 자리에는 dict의 같은 이름에 해당하는 값이 들어갑니다.
값을 SQL 문자열에 직접 이어 붙이지 마세요.
변경문 이름에 ``!`` 가 붙어 있어도 Python 호출에서는 ``!`` 를 뺍니다.
동일한 파일명을 가진 SQL 파일이 여러 곳에 있으면 등록 시 충돌할 수 있습니다.

메서드 고르기
------------------------------

.. list-table::
   :header-rows: 1
   :widths: 30 35 35

   * - 목적
     - 메서드
     - 결과
   * - 여러 행 조회
     - ``select_list()``
     - dict 목록
   * - 첫 행 조회
     - ``select_one()``
     - dict 또는 ``None``
   * - 단건 변경
     - ``execute()``
     - SQL 실행 결과
   * - 같은 SQL로 여러 건 변경
     - ``execute_many()``
     - 처리 행 수; 빈 입력이면 0

``select_one()`` 은 자동으로 ``LIMIT 1`` 을 붙이지 않습니다.
``execute_many()`` 에는 dict 한 개가 아닌 **dict 목록** 을 전달합니다.

함께 성공해야 하는 변경 묶기
------------------------------------

다음은 기존 상세를 새 데이터로 교체하는 예제입니다.
``machine_id`` 와 ``batch_params`` 는 앞 단계에서 준비한 값입니다.

.. code-block:: python

   with session.transaction():
       session.execute(
           "coffee_search.delete_machine_details",
           {"CFF_MACH_ID": machine_id},
       )
       session.execute_many(
           "coffee_search.insert_machine_detail",
           batch_params,
       )

블록이 정상 종료되면 반영(COMMIT), 예외가 전파되면 취소(ROLLBACK)합니다.
한 연결을 재사용하며 중첩 트랜잭션은 지원하지 않습니다.
배치 파라미터에는 ``CFF_MACH_ID``, ``PAGE_NO``, ``TEXT``, ``EMBEDDING``, ``USER_ID`` 가 필요합니다.

로그를 공유하기 전에
------------------------------

기본 ``combined`` 모드는 SQL에 파라미터를 합쳐 로그로 출력합니다.
``separate`` 도 값을 따로 출력하므로 비밀값 보호 기능이 아닙니다.
``result_log=True`` 는 조회 원문을 출력할 수 있습니다.
벡터 축약 역시 인증정보 마스킹과는 다릅니다.

현재 구현에서 ``sql_log_mode="none"`` 만으로 변경·배치 로그까지 모두 꺼지지는 않습니다.
:doc:`getting_started` 예제처럼 SQL 로거를 끄고 결과 원문 출력을 피하세요.
예외 메시지 등 다른 출력은 공유 전에 별도로 확인해야 합니다.
