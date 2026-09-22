"""
Extract + Transform step: pulls the same order-ops data out of PostgreSQL
and reshapes it into genuine denormalized DOCUMENTS -- one JSON document per
order, with line items, payment info, and review embedded inline. This is
the actual point of a document database: model for how the data is *read*
(a whole order at once), not for update-anomaly-free normalization the way
the relational schema is.

Contrast with warehouse_etl/, which models the SAME source data as a
normalized star schema for Snowflake -- deliberately different modeling
disciplines for the same underlying facts, on purpose.

Output: nosql_mongo/data/staged/orders.jsonl.gz (one JSON object per line,
gzip-compressed -- ~75MB uncompressed shrinks to ~16MB), consumed by
load_to_mongodb.py.
"""
import gzip
import json
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[1]
STAGED = ROOT / "data" / "staged"
STAGED.mkdir(parents=True, exist_ok=True)

ENGINE = create_engine("postgresql+psycopg2://postgres:postgres@localhost:5432/order_ops_analytics")


def fetch_base() -> pd.DataFrame:
    return pd.read_sql(
        """
        SELECT o.order_id, o.order_status, o.order_purchase_timestamp,
               o.order_delivered_customer_date, o.order_estimated_delivery_date,
               c.customer_unique_id, c.customer_city, c.customer_state
        FROM orders o
        JOIN customers c ON c.customer_id = o.customer_id
        """,
        ENGINE,
        parse_dates=["order_purchase_timestamp", "order_delivered_customer_date", "order_estimated_delivery_date"],
    )


def fetch_items() -> pd.DataFrame:
    return pd.read_sql(
        """
        SELECT oi.order_id, oi.product_id, oi.seller_id, oi.price, oi.freight_value,
               COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category,
               s.seller_state
        FROM order_items oi
        JOIN products p ON p.product_id = oi.product_id
        LEFT JOIN product_category_name_translation t ON t.product_category_name = p.product_category_name
        JOIN sellers s ON s.seller_id = oi.seller_id
        """,
        ENGINE,
    )


def fetch_payments() -> pd.DataFrame:
    return pd.read_sql(
        "SELECT order_id, payment_type, payment_installments, payment_value FROM order_payments", ENGINE
    )


def fetch_reviews() -> pd.DataFrame:
    return pd.read_sql(
        "SELECT DISTINCT ON (order_id) order_id, review_score, review_comment_title, review_comment_message "
        "FROM order_reviews ORDER BY order_id, review_creation_date DESC",
        ENGINE,
    )


def build_document(order_row, items_group, payments_group, review_row) -> dict:
    is_late = None
    delivery_days = None
    if pd.notna(order_row.order_delivered_customer_date):
        is_late = bool(order_row.order_delivered_customer_date > order_row.order_estimated_delivery_date)
        delivery_days = round(
            (order_row.order_delivered_customer_date - order_row.order_purchase_timestamp).total_seconds() / 86400, 2
        )

    items = [
        {
            "product_id": r.product_id,
            "category": r.category,
            "seller_id": r.seller_id,
            "seller_state": r.seller_state,
            "price": float(r.price),
            "freight_value": float(r.freight_value),
        }
        for r in items_group.itertuples()
    ]
    total_value = round(sum(i["price"] + i["freight_value"] for i in items), 2)

    payments = [
        {
            "type": r.payment_type,
            "installments": int(r.payment_installments),
            "value": float(r.payment_value),
        }
        for r in payments_group.itertuples()
    ]

    review = None
    if review_row is not None:
        review = {
            "score": int(review_row.review_score) if pd.notna(review_row.review_score) else None,
            "title": review_row.review_comment_title if pd.notna(review_row.review_comment_title) else None,
            "message": review_row.review_comment_message if pd.notna(review_row.review_comment_message) else None,
        }

    return {
        "_id": order_row.order_id,
        "status": order_row.order_status,
        "purchased_at": order_row.order_purchase_timestamp.isoformat() if pd.notna(order_row.order_purchase_timestamp) else None,
        "delivered_at": order_row.order_delivered_customer_date.isoformat() if pd.notna(order_row.order_delivered_customer_date) else None,
        "estimated_delivery": order_row.order_estimated_delivery_date.isoformat() if pd.notna(order_row.order_estimated_delivery_date) else None,
        "is_late": is_late,
        "delivery_days": delivery_days,
        "customer": {
            "unique_id": order_row.customer_unique_id,
            "city": order_row.customer_city,
            "state": order_row.customer_state,
        },
        "items": items,
        "item_count": len(items),
        "total_value": total_value,
        "payments": payments,
        "review": review,
    }


def main() -> None:
    base = fetch_base()
    items = fetch_items().groupby("order_id")
    payments = fetch_payments().groupby("order_id")
    reviews = fetch_reviews().set_index("order_id")

    empty_items = pd.DataFrame(columns=["product_id", "category", "seller_id", "seller_state", "price", "freight_value"])
    empty_payments = pd.DataFrame(columns=["payment_type", "payment_installments", "payment_value"])

    out_path = STAGED / "orders.jsonl.gz"
    n = 0
    with gzip.open(out_path, "wt", encoding="utf-8") as f:
        for row in base.itertuples():
            items_group = items.get_group(row.order_id) if row.order_id in items.groups else empty_items
            payments_group = payments.get_group(row.order_id) if row.order_id in payments.groups else empty_payments
            review_row = reviews.loc[row.order_id] if row.order_id in reviews.index else None
            doc = build_document(row, items_group, payments_group, review_row)
            f.write(json.dumps(doc) + "\n")
            n += 1

    print(f"Wrote {n:,} order documents -> {out_path}")


if __name__ == "__main__":
    main()
