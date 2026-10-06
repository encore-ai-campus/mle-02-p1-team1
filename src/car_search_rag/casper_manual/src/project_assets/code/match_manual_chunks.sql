-- Actual team database function DDL supplied by the user.
CREATE OR REPLACE FUNCTION public.match_manual_chunks(
    query_embedding vector,
    match_count integer,
    filter_model text,
    filter_version text
)
RETURNS TABLE (
    chunk_id text, document_name text, chapter text, section text,
    subsection text, source_title text, page_start integer,
    page_end integer, chunk_text text, similarity double precision
)
LANGUAGE sql
STABLE
SET search_path TO 'public'
AS $function$
    select c.chunk_id, c.document_name, c.chapter, c.section,
           c.subsection, c.source_title, c.page_start, c.page_end,
           c.chunk_text, 1 - (e.embedding <=> query_embedding) as similarity
    from public.casper_manual_embeddings as e
    join public.casper_manual_chunks as c on c.chunk_id = e.chunk_id
    where e.embedding_model = filter_model
      and e.embedding_version = filter_version
    order by e.embedding <=> query_embedding
    limit match_count;
$function$;
