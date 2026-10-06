--=========================================================
-- 삭제
--=========================================================

BEGIN;

DELETE FROM car_manual_chunk;
DELETE FROM car_manual_image;
DELETE FROM car_manual_chapter;
DELETE FROM car;

COMMIT;


--=========================================================
-- 조회
--=========================================================

--title: car
SELECT *
FROM car;

--title: car_manual_chapter
SELECT *
FROM car_manual_chapter;

--title: car_manual_chunk
SELECT *
FROM car_manual_chunk;

--title: car_manual_image
SELECT *
FROM car_manual_image;