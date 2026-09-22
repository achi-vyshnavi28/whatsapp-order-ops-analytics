"""
Load step of the ETL pipeline. Run this yourself, after setting 4 environment
variables (SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD,
SNOWFLAKE_WAREHOUSE) in your own terminal -- this script never asks for or
hardcodes credentials, it only reads them from the environment.

Usage:
    python build_star_schema.py     # extract + transform (needs local Postgres)
    python load_to_snowflake.py     # load (needs your own Snowflake credentials)
"""
import os
from pathlib import Path

import pandas as pd
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas

ROOT = Path(__file__).resolve().parents[1]
STAGED = ROOT / "data" / "staged"
DDL_PATH = ROOT / "sql" / "create_warehouse_schema.sql"

REQUIRED_ENV = ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD", "SNOWFLAKE_WAREHOUSE"]

TABLES = ["dim_customer", "dim_product", "dim_seller", "dim_date", "fact_order_items"]


def get_connection():
    missing = [v for v in REQUIRED_ENV if not os.environ.get(v)]
    if missing:
        raise SystemExit(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Set them in your own terminal before running this script."
        )
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        # ACCOUNTADMIN is the role every new trial account's first user holds,
        # and CREATE DATABASE requires it (or SYSADMIN with the right grants).
        # Override with SNOWFLAKE_ROLE if your account uses a different setup.
        role=os.environ.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
    )


def run_ddl(conn) -> None:
    ddl = DDL_PATH.read_text(encoding="utf-8")
    # Splitting on ";" is safe here: the file has no string literals containing
    # ";" and its one multi-line trailing comment (the example query) contains
    # exactly one ";", so it collapses to a single chunk starting with "--"
    # that the filter below drops.
    statements = [s.strip() for s in ddl.split(";") if s.strip() and not s.strip().startswith("--")]
    cur = conn.cursor()
    for stmt in statements:
        cur.execute(stmt)
    cur.close()


def load_table(conn, name: str) -> int:
    df = pd.read_parquet(STAGED / f"{name}.parquet")
    # Snowflake's write_pandas expects uppercase column names by default
    # to match unquoted identifiers.
    df.columns = [c.upper() for c in df.columns]
    success, n_chunks, n_rows, _ = write_pandas(
        conn, df, table_name=name.upper(), database="ORDER_OPS_WAREHOUSE", schema="ANALYTICS"
    )
    if not success:
        raise RuntimeError(f"Failed to load {name}")
    return n_rows


def main() -> None:
    conn = get_connection()
    try:
        print("Creating database/schema/tables...")
        run_ddl(conn)

        for table in TABLES:
            n = load_table(conn, table)
            print(f"Loaded {table}: {n:,} rows")

        print("\nVerifying with a warehouse-style analytical query...")
        cur = conn.cursor()
        cur.execute(
            """
            SELECT d.year, d.month_name, COUNT(DISTINCT f.order_id) AS orders,
                   ROUND(SUM(f.price + f.freight_value), 2) AS revenue
            FROM ORDER_OPS_WAREHOUSE.ANALYTICS.fact_order_items f
            JOIN ORDER_OPS_WAREHOUSE.ANALYTICS.dim_date d ON d.date_key = f.date_key
            WHERE f.order_status NOT IN ('canceled', 'unavailable')
            GROUP BY d.year, d.month_name
            ORDER BY d.year, MONTH(d.full_date)
            LIMIT 5
            """
        )
        for row in cur.fetchall():
            print(row)
        cur.close()
        print("\nDone. Data is live in Snowflake under ORDER_OPS_WAREHOUSE.ANALYTICS.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
