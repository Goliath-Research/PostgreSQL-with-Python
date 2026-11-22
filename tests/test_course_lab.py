"""Request and release behavior for the private course lab."""

from __future__ import annotations

import importlib.util
import json
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

import course_lab


NOTEBOOKS = (
    "1 - PostgreSQL Environment/01_postgresql_environment.py",
    "2 - Migrating the E-Commerce Database from SQLite to PostgreSQL/02_sqlite_to_postgresql.py",
    "3 - PostgreSQL SQL & Transactions/03_postgresql_sql_and_transactions.py",
    "4 - DuckDB PostgreSQL Connection/04_duckdb_postgresql_connection.py",
    "5 - Pythonic Relational Analytics/05_pythonic_relational_analytics.py",
    "6 - Analytical Reporting & Performance/06_analytical_reporting_and_performance.py",
    "7 - SQLAlchemy Core & Connections/07_sqlalchemy_core_and_connections.py",
    "8 - SQLAlchemy ORM Models/08_sqlalchemy_orm_models.py",
    "9 - Sessions & Transactional Services/09_sessions_and_transactional_services.py",
    "10 - Migrations, Testing & Capstone/10_migrations_testing_and_capstone.py",
)


class _Mo:
    class ui:
        @staticmethod
        def button(label):
            return SimpleNamespace(label=label, value=0)

    @staticmethod
    def md(text):
        return text

    @staticmethod
    def vstack(items):
        return items


@pytest.fixture
def lab(monkeypatch, tmp_path):
    root = tmp_path / "repo"
    sessions = tmp_path / "sessions"
    root.mkdir()
    (root / "compose.learner.yaml").write_text("services: {}\n", encoding="utf-8")
    monkeypatch.setenv("COURSE_LAB_ROOT", str(root))
    monkeypatch.setenv("COURSE_LAB_SESSION_DIR", str(sessions))
    monkeypatch.setattr(course_lab, "current_os_slug", lambda: "alice")
    monkeypatch.setattr(course_lab, "_configure_database", lambda *_args, **_kwargs: None)
    calls = []

    def fake_compose(project, env, *args):
        calls.append((project, env["PG_HOST_PORT"], args))

    monkeypatch.setattr(course_lab, "_compose", fake_compose)
    return SimpleNamespace(root=root, sessions=sessions, calls=calls)


def test_slug_normalizes_names():
    assert course_lab._slug("Ada Lovelace") == "ada-lovelace"
    assert course_lab._slug("123") == "s-123"
    with pytest.raises(course_lab.LabSessionError):
        course_lab._slug("   ")


def test_student_slug_refuses_another_student(monkeypatch):
    monkeypatch.setattr(course_lab, "current_os_slug", lambda: "alice")
    with pytest.raises(course_lab.LabSessionError, match="different student"):
        course_lab.student_slug("bob")


def test_autostart_respects_flag_and_pytest(monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("COURSE_LAB_AUTOSTART", "0")
    assert course_lab.autostart_enabled() is False
    monkeypatch.setenv("COURSE_LAB_AUTOSTART", "1")
    assert course_lab.autostart_enabled() is True
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/test_course_lab.py::test")
    assert course_lab.autostart_enabled() is False


def test_attach_creates_then_reuses_one_database(lab):
    first = course_lab.attach()
    password = (lab.sessions / "alice.env").read_text(encoding="utf-8")
    record = (lab.sessions / "alice.json").read_text(encoding="utf-8")
    assert first.project == "goliath-alice"
    assert first.port == course_lab.PORT_MIN
    assert first.public_summary() == (
        "Lab database goliath_ecommerce for alice "
        f"at 127.0.0.1:{course_lab.PORT_MIN} (project goliath-alice)."
    )
    assert "PASSWORD" not in record
    assert json.loads(record)["database"] == "goliath_ecommerce"
    for line in password.splitlines():
        if line.startswith("COURSE_APP_PASSWORD="):
            secret = line.split("=", 1)[1]
            assert secret not in record
            assert secret not in first.public_summary()
    second = course_lab.attach()
    assert second.port == first.port
    assert [call[2][0] for call in lab.calls] == ["up", "up"]
    assert lab.calls[0][0] == "goliath-alice"


def test_attach_skips_ports_already_reserved(lab, monkeypatch):
    monkeypatch.setattr(course_lab, "_port_free", lambda port: port != course_lab.PORT_MIN)
    now = course_lab._iso(course_lab._utc_now())
    course_lab._write_session(
        {
            "student_id": "bob",
            "project": "goliath-bob",
            "host": "127.0.0.1",
            "port": course_lab.PORT_MIN + 1,
            "database": "goliath_ecommerce",
            "created_at": now,
            "last_attached": now,
        }
    )
    session = course_lab.attach()
    assert session.port == course_lab.PORT_MIN + 2


def test_failed_request_removes_the_new_session(lab, monkeypatch):
    def fail_up(project, env, *args):
        if args[0] == "up":
            raise course_lab.LabSessionError("boom")

    monkeypatch.setattr(course_lab, "_compose", fail_up)
    with pytest.raises(course_lab.LabSessionError, match="boom"):
        course_lab.attach()
    assert list(lab.sessions.glob("*.json")) == []
    assert list(lab.sessions.glob("*.env")) == []


def test_leave_rejects_a_foreign_project(lab, monkeypatch):
    now = course_lab._iso(course_lab._utc_now())
    (lab.sessions).mkdir(parents=True, exist_ok=True)
    (lab.sessions / "alice.json").write_text(
        json.dumps(
            {
                "student_id": "alice",
                "project": "goliath_pg_lab",
                "host": "127.0.0.1",
                "port": course_lab.PORT_MIN,
                "database": "goliath_ecommerce",
                "created_at": now,
                "last_attached": now,
            }
        ),
        encoding="utf-8",
    )
    called = []
    monkeypatch.setattr(course_lab, "_compose", lambda *args: called.append(args))
    with pytest.raises(course_lab.LabSessionError, match="invalid"):
        course_lab.leave()
    assert called == []


def test_leave_deletes_only_this_student_and_clears_credentials(lab, monkeypatch):
    monkeypatch.setenv("COURSE_APP_PASSWORD", "prior")
    session = course_lab.attach()
    monkeypatch.setattr(course_lab, "current_os_slug", lambda: "alice")
    course_lab.leave()
    assert course_lab.current_session() is None
    assert not (lab.sessions / "alice.json").exists()
    assert not (lab.sessions / "alice.env").exists()
    assert os_port() == "0"
    assert "COURSE_APP_PASSWORD" not in __import__("os").environ
    assert lab.calls[-1][0] == session.project
    assert lab.calls[-1][2] == ("down", "-v")


def test_reap_releases_only_idle_sessions(lab, monkeypatch):
    course_lab.attach()
    stale = course_lab._utc_now() - timedelta(hours=13)
    record = json.loads((lab.sessions / "alice.json").read_text(encoding="utf-8"))
    record["last_attached"] = course_lab._iso(stale)
    (lab.sessions / "alice.json").write_text(json.dumps(record), encoding="utf-8")
    fresh_now = course_lab._iso(course_lab._utc_now())
    course_lab._write_session(
        {
            "student_id": "bob",
            "project": "goliath-bob",
            "host": "127.0.0.1",
            "port": course_lab.PORT_MIN + 1,
            "database": "goliath_ecommerce",
            "created_at": fresh_now,
            "last_attached": fresh_now,
        }
    )
    (lab.sessions / "bob.env").write_text(
        "POSTGRES_USER=postgres\nPOSTGRES_PASSWORD=x\nPOSTGRES_DB=goliath_ecommerce\n"
        f"PG_HOST_PORT={course_lab.PORT_MIN + 1}\nCOURSE_MIGRATOR_PASSWORD=x\n"
        "COURSE_APP_PASSWORD=x\nCOURSE_ANALYST_PASSWORD=x\n",
        encoding="utf-8",
    )
    released = course_lab.reap(12)
    assert released == ["alice"]
    assert (lab.sessions / "bob.json").is_file()
    assert not (lab.sessions / "alice.json").exists()


def test_leave_controls_hide_passwords(lab):
    course_lab.attach()
    secret = __import__("os").environ["COURSE_APP_PASSWORD"]
    panel, button = course_lab.leave_controls(_Mo())
    assert secret not in panel[0]
    assert "goliath-alice" in panel[0]
    assert button.label == "Leave the lab"
    assert course_lab.release_if_requested(0) is None


def test_compose_error_redacts_passwords(monkeypatch, tmp_path):
    (tmp_path / "compose.learner.yaml").write_text("services: {}\n", encoding="utf-8")
    monkeypatch.setenv("COURSE_LAB_ROOT", str(tmp_path))

    def fake_run(command, **kwargs):
        assert command[:4] == ["docker", "compose", "-p", "goliath-alice"]
        return SimpleNamespace(
            returncode=1,
            stderr=kwargs["env"]["POSTGRES_PASSWORD"],
            stdout="",
        )

    monkeypatch.setattr(course_lab.subprocess, "run", fake_run)
    with pytest.raises(course_lab.LabSessionError) as caught:
        course_lab._compose(
            "goliath-alice",
            {"POSTGRES_PASSWORD": "s3cret-value"},
            "up",
        )
    assert "s3cret-value" not in str(caught.value)
    assert "[REDACTED]" in str(caught.value)


def test_compose_refuses_the_shared_lab_project():
    with pytest.raises(course_lab.LabSessionError, match="invalid"):
        course_lab._compose("goliath_pg_lab", {}, "down", "-v")


def test_course_notebooks_register_the_lab_hook(monkeypatch):
    monkeypatch.setenv("COURSE_LAB_AUTOSTART", "0")
    root = Path(__file__).resolve().parents[1]
    for relative in NOTEBOOKS:
        path = root / relative
        spec = importlib.util.spec_from_file_location(path.stem, path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.app._maybe_initialize()
        assert "course_lab" in module.app._defs


def os_port():
    return __import__("os").environ["PGPORT"]
