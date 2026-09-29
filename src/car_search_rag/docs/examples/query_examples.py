import logging                                                                                      # SQL 로그를 콘솔에 표시
import sys                                                                                          # 로그를 print와 같은 표준 출력에 표시
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from group_project.common.sql_session import SqlSession                                         # 공통 SQL 세션 클래스 가져오기
from car_search_rag.car_search import query_examples_service

result_logger = logging.getLogger("group_project.results")                                          # 조회한 행을 표시할 별도 로그 이름


def main() -> None:                                                                                 # WHERE와 GROUP BY mapper의 실제 DB 실행 예제
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s", stream=sys.stdout)     # SQL 로그 활성화
    sql_session = SqlSession()  # camelCase key로 테스트하려면 이 줄을 사용
    # sql_session = SqlSession(camel_case_keys=False)  # snake_case key로 테스트
    brand_key = "cffCapsBrand" if sql_session.camel_case_keys else "cff_caps_brand"
    count_key = "capsuleCount" if sql_session.camel_case_keys else "capsule_count"

    service = query_examples_service.QueryExamplesService(sql_session)
    groups = service.list_brand_counts()                               # GROUP BY 집계 실행
    result_logger.info("GROUP BY 조회 데이터: %s", groups)                                            # 집계 결과 행 전체를 로그에 표시
    if not groups:                                                                                  # 테이블이 비어 있으면 WHERE 비교 대상이 없음
        result_logger.info("조회된 캡슐이 없습니다.")                                                   # 빈 테이블임을 로그로 표시
        return                                                                                      # 나머지 예제를 종료

    selected_group = next((group for group in groups if group[brand_key] is not None), None)  # NULL이 아닌 브랜드 선택
    if selected_group is None:                                                                      # 브랜드가 모두 NULL인 경우
        result_logger.info("비교할 브랜드가 없습니다.")                                                  # = 조건으로 조회할 수 없음을 표시
        return                                                                                      # WHERE 예제를 종료

    brand = selected_group[brand_key]  # WHERE에 전달할 브랜드 값
    rows = service.list_by_brand(brand)  # WHERE 파라미터 실행

    result_logger.info("WHERE 조회 데이터 (%d건):", len(rows))                                        # 조회 결과 제목과 건수 표시
    for row in rows:                                                                                # 조회된 행을 하나씩 순회
        result_logger.info("%s", row)                                                               # 각 행을 별도 로그 줄에 표시

    expected = selected_group[count_key]  # 선택한 브랜드의 집계 건수

    assert len(rows) == expected, "WHERE 조회 건수와 GROUP BY 집계 건수가 다릅니다."                      # 두 쿼리의 결과 비교

    result_logger.info("brand=%r, group_count=%d, where_count=%d", brand, expected, len(rows))      # 검증에 사용한 건수 표시


if __name__ == "__main__":                                                                          # 이 파일을 직접 실행한 경우
    main()                                                                                          # 샘플 쿼리 실행
