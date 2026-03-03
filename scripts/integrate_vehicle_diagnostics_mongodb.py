"""
Integrate CJJones/Vehicle_Diagnostics_LLM_Training_Sample into MongoDB:
- New Diagnostics collection (fault_code, symptoms, system_affected, resolution, diagnostic_steps)
- Enrich Operations with diagnostic_steps and resolution
- Add symptom and failure_label to MachineLogs (ML target)
Uses bulk UpdateOne in batches to avoid rate limits.
"""

import os
import re
from typing import Any

import pandas as pd
import pymongo
from datasets import load_dataset
from pymongo import MongoClient, UpdateOne

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
DIAGNOSTICS_COLLECTION = "diagnostics"
OPERATIONS_COLLECTION = "operations"
MACHINE_LOGS_COLLECTION = "machinelogs"
BATCH_SIZE = 500

# Map DTC prefix / keywords to Cummins engine categories
DTC_SYSTEM_MAP = {
    "P": "Engine",  # Powertrain (engine, fuel, ignition, emissions)
    "P0": "Fuel System",
    "P02": "Fuel System",
    "P03": "Ignition",
    "P04": "Emissions",
    "P05": "Engine",
    "P06": "Engine",
    "P07": "Transmission",
    "P08": "Engine",
    "P09": "Transmission",
    "P0A": "Electrical",  # Hybrid / electrical
    "C": "Chassis",
    "C00": "Brakes",
    "B": "Body",
    "U": "Electrical",
}
SYMPTOM_SYSTEM_KEYWORDS = [
    ("fuel", "Fuel System"),
    ("cooling", "Cooling"),
    ("overheat", "Cooling"),
    ("transmission", "Transmission"),
    ("shift", "Transmission"),
    ("charging", "Electrical"),
    ("battery", "Electrical"),
    ("brake", "Brakes"),
    ("pedal", "Brakes"),
    ("idle", "Engine"),
    ("engine", "Engine"),
    ("exhaust", "Emissions"),
    ("emission", "Emissions"),
]


def _system_from_dtc_and_text(fault_code: str, text: str) -> str:
    """Map fault_code and text to Cummins-style system_affected."""
    text_lower = (text or "").lower()
    for kw, sys in SYMPTOM_SYSTEM_KEYWORDS:
        if kw in text_lower:
            return sys
    if not fault_code:
        return "Engine"
    prefix = fault_code.upper()[:1]
    prefix2 = fault_code.upper()[:2]
    prefix3 = fault_code.upper()[:3]
    return (
        DTC_SYSTEM_MAP.get(prefix3)
        or DTC_SYSTEM_MAP.get(prefix2)
        or DTC_SYSTEM_MAP.get(prefix)
        or "Engine"
    )


def _severity_from_dtc(fault_code: str) -> int:
    """Derive severity 1-5 for ML target from DTC (e.g. P0xxx vs P07xx)."""
    if not fault_code or len(fault_code) < 2:
        return 3
    try:
        num_part = re.sub(r"[^0-9]", "", fault_code)
        if not num_part:
            return 3
        n = int(num_part[:3]) % 100
        return min(5, max(1, (n % 5) + 1))
    except Exception:
        return 3


def load_and_parse_diagnostics() -> pd.DataFrame:
    """Load HF dataset and parse Notes rows into structured diagnostics."""
    print("Loading CJJones/Vehicle_Diagnostics_LLM_Training_Sample...")
    ds = load_dataset("CJJones/Vehicle_Diagnostics_LLM_Training_Sample", split="train")
    rows = []
    for i in range(len(ds)):
        text = (ds[i].get("text") or "").strip()
        if not text.startswith("Notes:"):
            continue
        sym_m = re.search(r"Observed symptoms:\s*([^.]+?)(?:\.|Diagnostic)", text, re.I | re.DOTALL)
        dtc_m = re.search(r"Diagnostic trouble code:\s*([A-Z0-9]+)", text, re.I)
        actions_m = re.search(r"Recommended actions:\s*(.+?)(?:\.\s*$|$)", text, re.I | re.DOTALL)
        symptoms = (sym_m.group(1).strip() if sym_m else "").strip()
        fault_code = dtc_m.group(1).strip() if dtc_m else ""
        resolution = (actions_m.group(1).strip() if actions_m else "").strip()
        if not fault_code and not symptoms:
            continue
        if not fault_code:
            fault_code = f"GEN_{i}"
        system_affected = _system_from_dtc_and_text(fault_code, text + " " + resolution)
        diagnostic_steps = resolution  # use recommended actions as steps
        severity = _severity_from_dtc(fault_code)
        rows.append({
            "fault_code": fault_code,
            "symptoms": symptoms or "Unknown symptom",
            "system_affected": system_affected,
            "resolution": resolution,
            "diagnostic_steps": diagnostic_steps,
            "severity": severity,
            "source_text": text[:500],
        })
    df = pd.DataFrame(rows)
    print(f"Parsed {len(df)} diagnostic records.")
    return df


def insert_diagnostics(db, df: pd.DataFrame) -> list[dict]:
    """Insert diagnostics into Diagnostics collection; return list of dicts for linking."""
    coll = db[DIAGNOSTICS_COLLECTION]
    clear = os.environ.get("CLEAR_DIAGNOSTICS", "0").strip().lower() in ("1", "true", "yes")
    if clear:
        coll.delete_many({})
    docs = df.to_dict("records")
    if docs:
        coll.insert_many(docs)
    print(f"Inserted {len(docs)} documents into {DIAGNOSTICS_COLLECTION}.")
    return docs


def enrich_operations(db, diagnostics: list[dict]) -> None:
    """Enrich all Operations with diagnostic_steps and resolution from diagnostics."""
    coll = db[OPERATIONS_COLLECTION]
    ops = list(coll.find({}, {"_id": 1, "orderId": 1, "operationId": 1, "description": 1}))
    if not ops:
        print("No operations to enrich.")
        return
    if not diagnostics:
        print("No diagnostics; skipping operation enrichment.")
        return
    by_system: dict[str, list[dict]] = {}
    for d in diagnostics:
        s = d.get("system_affected") or "Engine"
        by_system.setdefault(s, []).append(d)
    all_diags = diagnostics
    op_system_keywords = [
        ("fuel", "Fuel System"), ("cooling", "Cooling"), ("lubrication", "Engine"),
        ("bearing", "Engine"), ("electrical", "Electrical"), ("filter", "Engine"),
        ("transmission", "Transmission"), ("brake", "Brakes"), ("seal", "Engine"),
        ("inspection", "Engine"), ("calibration", "Engine"), ("vibration", "Engine"),
    ]

    def _op_system(desc: str) -> str | None:
        d = (desc or "").lower()
        for kw, sys in op_system_keywords:
            if kw in d:
                return sys
        return None

    updates = []
    for idx, op in enumerate(ops):
        desc = op.get("description") or ""
        sys = _op_system(desc)
        if sys and sys in by_system:
            diag = by_system[sys][idx % len(by_system[sys])]
        else:
            diag = all_diags[idx % len(all_diags)]
        updates.append(
            UpdateOne(
                {"_id": op["_id"]},
                {
                    "$set": {
                        "description": diag.get("diagnostic_steps") or diag.get("resolution") or desc,
                        "diagnostic_steps": diag.get("diagnostic_steps"),
                        "resolution": diag.get("resolution"),
                    }
                },
            )
        )
    for i in range(0, len(updates), BATCH_SIZE):
        batch = updates[i : i + BATCH_SIZE]
        coll.bulk_write(batch, ordered=False)
    print(f"Enriched {len(updates)} operations with diagnostic_steps and resolution.")


def enrich_machinelogs(db, diagnostics: list[dict]) -> None:
    """Add symptom and failure_label to MachineLogs (with failure flags)."""
    coll = db[MACHINE_LOGS_COLLECTION]
    failure_types = {"Tool Wear Failure", "Heat Dissipation Failure", "Power Failure",
                    "Overstrain Failure", "Random Failures", "High Tool Wear"}
    cursor = coll.find({
        "$or": [
            {"Failure_Type": {"$in": list(failure_types)}},
            {"Machine_failure": 1},
        ]
    }, {"_id": 1})
    log_ids = [doc["_id"] for doc in cursor]
    if not log_ids:
        print("No machine logs with failure flags to enrich.")
        return
    if not diagnostics:
        print("No diagnostics; skipping machinelog enrichment.")
        return
    updates = []
    for j, _id in enumerate(log_ids):
        diag = diagnostics[j % len(diagnostics)]
        fault_code = diag.get("fault_code", "")
        severity = diag.get("severity", 3)
        failure_label = f"{fault_code}_S{severity}"
        updates.append(
            UpdateOne(
                {"_id": _id},
                {
                    "$set": {
                        "symptom": diag.get("symptoms"),
                        "failure_label": failure_label,
                    }
                },
            )
        )
    for i in range(0, len(updates), BATCH_SIZE):
        batch = updates[i : i + BATCH_SIZE]
        coll.bulk_write(batch, ordered=False)
    print(f"Enriched {len(updates)} machine logs with symptom and failure_label.")
    # Set failure_label=No_Failure for logs without failure (ML target for negative class)
    result = coll.update_many(
        {"Failure_Type": "No Failure", "failure_label": {"$exists": False}},
        {"$set": {"failure_label": "No_Failure", "symptom": None}},
    )
    if result.modified_count:
        print(f"Set failure_label=No_Failure for {result.modified_count} non-failure logs.")


def main() -> None:
    if "<db_password>" in MONGODB_URI:
        print("ERROR: Set MONGODB_PASSWORD in environment.")
        return
    df = load_and_parse_diagnostics()
    if df.empty:
        print("No diagnostic records parsed; exiting.")
        return
    client: MongoClient = pymongo.MongoClient(MONGODB_URI)
    db = client[DB_NAME]
    diagnostics = insert_diagnostics(db, df)
    enrich_operations(db, diagnostics)
    enrich_machinelogs(db, diagnostics)
    client.close()
    print("Done.")


if __name__ == "__main__":
    main()
