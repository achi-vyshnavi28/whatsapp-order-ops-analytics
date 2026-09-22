"""
Loads the raw Olist CSVs into the order_ops_analytics PostgreSQL database.
Run after sql/01_schema.sql has been applied.
"""
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PSQL = r"C:\Program Files\PostgreSQL\16\bin\psql.exe"

DB = {
    "host": "localhost",
    "port": "5432",
    "user": "postgres",
    "dbname": "order_ops_analytics",
}

# Load order respects foreign-key dependencies.
LOAD_ORDER = [
    ("customers", "olist_customers_dataset.csv"),
    ("sellers", "olist_sellers_dataset.csv"),
    ("product_category_name_translation", "product_category_name_translation.csv"),
    ("products", "olist_products_dataset.csv"),
    ("orders", "olist_orders_dataset.csv"),
    ("order_items", "olist_order_items_dataset.csv"),
    ("order_payments", "olist_order_payments_dataset.csv"),
    ("order_reviews", "olist_order_reviews_dataset.csv"),
    ("geolocation", "olist_geolocation_dataset.csv"),
]


def run_copy(table: str, csv_file: str) -> None:
    csv_path = (RAW_DIR / csv_file).as_posix()
    copy_cmd = f"\\copy {table} FROM '{csv_path}' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')"
    cmd = [
        PSQL,
        "-h", DB["host"],
        "-p", DB["port"],
        "-U", DB["user"],
        "-d", DB["dbname"],
        "-c", copy_cmd,
    ]
    env = os.environ.copy()
    env["PGPASSWORD"] = os.environ.get("PGPASSWORD", "postgres")
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    print(f"[{table}] {result.stdout.strip() or result.stderr.strip()}")
    if result.returncode != 0:
        raise RuntimeError(f"Failed loading {table}: {result.stderr}")


def main() -> None:
    for table, csv_file in LOAD_ORDER:
        run_copy(table, csv_file)
    print("\nAll tables loaded.")


if __name__ == "__main__":
    main()
