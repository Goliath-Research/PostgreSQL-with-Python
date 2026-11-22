"""Request and release one private PostgreSQL lab database per student.

Opening a course notebook calls :func:`attach`. Later notebooks for the same
operating-system user reuse that database. :func:`leave` deletes it and is
never registered as an interpreter shutdown hook. Module 11 does not attach:
its fixture is designed to run without this server.

Each student gets a Compose project so the course roles can keep the names
``course_owner``, ``course_migrator``, ``course_app``, and ``course_analyst``.
Role names are cluster-wide, so two students cannot share one PostgreSQL
server and still log in with those names.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from psycopg import sql

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

DATABASE = "goliath_ecommerce"
HOST = "127.0.0.1"
PORT_MIN = 54400
PORT_MAX = 54499
_PROJECT_PREFIX = "goliath-"
_SESSION_KEYS = (
    "student_id",
    "project",
    "host",
    "port",
    "database",
    "created_at",
    "last_attached",
)
_ENV_KEYS = (
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "PG_HOST_PORT",
    "COURSE_MIGRATOR_PASSWORD",
    "COURSE_APP_PASSWORD",
    "COURSE_ANALYST_PASSWORD",
)
_ROLE_PASSWORDS = {
    "course_migrator": "COURSE_MIGRATOR_PASSWORD",
    "course_app": "COURSE_APP_PASSWORD",
    "course_analyst": "COURSE_ANALYST_PASSWORD",
}
_EXPORTED = (
    "PGHOST",
    "PGPORT",
    "PGDATABASE",
    "PGCONNECT_TIMEOUT",
    "COURSE_MIGRATOR_USER",
    "COURSE_MIGRATOR_PASSWORD",
    "COURSE_APP_USER",
    "COURSE_APP_PASSWORD",
    "COURSE_ANALYST_USER",
    "COURSE_ANALYST_PASSWORD",
)


class LabSessionError(Exception):
    """A lab request or release failed. The message is safe to display."""


@dataclass(frozen=True)
class Session:
    student_id: str
    project: str
    host: str
    port: int
    database: str

    def public_summary(self) -> str:
        return (
            f"Lab database {self.database} for {self.student_id} "
            f"at {self.host}:{self.port} (project {self.project})."
        )


def repo_root() -> Path:
    override = os.environ.get("COURSE_LAB_ROOT")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent


def session_dir() -> Path:
    override = os.environ.get("COURSE_LAB_SESSION_DIR")
    if override:
        return Path(override)
    return repo_root() / ".lab-sessions"


def autostart_enabled() -> bool:
    """Notebooks request a database on open unless this is turned off."""
    flag = os.environ.get("COURSE_LAB_AUTOSTART", "1").strip().lower()
    if flag in {"0", "false", "no", "off"}:
        return False
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    return True


def current_os_slug() -> str:
    return _slug(getpass.getuser())


def student_slug(student_id: str | None = None) -> str:
    """Return the current student's id. Another student's id is refused."""
    actual = current_os_slug()
    if student_id is None:
        return actual
    requested = _slug(student_id)
    if requested != actual:
        raise LabSessionError("This session belongs to a different student.")
    return actual


def attach(student_id: str | None = None) -> Session:
    """Start this student's lab database, or reconnect to the existing one."""
    slug = student_slug(student_id)
    _compose_file()
    with _session_lock():
        record = _read_session(slug)
        if record is None:
            record = _new_record(slug)
            env = _new_env(int(record["port"]))
            _write_env(slug, env)
            _write_session(record)
            created = True
        elif record["student_id"] != slug:
            raise LabSessionError("This session belongs to a different student.")
        else:
            env = _read_env(slug)
            created = False
        try:
            _compose(record["project"], env, "up", "-d", "--wait")
            _configure_database(record, env)
        except Exception:
            if created:
                _release_record(record, env, missing_ok=True)
            raise
        record["last_attached"] = _iso(_utc_now())
        _write_session(record)
        session = _session_from_record(record)
    _export(session, env)
    return session


def leave(student_id: str | None = None) -> None:
    """Delete this student's lab database, volume, and session record."""
    slug = student_slug(student_id)
    with _session_lock():
        record = _read_session(slug)
        if record is None:
            raise LabSessionError("No lab database is allocated for this student.")
        if record["student_id"] != slug:
            raise LabSessionError("This session belongs to a different student.")
        env = _read_env(slug) if _env_path(slug).is_file() else _down_env(record)
        _release_record(record, env, missing_ok=False)
    _mark_released()


def current_session(student_id: str | None = None) -> Session | None:
    slug = student_slug(student_id)
    record = _read_session(slug)
    if record is None:
        return None
    if record["student_id"] != slug:
        raise LabSessionError("This session belongs to a different student.")
    return _session_from_record(record)


def reap(idle_hours: float) -> list[str]:
    """Release lab databases that have not been opened within ``idle_hours``."""
    if idle_hours <= 0:
        raise LabSessionError("Idle time must be positive.")
    cutoff = _utc_now() - timedelta(hours=idle_hours)
    released: list[str] = []
    with _session_lock():
        for slug, record in _list_sessions():
            last_attached = datetime.fromisoformat(str(record["last_attached"]))
            if last_attached.tzinfo is None:
                last_attached = last_attached.replace(tzinfo=timezone.utc)
            if last_attached > cutoff:
                continue
            env = _read_env(slug) if _env_path(slug).is_file() else _down_env(record)
            _release_record(record, env, missing_ok=True)
            released.append(slug)
    return released


def leave_controls(mo: object) -> tuple[object, object]:
    """Build the notebook status line and the Leave the lab button."""
    session = current_session()
    button = mo.ui.button(label="Leave the lab")  # type: ignore[attr-defined]
    if session is None:
        summary = "No lab database is allocated."
    else:
        summary = (
            f"{session.public_summary()} Other course notebooks keep this "
            "database until you leave the lab."
        )
    panel = mo.vstack([mo.md(f"**Lab.** {summary}"), button])  # type: ignore[attr-defined]
    return panel, button


def release_if_requested(requested: object) -> str | None:
    """Release the lab when the Leave button has been used."""
    if not requested:
        return None
    try:
        leave()
    except LabSessionError as error:
        return str(error)
    return "Lab database released. Open a course notebook to request a new one."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Request and release a private course lab database.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    attach_command = commands.add_parser("attach", help="request or reuse your lab database")
    attach_command.add_argument("--student", default=None)
    leave_command = commands.add_parser("leave", help="release your lab database")
    leave_command.add_argument("--student", default=None)
    reap_command = commands.add_parser("reap", help="release idle lab databases")
    reap_command.add_argument("--idle-hours", type=float, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "attach":
            print(attach(args.student).public_summary())
        elif args.command == "leave":
            leave(args.student)
            print("Lab database released.")
        else:
            released = reap(args.idle_hours)
            print(f"Released {len(released)} lab database(s).")
    except LabSessionError as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    if cleaned and not cleaned[0].isalpha():
        cleaned = f"s-{cleaned}"
    cleaned = cleaned[:40].strip("-")
    if cleaned is None or re.fullmatch(r"[a-z][a-z0-9-]*", cleaned or "") is None:
        raise LabSessionError("Student id is empty.")
    return cleaned


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat()


def _project_name(slug: str) -> str:
    return f"{_PROJECT_PREFIX}{slug}"


def _session_path(slug: str) -> Path:
    return session_dir() / f"{slug}.json"


def _env_path(slug: str) -> Path:
    return session_dir() / f"{slug}.env"


def _compose_file() -> Path:
    path = repo_root() / "compose.learner.yaml"
    if not path.is_file():
        raise LabSessionError("compose.learner.yaml is missing.")
    return path


@contextmanager
def _session_lock():
    directory = session_dir()
    directory.mkdir(parents=True, exist_ok=True)
    handle = open(directory / ".lock", "a+b")
    try:
        if handle.seek(0, os.SEEK_END) == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        if sys.platform == "win32":
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            handle.seek(0)
            if sys.platform == "win32":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


def _new_record(slug: str) -> dict[str, object]:
    now = _iso(_utc_now())
    return {
        "student_id": slug,
        "project": _project_name(slug),
        "host": HOST,
        "port": _pick_port(),
        "database": DATABASE,
        "created_at": now,
        "last_attached": now,
    }


def _pick_port() -> int:
    used = _allocated_ports()
    for port in range(PORT_MIN, PORT_MAX + 1):
        if port in used:
            continue
        if _port_free(port):
            return port
    raise LabSessionError("No free localhost port is available for a lab database.")


def _allocated_ports() -> set[int]:
    ports: set[int] = set()
    for _slug_name, record in _list_sessions():
        ports.add(int(record["port"]))
    return ports


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((HOST, port))
        except OSError:
            return False
    return True


def _down_env(record: dict[str, object]) -> dict[str, str]:
    """Satisfy Compose interpolation when the credential file is already gone."""
    env = _new_env(int(record["port"]))
    env["POSTGRES_PASSWORD"] = "released"
    env["COURSE_MIGRATOR_PASSWORD"] = "released"
    env["COURSE_APP_PASSWORD"] = "released"
    env["COURSE_ANALYST_PASSWORD"] = "released"
    return env


def _new_env(port: int) -> dict[str, str]:
    return {
        "POSTGRES_USER": "postgres",
        "POSTGRES_PASSWORD": secrets.token_hex(24),
        "POSTGRES_DB": DATABASE,
        "PG_HOST_PORT": str(port),
        "COURSE_MIGRATOR_PASSWORD": secrets.token_hex(24),
        "COURSE_APP_PASSWORD": secrets.token_hex(24),
        "COURSE_ANALYST_PASSWORD": secrets.token_hex(24),
    }


def _write_env(slug: str, env: dict[str, str]) -> None:
    lines = [f"{key}={env[key]}" for key in _ENV_KEYS]
    _write_private(_env_path(slug), ("\n".join(lines) + "\n").encode("utf-8"))


def _read_env(slug: str) -> dict[str, str]:
    path = _env_path(slug)
    if not path.is_file():
        raise LabSessionError("Lab session credentials are missing.")
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key] = value
    if any(not env.get(key) for key in _ENV_KEYS):
        raise LabSessionError("Lab session credentials are incomplete.")
    return {key: env[key] for key in _ENV_KEYS}


def _write_session(record: dict[str, object]) -> None:
    payload = {key: record[key] for key in _SESSION_KEYS}
    encoded = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
    _write_private(_session_path(str(record["student_id"])), encoded)


def _write_private(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(temporary, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    temporary.replace(path)


def _read_session(slug: str) -> dict[str, object] | None:
    path = _session_path(slug)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise LabSessionError("Lab session record is unreadable.") from None
    return _validate_record(slug, data)


def _list_sessions() -> list[tuple[str, dict[str, object]]]:
    directory = session_dir()
    if not directory.is_dir():
        return []
    found: list[tuple[str, dict[str, object]]] = []
    for path in sorted(directory.glob("*.json")):
        found.append((path.stem, _read_session(path.stem) or {}))
    return [(slug, record) for slug, record in found if record]


def _validate_record(slug: str, data: object) -> dict[str, object]:
    if not isinstance(data, dict) or any(key not in data for key in _SESSION_KEYS):
        raise LabSessionError("Lab session record is incomplete.")
    port = data["port"]
    if (
        data["student_id"] != slug
        or data["project"] != _project_name(slug)
        or data["host"] != HOST
        or data["database"] != DATABASE
        or not isinstance(port, int)
        or not PORT_MIN <= port <= PORT_MAX
    ):
        raise LabSessionError("Lab session record is invalid.")
    return data


def _session_from_record(record: dict[str, object]) -> Session:
    return Session(
        student_id=str(record["student_id"]),
        project=str(record["project"]),
        host=str(record["host"]),
        port=int(record["port"]),
        database=str(record["database"]),
    )


def _compose(project: str, env: dict[str, str], *args: str) -> None:
    if not project.startswith(_PROJECT_PREFIX) or project == _PROJECT_PREFIX:
        raise LabSessionError("Lab session record is invalid.")
    command = [
        "docker",
        "compose",
        "-p",
        project,
        "-f",
        str(_compose_file()),
        *args,
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=repo_root(),
            env={**os.environ, **env},
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            timeout=180,
        )
    except FileNotFoundError:
        raise LabSessionError("Docker is not available.") from None
    except subprocess.TimeoutExpired:
        raise LabSessionError("The lab database did not become ready in time.") from None
    if completed.returncode != 0:
        detail = _redact((completed.stderr or completed.stdout or "").strip(), env)
        raise LabSessionError(f"Lab container command failed. {detail[:500]}".rstrip())


def _configure_database(record: dict[str, object], env: dict[str, str]) -> None:
    last_error = "PostgreSQL did not accept connections."
    for _attempt in range(20):
        try:
            _apply_roles(record, env)
            return
        except LabSessionError:
            raise
        except Exception as error:
            last_error = type(error).__name__
            time.sleep(0.5)
    raise LabSessionError(last_error)


def _apply_roles(record: dict[str, object], env: dict[str, str]) -> None:
    with psycopg.connect(
        host=str(record["host"]),
        port=int(record["port"]),
        dbname=str(record["database"]),
        user=env["POSTGRES_USER"],
        password=env["POSTGRES_PASSWORD"],
        connect_timeout=5,
        autocommit=True,
    ) as connection:
        for role, key in _ROLE_PASSWORDS.items():
            connection.execute(
                sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                    sql.Identifier(role),
                    sql.Literal(env[key]),
                )
            )
        owner = connection.execute(
            "SELECT rolcanlogin FROM pg_roles WHERE rolname = 'course_owner'"
        ).fetchone()
        probe = connection.execute(
            """
            SELECT count(*)
            FROM lab.connection_probe
            WHERE probe_note = 'Initial bootstrap probe record'
            """
        ).fetchone()
    if owner is None or owner[0] or probe is None or int(probe[0]) < 1:
        raise LabSessionError("Lab database bootstrap did not finish.")


def _export(session: Session, env: dict[str, str]) -> None:
    os.environ["PGHOST"] = session.host
    os.environ["PGPORT"] = str(session.port)
    os.environ["PGDATABASE"] = session.database
    os.environ["PGCONNECT_TIMEOUT"] = "5"
    os.environ["COURSE_MIGRATOR_USER"] = "course_migrator"
    os.environ["COURSE_APP_USER"] = "course_app"
    os.environ["COURSE_ANALYST_USER"] = "course_analyst"
    for key in _ROLE_PASSWORDS.values():
        os.environ[key] = env[key]


def _mark_released() -> None:
    os.environ["PGHOST"] = HOST
    os.environ["PGPORT"] = "0"
    os.environ["PGDATABASE"] = DATABASE
    os.environ["PGCONNECT_TIMEOUT"] = "5"
    for key in _ROLE_PASSWORDS.values():
        os.environ.pop(key, None)


def _release_record(record: dict[str, object], env: dict[str, str], *, missing_ok: bool) -> None:
    project = str(record["project"])
    slug = str(record["student_id"])
    if project != _project_name(slug):
        raise LabSessionError("Lab session record is invalid.")
    try:
        _compose(project, env, "down", "-v")
    except LabSessionError:
        if not missing_ok:
            raise
    _session_path(slug).unlink(missing_ok=True)
    _env_path(slug).unlink(missing_ok=True)


def _redact(text: str, env: dict[str, str]) -> str:
    redacted = text
    for key, value in env.items():
        if "PASSWORD" in key and value:
            redacted = redacted.replace(value, "[REDACTED]")
    return redacted


if __name__ == "__main__":
    raise SystemExit(main())
