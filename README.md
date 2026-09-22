# whatsapp-order-ops-analytics

A merchant order-operations analytics project built to demonstrate a **Data Analyst (SQL, Python & Business Intelligence)** skill set: complex SQL, Python EDA + automated reporting, Excel financial modeling, and a live Power BI dashboard — applied to a WhatsApp-first SMB order platform's core problem of turning conversational order and delivery data into operational intelligence for small merchants.

**Why this dataset:** a WhatsApp-first order platform needs to turn conversational order + delivery data into operational intelligence for small merchants. [Olist](https://olist.com) solves a structurally identical problem — it connects small/medium merchants to marketplaces and coordinates fulfillment and delivery on their behalf. Its public dataset (100k+ real, anonymized Brazilian e-commerce orders, 2016–2018) is used here as a stand-in for that kind of merchant-order-delivery data, so every query and chart in this repo answers a question that business would actually ask.

**Start here:** [`docs/case_study.md`](docs/case_study.md) — a narrative write-up of the analysis (business question → findings → quantified revenue impact → recommendations), not just raw output.

**Live dashboard:** [Deploy on Streamlit Community Cloud](https://share.streamlit.io) pointing at `streamlit_app/app.py` in this repo → link it here once deployed.

## Skills demonstrated → where to find them

| Skill | Where |
|---|---|
| Complex SQL: multi-table joins, subqueries, CTEs, window functions | [`sql/02_analysis_queries.sql`](sql/02_analysis_queries.sql) — 9 queries, all run against live PostgreSQL |
| PostgreSQL | [`sql/01_schema.sql`](sql/01_schema.sql) — full schema with FKs and indexes, loaded via [`python/load_data.py`](python/load_data.py) |
| Python for data analysis (Pandas, NumPy, Matplotlib/Seaborn) | [`python/eda_analysis.py`](python/eda_analysis.py) — cleaning, EDA, SciPy statistical tests |
| Automated reporting | `eda_analysis.py` generates [`reports/eda_report.md`](reports/eda_report.md) + 5 charts on every run, no manual editing |
| Dashboard & visualization (Power BI) | [`dashboard/order_ops_dashboard.pbix`](dashboard/order_ops_dashboard.pbix) — live PostgreSQL connection, DAX measures, 3 KPI cards + trend/geo/leaderboard visuals |
| Descriptive statistics, metric definitions, anomaly detection | Pearson correlation + ANOVA in the EDA report; regional SLA-breach anomaly detection in SQL Q8 |
| Excel / spreadsheet modeling | [`excel/financial_ops_model.xlsx`](excel/financial_ops_model.xlsx) — live formulas (TREND() forecast, revenue-at-risk what-if model) |
| Real analytical case study | [`docs/case_study.md`](docs/case_study.md) — business question → findings → quantified revenue impact → recommendations |
| Live dashboard link | [`streamlit_app/app.py`](streamlit_app/app.py) — interactive Streamlit + Plotly app, including a live revenue-at-risk what-if calculator |
| Proof of work | This repo — real data, real queries, real dashboard, all reproducible from a fresh clone |

## Data source

[Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) — CC BY-NC-SA 4.0. Real, anonymized order data (2016–2018) covering orders, customers, products, sellers, payments, reviews and geolocation. Not synthetic.

## Repo structure

```
data/raw/          9 original Olist CSVs
sql/               01_schema.sql (DDL) + 02_analysis_queries.sql (analysis)
python/            load_data.py, eda_analysis.py, build_excel_model.py
excel/             financial_ops_model.xlsx
dashboard/         order_ops_dashboard.pbix
streamlit_app/     app.py, requirements.txt (live interactive dashboard)
reports/           eda_report.md + figures/ (auto-generated)
docs/              case_study.md
```

## Reproducing this locally

1. **Database**: Create a PostgreSQL database, then apply the schema:
   ```
   psql -U postgres -d order_ops_analytics -f sql/01_schema.sql
   ```
2. **Load data**: `python python/load_data.py` (loads all 9 CSVs respecting FK order)
3. **Run the analysis queries**: `psql -U postgres -d order_ops_analytics -f sql/02_analysis_queries.sql`
4. **Python EDA + auto report**: `pip install -r requirements.txt && python python/eda_analysis.py`
5. **Excel model**: `python python/build_excel_model.py`
6. **Power BI**: open `dashboard/order_ops_dashboard.pbix` in Power BI Desktop (connection details point at `localhost:5432/order_ops_analytics`)

## Key findings (from the automated EDA report)

- **Delivery SLA is a regional problem, not a uniform one**: late-delivery rate ranges from **2.9%** (Rondônia) to **23.9%** (Alagoas) — an 8x gap that a blanket policy would miss but a regional root-cause fix would catch.
- **Delivery delay measurably hurts satisfaction**: Pearson r = -0.27 (p < 0.001) between delivery delay and review score, confirmed by one-way ANOVA (F = 1979.6, p < 0.001) across the 5 review-score groups.
- **Repeat-purchase rate is low (~3%)**: of 94,990 unique customers, only ~3% ever placed a second order — retention, not acquisition, is the binding growth constraint.
- **Data-quality gaps found and documented, not silently patched**: 623 products carry a category name with no English translation mapping; 8 "delivered" orders are missing a delivery timestamp. Both are called out explicitly in the generated report.

Full report with charts: [`reports/eda_report.md`](reports/eda_report.md)

## Notes on the Power BI file

The `.pbix` connects live to a local PostgreSQL instance — Power BI auto-detected all 6 foreign-key relationships from the schema. Three DAX measures (`Total Orders`, `Total Revenue`, `Avg Review Score`) and one calculated column (`Order Month`, for correct chronological sorting) drive a KPI-card + trend-line + state-breakdown + seller-leaderboard report page. The report opens fine on any machine since the data is already imported; if you want to hit **Refresh**, point the connection at your own Postgres instance first via **Transform data → Data source settings → Change Source**.
