-- name: select_test
/* 실행 여부 단순 테스트 SQL */
SELECT  *
FROM    CFF_MACH;


-- name: search_machine_manual
/* 임베딩 조회 테스트 */
SELECT M.CFF_MACH_ID
    , M.CFF_MACH_BRAND AS BRAND
    , M.CFF_MACH_NM AS MACHINE_NAME
    , D.CFF_MACH_PAGE_NO
    , D.CFF_MACH_EMBED_TXT
    , 1 - (D.CFF_MACH_EMBED_VEC <=> :EMBEDDING) AS SIMILARITY
FROM CFF_MACH M
JOIN CFF_MACH_DTL D
ON      D.CFF_MACH_ID = M.CFF_MACH_ID
WHERE   M.CFF_MACH_BRAND = :BRAND
AND     M.CFF_MACH_NM = :MACHINE_NAME
ORDER BY D.CFF_MACH_EMBED_VEC <=> :EMBEDDING
LIMIT :LIMIT
;

-- name: lock_machine_registration
-- 동일 머신의 동시 등록을 트랜잭션 동안 직렬화한다.
SELECT  PG_ADVISORY_XACT_LOCK(HASHTEXT('CFF_MACH'), HASHTEXT('MACHINE_REGISTRATION')) AS LOCKED;

-- name: select_machine
-- 브랜드와 모델명으로 기존 머신 ID를 찾는다.
SELECT  CFF_MACH_ID AS ID
FROM    PUBLIC.CFF_MACH
WHERE   CFF_MACH_BRAND = :BRAND
AND     CFF_MACH_NM = :MACHINE_NAME
ORDER BY CFF_MACH_ID
LIMIT   1;

-- name: generate_biz_id
-- 기존 DB 함수에서 테이블별 YYYYMMDD_000001 형식의 ID를 받는다.
SELECT  PUBLIC.FN_GEN_BIZ_ID(:TABLE_NAME) AS ID;

-- name: insert_machine!
-- 머신 한 건을 등록하고 날짜 컬럼은 DB 기본값을 사용한다.
INSERT INTO PUBLIC.CFF_MACH (
    CFF_MACH_ID,
    CFF_MACH_BRAND,
    CFF_MACH_NM,
    CREATE_USER_ID,
    UPDATE_USER_ID
) VALUES (
    :CFF_MACH_ID,
    :BRAND,
    :MACHINE_NAME,
    :USER_ID,
    :USER_ID
);

-- name: select_detail_by_page
-- 재실행할 때 같은 머신의 같은 PDF 페이지를 중복 등록하지 않는다.
SELECT  CFF_MACH_DTL_ID AS ID
FROM    PUBLIC.CFF_MACH_DTL
WHERE   CFF_MACH_ID = :CFF_MACH_ID
AND     CFF_MACH_PAGE_NO = :PAGE_NO
LIMIT   1;

-- name: delete_machine_details!
-- 대상 머신의 상세만 삭제하며 머신과 관계 테이블은 유지한다.
DELETE FROM PUBLIC.CFF_MACH_DTL
WHERE CFF_MACH_ID = :CFF_MACH_ID;

-- name: insert_machine_detail!
-- 페이지 텍스트와 검증된 임베딩 벡터를 함께 저장한다.
INSERT INTO CFF_MACH_DTL (
    CFF_MACH_ID,
    CFF_MACH_DTL_ID,
    CFF_MACH_PAGE_NO,
    CFF_MACH_EMBED_TXT,
    CFF_MACH_EMBED_VEC,
    CREATE_USER_ID,
    UPDATE_USER_ID
) VALUES (
    :CFF_MACH_ID,
    FN_GEN_BIZ_ID('CFF_MACH_DTL'),
    :PAGE_NO,
    :TEXT,
    :EMBEDDING,
    :USER_ID,
    :USER_ID
);
