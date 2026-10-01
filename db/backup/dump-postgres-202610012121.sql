--
-- PostgreSQL database dump
--

-- Dumped from database version 17.6
-- Dumped by pg_dump version 17.0

-- Started on 2026-10-01 21:21:29

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- TOC entry 33 (class 2615 OID 2200)
-- Name: public; Type: SCHEMA; Schema: -; Owner: pg_database_owner
--

CREATE SCHEMA public;


ALTER SCHEMA public OWNER TO pg_database_owner;

--
-- TOC entry 4101 (class 0 OID 0)
-- Dependencies: 33
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: pg_database_owner
--

COMMENT ON SCHEMA public IS 'standard public schema';


--
-- TOC entry 449 (class 1255 OID 17555)
-- Name: delete_user_own_account(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.delete_user_own_account() RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
BEGIN
  -- 현재 로그인한 유저 ID를 auth.uid()로 가져와서 auth.users 테이블에서 삭제
  DELETE FROM auth.users WHERE id = auth.uid();
END;
$$;


ALTER FUNCTION public.delete_user_own_account() OWNER TO postgres;

--
-- TOC entry 576 (class 1255 OID 18515)
-- Name: fn_gen_biz_id(text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.fn_gen_biz_id(p_tbl_nm text) RETURNS text
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_seq_nm text;
    v_today text;
    v_seq_val bigint;
    v_result_id text;
BEGIN

    -- 오늘 날짜 (YYYYMMDD)
    v_today := to_char(now(), 'YYYYMMDD');

    -- 기존 시퀀스명
    -- CFF_MACH     -> seq_cff_mach
    -- CFF_MACH_DTL -> seq_cff_mach_dtl
    v_seq_nm := 'seq_' || lower(p_tbl_nm);

    -- 기존 시퀀스에서 다음 번호 채번
    EXECUTE format(
        'SELECT nextval(%L)',
        v_seq_nm
    )
    INTO v_seq_val;

    -- 최종 ID
    -- 예: 20260927_000001
    v_result_id :=
        v_today || '_' || lpad(v_seq_val::text, 6, '0');

    RETURN v_result_id;

END;
$$;


ALTER FUNCTION public.fn_gen_biz_id(p_tbl_nm text) OWNER TO postgres;

--
-- TOC entry 577 (class 1255 OID 21420)
-- Name: match_manual_chunks(public.vector, integer, text, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.match_manual_chunks(query_embedding public.vector, match_count integer, filter_model text, filter_version text) RETURNS TABLE(chunk_id text, document_name text, chapter text, section text, subsection text, source_title text, page_start integer, page_end integer, chunk_text text, similarity double precision)
    LANGUAGE sql STABLE
    SET search_path TO 'public'
    AS $$
    select
        c.chunk_id,
        c.document_name,
        c.chapter,
        c.section,
        c.subsection,
        c.source_title,
        c.page_start,
        c.page_end,
        c.chunk_text,
        1 - (e.embedding <=> query_embedding) as similarity
    from public.casper_manual_embeddings as e
    join public.casper_manual_chunks as c
        on c.chunk_id = e.chunk_id
    where e.embedding_model = filter_model
      and e.embedding_version = filter_version
    order by e.embedding <=> query_embedding
    limit match_count;
$$;


ALTER FUNCTION public.match_manual_chunks(query_embedding public.vector, match_count integer, filter_model text, filter_version text) OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 335 (class 1259 OID 19413)
-- Name: car; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.car (
    car_id character varying(20) NOT NULL,
    car_brand_nm character varying(100) NOT NULL,
    car_nm character varying(150) NOT NULL,
    car_model_cd character varying(50) NOT NULL,
    car_model_yr integer NOT NULL,
    create_date timestamp with time zone DEFAULT now() NOT NULL,
    create_user_id character varying(50) NOT NULL,
    update_date timestamp with time zone DEFAULT now() NOT NULL,
    update_user_id character varying(50) NOT NULL
);


ALTER TABLE public.car OWNER TO postgres;

--
-- TOC entry 4106 (class 0 OID 0)
-- Dependencies: 335
-- Name: TABLE car; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.car IS '차량 마스터';


--
-- TOC entry 4107 (class 0 OID 0)
-- Dependencies: 335
-- Name: COLUMN car.car_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.car.car_id IS '차량 ID';


--
-- TOC entry 4108 (class 0 OID 0)
-- Dependencies: 335
-- Name: COLUMN car.car_brand_nm; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.car.car_brand_nm IS '차량 브랜드명';


--
-- TOC entry 4109 (class 0 OID 0)
-- Dependencies: 335
-- Name: COLUMN car.car_nm; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.car.car_nm IS '차량명';


--
-- TOC entry 4110 (class 0 OID 0)
-- Dependencies: 335
-- Name: COLUMN car.car_model_cd; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.car.car_model_cd IS '차량 모델 코드';


--
-- TOC entry 4111 (class 0 OID 0)
-- Dependencies: 335
-- Name: COLUMN car.car_model_yr; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.car.car_model_yr IS '차량 모델 연도';


--
-- TOC entry 4112 (class 0 OID 0)
-- Dependencies: 335
-- Name: COLUMN car.create_date; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.car.create_date IS '등록 일시';


--
-- TOC entry 4113 (class 0 OID 0)
-- Dependencies: 335
-- Name: COLUMN car.create_user_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.car.create_user_id IS '등록 사용자 ID';


--
-- TOC entry 4114 (class 0 OID 0)
-- Dependencies: 335
-- Name: COLUMN car.update_date; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.car.update_date IS '수정 일시';


--
-- TOC entry 4115 (class 0 OID 0)
-- Dependencies: 335
-- Name: COLUMN car.update_user_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.car.update_user_id IS '수정 사용자 ID';


--
-- TOC entry 347 (class 1259 OID 21572)
-- Name: car_manual_chapter; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.car_manual_chapter (
    car_id character varying(20) NOT NULL,
    car_manual_chapter_id character varying(20) NOT NULL,
    car_manual_chapter_no character varying(20) NOT NULL,
    car_manual_chapter_nm character varying(200) NOT NULL,
    car_manual_chapter_sort_no integer,
    create_date timestamp with time zone DEFAULT now() NOT NULL,
    create_user_id character varying(50) NOT NULL,
    update_date timestamp with time zone DEFAULT now() NOT NULL,
    update_user_id character varying(50) NOT NULL
);


ALTER TABLE public.car_manual_chapter OWNER TO postgres;

--
-- TOC entry 4117 (class 0 OID 0)
-- Dependencies: 347
-- Name: TABLE car_manual_chapter; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.car_manual_chapter IS '차량 매뉴얼 Chapter';


--
-- TOC entry 4118 (class 0 OID 0)
-- Dependencies: 347
-- Name: COLUMN car_manual_chapter.car_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.car_manual_chapter.car_id IS '차량 ID';


--
-- TOC entry 4119 (class 0 OID 0)
-- Dependencies: 347
-- Name: COLUMN car_manual_chapter.car_manual_chapter_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.car_manual_chapter.car_manual_chapter_id IS '차량 매뉴얼 Chapter ID';


--
-- TOC entry 4120 (class 0 OID 0)
-- Dependencies: 347
-- Name: COLUMN car_manual_chapter.car_manual_chapter_no; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.car_manual_chapter.car_manual_chapter_no IS '차량 매뉴얼 Chapter 번호';


--
-- TOC entry 4121 (class 0 OID 0)
-- Dependencies: 347
-- Name: COLUMN car_manual_chapter.car_manual_chapter_nm; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.car_manual_chapter.car_manual_chapter_nm IS '차량 매뉴얼 Chapter명';


--
-- TOC entry 4122 (class 0 OID 0)
-- Dependencies: 347
-- Name: COLUMN car_manual_chapter.car_manual_chapter_sort_no; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.car_manual_chapter.car_manual_chapter_sort_no IS '차량 매뉴얼 Chapter 정렬 순번';


--
-- TOC entry 4123 (class 0 OID 0)
-- Dependencies: 347
-- Name: COLUMN car_manual_chapter.create_date; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.car_manual_chapter.create_date IS '등록 일시';


--
-- TOC entry 4124 (class 0 OID 0)
-- Dependencies: 347
-- Name: COLUMN car_manual_chapter.create_user_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.car_manual_chapter.create_user_id IS '등록 사용자 ID';


--
-- TOC entry 4125 (class 0 OID 0)
-- Dependencies: 347
-- Name: COLUMN car_manual_chapter.update_date; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.car_manual_chapter.update_date IS '수정 일시';


--
-- TOC entry 4126 (class 0 OID 0)
-- Dependencies: 347
-- Name: COLUMN car_manual_chapter.update_user_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.car_manual_chapter.update_user_id IS '수정 사용자 ID';


--
-- TOC entry 348 (class 1259 OID 21579)
-- Name: car_manual_chunk; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.car_manual_chunk (
    car_id character varying(20) NOT NULL,
    car_manual_chapter_id character varying(20) NOT NULL,
    car_manual_chunk_id character varying(20) NOT NULL,
    car_manual_chunk_page_no integer,
    car_manual_chunk_no integer NOT NULL,
    car_manual_chunk_txt text NOT NULL,
    car_manual_chunk_embed_vec public.vector,
    create_date timestamp with time zone DEFAULT now() NOT NULL,
    create_user_id character varying(50) NOT NULL,
    update_date timestamp with time zone DEFAULT now() NOT NULL,
    update_user_id character varying(50) NOT NULL
);


ALTER TABLE public.car_manual_chunk OWNER TO postgres;

--
-- TOC entry 4128 (class 0 OID 0)
-- Dependencies: 348
-- Name: TABLE car_manual_chunk; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.car_manual_chunk IS '차량 매뉴얼 RAG 청크';


--
-- TOC entry 4129 (class 0 OID 0)
-- Dependencies: 348
-- Name: COLUMN car_manual_chunk.car_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.car_manual_chunk.car_id IS '차량 ID';


--
-- TOC entry 4130 (class 0 OID 0)
-- Dependencies: 348
-- Name: COLUMN car_manual_chunk.car_manual_chapter_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.car_manual_chunk.car_manual_chapter_id IS '차량 매뉴얼 Chapter ID';


--
-- TOC entry 4131 (class 0 OID 0)
-- Dependencies: 348
-- Name: COLUMN car_manual_chunk.car_manual_chunk_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.car_manual_chunk.car_manual_chunk_id IS '차량 매뉴얼 청크 ID';


--
-- TOC entry 4132 (class 0 OID 0)
-- Dependencies: 348
-- Name: COLUMN car_manual_chunk.car_manual_chunk_page_no; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.car_manual_chunk.car_manual_chunk_page_no IS '차량 매뉴얼 페이지 번호';


--
-- TOC entry 4133 (class 0 OID 0)
-- Dependencies: 348
-- Name: COLUMN car_manual_chunk.car_manual_chunk_no; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.car_manual_chunk.car_manual_chunk_no IS '차량 매뉴얼 청크 순번';


--
-- TOC entry 4134 (class 0 OID 0)
-- Dependencies: 348
-- Name: COLUMN car_manual_chunk.car_manual_chunk_txt; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.car_manual_chunk.car_manual_chunk_txt IS '차량 매뉴얼 청크 텍스트';


--
-- TOC entry 4135 (class 0 OID 0)
-- Dependencies: 348
-- Name: COLUMN car_manual_chunk.car_manual_chunk_embed_vec; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.car_manual_chunk.car_manual_chunk_embed_vec IS '차량 매뉴얼 청크 임베딩 벡터';


--
-- TOC entry 4136 (class 0 OID 0)
-- Dependencies: 348
-- Name: COLUMN car_manual_chunk.create_date; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.car_manual_chunk.create_date IS '등록 일시';


--
-- TOC entry 4137 (class 0 OID 0)
-- Dependencies: 348
-- Name: COLUMN car_manual_chunk.create_user_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.car_manual_chunk.create_user_id IS '등록 사용자 ID';


--
-- TOC entry 4138 (class 0 OID 0)
-- Dependencies: 348
-- Name: COLUMN car_manual_chunk.update_date; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.car_manual_chunk.update_date IS '수정 일시';


--
-- TOC entry 4139 (class 0 OID 0)
-- Dependencies: 348
-- Name: COLUMN car_manual_chunk.update_user_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.car_manual_chunk.update_user_id IS '수정 사용자 ID';


--
-- TOC entry 339 (class 1259 OID 19519)
-- Name: casper_manual_chunks; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.casper_manual_chunks (
    chunk_id text NOT NULL,
    document_name text,
    chapter text,
    section text,
    subsection text,
    source_title text,
    page_start integer,
    page_end integer,
    chunk_index integer,
    chunk_text text NOT NULL,
    token_count integer
);


ALTER TABLE public.casper_manual_chunks OWNER TO postgres;

--
-- TOC entry 340 (class 1259 OID 19526)
-- Name: casper_manual_embeddings; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.casper_manual_embeddings (
    chunk_id text NOT NULL,
    embedding_model text NOT NULL,
    embedding_version text NOT NULL,
    embedding_dimension integer NOT NULL,
    embedding public.vector(768) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.casper_manual_embeddings OWNER TO postgres;

--
-- TOC entry 327 (class 1259 OID 18620)
-- Name: cff_caps; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.cff_caps (
    cff_caps_id character varying(20) NOT NULL,
    cff_caps_brand character varying(100) NOT NULL,
    cff_caps_nm character varying(150) NOT NULL,
    cff_caps_intensity integer,
    cff_caps_embed_txt text,
    cff_caps_embed_vec public.vector(1536),
    create_date timestamp with time zone DEFAULT now() NOT NULL,
    create_user_id character varying(50) NOT NULL,
    update_date timestamp with time zone DEFAULT now() NOT NULL,
    update_user_id character varying(50) NOT NULL
);


ALTER TABLE public.cff_caps OWNER TO postgres;

--
-- TOC entry 4143 (class 0 OID 0)
-- Dependencies: 327
-- Name: TABLE cff_caps; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.cff_caps IS '커피 캡슐';


--
-- TOC entry 4144 (class 0 OID 0)
-- Dependencies: 327
-- Name: COLUMN cff_caps.cff_caps_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.cff_caps.cff_caps_id IS '캡슐 식별 ID (YYYYMMDD_000001)';


--
-- TOC entry 4145 (class 0 OID 0)
-- Dependencies: 327
-- Name: COLUMN cff_caps.cff_caps_brand; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.cff_caps.cff_caps_brand IS '캡슐 브랜드명 (예: 네스프레소, 스타벅스)';


--
-- TOC entry 4146 (class 0 OID 0)
-- Dependencies: 327
-- Name: COLUMN cff_caps.cff_caps_nm; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.cff_caps.cff_caps_nm IS '캡슐 제품명 (예: 아르페지오)';


--
-- TOC entry 4147 (class 0 OID 0)
-- Dependencies: 327
-- Name: COLUMN cff_caps.cff_caps_intensity; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.cff_caps.cff_caps_intensity IS '커피 강도 (숫자)';


--
-- TOC entry 4148 (class 0 OID 0)
-- Dependencies: 327
-- Name: COLUMN cff_caps.cff_caps_embed_txt; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.cff_caps.cff_caps_embed_txt IS 'AI 임베딩용 원본 텍스트';


--
-- TOC entry 4149 (class 0 OID 0)
-- Dependencies: 327
-- Name: COLUMN cff_caps.cff_caps_embed_vec; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.cff_caps.cff_caps_embed_vec IS 'AI 임베딩 벡터 데이터 (pgvector 1536차원)';


--
-- TOC entry 4150 (class 0 OID 0)
-- Dependencies: 327
-- Name: COLUMN cff_caps.create_date; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.cff_caps.create_date IS '생성일시';


--
-- TOC entry 4151 (class 0 OID 0)
-- Dependencies: 327
-- Name: COLUMN cff_caps.create_user_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.cff_caps.create_user_id IS '생성자 ID';


--
-- TOC entry 4152 (class 0 OID 0)
-- Dependencies: 327
-- Name: COLUMN cff_caps.update_date; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.cff_caps.update_date IS '수정일시';


--
-- TOC entry 4153 (class 0 OID 0)
-- Dependencies: 327
-- Name: COLUMN cff_caps.update_user_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.cff_caps.update_user_id IS '수정자 ID';


--
-- TOC entry 326 (class 1259 OID 18610)
-- Name: cff_mach; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.cff_mach (
    cff_mach_id character varying(20) NOT NULL,
    cff_mach_brand character varying(100) NOT NULL,
    cff_mach_nm character varying(150) NOT NULL,
    create_date timestamp with time zone DEFAULT now() NOT NULL,
    create_user_id character varying(50) NOT NULL,
    update_date timestamp with time zone DEFAULT now() NOT NULL,
    update_user_id character varying(50) NOT NULL
);


ALTER TABLE public.cff_mach OWNER TO postgres;

--
-- TOC entry 4155 (class 0 OID 0)
-- Dependencies: 326
-- Name: TABLE cff_mach; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.cff_mach IS '커피 머신';


--
-- TOC entry 4156 (class 0 OID 0)
-- Dependencies: 326
-- Name: COLUMN cff_mach.cff_mach_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.cff_mach.cff_mach_id IS '커피 머신 식별 ID (YYYYMMDD_000001)';


--
-- TOC entry 4157 (class 0 OID 0)
-- Dependencies: 326
-- Name: COLUMN cff_mach.cff_mach_brand; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.cff_mach.cff_mach_brand IS '커피 머신 브랜드명 (예: 네스프레소, 일리)';


--
-- TOC entry 4158 (class 0 OID 0)
-- Dependencies: 326
-- Name: COLUMN cff_mach.cff_mach_nm; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.cff_mach.cff_mach_nm IS '커피 머신 모델명 (예: 시티즈, 에센사 미니)';


--
-- TOC entry 4159 (class 0 OID 0)
-- Dependencies: 326
-- Name: COLUMN cff_mach.create_date; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.cff_mach.create_date IS '생성일시';


--
-- TOC entry 4160 (class 0 OID 0)
-- Dependencies: 326
-- Name: COLUMN cff_mach.create_user_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.cff_mach.create_user_id IS '생성자 ID';


--
-- TOC entry 4161 (class 0 OID 0)
-- Dependencies: 326
-- Name: COLUMN cff_mach.update_date; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.cff_mach.update_date IS '수정일시';


--
-- TOC entry 4162 (class 0 OID 0)
-- Dependencies: 326
-- Name: COLUMN cff_mach.update_user_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.cff_mach.update_user_id IS '수정자 ID';


--
-- TOC entry 328 (class 1259 OID 18630)
-- Name: cff_mach_caps_rel; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.cff_mach_caps_rel (
    cff_mach_id character varying(20) NOT NULL,
    cff_caps_id character varying(20) NOT NULL,
    create_date timestamp with time zone DEFAULT now() NOT NULL,
    create_user_id character varying(50) NOT NULL,
    update_date timestamp with time zone DEFAULT now() NOT NULL,
    update_user_id character varying(50) NOT NULL
);


ALTER TABLE public.cff_mach_caps_rel OWNER TO postgres;

--
-- TOC entry 4164 (class 0 OID 0)
-- Dependencies: 328
-- Name: TABLE cff_mach_caps_rel; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.cff_mach_caps_rel IS '커피 머신 및 캡슐 호환 관계';


--
-- TOC entry 4165 (class 0 OID 0)
-- Dependencies: 328
-- Name: COLUMN cff_mach_caps_rel.cff_mach_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.cff_mach_caps_rel.cff_mach_id IS '커피 머신 식별 ID';


--
-- TOC entry 4166 (class 0 OID 0)
-- Dependencies: 328
-- Name: COLUMN cff_mach_caps_rel.cff_caps_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.cff_mach_caps_rel.cff_caps_id IS '커피 캡슐 식별 ID';


--
-- TOC entry 4167 (class 0 OID 0)
-- Dependencies: 328
-- Name: COLUMN cff_mach_caps_rel.create_date; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.cff_mach_caps_rel.create_date IS '생성일시';


--
-- TOC entry 4168 (class 0 OID 0)
-- Dependencies: 328
-- Name: COLUMN cff_mach_caps_rel.create_user_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.cff_mach_caps_rel.create_user_id IS '생성자 ID';


--
-- TOC entry 4169 (class 0 OID 0)
-- Dependencies: 328
-- Name: COLUMN cff_mach_caps_rel.update_date; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.cff_mach_caps_rel.update_date IS '수정일시';


--
-- TOC entry 4170 (class 0 OID 0)
-- Dependencies: 328
-- Name: COLUMN cff_mach_caps_rel.update_user_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.cff_mach_caps_rel.update_user_id IS '수정자 ID';


--
-- TOC entry 332 (class 1259 OID 18716)
-- Name: cff_mach_dtl; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.cff_mach_dtl (
    cff_mach_id character varying(20) NOT NULL,
    cff_mach_dtl_id character varying(20) NOT NULL,
    cff_mach_page_no character varying(100),
    cff_mach_embed_txt text NOT NULL,
    cff_mach_embed_vec public.vector,
    create_date timestamp with time zone DEFAULT now() NOT NULL,
    create_user_id character varying(50) NOT NULL,
    update_date timestamp with time zone DEFAULT now() NOT NULL,
    update_user_id character varying(50) NOT NULL
);


ALTER TABLE public.cff_mach_dtl OWNER TO postgres;

--
-- TOC entry 4172 (class 0 OID 0)
-- Dependencies: 332
-- Name: TABLE cff_mach_dtl; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.cff_mach_dtl IS '커피 머신 상세';


--
-- TOC entry 4173 (class 0 OID 0)
-- Dependencies: 332
-- Name: COLUMN cff_mach_dtl.cff_mach_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.cff_mach_dtl.cff_mach_id IS '커피 머신 식별 ID';


--
-- TOC entry 4174 (class 0 OID 0)
-- Dependencies: 332
-- Name: COLUMN cff_mach_dtl.cff_mach_dtl_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.cff_mach_dtl.cff_mach_dtl_id IS '커피 머신 상세 식별 ID';


--
-- TOC entry 4175 (class 0 OID 0)
-- Dependencies: 332
-- Name: COLUMN cff_mach_dtl.cff_mach_page_no; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.cff_mach_dtl.cff_mach_page_no IS '매뉴얼 원본 페이지 번호 (여러 페이지인 경우 쉼표로 구분)';


--
-- TOC entry 4176 (class 0 OID 0)
-- Dependencies: 332
-- Name: COLUMN cff_mach_dtl.cff_mach_embed_txt; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.cff_mach_dtl.cff_mach_embed_txt IS 'AI 임베딩 대상 매뉴얼 내용';


--
-- TOC entry 4177 (class 0 OID 0)
-- Dependencies: 332
-- Name: COLUMN cff_mach_dtl.cff_mach_embed_vec; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.cff_mach_dtl.cff_mach_embed_vec IS 'AI 임베딩 벡터 데이터';


--
-- TOC entry 4178 (class 0 OID 0)
-- Dependencies: 332
-- Name: COLUMN cff_mach_dtl.create_date; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.cff_mach_dtl.create_date IS '생성일시';


--
-- TOC entry 4179 (class 0 OID 0)
-- Dependencies: 332
-- Name: COLUMN cff_mach_dtl.create_user_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.cff_mach_dtl.create_user_id IS '생성자 ID';


--
-- TOC entry 4180 (class 0 OID 0)
-- Dependencies: 332
-- Name: COLUMN cff_mach_dtl.update_date; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.cff_mach_dtl.update_date IS '수정일시';


--
-- TOC entry 4181 (class 0 OID 0)
-- Dependencies: 332
-- Name: COLUMN cff_mach_dtl.update_user_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.cff_mach_dtl.update_user_id IS '수정자 ID';


--
-- TOC entry 331 (class 1259 OID 18674)
-- Name: cff_mach_vector_test; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.cff_mach_vector_test (
    cff_mach_id character varying(20) NOT NULL,
    cff_mach_brand character varying(100),
    cff_mach_nm character varying(150),
    cff_mach_embed_txt text,
    embedding public.vector(1536)
);


ALTER TABLE public.cff_mach_vector_test OWNER TO postgres;

--
-- TOC entry 336 (class 1259 OID 19436)
-- Name: seq_car; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.seq_car
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    MAXVALUE 999999
    CACHE 1
    CYCLE;


ALTER SEQUENCE public.seq_car OWNER TO postgres;

--
-- TOC entry 338 (class 1259 OID 19438)
-- Name: seq_car_manual_chunk; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.seq_car_manual_chunk
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    MAXVALUE 999999
    CACHE 1
    CYCLE;


ALTER SEQUENCE public.seq_car_manual_chunk OWNER TO postgres;

--
-- TOC entry 337 (class 1259 OID 19437)
-- Name: seq_car_manual_section; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.seq_car_manual_section
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    MAXVALUE 999999
    CACHE 1
    CYCLE;


ALTER SEQUENCE public.seq_car_manual_section OWNER TO postgres;

--
-- TOC entry 329 (class 1259 OID 18637)
-- Name: seq_cff_caps; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.seq_cff_caps
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    MAXVALUE 999999
    CACHE 1
    CYCLE;


ALTER SEQUENCE public.seq_cff_caps OWNER TO postgres;

--
-- TOC entry 330 (class 1259 OID 18638)
-- Name: seq_cff_mach; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.seq_cff_mach
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    MAXVALUE 999999
    CACHE 1
    CYCLE;


ALTER SEQUENCE public.seq_cff_mach OWNER TO postgres;

--
-- TOC entry 334 (class 1259 OID 19232)
-- Name: seq_cff_mach_caps_rel; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.seq_cff_mach_caps_rel
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    MAXVALUE 999999
    CACHE 1
    CYCLE;


ALTER SEQUENCE public.seq_cff_mach_caps_rel OWNER TO postgres;

--
-- TOC entry 333 (class 1259 OID 18725)
-- Name: seq_cff_mach_dtl; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.seq_cff_mach_dtl
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    MAXVALUE 999999
    CACHE 1
    CYCLE;


ALTER SEQUENCE public.seq_cff_mach_dtl OWNER TO postgres;

--
-- TOC entry 3943 (class 2606 OID 21578)
-- Name: car_manual_chapter car_manual_chapter_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.car_manual_chapter
    ADD CONSTRAINT car_manual_chapter_pkey PRIMARY KEY (car_id, car_manual_chapter_id);


--
-- TOC entry 3945 (class 2606 OID 21587)
-- Name: car_manual_chunk car_manual_chunk_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.car_manual_chunk
    ADD CONSTRAINT car_manual_chunk_pkey PRIMARY KEY (car_id, car_manual_chapter_id, car_manual_chunk_id);


--
-- TOC entry 3937 (class 2606 OID 19419)
-- Name: car car_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.car
    ADD CONSTRAINT car_pkey PRIMARY KEY (car_id);


--
-- TOC entry 3939 (class 2606 OID 19525)
-- Name: casper_manual_chunks casper_manual_chunks_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.casper_manual_chunks
    ADD CONSTRAINT casper_manual_chunks_pkey PRIMARY KEY (chunk_id);


--
-- TOC entry 3941 (class 2606 OID 19533)
-- Name: casper_manual_embeddings casper_manual_embeddings_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.casper_manual_embeddings
    ADD CONSTRAINT casper_manual_embeddings_pkey PRIMARY KEY (chunk_id);


--
-- TOC entry 3928 (class 2606 OID 18628)
-- Name: cff_caps cff_caps_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cff_caps
    ADD CONSTRAINT cff_caps_pkey PRIMARY KEY (cff_caps_id);


--
-- TOC entry 3931 (class 2606 OID 18636)
-- Name: cff_mach_caps_rel cff_mach_caps_rel_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cff_mach_caps_rel
    ADD CONSTRAINT cff_mach_caps_rel_pkey PRIMARY KEY (cff_mach_id, cff_caps_id);


--
-- TOC entry 3935 (class 2606 OID 18724)
-- Name: cff_mach_dtl cff_mach_dtl_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cff_mach_dtl
    ADD CONSTRAINT cff_mach_dtl_pkey PRIMARY KEY (cff_mach_id, cff_mach_dtl_id);


--
-- TOC entry 3926 (class 2606 OID 18618)
-- Name: cff_mach cff_mach_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cff_mach
    ADD CONSTRAINT cff_mach_pkey PRIMARY KEY (cff_mach_id);


--
-- TOC entry 3933 (class 2606 OID 18680)
-- Name: cff_mach_vector_test cff_mach_vector_test_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cff_mach_vector_test
    ADD CONSTRAINT cff_mach_vector_test_pkey PRIMARY KEY (cff_mach_id);


--
-- TOC entry 3929 (class 1259 OID 18629)
-- Name: idx_cff_caps_embed_vec; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_cff_caps_embed_vec ON public.cff_caps USING hnsw (cff_caps_embed_vec public.vector_cosine_ops);


--
-- TOC entry 3946 (class 2606 OID 19534)
-- Name: casper_manual_embeddings casper_manual_embeddings_chunk_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.casper_manual_embeddings
    ADD CONSTRAINT casper_manual_embeddings_chunk_id_fkey FOREIGN KEY (chunk_id) REFERENCES public.casper_manual_chunks(chunk_id) ON DELETE CASCADE;


--
-- TOC entry 4102 (class 0 OID 0)
-- Dependencies: 33
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: pg_database_owner
--

GRANT USAGE ON SCHEMA public TO postgres;
GRANT USAGE ON SCHEMA public TO anon;
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT USAGE ON SCHEMA public TO service_role;


--
-- TOC entry 4103 (class 0 OID 0)
-- Dependencies: 449
-- Name: FUNCTION delete_user_own_account(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.delete_user_own_account() TO anon;
GRANT ALL ON FUNCTION public.delete_user_own_account() TO authenticated;
GRANT ALL ON FUNCTION public.delete_user_own_account() TO service_role;


--
-- TOC entry 4104 (class 0 OID 0)
-- Dependencies: 576
-- Name: FUNCTION fn_gen_biz_id(p_tbl_nm text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.fn_gen_biz_id(p_tbl_nm text) TO anon;
GRANT ALL ON FUNCTION public.fn_gen_biz_id(p_tbl_nm text) TO authenticated;
GRANT ALL ON FUNCTION public.fn_gen_biz_id(p_tbl_nm text) TO service_role;


--
-- TOC entry 4105 (class 0 OID 0)
-- Dependencies: 577
-- Name: FUNCTION match_manual_chunks(query_embedding public.vector, match_count integer, filter_model text, filter_version text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.match_manual_chunks(query_embedding public.vector, match_count integer, filter_model text, filter_version text) TO anon;
GRANT ALL ON FUNCTION public.match_manual_chunks(query_embedding public.vector, match_count integer, filter_model text, filter_version text) TO authenticated;
GRANT ALL ON FUNCTION public.match_manual_chunks(query_embedding public.vector, match_count integer, filter_model text, filter_version text) TO service_role;


--
-- TOC entry 4116 (class 0 OID 0)
-- Dependencies: 335
-- Name: TABLE car; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.car TO anon;
GRANT ALL ON TABLE public.car TO authenticated;
GRANT ALL ON TABLE public.car TO service_role;


--
-- TOC entry 4127 (class 0 OID 0)
-- Dependencies: 347
-- Name: TABLE car_manual_chapter; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.car_manual_chapter TO anon;
GRANT ALL ON TABLE public.car_manual_chapter TO authenticated;
GRANT ALL ON TABLE public.car_manual_chapter TO service_role;


--
-- TOC entry 4140 (class 0 OID 0)
-- Dependencies: 348
-- Name: TABLE car_manual_chunk; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.car_manual_chunk TO anon;
GRANT ALL ON TABLE public.car_manual_chunk TO authenticated;
GRANT ALL ON TABLE public.car_manual_chunk TO service_role;


--
-- TOC entry 4141 (class 0 OID 0)
-- Dependencies: 339
-- Name: TABLE casper_manual_chunks; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.casper_manual_chunks TO anon;
GRANT ALL ON TABLE public.casper_manual_chunks TO authenticated;
GRANT ALL ON TABLE public.casper_manual_chunks TO service_role;


--
-- TOC entry 4142 (class 0 OID 0)
-- Dependencies: 340
-- Name: TABLE casper_manual_embeddings; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.casper_manual_embeddings TO anon;
GRANT ALL ON TABLE public.casper_manual_embeddings TO authenticated;
GRANT ALL ON TABLE public.casper_manual_embeddings TO service_role;


--
-- TOC entry 4154 (class 0 OID 0)
-- Dependencies: 327
-- Name: TABLE cff_caps; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.cff_caps TO anon;
GRANT ALL ON TABLE public.cff_caps TO authenticated;
GRANT ALL ON TABLE public.cff_caps TO service_role;


--
-- TOC entry 4163 (class 0 OID 0)
-- Dependencies: 326
-- Name: TABLE cff_mach; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.cff_mach TO anon;
GRANT ALL ON TABLE public.cff_mach TO authenticated;
GRANT ALL ON TABLE public.cff_mach TO service_role;


--
-- TOC entry 4171 (class 0 OID 0)
-- Dependencies: 328
-- Name: TABLE cff_mach_caps_rel; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.cff_mach_caps_rel TO anon;
GRANT ALL ON TABLE public.cff_mach_caps_rel TO authenticated;
GRANT ALL ON TABLE public.cff_mach_caps_rel TO service_role;


--
-- TOC entry 4182 (class 0 OID 0)
-- Dependencies: 332
-- Name: TABLE cff_mach_dtl; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.cff_mach_dtl TO anon;
GRANT ALL ON TABLE public.cff_mach_dtl TO authenticated;
GRANT ALL ON TABLE public.cff_mach_dtl TO service_role;


--
-- TOC entry 4183 (class 0 OID 0)
-- Dependencies: 331
-- Name: TABLE cff_mach_vector_test; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.cff_mach_vector_test TO anon;
GRANT ALL ON TABLE public.cff_mach_vector_test TO authenticated;
GRANT ALL ON TABLE public.cff_mach_vector_test TO service_role;


--
-- TOC entry 4184 (class 0 OID 0)
-- Dependencies: 336
-- Name: SEQUENCE seq_car; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.seq_car TO anon;
GRANT ALL ON SEQUENCE public.seq_car TO authenticated;
GRANT ALL ON SEQUENCE public.seq_car TO service_role;


--
-- TOC entry 4185 (class 0 OID 0)
-- Dependencies: 338
-- Name: SEQUENCE seq_car_manual_chunk; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.seq_car_manual_chunk TO anon;
GRANT ALL ON SEQUENCE public.seq_car_manual_chunk TO authenticated;
GRANT ALL ON SEQUENCE public.seq_car_manual_chunk TO service_role;


--
-- TOC entry 4186 (class 0 OID 0)
-- Dependencies: 337
-- Name: SEQUENCE seq_car_manual_section; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.seq_car_manual_section TO anon;
GRANT ALL ON SEQUENCE public.seq_car_manual_section TO authenticated;
GRANT ALL ON SEQUENCE public.seq_car_manual_section TO service_role;


--
-- TOC entry 4187 (class 0 OID 0)
-- Dependencies: 329
-- Name: SEQUENCE seq_cff_caps; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.seq_cff_caps TO anon;
GRANT ALL ON SEQUENCE public.seq_cff_caps TO authenticated;
GRANT ALL ON SEQUENCE public.seq_cff_caps TO service_role;


--
-- TOC entry 4188 (class 0 OID 0)
-- Dependencies: 330
-- Name: SEQUENCE seq_cff_mach; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.seq_cff_mach TO anon;
GRANT ALL ON SEQUENCE public.seq_cff_mach TO authenticated;
GRANT ALL ON SEQUENCE public.seq_cff_mach TO service_role;


--
-- TOC entry 4189 (class 0 OID 0)
-- Dependencies: 334
-- Name: SEQUENCE seq_cff_mach_caps_rel; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.seq_cff_mach_caps_rel TO anon;
GRANT ALL ON SEQUENCE public.seq_cff_mach_caps_rel TO authenticated;
GRANT ALL ON SEQUENCE public.seq_cff_mach_caps_rel TO service_role;


--
-- TOC entry 4190 (class 0 OID 0)
-- Dependencies: 333
-- Name: SEQUENCE seq_cff_mach_dtl; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.seq_cff_mach_dtl TO anon;
GRANT ALL ON SEQUENCE public.seq_cff_mach_dtl TO authenticated;
GRANT ALL ON SEQUENCE public.seq_cff_mach_dtl TO service_role;


--
-- TOC entry 2647 (class 826 OID 16494)
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON SEQUENCES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON SEQUENCES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON SEQUENCES TO service_role;


--
-- TOC entry 2648 (class 826 OID 16495)
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: public; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON SEQUENCES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON SEQUENCES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON SEQUENCES TO service_role;


--
-- TOC entry 2646 (class 826 OID 16493)
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON FUNCTIONS TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON FUNCTIONS TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON FUNCTIONS TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON FUNCTIONS TO service_role;


--
-- TOC entry 2650 (class 826 OID 16497)
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: public; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON FUNCTIONS TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON FUNCTIONS TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON FUNCTIONS TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON FUNCTIONS TO service_role;


--
-- TOC entry 2645 (class 826 OID 16492)
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TABLES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TABLES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TABLES TO service_role;


--
-- TOC entry 2649 (class 826 OID 16496)
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: public; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON TABLES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON TABLES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON TABLES TO service_role;


-- Completed on 2026-10-01 21:21:33

--
-- PostgreSQL database dump complete
--

