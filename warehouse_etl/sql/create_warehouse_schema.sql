-- ============================================================================
-- Snowflake star-schema DDL for the order-ops data warehouse.
-- Run automatically by python/load_to_snowflake.py (via the Snowflake Python
-- connector) -- kept here as a standalone file too so the schema design can
-- be read/reviewed independently of the load script.
-- ============================================================================

CREATE DATABASE IF NOT EXISTS ORDER_OPS_WAREHOUSE;
CREATE SCHEMA IF NOT EXISTS ORDER_OPS_WAREHOUSE.ANALYTICS;
USE SCHEMA ORDER_OPS_WAREHOUSE.ANALYTICS;

CREATE OR REPLACE TABLE dim_customer (
    customer_id         VARCHAR(32) PRIMARY KEY,
    customer_unique_id  VARCHAR(32),
    customer_city       VARCHAR(100),
    customer_state      VARCHAR(2)
);

CREATE OR REPLACE TABLE dim_product (
    product_id           VARCHAR(32) PRIMARY KEY,
    category_english     VARCHAR(100),
    product_weight_g     NUMBER,
    product_length_cm    NUMBER,
    product_height_cm    NUMBER,
    product_width_cm     NUMBER
);

CREATE OR REPLACE TABLE dim_seller (
    seller_id     VARCHAR(32) PRIMARY KEY,
    seller_city   VARCHAR(100),
    seller_state  VARCHAR(2)
);

CREATE OR REPLACE TABLE dim_date (
    date_key      NUMBER PRIMARY KEY,   -- YYYYMMDD
    full_date     DATE,
    year          NUMBER,
    month         NUMBER,
    month_name    VARCHAR(20),
    day           NUMBER,
    day_of_week   VARCHAR(20),
    is_weekend    BOOLEAN
);

CREATE OR REPLACE TABLE fact_order_items (
    order_id           VARCHAR(32),
    order_item_id      NUMBER,
    customer_id        VARCHAR(32) REFERENCES dim_customer(customer_id),
    product_id         VARCHAR(32) REFERENCES dim_product(product_id),
    seller_id          VARCHAR(32) REFERENCES dim_seller(seller_id),
    date_key           NUMBER REFERENCES dim_date(date_key),
    order_status       VARCHAR(20),
    price              NUMBER(10,2),
    freight_value      NUMBER(10,2),
    payment_value      NUMBER(10,2),
    payment_types      VARCHAR(200),
    review_score       FLOAT,
    is_late            BOOLEAN,
    delivery_days      FLOAT,
    PRIMARY KEY (order_id, order_item_id)
);

-- Example warehouse-style analytical query: monthly revenue by product
-- category, computed straight from the star schema.
-- SELECT d.year, d.month_name, p.category_english,
--        SUM(f.price + f.freight_value) AS revenue
-- FROM fact_order_items f
-- JOIN dim_date d ON d.date_key = f.date_key
-- JOIN dim_product p ON p.product_id = f.product_id
-- WHERE f.order_status NOT IN ('canceled', 'unavailable')
-- GROUP BY d.year, d.month_name, p.category_english
-- ORDER BY d.year, d.month_name;
