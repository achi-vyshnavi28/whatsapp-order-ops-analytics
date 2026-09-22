# nosql_mongo

The same order-ops facts, modeled a third way: as **denormalized documents** in **MongoDB Atlas**, alongside the normalized relational schema (`sql/`) and the star-schema data warehouse (`warehouse_etl/`) elsewhere in this repo.

## Why documents, not just "the same tables as JSON"

A document database earns its place when data is modeled for how it's *read*, not for update-anomaly-free normalization. An order is naturally one document: its line items, payment installments, and review don't need a join to reconstruct — they're embedded right on the order.

```json
{
  "_id": "e481f51cbdc54678b7cc49136f2d6af7",
  "status": "delivered",
  "customer": {"unique_id": "...", "city": "sao paulo", "state": "SP"},
  "items": [{"product_id": "...", "category": "housewares", "price": 29.99, "freight_value": 8.72}],
  "total_value": 38.71,
  "payments": [{"type": "credit_card", "installments": 1, "value": 18.12}, ...],
  "review": {"score": 4, "message": "..."}
}
```

Compare this to `warehouse_etl/`'s star schema for the exact same source data — same facts, deliberately different modeling discipline, because the two systems answer different questions (fast dimensional rollups vs. "give me everything about this one order").

## Pipeline (two steps, same split as the other modules)

1. **Extract + Transform** — [`python/build_documents.py`](python/build_documents.py). Pulls from local Postgres, builds one JSON document per order (99,441 total), stages as gzip-compressed JSONL (`data/staged/orders.jsonl.gz`, ~16MB).
2. **Load** — [`python/load_to_mongodb.py`](python/load_to_mongodb.py). Bulk-loads the staged documents into MongoDB Atlas, creates indexes, and runs 4 example queries (a filtered `find`, two aggregation pipelines including an `$unwind` over embedded items, and a direct count) to demonstrate actually querying the document store — not just inserting into it.

## Running it

```bash
pip install -r requirements.txt
python python/build_documents.py     # needs local Postgres

set MONGODB_URI=mongodb+srv://user:password@cluster0.xxxxx.mongodb.net/
python python/load_to_mongodb.py     # needs your own MongoDB Atlas cluster
```

## Confirmed working — actual output from a live run

```
Loading documents into order_ops_nosql.orders ...
Loaded 99,441 documents
Created indexes on customer.state, status, items.category

--- Example NoSQL queries against the loaded documents ---

1) Find: 3 delivered orders from Rio de Janeiro (SP) with a low review score
   order f70a0aff17df...  score=2  total=R$ 313.19
   order 5164933efe0c...  score=1  total=R$ 141.9
   order f4471dae8c48...  score=1  total=R$ 232.14

2) Aggregation: revenue and avg review score by customer state (top 5)
   SP: 41,127 orders, R$ 5,878,132.06 revenue, avg review 4.21
   RJ: 12,698 orders, R$ 2,115,667.56 revenue, avg review 3.91
   MG: 11,496 orders, R$ 1,843,074.43 revenue, avg review 4.16
   RS: 5,417 orders, R$ 877,290.59 revenue, avg review 4.15
   PR: 4,983 orders, R$ 794,196.61 revenue, avg review 4.21

3) Aggregation: unwind embedded items to find top 5 product categories by revenue
   health_beauty: R$ 1,258,681.34 across 9,670 units
   watches_gifts: R$ 1,205,005.68 across 5,991 units
   bed_bath_table: R$ 1,036,988.68 across 11,115 units
   sports_leisure: R$ 988,048.97 across 8,641 units
   computers_accessories: R$ 911,954.32 across 7,827 units

4) Late-delivery rate computed directly from embedded fields (no join needed)
   7,826 / 96,478 delivered orders were late (8.1%)

Done. Data is live in MongoDB Atlas: order_ops_nosql.orders
```

The 8.1% late-delivery rate matches exactly what the PostgreSQL and Snowflake versions of this same analysis found — same facts, three different database paradigms, consistent answer.

## Data

Real order-operations data (same source as the rest of this repo): 99,441 orders from the [Olist Brazilian E-Commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), including real (Portuguese-language) customer review text.
