--
-- PostgreSQL database dump
--

\restrict whhN33j0yH2v0nErTWPQbUFGkfGYaWvg8Rb7KNfE5Nl9U30a55Iluz0OiQsXVx3

-- Dumped from database version 16.12
-- Dumped by pg_dump version 16.12

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
-- Name: invoicekind; Type: TYPE; Schema: public; Owner: uask_user
--

CREATE TYPE public.invoicekind AS ENUM (
    'TOPUP',
    'SUBSCRIPTION',
    'ADJUSTMENT'
);


ALTER TYPE public.invoicekind OWNER TO uask_user;

--
-- Name: invoicelineitemkind; Type: TYPE; Schema: public; Owner: uask_user
--

CREATE TYPE public.invoicelineitemkind AS ENUM (
    'TOPUP_CREDITS',
    'SUBSCRIPTION_FEE',
    'USAGE_CHARGE',
    'REFUND',
    'DISCOUNT',
    'TAX',
    'ADJUSTMENT'
);


ALTER TYPE public.invoicelineitemkind OWNER TO uask_user;

--
-- Name: invoicestatus; Type: TYPE; Schema: public; Owner: uask_user
--

CREATE TYPE public.invoicestatus AS ENUM (
    'DRAFT',
    'OPEN',
    'PAID',
    'VOID',
    'UNCOLLECTIBLE',
    'REFUNDED',
    'PARTIALLY_REFUNDED'
);


ALTER TYPE public.invoicestatus OWNER TO uask_user;

--
-- Name: promptmodeenum; Type: TYPE; Schema: public; Owner: uask_user
--

CREATE TYPE public.promptmodeenum AS ENUM (
    'SOLVE',
    'VERIFY',
    'PLOT_TRIGGER',
    'PLOT_SPEC',
    'OCR_EXTRACT'
);


ALTER TYPE public.promptmodeenum OWNER TO uask_user;

--
-- Name: promptroleenum; Type: TYPE; Schema: public; Owner: uask_user
--

CREATE TYPE public.promptroleenum AS ENUM (
    'SYSTEM',
    'DEVELOPER',
    'USER',
    'INTERNAL'
);


ALTER TYPE public.promptroleenum OWNER TO uask_user;

--
-- Name: prompttierenum; Type: TYPE; Schema: public; Owner: uask_user
--

CREATE TYPE public.prompttierenum AS ENUM (
    'SHORT_STEPS',
    'FINAL',
    'STANDARD',
    'RESEARCH'
);


ALTER TYPE public.prompttierenum OWNER TO uask_user;

--
-- Name: providerpricingaction; Type: TYPE; Schema: public; Owner: uask_user
--

CREATE TYPE public.providerpricingaction AS ENUM (
    'CREATE',
    'UPDATE',
    'RETIRE'
);


ALTER TYPE public.providerpricingaction OWNER TO uask_user;

--
-- Name: taxmode; Type: TYPE; Schema: public; Owner: uask_user
--

CREATE TYPE public.taxmode AS ENUM (
    'NONE',
    'ESTIMATED',
    'FINAL'
);


ALTER TYPE public.taxmode OWNER TO uask_user;

--
-- Name: trimstrategyenum; Type: TYPE; Schema: public; Owner: uask_user
--

CREATE TYPE public.trimstrategyenum AS ENUM (
    'NONE',
    'TRIM_CONTEXT_FIRST',
    'TRIM_USER_FIRST',
    'SUMMARIZE_CONTEXT',
    'TRIM_EVERYTHING_EXCEPT_PLOT_PLAN'
);


ALTER TYPE public.trimstrategyenum OWNER TO uask_user;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: adminauditlog; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.adminauditlog (
    id integer NOT NULL,
    admin_user_id integer NOT NULL,
    action character varying NOT NULL,
    entity_type character varying NOT NULL,
    entity_id character varying,
    before_json json,
    after_json json,
    reason character varying,
    ip_address character varying,
    user_agent character varying,
    idempotency_key character varying,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.adminauditlog OWNER TO uask_user;

--
-- Name: adminauditlog_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.adminauditlog_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.adminauditlog_id_seq OWNER TO uask_user;

--
-- Name: adminauditlog_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.adminauditlog_id_seq OWNED BY public.adminauditlog.id;


--
-- Name: adminnote; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.adminnote (
    id integer NOT NULL,
    user_id integer NOT NULL,
    admin_name character varying NOT NULL,
    content character varying NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.adminnote OWNER TO uask_user;

--
-- Name: adminnote_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.adminnote_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.adminnote_id_seq OWNER TO uask_user;

--
-- Name: adminnote_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.adminnote_id_seq OWNED BY public.adminnote.id;


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO uask_user;

--
-- Name: attemptevent; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.attemptevent (
    id integer NOT NULL,
    attempt_id character varying NOT NULL,
    seq integer NOT NULL,
    type character varying NOT NULL,
    payload json,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.attemptevent OWNER TO uask_user;

--
-- Name: attemptevent_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.attemptevent_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.attemptevent_id_seq OWNER TO uask_user;

--
-- Name: attemptevent_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.attemptevent_id_seq OWNED BY public.attemptevent.id;


--
-- Name: billingledger; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.billingledger (
    id integer NOT NULL,
    user_id integer NOT NULL,
    action_type character varying NOT NULL,
    request_id character varying,
    source_asset_id character varying,
    question_id character varying,
    idempotency_key character varying,
    status character varying NOT NULL,
    credits_charged numeric(20,10),
    estimated_credits numeric(20,10),
    actual_credits numeric(20,10),
    delta_credits numeric(20,10),
    credits_before numeric(20,10) NOT NULL,
    credits_after numeric(20,10) NOT NULL,
    fee_tokens_applied integer NOT NULL,
    estimated_usage_json json,
    actual_usage_json json,
    token_usage_json json,
    pricing_snapshot_json json,
    config_version_id integer,
    provider_cost_usd numeric(20,10),
    markup_multiplier numeric(20,10),
    fixed_fee_usd numeric(20,10),
    charge_usd numeric(20,10),
    credit_value_usd numeric(20,10),
    tier character varying,
    finalized_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    ok boolean NOT NULL,
    error_json json
);


ALTER TABLE public.billingledger OWNER TO uask_user;

--
-- Name: billingledger_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.billingledger_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.billingledger_id_seq OWNER TO uask_user;

--
-- Name: billingledger_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.billingledger_id_seq OWNED BY public.billingledger.id;


--
-- Name: canonicalproblem; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.canonicalproblem (
    id integer NOT NULL,
    normalized_problem_hash character varying NOT NULL,
    normalized_text character varying NOT NULL,
    intent character varying NOT NULL,
    canonical_math_object character varying NOT NULL,
    assumptions_hash character varying,
    prompt_version character varying,
    solver_version character varying,
    schema_version character varying,
    normalized_latex_blocks json,
    subject character varying,
    language character varying NOT NULL,
    created_at timestamp without time zone NOT NULL,
    last_seen_at timestamp without time zone NOT NULL,
    seen_count integer NOT NULL
);


ALTER TABLE public.canonicalproblem OWNER TO uask_user;

--
-- Name: canonicalproblem_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.canonicalproblem_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.canonicalproblem_id_seq OWNER TO uask_user;

--
-- Name: canonicalproblem_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.canonicalproblem_id_seq OWNED BY public.canonicalproblem.id;


--
-- Name: canonicalsolution; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.canonicalsolution (
    id integer NOT NULL,
    problem_id integer NOT NULL,
    solution_json json,
    verification_status character varying NOT NULL,
    verification_report json,
    prompt_version character varying,
    model_id character varying,
    created_at timestamp without time zone NOT NULL,
    last_served_at timestamp without time zone NOT NULL,
    served_count integer NOT NULL
);


ALTER TABLE public.canonicalsolution OWNER TO uask_user;

--
-- Name: canonicalsolution_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.canonicalsolution_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.canonicalsolution_id_seq OWNER TO uask_user;

--
-- Name: canonicalsolution_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.canonicalsolution_id_seq OWNED BY public.canonicalsolution.id;


--
-- Name: chateditcopy; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.chateditcopy (
    id integer NOT NULL,
    chat_id integer NOT NULL,
    user_id integer NOT NULL,
    edited_md text,
    canonical_md_hash character varying NOT NULL,
    version integer NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


ALTER TABLE public.chateditcopy OWNER TO uask_user;

--
-- Name: chateditcopy_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.chateditcopy_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.chateditcopy_id_seq OWNER TO uask_user;

--
-- Name: chateditcopy_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.chateditcopy_id_seq OWNED BY public.chateditcopy.id;


--
-- Name: chateditcopyv2; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.chateditcopyv2 (
    id integer NOT NULL,
    chat_id integer NOT NULL,
    user_id integer NOT NULL,
    edited_md text,
    canonical_md_hash character varying NOT NULL,
    version integer NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


ALTER TABLE public.chateditcopyv2 OWNER TO uask_user;

--
-- Name: chateditcopyv2_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.chateditcopyv2_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.chateditcopyv2_id_seq OWNER TO uask_user;

--
-- Name: chateditcopyv2_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.chateditcopyv2_id_seq OWNED BY public.chateditcopyv2.id;


--
-- Name: chateditnotev2; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.chateditnotev2 (
    id integer NOT NULL,
    chat_id integer NOT NULL,
    user_id integer NOT NULL,
    notes_md text,
    version integer NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


ALTER TABLE public.chateditnotev2 OWNER TO uask_user;

--
-- Name: chateditnotev2_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.chateditnotev2_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.chateditnotev2_id_seq OWNER TO uask_user;

--
-- Name: chateditnotev2_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.chateditnotev2_id_seq OWNED BY public.chateditnotev2.id;


--
-- Name: chatmessage; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.chatmessage (
    id integer NOT NULL,
    session_id integer NOT NULL,
    role character varying NOT NULL,
    content character varying NOT NULL,
    structured_data json,
    telemetry json,
    model_used character varying,
    tokens_used integer NOT NULL,
    subject character varying,
    grade_level character varying,
    difficulty character varying,
    topics json,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.chatmessage OWNER TO uask_user;

--
-- Name: chatmessage_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.chatmessage_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.chatmessage_id_seq OWNER TO uask_user;

--
-- Name: chatmessage_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.chatmessage_id_seq OWNED BY public.chatmessage.id;


--
-- Name: chatnote; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.chatnote (
    id integer NOT NULL,
    chat_id integer NOT NULL,
    user_id integer NOT NULL,
    notes_md text,
    version integer NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


ALTER TABLE public.chatnote OWNER TO uask_user;

--
-- Name: chatnote_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.chatnote_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.chatnote_id_seq OWNER TO uask_user;

--
-- Name: chatnote_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.chatnote_id_seq OWNED BY public.chatnote.id;


--
-- Name: chatsession; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.chatsession (
    id integer NOT NULL,
    user_id integer,
    title character varying NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    subject character varying,
    topic character varying,
    is_saved boolean NOT NULL,
    learning_mode character varying,
    requested_mode character varying,
    solve_tier character varying
);


ALTER TABLE public.chatsession OWNER TO uask_user;

--
-- Name: chatsession_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.chatsession_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.chatsession_id_seq OWNER TO uask_user;

--
-- Name: chatsession_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.chatsession_id_seq OWNED BY public.chatsession.id;


--
-- Name: credit_hold_allocations; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.credit_hold_allocations (
    hold_id character varying NOT NULL,
    lot_id character varying NOT NULL,
    amount numeric(20,10) NOT NULL
);


ALTER TABLE public.credit_hold_allocations OWNER TO uask_user;

--
-- Name: credit_holds; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.credit_holds (
    hold_id character varying NOT NULL,
    user_id integer NOT NULL,
    request_id character varying NOT NULL,
    attempt_id character varying,
    idempotency_key character varying NOT NULL,
    tier character varying NOT NULL,
    action character varying NOT NULL,
    amount_reserved numeric(20,10) NOT NULL,
    amount_settled numeric(20,10) NOT NULL,
    amount_released numeric(20,10) NOT NULL,
    status character varying NOT NULL,
    created_at timestamp without time zone NOT NULL,
    expires_at timestamp without time zone NOT NULL
);


ALTER TABLE public.credit_holds OWNER TO uask_user;

--
-- Name: credit_lots; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.credit_lots (
    lot_id character varying NOT NULL,
    user_id integer NOT NULL,
    source character varying NOT NULL,
    credits_total numeric(20,10) NOT NULL,
    credits_remaining numeric(20,10) NOT NULL,
    expires_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.credit_lots OWNER TO uask_user;

--
-- Name: credit_packs; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.credit_packs (
    id integer NOT NULL,
    pack_code character varying NOT NULL,
    credits integer NOT NULL,
    pricing_strategy_label character varying NOT NULL,
    is_active boolean NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


ALTER TABLE public.credit_packs OWNER TO uask_user;

--
-- Name: credit_packs_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.credit_packs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.credit_packs_id_seq OWNER TO uask_user;

--
-- Name: credit_packs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.credit_packs_id_seq OWNED BY public.credit_packs.id;


--
-- Name: credit_transfers; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.credit_transfers (
    id character varying NOT NULL,
    sender_user_id integer NOT NULL,
    recipient_email character varying NOT NULL,
    recipient_user_id integer,
    amount numeric(20,10) NOT NULL,
    status character varying NOT NULL,
    idempotency_key character varying NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    expires_at timestamp without time zone NOT NULL,
    claimed_at timestamp without time zone,
    failure_reason character varying,
    sender_ip_hash character varying,
    escrow_lot_id integer,
    sender_ledger_id integer,
    recipient_ledger_id integer,
    refund_ledger_id integer
);


ALTER TABLE public.credit_transfers OWNER TO uask_user;

--
-- Name: credithold; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.credithold (
    id integer NOT NULL,
    user_id integer NOT NULL,
    subscription_id integer NOT NULL,
    request_id character varying NOT NULL,
    question_id character varying,
    reserved_credits numeric(20,10),
    status character varying NOT NULL,
    meta json,
    created_at timestamp without time zone NOT NULL,
    finalized_at timestamp without time zone
);


ALTER TABLE public.credithold OWNER TO uask_user;

--
-- Name: credithold_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.credithold_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.credithold_id_seq OWNER TO uask_user;

--
-- Name: credithold_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.credithold_id_seq OWNED BY public.credithold.id;


--
-- Name: creditlot; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.creditlot (
    id integer NOT NULL,
    user_id integer NOT NULL,
    subscription_id integer,
    credits_total numeric(20,10) NOT NULL,
    credits_remaining numeric(20,10) NOT NULL,
    lot_type character varying NOT NULL,
    status character varying NOT NULL,
    source character varying NOT NULL,
    external_ref character varying,
    currency character varying NOT NULL,
    amount_paid numeric(20,10),
    purchased_at timestamp without time zone NOT NULL,
    expires_at timestamp without time zone,
    source_program_id integer,
    source_payment_id character varying,
    source_attempt_id character varying,
    reason_code character varying,
    is_active boolean NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.creditlot OWNER TO uask_user;

--
-- Name: creditlot_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.creditlot_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.creditlot_id_seq OWNER TO uask_user;

--
-- Name: creditlot_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.creditlot_id_seq OWNED BY public.creditlot.id;


--
-- Name: creditlotconsumption; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.creditlotconsumption (
    id integer NOT NULL,
    user_id integer NOT NULL,
    subscription_id integer,
    credit_lot_id integer NOT NULL,
    usage_ledger_id integer,
    ledger_event_id integer,
    attempt_id character varying,
    direction character varying NOT NULL,
    amount numeric(20,10) NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.creditlotconsumption OWNER TO uask_user;

--
-- Name: creditlotconsumption_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.creditlotconsumption_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.creditlotconsumption_id_seq OWNER TO uask_user;

--
-- Name: creditlotconsumption_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.creditlotconsumption_id_seq OWNED BY public.creditlotconsumption.id;


--
-- Name: creditprogramdefinition; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.creditprogramdefinition (
    id integer NOT NULL,
    name character varying NOT NULL,
    slug character varying NOT NULL,
    description character varying,
    status character varying NOT NULL,
    monthly_gift_credits numeric(20,10),
    gift_expiry_window_days integer NOT NULL,
    entitlements json,
    purchase_bonus_rules json,
    effective_from timestamp without time zone NOT NULL,
    effective_to timestamp without time zone,
    display_price_monthly_usd numeric(20,10),
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    created_by integer
);


ALTER TABLE public.creditprogramdefinition OWNER TO uask_user;

--
-- Name: creditprogramdefinition_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.creditprogramdefinition_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.creditprogramdefinition_id_seq OWNER TO uask_user;

--
-- Name: creditprogramdefinition_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.creditprogramdefinition_id_seq OWNED BY public.creditprogramdefinition.id;


--
-- Name: creditprogramenrollment; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.creditprogramenrollment (
    id integer NOT NULL,
    user_id integer NOT NULL,
    program_id integer NOT NULL,
    status character varying NOT NULL,
    started_at timestamp without time zone NOT NULL,
    ended_at timestamp without time zone,
    paused_at timestamp without time zone,
    last_grant_month character varying,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


ALTER TABLE public.creditprogramenrollment OWNER TO uask_user;

--
-- Name: creditprogramenrollment_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.creditprogramenrollment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.creditprogramenrollment_id_seq OWNER TO uask_user;

--
-- Name: creditprogramenrollment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.creditprogramenrollment_id_seq OWNED BY public.creditprogramenrollment.id;


--
-- Name: creditprogramgrantlog; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.creditprogramgrantlog (
    id integer NOT NULL,
    enrollment_id integer NOT NULL,
    user_id integer NOT NULL,
    program_id integer NOT NULL,
    grant_month character varying NOT NULL,
    credits_granted numeric(20,10) NOT NULL,
    credit_lot_id integer NOT NULL,
    expires_at timestamp without time zone NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.creditprogramgrantlog OWNER TO uask_user;

--
-- Name: creditprogramgrantlog_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.creditprogramgrantlog_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.creditprogramgrantlog_id_seq OWNER TO uask_user;

--
-- Name: creditprogramgrantlog_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.creditprogramgrantlog_id_seq OWNED BY public.creditprogramgrantlog.id;


--
-- Name: crop; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.crop (
    id integer NOT NULL,
    upload_id integer NOT NULL,
    crop_rect json,
    rotation integer NOT NULL,
    margin_pct integer NOT NULL,
    crop_image_hash character varying NOT NULL,
    cropped_storage_url character varying NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.crop OWNER TO uask_user;

--
-- Name: crop_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.crop_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.crop_id_seq OWNER TO uask_user;

--
-- Name: crop_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.crop_id_seq OWNED BY public.crop.id;


--
-- Name: devicesignuplog; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.devicesignuplog (
    id integer NOT NULL,
    device_hash character varying NOT NULL,
    created_at timestamp without time zone NOT NULL,
    user_id integer
);


ALTER TABLE public.devicesignuplog OWNER TO uask_user;

--
-- Name: devicesignuplog_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.devicesignuplog_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.devicesignuplog_id_seq OWNER TO uask_user;

--
-- Name: devicesignuplog_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.devicesignuplog_id_seq OWNED BY public.devicesignuplog.id;


--
-- Name: followupchatturn; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.followupchatturn (
    id integer NOT NULL,
    solve_session_id integer NOT NULL,
    user_id integer NOT NULL,
    turn_index integer NOT NULL,
    user_message character varying NOT NULL,
    assistant_message character varying NOT NULL,
    refused_out_of_scope boolean NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.followupchatturn OWNER TO uask_user;

--
-- Name: followupchatturn_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.followupchatturn_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.followupchatturn_id_seq OWNER TO uask_user;

--
-- Name: followupchatturn_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.followupchatturn_id_seq OWNED BY public.followupchatturn.id;


--
-- Name: invoice; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.invoice (
    id integer NOT NULL,
    user_id integer NOT NULL,
    subscription_id integer,
    topup_order_id integer,
    stripe_invoice_id character varying,
    stripe_payment_intent_id character varying,
    invoice_number character varying NOT NULL,
    kind public.invoicekind NOT NULL,
    status public.invoicestatus NOT NULL,
    currency character varying NOT NULL,
    period_start timestamp without time zone,
    period_end timestamp without time zone,
    subtotal_amount double precision NOT NULL,
    tax_amount double precision NOT NULL,
    total_amount double precision NOT NULL,
    amount_paid double precision NOT NULL,
    amount_due double precision NOT NULL,
    tax_mode public.taxmode NOT NULL,
    tax_rate double precision,
    billing_address_json json,
    issued_at timestamp without time zone,
    due_at timestamp without time zone,
    paid_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


ALTER TABLE public.invoice OWNER TO uask_user;

--
-- Name: invoice_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.invoice_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.invoice_id_seq OWNER TO uask_user;

--
-- Name: invoice_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.invoice_id_seq OWNED BY public.invoice.id;


--
-- Name: invoicelineitem; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.invoicelineitem (
    id integer NOT NULL,
    invoice_id integer NOT NULL,
    kind public.invoicelineitemkind NOT NULL,
    description character varying NOT NULL,
    quantity double precision NOT NULL,
    unit_price double precision NOT NULL,
    amount double precision NOT NULL,
    currency character varying NOT NULL,
    billing_ledger_id integer,
    payment_id integer,
    metadata_json json,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.invoicelineitem OWNER TO uask_user;

--
-- Name: invoicelineitem_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.invoicelineitem_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.invoicelineitem_id_seq OWNER TO uask_user;

--
-- Name: invoicelineitem_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.invoicelineitem_id_seq OWNED BY public.invoicelineitem.id;


--
-- Name: invoicesequence; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.invoicesequence (
    id integer NOT NULL,
    year integer NOT NULL,
    last_value integer NOT NULL
);


ALTER TABLE public.invoicesequence OWNER TO uask_user;

--
-- Name: invoicesequence_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.invoicesequence_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.invoicesequence_id_seq OWNER TO uask_user;

--
-- Name: invoicesequence_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.invoicesequence_id_seq OWNED BY public.invoicesequence.id;


--
-- Name: json_schemas; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.json_schemas (
    id character varying NOT NULL,
    schema_id character varying NOT NULL,
    content json,
    version integer NOT NULL,
    is_active boolean NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    updated_by character varying
);


ALTER TABLE public.json_schemas OWNER TO uask_user;

--
-- Name: legal_acceptances; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.legal_acceptances (
    id integer NOT NULL,
    user_id integer NOT NULL,
    document_key character varying NOT NULL,
    document_version character varying NOT NULL,
    accepted_at timestamp with time zone DEFAULT now() NOT NULL,
    ip character varying,
    user_agent character varying,
    locale character varying,
    method character varying NOT NULL
);


ALTER TABLE public.legal_acceptances OWNER TO uask_user;

--
-- Name: legal_acceptances_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.legal_acceptances_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.legal_acceptances_id_seq OWNER TO uask_user;

--
-- Name: legal_acceptances_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.legal_acceptances_id_seq OWNED BY public.legal_acceptances.id;


--
-- Name: legal_documents; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.legal_documents (
    id integer NOT NULL,
    key character varying NOT NULL,
    version character varying NOT NULL,
    status character varying NOT NULL,
    content_md text NOT NULL,
    content_html text NOT NULL,
    effective_at timestamp with time zone,
    published_at timestamp with time zone,
    created_by integer,
    updated_by integer,
    checksum_sha256 character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.legal_documents OWNER TO uask_user;

--
-- Name: legal_documents_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.legal_documents_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.legal_documents_id_seq OWNER TO uask_user;

--
-- Name: legal_documents_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.legal_documents_id_seq OWNED BY public.legal_documents.id;


--
-- Name: llmusageledger; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.llmusageledger (
    id integer NOT NULL,
    solve_session_id integer NOT NULL,
    followup_turn_id integer,
    provider character varying NOT NULL,
    model character varying NOT NULL,
    request_id character varying,
    system_prompt_tokens integer NOT NULL,
    input_tokens integer NOT NULL,
    output_tokens integer NOT NULL,
    total_tokens integer NOT NULL,
    latency_ms integer,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.llmusageledger OWNER TO uask_user;

--
-- Name: llmusageledger_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.llmusageledger_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.llmusageledger_id_seq OWNER TO uask_user;

--
-- Name: llmusageledger_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.llmusageledger_id_seq OWNED BY public.llmusageledger.id;


--
-- Name: notifications; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.notifications (
    id integer NOT NULL,
    user_id integer NOT NULL,
    type character varying NOT NULL,
    title character varying NOT NULL,
    body character varying NOT NULL,
    payload_json json,
    severity character varying NOT NULL,
    is_read boolean NOT NULL,
    created_at timestamp without time zone NOT NULL,
    read_at timestamp without time zone,
    action_type character varying,
    action_payload json,
    dedupe_key character varying
);


ALTER TABLE public.notifications OWNER TO uask_user;

--
-- Name: notifications_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.notifications_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.notifications_id_seq OWNER TO uask_user;

--
-- Name: notifications_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.notifications_id_seq OWNED BY public.notifications.id;


--
-- Name: ocrartifact; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.ocrartifact (
    id integer NOT NULL,
    crop_id integer NOT NULL,
    job_id character varying NOT NULL,
    engine_used character varying NOT NULL,
    doc_type character varying,
    page_metadata json,
    instructions json,
    raw_markdown character varying NOT NULL,
    plain_text character varying NOT NULL,
    latex_blocks json,
    confidence_score double precision NOT NULL,
    pix2text_version character varying,
    provider character varying,
    provider_model character varying,
    usage_metadata json,
    blocks json,
    derived_json json,
    coverage_checklist json,
    timings json,
    warnings json,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.ocrartifact OWNER TO uask_user;

--
-- Name: ocrartifact_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.ocrartifact_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ocrartifact_id_seq OWNER TO uask_user;

--
-- Name: ocrartifact_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.ocrartifact_id_seq OWNED BY public.ocrartifact.id;


--
-- Name: ocrauditevent; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.ocrauditevent (
    id integer NOT NULL,
    user_id integer,
    upload_id integer,
    crop_id integer,
    job_id character varying,
    artifact_id integer,
    routing_engine_chosen character varying NOT NULL,
    vlm_type_chosen character varying,
    reasons json,
    confidence_score_before double precision,
    cost_estimate_usd double precision,
    latency_ms integer,
    provider character varying,
    provider_model character varying,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.ocrauditevent OWNER TO uask_user;

--
-- Name: ocrauditevent_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.ocrauditevent_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ocrauditevent_id_seq OWNER TO uask_user;

--
-- Name: ocrauditevent_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.ocrauditevent_id_seq OWNED BY public.ocrauditevent.id;


--
-- Name: ocrcache; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.ocrcache (
    id integer NOT NULL,
    cache_key character varying NOT NULL,
    extracted_text character varying NOT NULL,
    extracted_markdown character varying,
    questions json,
    hit_count integer NOT NULL,
    created_at timestamp without time zone NOT NULL,
    last_hit_at timestamp without time zone NOT NULL
);


ALTER TABLE public.ocrcache OWNER TO uask_user;

--
-- Name: ocrcache_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.ocrcache_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ocrcache_id_seq OWNER TO uask_user;

--
-- Name: ocrcache_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.ocrcache_id_seq OWNED BY public.ocrcache.id;


--
-- Name: ocrchoice; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.ocrchoice (
    id integer NOT NULL,
    question_id integer NOT NULL,
    label character varying NOT NULL,
    text character varying NOT NULL
);


ALTER TABLE public.ocrchoice OWNER TO uask_user;

--
-- Name: ocrchoice_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.ocrchoice_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ocrchoice_id_seq OWNER TO uask_user;

--
-- Name: ocrchoice_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.ocrchoice_id_seq OWNED BY public.ocrchoice.id;


--
-- Name: ocrconfirmation; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.ocrconfirmation (
    id integer NOT NULL,
    artifact_id integer NOT NULL,
    user_id integer NOT NULL,
    confirmed_markdown character varying NOT NULL,
    confirmed_text character varying NOT NULL,
    confirmed_latex_blocks json,
    normalized_problem_hash character varying NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.ocrconfirmation OWNER TO uask_user;

--
-- Name: ocrconfirmation_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.ocrconfirmation_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ocrconfirmation_id_seq OWNER TO uask_user;

--
-- Name: ocrconfirmation_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.ocrconfirmation_id_seq OWNED BY public.ocrconfirmation.id;


--
-- Name: ocrextractioncache; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.ocrextractioncache (
    id integer NOT NULL,
    cache_key character varying NOT NULL,
    user_id integer,
    result_json json,
    meta json,
    hit_count integer NOT NULL,
    created_at timestamp without time zone NOT NULL,
    last_hit_at timestamp without time zone NOT NULL
);


ALTER TABLE public.ocrextractioncache OWNER TO uask_user;

--
-- Name: ocrextractioncache_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.ocrextractioncache_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ocrextractioncache_id_seq OWNER TO uask_user;

--
-- Name: ocrextractioncache_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.ocrextractioncache_id_seq OWNED BY public.ocrextractioncache.id;


--
-- Name: ocrfigure; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.ocrfigure (
    id integer NOT NULL,
    artifact_id integer NOT NULL,
    external_id character varying NOT NULL,
    type character varying NOT NULL,
    description character varying,
    data_json json
);


ALTER TABLE public.ocrfigure OWNER TO uask_user;

--
-- Name: ocrfigure_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.ocrfigure_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ocrfigure_id_seq OWNER TO uask_user;

--
-- Name: ocrfigure_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.ocrfigure_id_seq OWNED BY public.ocrfigure.id;


--
-- Name: ocrjob; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.ocrjob (
    id character varying NOT NULL,
    user_id integer NOT NULL,
    crop_id integer NOT NULL,
    requested_engine character varying NOT NULL,
    status character varying NOT NULL,
    priority character varying NOT NULL,
    attempts integer NOT NULL,
    error_code character varying,
    error_message character varying,
    extracted_text text,
    structured_json json,
    quality_score double precision,
    image_fingerprint character varying,
    dedupe_key character varying,
    prompt_template_id character varying,
    json_schema_id character varying,
    hold_request_id character varying,
    hold_amount numeric(20,10),
    accepted_solve_attempt_id character varying,
    created_at timestamp without time zone NOT NULL,
    started_at timestamp without time zone,
    finished_at timestamp without time zone
);


ALTER TABLE public.ocrjob OWNER TO uask_user;

--
-- Name: ocrquestion; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.ocrquestion (
    id integer NOT NULL,
    artifact_id integer NOT NULL,
    external_id character varying NOT NULL,
    prompt character varying NOT NULL,
    has_figure boolean NOT NULL,
    math_expressions json,
    notes character varying,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.ocrquestion OWNER TO uask_user;

--
-- Name: ocrquestion_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.ocrquestion_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ocrquestion_id_seq OWNER TO uask_user;

--
-- Name: ocrquestion_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.ocrquestion_id_seq OWNED BY public.ocrquestion.id;


--
-- Name: payment; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.payment (
    id integer NOT NULL,
    user_id integer NOT NULL,
    subscription_id integer,
    amount double precision NOT NULL,
    currency character varying NOT NULL,
    status character varying NOT NULL,
    transaction_id character varying NOT NULL,
    payment_method character varying NOT NULL,
    provider character varying NOT NULL,
    external_id character varying,
    external_type character varying,
    idempotency_key character varying,
    metadata_json json,
    ip_address character varying,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.payment OWNER TO uask_user;

--
-- Name: payment_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.payment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.payment_id_seq OWNER TO uask_user;

--
-- Name: payment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.payment_id_seq OWNED BY public.payment.id;


--
-- Name: plan; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.plan (
    id integer NOT NULL,
    name character varying NOT NULL,
    slug character varying NOT NULL,
    credits_per_month integer NOT NULL,
    price_monthly_cents integer NOT NULL,
    price_yearly_cents integer NOT NULL,
    seats integer NOT NULL,
    features json,
    multipliers json,
    is_active boolean NOT NULL,
    version integer NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.plan OWNER TO uask_user;

--
-- Name: plan_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.plan_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.plan_id_seq OWNER TO uask_user;

--
-- Name: plan_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.plan_id_seq OWNED BY public.plan.id;


--
-- Name: promocode; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.promocode (
    id integer NOT NULL,
    code character varying NOT NULL,
    discount_percent integer NOT NULL,
    valid_from timestamp without time zone NOT NULL,
    valid_until timestamp without time zone,
    is_active boolean NOT NULL,
    max_uses integer,
    current_uses integer NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.promocode OWNER TO uask_user;

--
-- Name: promocode_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.promocode_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.promocode_id_seq OWNER TO uask_user;

--
-- Name: promocode_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.promocode_id_seq OWNED BY public.promocode.id;


--
-- Name: prompt_bindings; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.prompt_bindings (
    id character varying NOT NULL,
    tier public.prompttierenum,
    mode public.promptmodeenum,
    global_system_prompt_id character varying NOT NULL,
    developer_prompt_id character varying NOT NULL,
    output_schema_id character varying NOT NULL,
    features json,
    multipliers json,
    max_questions_allowed integer,
    max_output_tokens integer,
    max_input_tokens integer,
    system_schema_budget_tokens integer,
    context_budget_tokens integer,
    json_retry_max_output_tokens integer,
    json_retry_max_attempts integer,
    timeout_ms integer,
    temperature double precision,
    top_p double precision,
    plot_points_cap integer,
    plot_traces_cap integer,
    plot_annotations_cap integer,
    trim_strategy public.trimstrategyenum,
    solve_text_cost numeric(18,10),
    solve_snap_image_cost numeric(18,10),
    solve_snap_pdf_cost numeric(18,10),
    solve_voice_cost numeric(18,10),
    verify_addon_cost numeric(18,10),
    plot_addon_cost numeric(18,10),
    attempt_fee numeric(18,10),
    max_steps integer,
    retry_cap_tokens integer,
    is_active boolean NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    updated_by character varying,
    provider character varying(255) DEFAULT 'openai'::character varying,
    openai_prompt_id character varying,
    openai_prompt_version character varying,
    openai_prompt_use_latest boolean DEFAULT false NOT NULL,
    openai_prompt_variable_mapping json,
    openai_prompt_cache_key_template character varying,
    openai_prompt_cache_retention character varying
);


ALTER TABLE public.prompt_bindings OWNER TO uask_user;

--
-- Name: prompt_templates; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.prompt_templates (
    id character varying NOT NULL,
    prompt_id character varying NOT NULL,
    tier public.prompttierenum,
    mode public.promptmodeenum,
    role public.promptroleenum,
    content text,
    version integer NOT NULL,
    is_active boolean NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    updated_by character varying
);


ALTER TABLE public.prompt_templates OWNER TO uask_user;

--
-- Name: providermodelpricing; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.providermodelpricing (
    id integer NOT NULL,
    provider character varying NOT NULL,
    model character varying NOT NULL,
    price_in_per_1m double precision NOT NULL,
    price_out_per_1m double precision NOT NULL,
    price_cached_in_per_1m double precision,
    currency character varying NOT NULL,
    effective_from timestamp without time zone NOT NULL,
    effective_to timestamp without time zone,
    created_at timestamp without time zone NOT NULL,
    created_by integer,
    status character varying NOT NULL,
    change_reason character varying
);


ALTER TABLE public.providermodelpricing OWNER TO uask_user;

--
-- Name: providermodelpricing_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.providermodelpricing_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.providermodelpricing_id_seq OWNER TO uask_user;

--
-- Name: providermodelpricing_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.providermodelpricing_id_seq OWNED BY public.providermodelpricing.id;


--
-- Name: providerpricingauditevent; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.providerpricingauditevent (
    id integer NOT NULL,
    admin_user_id integer NOT NULL,
    provider_model_pricing_id integer NOT NULL,
    action public.providerpricingaction NOT NULL,
    before_json json,
    after_json json,
    reason character varying NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.providerpricingauditevent OWNER TO uask_user;

--
-- Name: providerpricingauditevent_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.providerpricingauditevent_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.providerpricingauditevent_id_seq OWNER TO uask_user;

--
-- Name: providerpricingauditevent_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.providerpricingauditevent_id_seq OWNED BY public.providerpricingauditevent.id;


--
-- Name: question_identity_cache; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.question_identity_cache (
    id integer NOT NULL,
    question_key character varying NOT NULL,
    normalized_stem character varying NOT NULL,
    normalized_options character varying,
    question_type character varying NOT NULL,
    solution_json json,
    original_variants json,
    hit_count integer NOT NULL,
    created_at timestamp without time zone NOT NULL,
    last_seen_at timestamp without time zone NOT NULL
);


ALTER TABLE public.question_identity_cache OWNER TO uask_user;

--
-- Name: question_identity_cache_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.question_identity_cache_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.question_identity_cache_id_seq OWNER TO uask_user;

--
-- Name: question_identity_cache_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.question_identity_cache_id_seq OWNED BY public.question_identity_cache.id;


--
-- Name: reconciliationfinding; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.reconciliationfinding (
    id integer NOT NULL,
    finding_type character varying NOT NULL,
    severity character varying NOT NULL,
    entity_type character varying NOT NULL,
    entity_id character varying NOT NULL,
    trace_id character varying,
    details_json json,
    status character varying NOT NULL,
    created_at timestamp without time zone NOT NULL,
    resolved_at timestamp without time zone,
    resolved_by integer
);


ALTER TABLE public.reconciliationfinding OWNER TO uask_user;

--
-- Name: reconciliationfinding_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.reconciliationfinding_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.reconciliationfinding_id_seq OWNER TO uask_user;

--
-- Name: reconciliationfinding_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.reconciliationfinding_id_seq OWNED BY public.reconciliationfinding.id;


--
-- Name: reconciliationrecord; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.reconciliationrecord (
    id integer NOT NULL,
    user_id integer NOT NULL,
    cached_balance numeric(20,10) NOT NULL,
    computed_balance numeric(20,10) NOT NULL,
    delta numeric(20,10) NOT NULL,
    auto_fixed boolean NOT NULL,
    job_run_id character varying NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.reconciliationrecord OWNER TO uask_user;

--
-- Name: reconciliationrecord_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.reconciliationrecord_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.reconciliationrecord_id_seq OWNER TO uask_user;

--
-- Name: reconciliationrecord_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.reconciliationrecord_id_seq OWNED BY public.reconciliationrecord.id;


--
-- Name: requestevent; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.requestevent (
    id integer NOT NULL,
    request_id character varying,
    user_id integer,
    created_at timestamp without time zone NOT NULL,
    mode character varying,
    learning_mode character varying,
    subject character varying,
    grade_level character varying,
    model character varying,
    provider character varying,
    route character varying,
    tokens_in integer,
    tokens_out integer,
    tokens_total integer,
    cost_usd double precision,
    latency_ms integer,
    status character varying,
    error_type character varying,
    schema_valid boolean,
    verification_pass boolean,
    is_stream boolean NOT NULL,
    is_cached boolean NOT NULL,
    credit_deducted boolean,
    credit_amount double precision,
    ocr_used boolean NOT NULL,
    voice_used boolean NOT NULL,
    response_truncated boolean NOT NULL
);


ALTER TABLE public.requestevent OWNER TO uask_user;

--
-- Name: requestevent_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.requestevent_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.requestevent_id_seq OWNER TO uask_user;

--
-- Name: requestevent_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.requestevent_id_seq OWNED BY public.requestevent.id;


--
-- Name: school; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.school (
    id integer NOT NULL,
    country character varying NOT NULL,
    province_state character varying NOT NULL,
    district character varying,
    city character varying,
    school_name character varying NOT NULL,
    school_type character varying,
    grade_range character varying,
    external_id character varying,
    source character varying NOT NULL,
    school_key character varying NOT NULL,
    website_url character varying,
    address_line1 character varying,
    full_address character varying,
    street_no character varying,
    street_name character varying,
    postal_code character varying,
    latitude double precision,
    longitude double precision,
    csdname character varying,
    csduid character varying,
    normalized_name character varying,
    normalized_address character varying,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.school OWNER TO uask_user;

--
-- Name: school_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.school_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.school_id_seq OWNER TO uask_user;

--
-- Name: school_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.school_id_seq OWNED BY public.school.id;


--
-- Name: schoolimportrun; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.schoolimportrun (
    id integer NOT NULL,
    started_at timestamp without time zone NOT NULL,
    finished_at timestamp without time zone,
    status character varying NOT NULL,
    us_rows_processed integer NOT NULL,
    ca_rows_processed integer NOT NULL,
    inserted_count integer NOT NULL,
    updated_count integer NOT NULL,
    skipped_count integer NOT NULL,
    error_count integer NOT NULL,
    errors_json json,
    reset_before_import boolean NOT NULL
);


ALTER TABLE public.schoolimportrun OWNER TO uask_user;

--
-- Name: schoolimportrun_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.schoolimportrun_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.schoolimportrun_id_seq OWNER TO uask_user;

--
-- Name: schoolimportrun_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.schoolimportrun_id_seq OWNED BY public.schoolimportrun.id;


--
-- Name: seed_registry; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.seed_registry (
    id integer NOT NULL,
    seed_name character varying NOT NULL,
    seed_version integer NOT NULL,
    applied_at timestamp with time zone DEFAULT now() NOT NULL,
    git_sha character varying,
    environment character varying NOT NULL,
    row_count integer,
    checksum character varying,
    notes character varying
);


ALTER TABLE public.seed_registry OWNER TO uask_user;

--
-- Name: seed_registry_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.seed_registry_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.seed_registry_id_seq OWNER TO uask_user;

--
-- Name: seed_registry_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.seed_registry_id_seq OWNED BY public.seed_registry.id;


--
-- Name: solution_shares; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.solution_shares (
    id character varying NOT NULL,
    solver_output_attempt_id integer NOT NULL,
    attempt_id character varying NOT NULL,
    owner_user_id integer NOT NULL,
    visibility character varying NOT NULL,
    share_token character varying,
    share_token_hash character varying,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    revoked_at timestamp without time zone,
    last_viewed_at timestamp without time zone,
    view_count integer NOT NULL,
    expires_at timestamp without time zone,
    metadata_json json
);


ALTER TABLE public.solution_shares OWNER TO uask_user;

--
-- Name: solve_debug_blob; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.solve_debug_blob (
    id character varying NOT NULL,
    attempt_id character varying NOT NULL,
    blob_type character varying NOT NULL,
    content_json json,
    content_text text,
    sha256 character varying,
    size_bytes bigint,
    stored_reason character varying DEFAULT 'debug'::character varying NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    retention_until timestamp without time zone
);


ALTER TABLE public.solve_debug_blob OWNER TO uask_user;

--
-- Name: solvedebugblob; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.solvedebugblob (
    id character varying NOT NULL,
    attempt_id character varying NOT NULL,
    blob_type character varying NOT NULL,
    content_json json,
    content_text text,
    sha256 character varying,
    size_bytes bigint,
    stored_reason character varying NOT NULL,
    created_at timestamp without time zone NOT NULL,
    retention_until timestamp without time zone,
    validation_json json,
    validation_errors json,
    clarification_count integer NOT NULL,
    clarification_history json,
    input_tokens integer NOT NULL,
    output_tokens integer NOT NULL,
    total_tokens integer NOT NULL,
    llm_responses json,
    validation_events json,
    latency_ms integer,
    time_to_first_token_ms integer,
    provider_model character varying,
    archive_path character varying,
    status character varying NOT NULL,
    failure_code character varying,
    error_message text,
    updated_at timestamp without time zone NOT NULL
);


ALTER TABLE public.solvedebugblob OWNER TO uask_user;

--
-- Name: solveroutputattempt; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.solveroutputattempt (
    id integer NOT NULL,
    request_id character varying NOT NULL,
    attempt_id character varying NOT NULL,
    user_id integer,
    session_id integer,
    message_id integer,
    output_format character varying NOT NULL,
    prompt_id character varying,
    prompt_version character varying,
    prompt_meta json,
    attempt_number integer NOT NULL,
    provider character varying,
    model character varying,
    input_text_raw text,
    input_text_normalized text,
    latency_ms integer,
    char_count integer NOT NULL,
    extracted_answer text,
    raw_solution_text text,
    llm_raw_response json,
    validation_json json,
    validation_errors json,
    clarification_count integer NOT NULL,
    clarification_history json,
    input_tokens integer NOT NULL,
    output_tokens integer NOT NULL,
    total_tokens integer NOT NULL,
    llm_responses json,
    validation_events json,
    time_to_first_token_ms integer,
    provider_model character varying,
    archive_path character varying,
    status character varying NOT NULL,
    failure_code character varying,
    error_message text,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    billing_breakdown_json json,
    solve_mode character varying,
    charged_total_credits numeric(20,10),
    selected_task_ids_json json,
    started_at timestamp without time zone,
    finished_at timestamp without time zone,
    cancel_requested_at timestamp without time zone,
    ttl_deadline_at timestamp without time zone,
    result_json json,
    error_json json,
    provider_meta json
);


ALTER TABLE public.solveroutputattempt OWNER TO uask_user;

--
-- Name: solveroutputattempt_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.solveroutputattempt_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.solveroutputattempt_id_seq OWNER TO uask_user;

--
-- Name: solveroutputattempt_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.solveroutputattempt_id_seq OWNED BY public.solveroutputattempt.id;


--
-- Name: solvesession; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.solvesession (
    id integer NOT NULL,
    user_id integer NOT NULL,
    problem_text character varying NOT NULL,
    topic character varying NOT NULL,
    solution_steps_text character varying NOT NULL,
    final_answer_text character varying NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.solvesession OWNER TO uask_user;

--
-- Name: solvesession_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.solvesession_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.solvesession_id_seq OWNER TO uask_user;

--
-- Name: solvesession_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.solvesession_id_seq OWNED BY public.solvesession.id;


--
-- Name: stripeevent; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.stripeevent (
    id integer NOT NULL,
    stripe_event_id character varying NOT NULL,
    type character varying NOT NULL,
    api_version character varying,
    created_ts integer NOT NULL,
    livemode boolean NOT NULL,
    payload_json json,
    received_at timestamp without time zone NOT NULL,
    processed_at timestamp without time zone,
    process_status character varying NOT NULL,
    last_error text
);


ALTER TABLE public.stripeevent OWNER TO uask_user;

--
-- Name: stripeevent_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.stripeevent_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.stripeevent_id_seq OWNER TO uask_user;

--
-- Name: stripeevent_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.stripeevent_id_seq OWNED BY public.stripeevent.id;


--
-- Name: stripepricemap; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.stripepricemap (
    id integer NOT NULL,
    kind character varying NOT NULL,
    internal_code character varying NOT NULL,
    stripe_price_id character varying NOT NULL,
    currency character varying NOT NULL,
    active boolean NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.stripepricemap OWNER TO uask_user;

--
-- Name: stripepricemap_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.stripepricemap_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.stripepricemap_id_seq OWNER TO uask_user;

--
-- Name: stripepricemap_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.stripepricemap_id_seq OWNED BY public.stripepricemap.id;


--
-- Name: subscription; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.subscription (
    id integer NOT NULL,
    user_id integer NOT NULL,
    plan_id integer NOT NULL,
    status character varying NOT NULL,
    current_period_start timestamp without time zone NOT NULL,
    current_period_end timestamp without time zone NOT NULL,
    credits_balance numeric(20,10),
    credits_used_this_period numeric(20,10),
    feature_usage json,
    auto_renew boolean NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


ALTER TABLE public.subscription OWNER TO uask_user;

--
-- Name: subscription_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.subscription_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.subscription_id_seq OWNER TO uask_user;

--
-- Name: subscription_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.subscription_id_seq OWNED BY public.subscription.id;


--
-- Name: subscriptionbillinglink; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.subscriptionbillinglink (
    id integer NOT NULL,
    subscription_id integer NOT NULL,
    user_id integer NOT NULL,
    stripe_customer_id character varying NOT NULL,
    stripe_subscription_id character varying NOT NULL,
    stripe_price_id character varying NOT NULL,
    status character varying NOT NULL,
    current_period_start timestamp without time zone NOT NULL,
    current_period_end timestamp without time zone NOT NULL,
    cancel_at_period_end boolean NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


ALTER TABLE public.subscriptionbillinglink OWNER TO uask_user;

--
-- Name: subscriptionbillinglink_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.subscriptionbillinglink_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.subscriptionbillinglink_id_seq OWNER TO uask_user;

--
-- Name: subscriptionbillinglink_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.subscriptionbillinglink_id_seq OWNED BY public.subscriptionbillinglink.id;


--
-- Name: subscriptionperiod; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.subscriptionperiod (
    id integer NOT NULL,
    subscription_id integer NOT NULL,
    period_start timestamp without time zone NOT NULL,
    period_end timestamp without time zone NOT NULL,
    status character varying NOT NULL,
    granted_credits integer NOT NULL,
    grant_lot_id integer,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.subscriptionperiod OWNER TO uask_user;

--
-- Name: subscriptionperiod_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.subscriptionperiod_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.subscriptionperiod_id_seq OWNER TO uask_user;

--
-- Name: subscriptionperiod_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.subscriptionperiod_id_seq OWNED BY public.subscriptionperiod.id;


--
-- Name: systemconfig; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.systemconfig (
    key character varying NOT NULL,
    value character varying NOT NULL,
    description character varying,
    updated_at timestamp without time zone NOT NULL
);


ALTER TABLE public.systemconfig OWNER TO uask_user;

--
-- Name: systemconfigversion; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.systemconfigversion (
    id integer NOT NULL,
    config_type character varying NOT NULL,
    version integer NOT NULL,
    value json,
    diff_json json,
    check_sum character varying NOT NULL,
    created_by integer NOT NULL,
    change_msg character varying NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.systemconfigversion OWNER TO uask_user;

--
-- Name: systemconfigversion_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.systemconfigversion_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.systemconfigversion_id_seq OWNER TO uask_user;

--
-- Name: systemconfigversion_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.systemconfigversion_id_seq OWNED BY public.systemconfigversion.id;


--
-- Name: systemerrorentry; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.systemerrorentry (
    id integer NOT NULL,
    severity character varying NOT NULL,
    error_code character varying,
    component character varying NOT NULL,
    message character varying NOT NULL,
    stack_trace character varying,
    trace_id character varying,
    request_id character varying,
    user_id integer,
    fingerprint character varying,
    occurrence_count integer NOT NULL,
    context_json json,
    is_resolved boolean NOT NULL,
    created_at timestamp without time zone NOT NULL,
    last_seen_at timestamp without time zone NOT NULL
);


ALTER TABLE public.systemerrorentry OWNER TO uask_user;

--
-- Name: systemerrorentry_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.systemerrorentry_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.systemerrorentry_id_seq OWNER TO uask_user;

--
-- Name: systemerrorentry_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.systemerrorentry_id_seq OWNED BY public.systemerrorentry.id;


--
-- Name: topuporder; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.topuporder (
    id integer NOT NULL,
    user_id integer NOT NULL,
    topup_product_id integer NOT NULL,
    credits double precision NOT NULL,
    price_usd double precision NOT NULL,
    currency character varying NOT NULL,
    status character varying NOT NULL,
    stripe_checkout_session_id character varying,
    stripe_payment_intent_id character varying,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    fulfill_usage_ledger_id integer,
    fulfill_credit_lot_id integer
);


ALTER TABLE public.topuporder OWNER TO uask_user;

--
-- Name: topuporder_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.topuporder_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.topuporder_id_seq OWNER TO uask_user;

--
-- Name: topuporder_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.topuporder_id_seq OWNED BY public.topuporder.id;


--
-- Name: topupproduct; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.topupproduct (
    id integer NOT NULL,
    code character varying NOT NULL,
    name character varying NOT NULL,
    credits integer NOT NULL,
    price_usd double precision NOT NULL,
    is_active boolean NOT NULL,
    metadata_json json
);


ALTER TABLE public.topupproduct OWNER TO uask_user;

--
-- Name: topupproduct_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.topupproduct_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.topupproduct_id_seq OWNER TO uask_user;

--
-- Name: topupproduct_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.topupproduct_id_seq OWNED BY public.topupproduct.id;


--
-- Name: upload; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.upload (
    id integer NOT NULL,
    user_id integer NOT NULL,
    storage_url character varying NOT NULL,
    file_hash character varying NOT NULL,
    content_type character varying NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.upload OWNER TO uask_user;

--
-- Name: upload_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.upload_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.upload_id_seq OWNER TO uask_user;

--
-- Name: upload_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.upload_id_seq OWNED BY public.upload.id;


--
-- Name: usage_ledger; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.usage_ledger (
    ledger_id character varying NOT NULL,
    user_id integer NOT NULL,
    hold_id character varying,
    request_id character varying NOT NULL,
    attempt_id character varying,
    idempotency_key character varying NOT NULL,
    tier character varying NOT NULL,
    action character varying NOT NULL,
    question_id character varying,
    question_index integer,
    base_cost numeric(20,10) NOT NULL,
    addons_cost numeric(20,10) NOT NULL,
    attempt_fee numeric(20,10) NOT NULL,
    total_cost numeric(20,10) NOT NULL,
    pricing_snapshot json NOT NULL,
    outcome character varying NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.usage_ledger OWNER TO uask_user;

--
-- Name: usageledger; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.usageledger (
    id integer NOT NULL,
    subscription_id integer NOT NULL,
    transaction_type character varying NOT NULL,
    amount numeric(20,10) NOT NULL,
    balance_after numeric(20,10) NOT NULL,
    reference_id character varying,
    meta json,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.usageledger OWNER TO uask_user;

--
-- Name: usageledger_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.usageledger_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.usageledger_id_seq OWNER TO uask_user;

--
-- Name: usageledger_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.usageledger_id_seq OWNED BY public.usageledger.id;


--
-- Name: usagelog; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.usagelog (
    id integer NOT NULL,
    user_id integer NOT NULL,
    action_type character varying NOT NULL,
    tokens_used integer NOT NULL,
    "timestamp" timestamp without time zone NOT NULL
);


ALTER TABLE public.usagelog OWNER TO uask_user;

--
-- Name: usagelog_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.usagelog_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.usagelog_id_seq OWNER TO uask_user;

--
-- Name: usagelog_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.usagelog_id_seq OWNED BY public.usagelog.id;


--
-- Name: user; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public."user" (
    id integer NOT NULL,
    email character varying NOT NULL,
    full_name character varying NOT NULL,
    password_hash character varying NOT NULL,
    created_at timestamp without time zone NOT NULL,
    role character varying NOT NULL,
    is_internal boolean NOT NULL,
    academic_level character varying,
    preferred_language character varying NOT NULL,
    timezone character varying NOT NULL,
    theme character varying NOT NULL,
    solving_mode character varying NOT NULL,
    subscription_tier character varying NOT NULL,
    subscription_status character varying NOT NULL,
    subscription_expiry timestamp without time zone,
    quota_questions_total integer NOT NULL,
    credits_balance numeric(20,10),
    quota_scans_total integer NOT NULL,
    tokens_used_this_month integer NOT NULL,
    last_token_reset timestamp without time zone NOT NULL,
    avatar_url character varying,
    bio character varying,
    is_verified boolean NOT NULL,
    verification_token character varying,
    ip_address character varying,
    country character varying,
    profile_country character varying,
    profile_province_state character varying,
    grade_level character varying,
    school_id integer,
    is_public boolean NOT NULL,
    learning_interests json,
    last_active_at timestamp without time zone NOT NULL,
    session_token character varying,
    last_ip character varying,
    whatsapp_number character varying,
    whatsapp_secret character varying,
    whatsapp_enabled boolean NOT NULL
);


ALTER TABLE public."user" OWNER TO uask_user;

--
-- Name: user_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_id_seq OWNER TO uask_user;

--
-- Name: user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.user_id_seq OWNED BY public."user".id;


--
-- Name: userquotaoverride; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.userquotaoverride (
    id integer NOT NULL,
    user_id integer NOT NULL,
    token_limit integer,
    ocr_concurrency integer,
    expires_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.userquotaoverride OWNER TO uask_user;

--
-- Name: userquotaoverride_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.userquotaoverride_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.userquotaoverride_id_seq OWNER TO uask_user;

--
-- Name: userquotaoverride_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.userquotaoverride_id_seq OWNED BY public.userquotaoverride.id;


--
-- Name: usersavedsolution; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.usersavedsolution (
    user_id integer NOT NULL,
    solution_id integer NOT NULL,
    saved_at timestamp without time zone NOT NULL,
    tags json,
    notes character varying
);


ALTER TABLE public.usersavedsolution OWNER TO uask_user;

--
-- Name: voiceartifact; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.voiceartifact (
    id integer NOT NULL,
    job_id integer NOT NULL,
    transcript_raw character varying NOT NULL,
    transcript_confidence double precision,
    normalized_math_text character varying NOT NULL,
    ambiguity_flags json,
    clarifier_question json,
    stt_provider character varying NOT NULL,
    stt_model character varying NOT NULL,
    timings_json json,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.voiceartifact OWNER TO uask_user;

--
-- Name: voiceartifact_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.voiceartifact_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.voiceartifact_id_seq OWNER TO uask_user;

--
-- Name: voiceartifact_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.voiceartifact_id_seq OWNED BY public.voiceartifact.id;


--
-- Name: voiceaudio; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.voiceaudio (
    id integer NOT NULL,
    voice_session_id integer NOT NULL,
    storage_url character varying NOT NULL,
    audio_hash character varying NOT NULL,
    duration_ms integer,
    codec character varying,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.voiceaudio OWNER TO uask_user;

--
-- Name: voiceaudio_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.voiceaudio_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.voiceaudio_id_seq OWNER TO uask_user;

--
-- Name: voiceaudio_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.voiceaudio_id_seq OWNED BY public.voiceaudio.id;


--
-- Name: voiceconfirmation; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.voiceconfirmation (
    id integer NOT NULL,
    artifact_id integer NOT NULL,
    user_id integer NOT NULL,
    confirmed_transcript_text character varying NOT NULL,
    confirmed_normalized_text character varying NOT NULL,
    problem_json json,
    normalized_problem_hash character varying NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.voiceconfirmation OWNER TO uask_user;

--
-- Name: voiceconfirmation_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.voiceconfirmation_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.voiceconfirmation_id_seq OWNER TO uask_user;

--
-- Name: voiceconfirmation_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.voiceconfirmation_id_seq OWNED BY public.voiceconfirmation.id;


--
-- Name: voicejob; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.voicejob (
    id integer NOT NULL,
    voice_session_id integer NOT NULL,
    audio_id integer NOT NULL,
    status character varying NOT NULL,
    attempts integer NOT NULL,
    created_at timestamp without time zone NOT NULL,
    started_at timestamp without time zone,
    finished_at timestamp without time zone,
    error_code character varying,
    error_message character varying
);


ALTER TABLE public.voicejob OWNER TO uask_user;

--
-- Name: voicejob_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.voicejob_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.voicejob_id_seq OWNER TO uask_user;

--
-- Name: voicejob_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.voicejob_id_seq OWNED BY public.voicejob.id;


--
-- Name: voicesession; Type: TABLE; Schema: public; Owner: uask_user
--

CREATE TABLE public.voicesession (
    id integer NOT NULL,
    user_id integer NOT NULL,
    language character varying NOT NULL,
    preferred_stt character varying NOT NULL,
    status character varying NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.voicesession OWNER TO uask_user;

--
-- Name: voicesession_id_seq; Type: SEQUENCE; Schema: public; Owner: uask_user
--

CREATE SEQUENCE public.voicesession_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.voicesession_id_seq OWNER TO uask_user;

--
-- Name: voicesession_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: uask_user
--

ALTER SEQUENCE public.voicesession_id_seq OWNED BY public.voicesession.id;


--
-- Name: adminauditlog id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.adminauditlog ALTER COLUMN id SET DEFAULT nextval('public.adminauditlog_id_seq'::regclass);


--
-- Name: adminnote id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.adminnote ALTER COLUMN id SET DEFAULT nextval('public.adminnote_id_seq'::regclass);


--
-- Name: attemptevent id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.attemptevent ALTER COLUMN id SET DEFAULT nextval('public.attemptevent_id_seq'::regclass);


--
-- Name: billingledger id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.billingledger ALTER COLUMN id SET DEFAULT nextval('public.billingledger_id_seq'::regclass);


--
-- Name: canonicalproblem id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.canonicalproblem ALTER COLUMN id SET DEFAULT nextval('public.canonicalproblem_id_seq'::regclass);


--
-- Name: canonicalsolution id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.canonicalsolution ALTER COLUMN id SET DEFAULT nextval('public.canonicalsolution_id_seq'::regclass);


--
-- Name: chateditcopy id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.chateditcopy ALTER COLUMN id SET DEFAULT nextval('public.chateditcopy_id_seq'::regclass);


--
-- Name: chateditcopyv2 id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.chateditcopyv2 ALTER COLUMN id SET DEFAULT nextval('public.chateditcopyv2_id_seq'::regclass);


--
-- Name: chateditnotev2 id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.chateditnotev2 ALTER COLUMN id SET DEFAULT nextval('public.chateditnotev2_id_seq'::regclass);


--
-- Name: chatmessage id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.chatmessage ALTER COLUMN id SET DEFAULT nextval('public.chatmessage_id_seq'::regclass);


--
-- Name: chatnote id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.chatnote ALTER COLUMN id SET DEFAULT nextval('public.chatnote_id_seq'::regclass);


--
-- Name: chatsession id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.chatsession ALTER COLUMN id SET DEFAULT nextval('public.chatsession_id_seq'::regclass);


--
-- Name: credit_packs id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.credit_packs ALTER COLUMN id SET DEFAULT nextval('public.credit_packs_id_seq'::regclass);


--
-- Name: credithold id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.credithold ALTER COLUMN id SET DEFAULT nextval('public.credithold_id_seq'::regclass);


--
-- Name: creditlot id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.creditlot ALTER COLUMN id SET DEFAULT nextval('public.creditlot_id_seq'::regclass);


--
-- Name: creditlotconsumption id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.creditlotconsumption ALTER COLUMN id SET DEFAULT nextval('public.creditlotconsumption_id_seq'::regclass);


--
-- Name: creditprogramdefinition id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.creditprogramdefinition ALTER COLUMN id SET DEFAULT nextval('public.creditprogramdefinition_id_seq'::regclass);


--
-- Name: creditprogramenrollment id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.creditprogramenrollment ALTER COLUMN id SET DEFAULT nextval('public.creditprogramenrollment_id_seq'::regclass);


--
-- Name: creditprogramgrantlog id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.creditprogramgrantlog ALTER COLUMN id SET DEFAULT nextval('public.creditprogramgrantlog_id_seq'::regclass);


--
-- Name: crop id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.crop ALTER COLUMN id SET DEFAULT nextval('public.crop_id_seq'::regclass);


--
-- Name: devicesignuplog id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.devicesignuplog ALTER COLUMN id SET DEFAULT nextval('public.devicesignuplog_id_seq'::regclass);


--
-- Name: followupchatturn id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.followupchatturn ALTER COLUMN id SET DEFAULT nextval('public.followupchatturn_id_seq'::regclass);


--
-- Name: invoice id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.invoice ALTER COLUMN id SET DEFAULT nextval('public.invoice_id_seq'::regclass);


--
-- Name: invoicelineitem id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.invoicelineitem ALTER COLUMN id SET DEFAULT nextval('public.invoicelineitem_id_seq'::regclass);


--
-- Name: invoicesequence id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.invoicesequence ALTER COLUMN id SET DEFAULT nextval('public.invoicesequence_id_seq'::regclass);


--
-- Name: legal_acceptances id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.legal_acceptances ALTER COLUMN id SET DEFAULT nextval('public.legal_acceptances_id_seq'::regclass);


--
-- Name: legal_documents id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.legal_documents ALTER COLUMN id SET DEFAULT nextval('public.legal_documents_id_seq'::regclass);


--
-- Name: llmusageledger id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.llmusageledger ALTER COLUMN id SET DEFAULT nextval('public.llmusageledger_id_seq'::regclass);


--
-- Name: notifications id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.notifications ALTER COLUMN id SET DEFAULT nextval('public.notifications_id_seq'::regclass);


--
-- Name: ocrartifact id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.ocrartifact ALTER COLUMN id SET DEFAULT nextval('public.ocrartifact_id_seq'::regclass);


--
-- Name: ocrauditevent id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.ocrauditevent ALTER COLUMN id SET DEFAULT nextval('public.ocrauditevent_id_seq'::regclass);


--
-- Name: ocrcache id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.ocrcache ALTER COLUMN id SET DEFAULT nextval('public.ocrcache_id_seq'::regclass);


--
-- Name: ocrchoice id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.ocrchoice ALTER COLUMN id SET DEFAULT nextval('public.ocrchoice_id_seq'::regclass);


--
-- Name: ocrconfirmation id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.ocrconfirmation ALTER COLUMN id SET DEFAULT nextval('public.ocrconfirmation_id_seq'::regclass);


--
-- Name: ocrextractioncache id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.ocrextractioncache ALTER COLUMN id SET DEFAULT nextval('public.ocrextractioncache_id_seq'::regclass);


--
-- Name: ocrfigure id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.ocrfigure ALTER COLUMN id SET DEFAULT nextval('public.ocrfigure_id_seq'::regclass);


--
-- Name: ocrquestion id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.ocrquestion ALTER COLUMN id SET DEFAULT nextval('public.ocrquestion_id_seq'::regclass);


--
-- Name: payment id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.payment ALTER COLUMN id SET DEFAULT nextval('public.payment_id_seq'::regclass);


--
-- Name: plan id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.plan ALTER COLUMN id SET DEFAULT nextval('public.plan_id_seq'::regclass);


--
-- Name: promocode id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.promocode ALTER COLUMN id SET DEFAULT nextval('public.promocode_id_seq'::regclass);


--
-- Name: providermodelpricing id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.providermodelpricing ALTER COLUMN id SET DEFAULT nextval('public.providermodelpricing_id_seq'::regclass);


--
-- Name: providerpricingauditevent id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.providerpricingauditevent ALTER COLUMN id SET DEFAULT nextval('public.providerpricingauditevent_id_seq'::regclass);


--
-- Name: question_identity_cache id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.question_identity_cache ALTER COLUMN id SET DEFAULT nextval('public.question_identity_cache_id_seq'::regclass);


--
-- Name: reconciliationfinding id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.reconciliationfinding ALTER COLUMN id SET DEFAULT nextval('public.reconciliationfinding_id_seq'::regclass);


--
-- Name: reconciliationrecord id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.reconciliationrecord ALTER COLUMN id SET DEFAULT nextval('public.reconciliationrecord_id_seq'::regclass);


--
-- Name: requestevent id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.requestevent ALTER COLUMN id SET DEFAULT nextval('public.requestevent_id_seq'::regclass);


--
-- Name: school id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.school ALTER COLUMN id SET DEFAULT nextval('public.school_id_seq'::regclass);


--
-- Name: schoolimportrun id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.schoolimportrun ALTER COLUMN id SET DEFAULT nextval('public.schoolimportrun_id_seq'::regclass);


--
-- Name: seed_registry id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.seed_registry ALTER COLUMN id SET DEFAULT nextval('public.seed_registry_id_seq'::regclass);


--
-- Name: solveroutputattempt id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.solveroutputattempt ALTER COLUMN id SET DEFAULT nextval('public.solveroutputattempt_id_seq'::regclass);


--
-- Name: solvesession id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.solvesession ALTER COLUMN id SET DEFAULT nextval('public.solvesession_id_seq'::regclass);


--
-- Name: stripeevent id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.stripeevent ALTER COLUMN id SET DEFAULT nextval('public.stripeevent_id_seq'::regclass);


--
-- Name: stripepricemap id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.stripepricemap ALTER COLUMN id SET DEFAULT nextval('public.stripepricemap_id_seq'::regclass);


--
-- Name: subscription id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.subscription ALTER COLUMN id SET DEFAULT nextval('public.subscription_id_seq'::regclass);


--
-- Name: subscriptionbillinglink id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.subscriptionbillinglink ALTER COLUMN id SET DEFAULT nextval('public.subscriptionbillinglink_id_seq'::regclass);


--
-- Name: subscriptionperiod id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.subscriptionperiod ALTER COLUMN id SET DEFAULT nextval('public.subscriptionperiod_id_seq'::regclass);


--
-- Name: systemconfigversion id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.systemconfigversion ALTER COLUMN id SET DEFAULT nextval('public.systemconfigversion_id_seq'::regclass);


--
-- Name: systemerrorentry id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.systemerrorentry ALTER COLUMN id SET DEFAULT nextval('public.systemerrorentry_id_seq'::regclass);


--
-- Name: topuporder id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.topuporder ALTER COLUMN id SET DEFAULT nextval('public.topuporder_id_seq'::regclass);


--
-- Name: topupproduct id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.topupproduct ALTER COLUMN id SET DEFAULT nextval('public.topupproduct_id_seq'::regclass);


--
-- Name: upload id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.upload ALTER COLUMN id SET DEFAULT nextval('public.upload_id_seq'::regclass);


--
-- Name: usageledger id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.usageledger ALTER COLUMN id SET DEFAULT nextval('public.usageledger_id_seq'::regclass);


--
-- Name: usagelog id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.usagelog ALTER COLUMN id SET DEFAULT nextval('public.usagelog_id_seq'::regclass);


--
-- Name: user id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public."user" ALTER COLUMN id SET DEFAULT nextval('public.user_id_seq'::regclass);


--
-- Name: userquotaoverride id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.userquotaoverride ALTER COLUMN id SET DEFAULT nextval('public.userquotaoverride_id_seq'::regclass);


--
-- Name: voiceartifact id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.voiceartifact ALTER COLUMN id SET DEFAULT nextval('public.voiceartifact_id_seq'::regclass);


--
-- Name: voiceaudio id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.voiceaudio ALTER COLUMN id SET DEFAULT nextval('public.voiceaudio_id_seq'::regclass);


--
-- Name: voiceconfirmation id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.voiceconfirmation ALTER COLUMN id SET DEFAULT nextval('public.voiceconfirmation_id_seq'::regclass);


--
-- Name: voicejob id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.voicejob ALTER COLUMN id SET DEFAULT nextval('public.voicejob_id_seq'::regclass);


--
-- Name: voicesession id; Type: DEFAULT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.voicesession ALTER COLUMN id SET DEFAULT nextval('public.voicesession_id_seq'::regclass);


--
-- Name: adminauditlog adminauditlog_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.adminauditlog
    ADD CONSTRAINT adminauditlog_pkey PRIMARY KEY (id);


--
-- Name: adminnote adminnote_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.adminnote
    ADD CONSTRAINT adminnote_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: attemptevent attemptevent_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.attemptevent
    ADD CONSTRAINT attemptevent_pkey PRIMARY KEY (id);


--
-- Name: billingledger billingledger_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.billingledger
    ADD CONSTRAINT billingledger_pkey PRIMARY KEY (id);


--
-- Name: canonicalproblem canonicalproblem_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.canonicalproblem
    ADD CONSTRAINT canonicalproblem_pkey PRIMARY KEY (id);


--
-- Name: canonicalsolution canonicalsolution_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.canonicalsolution
    ADD CONSTRAINT canonicalsolution_pkey PRIMARY KEY (id);


--
-- Name: chateditcopy chateditcopy_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.chateditcopy
    ADD CONSTRAINT chateditcopy_pkey PRIMARY KEY (id);


--
-- Name: chateditcopyv2 chateditcopyv2_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.chateditcopyv2
    ADD CONSTRAINT chateditcopyv2_pkey PRIMARY KEY (id);


--
-- Name: chateditnotev2 chateditnotev2_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.chateditnotev2
    ADD CONSTRAINT chateditnotev2_pkey PRIMARY KEY (id);


--
-- Name: chatmessage chatmessage_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.chatmessage
    ADD CONSTRAINT chatmessage_pkey PRIMARY KEY (id);


--
-- Name: chatnote chatnote_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.chatnote
    ADD CONSTRAINT chatnote_pkey PRIMARY KEY (id);


--
-- Name: chatsession chatsession_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.chatsession
    ADD CONSTRAINT chatsession_pkey PRIMARY KEY (id);


--
-- Name: credit_hold_allocations credit_hold_allocations_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.credit_hold_allocations
    ADD CONSTRAINT credit_hold_allocations_pkey PRIMARY KEY (hold_id, lot_id);


--
-- Name: credit_holds credit_holds_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.credit_holds
    ADD CONSTRAINT credit_holds_pkey PRIMARY KEY (hold_id);


--
-- Name: credit_lots credit_lots_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.credit_lots
    ADD CONSTRAINT credit_lots_pkey PRIMARY KEY (lot_id);


--
-- Name: credit_packs credit_packs_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.credit_packs
    ADD CONSTRAINT credit_packs_pkey PRIMARY KEY (id);


--
-- Name: credit_transfers credit_transfers_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.credit_transfers
    ADD CONSTRAINT credit_transfers_pkey PRIMARY KEY (id);


--
-- Name: credithold credithold_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.credithold
    ADD CONSTRAINT credithold_pkey PRIMARY KEY (id);


--
-- Name: creditlot creditlot_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.creditlot
    ADD CONSTRAINT creditlot_pkey PRIMARY KEY (id);


--
-- Name: creditlotconsumption creditlotconsumption_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.creditlotconsumption
    ADD CONSTRAINT creditlotconsumption_pkey PRIMARY KEY (id);


--
-- Name: creditprogramdefinition creditprogramdefinition_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.creditprogramdefinition
    ADD CONSTRAINT creditprogramdefinition_pkey PRIMARY KEY (id);


--
-- Name: creditprogramenrollment creditprogramenrollment_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.creditprogramenrollment
    ADD CONSTRAINT creditprogramenrollment_pkey PRIMARY KEY (id);


--
-- Name: creditprogramgrantlog creditprogramgrantlog_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.creditprogramgrantlog
    ADD CONSTRAINT creditprogramgrantlog_pkey PRIMARY KEY (id);


--
-- Name: crop crop_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.crop
    ADD CONSTRAINT crop_pkey PRIMARY KEY (id);


--
-- Name: devicesignuplog devicesignuplog_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.devicesignuplog
    ADD CONSTRAINT devicesignuplog_pkey PRIMARY KEY (id);


--
-- Name: followupchatturn followupchatturn_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.followupchatturn
    ADD CONSTRAINT followupchatturn_pkey PRIMARY KEY (id);


--
-- Name: invoice invoice_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.invoice
    ADD CONSTRAINT invoice_pkey PRIMARY KEY (id);


--
-- Name: invoicelineitem invoicelineitem_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.invoicelineitem
    ADD CONSTRAINT invoicelineitem_pkey PRIMARY KEY (id);


--
-- Name: invoicesequence invoicesequence_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.invoicesequence
    ADD CONSTRAINT invoicesequence_pkey PRIMARY KEY (id);


--
-- Name: json_schemas json_schemas_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.json_schemas
    ADD CONSTRAINT json_schemas_pkey PRIMARY KEY (id);


--
-- Name: json_schemas json_schemas_schema_id_version_key; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.json_schemas
    ADD CONSTRAINT json_schemas_schema_id_version_key UNIQUE (schema_id, version);


--
-- Name: legal_acceptances legal_acceptances_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.legal_acceptances
    ADD CONSTRAINT legal_acceptances_pkey PRIMARY KEY (id);


--
-- Name: legal_documents legal_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.legal_documents
    ADD CONSTRAINT legal_documents_pkey PRIMARY KEY (id);


--
-- Name: llmusageledger llmusageledger_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.llmusageledger
    ADD CONSTRAINT llmusageledger_pkey PRIMARY KEY (id);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);


--
-- Name: ocrartifact ocrartifact_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.ocrartifact
    ADD CONSTRAINT ocrartifact_pkey PRIMARY KEY (id);


--
-- Name: ocrauditevent ocrauditevent_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.ocrauditevent
    ADD CONSTRAINT ocrauditevent_pkey PRIMARY KEY (id);


--
-- Name: ocrcache ocrcache_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.ocrcache
    ADD CONSTRAINT ocrcache_pkey PRIMARY KEY (id);


--
-- Name: ocrchoice ocrchoice_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.ocrchoice
    ADD CONSTRAINT ocrchoice_pkey PRIMARY KEY (id);


--
-- Name: ocrconfirmation ocrconfirmation_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.ocrconfirmation
    ADD CONSTRAINT ocrconfirmation_pkey PRIMARY KEY (id);


--
-- Name: ocrextractioncache ocrextractioncache_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.ocrextractioncache
    ADD CONSTRAINT ocrextractioncache_pkey PRIMARY KEY (id);


--
-- Name: ocrfigure ocrfigure_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.ocrfigure
    ADD CONSTRAINT ocrfigure_pkey PRIMARY KEY (id);


--
-- Name: ocrjob ocrjob_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.ocrjob
    ADD CONSTRAINT ocrjob_pkey PRIMARY KEY (id);


--
-- Name: ocrquestion ocrquestion_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.ocrquestion
    ADD CONSTRAINT ocrquestion_pkey PRIMARY KEY (id);


--
-- Name: payment payment_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.payment
    ADD CONSTRAINT payment_pkey PRIMARY KEY (id);


--
-- Name: plan plan_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.plan
    ADD CONSTRAINT plan_pkey PRIMARY KEY (id);


--
-- Name: promocode promocode_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.promocode
    ADD CONSTRAINT promocode_pkey PRIMARY KEY (id);


--
-- Name: prompt_bindings prompt_bindings_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.prompt_bindings
    ADD CONSTRAINT prompt_bindings_pkey PRIMARY KEY (id);


--
-- Name: prompt_templates prompt_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.prompt_templates
    ADD CONSTRAINT prompt_templates_pkey PRIMARY KEY (id);


--
-- Name: prompt_templates prompt_templates_prompt_id_version_key; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.prompt_templates
    ADD CONSTRAINT prompt_templates_prompt_id_version_key UNIQUE (prompt_id, version);


--
-- Name: providermodelpricing providermodelpricing_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.providermodelpricing
    ADD CONSTRAINT providermodelpricing_pkey PRIMARY KEY (id);


--
-- Name: providerpricingauditevent providerpricingauditevent_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.providerpricingauditevent
    ADD CONSTRAINT providerpricingauditevent_pkey PRIMARY KEY (id);


--
-- Name: question_identity_cache question_identity_cache_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.question_identity_cache
    ADD CONSTRAINT question_identity_cache_pkey PRIMARY KEY (id);


--
-- Name: reconciliationfinding reconciliationfinding_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.reconciliationfinding
    ADD CONSTRAINT reconciliationfinding_pkey PRIMARY KEY (id);


--
-- Name: reconciliationrecord reconciliationrecord_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.reconciliationrecord
    ADD CONSTRAINT reconciliationrecord_pkey PRIMARY KEY (id);


--
-- Name: requestevent requestevent_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.requestevent
    ADD CONSTRAINT requestevent_pkey PRIMARY KEY (id);


--
-- Name: school school_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.school
    ADD CONSTRAINT school_pkey PRIMARY KEY (id);


--
-- Name: schoolimportrun schoolimportrun_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.schoolimportrun
    ADD CONSTRAINT schoolimportrun_pkey PRIMARY KEY (id);


--
-- Name: seed_registry seed_registry_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.seed_registry
    ADD CONSTRAINT seed_registry_pkey PRIMARY KEY (id);


--
-- Name: solution_shares solution_shares_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.solution_shares
    ADD CONSTRAINT solution_shares_pkey PRIMARY KEY (id);


--
-- Name: solve_debug_blob solve_debug_blob_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.solve_debug_blob
    ADD CONSTRAINT solve_debug_blob_pkey PRIMARY KEY (id);


--
-- Name: solvedebugblob solvedebugblob_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.solvedebugblob
    ADD CONSTRAINT solvedebugblob_pkey PRIMARY KEY (id);


--
-- Name: solveroutputattempt solveroutputattempt_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.solveroutputattempt
    ADD CONSTRAINT solveroutputattempt_pkey PRIMARY KEY (id);


--
-- Name: solvesession solvesession_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.solvesession
    ADD CONSTRAINT solvesession_pkey PRIMARY KEY (id);


--
-- Name: stripeevent stripeevent_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.stripeevent
    ADD CONSTRAINT stripeevent_pkey PRIMARY KEY (id);


--
-- Name: stripepricemap stripepricemap_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.stripepricemap
    ADD CONSTRAINT stripepricemap_pkey PRIMARY KEY (id);


--
-- Name: subscription subscription_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.subscription
    ADD CONSTRAINT subscription_pkey PRIMARY KEY (id);


--
-- Name: subscriptionbillinglink subscriptionbillinglink_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.subscriptionbillinglink
    ADD CONSTRAINT subscriptionbillinglink_pkey PRIMARY KEY (id);


--
-- Name: subscriptionperiod subscriptionperiod_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.subscriptionperiod
    ADD CONSTRAINT subscriptionperiod_pkey PRIMARY KEY (id);


--
-- Name: systemconfig systemconfig_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.systemconfig
    ADD CONSTRAINT systemconfig_pkey PRIMARY KEY (key);


--
-- Name: systemconfigversion systemconfigversion_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.systemconfigversion
    ADD CONSTRAINT systemconfigversion_pkey PRIMARY KEY (id);


--
-- Name: systemerrorentry systemerrorentry_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.systemerrorentry
    ADD CONSTRAINT systemerrorentry_pkey PRIMARY KEY (id);


--
-- Name: topuporder topuporder_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.topuporder
    ADD CONSTRAINT topuporder_pkey PRIMARY KEY (id);


--
-- Name: topupproduct topupproduct_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.topupproduct
    ADD CONSTRAINT topupproduct_pkey PRIMARY KEY (id);


--
-- Name: upload upload_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.upload
    ADD CONSTRAINT upload_pkey PRIMARY KEY (id);


--
-- Name: attemptevent uq_attempt_event_attempt_seq; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.attemptevent
    ADD CONSTRAINT uq_attempt_event_attempt_seq UNIQUE (attempt_id, seq);


--
-- Name: chateditcopy uq_chat_edit_copy_chat_user; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.chateditcopy
    ADD CONSTRAINT uq_chat_edit_copy_chat_user UNIQUE (chat_id, user_id);


--
-- Name: chateditcopyv2 uq_chat_edit_copy_v2_chat_user; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.chateditcopyv2
    ADD CONSTRAINT uq_chat_edit_copy_v2_chat_user UNIQUE (chat_id, user_id);


--
-- Name: chateditnotev2 uq_chat_edit_note_v2_chat_user; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.chateditnotev2
    ADD CONSTRAINT uq_chat_edit_note_v2_chat_user UNIQUE (chat_id, user_id);


--
-- Name: chatnote uq_chat_note_chat_user; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.chatnote
    ADD CONSTRAINT uq_chat_note_chat_user UNIQUE (chat_id, user_id);


--
-- Name: credit_holds uq_credit_holds_user_idempotency; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.credit_holds
    ADD CONSTRAINT uq_credit_holds_user_idempotency UNIQUE (user_id, idempotency_key);


--
-- Name: credit_packs uq_credit_packs_pack_code; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.credit_packs
    ADD CONSTRAINT uq_credit_packs_pack_code UNIQUE (pack_code);


--
-- Name: credit_transfers uq_credit_transfer_sender_idem; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.credit_transfers
    ADD CONSTRAINT uq_credit_transfer_sender_idem UNIQUE (sender_user_id, idempotency_key);


--
-- Name: creditprogramgrantlog uq_enrollment_grant_month; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.creditprogramgrantlog
    ADD CONSTRAINT uq_enrollment_grant_month UNIQUE (enrollment_id, grant_month);


--
-- Name: legal_acceptances uq_legal_acceptances_user_doc_version; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.legal_acceptances
    ADD CONSTRAINT uq_legal_acceptances_user_doc_version UNIQUE (user_id, document_key, document_version);


--
-- Name: legal_documents uq_legal_documents_key_version; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.legal_documents
    ADD CONSTRAINT uq_legal_documents_key_version UNIQUE (key, version);


--
-- Name: notifications uq_notifications_user_dedupe; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT uq_notifications_user_dedupe UNIQUE (user_id, dedupe_key);


--
-- Name: payment uq_payment_external; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.payment
    ADD CONSTRAINT uq_payment_external UNIQUE (provider, external_type, external_id);


--
-- Name: prompt_bindings uq_prompt_binding_tier_mode_provider; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.prompt_bindings
    ADD CONSTRAINT uq_prompt_binding_tier_mode_provider UNIQUE (tier, mode, provider);


--
-- Name: school uq_school_country_source_external_id; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.school
    ADD CONSTRAINT uq_school_country_source_external_id UNIQUE (country, source, external_id);


--
-- Name: solution_shares uq_solution_share_owner_attempt; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.solution_shares
    ADD CONSTRAINT uq_solution_share_owner_attempt UNIQUE (owner_user_id, attempt_id);


--
-- Name: solution_shares uq_solution_share_token; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.solution_shares
    ADD CONSTRAINT uq_solution_share_token UNIQUE (share_token);


--
-- Name: solution_shares uq_solution_share_token_hash; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.solution_shares
    ADD CONSTRAINT uq_solution_share_token_hash UNIQUE (share_token_hash);


--
-- Name: subscriptionperiod uq_sub_period_start; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.subscriptionperiod
    ADD CONSTRAINT uq_sub_period_start UNIQUE (subscription_id, period_start);


--
-- Name: creditprogramenrollment uq_user_program_active; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.creditprogramenrollment
    ADD CONSTRAINT uq_user_program_active UNIQUE (user_id, program_id);


--
-- Name: usage_ledger usage_ledger_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.usage_ledger
    ADD CONSTRAINT usage_ledger_pkey PRIMARY KEY (ledger_id);


--
-- Name: usageledger usageledger_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.usageledger
    ADD CONSTRAINT usageledger_pkey PRIMARY KEY (id);


--
-- Name: usagelog usagelog_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.usagelog
    ADD CONSTRAINT usagelog_pkey PRIMARY KEY (id);


--
-- Name: user user_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_pkey PRIMARY KEY (id);


--
-- Name: userquotaoverride userquotaoverride_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.userquotaoverride
    ADD CONSTRAINT userquotaoverride_pkey PRIMARY KEY (id);


--
-- Name: usersavedsolution usersavedsolution_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.usersavedsolution
    ADD CONSTRAINT usersavedsolution_pkey PRIMARY KEY (user_id, solution_id);


--
-- Name: voiceartifact voiceartifact_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.voiceartifact
    ADD CONSTRAINT voiceartifact_pkey PRIMARY KEY (id);


--
-- Name: voiceaudio voiceaudio_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.voiceaudio
    ADD CONSTRAINT voiceaudio_pkey PRIMARY KEY (id);


--
-- Name: voiceconfirmation voiceconfirmation_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.voiceconfirmation
    ADD CONSTRAINT voiceconfirmation_pkey PRIMARY KEY (id);


--
-- Name: voicejob voicejob_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.voicejob
    ADD CONSTRAINT voicejob_pkey PRIMARY KEY (id);


--
-- Name: voicesession voicesession_pkey; Type: CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.voicesession
    ADD CONSTRAINT voicesession_pkey PRIMARY KEY (id);


--
-- Name: idx_prompt_bindings_provider; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX idx_prompt_bindings_provider ON public.prompt_bindings USING btree (provider);


--
-- Name: idx_school_country_province_city; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX idx_school_country_province_city ON public.school USING btree (country, province_state, city);


--
-- Name: idx_school_external_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX idx_school_external_id ON public.school USING btree (external_id);


--
-- Name: idx_school_school_key; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX idx_school_school_key ON public.school USING btree (school_key);


--
-- Name: ix_adminauditlog_action; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_adminauditlog_action ON public.adminauditlog USING btree (action);


--
-- Name: ix_adminauditlog_admin_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_adminauditlog_admin_user_id ON public.adminauditlog USING btree (admin_user_id);


--
-- Name: ix_adminauditlog_created_at; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_adminauditlog_created_at ON public.adminauditlog USING btree (created_at);


--
-- Name: ix_adminauditlog_entity_type; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_adminauditlog_entity_type ON public.adminauditlog USING btree (entity_type);


--
-- Name: ix_adminauditlog_idempotency_key; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_adminauditlog_idempotency_key ON public.adminauditlog USING btree (idempotency_key);


--
-- Name: ix_adminnote_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_adminnote_user_id ON public.adminnote USING btree (user_id);


--
-- Name: ix_attempt_event_attempt_seq; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_attempt_event_attempt_seq ON public.attemptevent USING btree (attempt_id, seq);


--
-- Name: ix_attempt_event_created_at; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_attempt_event_created_at ON public.attemptevent USING btree (created_at);


--
-- Name: ix_attemptevent_attempt_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_attemptevent_attempt_id ON public.attemptevent USING btree (attempt_id);


--
-- Name: ix_attemptevent_created_at; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_attemptevent_created_at ON public.attemptevent USING btree (created_at);


--
-- Name: ix_attemptevent_seq; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_attemptevent_seq ON public.attemptevent USING btree (seq);


--
-- Name: ix_attemptevent_type; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_attemptevent_type ON public.attemptevent USING btree (type);


--
-- Name: ix_billingledger_action_type; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_billingledger_action_type ON public.billingledger USING btree (action_type);


--
-- Name: ix_billingledger_config_version_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_billingledger_config_version_id ON public.billingledger USING btree (config_version_id);


--
-- Name: ix_billingledger_created_at; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_billingledger_created_at ON public.billingledger USING btree (created_at);


--
-- Name: ix_billingledger_idempotency_key; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE UNIQUE INDEX ix_billingledger_idempotency_key ON public.billingledger USING btree (idempotency_key);


--
-- Name: ix_billingledger_request_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_billingledger_request_id ON public.billingledger USING btree (request_id);


--
-- Name: ix_billingledger_status; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_billingledger_status ON public.billingledger USING btree (status);


--
-- Name: ix_billingledger_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_billingledger_user_id ON public.billingledger USING btree (user_id);


--
-- Name: ix_canonicalproblem_intent; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_canonicalproblem_intent ON public.canonicalproblem USING btree (intent);


--
-- Name: ix_canonicalproblem_normalized_problem_hash; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE UNIQUE INDEX ix_canonicalproblem_normalized_problem_hash ON public.canonicalproblem USING btree (normalized_problem_hash);


--
-- Name: ix_canonicalsolution_problem_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_canonicalsolution_problem_id ON public.canonicalsolution USING btree (problem_id);


--
-- Name: ix_chat_edit_copy_chat_user; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_chat_edit_copy_chat_user ON public.chateditcopy USING btree (chat_id, user_id);


--
-- Name: ix_chat_edit_copy_v2_chat_user; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_chat_edit_copy_v2_chat_user ON public.chateditcopyv2 USING btree (chat_id, user_id);


--
-- Name: ix_chat_edit_note_v2_chat_user; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_chat_edit_note_v2_chat_user ON public.chateditnotev2 USING btree (chat_id, user_id);


--
-- Name: ix_chat_note_chat_user; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_chat_note_chat_user ON public.chatnote USING btree (chat_id, user_id);


--
-- Name: ix_chateditcopy_canonical_md_hash; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_chateditcopy_canonical_md_hash ON public.chateditcopy USING btree (canonical_md_hash);


--
-- Name: ix_chateditcopy_chat_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_chateditcopy_chat_id ON public.chateditcopy USING btree (chat_id);


--
-- Name: ix_chateditcopy_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_chateditcopy_user_id ON public.chateditcopy USING btree (user_id);


--
-- Name: ix_chateditcopy_version; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_chateditcopy_version ON public.chateditcopy USING btree (version);


--
-- Name: ix_chateditcopyv2_canonical_md_hash; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_chateditcopyv2_canonical_md_hash ON public.chateditcopyv2 USING btree (canonical_md_hash);


--
-- Name: ix_chateditcopyv2_chat_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_chateditcopyv2_chat_id ON public.chateditcopyv2 USING btree (chat_id);


--
-- Name: ix_chateditcopyv2_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_chateditcopyv2_user_id ON public.chateditcopyv2 USING btree (user_id);


--
-- Name: ix_chateditcopyv2_version; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_chateditcopyv2_version ON public.chateditcopyv2 USING btree (version);


--
-- Name: ix_chateditnotev2_chat_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_chateditnotev2_chat_id ON public.chateditnotev2 USING btree (chat_id);


--
-- Name: ix_chateditnotev2_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_chateditnotev2_user_id ON public.chateditnotev2 USING btree (user_id);


--
-- Name: ix_chateditnotev2_version; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_chateditnotev2_version ON public.chateditnotev2 USING btree (version);


--
-- Name: ix_chatnote_chat_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_chatnote_chat_id ON public.chatnote USING btree (chat_id);


--
-- Name: ix_chatnote_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_chatnote_user_id ON public.chatnote USING btree (user_id);


--
-- Name: ix_chatnote_version; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_chatnote_version ON public.chatnote USING btree (version);


--
-- Name: ix_chatsession_is_saved; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_chatsession_is_saved ON public.chatsession USING btree (is_saved);


--
-- Name: ix_credit_holds_idempotency_key; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_credit_holds_idempotency_key ON public.credit_holds USING btree (idempotency_key);


--
-- Name: ix_credit_holds_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_credit_holds_user_id ON public.credit_holds USING btree (user_id);


--
-- Name: ix_credit_lots_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_credit_lots_user_id ON public.credit_lots USING btree (user_id);


--
-- Name: ix_credit_packs_is_active; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_credit_packs_is_active ON public.credit_packs USING btree (is_active);


--
-- Name: ix_credit_packs_pack_code; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_credit_packs_pack_code ON public.credit_packs USING btree (pack_code);


--
-- Name: ix_credit_transfer_recipient_status; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_credit_transfer_recipient_status ON public.credit_transfers USING btree (recipient_email, status);


--
-- Name: ix_credit_transfer_sender_created; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_credit_transfer_sender_created ON public.credit_transfers USING btree (sender_user_id, created_at);


--
-- Name: ix_credit_transfers_created_at; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_credit_transfers_created_at ON public.credit_transfers USING btree (created_at);


--
-- Name: ix_credit_transfers_escrow_lot_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_credit_transfers_escrow_lot_id ON public.credit_transfers USING btree (escrow_lot_id);


--
-- Name: ix_credit_transfers_expires_at; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_credit_transfers_expires_at ON public.credit_transfers USING btree (expires_at);


--
-- Name: ix_credit_transfers_idempotency_key; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_credit_transfers_idempotency_key ON public.credit_transfers USING btree (idempotency_key);


--
-- Name: ix_credit_transfers_recipient_email; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_credit_transfers_recipient_email ON public.credit_transfers USING btree (recipient_email);


--
-- Name: ix_credit_transfers_recipient_ledger_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_credit_transfers_recipient_ledger_id ON public.credit_transfers USING btree (recipient_ledger_id);


--
-- Name: ix_credit_transfers_recipient_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_credit_transfers_recipient_user_id ON public.credit_transfers USING btree (recipient_user_id);


--
-- Name: ix_credit_transfers_refund_ledger_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_credit_transfers_refund_ledger_id ON public.credit_transfers USING btree (refund_ledger_id);


--
-- Name: ix_credit_transfers_sender_ip_hash; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_credit_transfers_sender_ip_hash ON public.credit_transfers USING btree (sender_ip_hash);


--
-- Name: ix_credit_transfers_sender_ledger_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_credit_transfers_sender_ledger_id ON public.credit_transfers USING btree (sender_ledger_id);


--
-- Name: ix_credit_transfers_sender_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_credit_transfers_sender_user_id ON public.credit_transfers USING btree (sender_user_id);


--
-- Name: ix_credit_transfers_status; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_credit_transfers_status ON public.credit_transfers USING btree (status);


--
-- Name: ix_credithold_question_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_credithold_question_id ON public.credithold USING btree (question_id);


--
-- Name: ix_credithold_request_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_credithold_request_id ON public.credithold USING btree (request_id);


--
-- Name: ix_credithold_subscription_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_credithold_subscription_id ON public.credithold USING btree (subscription_id);


--
-- Name: ix_credithold_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_credithold_user_id ON public.credithold USING btree (user_id);


--
-- Name: ix_creditlot_expires_at; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_creditlot_expires_at ON public.creditlot USING btree (expires_at);


--
-- Name: ix_creditlot_external_ref; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_creditlot_external_ref ON public.creditlot USING btree (external_ref);


--
-- Name: ix_creditlot_lot_type; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_creditlot_lot_type ON public.creditlot USING btree (lot_type);


--
-- Name: ix_creditlot_source; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_creditlot_source ON public.creditlot USING btree (source);


--
-- Name: ix_creditlot_source_attempt_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_creditlot_source_attempt_id ON public.creditlot USING btree (source_attempt_id);


--
-- Name: ix_creditlot_source_payment_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_creditlot_source_payment_id ON public.creditlot USING btree (source_payment_id);


--
-- Name: ix_creditlot_source_program_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_creditlot_source_program_id ON public.creditlot USING btree (source_program_id);


--
-- Name: ix_creditlot_status; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_creditlot_status ON public.creditlot USING btree (status);


--
-- Name: ix_creditlot_subscription_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_creditlot_subscription_id ON public.creditlot USING btree (subscription_id);


--
-- Name: ix_creditlot_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_creditlot_user_id ON public.creditlot USING btree (user_id);


--
-- Name: ix_creditlotconsumption_attempt_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_creditlotconsumption_attempt_id ON public.creditlotconsumption USING btree (attempt_id);


--
-- Name: ix_creditlotconsumption_credit_lot_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_creditlotconsumption_credit_lot_id ON public.creditlotconsumption USING btree (credit_lot_id);


--
-- Name: ix_creditlotconsumption_direction; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_creditlotconsumption_direction ON public.creditlotconsumption USING btree (direction);


--
-- Name: ix_creditlotconsumption_ledger_event_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_creditlotconsumption_ledger_event_id ON public.creditlotconsumption USING btree (ledger_event_id);


--
-- Name: ix_creditlotconsumption_usage_ledger_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_creditlotconsumption_usage_ledger_id ON public.creditlotconsumption USING btree (usage_ledger_id);


--
-- Name: ix_creditlotconsumption_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_creditlotconsumption_user_id ON public.creditlotconsumption USING btree (user_id);


--
-- Name: ix_creditprogramdefinition_name; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_creditprogramdefinition_name ON public.creditprogramdefinition USING btree (name);


--
-- Name: ix_creditprogramdefinition_slug; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE UNIQUE INDEX ix_creditprogramdefinition_slug ON public.creditprogramdefinition USING btree (slug);


--
-- Name: ix_creditprogramdefinition_status; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_creditprogramdefinition_status ON public.creditprogramdefinition USING btree (status);


--
-- Name: ix_creditprogramenrollment_last_grant_month; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_creditprogramenrollment_last_grant_month ON public.creditprogramenrollment USING btree (last_grant_month);


--
-- Name: ix_creditprogramenrollment_program_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_creditprogramenrollment_program_id ON public.creditprogramenrollment USING btree (program_id);


--
-- Name: ix_creditprogramenrollment_status; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_creditprogramenrollment_status ON public.creditprogramenrollment USING btree (status);


--
-- Name: ix_creditprogramenrollment_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_creditprogramenrollment_user_id ON public.creditprogramenrollment USING btree (user_id);


--
-- Name: ix_creditprogramgrantlog_credit_lot_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_creditprogramgrantlog_credit_lot_id ON public.creditprogramgrantlog USING btree (credit_lot_id);


--
-- Name: ix_creditprogramgrantlog_enrollment_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_creditprogramgrantlog_enrollment_id ON public.creditprogramgrantlog USING btree (enrollment_id);


--
-- Name: ix_creditprogramgrantlog_grant_month; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_creditprogramgrantlog_grant_month ON public.creditprogramgrantlog USING btree (grant_month);


--
-- Name: ix_creditprogramgrantlog_program_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_creditprogramgrantlog_program_id ON public.creditprogramgrantlog USING btree (program_id);


--
-- Name: ix_creditprogramgrantlog_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_creditprogramgrantlog_user_id ON public.creditprogramgrantlog USING btree (user_id);


--
-- Name: ix_crop_crop_image_hash; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE UNIQUE INDEX ix_crop_crop_image_hash ON public.crop USING btree (crop_image_hash);


--
-- Name: ix_crop_upload_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_crop_upload_id ON public.crop USING btree (upload_id);


--
-- Name: ix_devicesignuplog_device_hash; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_devicesignuplog_device_hash ON public.devicesignuplog USING btree (device_hash);


--
-- Name: ix_followupchatturn_solve_session_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_followupchatturn_solve_session_id ON public.followupchatturn USING btree (solve_session_id);


--
-- Name: ix_followupchatturn_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_followupchatturn_user_id ON public.followupchatturn USING btree (user_id);


--
-- Name: ix_invoice_invoice_number; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE UNIQUE INDEX ix_invoice_invoice_number ON public.invoice USING btree (invoice_number);


--
-- Name: ix_invoice_kind; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_invoice_kind ON public.invoice USING btree (kind);


--
-- Name: ix_invoice_status; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_invoice_status ON public.invoice USING btree (status);


--
-- Name: ix_invoice_stripe_invoice_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE UNIQUE INDEX ix_invoice_stripe_invoice_id ON public.invoice USING btree (stripe_invoice_id);


--
-- Name: ix_invoice_stripe_payment_intent_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_invoice_stripe_payment_intent_id ON public.invoice USING btree (stripe_payment_intent_id);


--
-- Name: ix_invoice_subscription_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_invoice_subscription_id ON public.invoice USING btree (subscription_id);


--
-- Name: ix_invoice_topup_order_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_invoice_topup_order_id ON public.invoice USING btree (topup_order_id);


--
-- Name: ix_invoice_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_invoice_user_id ON public.invoice USING btree (user_id);


--
-- Name: ix_invoicelineitem_invoice_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_invoicelineitem_invoice_id ON public.invoicelineitem USING btree (invoice_id);


--
-- Name: ix_invoicesequence_year; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE UNIQUE INDEX ix_invoicesequence_year ON public.invoicesequence USING btree (year);


--
-- Name: ix_json_schemas_is_active; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_json_schemas_is_active ON public.json_schemas USING btree (is_active);


--
-- Name: ix_json_schemas_schema_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_json_schemas_schema_id ON public.json_schemas USING btree (schema_id);


--
-- Name: ix_json_schemas_version; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_json_schemas_version ON public.json_schemas USING btree (version);


--
-- Name: ix_legal_acceptances_doc_key_version; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_legal_acceptances_doc_key_version ON public.legal_acceptances USING btree (document_key, document_version);


--
-- Name: ix_legal_acceptances_document_key; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_legal_acceptances_document_key ON public.legal_acceptances USING btree (document_key);


--
-- Name: ix_legal_acceptances_document_version; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_legal_acceptances_document_version ON public.legal_acceptances USING btree (document_version);


--
-- Name: ix_legal_acceptances_user_doc_key_time; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_legal_acceptances_user_doc_key_time ON public.legal_acceptances USING btree (user_id, document_key, accepted_at);


--
-- Name: ix_legal_acceptances_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_legal_acceptances_user_id ON public.legal_acceptances USING btree (user_id);


--
-- Name: ix_legal_documents_checksum_sha256; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_legal_documents_checksum_sha256 ON public.legal_documents USING btree (checksum_sha256);


--
-- Name: ix_legal_documents_created_by; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_legal_documents_created_by ON public.legal_documents USING btree (created_by);


--
-- Name: ix_legal_documents_key; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_legal_documents_key ON public.legal_documents USING btree (key);


--
-- Name: ix_legal_documents_key_status; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_legal_documents_key_status ON public.legal_documents USING btree (key, status);


--
-- Name: ix_legal_documents_status; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_legal_documents_status ON public.legal_documents USING btree (status);


--
-- Name: ix_legal_documents_updated_by; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_legal_documents_updated_by ON public.legal_documents USING btree (updated_by);


--
-- Name: ix_legal_documents_version; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_legal_documents_version ON public.legal_documents USING btree (version);


--
-- Name: ix_llmusageledger_followup_turn_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE UNIQUE INDEX ix_llmusageledger_followup_turn_id ON public.llmusageledger USING btree (followup_turn_id);


--
-- Name: ix_llmusageledger_solve_session_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_llmusageledger_solve_session_id ON public.llmusageledger USING btree (solve_session_id);


--
-- Name: ix_notifications_action_type; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_notifications_action_type ON public.notifications USING btree (action_type);


--
-- Name: ix_notifications_created_at; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_notifications_created_at ON public.notifications USING btree (created_at);


--
-- Name: ix_notifications_dedupe_key; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_notifications_dedupe_key ON public.notifications USING btree (dedupe_key);


--
-- Name: ix_notifications_is_read; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_notifications_is_read ON public.notifications USING btree (is_read);


--
-- Name: ix_notifications_severity; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_notifications_severity ON public.notifications USING btree (severity);


--
-- Name: ix_notifications_type; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_notifications_type ON public.notifications USING btree (type);


--
-- Name: ix_notifications_user_created; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_notifications_user_created ON public.notifications USING btree (user_id, created_at);


--
-- Name: ix_notifications_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_notifications_user_id ON public.notifications USING btree (user_id);


--
-- Name: ix_notifications_user_unread; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_notifications_user_unread ON public.notifications USING btree (user_id, is_read);


--
-- Name: ix_ocrartifact_crop_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_ocrartifact_crop_id ON public.ocrartifact USING btree (crop_id);


--
-- Name: ix_ocrartifact_engine_used; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_ocrartifact_engine_used ON public.ocrartifact USING btree (engine_used);


--
-- Name: ix_ocrartifact_job_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_ocrartifact_job_id ON public.ocrartifact USING btree (job_id);


--
-- Name: ix_ocrauditevent_created_at; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_ocrauditevent_created_at ON public.ocrauditevent USING btree (created_at);


--
-- Name: ix_ocrauditevent_routing_engine_chosen; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_ocrauditevent_routing_engine_chosen ON public.ocrauditevent USING btree (routing_engine_chosen);


--
-- Name: ix_ocrauditevent_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_ocrauditevent_user_id ON public.ocrauditevent USING btree (user_id);


--
-- Name: ix_ocrcache_cache_key; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE UNIQUE INDEX ix_ocrcache_cache_key ON public.ocrcache USING btree (cache_key);


--
-- Name: ix_ocrchoice_question_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_ocrchoice_question_id ON public.ocrchoice USING btree (question_id);


--
-- Name: ix_ocrconfirmation_artifact_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_ocrconfirmation_artifact_id ON public.ocrconfirmation USING btree (artifact_id);


--
-- Name: ix_ocrconfirmation_normalized_problem_hash; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_ocrconfirmation_normalized_problem_hash ON public.ocrconfirmation USING btree (normalized_problem_hash);


--
-- Name: ix_ocrconfirmation_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_ocrconfirmation_user_id ON public.ocrconfirmation USING btree (user_id);


--
-- Name: ix_ocrextractioncache_cache_key; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE UNIQUE INDEX ix_ocrextractioncache_cache_key ON public.ocrextractioncache USING btree (cache_key);


--
-- Name: ix_ocrextractioncache_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_ocrextractioncache_user_id ON public.ocrextractioncache USING btree (user_id);


--
-- Name: ix_ocrfigure_artifact_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_ocrfigure_artifact_id ON public.ocrfigure USING btree (artifact_id);


--
-- Name: ix_ocrjob_accepted_solve_attempt_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_ocrjob_accepted_solve_attempt_id ON public.ocrjob USING btree (accepted_solve_attempt_id);


--
-- Name: ix_ocrjob_crop_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_ocrjob_crop_id ON public.ocrjob USING btree (crop_id);


--
-- Name: ix_ocrjob_dedupe_key; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_ocrjob_dedupe_key ON public.ocrjob USING btree (dedupe_key);


--
-- Name: ix_ocrjob_hold_request_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_ocrjob_hold_request_id ON public.ocrjob USING btree (hold_request_id);


--
-- Name: ix_ocrjob_image_fingerprint; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_ocrjob_image_fingerprint ON public.ocrjob USING btree (image_fingerprint);


--
-- Name: ix_ocrjob_json_schema_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_ocrjob_json_schema_id ON public.ocrjob USING btree (json_schema_id);


--
-- Name: ix_ocrjob_prompt_template_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_ocrjob_prompt_template_id ON public.ocrjob USING btree (prompt_template_id);


--
-- Name: ix_ocrjob_user_created; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_ocrjob_user_created ON public.ocrjob USING btree (user_id, created_at);


--
-- Name: ix_ocrjob_user_dedupe; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_ocrjob_user_dedupe ON public.ocrjob USING btree (user_id, dedupe_key);


--
-- Name: ix_ocrjob_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_ocrjob_user_id ON public.ocrjob USING btree (user_id);


--
-- Name: ix_ocrquestion_artifact_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_ocrquestion_artifact_id ON public.ocrquestion USING btree (artifact_id);


--
-- Name: ix_payment_created_at; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_payment_created_at ON public.payment USING btree (created_at);


--
-- Name: ix_payment_external_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_payment_external_id ON public.payment USING btree (external_id);


--
-- Name: ix_payment_external_type; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_payment_external_type ON public.payment USING btree (external_type);


--
-- Name: ix_payment_idempotency_key; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_payment_idempotency_key ON public.payment USING btree (idempotency_key);


--
-- Name: ix_payment_provider; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_payment_provider ON public.payment USING btree (provider);


--
-- Name: ix_payment_status; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_payment_status ON public.payment USING btree (status);


--
-- Name: ix_payment_subscription_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_payment_subscription_id ON public.payment USING btree (subscription_id);


--
-- Name: ix_payment_transaction_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_payment_transaction_id ON public.payment USING btree (transaction_id);


--
-- Name: ix_payment_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_payment_user_id ON public.payment USING btree (user_id);


--
-- Name: ix_plan_slug; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE UNIQUE INDEX ix_plan_slug ON public.plan USING btree (slug);


--
-- Name: ix_promocode_code; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE UNIQUE INDEX ix_promocode_code ON public.promocode USING btree (code);


--
-- Name: ix_prompt_bindings_developer_prompt_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_prompt_bindings_developer_prompt_id ON public.prompt_bindings USING btree (developer_prompt_id);


--
-- Name: ix_prompt_bindings_global_system_prompt_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_prompt_bindings_global_system_prompt_id ON public.prompt_bindings USING btree (global_system_prompt_id);


--
-- Name: ix_prompt_bindings_is_active; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_prompt_bindings_is_active ON public.prompt_bindings USING btree (is_active);


--
-- Name: ix_prompt_bindings_openai_prompt_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_prompt_bindings_openai_prompt_id ON public.prompt_bindings USING btree (openai_prompt_id);


--
-- Name: ix_prompt_bindings_output_schema_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_prompt_bindings_output_schema_id ON public.prompt_bindings USING btree (output_schema_id);


--
-- Name: ix_prompt_templates_is_active; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_prompt_templates_is_active ON public.prompt_templates USING btree (is_active);


--
-- Name: ix_prompt_templates_prompt_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_prompt_templates_prompt_id ON public.prompt_templates USING btree (prompt_id);


--
-- Name: ix_prompt_templates_version; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_prompt_templates_version ON public.prompt_templates USING btree (version);


--
-- Name: ix_providermodelpricing_model; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_providermodelpricing_model ON public.providermodelpricing USING btree (model);


--
-- Name: ix_providermodelpricing_provider; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_providermodelpricing_provider ON public.providermodelpricing USING btree (provider);


--
-- Name: ix_providermodelpricing_status; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_providermodelpricing_status ON public.providermodelpricing USING btree (status);


--
-- Name: ix_providerpricingauditevent_admin_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_providerpricingauditevent_admin_user_id ON public.providerpricingauditevent USING btree (admin_user_id);


--
-- Name: ix_providerpricingauditevent_provider_model_pricing_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_providerpricingauditevent_provider_model_pricing_id ON public.providerpricingauditevent USING btree (provider_model_pricing_id);


--
-- Name: ix_question_identity_cache_question_key; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE UNIQUE INDEX ix_question_identity_cache_question_key ON public.question_identity_cache USING btree (question_key);


--
-- Name: ix_reconciliationfinding_created_at; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_reconciliationfinding_created_at ON public.reconciliationfinding USING btree (created_at);


--
-- Name: ix_reconciliationfinding_entity_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_reconciliationfinding_entity_id ON public.reconciliationfinding USING btree (entity_id);


--
-- Name: ix_reconciliationfinding_entity_type; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_reconciliationfinding_entity_type ON public.reconciliationfinding USING btree (entity_type);


--
-- Name: ix_reconciliationfinding_finding_type; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_reconciliationfinding_finding_type ON public.reconciliationfinding USING btree (finding_type);


--
-- Name: ix_reconciliationfinding_status; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_reconciliationfinding_status ON public.reconciliationfinding USING btree (status);


--
-- Name: ix_reconciliationfinding_trace_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_reconciliationfinding_trace_id ON public.reconciliationfinding USING btree (trace_id);


--
-- Name: ix_reconciliationrecord_created_at; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_reconciliationrecord_created_at ON public.reconciliationrecord USING btree (created_at);


--
-- Name: ix_reconciliationrecord_job_run_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_reconciliationrecord_job_run_id ON public.reconciliationrecord USING btree (job_run_id);


--
-- Name: ix_reconciliationrecord_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_reconciliationrecord_user_id ON public.reconciliationrecord USING btree (user_id);


--
-- Name: ix_requestevent_created_at; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_requestevent_created_at ON public.requestevent USING btree (created_at);


--
-- Name: ix_requestevent_error_type; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_requestevent_error_type ON public.requestevent USING btree (error_type);


--
-- Name: ix_requestevent_grade_level; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_requestevent_grade_level ON public.requestevent USING btree (grade_level);


--
-- Name: ix_requestevent_learning_mode; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_requestevent_learning_mode ON public.requestevent USING btree (learning_mode);


--
-- Name: ix_requestevent_mode; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_requestevent_mode ON public.requestevent USING btree (mode);


--
-- Name: ix_requestevent_model; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_requestevent_model ON public.requestevent USING btree (model);


--
-- Name: ix_requestevent_provider; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_requestevent_provider ON public.requestevent USING btree (provider);


--
-- Name: ix_requestevent_request_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_requestevent_request_id ON public.requestevent USING btree (request_id);


--
-- Name: ix_requestevent_route; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_requestevent_route ON public.requestevent USING btree (route);


--
-- Name: ix_requestevent_status; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_requestevent_status ON public.requestevent USING btree (status);


--
-- Name: ix_requestevent_subject; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_requestevent_subject ON public.requestevent USING btree (subject);


--
-- Name: ix_requestevent_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_requestevent_user_id ON public.requestevent USING btree (user_id);


--
-- Name: ix_school_country; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_school_country ON public.school USING btree (country);


--
-- Name: ix_school_province_state; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_school_province_state ON public.school USING btree (province_state);


--
-- Name: ix_school_school_key; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_school_school_key ON public.school USING btree (school_key);


--
-- Name: ix_school_school_name; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_school_school_name ON public.school USING btree (school_name);


--
-- Name: ix_school_source; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_school_source ON public.school USING btree (source);


--
-- Name: ix_schoolimportrun_status; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_schoolimportrun_status ON public.schoolimportrun USING btree (status);


--
-- Name: ix_seed_registry_environment; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_seed_registry_environment ON public.seed_registry USING btree (environment);


--
-- Name: ix_seed_registry_seed_name; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE UNIQUE INDEX ix_seed_registry_seed_name ON public.seed_registry USING btree (seed_name);


--
-- Name: ix_solution_share_attempt_owner; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solution_share_attempt_owner ON public.solution_shares USING btree (attempt_id, owner_user_id);


--
-- Name: ix_solution_shares_attempt_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solution_shares_attempt_id ON public.solution_shares USING btree (attempt_id);


--
-- Name: ix_solution_shares_created_at; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solution_shares_created_at ON public.solution_shares USING btree (created_at);


--
-- Name: ix_solution_shares_expires_at; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solution_shares_expires_at ON public.solution_shares USING btree (expires_at);


--
-- Name: ix_solution_shares_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solution_shares_id ON public.solution_shares USING btree (id);


--
-- Name: ix_solution_shares_last_viewed_at; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solution_shares_last_viewed_at ON public.solution_shares USING btree (last_viewed_at);


--
-- Name: ix_solution_shares_owner_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solution_shares_owner_user_id ON public.solution_shares USING btree (owner_user_id);


--
-- Name: ix_solution_shares_revoked_at; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solution_shares_revoked_at ON public.solution_shares USING btree (revoked_at);


--
-- Name: ix_solution_shares_share_token; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solution_shares_share_token ON public.solution_shares USING btree (share_token);


--
-- Name: ix_solution_shares_share_token_hash; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solution_shares_share_token_hash ON public.solution_shares USING btree (share_token_hash);


--
-- Name: ix_solution_shares_solver_output_attempt_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solution_shares_solver_output_attempt_id ON public.solution_shares USING btree (solver_output_attempt_id);


--
-- Name: ix_solution_shares_visibility; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solution_shares_visibility ON public.solution_shares USING btree (visibility);


--
-- Name: ix_solve_debug_blob_attempt_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solve_debug_blob_attempt_id ON public.solve_debug_blob USING btree (attempt_id);


--
-- Name: ix_solve_debug_blob_blob_type; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solve_debug_blob_blob_type ON public.solve_debug_blob USING btree (blob_type);


--
-- Name: ix_solve_debug_blob_sha256; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solve_debug_blob_sha256 ON public.solve_debug_blob USING btree (sha256);


--
-- Name: ix_solvedebugblob_attempt_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solvedebugblob_attempt_id ON public.solvedebugblob USING btree (attempt_id);


--
-- Name: ix_solvedebugblob_blob_type; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solvedebugblob_blob_type ON public.solvedebugblob USING btree (blob_type);


--
-- Name: ix_solvedebugblob_created_at; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solvedebugblob_created_at ON public.solvedebugblob USING btree (created_at);


--
-- Name: ix_solvedebugblob_failure_code; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solvedebugblob_failure_code ON public.solvedebugblob USING btree (failure_code);


--
-- Name: ix_solvedebugblob_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solvedebugblob_id ON public.solvedebugblob USING btree (id);


--
-- Name: ix_solvedebugblob_provider_model; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solvedebugblob_provider_model ON public.solvedebugblob USING btree (provider_model);


--
-- Name: ix_solvedebugblob_sha256; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solvedebugblob_sha256 ON public.solvedebugblob USING btree (sha256);


--
-- Name: ix_solvedebugblob_status; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solvedebugblob_status ON public.solvedebugblob USING btree (status);


--
-- Name: ix_solvedebugblob_stored_reason; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solvedebugblob_stored_reason ON public.solvedebugblob USING btree (stored_reason);


--
-- Name: ix_solver_attempt_cancel_requested_at; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solver_attempt_cancel_requested_at ON public.solveroutputattempt USING btree (cancel_requested_at);


--
-- Name: ix_solver_attempt_finished_at; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solver_attempt_finished_at ON public.solveroutputattempt USING btree (finished_at);


--
-- Name: ix_solver_attempt_started_at; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solver_attempt_started_at ON public.solveroutputattempt USING btree (started_at);


--
-- Name: ix_solver_attempt_ttl_deadline_at; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solver_attempt_ttl_deadline_at ON public.solveroutputattempt USING btree (ttl_deadline_at);


--
-- Name: ix_solveroutputattempt_attempt_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solveroutputattempt_attempt_id ON public.solveroutputattempt USING btree (attempt_id);


--
-- Name: ix_solveroutputattempt_attempt_number; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solveroutputattempt_attempt_number ON public.solveroutputattempt USING btree (attempt_number);


--
-- Name: ix_solveroutputattempt_created_at; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solveroutputattempt_created_at ON public.solveroutputattempt USING btree (created_at);


--
-- Name: ix_solveroutputattempt_failure_code; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solveroutputattempt_failure_code ON public.solveroutputattempt USING btree (failure_code);


--
-- Name: ix_solveroutputattempt_message_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solveroutputattempt_message_id ON public.solveroutputattempt USING btree (message_id);


--
-- Name: ix_solveroutputattempt_model; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solveroutputattempt_model ON public.solveroutputattempt USING btree (model);


--
-- Name: ix_solveroutputattempt_output_format; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solveroutputattempt_output_format ON public.solveroutputattempt USING btree (output_format);


--
-- Name: ix_solveroutputattempt_prompt_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solveroutputattempt_prompt_id ON public.solveroutputattempt USING btree (prompt_id);


--
-- Name: ix_solveroutputattempt_provider; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solveroutputattempt_provider ON public.solveroutputattempt USING btree (provider);


--
-- Name: ix_solveroutputattempt_provider_model; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solveroutputattempt_provider_model ON public.solveroutputattempt USING btree (provider_model);


--
-- Name: ix_solveroutputattempt_request_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solveroutputattempt_request_id ON public.solveroutputattempt USING btree (request_id);


--
-- Name: ix_solveroutputattempt_session_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solveroutputattempt_session_id ON public.solveroutputattempt USING btree (session_id);


--
-- Name: ix_solveroutputattempt_solve_mode; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solveroutputattempt_solve_mode ON public.solveroutputattempt USING btree (solve_mode);


--
-- Name: ix_solveroutputattempt_status; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solveroutputattempt_status ON public.solveroutputattempt USING btree (status);


--
-- Name: ix_solveroutputattempt_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solveroutputattempt_user_id ON public.solveroutputattempt USING btree (user_id);


--
-- Name: ix_solvesession_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_solvesession_user_id ON public.solvesession USING btree (user_id);


--
-- Name: ix_stripeevent_created_ts; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_stripeevent_created_ts ON public.stripeevent USING btree (created_ts);


--
-- Name: ix_stripeevent_process_status; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_stripeevent_process_status ON public.stripeevent USING btree (process_status);


--
-- Name: ix_stripeevent_stripe_event_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE UNIQUE INDEX ix_stripeevent_stripe_event_id ON public.stripeevent USING btree (stripe_event_id);


--
-- Name: ix_stripeevent_type; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_stripeevent_type ON public.stripeevent USING btree (type);


--
-- Name: ix_stripepricemap_internal_code; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_stripepricemap_internal_code ON public.stripepricemap USING btree (internal_code);


--
-- Name: ix_stripepricemap_kind; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_stripepricemap_kind ON public.stripepricemap USING btree (kind);


--
-- Name: ix_stripepricemap_stripe_price_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_stripepricemap_stripe_price_id ON public.stripepricemap USING btree (stripe_price_id);


--
-- Name: ix_subscription_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE UNIQUE INDEX ix_subscription_user_id ON public.subscription USING btree (user_id);


--
-- Name: ix_subscriptionbillinglink_status; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_subscriptionbillinglink_status ON public.subscriptionbillinglink USING btree (status);


--
-- Name: ix_subscriptionbillinglink_stripe_customer_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_subscriptionbillinglink_stripe_customer_id ON public.subscriptionbillinglink USING btree (stripe_customer_id);


--
-- Name: ix_subscriptionbillinglink_stripe_price_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_subscriptionbillinglink_stripe_price_id ON public.subscriptionbillinglink USING btree (stripe_price_id);


--
-- Name: ix_subscriptionbillinglink_stripe_subscription_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE UNIQUE INDEX ix_subscriptionbillinglink_stripe_subscription_id ON public.subscriptionbillinglink USING btree (stripe_subscription_id);


--
-- Name: ix_subscriptionbillinglink_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_subscriptionbillinglink_user_id ON public.subscriptionbillinglink USING btree (user_id);


--
-- Name: ix_subscriptionperiod_period_end; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_subscriptionperiod_period_end ON public.subscriptionperiod USING btree (period_end);


--
-- Name: ix_subscriptionperiod_period_start; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_subscriptionperiod_period_start ON public.subscriptionperiod USING btree (period_start);


--
-- Name: ix_subscriptionperiod_status; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_subscriptionperiod_status ON public.subscriptionperiod USING btree (status);


--
-- Name: ix_subscriptionperiod_subscription_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_subscriptionperiod_subscription_id ON public.subscriptionperiod USING btree (subscription_id);


--
-- Name: ix_systemconfigversion_config_type; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_systemconfigversion_config_type ON public.systemconfigversion USING btree (config_type);


--
-- Name: ix_systemconfigversion_created_by; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_systemconfigversion_created_by ON public.systemconfigversion USING btree (created_by);


--
-- Name: ix_systemconfigversion_version; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_systemconfigversion_version ON public.systemconfigversion USING btree (version);


--
-- Name: ix_systemerrorentry_component; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_systemerrorentry_component ON public.systemerrorentry USING btree (component);


--
-- Name: ix_systemerrorentry_created_at; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_systemerrorentry_created_at ON public.systemerrorentry USING btree (created_at);


--
-- Name: ix_systemerrorentry_error_code; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_systemerrorentry_error_code ON public.systemerrorentry USING btree (error_code);


--
-- Name: ix_systemerrorentry_fingerprint; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_systemerrorentry_fingerprint ON public.systemerrorentry USING btree (fingerprint);


--
-- Name: ix_systemerrorentry_is_resolved; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_systemerrorentry_is_resolved ON public.systemerrorentry USING btree (is_resolved);


--
-- Name: ix_systemerrorentry_request_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_systemerrorentry_request_id ON public.systemerrorentry USING btree (request_id);


--
-- Name: ix_systemerrorentry_trace_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_systemerrorentry_trace_id ON public.systemerrorentry USING btree (trace_id);


--
-- Name: ix_systemerrorentry_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_systemerrorentry_user_id ON public.systemerrorentry USING btree (user_id);


--
-- Name: ix_topuporder_status; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_topuporder_status ON public.topuporder USING btree (status);


--
-- Name: ix_topuporder_stripe_checkout_session_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE UNIQUE INDEX ix_topuporder_stripe_checkout_session_id ON public.topuporder USING btree (stripe_checkout_session_id);


--
-- Name: ix_topuporder_stripe_payment_intent_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE UNIQUE INDEX ix_topuporder_stripe_payment_intent_id ON public.topuporder USING btree (stripe_payment_intent_id);


--
-- Name: ix_topuporder_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_topuporder_user_id ON public.topuporder USING btree (user_id);


--
-- Name: ix_topupproduct_code; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE UNIQUE INDEX ix_topupproduct_code ON public.topupproduct USING btree (code);


--
-- Name: ix_upload_file_hash; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_upload_file_hash ON public.upload USING btree (file_hash);


--
-- Name: ix_upload_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_upload_user_id ON public.upload USING btree (user_id);


--
-- Name: ix_usage_ledger_idempotency_key; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_usage_ledger_idempotency_key ON public.usage_ledger USING btree (idempotency_key);


--
-- Name: ix_usage_ledger_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_usage_ledger_user_id ON public.usage_ledger USING btree (user_id);


--
-- Name: ix_usageledger_reference_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_usageledger_reference_id ON public.usageledger USING btree (reference_id);


--
-- Name: ix_usageledger_subscription_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_usageledger_subscription_id ON public.usageledger USING btree (subscription_id);


--
-- Name: ix_usagelog_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_usagelog_user_id ON public.usagelog USING btree (user_id);


--
-- Name: ix_user_email; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE UNIQUE INDEX ix_user_email ON public."user" USING btree (email);


--
-- Name: ix_user_is_internal; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_user_is_internal ON public."user" USING btree (is_internal);


--
-- Name: ix_user_school_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_user_school_id ON public."user" USING btree (school_id);


--
-- Name: ix_user_whatsapp_number; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_user_whatsapp_number ON public."user" USING btree (whatsapp_number);


--
-- Name: ix_userquotaoverride_user_id; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_userquotaoverride_user_id ON public.userquotaoverride USING btree (user_id);


--
-- Name: ix_voiceartifact_created_at; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_voiceartifact_created_at ON public.voiceartifact USING btree (created_at);


--
-- Name: ix_voiceaudio_audio_hash; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_voiceaudio_audio_hash ON public.voiceaudio USING btree (audio_hash);


--
-- Name: ix_voiceaudio_created_at; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_voiceaudio_created_at ON public.voiceaudio USING btree (created_at);


--
-- Name: ix_voiceconfirmation_created_at; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_voiceconfirmation_created_at ON public.voiceconfirmation USING btree (created_at);


--
-- Name: ix_voiceconfirmation_normalized_problem_hash; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_voiceconfirmation_normalized_problem_hash ON public.voiceconfirmation USING btree (normalized_problem_hash);


--
-- Name: ix_voicesession_created_at; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_voicesession_created_at ON public.voicesession USING btree (created_at);


--
-- Name: ix_voicesession_status; Type: INDEX; Schema: public; Owner: uask_user
--

CREATE INDEX ix_voicesession_status ON public.voicesession USING btree (status);


--
-- Name: adminauditlog adminauditlog_admin_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.adminauditlog
    ADD CONSTRAINT adminauditlog_admin_user_id_fkey FOREIGN KEY (admin_user_id) REFERENCES public."user"(id);


--
-- Name: adminnote adminnote_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.adminnote
    ADD CONSTRAINT adminnote_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: billingledger billingledger_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.billingledger
    ADD CONSTRAINT billingledger_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: canonicalsolution canonicalsolution_problem_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.canonicalsolution
    ADD CONSTRAINT canonicalsolution_problem_id_fkey FOREIGN KEY (problem_id) REFERENCES public.canonicalproblem(id);


--
-- Name: chateditcopy chateditcopy_chat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.chateditcopy
    ADD CONSTRAINT chateditcopy_chat_id_fkey FOREIGN KEY (chat_id) REFERENCES public.chatsession(id);


--
-- Name: chateditcopy chateditcopy_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.chateditcopy
    ADD CONSTRAINT chateditcopy_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: chateditcopyv2 chateditcopyv2_chat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.chateditcopyv2
    ADD CONSTRAINT chateditcopyv2_chat_id_fkey FOREIGN KEY (chat_id) REFERENCES public.chatsession(id);


--
-- Name: chateditcopyv2 chateditcopyv2_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.chateditcopyv2
    ADD CONSTRAINT chateditcopyv2_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: chateditnotev2 chateditnotev2_chat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.chateditnotev2
    ADD CONSTRAINT chateditnotev2_chat_id_fkey FOREIGN KEY (chat_id) REFERENCES public.chatsession(id);


--
-- Name: chateditnotev2 chateditnotev2_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.chateditnotev2
    ADD CONSTRAINT chateditnotev2_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: chatmessage chatmessage_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.chatmessage
    ADD CONSTRAINT chatmessage_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.chatsession(id);


--
-- Name: chatnote chatnote_chat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.chatnote
    ADD CONSTRAINT chatnote_chat_id_fkey FOREIGN KEY (chat_id) REFERENCES public.chatsession(id);


--
-- Name: chatnote chatnote_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.chatnote
    ADD CONSTRAINT chatnote_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: chatsession chatsession_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.chatsession
    ADD CONSTRAINT chatsession_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: credit_hold_allocations credit_hold_allocations_hold_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.credit_hold_allocations
    ADD CONSTRAINT credit_hold_allocations_hold_id_fkey FOREIGN KEY (hold_id) REFERENCES public.credit_holds(hold_id);


--
-- Name: credit_hold_allocations credit_hold_allocations_lot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.credit_hold_allocations
    ADD CONSTRAINT credit_hold_allocations_lot_id_fkey FOREIGN KEY (lot_id) REFERENCES public.credit_lots(lot_id);


--
-- Name: credit_holds credit_holds_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.credit_holds
    ADD CONSTRAINT credit_holds_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: credit_lots credit_lots_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.credit_lots
    ADD CONSTRAINT credit_lots_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: credit_transfers credit_transfers_escrow_lot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.credit_transfers
    ADD CONSTRAINT credit_transfers_escrow_lot_id_fkey FOREIGN KEY (escrow_lot_id) REFERENCES public.creditlot(id);


--
-- Name: credit_transfers credit_transfers_recipient_ledger_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.credit_transfers
    ADD CONSTRAINT credit_transfers_recipient_ledger_id_fkey FOREIGN KEY (recipient_ledger_id) REFERENCES public.billingledger(id);


--
-- Name: credit_transfers credit_transfers_recipient_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.credit_transfers
    ADD CONSTRAINT credit_transfers_recipient_user_id_fkey FOREIGN KEY (recipient_user_id) REFERENCES public."user"(id);


--
-- Name: credit_transfers credit_transfers_refund_ledger_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.credit_transfers
    ADD CONSTRAINT credit_transfers_refund_ledger_id_fkey FOREIGN KEY (refund_ledger_id) REFERENCES public.billingledger(id);


--
-- Name: credit_transfers credit_transfers_sender_ledger_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.credit_transfers
    ADD CONSTRAINT credit_transfers_sender_ledger_id_fkey FOREIGN KEY (sender_ledger_id) REFERENCES public.billingledger(id);


--
-- Name: credit_transfers credit_transfers_sender_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.credit_transfers
    ADD CONSTRAINT credit_transfers_sender_user_id_fkey FOREIGN KEY (sender_user_id) REFERENCES public."user"(id);


--
-- Name: credithold credithold_subscription_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.credithold
    ADD CONSTRAINT credithold_subscription_id_fkey FOREIGN KEY (subscription_id) REFERENCES public.subscription(id);


--
-- Name: credithold credithold_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.credithold
    ADD CONSTRAINT credithold_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: creditlot creditlot_subscription_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.creditlot
    ADD CONSTRAINT creditlot_subscription_id_fkey FOREIGN KEY (subscription_id) REFERENCES public.subscription(id);


--
-- Name: creditlot creditlot_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.creditlot
    ADD CONSTRAINT creditlot_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: creditlotconsumption creditlotconsumption_credit_lot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.creditlotconsumption
    ADD CONSTRAINT creditlotconsumption_credit_lot_id_fkey FOREIGN KEY (credit_lot_id) REFERENCES public.creditlot(id);


--
-- Name: creditlotconsumption creditlotconsumption_subscription_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.creditlotconsumption
    ADD CONSTRAINT creditlotconsumption_subscription_id_fkey FOREIGN KEY (subscription_id) REFERENCES public.subscription(id);


--
-- Name: creditlotconsumption creditlotconsumption_usage_ledger_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.creditlotconsumption
    ADD CONSTRAINT creditlotconsumption_usage_ledger_id_fkey FOREIGN KEY (usage_ledger_id) REFERENCES public.usageledger(id);


--
-- Name: creditlotconsumption creditlotconsumption_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.creditlotconsumption
    ADD CONSTRAINT creditlotconsumption_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: creditprogramdefinition creditprogramdefinition_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.creditprogramdefinition
    ADD CONSTRAINT creditprogramdefinition_created_by_fkey FOREIGN KEY (created_by) REFERENCES public."user"(id);


--
-- Name: creditprogramenrollment creditprogramenrollment_program_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.creditprogramenrollment
    ADD CONSTRAINT creditprogramenrollment_program_id_fkey FOREIGN KEY (program_id) REFERENCES public.creditprogramdefinition(id);


--
-- Name: creditprogramenrollment creditprogramenrollment_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.creditprogramenrollment
    ADD CONSTRAINT creditprogramenrollment_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: creditprogramgrantlog creditprogramgrantlog_credit_lot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.creditprogramgrantlog
    ADD CONSTRAINT creditprogramgrantlog_credit_lot_id_fkey FOREIGN KEY (credit_lot_id) REFERENCES public.creditlot(id);


--
-- Name: creditprogramgrantlog creditprogramgrantlog_enrollment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.creditprogramgrantlog
    ADD CONSTRAINT creditprogramgrantlog_enrollment_id_fkey FOREIGN KEY (enrollment_id) REFERENCES public.creditprogramenrollment(id);


--
-- Name: creditprogramgrantlog creditprogramgrantlog_program_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.creditprogramgrantlog
    ADD CONSTRAINT creditprogramgrantlog_program_id_fkey FOREIGN KEY (program_id) REFERENCES public.creditprogramdefinition(id);


--
-- Name: creditprogramgrantlog creditprogramgrantlog_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.creditprogramgrantlog
    ADD CONSTRAINT creditprogramgrantlog_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: crop crop_upload_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.crop
    ADD CONSTRAINT crop_upload_id_fkey FOREIGN KEY (upload_id) REFERENCES public.upload(id);


--
-- Name: followupchatturn followupchatturn_solve_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.followupchatturn
    ADD CONSTRAINT followupchatturn_solve_session_id_fkey FOREIGN KEY (solve_session_id) REFERENCES public.solvesession(id);


--
-- Name: followupchatturn followupchatturn_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.followupchatturn
    ADD CONSTRAINT followupchatturn_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: invoice invoice_subscription_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.invoice
    ADD CONSTRAINT invoice_subscription_id_fkey FOREIGN KEY (subscription_id) REFERENCES public.subscription(id);


--
-- Name: invoice invoice_topup_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.invoice
    ADD CONSTRAINT invoice_topup_order_id_fkey FOREIGN KEY (topup_order_id) REFERENCES public.topuporder(id);


--
-- Name: invoice invoice_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.invoice
    ADD CONSTRAINT invoice_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: invoicelineitem invoicelineitem_billing_ledger_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.invoicelineitem
    ADD CONSTRAINT invoicelineitem_billing_ledger_id_fkey FOREIGN KEY (billing_ledger_id) REFERENCES public.billingledger(id);


--
-- Name: invoicelineitem invoicelineitem_invoice_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.invoicelineitem
    ADD CONSTRAINT invoicelineitem_invoice_id_fkey FOREIGN KEY (invoice_id) REFERENCES public.invoice(id);


--
-- Name: invoicelineitem invoicelineitem_payment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.invoicelineitem
    ADD CONSTRAINT invoicelineitem_payment_id_fkey FOREIGN KEY (payment_id) REFERENCES public.payment(id);


--
-- Name: legal_acceptances legal_acceptances_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.legal_acceptances
    ADD CONSTRAINT legal_acceptances_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: llmusageledger llmusageledger_followup_turn_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.llmusageledger
    ADD CONSTRAINT llmusageledger_followup_turn_id_fkey FOREIGN KEY (followup_turn_id) REFERENCES public.followupchatturn(id);


--
-- Name: llmusageledger llmusageledger_solve_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.llmusageledger
    ADD CONSTRAINT llmusageledger_solve_session_id_fkey FOREIGN KEY (solve_session_id) REFERENCES public.solvesession(id);


--
-- Name: notifications notifications_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: ocrartifact ocrartifact_crop_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.ocrartifact
    ADD CONSTRAINT ocrartifact_crop_id_fkey FOREIGN KEY (crop_id) REFERENCES public.crop(id);


--
-- Name: ocrartifact ocrartifact_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.ocrartifact
    ADD CONSTRAINT ocrartifact_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.ocrjob(id);


--
-- Name: ocrauditevent ocrauditevent_artifact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.ocrauditevent
    ADD CONSTRAINT ocrauditevent_artifact_id_fkey FOREIGN KEY (artifact_id) REFERENCES public.ocrartifact(id);


--
-- Name: ocrauditevent ocrauditevent_crop_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.ocrauditevent
    ADD CONSTRAINT ocrauditevent_crop_id_fkey FOREIGN KEY (crop_id) REFERENCES public.crop(id);


--
-- Name: ocrauditevent ocrauditevent_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.ocrauditevent
    ADD CONSTRAINT ocrauditevent_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.ocrjob(id);


--
-- Name: ocrauditevent ocrauditevent_upload_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.ocrauditevent
    ADD CONSTRAINT ocrauditevent_upload_id_fkey FOREIGN KEY (upload_id) REFERENCES public.upload(id);


--
-- Name: ocrauditevent ocrauditevent_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.ocrauditevent
    ADD CONSTRAINT ocrauditevent_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: ocrchoice ocrchoice_question_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.ocrchoice
    ADD CONSTRAINT ocrchoice_question_id_fkey FOREIGN KEY (question_id) REFERENCES public.ocrquestion(id);


--
-- Name: ocrconfirmation ocrconfirmation_artifact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.ocrconfirmation
    ADD CONSTRAINT ocrconfirmation_artifact_id_fkey FOREIGN KEY (artifact_id) REFERENCES public.ocrartifact(id);


--
-- Name: ocrconfirmation ocrconfirmation_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.ocrconfirmation
    ADD CONSTRAINT ocrconfirmation_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: ocrfigure ocrfigure_artifact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.ocrfigure
    ADD CONSTRAINT ocrfigure_artifact_id_fkey FOREIGN KEY (artifact_id) REFERENCES public.ocrartifact(id);


--
-- Name: ocrjob ocrjob_crop_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.ocrjob
    ADD CONSTRAINT ocrjob_crop_id_fkey FOREIGN KEY (crop_id) REFERENCES public.crop(id);


--
-- Name: ocrjob ocrjob_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.ocrjob
    ADD CONSTRAINT ocrjob_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: ocrquestion ocrquestion_artifact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.ocrquestion
    ADD CONSTRAINT ocrquestion_artifact_id_fkey FOREIGN KEY (artifact_id) REFERENCES public.ocrartifact(id);


--
-- Name: payment payment_subscription_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.payment
    ADD CONSTRAINT payment_subscription_id_fkey FOREIGN KEY (subscription_id) REFERENCES public.subscription(id);


--
-- Name: payment payment_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.payment
    ADD CONSTRAINT payment_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: providerpricingauditevent providerpricingauditevent_admin_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.providerpricingauditevent
    ADD CONSTRAINT providerpricingauditevent_admin_user_id_fkey FOREIGN KEY (admin_user_id) REFERENCES public."user"(id);


--
-- Name: providerpricingauditevent providerpricingauditevent_provider_model_pricing_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.providerpricingauditevent
    ADD CONSTRAINT providerpricingauditevent_provider_model_pricing_id_fkey FOREIGN KEY (provider_model_pricing_id) REFERENCES public.providermodelpricing(id);


--
-- Name: reconciliationrecord reconciliationrecord_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.reconciliationrecord
    ADD CONSTRAINT reconciliationrecord_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: solution_shares solution_shares_owner_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.solution_shares
    ADD CONSTRAINT solution_shares_owner_user_id_fkey FOREIGN KEY (owner_user_id) REFERENCES public."user"(id);


--
-- Name: solution_shares solution_shares_solver_output_attempt_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.solution_shares
    ADD CONSTRAINT solution_shares_solver_output_attempt_id_fkey FOREIGN KEY (solver_output_attempt_id) REFERENCES public.solveroutputattempt(id);


--
-- Name: solveroutputattempt solveroutputattempt_message_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.solveroutputattempt
    ADD CONSTRAINT solveroutputattempt_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.chatmessage(id);


--
-- Name: solveroutputattempt solveroutputattempt_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.solveroutputattempt
    ADD CONSTRAINT solveroutputattempt_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.chatsession(id);


--
-- Name: solveroutputattempt solveroutputattempt_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.solveroutputattempt
    ADD CONSTRAINT solveroutputattempt_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: solvesession solvesession_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.solvesession
    ADD CONSTRAINT solvesession_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: subscription subscription_plan_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.subscription
    ADD CONSTRAINT subscription_plan_id_fkey FOREIGN KEY (plan_id) REFERENCES public.plan(id);


--
-- Name: subscription subscription_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.subscription
    ADD CONSTRAINT subscription_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: subscriptionbillinglink subscriptionbillinglink_subscription_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.subscriptionbillinglink
    ADD CONSTRAINT subscriptionbillinglink_subscription_id_fkey FOREIGN KEY (subscription_id) REFERENCES public.subscription(id);


--
-- Name: subscriptionbillinglink subscriptionbillinglink_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.subscriptionbillinglink
    ADD CONSTRAINT subscriptionbillinglink_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: subscriptionperiod subscriptionperiod_grant_lot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.subscriptionperiod
    ADD CONSTRAINT subscriptionperiod_grant_lot_id_fkey FOREIGN KEY (grant_lot_id) REFERENCES public.creditlot(id);


--
-- Name: subscriptionperiod subscriptionperiod_subscription_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.subscriptionperiod
    ADD CONSTRAINT subscriptionperiod_subscription_id_fkey FOREIGN KEY (subscription_id) REFERENCES public.subscription(id);


--
-- Name: systemconfigversion systemconfigversion_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.systemconfigversion
    ADD CONSTRAINT systemconfigversion_created_by_fkey FOREIGN KEY (created_by) REFERENCES public."user"(id);


--
-- Name: topuporder topuporder_topup_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.topuporder
    ADD CONSTRAINT topuporder_topup_product_id_fkey FOREIGN KEY (topup_product_id) REFERENCES public.topupproduct(id);


--
-- Name: topuporder topuporder_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.topuporder
    ADD CONSTRAINT topuporder_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: upload upload_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.upload
    ADD CONSTRAINT upload_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: usage_ledger usage_ledger_hold_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.usage_ledger
    ADD CONSTRAINT usage_ledger_hold_id_fkey FOREIGN KEY (hold_id) REFERENCES public.credit_holds(hold_id);


--
-- Name: usage_ledger usage_ledger_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.usage_ledger
    ADD CONSTRAINT usage_ledger_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: usageledger usageledger_subscription_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.usageledger
    ADD CONSTRAINT usageledger_subscription_id_fkey FOREIGN KEY (subscription_id) REFERENCES public.subscription(id);


--
-- Name: usagelog usagelog_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.usagelog
    ADD CONSTRAINT usagelog_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: user user_school_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_school_id_fkey FOREIGN KEY (school_id) REFERENCES public.school(id);


--
-- Name: userquotaoverride userquotaoverride_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.userquotaoverride
    ADD CONSTRAINT userquotaoverride_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: usersavedsolution usersavedsolution_solution_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.usersavedsolution
    ADD CONSTRAINT usersavedsolution_solution_id_fkey FOREIGN KEY (solution_id) REFERENCES public.canonicalsolution(id);


--
-- Name: usersavedsolution usersavedsolution_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.usersavedsolution
    ADD CONSTRAINT usersavedsolution_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: voiceartifact voiceartifact_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.voiceartifact
    ADD CONSTRAINT voiceartifact_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.voicejob(id);


--
-- Name: voiceaudio voiceaudio_voice_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.voiceaudio
    ADD CONSTRAINT voiceaudio_voice_session_id_fkey FOREIGN KEY (voice_session_id) REFERENCES public.voicesession(id);


--
-- Name: voiceconfirmation voiceconfirmation_artifact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.voiceconfirmation
    ADD CONSTRAINT voiceconfirmation_artifact_id_fkey FOREIGN KEY (artifact_id) REFERENCES public.voiceartifact(id);


--
-- Name: voiceconfirmation voiceconfirmation_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.voiceconfirmation
    ADD CONSTRAINT voiceconfirmation_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: voicejob voicejob_audio_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.voicejob
    ADD CONSTRAINT voicejob_audio_id_fkey FOREIGN KEY (audio_id) REFERENCES public.voiceaudio(id);


--
-- Name: voicejob voicejob_voice_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.voicejob
    ADD CONSTRAINT voicejob_voice_session_id_fkey FOREIGN KEY (voice_session_id) REFERENCES public.voicesession(id);


--
-- Name: voicesession voicesession_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: uask_user
--

ALTER TABLE ONLY public.voicesession
    ADD CONSTRAINT voicesession_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- PostgreSQL database dump complete
--

\unrestrict whhN33j0yH2v0nErTWPQbUFGkfGYaWvg8Rb7KNfE5Nl9U30a55Iluz0OiQsXVx3

