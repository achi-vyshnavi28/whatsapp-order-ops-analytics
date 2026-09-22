"""
Load step. Run this yourself, after setting MONGODB_URI in your own
terminal -- this script never asks for or hardcodes a connection string
(it contains your password).

Usage:
    python build_documents.py   # extract + transform (needs local Postgres)
    python load_to_mongodb.py   # load (needs your own MongoDB Atlas URI)
"""
import gzip
import json
import os
from pathlib import Path

from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
STAGED = ROOT / "data" / "staged" / "orders.jsonl.gz"

DB_NAME = "order_ops_nosql"
COLLECTION_NAME = "orders"
BATCH_SIZE = 2000


def get_client() -> MongoClient:
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        raise SystemExit(
            "Missing required environment variable MONGODB_URI. "
            "Set it in your own terminal before running this script, e.g.\n"
            '  set MONGODB_URI=mongodb+srv://user:password@cluster0.xxxxx.mongodb.net/'
        )
    return MongoClient(uri)


def load_documents(collection) -> int:
    collection.delete_many({})  # idempotent re-run
    batch = []
    n = 0
    with gzip.open(STAGED, "rt", encoding="utf-8") as f:
        for line in f:
            batch.append(json.loads(line))
            if len(batch) >= BATCH_SIZE:
                collection.insert_many(batch)
                n += len(batch)
                batch = []
        if batch:
            collection.insert_many(batch)
            n += len(batch)
    return n


def run_example_queries(collection) -> None:
    print("\n--- Example NoSQL queries against the loaded documents ---\n")

    print("1) Find: 3 delivered orders from Rio de Janeiro (SP) with a low review score")
    for doc in collection.find(
        {"customer.state": "SP", "status": "delivered", "review.score": {"$lte": 2}}
    ).limit(3):
        print(f"   order {doc['_id'][:12]}...  score={doc['review']['score']}  total=R$ {doc['total_value']}")

    print("\n2) Aggregation: revenue and avg review score by customer state (top 5)")
    pipeline = [
        {"$match": {"status": {"$nin": ["canceled", "unavailable"]}}},
        {"$group": {
            "_id": "$customer.state",
            "orders": {"$sum": 1},
            "revenue": {"$sum": "$total_value"},
            "avg_review": {"$avg": "$review.score"},
        }},
        {"$sort": {"revenue": -1}},
        {"$limit": 5},
    ]
    for row in collection.aggregate(pipeline):
        line = f"   {row['_id']}: {row['orders']:,} orders, R$ {row['revenue']:,.2f} revenue"
        if row["avg_review"] is not None:
            line += f", avg review {row['avg_review']:.2f}"
        print(line)

    print("\n3) Aggregation: unwind embedded items to find top 5 product categories by revenue")
    pipeline2 = [
        {"$unwind": "$items"},
        {"$group": {"_id": "$items.category", "revenue": {"$sum": "$items.price"}, "units": {"$sum": 1}}},
        {"$sort": {"revenue": -1}},
        {"$limit": 5},
    ]
    for row in collection.aggregate(pipeline2):
        print(f"   {row['_id']}: R$ {row['revenue']:,.2f} across {row['units']:,} units")

    print("\n4) Late-delivery rate computed directly from embedded fields (no join needed)")
    total = collection.count_documents({"status": "delivered"})
    late = collection.count_documents({"status": "delivered", "is_late": True})
    print(f"   {late:,} / {total:,} delivered orders were late ({late / total:.1%})")


def main() -> None:
    client = get_client()
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    print(f"Loading documents into {DB_NAME}.{COLLECTION_NAME} ...")
    n = load_documents(collection)
    print(f"Loaded {n:,} documents")

    collection.create_index("customer.state")
    collection.create_index("status")
    collection.create_index([("items.category", 1)])
    print("Created indexes on customer.state, status, items.category")

    run_example_queries(collection)

    client.close()
    print(f"\nDone. Data is live in MongoDB Atlas: {DB_NAME}.{COLLECTION_NAME}")


if __name__ == "__main__":
    main()
