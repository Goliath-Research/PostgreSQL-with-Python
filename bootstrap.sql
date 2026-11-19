-- =============================================================================
-- PostgreSQL with Python: Advanced Relational Databases
-- Module 1 One-Time Provisioning Script (bootstrap.sql)
--
-- Usage (run as an administrative PostgreSQL superuser via psql):
--   psql -v ON_ERROR_STOP=1 -U postgres -d goliath_ecommerce -f bootstrap.sql
-- =============================================================================

\set ON_ERROR_STOP on

\ir bootstrap/01_roles_and_database.sql
\ir bootstrap/02_schemas_and_probe.sql
