--
-- PostgreSQL database dump
--

-- Dumped from database version 14.2
-- Dumped by pg_dump version 14.2

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

--
-- Name: hstore; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS hstore WITH SCHEMA public;


--
-- Name: EXTENSION hstore; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION hstore IS 'data type for storing sets of (key, value) pairs';


--
-- Name: postgis; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA public;


--
-- Name: EXTENSION postgis; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION postgis IS 'PostGIS geometry and geography spatial types and functions';


--
-- Name: osmosisupdate(); Type: FUNCTION; Schema: public; Owner: mvexel
--

CREATE FUNCTION public.osmosisupdate() RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
END;
$$;


ALTER FUNCTION public.osmosisupdate() OWNER TO mvexel;

--
-- Name: unnest_bbox_way_nodes(); Type: FUNCTION; Schema: public; Owner: mvexel
--

CREATE FUNCTION public.unnest_bbox_way_nodes() RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
	previousId ways.id%TYPE;
	currentId ways.id%TYPE;
	result bigint[];
	wayNodeRow way_nodes%ROWTYPE;
	wayNodes ways.nodes%TYPE;
BEGIN
	FOR wayNodes IN SELECT bw.nodes FROM bbox_ways bw LOOP
		FOR i IN 1 .. array_upper(wayNodes, 1) LOOP
			INSERT INTO bbox_way_nodes (id) VALUES (wayNodes[i]);
		END LOOP;
	END LOOP;
END;
$$;


ALTER FUNCTION public.unnest_bbox_way_nodes() OWNER TO mvexel;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: nodes; Type: TABLE; Schema: public; Owner: mvexel
--

CREATE TABLE public.nodes (
    id bigint NOT NULL,
    version integer NOT NULL,
    user_id integer NOT NULL,
    tstamp timestamp without time zone NOT NULL,
    changeset_id bigint NOT NULL,
    tags public.hstore,
    geom public.geometry(Point,4326)
);


ALTER TABLE public.nodes OWNER TO mvexel;

--
-- Name: relation_members; Type: TABLE; Schema: public; Owner: mvexel
--

CREATE TABLE public.relation_members (
    relation_id bigint NOT NULL,
    member_id bigint NOT NULL,
    member_type character(1) NOT NULL,
    member_role text NOT NULL,
    sequence_id integer NOT NULL
);
ALTER TABLE ONLY public.relation_members ALTER COLUMN relation_id SET (n_distinct=-0.09);
ALTER TABLE ONLY public.relation_members ALTER COLUMN member_id SET (n_distinct=-0.62);
ALTER TABLE ONLY public.relation_members ALTER COLUMN member_role SET (n_distinct=6500);
ALTER TABLE ONLY public.relation_members ALTER COLUMN sequence_id SET (n_distinct=10000);


ALTER TABLE public.relation_members OWNER TO mvexel;

--
-- Name: relations; Type: TABLE; Schema: public; Owner: mvexel
--

CREATE TABLE public.relations (
    id bigint NOT NULL,
    version integer NOT NULL,
    user_id integer NOT NULL,
    tstamp timestamp without time zone NOT NULL,
    changeset_id bigint NOT NULL,
    tags public.hstore
);


ALTER TABLE public.relations OWNER TO mvexel;

--
-- Name: schema_info; Type: TABLE; Schema: public; Owner: mvexel
--

CREATE TABLE public.schema_info (
    version integer NOT NULL
);


ALTER TABLE public.schema_info OWNER TO mvexel;

--
-- Name: users; Type: TABLE; Schema: public; Owner: mvexel
--

CREATE TABLE public.users (
    id integer NOT NULL,
    name text NOT NULL
);


ALTER TABLE public.users OWNER TO mvexel;

--
-- Name: way_nodes; Type: TABLE; Schema: public; Owner: mvexel
--

CREATE TABLE public.way_nodes (
    way_id bigint NOT NULL,
    node_id bigint NOT NULL,
    sequence_id integer NOT NULL
);
ALTER TABLE ONLY public.way_nodes ALTER COLUMN way_id SET (n_distinct=-0.08);
ALTER TABLE ONLY public.way_nodes ALTER COLUMN node_id SET (n_distinct=-0.83);
ALTER TABLE ONLY public.way_nodes ALTER COLUMN sequence_id SET (n_distinct=2000);


ALTER TABLE public.way_nodes OWNER TO mvexel;

--
-- Name: ways; Type: TABLE; Schema: public; Owner: mvexel
--

CREATE TABLE public.ways (
    id bigint NOT NULL,
    version integer NOT NULL,
    user_id integer NOT NULL,
    tstamp timestamp without time zone NOT NULL,
    changeset_id bigint NOT NULL,
    tags public.hstore,
    nodes bigint[],
    linestring public.geometry(Geometry,4326)
);


ALTER TABLE public.ways OWNER TO mvexel;

--
-- Name: nodes pk_nodes; Type: CONSTRAINT; Schema: public; Owner: mvexel
--

ALTER TABLE ONLY public.nodes
    ADD CONSTRAINT pk_nodes PRIMARY KEY (id);


--
-- Name: relation_members pk_relation_members; Type: CONSTRAINT; Schema: public; Owner: mvexel
--

ALTER TABLE ONLY public.relation_members
    ADD CONSTRAINT pk_relation_members PRIMARY KEY (relation_id, sequence_id);

ALTER TABLE public.relation_members CLUSTER ON pk_relation_members;


--
-- Name: relations pk_relations; Type: CONSTRAINT; Schema: public; Owner: mvexel
--

ALTER TABLE ONLY public.relations
    ADD CONSTRAINT pk_relations PRIMARY KEY (id);


--
-- Name: schema_info pk_schema_info; Type: CONSTRAINT; Schema: public; Owner: mvexel
--

ALTER TABLE ONLY public.schema_info
    ADD CONSTRAINT pk_schema_info PRIMARY KEY (version);


--
-- Name: users pk_users; Type: CONSTRAINT; Schema: public; Owner: mvexel
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT pk_users PRIMARY KEY (id);


--
-- Name: way_nodes pk_way_nodes; Type: CONSTRAINT; Schema: public; Owner: mvexel
--

ALTER TABLE ONLY public.way_nodes
    ADD CONSTRAINT pk_way_nodes PRIMARY KEY (way_id, sequence_id);

ALTER TABLE public.way_nodes CLUSTER ON pk_way_nodes;


--
-- Name: ways pk_ways; Type: CONSTRAINT; Schema: public; Owner: mvexel
--

ALTER TABLE ONLY public.ways
    ADD CONSTRAINT pk_ways PRIMARY KEY (id);


--
-- Name: idx_nodes_geom; Type: INDEX; Schema: public; Owner: mvexel
--

CREATE INDEX idx_nodes_geom ON public.nodes USING gist (geom);

ALTER TABLE public.nodes CLUSTER ON idx_nodes_geom;


--
-- Name: idx_relation_members_member_id_and_type; Type: INDEX; Schema: public; Owner: mvexel
--

CREATE INDEX idx_relation_members_member_id_and_type ON public.relation_members USING btree (member_id, member_type);


--
-- Name: idx_way_nodes_node_id; Type: INDEX; Schema: public; Owner: mvexel
--

CREATE INDEX idx_way_nodes_node_id ON public.way_nodes USING btree (node_id);


--
-- Name: idx_ways_linestring; Type: INDEX; Schema: public; Owner: mvexel
--

CREATE INDEX idx_ways_linestring ON public.ways USING gist (linestring);

ALTER TABLE public.ways CLUSTER ON idx_ways_linestring;


--
-- PostgreSQL database dump complete
--

