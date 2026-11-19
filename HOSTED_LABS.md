# Hosted Labs: Architecture, Execution Modes, and Responsibilities

> **Important:** This guide describes an architecture recommendation, not an
> implemented hosted platform. This repository provides a single-user local
> development setup; it does not provision hosted learner environments,
> authentication, or reset and persistence workflows.

## What the course needs

The advanced course teaches PostgreSQL as a client/server database. Its full
coursework requires real PostgreSQL backend sessions for independent
connections, transaction isolation, row locks, deadlocks, and Serializable
conflicts. The current Psycopg/threaded notebooks also require the Python
process (including the Marimo kernel) to run natively on the learner's machine
or in an isolated hosted runtime. The browser is the editing interface; browser
access to an editor does **not** mean that Python executes in the browser.

```text
 Learner's browser
 (authenticated editing UI)
          │
          │ authenticated, authorized session
          ▼
 ┌──────────────────────── Learner environment ─────────────────────────┐
 │ Marimo server + native Python kernel                                 │
 │ Psycopg / course Python code                                         │
 │          │ private learner network                                   │
 │          ▼                                                           │
 │ PostgreSQL service ───── private database storage                    │
 │ Real backend sessions, isolated from other learners                  │
 └──────────────────────────────────────────────────────────────────────┘
          ▲
          │ authentication, routing, isolation, limits, lifecycle
          │ and secret management are operator responsibilities
     Hosting platform / operator
```

In a local setup, native Python on the learner's machine connects through the
published localhost port. In a hosted setup, the browser connects to an
authenticated editing service, while the notebook kernel runs inside the
learner's isolated environment. The notebook container reaches PostgreSQL at
the database service hostname and port `5432`; it must not use its own
`localhost` to find the database.

## Execution-mode matrix

| Mode | What runs where | Course fit |
|---|---|---|
| Browser-only WASM / PGlite | Python or SQL runs in the browser against a browser-local database | Supports selected SQL lessons, but **not** the unchanged course: it does not provide the required real PostgreSQL backend sessions and threading behavior. |
| Local native Marimo + native or containerized PostgreSQL | Marimo/Python runs natively on the learner machine; PostgreSQL is a real server | Supports the intended backend and concurrency features. |
| Isolated hosted native Marimo + real PostgreSQL | Browser is the editing UI; Marimo/Python and PostgreSQL run in a private learner environment | Intended no-install learner experience; recommended architecture, **not implemented or provisioned here**. |

Marimo's WebAssembly/Pyodide mode does not turn the current Psycopg notebooks
into browser-only applications. Browser Pyodide cannot use ordinary raw TCP
sockets, and it does not support the `threading.Barrier` mechanism used by the
course's concurrency exercises. A future WASM-client design would need a
separately designed authenticated bridge to PostgreSQL, compatible packages,
and a revised concurrency implementation. That design has not been implemented
or validated here.

[PGlite](https://pglite.dev/) can be a useful optional browser-only SQL
alternative for selected lessons. Its single underlying connection is not a
substitute for independent PostgreSQL sessions in the multi-session
concurrency labs.

## Learner and operator responsibilities

**Learners** use the course notebooks and their assigned database credentials,
keep credentials out of notebook output and shared artifacts, and follow the
course's documented data-reset instructions. A database assignment does not
make arbitrary Python code safe to execute.

**Operators** must provide and maintain the platform around the course,
including:

- Authentication and per-learner routing to the correct editor and runtime.
- A hardened execution boundary for editable Python, plus resource limits.
- A private PostgreSQL instance, storage, network, and credentials for each
  logical learner environment.
- Network restrictions, secret isolation, idle shutdown, and defined
  persistence and reset policies.
- Safe lifecycle, backup, monitoring, and recovery procedures.

An actual browser-accessible editing service must be authenticated and
sandboxed; do not publicly expose an unrestricted Marimo edit server. Never
expose the Docker socket or platform-administrator secrets to learner code.
Compose alone does not deliver any of these hosting, authentication, execution
sandbox, resource, or lifecycle guarantees.

One logical learner environment should contain a Marimo/Python runtime and a
private PostgreSQL instance, storage, network, and credentials. A platform can
reuse one Compose template with distinct project names; it does not need a
separately authored YAML file or physical host for each learner. Compose is not
the only possible orchestrator. Multiple learner environments may share
managed host infrastructure without sharing learner database data. A separate
database alone is not an adequate sandbox for arbitrary editable Python.

## Current Compose file: local development only

The repository's `compose.yaml` is a **single-user local development
configuration**, not production-ready or multi-user-ready. It currently has:

- Fixed `container_name: goliath_pg_lab`.
- Explicit named volume `goliath_pgdata`.
- A default published host port of `54329` (bound to localhost).
- A PostgreSQL 18 data mount at `/var/lib/postgresql`, the image's volume target. Default `PGDATA` is `/var/lib/postgresql/18/docker`.

Distinct Compose project names do not remove the fixed container-name and
explicit-volume collisions or the risk of sharing the named volume; instances
using the default host port also conflict. A future hosted template must remove
or isolate explicit global names, avoid conflicting host ports, and separate
learner storage and credentials. Do not point this mount at a volume that was
initialized under `/var/lib/postgresql/data` without a backup and a reviewed
migration.

These are outstanding implementation requirements, not changes made by this
documentation. Do not move or reinitialize an existing volume, or point a new
image at an old data directory, without a backup and a reviewed migration.

## PostgreSQL version policy (November 17, 2026)

PostgreSQL **18.7** is the released baseline on this date, and the official
image lists `postgres:18.7-bookworm`. This repository currently uses the
floating-minor tag `postgres:18-bookworm`; it is not an exact 18.7 pin or an
image digest. Recommend an exact tested tag for reproducible deployments and,
for controlled releases, a verified image digest. No digest is configured or
specified here.

PostgreSQL 19 is at **RC 2**, with general availability planned for November
19, subject to change. Treat PostgreSQL 19 as a future compatibility target,
not a supported course runtime: the current Module 2 and Module 3 version
guards accept PostgreSQL 18 only. Adoption requires reviewing those guards,
bootstrap behavior, and image volume layout; running populated migration and
concurrency integration tests; and planning a proper major-version data
upgrade. Do not point a PostgreSQL 19 image at an existing PostgreSQL 18 data
directory.

## Official references

- [Marimo: WebAssembly](https://docs.marimo.io/guides/wasm/)
- [Marimo: Deploying](https://docs.marimo.io/guides/deploying/)
- [Pyodide: Sockets](https://pyodide.org/en/stable/usage/socket.html)
- [PGlite: Multi-tab workers](https://pglite.dev/docs/multi-tab-worker)
- [Docker Compose: Project name](https://docs.docker.com/compose/how-tos/project-name/)
- [Official PostgreSQL Docker image](https://hub.docker.com/_/postgres/)
- [PostgreSQL 18.7 and 19 RC 2 release announcement](https://www.postgresql.org/about/news/postgresql-187-1712-1616-1520-1425-and-19-rc-2-released-3442/)
