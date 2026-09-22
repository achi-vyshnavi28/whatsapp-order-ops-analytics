"""
Interactive order-operations dashboard (Streamlit).

Reads directly from the raw Olist CSVs shipped in this repo (data/raw/) --
no database required, so it runs anywhere this repo is cloned, including
Streamlit Community Cloud.
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

st.set_page_config(page_title="Order Ops Dashboard", page_icon="\U0001F4E6", layout="wide")


@st.cache_data
def load_data():
    customers = pd.read_csv(RAW / "olist_customers_dataset.csv")
    orders = pd.read_csv(
        RAW / "olist_orders_dataset.csv",
        parse_dates=["order_purchase_timestamp", "order_delivered_customer_date", "order_estimated_delivery_date"],
    )
    items = pd.read_csv(RAW / "olist_order_items_dataset.csv")
    reviews = pd.read_csv(RAW / "olist_order_reviews_dataset.csv")
    products = pd.read_csv(RAW / "olist_products_dataset.csv")
    sellers = pd.read_csv(RAW / "olist_sellers_dataset.csv")
    cat_map = pd.read_csv(RAW / "product_category_name_translation.csv")

    orders = orders.merge(customers[["customer_id", "customer_state"]], on="customer_id")
    orders["is_late"] = orders["order_delivered_customer_date"] > orders["order_estimated_delivery_date"]

    items_full = items.merge(orders[["order_id", "order_status", "order_purchase_timestamp"]], on="order_id")
    items_full = items_full[~items_full.order_status.isin(["canceled", "unavailable"])]

    products = products.merge(cat_map, on="product_category_name", how="left")
    products["category_en"] = products["product_category_name_english"].fillna(
        products["product_category_name"]
    ).fillna("unknown")

    items_seller = items.merge(sellers[["seller_id", "seller_state"]], on="seller_id")
    reviews_dedup = reviews.drop_duplicates(subset=["review_id", "order_id"])

    return orders, items, items_full, items_seller, reviews_dedup, products, sellers


orders, items_raw, items_full, items_seller, reviews, products, sellers = load_data()

st.title("Order Ops Dashboard")
st.caption(
    "Real order, delivery, and review data from the Olist Brazilian E-Commerce dataset (2016–2018), "
    "used as a structural analogue for a WhatsApp-first SMB order platform's merchant-order-delivery "
    "operations. [Full case study & repo](https://github.com/achi-vyshnavi28/whatsapp-order-ops-analytics)."
)

# ---------------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------------
# KPI card matches the Power BI "Total Revenue"/"Total Orders" measures exactly: no order-status
# filter (SUM over every order_items row). The monthly trend chart below deliberately excludes
# canceled/unavailable orders instead, same as sql/02_analysis_queries.sql Q1.
total_revenue = (items_raw["price"] + items_raw["freight_value"]).sum()
total_orders = orders["order_id"].nunique()
avg_review = reviews["review_score"].mean()

delivered = orders[(orders.order_status == "delivered") & orders.order_delivered_customer_date.notna()]
repeat_customers = orders.merge(
    pd.read_csv(RAW / "olist_customers_dataset.csv")[["customer_id", "customer_unique_id"]], on="customer_id"
)
order_counts = repeat_customers[~repeat_customers.order_status.isin(["canceled", "unavailable"])].groupby(
    "customer_unique_id"
)["order_id"].nunique()
repeat_rate = (order_counts >= 2).mean() * 100

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Revenue", f"R$ {total_revenue / 1e6:.2f}M")
c2.metric("Total Orders", f"{total_orders:,}")
c3.metric("Avg Review Score", f"{avg_review:.2f} / 5")
c4.metric("Repeat-Purchase Rate", f"{repeat_rate:.1f}%", help="% of unique customers who ordered more than once")

st.divider()

# ---------------------------------------------------------------------------
# Monthly revenue trend
# ---------------------------------------------------------------------------
st.subheader("Monthly Order Revenue")
valid_items = items_full.copy()
valid_items["month"] = valid_items["order_purchase_timestamp"].dt.to_period("M").dt.to_timestamp()
monthly = (
    valid_items.groupby("month")
    .apply(lambda d: (d["price"] + d["freight_value"]).sum())
    .reset_index(name="revenue")
)
monthly = monthly[(monthly.month >= "2017-01-01") & (monthly.month <= "2018-08-01")]
fig = px.line(monthly, x="month", y="revenue", markers=True)
fig.update_layout(yaxis_title="Revenue (R$)", xaxis_title="", height=380)
fig.update_traces(line_color="#0f7a6c")
st.plotly_chart(fig, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Delivery SLA + Revenue-at-risk what-if (interactive)
# ---------------------------------------------------------------------------
left, right = st.columns([1.3, 1])

with left:
    st.subheader("Delivery SLA by State")
    by_state = (
        delivered.groupby("customer_state")
        .agg(delivered_orders=("order_id", "count"), late_pct=("is_late", "mean"))
        .query("delivered_orders >= 30")
        .sort_values("late_pct", ascending=False)
        .reset_index()
    )
    by_state["late_pct"] = by_state["late_pct"] * 100
    fig2 = px.bar(by_state, x="late_pct", y="customer_state", orientation="h", color="late_pct",
                  color_continuous_scale=["#2e9e5b", "#c9791f", "#c1443a"])
    fig2.update_layout(yaxis={"categoryorder": "total ascending"}, xaxis_title="Late-delivery rate (%)",
                        yaxis_title="", height=560, coloraxis_showscale=False)
    st.plotly_chart(fig2, use_container_width=True)

with right:
    st.subheader("Revenue-at-Risk Calculator")
    st.caption("Same formula as the Excel model — move the sliders to stress-test the assumptions.")

    total_delivered = len(delivered)
    late_delivered = int(delivered["is_late"].sum())
    avg_order_value = (items_full["price"] + items_full["freight_value"]).sum() / total_orders
    current_late_rate = late_delivered / total_delivered * 100

    st.metric("Current late-delivery rate", f"{current_late_rate:.1f}%")

    target_sla = st.slider("Target late-delivery rate (%)", 1.0, 15.0, 5.0, 0.5)
    loss_rate = st.slider("Est. repeat-purchase loss per late delivery (%)", 5, 40, 15, 1) / 100
    lifetime_orders = st.slider("Est. avg customer lifetime orders", 1.0, 5.0, 2.5, 0.1)

    orders_to_shift = max(late_delivered - target_sla / 100 * total_delivered, 0)
    revenue_at_risk = late_delivered * avg_order_value * loss_rate * lifetime_orders
    revenue_recoverable = orders_to_shift * avg_order_value * loss_rate * lifetime_orders

    st.metric("Revenue currently at risk", f"R$ {revenue_at_risk:,.0f}")
    st.metric(f"Recoverable by hitting {target_sla:.1f}% SLA", f"R$ {revenue_recoverable:,.0f}",
              delta=f"{orders_to_shift:,.0f} orders to shift")

st.divider()

# ---------------------------------------------------------------------------
# Sellers + categories
# ---------------------------------------------------------------------------
left2, right2 = st.columns(2)

with left2:
    st.subheader("Top Sellers by Revenue")
    seller_rev = items_seller.merge(orders[["order_id", "order_status"]], on="order_id")
    seller_rev = seller_rev[seller_rev.order_status == "delivered"]
    top_sellers = (
        seller_rev.groupby(["seller_id", "seller_state"])
        .agg(orders=("order_id", "nunique"), revenue=("price", "sum"))
        .reset_index()
        .sort_values("revenue", ascending=False)
        .head(10)
    )
    top_sellers["seller_id"] = top_sellers["seller_id"].str[:10] + "…"
    top_sellers["revenue"] = top_sellers["revenue"].map(lambda v: f"R$ {v:,.2f}")
    st.dataframe(top_sellers, hide_index=True, use_container_width=True)

with right2:
    st.subheader("Lowest-Rated Categories")
    cat_reviews = items_full.merge(products[["product_id", "category_en"]], on="product_id").merge(
        reviews[["order_id", "review_score"]], on="order_id"
    )
    by_cat = (
        cat_reviews.groupby("category_en")
        .agg(n=("review_score", "count"), avg_review=("review_score", "mean"))
        .query("n >= 30")
        .sort_values("avg_review")
        .head(10)
        .reset_index()
    )
    fig3 = px.bar(by_cat, x="avg_review", y="category_en", orientation="h", range_x=[0, 5],
                  color_discrete_sequence=["#c1443a"])
    fig3.update_layout(yaxis={"categoryorder": "total descending"}, xaxis_title="Avg review score",
                        yaxis_title="", height=380)
    st.plotly_chart(fig3, use_container_width=True)

st.divider()
st.caption(
    "Data source: [Olist Brazilian E-Commerce Public Dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) "
    "(CC BY-NC-SA 4.0). Built with Streamlit, Pandas, and Plotly."
)
