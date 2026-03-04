"""
Debug MongoDB connection used by the backend.

Run from project root with venv active:
  python scripts/debug_mongodb.py

Checks: .env loading, URI (masked), connection, ping, and collection counts.
"""

import os
import sys
from pathlib import Path

# Load .env from project root
ROOT = Path(__file__).resolve().parent.parent
env_file = ROOT / ".env"
if env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
        print(f"[OK] Loaded .env from {env_file}")
    except ImportError:
        print("[WARN] python-dotenv not installed; using existing env only")
else:
    print(f"[WARN] No .env at {env_file}; using defaults / existing env")

# Use same config as api.agent_tools
MONGODB_URI = os.environ.get(
    "MONGODB_URI",
    "mongodb+srv://sankethrp_db_user:<db_password>@workorderandconfirmatio.gfkc6h6.mongodb.net/?appName=WorkOrderAndConfirmations",
)
if "<db_password>" in MONGODB_URI and os.environ.get("MONGODB_PASSWORD"):
    MONGODB_URI = MONGODB_URI.replace("<db_password>", os.environ["MONGODB_PASSWORD"])
DB_NAME = os.environ.get("MONGODB_DB", "sap_bnac")


def _mask_uri(uri: str) -> str:
    if "@" in uri:
        pre, rest = uri.split("@", 1)
        if "://" in pre:
            scheme, auth = pre.split("://", 1)
            if ":" in auth:
                user, _ = auth.split(":", 1)
                return f"{scheme}://{user}:****@{rest}"
        return f"...****@{rest}"
    return uri


def main():
    print()
    print("=== MongoDB connection debug ===")
    print(f"MONGODB_DB:     {DB_NAME}")
    print(f"MONGODB_URI:    {_mask_uri(MONGODB_URI)}")
    if "<db_password>" in MONGODB_URI:
        print("[FAIL] URI still contains <db_password>. Set MONGODB_PASSWORD in .env")
        sys.exit(1)
    print()

    try:
        import pymongo
        from pymongo.errors import PyMongoError
    except ImportError:
        print("[FAIL] pymongo not installed. Run: pip install pymongo")
        sys.exit(1)

    print("Connecting (timeout 5s)...")
    try:
        client = pymongo.MongoClient(
            MONGODB_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
        )
        client.admin.command("ping")
        print("[OK] Connected and ping succeeded")
    except PyMongoError as e:
        print(f"[FAIL] Connection error: {e}")
        sys.exit(1)

    db = client[DB_NAME]
    print(f"\nDatabase: {DB_NAME}")
    collections = ["workorders", "machinelogs", "manuals", "diagnostics", "confirmations", "audit_trail"]
    for col_name in collections:
        try:
            count = db[col_name].count_documents({})
            print(f"  {col_name}: {count} documents")
        except Exception as e:
            print(f"  {col_name}: error - {e}")

    wo = db["workorders"].find_one({}, {"orderId": 1, "equipmentId": 1})
    if wo:
        print(f"\nSample work order: {wo.get('orderId')} (equipmentId: {wo.get('equipmentId')})")
        print("  Use in app: ?orderId=" + wo.get("orderId", ""))
    else:
        print("\nNo work orders in DB. Run: python scripts/load_and_insert_mongodb.py")

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
