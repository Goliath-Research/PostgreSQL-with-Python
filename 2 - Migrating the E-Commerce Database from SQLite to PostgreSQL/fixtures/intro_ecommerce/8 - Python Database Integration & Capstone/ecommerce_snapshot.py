"""Module 8 baseline and explicit SQLite handoff; importing does not write files."""

import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import io
import json
import math
import os
from pathlib import Path
import sqlite3
import subprocess
import time


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = ROOT / "1 - The Relational Model" / "messy_ecommerce_orders.csv"
TABLES = ("customers", "products", "warehouses", "orders", "order_items", "catalog_observations")
CONTRACT = "goliath-ecommerce-snapshot/v1"
REQUIRED = {"row_id", "order_id", "ordered_at", "order_status", "customer_email",
            "customer_name", "shipping_address", "warehouse_code", "warehouse_city",
            "sku", "product_name", "category", "unit_price", "quantity"}


def read_source(csv_path=DEFAULT_CSV):
    """Read exactly the bytes whose digest is returned, without modifying the CSV."""
    data = Path(csv_path).read_bytes()
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""))
    missing = REQUIRED - set(reader.fieldnames or [])
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    records = list(reader)
    if not records:
        raise ValueError("CSV is empty")
    return records, hashlib.sha256(data).hexdigest()


def build_application_database(records):
    def money(value):
        x = Decimal(value) * 100
        if not x.is_finite() or x != x.to_integral_value() or x < 0:
            raise ValueError("Invalid or fractional-cent source price")
        return int(x)

    def add(mapping, key, value):
        if not key or any(v == "" for v in (value if isinstance(value, tuple) else (value,))):
            raise ValueError("Required source metadata missing")
        if key in mapping and mapping[key] != value:
            raise ValueError("Conflicting metadata: " + str(key))
        mapping[key] = value

    customers, products, warehouses, orders = {}, {}, {}, {}
    for r in records:
        add(products, r["sku"], (r["product_name"], r["category"]))
        add(warehouses, r["warehouse_code"], r["warehouse_city"])
        if r["order_id"]:
            add(customers, r["customer_email"], r["customer_name"])
            add(orders, r["order_id"], (r["ordered_at"], r["order_status"], r["customer_email"], r["shipping_address"]))
        elif any(r[k] for k in ["ordered_at", "order_status", "customer_email", "customer_name", "shipping_address"]):
            raise ValueError("Ambiguous row without order_id")
    db = sqlite3.connect(":memory:", isolation_level=None)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA foreign_keys=ON")
        if db.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise RuntimeError("Foreign keys unavailable")
        db.executescript("""
            CREATE TABLE customers(customer_id INTEGER PRIMARY KEY,email TEXT NOT NULL UNIQUE,customer_name TEXT NOT NULL);
            CREATE TABLE products(sku TEXT NOT NULL PRIMARY KEY,product_name TEXT NOT NULL,category TEXT NOT NULL);
            CREATE TABLE warehouses(warehouse_code TEXT NOT NULL PRIMARY KEY,warehouse_city TEXT NOT NULL);
            CREATE TABLE orders(order_id TEXT NOT NULL PRIMARY KEY,ordered_at TEXT NOT NULL,order_status TEXT NOT NULL,
                customer_id INTEGER NOT NULL REFERENCES customers(customer_id) ON DELETE RESTRICT,shipping_address_snapshot TEXT NOT NULL);
            CREATE TABLE order_items(source_row_id INTEGER PRIMARY KEY,order_id TEXT NOT NULL REFERENCES orders(order_id) ON DELETE RESTRICT,
                line_no INTEGER NOT NULL CHECK(typeof(line_no)='integer' AND line_no>0),sku TEXT NOT NULL REFERENCES products(sku) ON DELETE RESTRICT,
                warehouse_code TEXT NOT NULL REFERENCES warehouses(warehouse_code) ON DELETE RESTRICT,
                unit_price_cents INTEGER NOT NULL CHECK(typeof(unit_price_cents)='integer' AND unit_price_cents>=0),
                quantity INTEGER NOT NULL CHECK(typeof(quantity)='integer' AND quantity>0),UNIQUE(order_id,line_no));
            CREATE TABLE catalog_observations(source_row_id INTEGER PRIMARY KEY,sku TEXT NOT NULL REFERENCES products(sku) ON DELETE RESTRICT,
                warehouse_code TEXT NOT NULL REFERENCES warehouses(warehouse_code) ON DELETE RESTRICT,
                observed_price_cents INTEGER NOT NULL CHECK(typeof(observed_price_cents)='integer' AND observed_price_cents>=0),
                observed_quantity INTEGER NOT NULL CHECK(typeof(observed_quantity)='integer' AND observed_quantity>=0));
            CREATE INDEX orders_customer_idx ON orders(customer_id);
            CREATE INDEX items_sku_idx ON order_items(sku);
            """)
        db.execute("BEGIN")
        db.executemany("INSERT INTO customers(email,customer_name) VALUES (?,?)", sorted(customers.items()))
        ids = {r["email"]: r["customer_id"] for r in db.execute("SELECT * FROM customers")}
        db.executemany("INSERT INTO products VALUES (?,?,?)", [(k, *v) for k, v in products.items()])
        db.executemany("INSERT INTO warehouses VALUES (?,?)", list(warehouses.items()))
        db.executemany("INSERT INTO orders VALUES (?,?,?,?,?)", [(k, v[0], v[1], ids[v[2]], v[3]) for k, v in orders.items()])
        lines, seen = {}, set()
        for r in records:
            rid, price, qty = int(r["row_id"]), money(r["unit_price"]), int(r["quantity"])
            if rid in seen:
                raise ValueError("Duplicate source row_id")
            seen.add(rid)
            if r["order_id"]:
                oid = r["order_id"]
                lines[oid] = lines.get(oid, 0) + 1
                db.execute("INSERT INTO order_items VALUES (?,?,?,?,?,?,?)", (rid, oid, lines[oid], r["sku"], r["warehouse_code"], price, qty))
            else:
                db.execute("INSERT INTO catalog_observations VALUES (?,?,?,?,?)", (rid, r["sku"], r["warehouse_code"], price, qty))
        db.execute("COMMIT")
        return db
    except Exception:
        if db.in_transaction:
            db.execute("ROLLBACK")
        db.close()
        raise


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_database(db):
    """Inspect the backed-up main database, including SQLite-generated objects."""
    if [row[0] for row in db.execute("PRAGMA integrity_check")] != ["ok"]:
        raise ValueError("SQLite integrity check failed")
    if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("SQLite foreign-key check failed")
    counts = {name: db.execute('SELECT COUNT(*) FROM "' + name + '"').fetchone()[0] for name in TABLES}
    inventory = [
        dict(zip(("type", "name", "table", "sql"), row))
        for row in db.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_schema "
            "WHERE type IN ('table','view','index','trigger') ORDER BY type, name"
        )
    ]
    encoded = json.dumps(inventory, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return counts, inventory, hashlib.sha256(encoded).hexdigest()


def exporter_commit():
    """Report HEAD only when this checkout has no tracked changes."""
    try:
        clean = not subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=normal"],
            cwd=ROOT, timeout=2, stderr=subprocess.DEVNULL,
        )
        if clean:
            return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, timeout=2, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def _export_snapshot(source, destination, *, snapshot_kind, source_csv_sha256, timeout):
    if source.in_transaction:
        raise ValueError("Commit or roll back the source transaction before export")
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be positive")
    destination = Path(destination)
    destination.mkdir(mode=0o700)  # exclusive: never reuse an existing directory
    db_path = destination / "ecommerce_source.sqlite"
    manifest_path = destination / "source_manifest.json"
    temp_manifest = destination / ".source_manifest.tmp"
    owned = []
    try:
        source_counts = {name: source.execute('SELECT COUNT(*) FROM "' + name + '"').fetchone()[0] for name in TABLES}
        fd = os.open(db_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        owned.append(db_path)
        os.close(fd)
        target = sqlite3.connect(str(db_path), timeout=timeout)
        try:
            deadline = time.monotonic() + timeout

            def progress(status, remaining, total):
                if time.monotonic() >= deadline:
                    raise TimeoutError("SQLite backup timed out")

            source.backup(target, pages=128, progress=progress, sleep=0.05)
            target.execute("PRAGMA journal_mode=DELETE")
        finally:
            target.close()
        restored = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            counts, inventory, signature = inspect_database(restored)
        finally:
            restored.close()
        if counts != source_counts:
            raise ValueError("Source and restored core counts differ; retry with a stable source")
        manifest = {
            "contract_version": CONTRACT,
            "snapshot_kind": snapshot_kind,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_repository": "Goliath-Research/Introduction-to-Databases",
            "exporter_commit": exporter_commit(),
            "source_commit": None,
            "source_csv_sha256": source_csv_sha256,
            "database_sha256": file_sha256(db_path),
            "sqlite_version": sqlite3.sqlite_version,
            "table_counts": counts,
            "schema_signature": signature,
            "objects": inventory,
        }
        with temp_manifest.open("x", encoding="utf-8", newline="\n") as stream:
            owned.append(temp_manifest)
            json.dump(manifest, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.link(temp_manifest, manifest_path)
        owned.append(manifest_path)
        temp_manifest.unlink()
        return manifest
    except BaseException:
        for path in owned:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        try:
            destination.rmdir()
        except OSError:
            pass
        raise


def export_snapshot(source, destination, *, timeout=5.0):
    """Export a caller-owned connection's committed main database to a new directory."""
    return _export_snapshot(source, destination, snapshot_kind="live_connection",
                            source_csv_sha256=None, timeout=timeout)


def verify_snapshot(destination):
    """Validate a completed bundle against its manifest, without trusting file hashes alone."""
    destination = Path(destination)
    with (destination / "source_manifest.json").open(encoding="utf-8") as stream:
        manifest = json.load(stream)
    if manifest["contract_version"] != CONTRACT:
        raise ValueError("Unsupported snapshot contract")
    db_path = destination / "ecommerce_source.sqlite"
    if file_sha256(db_path) != manifest["database_sha256"]:
        raise ValueError("Database checksum mismatch")
    db = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        counts, inventory, signature = inspect_database(db)
    finally:
        db.close()
    if (counts != manifest["table_counts"] or inventory != manifest["objects"]
            or signature != manifest["schema_signature"]):
        raise ValueError("Database does not match manifest")
    return manifest


def rebuild_baseline(destination, csv_path=DEFAULT_CSV):
    records, digest = read_source(csv_path)
    db = build_application_database(records)
    try:
        return _export_snapshot(db, destination, snapshot_kind="baseline_rebuilt",
                                source_csv_sha256=digest, timeout=5.0)
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Rebuild the Module 8 baseline or verify a snapshot bundle.")
    commands = parser.add_subparsers(dest="command", required=True)
    rebuild = commands.add_parser("rebuild")
    rebuild.add_argument("destination", help="new bundle directory (must not exist)")
    rebuild.add_argument("--csv", default=str(DEFAULT_CSV), help="source CSV path")
    verify = commands.add_parser("verify")
    verify.add_argument("destination", help="completed bundle directory")
    args = parser.parse_args()
    manifest = rebuild_baseline(args.destination, args.csv) if args.command == "rebuild" else verify_snapshot(args.destination)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
