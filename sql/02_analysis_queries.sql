-- ============================================================================
-- whatsapp-order-ops-analytics
-- Analytical SQL: multi-table joins, subqueries, CTEs, window functions
-- Run against order_ops_analytics (see sql/01_schema.sql + python/load_data.py)
-- ============================================================================


-- ----------------------------------------------------------------------------
-- Q1. Monthly revenue and order volume trend (aggregation + date truncation)
-- ----------------------------------------------------------------------------
SELECT
    DATE_TRUNC('month', o.order_purchase_timestamp)::date AS order_month,
    COUNT(DISTINCT o.order_id)                             AS total_orders,
    ROUND(SUM(oi.price + oi.freight_value)::numeric, 2)    AS total_revenue,
    ROUND(AVG(oi.price)::numeric, 2)                       AS avg_item_price
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.order_status NOT IN ('canceled', 'unavailable')
GROUP BY 1
ORDER BY 1;


-- ----------------------------------------------------------------------------
-- Q2. Month-over-month revenue growth (window function: LAG)
-- ----------------------------------------------------------------------------
WITH monthly_revenue AS (
    SELECT
        DATE_TRUNC('month', o.order_purchase_timestamp)::date AS order_month,
        SUM(oi.price + oi.freight_value)                       AS revenue
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    WHERE o.order_status NOT IN ('canceled', 'unavailable')
    GROUP BY 1
)
SELECT
    order_month,
    ROUND(revenue::numeric, 2)                                          AS revenue,
    ROUND(LAG(revenue) OVER (ORDER BY order_month)::numeric, 2)         AS prev_month_revenue,
    ROUND(
        100.0 * (revenue - LAG(revenue) OVER (ORDER BY order_month))
        / NULLIF(LAG(revenue) OVER (ORDER BY order_month), 0), 2
    )                                                                   AS mom_growth_pct
FROM monthly_revenue
ORDER BY order_month;


-- ----------------------------------------------------------------------------
-- Q3. Delivery performance: on-time vs late rate by state (multi-table join
--     + CASE aggregation) -- direct analogue of a WhatsApp order platform's
--     delivery-coordination SLA tracking.
-- ----------------------------------------------------------------------------
SELECT
    c.customer_state,
    COUNT(*)                                                                       AS delivered_orders,
    SUM(CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date
             THEN 1 ELSE 0 END)                                                    AS late_deliveries,
    ROUND(
        100.0 * SUM(CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date
                          THEN 1 ELSE 0 END) / COUNT(*), 2
    )                                                                               AS late_delivery_pct,
    ROUND(AVG(EXTRACT(EPOCH FROM (o.order_delivered_customer_date - o.order_purchase_timestamp)) / 86400.0)::numeric, 1)
                                                                                    AS avg_delivery_days
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
WHERE o.order_status = 'delivered'
  AND o.order_delivered_customer_date IS NOT NULL
GROUP BY c.customer_state
HAVING COUNT(*) >= 30
ORDER BY late_delivery_pct DESC;


-- ----------------------------------------------------------------------------
-- Q4. Seller (merchant) leaderboard with percentile rank (window function:
--     NTILE / RANK) -- mirrors "merchant health" scoring for WhatsApp-first SMBs.
-- ----------------------------------------------------------------------------
WITH seller_metrics AS (
    SELECT
        s.seller_id,
        s.seller_state,
        COUNT(DISTINCT oi.order_id)                    AS orders_fulfilled,
        ROUND(SUM(oi.price)::numeric, 2)               AS gross_sales,
        ROUND(AVG(r.review_score)::numeric, 2)         AS avg_review_score
    FROM sellers s
    JOIN order_items oi ON oi.seller_id = s.seller_id
    JOIN orders o        ON o.order_id = oi.order_id
    LEFT JOIN order_reviews r ON r.order_id = o.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY s.seller_id, s.seller_state
)
SELECT
    seller_id,
    seller_state,
    orders_fulfilled,
    gross_sales,
    avg_review_score,
    RANK()  OVER (ORDER BY gross_sales DESC)               AS sales_rank,
    NTILE(4) OVER (ORDER BY gross_sales DESC)               AS sales_quartile   -- 1 = top quartile
FROM seller_metrics
ORDER BY sales_rank
LIMIT 50;


-- ----------------------------------------------------------------------------
-- Q5. Customer repeat-purchase behaviour (self-join via customer_unique_id +
--     window function: ROW_NUMBER / running total) -- retention/loyalty view.
-- ----------------------------------------------------------------------------
WITH customer_orders AS (
    SELECT
        c.customer_unique_id,
        o.order_id,
        o.order_purchase_timestamp,
        ROW_NUMBER() OVER (
            PARTITION BY c.customer_unique_id ORDER BY o.order_purchase_timestamp
        ) AS order_sequence
    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
    WHERE o.order_status NOT IN ('canceled', 'unavailable')
)
SELECT
    order_sequence,
    COUNT(*) AS customers_reaching_this_order
FROM customer_orders
GROUP BY order_sequence
ORDER BY order_sequence
LIMIT 10;
-- Reading: row 1 = total unique customers; row 2 = how many placed a 2nd
-- order at all (repeat-purchase rate), etc.


-- ----------------------------------------------------------------------------
-- Q6. Product categories with above-average return-to-low-review rate
--     (subquery in WHERE + HAVING) -- "spot anomalies in raw data".
-- ----------------------------------------------------------------------------
SELECT
    COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category,
    COUNT(*)                                            AS reviewed_orders,
    ROUND(AVG(r.review_score)::numeric, 2)              AS avg_review_score
FROM order_items oi
JOIN products p        ON p.product_id = oi.product_id
LEFT JOIN product_category_name_translation t ON t.product_category_name = p.product_category_name
JOIN order_reviews r    ON r.order_id = oi.order_id
GROUP BY category
HAVING COUNT(*) >= 30
   AND AVG(r.review_score) < (
        SELECT AVG(review_score) FROM order_reviews
   )
ORDER BY avg_review_score ASC
LIMIT 15;


-- ----------------------------------------------------------------------------
-- Q7. Payment behaviour: installment usage vs order value (CTE + join +
--     aggregation) -- relevant to the "financial/ops modeling" angle.
-- ----------------------------------------------------------------------------
WITH order_totals AS (
    SELECT
        o.order_id,
        SUM(oi.price + oi.freight_value) AS order_value
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    GROUP BY o.order_id
)
SELECT
    op.payment_type,
    CASE
        WHEN op.payment_installments <= 1 THEN '1 (full payment)'
        WHEN op.payment_installments BETWEEN 2 AND 4 THEN '2-4'
        WHEN op.payment_installments BETWEEN 5 AND 8 THEN '5-8'
        ELSE '9+'
    END AS installment_bucket,
    COUNT(*)                                       AS orders,
    ROUND(AVG(ot.order_value)::numeric, 2)         AS avg_order_value
FROM order_payments op
JOIN order_totals ot ON ot.order_id = op.order_id
GROUP BY op.payment_type, installment_bucket
ORDER BY op.payment_type, installment_bucket;


-- ----------------------------------------------------------------------------
-- Q8. Anomaly detection: orders where freight cost exceeds product price
--     (a classic "spot the anomaly" analytical problem) using a subquery
--     and window function to flag outliers per category.
-- ----------------------------------------------------------------------------
WITH item_ratios AS (
    SELECT
        oi.order_id,
        oi.product_id,
        COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category,
        oi.price,
        oi.freight_value,
        ROUND((oi.freight_value / NULLIF(oi.price, 0))::numeric, 2) AS freight_to_price_ratio,
        AVG(oi.freight_value / NULLIF(oi.price, 0)) OVER (
            PARTITION BY COALESCE(t.product_category_name_english, p.product_category_name, 'unknown')
        ) AS category_avg_ratio
    FROM order_items oi
    JOIN products p ON p.product_id = oi.product_id
    LEFT JOIN product_category_name_translation t ON t.product_category_name = p.product_category_name
)
SELECT *
FROM item_ratios
WHERE freight_to_price_ratio > 3 * category_avg_ratio
ORDER BY freight_to_price_ratio DESC
LIMIT 25;


-- ----------------------------------------------------------------------------
-- Q9. Cohort-style retention: % of customers acquired in a given month who
--     ordered again within 90 days (CTE chain + self-join + date math).
-- ----------------------------------------------------------------------------
WITH first_orders AS (
    SELECT
        c.customer_unique_id,
        MIN(o.order_purchase_timestamp)                      AS first_order_date,
        DATE_TRUNC('month', MIN(o.order_purchase_timestamp)) AS cohort_month
    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
    WHERE o.order_status NOT IN ('canceled', 'unavailable')
    GROUP BY c.customer_unique_id
),
repeat_within_90d AS (
    SELECT DISTINCT fo.customer_unique_id, fo.cohort_month
    FROM first_orders fo
    JOIN customers c2 ON c2.customer_unique_id = fo.customer_unique_id
    JOIN orders o2    ON o2.customer_id = c2.customer_id
    WHERE o2.order_purchase_timestamp > fo.first_order_date
      AND o2.order_purchase_timestamp <= fo.first_order_date + INTERVAL '90 days'
)
SELECT
    fo.cohort_month::date,
    COUNT(DISTINCT fo.customer_unique_id)                                   AS cohort_size,
    COUNT(DISTINCT r.customer_unique_id)                                    AS retained_90d,
    ROUND(100.0 * COUNT(DISTINCT r.customer_unique_id)
          / NULLIF(COUNT(DISTINCT fo.customer_unique_id), 0), 2)           AS retention_90d_pct
FROM first_orders fo
LEFT JOIN repeat_within_90d r
       ON r.customer_unique_id = fo.customer_unique_id
      AND r.cohort_month = fo.cohort_month
GROUP BY fo.cohort_month
ORDER BY fo.cohort_month;
