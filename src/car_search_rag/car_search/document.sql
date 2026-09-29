-- name: select_documents
-- id 순서로 최대 5건을 조회한다.
SELECT                              -- 화면에서 사용할 캡슐 데이터 조회
    cff_caps_id AS id,              -- 캡슐 ID를 id 키로 반환
    cff_caps_embed_txt AS content,  -- 임베딩용 텍스트를 content 키로 반환
    cff_caps_embed_vec AS embedding -- 벡터 값을 embedding 키로 반환
FROM cff_caps                       -- 실제 PostgreSQL 테이블
ORDER BY cff_caps_id                -- ID 순서로 결과 정렬
LIMIT 5;                            -- 최대 5건만 조회
