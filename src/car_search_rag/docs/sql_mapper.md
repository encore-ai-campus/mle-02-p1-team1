# SQL 실행 구조

각 기능은 `car_search_rag/car_search/`에 `xxx.py`, `xxx_service.py`, `xxx.sql`로 나란히 있다. `xxx.py`가 실행을 시작하고 Service가 업무 순서와 `SqlSession` 호출을 담당한다.

`SqlSession`은 자체 파일의 `__file__` 기준으로 `car_search/*.sql`을 aiosql로 읽는다. SQL 파일의 `-- name:`은 `파일명.statement`로 호출한다. 예를 들어 `document.select_documents`는 `document.sql`에 정의되어 있다.

DB 연결은 기존 `DatabaseManager`를 재사용하며 `.env`의 `DB_URL`을 사용한다. `SqlSession.transaction()` 안에서는 연결을 공유하고 성공하면 COMMIT, 예외가 나면 ROLLBACK한다.

`execute()`는 파라미터 dict 한 건으로 SQL을 한 번 실행한다. 같은 SQL을 여러 INSERT·UPDATE·DELETE 데이터에 적용할 때는 `execute_many(statement_id, parameters_list)`에 dict 목록을 전달한다. 빈 목록은 0을 반환한다. Batch는 `cursor.executemany()`로 실행하고, INFO 로그가 활성화되면 `BATCH QUERY`·전건 `BATCH PARAMS`·`BATCH DONE`을 기록한다. 긴 Vector는 로그에서 앞부분만 표시하며 DB에는 원본이 전달된다. 자세한 예제는 [SQL / SqlSession 사용 가이드](./build/html/sql_mapper_guide.html)를 참고한다.

실행: `car_search_rag\run_car_search.bat` 또는 `python car_search_rag/car_search/coffee_search.py`.
