-- Run only in a fresh disposable lab database as its administrator.
-- Prerequisite: dedicated mcp_analyst LOGIN with no elevated role memberships.
BEGIN;
CREATE SCHEMA mcp_lab;
CREATE TABLE mcp_lab.sales_lines (
    line_id integer PRIMARY KEY, order_id integer NOT NULL, day date NOT NULL,
    category text NOT NULL, cents bigint NOT NULL CHECK (cents >= 0)
);
INSERT INTO mcp_lab.sales_lines VALUES
    (1, 101, '2026-01-01', 'Books', 1200),
    (2, 101, '2026-01-01', 'Games', 800),
    (3, 102, '2026-01-02', 'Books', 300);
CREATE TABLE mcp_lab.restricted_fixture (id integer PRIMARY KEY);
REVOKE ALL ON SCHEMA mcp_lab FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA mcp_lab FROM PUBLIC;
GRANT USAGE ON SCHEMA mcp_lab TO mcp_analyst;
GRANT SELECT ON mcp_lab.sales_lines TO mcp_analyst;
COMMIT;
