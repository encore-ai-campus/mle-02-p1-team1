-- name: select_by_brand
-- WHERE 바인딩으로 특정 브랜드의 캡슐만 조회한다.
SELECT  cff_caps_id,
        cff_caps_brand,
        cff_caps_nm
FROM    cff_caps
WHERE   cff_caps_brand like :brand
ORDER BY cff_caps_id;

-- name: count_by_brand
-- GROUP BY로 브랜드별 캡슐 개수를 집계한다.
SELECT  cff_caps_brand,
        COUNT(*) AS capsule_count
FROM    cff_caps
GROUP BY cff_caps_brand
ORDER BY cff_caps_brand NULLS FIRST;
