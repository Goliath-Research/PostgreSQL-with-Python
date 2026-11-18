# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo>=0.11,<1",
#     "duckdb>=2.0.0",
#     "psycopg[binary]>=3.2,<4",
#     "python-dotenv>=1,<2",
# ]
# ///

import marimo

__generated_with = "0.25.2"
app = marimo.App(
    width="medium",
    app_title="Module 4: DuckDB PostgreSQL Connection",
)


@app.cell
def _():
    import json
    from pathlib import Path
    import sys
    import marimo as mo

    _module_dir = Path(__file__).resolve().parent
    if str(_module_dir) not in sys.path:
        sys.path.insert(0, str(_module_dir))
    import module_04_support as lab

    return Path, json, lab, mo


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        # Module 4: DuckDB PostgreSQL Connection
        ## Goliath Research Academy — PostgreSQL with Python

        Use DuckDB to read the PostgreSQL database migrated in Module 2. Opening this notebook does not read `.env`, install extensions, or connect to PostgreSQL automatically. Read the companion `04_content.md` before submitting an action.

        | Section | Exercise | Evidence |
        | :--- | :--- | :--- |
        | **4.1** | Load the PostgreSQL extension and attach read-only | Remote role (`course_analyst`), database (`goliath_ecommerce`), version, read-only transaction mode |
        | **4.2** | Run DuckDB SQL over attached data | Filtered order-line count (`quantity >= 2`) and `POSTGRES_SCAN` plan indicator |
        | **4.3** | Execute SQL in PostgreSQL explicitly (`postgres_query`) | PostgreSQL session settings and server-side ordered limit (`ORDER BY order_item_id LIMIT n`) |
        | **4.4** | Compute locally after extracting a sample | Local `HUGEINT` aggregation succeeds in DuckDB after `DETACH course_pg` |

        ### 4.1 Load and Attach (`course_analyst`)
        Select **Install / load extension** if needed to run `INSTALL postgres` and `LOAD postgres` explicitly. Then select **Run read-only lab** and submit. `Settings.load()` enforces the `course_analyst` identity and `run()` attaches `commerce` under `course_pg` with `READ_ONLY` and `default_transaction_read_only=on`.

        ### 4.2 Attached Table Scan vs. 4.3 Explicit Remote Query (`postgres_query`) vs. 4.4 Local Aggregation After `DETACH`
        - **Attached Scan (`SCAN`):** Queries `course_pg.commerce.order_items WHERE quantity >= 2` at order-line grain and inspects `EXPLAIN` for `POSTGRES_SCAN`.
        - **Explicit Remote Query (`postgres_query`):** Sends `SELECT order_item_id, unit_price_cents, quantity FROM commerce.order_items ORDER BY order_item_id LIMIT {limit}` to PostgreSQL to materialize an in-memory `line_sample` table in DuckDB.
        - **Local Aggregation After `DETACH`:** Executes `DETACH course_pg` and then computes `count(*)` and `sum(CAST(unit_price_cents AS HUGEINT) * CAST(quantity AS HUGEINT))` strictly inside DuckDB from `line_sample`.
        """
    )
    return


@app.cell
def _(Path, lab, mo):
    get_evidence, set_evidence = mo.state(None)

    def execute_action(values):
        if not values:
            return
        action = values["action"]
        try:
            if action == "install":
                result = {"ok": True, "action": "install_extension", **lab.install_extension()}
            else:
                limit = int(values["limit"])
                report = lab.run(values["path"], limit)
                result = {"ok": True, "action": "run_read_only_lab", **report}
            set_evidence(result)
        except (lab.LabError, ValueError) as exc:
            set_evidence({"ok": False, "action": action, "error": str(exc)})
        except Exception:
            set_evidence(
                {
                    "ok": False,
                    "action": action,
                    "error": "Unexpected failure; raw driver messages are withheld to protect credentials.",
                }
            )

    lab_form = mo.ui.dictionary(
        {
            "action": mo.ui.dropdown(
                options={
                    "Install / load extension": "install",
                    "Run read-only lab": "run",
                },
                value="Run read-only lab",
                label="Action",
            ),
            "path": mo.ui.text(
                value=str(Path(__file__).resolve().parent.parent / ".env"),
                label="Path to repository .env",
            ),
            "limit": mo.ui.number(
                start=1,
                stop=lab.MAX_ROWS,
                step=1,
                value=25,
                label=f"Sample row limit (1 to {lab.MAX_ROWS})",
            ),
        }
    ).form(submit_button_label="Submit Module 4 action", on_change=execute_action)

    return get_evidence, lab_form


@app.cell(hide_code=True)
def _(lab_form, mo):
    mo.vstack(
        [
            mo.md(
                """
                ### Explicit Lab Submission
                Choose **Install / load extension** first if the DuckDB `postgres` extension is not yet cached locally, then choose **Run read-only lab** and click **Submit Module 4 action**.
                """
            ),
            lab_form,
        ]
    )
    return


@app.cell(hide_code=True)
def _(get_evidence, json, mo):
    _evidence = get_evidence()
    if _evidence is None:
        _display = mo.callout(
            mo.md("### Latest Evidence\nNo action has been submitted yet."),
            kind="neutral",
        )
    else:
        _report_str = json.dumps(_evidence, indent=2, sort_keys=True)
        _kind = "success" if _evidence.get("ok") else "danger"
        _display = mo.vstack(
            [
                mo.callout(
                    mo.md(
                        "**Module 4 Action Succeeded**"
                        if _evidence.get("ok")
                        else f"**Module 4 Action Blocked:** {_evidence.get('error', 'Verification failed.')}"
                    ),
                    kind=_kind,
                ),
                mo.md(f"```json\n{_report_str}\n```"),
                mo.download(
                    data=_report_str.encode("utf-8"),
                    filename="module04-evidence.json",
                    mimetype="application/json",
                    label="Download redacted evidence (JSON)",
                ),
            ]
        )
    _display
    return


if __name__ == "__main__":
    app.run()
