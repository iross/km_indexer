--
-- PostgreSQL database dump
--

-- Dumped from database version 10.13
-- Dumped by pg_dump version 10.13

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_with_oids = false;

--
-- Name: alice_abbreviations; Type: TABLE; Schema: public; Owner: kinderminer
--

CREATE TABLE public.alice_abbreviations (
    sequential_id integer,
    pubmed_id text,
    publication_year text,
    long_form_id integer,
    short_form_id integer,
    long_form text,
    short_form text
);


ALTER TABLE public.alice_abbreviations OWNER TO kinderminer;

--
-- Name: alice_abbreviations_pubmed_id_idx; Type: INDEX; Schema: public; Owner: kinderminer
--

CREATE INDEX alice_abbreviations_pubmed_id_idx ON public.alice_abbreviations USING btree (pubmed_id);

--
-- PostgreSQL database dump complete
--

