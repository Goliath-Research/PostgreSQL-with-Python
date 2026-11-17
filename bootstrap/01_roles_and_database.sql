-- =============================================================================
-- Bootstrap Step 1: Role Hierarchy and Database Access Boundary
-- File: bootstrap/01_roles_and_database.sql
--
-- Role Model:
--   course_owner    (NOLOGIN) : Owns course schemas (`commerce`, `lab`) and objects
--   course_migrator (LOGIN)   : Performs controlled DDL by assuming `course_owner`
--   course_app      (LOGIN)   : Executes permitted application reads and writes
--   course_analyst  (LOGIN)   : Executes read-only analytical queries (DuckDB)
-- =============================================================================

\set ON_ERROR_STOP on

DO $$
DECLARE
    v_migrator_pw text := COALESCE(NULLIF(current_setting('course.migrator_password', true), ''), 'lab_migrator_pw_change_me');
    v_app_pw      text := COALESCE(NULLIF(current_setting('course.app_password', true), ''),      'lab_app_pw_change_me');
    v_analyst_pw  text := COALESCE(NULLIF(current_setting('course.analyst_password', true), ''),  'lab_analyst_pw_change_me');
BEGIN
    -- 1. Object-owning role (no direct login permitted)
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'course_owner') THEN
        CREATE ROLE course_owner
            NOLOGIN
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOREPLICATION
            NOBYPASSRLS;
    END IF;

    -- 2. Controlled migration role (login enabled; NOINHERIT requires explicit `SET ROLE course_owner`)
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'course_migrator') THEN
        EXECUTE format(
            'CREATE ROLE course_migrator LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT',
            v_migrator_pw
        );
    ELSE
        EXECUTE format('ALTER ROLE course_migrator WITH LOGIN PASSWORD %L NOINHERIT', v_migrator_pw);
    END IF;

    -- 3. Application runtime role (transactional read/write on permitted tables only)
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'course_app') THEN
        EXECUTE format(
            'CREATE ROLE course_app LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS',
            v_app_pw
        );
    ELSE
        EXECUTE format('ALTER ROLE course_app WITH LOGIN PASSWORD %L', v_app_pw);
    END IF;

    -- 4. Analytical role (read-only access for DuckDB 2.0 and reporting)
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'course_analyst') THEN
        EXECUTE format(
            'CREATE ROLE course_analyst LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS',
            v_analyst_pw
        );
    ELSE
        EXECUTE format('ALTER ROLE course_analyst WITH LOGIN PASSWORD %L', v_analyst_pw);
    END IF;
END
$$;

-- Allow course_migrator to assume course_owner explicitly during migrations
GRANT course_owner TO course_migrator;

-- Transfer database ownership to course_owner and tighten database-level privileges
ALTER DATABASE goliath_ecommerce OWNER TO course_owner;
REVOKE ALL ON DATABASE goliath_ecommerce FROM PUBLIC;

GRANT CONNECT, TEMPORARY ON DATABASE goliath_ecommerce TO course_migrator;
GRANT CONNECT ON DATABASE goliath_ecommerce TO course_app;
GRANT CONNECT ON DATABASE goliath_ecommerce TO course_analyst;

-- Harden the default `public` schema so ordinary roles cannot create untrusted objects there
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
