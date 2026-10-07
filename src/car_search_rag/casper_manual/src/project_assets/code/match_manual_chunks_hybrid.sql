-- 팀 DB의 DBeaver SQL 편집기에서 전체 실행합니다.
-- 개인 DB의 테이블이 manual_chunks/manual_embeddings이면 아래 두 테이블명을 바꾸세요.
-- 기존 match_manual_chunks, 청크, 임베딩, 이미지 연결 데이터는 그대로 유지합니다.
BEGIN;

CREATE OR REPLACE FUNCTION public.match_manual_chunks_hybrid(
    query_embedding extensions.vector,
    match_count integer,
    filter_model text,
    filter_version text,
    query_text text,
    query_terms text[],
    candidate_count integer
)
RETURNS TABLE (
    chunk_id text, document_name text, chapter text, section text,
    subsection text, source_title text, page_start integer,
    page_end integer, chunk_text text, similarity double precision,
    lexical_score double precision, hybrid_score double precision,
    vector_rank integer, keyword_rank integer, matched_terms text[]
)
LANGUAGE sql STABLE SECURITY INVOKER
SET search_path TO public, extensions
AS $function$
WITH
settings AS (
    SELECT greatest(1, least(coalesce(match_count, 5), 20)) AS result_limit,
           greatest(20, least(coalesce(candidate_count, 50), 100)) AS pool_limit,
           lower(regexp_replace(left(coalesce(query_text, ''), 2000), '\s+', '', 'g')) AS q
),
terms AS MATERIALIZED (
    SELECT DISTINCT lower(btrim(t.term)) AS term
    FROM unnest(coalesce(query_terms, ARRAY[]::text[])) WITH ORDINALITY AS t(term, ord)
    WHERE t.ord <= 16 AND char_length(btrim(t.term)) BETWEEN 2 AND 100
),
eligible AS MATERIALIZED (
    SELECT c.*, e.embedding,
           lower(concat_ws(' ', c.source_title, c.subsection, c.section, c.chapter)) AS headings,
           lower(c.chunk_text) AS body,
           lower(regexp_replace(coalesce(c.source_title, ''), '\s+', '', 'g')) AS title_key
    FROM public.casper_manual_chunks AS c
    JOIN public.casper_manual_embeddings AS e ON e.chunk_id = c.chunk_id
    WHERE e.embedding_model = filter_model AND e.embedding_version = filter_version
),
-- 여러 청크에 흔하게 나타나는 단어보다 드문 단어에 더 높은 가중치를 줍니다.
-- 같은 단어가 한 청크에 반복되어도 반복 횟수로 점수를 높이지 않습니다.
term_weights AS (
    SELECT t.term,
           (1.0 + ln((1.0 + (SELECT count(*) FROM eligible)) /
                     (1.0 + count(e.chunk_id))))::double precision AS weight
    FROM terms AS t
    LEFT JOIN eligible AS e ON strpos(e.headings, t.term) > 0 OR strpos(e.body, t.term) > 0
    GROUP BY t.term
),
lexical AS MATERIALIZED (
    SELECT e.chunk_id,
           (sum(w.weight *
               (CASE WHEN strpos(e.headings, w.term) > 0 THEN 4.0 ELSE 0.0 END +
                CASE WHEN strpos(e.body, w.term) > 0 THEN 1.0 ELSE 0.0 END)) +
            CASE WHEN char_length(e.title_key) >= 4 AND strpos(s.q, e.title_key) > 0
                 THEN 4.0 ELSE 0.0 END)::double precision AS score,
           array_agg(w.term ORDER BY w.term) AS hits
    FROM eligible AS e
    CROSS JOIN settings AS s
    JOIN term_weights AS w ON strpos(e.headings, w.term) > 0 OR strpos(e.body, w.term) > 0
    GROUP BY e.chunk_id, e.title_key, s.q
),
vector_pool AS (
    SELECT e.chunk_id, e.embedding <=> query_embedding AS distance
    FROM eligible AS e
    ORDER BY e.embedding <=> query_embedding, e.chunk_id
    LIMIT (SELECT pool_limit FROM settings)
),
vectors AS (
    SELECT v.chunk_id, row_number() OVER (ORDER BY v.distance, v.chunk_id)::integer AS rank
    FROM vector_pool AS v
),
keyword_pool AS (
    SELECT l.* FROM lexical AS l
    ORDER BY l.score DESC, l.chunk_id
    LIMIT (SELECT pool_limit FROM settings)
),
keywords AS (
    SELECT k.chunk_id, row_number() OVER (ORDER BY k.score DESC, k.chunk_id)::integer AS rank
    FROM keyword_pool AS k
),
-- 순위 결합(RRF): 서로 다른 척도의 유사도와 키워드 점수를 직접 더하지 않습니다.
-- 초기 설정: 벡터 가중치 1, 키워드 가중치 2, 순위 상수 20. 평가 후 조정 가능.
fused AS (
    SELECT coalesce(v.chunk_id, k.chunk_id) AS chunk_id,
           v.rank AS vrank, k.rank AS krank,
           (coalesce(1.0 / (20.0 + v.rank), 0.0) +
            coalesce(2.0 / (20.0 + k.rank), 0.0))::double precision AS score
    FROM vectors AS v FULL JOIN keywords AS k ON k.chunk_id = v.chunk_id
)
SELECT e.chunk_id, e.document_name, e.chapter, e.section, e.subsection,
       e.source_title, e.page_start, e.page_end, e.chunk_text,
       (1 - (e.embedding <=> query_embedding))::double precision AS similarity,
       coalesce(l.score, 0.0)::double precision AS lexical_score,
       f.score AS hybrid_score, f.vrank AS vector_rank, f.krank AS keyword_rank,
       coalesce(l.hits, ARRAY[]::text[]) AS matched_terms
FROM fused AS f
JOIN eligible AS e ON e.chunk_id = f.chunk_id
LEFT JOIN lexical AS l ON l.chunk_id = f.chunk_id
ORDER BY f.score DESC, coalesce(l.score, 0.0) DESC,
         e.embedding <=> query_embedding, e.chunk_id
LIMIT (SELECT result_limit FROM settings);
$function$;

COMMENT ON FUNCTION public.match_manual_chunks_hybrid(extensions.vector, integer, text, text, text, text[], integer)
IS 'Casper vector + literal keyword retrieval with weighted rank fusion; similarity remains cosine similarity.';

-- 새 RPC 함수를 API 스키마 캐시에 알립니다.
NOTIFY pgrst, 'reload schema';
COMMIT;
