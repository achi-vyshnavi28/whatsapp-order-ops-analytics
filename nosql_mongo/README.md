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

## Data

Real order-operations data (same source as the rest of this repo): 99,441 orders from the [Olist Brazilian E-Commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), including real (Portuguese-language) customer review text.
