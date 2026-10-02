수정할 파일 찾기
==============================

**아래 경로는 저장소 루트를 기준으로 합니다.**

.. code-block:: text

   src/car_search_rag/
   ├── car_search/
   │   ├── coffee_search.py          # 실행 예제 + 이미지 업로드
   │   ├── coffee_search_service.py  # 검색·등록 순서
   │   ├── coffee_search.sql         # SQL 정의
   │   ├── car_manual_search.py      # 자동차 매뉴얼 관련 코드
   │   └── car_manual_search_service.py
   ├── common/
   │   ├── database_manager.py       # DB 연결
   │   ├── document_reader.py        # PDF 읽기
   │   ├── sql_session.py            # SQL 실행·트랜잭션
   │   └── storage_manager.py        # 이미지 저장소 연동
   └── docs/
       ├── source/                  # 이 문서의 원본
       ├── build_docs.py            # 문서 검사·빌드
       └── build/html/index.html    # 브라우저로 여는 결과

무엇을 바꾸고 싶나요?
------------------------------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - 할 일
     - 수정 위치
   * - 질문·브랜드·모델 입력 변경
     - 검색 전용 예제 또는 ``coffee_search.py``
   * - 검색·등록 처리 순서 변경
     - ``coffee_search_service.py``
   * - 조회 조건·정렬 변경
     - ``coffee_search.sql``
   * - PDF 텍스트 추출 변경
     - ``common/document_reader.py``
   * - DB 연결·SQL 실행 방식 변경
     - ``common/database_manager.py``, ``common/sql_session.py``
   * - 문서 내용·디자인 변경
     - ``docs/source/*.rst``, ``docs/source/_public/custom.css``

문서를 다시 만들 때
------------------------------

저장소 루트에서 실행합니다. 문서 빌드에는 애플리케이션용 환경변수나 DB 접속이 필요하지 않습니다.

.. code-block:: console

   uv run --no-project --with sphinx --with furo python src/car_search_rag/docs/build_docs.py

빌드는 원본을 검사한 후 새 HTML을 만들고 결과를 다시 검사합니다.
검사를 통과한 결과만 ``build/html`` 에 반영합니다.
HTML을 직접 수정하면 다음 빌드 때 사라지므로 원본을 수정하세요.
