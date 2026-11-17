-- =============================================================================
-- Bootstrap Step 2: Namespaces, Default Privileges, and Diagnostic Probe Table
-- File: bootstrap/02_schemas_and_probe.sql
--
-- Creates:
--   Schema `commerce` : Target namespace for the e-commerce migration in Module 2
--   Schema `lab`      : Diagnostic namespace for Module 1 readiness verification
--   Table  `lab.connection_probe` : Small disposable diagnostic table
-- =============================================================================

\set ON_ERROR_STOP on

-- Create schemas and diagnostic objects as `course_owner` so the bootstrap superuser
-- does not remain the owner of course relations.
SET ROLE course_owner;

CREATE SCHEMA IF NOT EXISTS commerce AUTHORIZATION course_owner;
CREATE SCHEMA IF NOT EXISTS lab AUTHORIZATION course_owner;

-- Lock down default PUBLIC access on both schemas
REVOKE ALL ON SCHEMA commerce FROM PUBLIC;
REVOKE ALL ON SCHEMA lab FROM PUBLIC;

-- Schema-level USAGE vs. CREATE separation:
-- * `course_migrator` can inspect schemas and must `SET ROLE course_owner` to create/alter objects.
-- * `course_app` and `course_analyst` receive USAGE on `lab` (and `commerce` for namespace visibility),
--   but NEVER receive CREATE on either schema.
GRANT USAGE ON SCHEMA lab TO course_migrator, course_app, course_analyst;
GRANT USAGE ON SCHEMA commerce TO course_migrator, course_app, course_analyst;

-- Configure default privileges for future objects created by `course_owner` in `lab`.
-- Note: Module 2 configures explicit grants and default privileges for `commerce` during migration.
ALTER DEFAULT PRIVILEGES FOR ROLE course_owner IN SCHEMA lab
    GRANT SELECT, INSERT ON TABLES TO course_app;

ALTER DEFAULT PRIVILEGES FOR ROLE course_owner IN SCHEMA lab
    GRANT USAGE, SELECT ON SEQUENCES TO course_app;

ALTER DEFAULT PRIVILEGES FOR ROLE course_owner IN SCHEMA lab
    GRANT SELECT ON TABLES TO course_analyst;

-- Create the disposable Module 1 diagnostic table owned by `course_owner`
CREATE TABLE IF NOT EXISTS lab.connection_probe (
    probe_id    INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_role  TEXT NOT NULL DEFAULT current_user,
    probe_note  TEXT NOT NULL CHECK (length(btrim(probe_note)) > 0),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- Explicit object-level privileges on `lab.connection_probe`
REVOKE ALL ON TABLE lab.connection_probe FROM PUBLIC;
GRANT SELECT, INSERT ON TABLE lab.connection_probe TO course_app;
GRANT USAGE, SELECT ON SEQUENCE lab.connection_probe_probe_id_seq TO course_app;
GRANT SELECT ON TABLE lab.connection_probe TO course_analyst;

-- Seed one idempotent bootstrap verification row if the table is empty
INSERT INTO lab.connection_probe (actor_role, probe_note)
SELECT 'course_owner', 'Initial bootstrap probe record'
WHERE NOT EXISTS (
    SELECT 1 FROM lab.connection_probe WHERE probe_note = 'Initial bootstrap probe record'
);

RESET ROLE;

-- Set deliberate role-level search_path defaults (students still practice explicit schema qualification)
ALTER ROLE course_migrator IN DATABASE goliath_ecommerce SET search_path = commerce, lab;
ALTER ROLE course_app IN DATABASE goliath_ecommerce SET search_path = commerce, lab;
ALTER ROLE course_analyst IN DATABASE goliath_ecommerce SET search_path = commerce, lab;
