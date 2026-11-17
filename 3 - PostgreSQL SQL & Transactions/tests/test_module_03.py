"""Offline tests by default; integration requires explicit disposable-target consent."""

import dataclasses
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import uuid

import pytest
from psycopg import sql


MODULE = Path(__file__).resolve().parents[1] / "module_03_support.py"
spec = importlib.util.spec_from_file_location("module_03_support", MODULE)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


@pytest.fixture
def config():
    return m.Config("127.0.0.1", 54329, "goliath_ecommerce", "secret1", "secret2", "secret3")


def test_import_does_not_connect(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("import connected")
    monkeypatch.setattr(m.psycopg, "connect", forbidden)
    spec.loader.exec_module(m)


def test_load_no_interpolation_and_environment_override(monkeypatch):
    values = {"PGHOST": "filehost", "PGPORT": "5432", "PGDATABASE": "goliath_ecommerce",
              "PGCONNECT_TIMEOUT": "5", "COURSE_MIGRATOR_USER": "course_migrator",
              "COURSE_APP_USER": "course_app", "COURSE_ANALYST_USER": "course_analyst",
              "COURSE_MIGRATOR_PASSWORD": " ${UNEXPANDED} ",
              "COURSE_APP_PASSWORD": " file ", "COURSE_ANALYST_PASSWORD": "secret"}
    for key in values:
        monkeypatch.delenv(key, raising=False)
    calls = []
    def dotenv(path, *, interpolate):
        calls.append(interpolate)
        return values
    monkeypatch.setattr(m, "dotenv_values", dotenv)
    monkeypatch.setenv("COURSE_APP_PASSWORD", " env spaces ")
    config = m.Config.load("ignored")
    assert calls == [False]
    assert config.migrator_password == " ${UNEXPANDED} "
    assert config.app_password == " env spaces "
    assert "secret" not in repr(config)


def test_real_dotenv_preserves_quoted_spaces_and_literals(monkeypatch):
    source = """PGHOST=localhost
PGPORT=5432
PGDATABASE=goliath_ecommerce
COURSE_MIGRATOR_USER=course_migrator
COURSE_MIGRATOR_PASSWORD=' ${OTHER} '
COURSE_APP_USER=course_app
COURSE_APP_PASSWORD=' app '
COURSE_ANALYST_USER=course_analyst
COURSE_ANALYST_PASSWORD=' analyst '
"""
    for key in ("PGHOST", "PGPORT", "PGDATABASE", "PGCONNECT_TIMEOUT",
                "COURSE_MIGRATOR_USER", "COURSE_MIGRATOR_PASSWORD", "COURSE_APP_USER",
                "COURSE_APP_PASSWORD", "COURSE_ANALYST_USER", "COURSE_ANALYST_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    parse = m.dotenv_values
    monkeypatch.setattr(m, "dotenv_values", lambda path, interpolate: parse(
        stream=io.StringIO(source), interpolate=interpolate))
    config = m.Config.load("unused")
    assert config.migrator_password == " ${OTHER} "
    assert config.app_password == " app "


def test_load_rejects_wrong_role_and_invalid_port(monkeypatch):
    monkeypatch.setattr(m, "dotenv_values", lambda *a, **k: {})
    for key in ("PGHOST", "PGPORT", "PGDATABASE", "COURSE_MIGRATOR_USER"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(m.LabError, match="Invalid configuration"):
        m.Config.load("unused")


def test_guards_before_any_connection(config, monkeypatch):
    monkeypatch.setattr(m, "_connect", lambda *a: pytest.fail("guard connected"))
    approval = m.authorize(config, "provision")
    changed = dataclasses.replace(config, app_password="different")
    for cfg, token in ((changed, approval), (config, m.authorize(config, "run:isolation"))):
        with pytest.raises(m.LabError, match="Authorization"):
            m.provision(cfg, token)
    with pytest.raises(m.LabError):
        m.run_experiment(config, approval, "unknown")
    with pytest.raises(m.LabError):
        m.cleanup(config, approval, "'; DROP TABLE commerce.orders; --")
    for bad in ("run:unknown", "cleanup:abc", "cleanup:" + str(uuid.uuid4()).upper(), ""):
        with pytest.raises(m.LabError):
            m.authorize(config, bad)


def test_preflight_is_fail_closed_and_redacted(config, monkeypatch):
    def fail(*args):
        raise RuntimeError("private credentials and private row")
    monkeypatch.setattr(m, "_connect", fail)
    report = m.preflight(config)
    assert report == {"ok": False, "check": "course_migrator", "error": "verification_failed"}
    assert "private" not in m.report_json(report)
    assert not m.preflight(dataclasses.replace(config, database="other"))["ok"]


def test_failure_codes_are_allowlisted():
    class FakeError(Exception):
        sqlstate = "42501"
    assert m._failure(FakeError("private")) == {"error": "permission_denied", "sqlstate": "42501"}
    FakeError.sqlstate = "NOT-A-SAFE-CODE"
    assert m._failure(FakeError("private")) == {"error": "verification_failed"}


@pytest.mark.parametrize("error,expected", [
    (m.psycopg.errors.SerializationFailure("private"), True),
    (m.psycopg.errors.DeadlockDetected("private"), False),
    (m.psycopg.errors.InsufficientPrivilege("private"), False),
    (m.psycopg.OperationalError("unknown commit acknowledgement"), False),
    (RuntimeError("private"), False),
])
def test_retry_decisions_are_bounded(error, expected):
    assert m._retry_serialization(error, 0) is expected
    assert m._retry_serialization(error, 1) is expected
    assert not m._retry_serialization(error, 2)


def test_unknown_commit_is_reported_and_not_retried(config, monkeypatch):
    class Connection:
        info = SimpleNamespace(transaction_status=m.psycopg.pq.TransactionStatus.INTRANS)
        closed = False
        def commit(self):
            raise m.psycopg.OperationalError("private connection details")
        def close(self):
            self.closed = True
        def rollback(self):
            pass
    connection = Connection()
    monkeypatch.setattr(m, "_connect", lambda *args: connection)
    monkeypatch.setattr(m, "_ready", lambda c: None)
    def experiment(config, run_id):
        with m._session(config, "course_app"):
            pass
    monkeypatch.setitem(m._EXPERIMENTS, "serializable", experiment)
    report = m.run_experiment(config, m.authorize(config, "run:serializable"), "serializable")
    assert report["error"] == "commit_outcome_unknown"
    assert not report["ok"] and connection.closed
    assert not m._retry_serialization(m._CommitOutcomeUnknown(), 0)
    assert "private" not in m.report_json(report)
    uuid.UUID(report["run_id"])


def test_report_json_drops_hostile_content():
    hostile = "******host/db private business row"
    report = {"ok": True, "run_id": hostile, "experiment": hostile,
              "sqlstate": hostile, "error": hostile, "password": hostile,
              "rows": [hostile], "exception": RuntimeError(hostile),
              "result": {"retry_decision": hostile, "data": hostile,
                         "conflict_sqlstate": "40001", "invariant_preserved": True},
              "order_item_count": hostile, "null_equals_null": None}
    exported = m.report_json(report)
    assert hostile not in exported
    assert json.loads(exported) == {"ok": True, "null_equals_null": None,
                                    "result": {"conflict_sqlstate": "40001",
                                               "invariant_preserved": True}}


def test_failed_experiment_has_cleanup_id_but_no_exception(config, monkeypatch):
    monkeypatch.setattr(m, "_ready", lambda c: None)
    def fail(*args):
        raise RuntimeError("secret1 sensitive row")
    monkeypatch.setitem(m._EXPERIMENTS, "isolation", fail)
    report = m.run_experiment(config, m.authorize(config, "run:isolation"), "isolation")
    assert not report["ok"] and report["cleanup_may_be_required"]
    uuid.UUID(report["run_id"])
    assert "secret1" not in m.report_json(report)
    assert json.loads(m.report_json(report)) == report


def test_inconclusive_locking_is_not_a_pass(config, monkeypatch):
    monkeypatch.setattr(m, "_ready", lambda c: None)
    monkeypatch.setitem(m._EXPERIMENTS, "locking", lambda *_: {
        "outcome": "inconclusive", "reason": "unsupported_timeout_configuration"})
    report = m.run_experiment(config, m.authorize(config, "run:locking"), "locking")
    assert report["ok"] is False
    assert json.loads(m.report_json(report)) == report


def integration_config():
    # Tests do not create or reset a database. The operator must supply an already
    # bootstrapped and migrated disposable localhost instance and consent explicitly.
    if os.getenv("MODULE03_DISPOSABLE") != "I_ACCEPT_DISPOSABLE_DATABASE_WRITES":
        pytest.skip("explicit disposable integration consent not provided")
    port = os.getenv("MODULE03_DISPOSABLE_PORT", "")
    if not port.isdecimal() or not 1 <= int(port) <= 65535:
        pytest.fail("explicit disposable localhost port required")
    return m.Config("127.0.0.1", int(port), "goliath_ecommerce",
                    os.environ["MODULE03_MIGRATOR_PASSWORD"],
                    os.environ["MODULE03_APP_PASSWORD"],
                    os.environ["MODULE03_ANALYST_PASSWORD"])


def commerce_fingerprint(config):
    with m._connect(config, "course_analyst") as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        metadata = conn.execute(
            """SELECT c.relname, c.relkind, pg_get_userbyid(c.relowner), c.relacl::text,
                      a.attnum, a.attname, format_type(a.atttypid,a.atttypmod),
                      a.attnotnull, a.attidentity, a.attgenerated
               FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
               JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped
               WHERE n.nspname='commerce' AND c.relname=ANY(%s)
               ORDER BY c.relname,a.attnum""", (list(m._TABLES),)).fetchall()
        signatures = []
        for table in sorted(m._TABLES):
            query = sql.SQL(
                "SELECT count(*), md5(coalesce(string_agg(md5(row_to_json(t)::text), "
                "'' ORDER BY md5(row_to_json(t)::text)),'')) FROM {} AS t"
            ).format(sql.Identifier("commerce", table))
            signatures.append(conn.execute(query).fetchone())
    return hashlib.sha256(repr((metadata, signatures)).encode()).hexdigest()


def test_disposable_postgres18_end_to_end():
    config = integration_config()
    assert m.preflight(config)["ok"]
    before = commerce_fingerprint(config)
    examples = m.read_sql_examples(config)
    assert examples["integer_division"] == 2 and examples["numeric_division"] == "2.5"
    assert examples["null_equals_null"] is None and examples["null_is_null"] is True
    assert examples["hypothetical_new_york_noon_utc"] == "2024-01-15T17:00:00"
    # Provision only if absent; an existing object must pass strict verification.
    with m._connect(config, "course_migrator") as conn:
        exists = conn.execute("SELECT to_regclass('lab.module_03_txn_rows') IS NOT NULL").fetchone()[0]
    if not exists:
        assert m.provision(config, m.authorize(config, "provision"))["ok"]
    else:
        m._ready(config)
    with pytest.raises(m.LabError, match="object_already_exists"):
        m.provision(config, m.authorize(config, "provision"))
    test_id = uuid.uuid4()
    with m._connect(config, "course_app") as conn:
        m._insert(conn, test_id, 1, 100)
        m._update(conn, test_id, 1, 50)
        assert m._value(conn, test_id, 1) == 50
        conn.execute("DELETE FROM lab.module_03_txn_rows WHERE run_id=%s", (test_id,))
        conn.rollback()
    with m._connect(config, "course_analyst") as conn:
        try:
            m._insert(conn, test_id, 1, 100)
        except m.psycopg.Error as error:
            assert error.sqlstate == "42501"
            conn.rollback()
        else:
            conn.rollback()
            pytest.fail("analyst unexpectedly had lab write access")
    runs = []
    try:
        for name in m._NAMES:
            report = m.run_experiment(config, m.authorize(config, "run:" + name), name)
            runs.append(report["run_id"])
            if name == "locking" and report.get("result", {}).get("outcome") == "inconclusive":
                pytest.skip("server locking timeouts do not support the deadlock demonstration")
            assert report["ok"], report
            result = report["result"]
            if name == "savepoints":
                assert result["aborted_sqlstate"] == "25P02"
            if name == "locking":
                assert result["outcome"] == "observed", result
                assert result["nowait_sqlstate"] == "55P03"
                assert result["deadlock_sqlstate"] == "40P01"
            if name == "serializable":
                assert result["repeatable_read_invariant_violated"]
                assert result["conflict_sqlstate"] == "40001"
                assert result["retry_decision"] == "decline" and result["invariant_preserved"]
        # Scoped cleanup must not remove another run.
        first, second = runs[:2]
        assert m.cleanup(config, m.authorize(config, "cleanup:" + first), first)["ok"]
        with m._connect(config, "course_app") as conn:
            assert conn.execute("SELECT count(*) FROM lab.module_03_txn_rows WHERE run_id=%s",
                                (uuid.UUID(first),)).fetchone()[0] == 0
            assert conn.execute("SELECT count(*) FROM lab.module_03_txn_rows WHERE run_id=%s",
                                (uuid.UUID(second),)).fetchone()[0] > 0
    finally:
        for run_id in runs:
            assert m.cleanup(config, m.authorize(config, "cleanup:" + run_id), run_id)["ok"]
        assert commerce_fingerprint(config) == before
