"""
Extract + Transform step of the ETL pipeline: pulls the OLTP-shaped data out
of the order_ops_analytics PostgreSQL database and reshapes it into a proper
dimensional (star schema) model -- the standard data-warehouse pattern,
distinct from just copying source tables 1:1.

Star schema:
    dim_customer, dim_product, dim_seller, dim_date  (dimensions)
    fact_order_items                                  (fact, grain = 1 row
                                                         per order line item)

Output: one Parquet file per table in warehouse_etl/data/staged/, which
load_to_snowflake.py then loads as-is (kept as a separate step so the load
step -- the one that needs real Snowflake credentials -- has zero
transformation logic in it).
"""
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[1]
STAGED = ROOT / "data" / "staged"
STAGED.mkdir(parents=True, exist_ok=True)

ENGINE = create_engine("postgresql+psycopg2://postgres:postgres@localhost:5432/order_ops_analytics")


def build_dim_customer() -> pd.DataFrame:
    df = pd.read_sql(
        "SELECT DISTINCT customer_id, customer_unique_id, customer_city, customer_state "
        "FROM customers", ENGINE,
    )
    return df


def build_dim_product() -> pd.DataFrame:
    df = pd.read_sql(
        """
        SELECT p.product_id,
               COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category_english,
               p.product_weight_g, p.product_length_cm, p.product_height_cm, p.product_width_cm
        FROM products p
        LEFT JOIN product_category_name_translation t
          ON t.product_category_name = p.product_category_name
        """,
        ENGINE,
    )
    return df


def build_dim_seller() -> pd.DataFrame:
    return pd.read_sql("SELECT seller_id, seller_city, seller_state FROM sellers", ENGINE)


def build_dim_date(min_date: str, max_date: str) -> pd.DataFrame:
    dates = pd.date_range(min_date, max_date, freq="D")
    return pd.DataFrame({
        "date_key": dates.strftime("%Y%m%d").astype(int),
        "full_date": dates,
        "year": dates.year,
        "month": dates.month,
        "month_name": dates.strftime("%B"),
        "day": dates.day,
        "day_of_week": dates.strftime("%A"),
        "is_weekend": dates.dayofweek.isin([5, 6]),
    })


def build_fact_order_items() -> pd.DataFrame:
    items = pd.read_sql(
        """
        SELECT oi.order_id, oi.order_item_id, oi.product_id, oi.seller_id,
               oi.price, oi.freight_value,
               o.customer_id, o.order_status, o.order_purchase_timestamp,
               o.order_delivered_customer_date, o.order_estimated_delivery_date
        FROM order_items oi
        JOIN orders o ON o.order_id = oi.order_id
        """,
        ENGINE,
        parse_dates=["order_purchase_timestamp", "order_delivered_customer_date", "order_estimated_delivery_date"],
    )

    payments = pd.read_sql(
        "SELECT order_id, SUM(payment_value) AS payment_value, "
        "STRING_AGG(DISTINCT payment_type, ',') AS payment_types "
        "FROM order_payments GROUP BY order_id",
        ENGINE,
    )
    reviews = pd.read_sql(
        "SELECT order_id, AVG(review_score) AS review_score FROM order_reviews GROUP BY order_id", ENGINE
    )

    fact = items.merge(payments, on="order_id", how="left").merge(reviews, on="order_id", how="left")
    fact["date_key"] = fact["order_purchase_timestamp"].dt.strftime("%Y%m%d").astype(int)
    fact["is_late"] = fact["order_delivered_customer_date"] > fact["order_estimated_delivery_date"]
    fact["delivery_days"] = (
        fact["order_delivered_customer_date"] - fact["order_purchase_timestamp"]
    ).dt.total_seconds() / 86400

    return fact[[
        "order_id", "order_item_id", "customer_id", "product_id", "seller_id", "date_key",
        "order_status", "price", "freight_value", "payment_value", "payment_types",
        "review_score", "is_late", "delivery_days",
    ]]


def main() -> None:
    dim_customer = build_dim_customer()
    dim_product = build_dim_product()
    dim_seller = build_dim_seller()
    fact = build_fact_order_items()

    min_date = fact["date_key"].astype(str).min()
    max_date = fact["date_key"].astype(str).max()
    min_date = f"{min_date[:4]}-{min_date[4:6]}-{min_date[6:]}"
    max_date = f"{max_date[:4]}-{max_date[4:6]}-{max_date[6:]}"
    dim_date = build_dim_date(min_date, max_date)

    tables = {
        "dim_customer": dim_customer,
        "dim_product": dim_product,
        "dim_seller": dim_seller,
        "dim_date": dim_date,
        "fact_order_items": fact,
    }
    for name, df in tables.items():
        out = STAGED / f"{name}.parquet"
        df.to_parquet(out, index=False)
        print(f"{name}: {len(df):,} rows -> {out}")


if __name__ == "__main__":
    main()
