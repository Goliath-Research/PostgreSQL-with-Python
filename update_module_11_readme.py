from pathlib import Path

path = Path("README.md")
original = path.read_bytes()
newline = "\r\n" if b"\r\n" in original else "\n"
text = original.decode("utf-8").replace("\r\n", "\n")
replacements = [('this 10-module advanced course', 'this 11-module advanced course'), ('## 2. Ten-Module Syllabus (Three Stages)', '## 2. Eleven-Module Syllabus (Four Stages)'), ('| **10** | `10 - Migrations, Testing & Capstone/10_migrations_testing_and_capstone.py` | Alembic migrations, integration tests, reporting, and the dual-deliverable application capstone |\n', '| **10** | `10 - Migrations, Testing & Capstone/10_migrations_testing_and_capstone.py` | Alembic migrations, integration tests, reporting, and the dual-deliverable application capstone |\n\n### Stage D — Model Context Protocol Integration\n| Module | Directory & Script | Focus |\n| :---: | :--- | :--- |\n| **11** | `11 - MCP Servers over PostgreSQL & DuckDB/11_mcp_servers.py` | Read-only MCP tools and a curated reporting resource; local stdio client, bounded DuckDB aggregation, protocol tests, and opt-in PostgreSQL privilege checks |\n\nModule 11 follows the Module 10 capstone. Start with the synthetic fixture (no PostgreSQL server or LLM account required), then optionally run the separate disposable PostgreSQL lab as `mcp_analyst`. See [the Module 11 guide](11%20-%20MCP%20Servers%20over%20PostgreSQL%20%26%20DuckDB/11_content.md) for installation, client commands, and verification. The lab does not expose arbitrary SQL or write tools and does not modify the course `commerce` schema.\n')]
if all(text.count(after) == 1 for _, after in replacements):
    print("README already has the Module 11 update.")
else:
    for before, after in replacements:
        if text.count(before) != 1:
            raise SystemExit(f"README unchanged: expected exactly one match for {before!r}")
        text = text.replace(before, after, 1)
    path.write_bytes(text.replace("\n", newline).encode("utf-8"))
    print("Updated README.md; review with git diff -- README.md")
