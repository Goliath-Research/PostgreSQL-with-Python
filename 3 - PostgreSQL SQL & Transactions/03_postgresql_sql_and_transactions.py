# /// script
# requires-python = ">=3.11"
# dependencies = ["marimo>=0.11,<1", "psycopg[binary]>=3.2,<4", "python-dotenv>=1,<2"]
# ///

import marimo

__generated_with = "0.25.2"
app = marimo.App(
    width="medium",
    app_title="Module 3: PostgreSQL SQL & Transactions",
)


with app.setup(hide_code=True):
    import sys as _course_sys
    from pathlib import Path as _CoursePath

    _course_here = _CoursePath.cwd().resolve()
    for _course_candidate in (_course_here, *_course_here.parents):
        if (_course_candidate / "course_lab.py").is_file():
            _course_root = str(_course_candidate)
            if _course_root not in _course_sys.path:
                _course_sys.path.insert(0, _course_root)
            break
    else:
        raise RuntimeError("Open this notebook from the course repository.")
    import course_lab

    if course_lab.autostart_enabled():
        course_lab.attach()


@app.cell(hide_code=True)
def _(mo):
    _lab_panel, leave_lab = course_lab.leave_controls(mo)
    _lab_panel
    return (leave_lab,)


@app.cell(hide_code=True)
def _(leave_lab, mo):
    _lab_message = course_lab.release_if_requested(leave_lab.value)
    mo.stop(_lab_message is None)
    mo.md(_lab_message)
    return


@app.cell
def _():
    from pathlib import Path
    import sys
    import marimo as mo

    _module_dir = Path(__file__).resolve().parent
    if str(_module_dir) not in sys.path:
        sys.path.insert(0, str(_module_dir))
    import module_03_support as lab

    return Path, lab, mo


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Module 3: PostgreSQL SQL & Transactions
    ## Goliath Research Academy — PostgreSQL with Python

    This notebook reads migrated commerce data and runs transaction examples
    only against explicitly provisioned synthetic lab rows. Opening it does
    not read `.env`, connect, provision, experiment, clean up, or export.
    Read the companion `03_content.md` before submitting an action.

    ## 3.1 Readiness and read-only SQL
    Module 1 and Module 2 must **actually** be ready: preflight checks
    PostgreSQL 19 (or 18), the course roles, ownership, six relations and access.
    Configure and submit preflight below; a merged PR is not proof of readiness.
    `orders.ordered_at` has no timezone; amounts are integer cents.
    Order-item and catalog-observation keys have distinct meanings.
    Observations are not inventory and database key history does not prove
    original CSV provenance. No source rows are changed by this module.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 3.2 Expressions, strict types and result grain
    Try the read-only examples after preflight. `NULL = NULL` is unknown;
    `IS NULL` tests for null. Integer `5 / 2` gives `2`, while
    `5::numeric / 2` gives exact `2.5`. Explicit casts make type intent clear.
    Filtered aggregates count subsets; a CTE establishes a grain before a
    window calculation. A window retains input rows rather than grouping
    them away. Explain the grain before comparing totals.

    ## 3.3 Timezone-free timestamps and instants
    A timezone-free value does not identify an instant without an external
    policy. The examples interpret a **hypothetical** wall-clock literal
    in a named zone, not an imported order. `TIMESTAMPTZ` represents an
    instant displayed in the session timezone; it does not preserve the
    original zone label.

    ## 3.4 Provisioning, COMMIT and ROLLBACK
    Submit provisioning separately as `course_migrator`, which explicitly
    assumes `course_owner`. No existing commerce or probe privileges are
    changed. Each experiment allocates a fresh UUID and uses synthetic cents.
    The atomicity exercise contrasts persisted committed changes with changes
    that disappear after rollback.

    ## 3.5 Aborted transactions and savepoints
    An expected constraint failure aborts its transaction. The next command
    receives `25P02` until rollback. A savepoint confines a later expected
    failure so the outer transaction can continue and commit.

    ## 3.6 Isolation snapshots
    Two real connections coordinate a reader and writer. Read Committed
    acquires a snapshot for each statement; Repeatable Read retains the
    snapshot of its first query. Repeatable Read is not Serializable.

    ## 3.7 Row locks
    `FOR UPDATE NOWAIT` conflicts with an existing row lock (`55P03`).
    Opposite lock order can deadlock: either session may be the `40P01`
    victim. A timeout is not evidence of deadlock detection. Consistent
    acquisition order prevents that particular cycle.

    ## 3.8 Serializable and whole-transaction retries
    Two accounts begin with 100 cents each; the total must remain at least
    100. Both sessions read before independently considering a 100-cent
    debit. Serializable can reject a conflicting transaction with `40001`.
    Retry the whole transaction with fresh reads and bounded attempts; a
    new decision may legitimately reject the debit. Do not retry arbitrary
    failures, uncertain commits, or external side effects.

    ## 3.9 Evidence and cleanup
    Save each run UUID. Cleanup is a separate submission scoped to that UUID;
    failed cleanup is not success. Reports contain no credentials, DSNs,
    raw driver messages or business rows. A skipped test or blocked
    demonstration is not a pass.

    ## 3.10 Plans, GIN, vacuum, and a materialized view
    Submit **Planner, GIN, and refresh** after provisioning. The action reads
    `commerce` and writes only in `lab`. `EXPLAIN (ANALYZE, BUFFERS)` names the
    join node PostgreSQL chose and reports buffer hits. A `jsonb` column in
    `lab.module_03_search` gets a `GIN` index. An update leaves the previous
    tuple version behind; `VACUUM` reclaims that dead version and keeps the
    live row. `lab.module_03_category_totals` is a materialized view of product
    categories, replaced with `REFRESH MATERIALIZED VIEW`.

    ## 3.11 Triggers
    Submit **Triggers** after provisioning. The action writes only in `lab`.
    A `BEFORE UPDATE` trigger allows `PENDING` to `PAID`, `PAID` to `SHIPPED`,
    `PAID` to `CANCELLED`, and `PENDING` to `CANCELLED`. The change from `PAID`
    back to `PENDING` raises and is contained with a savepoint. An `AFTER UPDATE`
    trigger records the legal change in `lab.module_03_status_audit` and writes
    nothing for the rejected change. A second change inside a savepoint rolls
    back with its audit row. `INSTEAD OF INSERT` on `lab.module_03_line_entry`
    writes `lab.module_03_lines`.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.vstack([
        mo.md("### Join methods reported by EXPLAIN"),
        mo.mermaid("""
flowchart TD
    explain["EXPLAIN ANALYZE, BUFFERS"]
    explain --> nestedLoop[NestedLoop]
    explain --> hashJoin[HashJoin]
    explain --> mergeJoin[MergeJoin]
    nestedLoop --> buffers["Buffers: shared hits and reads"]
    hashJoin --> buffers
    mergeJoin --> buffers
"""),
    ])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.vstack([
        mo.md("### Trigger work inside the statement"),
        mo.mermaid("""
flowchart TD
    updateStatus[UPDATE status]
    updateStatus --> beforeUpdate[BEFORE UPDATE]
    beforeUpdate -->|legal| statusRow[status row]
    beforeUpdate -->|illegal| savepoint[savepoint restores the statement]
    statusRow --> afterUpdate[AFTER UPDATE]
    afterUpdate --> auditRow[audit row]
    insertView[INSERT on the lab view] --> insteadOf[INSTEAD OF INSERT]
    insteadOf --> lineTable[lab.module_03_lines]
"""),
    ])
    return


@app.cell
def _(Path, lab, mo):
    get_evidence, set_evidence = mo.state(None)
    session = {"config": None}

    def blocked(error=None):
        codes = ("permission_denied", "object_already_exists", "object_missing",
                 "connection_failed", "authentication_failed",
                 "statement_timeout_or_cancelled", "lock_unavailable_or_timeout",
                 "commit_outcome_unknown")
        category = next((code for code in codes
                         if error is not None and str(error).endswith(": " + code + ".")),
                        "verification_failed")
        return {"ok": False, "error": category}

    def configure(values):
        session["config"] = None
        if not values:
            return
        try:
            config = lab.Config.load(values["path"])
            result = lab.preflight(config)
            if result.get("ok"):
                session["config"] = config
            set_evidence(result)
        except lab.LabError as error:
            set_evidence(blocked(error))
        except Exception:
            set_evidence(blocked())

    def execute(values):
        if not values:
            return
        config = session["config"]
        if config is None:
            set_evidence(blocked())
            return
        action = values["action"]
        expected = ("READ" if action == "read" else "PROVISION" if action == "provision"
                    else "CLEANUP" if action == "cleanup" else "RUN")
        if values["confirmation"] != expected:
            set_evidence(blocked())
            return
        try:
            if action == "read":
                result = lab.read_sql_examples(config)
            elif action == "provision":
                result = lab.provision(config, lab.authorize(config, "provision"))
            elif action == "cleanup":
                run_id = values["run_id"]
                result = lab.cleanup(config, lab.authorize(config, "cleanup:" + run_id), run_id)
            else:
                result = lab.run_experiment(config, lab.authorize(config, "run:" + action), action)
            set_evidence(result)
        except lab.LabError as error:
            set_evidence(blocked(error))
        except Exception:
            set_evidence(blocked())

    config_form = mo.ui.dictionary({
        "path": mo.ui.text(value=str(Path(__file__).resolve().parent.parent / ".env"),
                           label="Path to .env"),
    }).form(submit_button_label="Load configuration and run read-only preflight",
            on_change=configure)
    action_form = mo.ui.dictionary({
        "action": mo.ui.dropdown(
            options={"Read-only SQL examples": "read", "Provision lab": "provision",
                     "Commit and rollback": "commit_rollback", "Savepoints": "savepoints",
                     "Isolation snapshots": "isolation", "Row locks": "locking",
                     "Serializable": "serializable",
                     "Planner, GIN, and refresh": "planner",
                     "Triggers": "triggers",
                     "Cleanup one run": "cleanup"},
            value="Read-only SQL examples", label="Action"),
        "run_id": mo.ui.text(label="Run UUID (cleanup only)"),
        "confirmation": mo.ui.text(label="Type READ, PROVISION, RUN, or CLEANUP as appropriate"),
    }).form(submit_button_label="Submit selected action", on_change=execute)
    return action_form, config_form, get_evidence


@app.cell(hide_code=True)
def _(action_form, config_form, mo):
    mo.vstack([
        mo.md("### Explicit submissions\nSubmitting configuration replaces prior authorization. "
              "Preflight is read-only. Each later action requires a separate submission."),
        config_form,
        action_form,
    ])
    return


@app.cell(hide_code=True)
def _(get_evidence, lab, mo):
    _evidence = get_evidence()
    if _evidence is None:
        _display = mo.md("### Latest evidence\nNo action has been submitted.")
    else:
        _report = lab.report_json(_evidence)
        _display = mo.vstack([mo.md("### Latest evidence"), mo.md(f"```json\n{_report}\n```"),
                              mo.download(data=_report, filename="module03-evidence.json",
                                          mimetype="application/json", label="Download redacted evidence")])
    _display
    return


if __name__ == "__main__":
    app.run()
