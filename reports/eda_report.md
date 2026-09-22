# whatsapp-order-ops-analytics — Automated EDA Report

_Generated programmatically by `python/eda_analysis.py` from live queries against the `order_ops_analytics` PostgreSQL database._

## Data Source
Real, anonymized Brazilian e-commerce data from Olist (100k+ orders, 2016-2018), used as a structural analogue for a WhatsApp-first SMB order platform's merchant-order-delivery operations. Source: [Kaggle - Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), CC BY-NC-SA 4.0.

## Data Cleaning Notes
- **orders total**: 99441
- **delivered orders missing delivery date**: 8
- **duplicate review rows removed**: 0
- **products without english category mapping**: 623

## 1. Order Volume Trend
![Monthly order volume](reports/figures/01_monthly_order_volume.png)

Peak month was **November 2017** with **7,423 orders**. Volume grew steadily from 2017 through late 2017 before plateauing in 2018.

## 2. Delivery Performance & Anomalies
![Late delivery rate by state](reports/figures/02_late_delivery_by_state.png)

**Anomaly detected:** customers in **AL** experience a **23.93%** late-delivery rate (avg 24.5 days to deliver) versus **2.88%** in **RO** (avg 19.4 days) — a 8.3x gap. This points to a specific logistics/carrier bottleneck worth investigating at the regional level, directly analogous to flagging underperforming delivery partners in a WhatsApp order platform's own dispatch data.

## 3. Review Score vs. Delivery Delay
![Review score vs delay](reports/figures/03_review_vs_delay.png)

Pearson correlation between delivery delay and review score: **r = -0.2664** (p < 0.001, n = 96,359). One-way ANOVA across the 5 review-score groups: F = 1979.62, p < 0.001. Both confirm a statistically significant negative relationship: **later deliveries drive down customer satisfaction** — a direct, quantified link between an operational metric and a business outcome.

## 4. Customer Retention
![Repeat purchase distribution](reports/figures/04_repeat_purchase_distribution.png)

Of **94,990** unique customers, only **3.04%** placed a second order at all. This is a low repeat-purchase rate for a multi-category marketplace and flags retention/re-engagement as the highest-leverage growth lever — the kind of metric a WhatsApp-native re-engagement flow is positioned to move directly.

## 5. Lowest-Rated Product Categories
![Lowest rated categories](reports/figures/05_lowest_rated_categories.png)

| Category                          |   Reviews |   Avg Review Score |
|:----------------------------------|----------:|-------------------:|
| diapers_and_hygiene               |        39 |               3.26 |
| office_furniture                  |      1687 |               3.49 |
| fashion_male_clothing             |       131 |               3.64 |
| fixed_telephony                   |       262 |               3.68 |
| party_supplies                    |        43 |               3.77 |
| fashio_female_clothing            |        50 |               3.78 |
| furniture_mattress_and_upholstery |        38 |               3.82 |
| audio                             |       361 |               3.83 |
| home_confort                      |       435 |               3.83 |
| unknown                           |      1598 |               3.84 |

## Summary
- Order volume trend is healthy through 2017 but plateaus in 2018 — worth segmenting by acquisition channel to see if growth stalled or just seasonality.
- Delivery SLA breaches are heavily regional, not uniform — a targeted fix (carrier renegotiation / regional fulfillment) beats a blanket policy.
- Delivery delay is statistically linked to lower reviews — delivery ops *is* a customer-satisfaction lever, not just a logistics metric.
- Repeat-purchase rate is low (~3%) — retention, not acquisition, is the binding constraint on long-term revenue.
