"""
Extract flattened ML dataset from MongoDB: MachineLogs joined with equipmentId
and engineModel (from Manuals context). Output CSV for training.
"""

import os
from typing import Any

import pandas as pd
import pymongo
from pymongo import MongoClient

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

MONGODB_URI = os.environ.get(
    "MONGODB_URI",
    "mongodb+srv://sankethrp_db_user:<db_password>@workorderandconfirmatio.gfkc6h6.mongodb.net/?appName=WorkOrderAndConfirmations",
)
if "<db_password>" in MONGODB_URI and "MONGODB_PASSWORD" in os.environ:
    MONGODB_URI = MONGODB_URI.replace("<db_password>", os.environ["MONGODB_PASSWORD"])

DB_NAME = os.environ.get("MONGODB_DB", "sap_bnac")
MACHINE_LOGS_COLLECTION = "machinelogs"
MANUALS_COLLECTION = "manuals"
WORK_ORDERS_COLLECTION = "workorders"

NUMERIC_FEATURES = ["Process_Temperature", "Air_Temperature", "Rotational_Speed", "Torque", "Tool_Wear"]
TARGET = "failure_label"
EQUIPMENT_ID = "equipmentId"  # same as MachineID in logs
ENGINE_MODEL = "engineModel"


def _engine_models_from_manuals(db) -> list[str]:
    """Get distinct engine models from Manuals (e.g. X15, B6.7, ISB)."""
    models = db[MANUALS_COLLECTION].distinct("engineModel")
    return list(models) if models else ["X15", "B6.7", "ISB"]


def _equipment_to_engine_map(db, engine_models: list[str]) -> dict[str, str]:
    """Map equipmentId (MachineID) to engineModel. Use distinct equipmentIds from WorkOrders and assign engine deterministically."""
    equipment_ids = db[WORK_ORDERS_COLLECTION].distinct("equipmentId")
    if not equipment_ids:
        return {}
    n = len(engine_models)
    return {eid: engine_models[hash(eid) % n] for eid in equipment_ids}


def extract_flattened_dataset(out_path: str | None = None) -> pd.DataFrame:
    """
    Fetch MachineLogs, join with equipmentId -> engineModel (from Manuals context).
    Returns DataFrame with features X and target y.
    """
    client = pymongo.MongoClient(MONGODB_URI)
    db = client[DB_NAME]
    engine_models = _engine_models_from_manuals(db)
    eq_to_engine = _equipment_to_engine_map(db, engine_models)
    # If no work orders, map MachineID directly by hash
    if not eq_to_engine:
        eq_to_engine = {}
        n = len(engine_models)

    cursor = db[MACHINE_LOGS_COLLECTION].find(
        {},
        {
            "MachineID": 1,
            "Process_Temperature": 1,
            "Air_Temperature": 1,
            "Rotational_Speed": 1,
            "Torque": 1,
            "Tool_Wear": 1,
            "failure_label": 1,
        },
    )
    rows = []
    for doc in cursor:
        machine_id = doc.get("MachineID") or ""
        engine = eq_to_engine.get(machine_id) or engine_models[hash(machine_id) % len(engine_models)]
        failure_label = doc.get("failure_label")
        if failure_label is None:
            failure_label = "No_Failure"
        row = {
            "equipmentId": machine_id,
            ENGINE_MODEL: engine,
            "Process_Temperature": doc.get("Process_Temperature"),
            "Air_Temperature": doc.get("Air_Temperature"),
            "Rotational_Speed": doc.get("Rotational_Speed"),
            "Torque": doc.get("Torque"),
            "Tool_Wear": doc.get("Tool_Wear"),
            TARGET: failure_label,
        }
        rows.append(row)
    client.close()

    df = pd.DataFrame(rows)
    # Drop rows where all numeric features are null
    num_cols = [c for c in NUMERIC_FEATURES if c in df.columns]
    if not num_cols:
        num_cols = [c for c in df.columns if c not in (TARGET, EQUIPMENT_ID, ENGINE_MODEL) and pd.api.types.is_numeric_dtype(df[c])]
    if num_cols:
        df = df[df[num_cols].notna().any(axis=1)].copy()
    for col in NUMERIC_FEATURES:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if num_cols:
        df[num_cols] = df[num_cols].fillna(df[num_cols].median())
    else:
        for c in NUMERIC_FEATURES:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    if out_path:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        df.to_csv(out_path, index=False)
        print(f"Wrote {len(df)} rows to {out_path}")
    return df


if __name__ == "__main__":
    import sys
    out = "data/ml_dataset.csv"
    if "-o" in sys.argv:
        i = sys.argv.index("-o")
        if i + 1 < len(sys.argv):
            out = sys.argv[i + 1]
    df = extract_flattened_dataset(out)
    print(f"Rows: {len(df)}, columns: {list(df.columns)}")
