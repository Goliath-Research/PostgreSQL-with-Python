import argparse
from getpass import getpass
import os

from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import SQLAlchemyError


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quantity", type=int, default=3, choices=range(1, 6))
    args = parser.parse_args()
    engine = None
    try:
        url = URL.create("postgresql+psycopg", username="course_app",
                         password=getpass("course_app password: "),
                         host=os.getenv("PGHOST", "localhost"),
                         port=int(os.getenv("PGPORT", "54329")),
                         database=os.getenv("PGDATABASE", "goliath_ecommerce"))
        engine = create_engine(url, hide_parameters=True, connect_args={"connect_timeout": 5})
        with engine.begin() as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            result = conn.execute(text("""
                SELECT current_user AS role, CAST(:quantity AS integer) AS quantity,
                       current_setting('transaction_read_only') AS read_only
            """), {"quantity": args.quantity}).mappings().one()
            if result["role"] != "course_app" or result["read_only"] != "on":
                raise SystemExit("Unexpected role or transaction mode.")
        print(dict(result))
    except (SQLAlchemyError, ImportError, ValueError):
        raise SystemExit("Probe failed. Check Psycopg, server settings, and course_app credentials.") from None
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    main()
