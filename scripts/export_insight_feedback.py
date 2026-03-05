"""
Export insight_feedback from MongoDB for model improvement (fine-tuning / RLHF).

Usage (from project root with venv active):
  python scripts/export_insight_feedback.py
  python scripts/export_insight_feedback.py -o data/insight_feedback.jsonl
  python scripts/export_insight_feedback.py --rating up --rating down  # default: both
  python scripts/export_insight_feedback.py --format json              # single JSON array

Output (JSONL default): one JSON object per line with:
  orderId, equipmentId, rating, source, feedbackText, rootCauseAnalysis, userId, timestamp
"""

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Run from project root: allow importing api
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pymongo

MONGODB_URI = os.environ.get(
    "MONGODB_URI",
    "mongodb+srv://sankethrp_db_user:<db_password>@workorderandconfirmatio.gfkc6h6.mongodb.net/?appName=WorkOrderAndConfirmations",
)
if "<db_password>" in MONGODB_URI and os.environ.get("MONGODB_PASSWORD"):
    MONGODB_URI = MONGODB_URI.replace("<db_password>", os.environ["MONGODB_PASSWORD"])
DB_NAME = os.environ.get("MONGODB_DB", "sap_bnac")
COLLECTION = "insight_feedback"


def _serialize(doc):
    """Convert MongoDB doc to JSON-serializable dict (e.g. datetime -> ISO string)."""
    out = {}
    for k, v in doc.items():
        if k == "_id":
            out[k] = str(v)
        elif hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def main():
    parser = argparse.ArgumentParser(description="Export insight_feedback for model improvement")
    parser.add_argument("-o", "--output", default="data/insight_feedback.jsonl", help="Output file path")
    parser.add_argument("--rating", action="append", choices=["up", "down"], help="Filter by rating (can repeat)")
    parser.add_argument("--format", choices=["jsonl", "json"], default="jsonl", help="Output format")
    args = parser.parse_args()

    client = pymongo.MongoClient(MONGODB_URI)
    db = client[DB_NAME]
    coll = db[COLLECTION]

    query = {}
    if args.rating:
        query["rating"] = {"$in": args.rating}

    cursor = coll.find(query).sort("timestamp", 1)
    rows = [_serialize(doc) for doc in cursor]

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.format == "jsonl":
        with open(out_path, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    else:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2, ensure_ascii=False)

    print(f"Exported {len(rows)} feedback record(s) to {out_path}")


if __name__ == "__main__":
    main()
