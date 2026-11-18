"""Explicitly authorized, synthetic PostgreSQL transaction exercises.

Nothing connects or writes at import time. Approvals are process-local, bound to the
complete configuration and one action: ``provision``, ``run:<name>``, or
``cleanup:<UUID>``. Run IDs identify only this module's synthetic rows.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import psycopg
from dotenv import dotenv_values


_KEY = secrets.token_bytes(32)
_NAMES = ("commit_rollback", "savepoints", "isolation", "locking", "serializable")
_TABLES = {
    "customers": {"customer_id": "bigint", "email": "text", "customer_name": "text"},
    "products": {"sku": "text", "product_name": "text", "category": "text"},
    "warehouses": {"warehouse_code": "text", "warehouse_city": "text"},
    "orders": {"order_id": "text", "ordered_at": "timestamp(0) without time zone",
               "order_status": "text", "customer_id": "bigint",
               "shipping_address_snapshot": "text"},
    "order_items": {"order_item_id": "bigint", "order_id": "text", "line_no": "bigint",
                    "sku": "text", "warehouse_code": "text", "unit_price_cents": "bigint",
                    "quantity": "bigint"},
    "catalog_observations": {"observation_id": "bigint", "sku": "text",
                             "warehouse_code": "text", "observed_price_cents": "bigint",
                             "observed_quantity": "bigint"},
}
_REL = "lab.module_03_txn_rows"


class LabError(Exception):
    """A deliberately non-diagnostic error suitable for display in a notebook."""


class _CommitOutcomeUnknown(Exception):
    pass


@dataclass(frozen=True)
class Config:
    host: str
    port: int
    database: str
    migrator_password: str = field(repr=False)
    app_password: str = field(repr=False)
    analyst_password: str = field(repr=False)
    timeout: int = 5

    @classmethod
    def load(cls, path: str | os.PathLike = ".env") -> "Config":
        try:
            values = dotenv_values(Path(path), interpolate=False)
            keys = ("PGHOST", "PGPORT", "PGDATABASE", "PGCONNECT_TIMEOUT",
                    "COURSE_MIGRATOR_USER", "COURSE_MIGRATOR_PASSWORD", "COURSE_APP_USER",
                    "COURSE_APP_PASSWORD", "COURSE_ANALYST_USER", "COURSE_ANALYST_PASSWORD")
            data = {key: os.environ[key] if key in os.environ else values.get(key) for key in keys}
            for key, expected in (("COURSE_MIGRATOR_USER", "course_migrator"),
                                  ("COURSE_APP_USER", "course_app"),
                                  ("COURSE_ANALYST_USER", "course_analyst")):
                if data[key] != expected:
                    raise ValueError
            if not all(data[k] for k in ("PGHOST", "PGPORT", "PGDATABASE",
                                         "COURSE_MIGRATOR_PASSWORD", "COURSE_APP_PASSWORD",
                                         "COURSE_ANALYST_PASSWORD")):
                raise ValueError
            port, timeout = int(data["PGPORT"]), int(data["PGCONNECT_TIMEOUT"] or "5")
            if not 1 <= port <= 65535 or not 1 <= timeout <= 30:
                raise ValueError
            return cls(data["PGHOST"], port, data["PGDATABASE"],
                       data["COURSE_MIGRATOR_PASSWORD"], data["COURSE_APP_PASSWORD"],
                       data["COURSE_ANALYST_PASSWORD"], timeout)
        except Exception:
            raise LabError("Invalid configuration.") from None


@dataclass(frozen=True)
class Approval:
    action: str
    _signature: str = field(repr=False)


def _validate_action(action: str) -> None:
    if action == "provision" or action in {f"run:{n}" for n in _NAMES}:
        return
    if action.startswith("cleanup:"):
        try:
            value = action.removeprefix("cleanup:")
            if str(uuid.UUID(value)) == value:
                return
        except (ValueError, AttributeError):
            pass
    raise LabError("Invalid action.")


def _signature(config: Config, action: str) -> str:
    payload = json.dumps([config.host, config.port, config.database, config.timeout,
                          config.migrator_password, config.app_password,
                          config.analyst_password, action], ensure_ascii=True)
    return hmac.new(_KEY, payload.encode(), hashlib.sha256).hexdigest()


def authorize(config: Config, action: str) -> Approval:
    """Create an approval for one explicit action, without connecting."""
    if not isinstance(config, Config) or not isinstance(action, str):
        raise LabError("Invalid action.")
    _validate_action(action)
    return Approval(action, _signature(config, action))


def _guard(config: Config, approval: Approval, action: str) -> None:
    if (not isinstance(config, Config) or not isinstance(approval, Approval)
            or approval.action != action
            or not hmac.compare_digest(approval._signature, _signature(config, action))):
        raise LabError("Authorization required.")


def _connect(config: Config, role: str):
    passwords = {"course_migrator": config.migrator_password, "course_app": config.app_password,
                 "course_analyst": config.analyst_password}
    return psycopg.connect(host=config.host, port=config.port, dbname=config.database,
                           user=role, **{"password": passwords[role]}, connect_timeout=config.timeout,
                           options="-c statement_timeout=5000 -c lock_timeout=4000 -c search_path=pg_catalog")


def _commit(conn):
    try:
        conn.commit()
    except psycopg.OperationalError as error:
        if not error.sqlstate or error.sqlstate.startswith(("08", "57")):
            raise _CommitOutcomeUnknown from None
        raise


@contextmanager
def _session(config, role):
    conn = _connect(config, role)
    try:
        try:
            yield conn
        except BaseException:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        else:
            if conn.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
                _commit(conn)
    finally:
        conn.close()


_SQLSTATES = {
    "42501": "permission_denied",
    "57014": "statement_timeout_or_cancelled",
    "55P03": "lock_unavailable_or_timeout",
    "40P01": "deadlock",
    "40001": "serialization_failure",
    "23505": "unique_violation",
    "42P07": "object_already_exists",
    "42P01": "object_missing",
    "08001": "connection_failed",
    "28P01": "authentication_failed",
    "3D000": "database_missing",
}


def _failure(error: Exception) -> dict:
    if isinstance(error, _CommitOutcomeUnknown):
        return {"error": "commit_outcome_unknown"}
    state = getattr(error, "sqlstate", None)
    if state in _SQLSTATES:
        return {"error": _SQLSTATES[state], "sqlstate": state}
    if isinstance(error, psycopg.OperationalError):
        return {"error": "connection_failed"}
    return {"error": "verification_failed"}


def _retry_serialization(error: Exception, attempt: int, limit: int = 3) -> bool:
    """Only a confirmed server serialization failure permits a complete retry."""
    return (isinstance(error, psycopg.Error) and error.sqlstate == "40001"
            and 0 <= attempt < limit - 1)


def preflight(config: Config) -> dict:
    """Read-only identity, PostgreSQL 18, ownership, schema and privilege checks."""
    check = "database"
    try:
        if config.database != "goliath_ecommerce":
            raise ValueError
        for role in ("course_migrator", "course_app", "course_analyst"):
            check = role
            with _session(config, role) as conn:
                conn.execute("SET TRANSACTION READ ONLY")
                version, database, session, current, safe = conn.execute(
                    """SELECT current_setting('server_version_num')::int, current_database(),
                              session_user, current_user,
                              NOT (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)
                       FROM pg_catalog.pg_roles WHERE rolname = current_user"""
                ).fetchone()
                if not (180000 <= version < 190000 and database == config.database
                        and session == current == role and safe):
                    raise ValueError
                inherit, owner_member, migrator_member = conn.execute(
                    """SELECT rolinherit, pg_has_role(current_user,'course_owner','MEMBER'),
                              pg_has_role(current_user,'course_migrator','MEMBER')
                       FROM pg_roles WHERE rolname=current_user"""
                ).fetchone()
                if role == "course_migrator":
                    if inherit or not owner_member:
                        raise ValueError
                elif owner_member or migrator_member:
                    raise ValueError
                owner, owner_safe, can_set = conn.execute(
                    """SELECT pg_get_userbyid(n.nspowner), NOT (r.rolcanlogin OR r.rolsuper
                           OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls),
                           pg_has_role('course_migrator','course_owner','SET')
                       FROM pg_namespace n JOIN pg_roles r ON r.oid=n.nspowner
                       WHERE n.nspname='lab'"""
                ).fetchone()
                if (owner, owner_safe, can_set) != ("course_owner", True, True):
                    raise ValueError
                if not conn.execute("SELECT has_schema_privilege(current_user,'lab','USAGE') "
                                    "AND has_schema_privilege(current_user,'commerce','USAGE')").fetchone()[0]:
                    raise ValueError
                if role != "course_migrator" and conn.execute(
                    "SELECT has_schema_privilege(current_user,'lab','CREATE') OR "
                    "has_schema_privilege(current_user,'commerce','CREATE')"
                ).fetchone()[0]:
                    raise ValueError
                columns = conn.execute(
                    """SELECT c.relname, a.attname, pg_catalog.format_type(a.atttypid,a.atttypmod)
                       FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
                       JOIN pg_catalog.pg_attribute a ON a.attrelid=c.oid
                       WHERE n.nspname='commerce' AND c.relname = ANY(%s)
                         AND c.relkind='r' AND pg_get_userbyid(c.relowner)='course_owner'
                         AND NOT c.relispartition AND a.attnum>0 AND NOT a.attisdropped""",
                    (list(_TABLES),),
                ).fetchall()
                actual = {name: {} for name in _TABLES}
                for table, column, typ in columns:
                    actual[table][column] = typ
                if actual != _TABLES:
                    raise ValueError
                for table in _TABLES:
                    relation = "commerce." + table
                    if role == "course_app":
                        privileges = ("SELECT", "INSERT", "UPDATE", "DELETE")
                    else:
                        privileges = ("SELECT",)
                    if role != "course_migrator":
                        for privilege in privileges:
                            if not conn.execute("SELECT has_table_privilege(current_user,%s,%s)",
                                                (relation, privilege)).fetchone()[0]:
                                raise ValueError
                    if role == "course_analyst":
                        for privilege in ("INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                            if conn.execute("SELECT has_table_privilege(current_user,%s,%s)",
                                            (relation, privilege)).fetchone()[0]:
                                raise ValueError
        return {"ok": True, "checks": "PostgreSQL 18, identities, ownership, commerce schema and access"}
    except Exception as error:
        return {"ok": False, "check": check, **_failure(error)}


def _require_preflight(config: Config) -> None:
    result = preflight(config)
    if not result["ok"]:
        raise LabError("Preflight failed: " + result["error"] + ".")


def read_sql_examples(config: Config) -> dict:
    """Run fixed read-only examples; commerce contributes aggregate counts only.

    The timezone conversion uses a hypothetical literal, not a commerce timestamp.
    No approval is needed because both the preflight and transaction are read-only.
    """
    _require_preflight(config)
    try:
        with _session(config, "course_analyst") as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            scalar = conn.execute(
                """SELECT pg_typeof(1)::text, NULL::integer IS NULL, NULL::integer = NULL::integer,
                          5 / 2, (5::numeric / 2)::numeric(4,1)::text,
                          ('2024-01-15 12:00:00'::timestamp AT TIME ZONE 'America/New_York')
                              AT TIME ZONE 'UTC'"""
            ).fetchone()
            counts = conn.execute(
                """WITH per_order AS (
                       SELECT order_id, count(*) AS lines,
                              count(*) FILTER (WHERE unit_price_cents > 0) AS positive,
                              sum(unit_price_cents::numeric * quantity) AS total_cents
                       FROM commerce.order_items GROUP BY order_id
                   ), ranked AS (
                       SELECT lines, positive,
                              row_number() OVER (ORDER BY total_cents, order_id) AS position
                       FROM per_order
                   )
                   SELECT count(*), coalesce(sum(lines),0)::bigint,
                          coalesce(sum(positive),0)::bigint, coalesce(max(position),0)
                   FROM ranked"""
            ).fetchone()
        return {"ok": True, "integer_type": scalar[0], "null_is_null": scalar[1],
                "null_equals_null": scalar[2], "integer_division": scalar[3],
                "numeric_division": scalar[4],
                "hypothetical_new_york_noon_utc": scalar[5].isoformat(),
                "orders_with_items": counts[0], "order_item_count": counts[1],
                "positive_price_count": counts[2], "ranked_order_count": counts[3]}
    except Exception as error:
        raise LabError("Read-only examples failed: " + _failure(error)["error"] + ".") from None


def _verify_table(conn) -> None:
    row = conn.execute(
        """SELECT c.relkind, pg_get_userbyid(c.relowner), c.relrowsecurity,
                  c.relforcerowsecurity, c.relispartition
           FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
           WHERE n.nspname='lab' AND c.relname='module_03_txn_rows'"""
    ).fetchone()
    if row != ("r", "course_owner", False, False, False):
        raise ValueError
    columns = conn.execute(
        """SELECT a.attname, format_type(a.atttypid,a.atttypmod), a.attnotnull,
                  a.attidentity, a.attgenerated, a.atthasdef
           FROM pg_attribute a WHERE a.attrelid='lab.module_03_txn_rows'::regclass
           AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum"""
    ).fetchall()
    if columns != [("run_id", "uuid", True, "", "", False),
                   ("slot", "integer", True, "", "", False),
                   ("value", "integer", True, "", "", False)]:
        raise ValueError
    constraints = conn.execute(
        """SELECT contype, pg_get_constraintdef(oid) FROM pg_constraint
           WHERE conrelid='lab.module_03_txn_rows'::regclass"""
    ).fetchall()
    if set(constraints) != {("p", "PRIMARY KEY (run_id, slot)"),
                            ("n", "NOT NULL run_id"), ("n", "NOT NULL slot"),
                            ("n", "NOT NULL value")}:
        raise ValueError
    if conn.execute(
        """SELECT EXISTS(SELECT 1 FROM pg_trigger WHERE tgrelid='lab.module_03_txn_rows'::regclass
                         AND NOT tgisinternal)
                  OR EXISTS(SELECT 1 FROM pg_inherits WHERE inhparent='lab.module_03_txn_rows'::regclass
                            OR inhrelid='lab.module_03_txn_rows'::regclass)
                  OR EXISTS(SELECT 1 FROM pg_rewrite WHERE ev_class='lab.module_03_txn_rows'::regclass)
                  OR EXISTS(SELECT 1 FROM pg_constraint WHERE confrelid='lab.module_03_txn_rows'::regclass)
                  OR (SELECT count(*) FROM pg_index WHERE indrelid='lab.module_03_txn_rows'::regclass) <> 1"""
    ).fetchone()[0]:
        raise ValueError
    for role, required, forbidden in (
        ("course_app", ("SELECT", "INSERT", "UPDATE", "DELETE"), ("TRUNCATE",)),
        ("course_analyst", ("SELECT",), ("INSERT", "UPDATE", "DELETE", "TRUNCATE")),
    ):
        for privilege in required + forbidden:
            present = conn.execute("SELECT has_table_privilege(%s,%s,%s)",
                                   (role, _REL, privilege)).fetchone()[0]
            if present != (privilege in required):
                raise ValueError


def provision(config: Config, approval: Approval) -> dict:
    """Create the fixed lab table, refusing any pre-existing object with its name."""
    _guard(config, approval, "provision")
    _require_preflight(config)
    try:
        with _session(config, "course_migrator") as conn:
            conn.execute("SET LOCAL ROLE course_owner")
            conn.execute("""CREATE TABLE lab.module_03_txn_rows
                         (run_id uuid NOT NULL, slot integer NOT NULL, value integer NOT NULL,
                          PRIMARY KEY (run_id, slot))""")
            conn.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON lab.module_03_txn_rows TO course_app")
            conn.execute("GRANT SELECT ON lab.module_03_txn_rows TO course_analyst")
            _verify_table(conn)
        return {"ok": True}
    except Exception as error:
        raise LabError("Provisioning failed: " + _failure(error)["error"] + ".") from None


def _ready(config: Config) -> None:
    _require_preflight(config)
    try:
        with _session(config, "course_migrator") as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            _verify_table(conn)
    except Exception as error:
        raise LabError("Lab table verification failed: " + _failure(error)["error"] + ".") from None


def _insert(conn, run_id, slot, value):
    conn.execute("INSERT INTO lab.module_03_txn_rows VALUES (%s,%s,%s)", (run_id, slot, value))


def _value(conn, run_id, slot):
    row = conn.execute("SELECT value FROM lab.module_03_txn_rows WHERE run_id=%s AND slot=%s",
                       (run_id, slot)).fetchone()
    return None if row is None else row[0]


def _update(conn, run_id, slot, value):
    conn.execute("UPDATE lab.module_03_txn_rows SET value=%s WHERE run_id=%s AND slot=%s",
                 (value, run_id, slot))


def _commit_rollback(config, run_id):
    with _session(config, "course_app") as conn:
        _insert(conn, run_id, 1, 10)
    with _session(config, "course_app") as conn:
        _update(conn, run_id, 1, 20)
        conn.rollback()
        observed = _value(conn, run_id, 1)
    if observed != 10:
        raise ValueError
    return {"committed": True, "rollback_preserved_committed_value": True}


def _savepoints(config, run_id):
    with _session(config, "course_app") as conn:
        _insert(conn, run_id, 1, 10)
        conn.execute("SAVEPOINT exercise")
        try:
            _insert(conn, run_id, 1, 99)
        except psycopg.Error as error:
            first = error.sqlstate
        else:
            raise ValueError
        try:
            conn.execute("SELECT 1")
        except psycopg.Error as error:
            aborted = error.sqlstate
        else:
            raise ValueError
        conn.execute("ROLLBACK TO SAVEPOINT exercise")
        _insert(conn, run_id, 2, 20)
        conn.execute("RELEASE SAVEPOINT exercise")
        if first != "23505" or aborted != "25P02":
            raise ValueError
    return {"duplicate_sqlstate": first, "aborted_sqlstate": aborted, "savepoint_recovered": True}


def _isolation(config, run_id):
    with _session(config, "course_app") as conn:
        _insert(conn, run_id, 1, 10)
    with _session(config, "course_app") as reader, _session(config, "course_app") as writer:
        reader.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
        before = _value(reader, run_id, 1)
        _update(writer, run_id, 1, 20)
        uncommitted = _value(reader, run_id, 1)
        _commit(writer)
        committed = _value(reader, run_id, 1)
    if (before, uncommitted, committed) != (10, 10, 20):
        raise ValueError
    with _session(config, "course_app") as reader, _session(config, "course_app") as writer:
        reader.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        before = _value(reader, run_id, 1)
        _update(writer, run_id, 1, 30)
        _commit(writer)
        snapshot = _value(reader, run_id, 1)
        _commit(reader)
        refreshed = _value(reader, run_id, 1)
    if (before, snapshot, refreshed) != (20, 20, 30):
        raise ValueError
    return {"read_committed_refreshes": True, "repeatable_read_snapshot": True}


def _locking(config, run_id):
    with _session(config, "course_app") as conn:
        settings = conn.execute(
            """SELECT name, setting, unit FROM pg_settings
               WHERE name IN ('deadlock_timeout','lock_timeout','statement_timeout')"""
        ).fetchall()
    try:
        timeouts = {name: int(value) for name, value, unit in settings if unit == "ms"}
        deadlock = timeouts["deadlock_timeout"]
        lock = timeouts["lock_timeout"]
        statement = timeouts["statement_timeout"]
        supported = 0 < deadlock + 250 < lock < statement
    except (KeyError, ValueError):
        supported = False
    if not supported:
        return {"outcome": "inconclusive", "reason": "unsupported_timeout_configuration"}
    with _session(config, "course_app") as conn:
        _insert(conn, run_id, 1, 1)
        _insert(conn, run_id, 2, 1)
    nowait_result = [None]
    nowait_connection = [None]
    nowait_barrier = threading.Barrier(2, timeout=6)
    with _session(config, "course_app") as holder:
        holder.execute("SELECT 1 FROM lab.module_03_txn_rows WHERE run_id=%s AND slot=1 FOR UPDATE",
                       (run_id,))
        def nowait_worker():
            try:
                with _session(config, "course_app") as contender:
                    nowait_connection[0] = contender
                    nowait_barrier.wait()
                    contender.execute("SELECT 1 FROM lab.module_03_txn_rows WHERE run_id=%s AND slot=1 FOR UPDATE NOWAIT",
                                      (run_id,))
                    nowait_result[0] = "unexpected_success"
            except psycopg.Error as error:
                nowait_result[0] = error.sqlstate
            except Exception:
                nowait_result[0] = "failed"
                nowait_barrier.abort()
        thread = threading.Thread(target=nowait_worker, daemon=True)
        thread.start()
        try:
            nowait_barrier.wait()
        except threading.BrokenBarrierError:
            thread.join(6)
            raise ValueError from None
        thread.join(12 + config.timeout)
        if thread.is_alive():
            if nowait_connection[0] is not None:
                nowait_connection[0].cancel_safe(timeout=2)
            thread.join(6)
            raise ValueError
    nowait = nowait_result[0]
    barrier = threading.Barrier(2, timeout=6)
    results = [None, None]
    connections = [None, None]

    def worker(index):
        try:
            with _session(config, "course_app") as conn:
                connections[index] = conn
                conn.execute("SELECT 1 FROM lab.module_03_txn_rows WHERE run_id=%s AND slot=%s FOR UPDATE",
                             (run_id, index + 1))
                barrier.wait()
                conn.execute("SELECT 1 FROM lab.module_03_txn_rows WHERE run_id=%s AND slot=%s FOR UPDATE",
                             (run_id, 2 - index))
                results[index] = "committed"
        except psycopg.Error as error:
            results[index] = error.sqlstate
        except Exception as error:
            results[index] = "failed"
            barrier.abort()

    threads = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(12 + config.timeout)
    if any(t.is_alive() for t in threads):
        for conn in connections:
            if conn is not None:
                conn.cancel_safe(timeout=2)
        for thread in threads:
            thread.join(6)
        raise ValueError
    if nowait in ("57014", "08001") or any(result in ("57014", "55P03", "08001")
                                               for result in results):
        state = nowait if nowait in ("57014", "08001") else next(
            result for result in results if result in ("57014", "55P03", "08001"))
        return {"outcome": "inconclusive", "reason": "locking_timeout_or_connection",
                "sqlstate": state, "timeouts_ms": timeouts}
    if nowait != "55P03" or sorted(str(r) for r in results) != ["40P01", "committed"]:
        raise ValueError
    # Both transactions lock in the same order, so neither forms a cycle.
    barrier = threading.Barrier(2, timeout=6)
    ordered = [None, None]
    ordered_connections = [None, None]

    def ordered_worker(index):
        try:
            with _session(config, "course_app") as conn:
                ordered_connections[index] = conn
                barrier.wait()
                for slot in (1, 2):
                    conn.execute("SELECT 1 FROM lab.module_03_txn_rows WHERE run_id=%s AND slot=%s FOR UPDATE",
                                 (run_id, slot))
            ordered[index] = "committed"
        except psycopg.Error as error:
            ordered[index] = error.sqlstate
            barrier.abort()
        except Exception:
            ordered[index] = "failed"
            barrier.abort()

    threads = [threading.Thread(target=ordered_worker, args=(i,), daemon=True) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(12 + config.timeout)
    if any(t.is_alive() for t in threads):
        barrier.abort()
        for conn in ordered_connections:
            if conn is not None:
                conn.cancel_safe(timeout=2)
        for thread in threads:
            thread.join(6)
        raise ValueError
    if any(result in ("57014", "55P03", "08001") for result in ordered):
        state = next(result for result in ordered if result in ("57014", "55P03", "08001"))
        return {"outcome": "inconclusive", "reason": "locking_timeout_or_connection",
                "sqlstate": state, "timeouts_ms": timeouts}
    if ordered != ["committed", "committed"]:
        raise ValueError
    return {"outcome": "observed", "timeouts_ms": timeouts, "nowait_sqlstate": nowait,
            "deadlock_sqlstate": "40P01", "ordered_completed": True}


def _serializable(config, run_id):
    with _session(config, "course_app") as conn:
        _insert(conn, run_id, 1, 100)
        _insert(conn, run_id, 2, 100)
        _insert(conn, run_id, 11, 100)
        _insert(conn, run_id, 12, 100)
    with _session(config, "course_app") as a, _session(config, "course_app") as b:
        for conn in (a, b):
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            total = conn.execute(
                "SELECT sum(value) FROM lab.module_03_txn_rows WHERE run_id=%s AND slot IN (11,12)",
                (run_id,)).fetchone()[0]
            if total != 200:
                raise ValueError
        _update(a, run_id, 11, 0)
        _update(b, run_id, 12, 0)
        _commit(a)
        _commit(b)
    with _session(config, "course_app") as conn:
        baseline = conn.execute(
            "SELECT sum(value) FROM lab.module_03_txn_rows WHERE run_id=%s AND slot IN (11,12)",
            (run_id,)).fetchone()[0]
        if baseline != 0:
            raise ValueError
    with _session(config, "course_app") as a, _session(config, "course_app") as b:
        a.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        b.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        for conn in (a, b):
            if conn.execute("SELECT sum(value) FROM lab.module_03_txn_rows WHERE run_id=%s AND slot IN (1,2)",
                            (run_id,)).fetchone()[0] != 200:
                raise ValueError
        _update(a, run_id, 1, 0)
        state = None
        try:
            _update(b, run_id, 2, 0)
        except psycopg.Error as error:
            if error.sqlstate != "40001":
                raise
            state = error.sqlstate
            b.rollback()
        _commit(a)
        if state is None:
            try:
                _commit(b)
            except psycopg.Error as error:
                if error.sqlstate != "40001":
                    raise
                state = error.sqlstate
                b.rollback()
            else:
                raise ValueError
    if state != "40001":
        raise ValueError
    # Retry the complete decision, including the read, in a fresh transaction.
    decision = None
    for attempt in range(3):
        try:
            with _session(config, "course_app") as conn:
                conn.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                count = conn.execute("SELECT sum(value) FROM lab.module_03_txn_rows WHERE run_id=%s AND slot IN (1,2)",
                                     (run_id,)).fetchone()[0]
                decision = "debit" if count >= 200 else "decline"
                if decision == "debit":
                    _update(conn, run_id, 2, 0)
            break
        except Exception as error:
            if not _retry_serialization(error, attempt):
                raise
    with _session(config, "course_app") as conn:
        total = conn.execute("SELECT sum(value) FROM lab.module_03_txn_rows WHERE run_id=%s AND slot IN (1,2)",
                             (run_id,)).fetchone()[0]
    if total < 100 or decision != "decline":
        raise ValueError
    return {"repeatable_read_invariant_violated": True, "conflict_sqlstate": state,
            "retry_decision": decision, "invariant_preserved": True,
            "retry_attempts": attempt + 1}


_EXPERIMENTS = {"commit_rollback": _commit_rollback, "savepoints": _savepoints,
                "isolation": _isolation, "locking": _locking, "serializable": _serializable}


def run_experiment(config: Config, approval: Approval, name: str) -> dict:
    if name not in _EXPERIMENTS:
        raise LabError("Unknown experiment.")
    _guard(config, approval, "run:" + name)
    _ready(config)
    run_id = uuid.uuid4()
    try:
        result = _EXPERIMENTS[name](config, run_id)
        return {"ok": result.get("outcome") != "inconclusive", "run_id": str(run_id),
                "experiment": name, "result": result}
    except Exception as error:
        # Preserve the ID for explicit, authorized cleanup of partially committed rows.
        return {"ok": False, "run_id": str(run_id), "experiment": name,
                **_failure(error), "cleanup_may_be_required": True}


def cleanup(config: Config, approval: Approval, run_id: str) -> dict:
    if not isinstance(run_id, str):
        raise LabError("Invalid action.")
    action = "cleanup:" + run_id
    _validate_action(action)
    _guard(config, approval, action)
    _ready(config)
    try:
        with _session(config, "course_app") as conn:
            conn.execute("DELETE FROM lab.module_03_txn_rows WHERE run_id=%s", (uuid.UUID(run_id),))
        return {"ok": True, "run_id": run_id}
    except Exception as error:
        raise LabError("Cleanup failed: " + _failure(error)["error"] + ".") from None


def report_json(report: dict) -> str:
    """Export only typed, allowlisted report fields; discard all other content."""
    booleans = {"ok", "cleanup_may_be_required", "null_is_null", "committed",
                "rollback_preserved_committed_value", "savepoint_recovered",
                "read_committed_refreshes", "repeatable_read_snapshot", "ordered_completed",
                "repeatable_read_invariant_violated", "invariant_preserved"}
    numbers = {"integer_division", "orders_with_items", "order_item_count",
               "positive_price_count", "ranked_order_count", "retry_attempts",
               "deadlock_timeout", "lock_timeout", "statement_timeout"}
    strings = {
        "experiment": set(_NAMES),
        "error": set(_SQLSTATES.values()) | {"verification_failed", "connection_failed",
                                               "commit_outcome_unknown"},
        "sqlstate": set(_SQLSTATES),
        "duplicate_sqlstate": {"23505"}, "aborted_sqlstate": {"25P02"},
        "nowait_sqlstate": {"55P03"}, "deadlock_sqlstate": {"40P01"},
        "conflict_sqlstate": {"40001"}, "outcome": {"observed", "inconclusive"},
        "reason": {"unsupported_timeout_configuration", "locking_timeout_or_connection"},
        "retry_decision": {"debit", "decline"}, "integer_type": {"integer"},
        "numeric_division": {"2.5"},
        "hypothetical_new_york_noon_utc": {"2024-01-15T17:00:00"},
        "checks": {"PostgreSQL 18, identities, ownership, commerce schema and access"},
        "check": {"database", "course_migrator", "course_app", "course_analyst"},
    }

    def clean(data):
        if not isinstance(data, dict):
            return {}
        output = {}
        for key, value in data.items():
            if not isinstance(key, str):
                continue
            if key in booleans and type(value) is bool:
                output[key] = value
            elif key == "null_equals_null" and value is None:
                output[key] = None
            elif key in numbers and type(value) is int and 0 <= value <= 2**63 - 1:
                output[key] = value
            elif key in strings and isinstance(value, str) and value in strings[key]:
                output[key] = value
            elif key == "run_id" and isinstance(value, str):
                try:
                    parsed = uuid.UUID(value)
                    if str(parsed) == value and parsed.version == 4:
                        output[key] = value
                except ValueError:
                    pass
            elif key in {"result", "timeouts_ms"} and isinstance(value, dict):
                output[key] = clean(value)
        return output
    return json.dumps(clean(report), sort_keys=True, ensure_ascii=True)
