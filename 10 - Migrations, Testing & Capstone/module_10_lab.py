from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool


def migration_lab():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parent / "migrations").replace("%", "%%"))
    try:
        with engine.connect() as conn:
            config.attributes["connection"] = conn
            command.upgrade(config, "0001")
            with conn.begin():
                conn.execute(text("INSERT INTO orders (id, total_cents) VALUES (1, 1250)"))
            command.upgrade(config, "head")
            with conn.begin():
                upgraded = dict(conn.execute(text("SELECT id, total_cents, status FROM orders")).mappings().one())
            command.downgrade(config, "0001")
            with conn.begin():
                columns = [item["name"] for item in inspect(conn).get_columns("orders")]
                restored = dict(conn.execute(text("SELECT id, total_cents FROM orders")).mappings().one())
                revision = conn.scalar(text("SELECT version_num FROM alembic_version"))
            return {"upgraded": upgraded, "downgraded_columns": columns,
                    "retained_row": restored, "final_revision": revision}
    finally:
        engine.dispose()
