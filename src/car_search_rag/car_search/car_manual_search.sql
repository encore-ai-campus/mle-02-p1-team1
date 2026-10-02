--=========================================================
-- 차량 등록
--=========================================================

-- name: merge_car
MERGE INTO CAR AS T
USING (
    SELECT
        :CAR_BRAND_NM AS CAR_BRAND_NM,
        :CAR_BRAND_ENG_NM AS CAR_BRAND_ENG_NM,
        :CAR_NM AS CAR_NM,
        :CAR_ENG_NM AS CAR_ENG_NM,
        :CAR_MODEL_YR AS CAR_MODEL_YR,
        :USER_ID AS USER_ID
) AS S
ON (
    T.CAR_BRAND_ENG_NM = S.CAR_BRAND_ENG_NM
    AND T.CAR_ENG_NM = S.CAR_ENG_NM
    AND T.CAR_MODEL_YR = S.CAR_MODEL_YR
)

WHEN MATCHED THEN
    UPDATE SET
        CAR_BRAND_NM = S.CAR_BRAND_NM,
        CAR_NM = S.CAR_NM,
        UPDATE_DATE = NOW(),
        UPDATE_USER_ID = S.USER_ID

WHEN NOT MATCHED THEN
    INSERT (
        CAR_ID,
        CAR_BRAND_NM,
        CAR_BRAND_ENG_NM,
        CAR_NM,
        CAR_ENG_NM,
        CAR_MODEL_YR,
        CREATE_USER_ID,
        UPDATE_USER_ID
    )
    VALUES (
        FN_GET_BIZ_ID('CAR'),
        S.CAR_BRAND_NM,
        S.CAR_BRAND_ENG_NM,
        S.CAR_NM,
        S.CAR_ENG_NM,
        S.CAR_MODEL_YR,
        S.USER_ID,
        S.USER_ID
    )

RETURNING T.CAR_ID;


--=========================================================
-- 차량 매뉴얼 Chapter ID 생성
--=========================================================

-- name: get_car_manual_chapter_id
-- 차량 매뉴얼 Chapter 등록 전에 사용할 ID를 생성한다.
SELECT FN_GET_BIZ_ID('CAR_MANUAL_CHAPTER') AS ID;


--=========================================================
-- 차량 매뉴얼 Chapter 등록
--=========================================================

-- name: insert_car_manual_chapter!
-- 차량 매뉴얼 Chapter 정보를 등록한다.
INSERT INTO CAR_MANUAL_CHAPTER (
    CAR_ID,
    CAR_MANUAL_CHAPTER_ID,
    CAR_MANUAL_CHAPTER_NO,
    CAR_MANUAL_CHAPTER_NM,
    CAR_MANUAL_CHAPTER_SORT_NO,
    CREATE_USER_ID,
    UPDATE_USER_ID
) VALUES (
    :CAR_ID,
    :CAR_MANUAL_CHAPTER_ID,
    :CAR_MANUAL_CHAPTER_NO,
    :CAR_MANUAL_CHAPTER_NM,
    :CAR_MANUAL_CHAPTER_SORT_NO,
    :USER_ID,
    :USER_ID
);


--=========================================================
-- 차량 매뉴얼 Chunk 등록
--=========================================================

-- name: insert_car_manual_chunk!
-- 차량 매뉴얼 Chunk 텍스트와 임베딩 벡터를 등록한다.
INSERT INTO CAR_MANUAL_CHUNK (
    CAR_ID,
    CAR_MANUAL_CHAPTER_ID,
    CAR_MANUAL_CHUNK_ID,
    CAR_MANUAL_CHUNK_PAGE_NO,
    CAR_MANUAL_CHUNK_NO,
    CAR_MANUAL_CHUNK_TXT,
    CAR_MANUAL_CHUNK_EMBED_VEC,
    CREATE_USER_ID,
    UPDATE_USER_ID
) VALUES (
    :CAR_ID,
    :CAR_MANUAL_CHAPTER_ID,
    PUBLIC.FN_GET_BIZ_ID('CAR_MANUAL_CHUNK'),
    :CAR_MANUAL_CHUNK_PAGE_NO,
    :CAR_MANUAL_CHUNK_NO,
    :CAR_MANUAL_CHUNK_TXT,
    :CAR_MANUAL_CHUNK_EMBED_VEC,
    :USER_ID,
    :USER_ID
);


--=========================================================
-- 차량 매뉴얼 이미지 등록
--=========================================================

-- name: insert_car_manual_image!
-- Supabase Storage에 업로드된 차량 매뉴얼 이미지 정보를 등록한다.
INSERT INTO CAR_MANUAL_IMAGE (
    CAR_ID,
    CAR_MANUAL_CHAPTER_ID,
    CAR_MANUAL_IMAGE_ID,
    CAR_MANUAL_IMAGE_PAGE_NO,
    CAR_MANUAL_IMAGE_NO,
    CAR_MANUAL_IMAGE_URL,
    CAR_MANUAL_IMAGE_DESC,
    CREATE_USER_ID,
    UPDATE_USER_ID
) VALUES (
    :CAR_ID,
    :CAR_MANUAL_CHAPTER_ID,
    PUBLIC.FN_GET_BIZ_ID('CAR_MANUAL_IMAGE'),
    :CAR_MANUAL_IMAGE_PAGE_NO,
    :CAR_MANUAL_IMAGE_NO,
    :CAR_MANUAL_IMAGE_URL,
    :CAR_MANUAL_IMAGE_DESC,
    :USER_ID,
    :USER_ID
);