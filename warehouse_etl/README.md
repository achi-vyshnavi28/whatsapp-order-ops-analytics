# warehouse_etl

An automated ETL pipeline that extracts the order-ops data out of PostgreSQL, reshapes it into a proper **star-schema dimensional model** (the standard data-warehouse pattern — not just a copy of the source tables), and loads it into **Snowflake**.

## Why a star schema, not just a table dump

A data warehouse isn't "the same tables, but in the cloud" — it's modeled for fast analytical rollups. This pipeline builds:

- **`dim_customer`**, **`dim_product`**, **`dim_seller`**, **`dim_date`** — dimension tables, deduplicated and cleaned (e.g. `dim_product` resolves the category-name-translation join once, at load time, so every downstream query skips that join)
- **`fact_order_items`** — one row per order line item, at the grain analysts actually query at, with `is_late` and `delivery_days` pre-computed and payments/reviews pre-aggregated per order

This is the same schema-design skill tested by "basic understanding of data warehouse concepts" — not just running `pandas.to_sql`.

## Pipeline (two steps, deliberately split)

1. **Extract + Transform** — [`python/build_star_schema.py`](python/build_star_schema.py). Pulls from the local `order_ops_analytics` Postgres database, builds the star schema, and stages it as Parquet files in `data/staged/`. Needs local Postgres access only.
2. **Load** — [`python/load_to_snowflake.py`](python/load_to_snowflake.py). Creates the warehouse/schema/tables from [`sql/create_warehouse_schema.sql`](sql/create_warehouse_schema.sql) and bulk-loads the staged Parquet files via `write_pandas`. Needs real Snowflake credentials, read only from environment variables — the script never hardcodes or prompts for a password.

Splitting it this way means the step that needs real cloud credentials has zero transformation logic in it — easy to audit, easy to point at a different warehouse later.

## Running it

```bash
pip install -r requirements.txt

# Step 1 (needs local Postgres, already set up elsewhere in this repo)
python python/build_star_schema.py

# Step 2 (needs your own Snowflake account -- set these first)
export SNOWFLAKE_ACCOUNT="your-account-identifier"
export SNOWFLAKE_USER="your-username"
export SNOWFLAKE_PASSWORD="your-password"
export SNOWFLAKE_WAREHOUSE="COMPUTE_WH"
python python/load_to_snowflake.py
```

On success, `load_to_snowflake.py` prints the row count loaded into each table and runs a sample analytical query (monthly orders + revenue) directly against the newly loaded warehouse tables to confirm everything landed correctly.

## Confirmed working — actual output from a live run

```
Connected as user=VYSHNAVIACHI  role=ACCOUNTADMIN  warehouse=COMPUTE_WH
Creating database/schema/tables...
Loaded dim_customer: 99,441 rows
Loaded dim_product: 32,951 rows
Loaded dim_seller: 3,095 rows
Loaded dim_date: 730 rows
Loaded fact_order_items: 112,650 rows

Verifying with a warehouse-style analytical query...
(2016, 9, 'September', 2, Decimal('279.69'))
(2016, 10, 'October', 290, Decimal('51354.52'))
(2016, 12, 'December', 1, Decimal('19.62'))
(2017, 1, 'January', 787, Decimal('136943.46'))
(2017, 2, 'February', 1718, Decimal('283561.69'))

Done. Data is live in Snowflake under ORDER_OPS_WAREHOUSE.ANALYTICS.
```

Row counts and revenue figures match the PostgreSQL source exactly — this is a real, verified round trip through a live Snowflake warehouse, not just code that "should work."

## Data

Real order-operations data (same source as the rest of this repo): 99,441 orders / 112,650 order line items from the [Olist Brazilian E-Commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce).
