"""
Load pgurazada1/machine-failure-logs, generate synthetic SAP BNAC data,
and insert into MongoDB. Links MachineLogs to WorkOrders via MachineID <-> equipmentId.
"""

import os
import random
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import pymongo
from datasets import load_dataset
from pymongo import MongoClient

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Config: use env vars for credentials (set MONGODB_URI or individual vars)
# ---------------------------------------------------------------------------
MONGODB_URI = os.environ.get(
    "MONGODB_URI",
    "mongodb+srv://sankethrp_db_user:<db_password>@workorderandconfirmatio.gfkc6h6.mongodb.net/?appName=WorkOrderAndConfirmations",
)
if "<db_password>" in MONGODB_URI and "MONGODB_PASSWORD" in os.environ:
    MONGODB_URI = MONGODB_URI.replace("<db_password>", os.environ["MONGODB_PASSWORD"])

DB_NAME = os.environ.get("MONGODB_DB", "sap_bnac")
WORK_ORDERS_COLLECTION = "workorders"
OPERATIONS_COLLECTION = "operations"
CONFIRMATIONS_COLLECTION = "confirmations"
MACHINE_LOGS_COLLECTION = "machinelogs"

# ML training scale: more WOs, ops, confirmations with variety and discrepancies
NUM_WORK_ORDERS = int(os.environ.get("NUM_WORK_ORDERS", "2500"))
ORDER_DATE_DAYS_BACK = int(os.environ.get("ORDER_DATE_DAYS_BACK", "180"))
# Status distribution for variety (percent): Created, Released, In Progress, Completed, Cancelled
STATUS_WEIGHTS = (12, 18, 20, 42, 8)
# Fraction of Completed WOs that have a failure/high-tool-wear log shortly before (positive examples)
COMPLETED_WITH_PRECEDING_FAILURE_FRAC = 0.75
# Fraction of confirmations with intentional actualWork discrepancy (over/under report)
CONFIRMATION_DISCREPANCY_FRAC = 0.25
# Fraction of confirmations with vague/alternate text (for NLP variety)
CONFIRMATION_VAGUE_TEXT_FRAC = 0.20

# Normalized column names we want (MachineLogs)
COL_MACHINE_ID = "MachineID"
COL_TOOL_ID = "Tool_ID"
COL_PROCESS_TEMP = "Process_Temperature"
COL_AIR_TEMP = "Air_Temperature"
COL_ROTATIONAL_SPEED = "Rotational_Speed"
COL_TORQUE = "Torque"
COL_TOOL_WEAR = "Tool_Wear"
COL_FAILURE_TYPE = "Failure_Type"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_column_name(name: str) -> str:
    """Map dataset column names to our schema."""
    n = (name or "").strip().lower()
    if "udi" in n or "id" == n or "machine" in n:
        return COL_MACHINE_ID
    if "product" in n or "tool" in n:
        return COL_TOOL_ID
    if "process" in n and "temp" in n:
        return COL_PROCESS_TEMP
    if "air" in n and "temp" in n:
        return COL_AIR_TEMP
    if "rotation" in n or "rpm" in n or "speed" in n:
        return COL_ROTATIONAL_SPEED
    if "torque" in n:
        return COL_TORQUE
    if "tool wear" in n or "tool_wear" in n:
        return COL_TOOL_WEAR
    if "failure" in n or "type" == n:
        return COL_FAILURE_TYPE
    return name


def load_and_normalize_machine_logs() -> pd.DataFrame:
    """Load pgurazada1/machine-failure-logs and normalize to our schema."""
    print("Loading dataset pgurazada1/machine-failure-logs...")
    ds = load_dataset("pgurazada1/machine-failure-logs")
    df = ds["train"].to_pandas() if hasattr(ds, "train") else pd.DataFrame(ds[list(ds.keys())[0]])

    # Normalize column names
    rename = {}
    for c in df.columns:
        norm = _normalize_column_name(c)
        if norm != c:
            rename[c] = norm
    df = df.rename(columns=rename)

    # Ensure MachineID exists and is string (equipmentId link)
    if COL_MACHINE_ID not in df.columns:
        df[COL_MACHINE_ID] = (df.index % 100 + 1).astype(str)
    else:
        df[COL_MACHINE_ID] = df[COL_MACHINE_ID].astype(str)

    # Failure_Type: map common values; treat high tool wear as "High Tool Wear" when applicable
    if COL_FAILURE_TYPE not in df.columns:
        if "Machine_failure" in df.columns or "machine failure" in df.columns:
            fc = "Machine_failure" if "Machine_failure" in df.columns else "machine failure"
            df[COL_FAILURE_TYPE] = df[fc].map(lambda x: "No Failure" if x == 0 else "Tool Wear Failure")
        else:
            df[COL_FAILURE_TYPE] = "No Failure"

    # Optional: mark high tool wear
    if COL_TOOL_WEAR in df.columns:
        high_wear = df[COL_TOOL_WEAR] >= 200
        df.loc[high_wear & (df[COL_FAILURE_TYPE] == "No Failure"), COL_FAILURE_TYPE] = "High Tool Wear"

    return df


def get_unstable_machines(df: pd.DataFrame) -> list[str]:
    """Return list of MachineIDs that have at least one failure or high tool wear."""
    if COL_FAILURE_TYPE not in df.columns:
        return df[COL_MACHINE_ID].unique().tolist()[:20]
    failure_values = {"Tool Wear Failure", "Heat Dissipation Failure", "Power Failure",
                      "Overstrain Failure", "Random Failures", "High Tool Wear"}
    unstable = df[df[COL_FAILURE_TYPE].astype(str).str.strip().isin(failure_values)][COL_MACHINE_ID].unique()
    return list(unstable) if len(unstable) else df[COL_MACHINE_ID].unique().tolist()[:20]


def get_all_machine_ids(df: pd.DataFrame) -> list[str]:
    """Return all unique MachineIDs (stable and unstable) for variety."""
    return df[COL_MACHINE_ID].astype(str).unique().tolist()


def build_machine_log_doc(row: pd.Series, log_ts: datetime) -> dict[str, Any]:
    """Build one MachineLog document for MongoDB."""
    doc = {
        "MachineID": str(row.get(COL_MACHINE_ID, "")),
        "Tool_ID": str(row.get(COL_TOOL_ID, "")) if pd.notna(row.get(COL_TOOL_ID)) else None,
        "Process_Temperature": float(row[COL_PROCESS_TEMP]) if COL_PROCESS_TEMP in row and pd.notna(row.get(COL_PROCESS_TEMP)) else None,
        "Air_Temperature": float(row[COL_AIR_TEMP]) if COL_AIR_TEMP in row and pd.notna(row.get(COL_AIR_TEMP)) else None,
        "Rotational_Speed": float(row[COL_ROTATIONAL_SPEED]) if COL_ROTATIONAL_SPEED in row and pd.notna(row.get(COL_ROTATIONAL_SPEED)) else None,
        "Torque": float(row[COL_TORQUE]) if COL_TORQUE in row and pd.notna(row.get(COL_TORQUE)) else None,
        "Tool_Wear": float(row[COL_TOOL_WEAR]) if COL_TOOL_WEAR in row and pd.notna(row.get(COL_TOOL_WEAR)) else None,
        "Failure_Type": str(row.get(COL_FAILURE_TYPE, "No Failure")).strip() or "No Failure",
        "logTimestamp": log_ts,
        "createdAt": _utc_now(),
    }
    if "Machine_failure" in row and pd.notna(row.get("Machine_failure")):
        doc["Machine_failure"] = int(row["Machine_failure"])
    return doc


def generate_sap_documents(
    unstable_machine_ids: list[str],
    all_machine_ids: list[str],
    machine_logs_df: pd.DataFrame,
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """
    Generate many synthetic WorkOrders with multiple Operations and Confirmations.
    Designed for ML/AI: variety in status, priority, timing; intentional discrepancies
    in actualWork and confirmationText; only a fraction of Completed WOs have a
    preceding failure log (positive vs negative examples).
    """
    work_orders = []
    operations = []
    confirmations = []
    extra_logs = []

    statuses = ["Created", "Released", "In Progress", "Completed", "Cancelled"]
    base_time = _utc_now() - timedelta(days=ORDER_DATE_DAYS_BACK)
    failure_types = {"Tool Wear Failure", "Heat Dissipation Failure", "Power Failure",
                    "Overstrain Failure", "Random Failures", "High Tool Wear"}

    op_descriptions = [
        "Preventive maintenance - lubrication and inspection",
        "Corrective repair after fault alarm",
        "Tool change and calibration",
        "Inspection and cleaning",
        "Bearing replacement",
        "Seal replacement and leak check",
        "Electrical safety check",
        "Vibration analysis and alignment",
        "Filter replacement",
        "Routine service per schedule",
    ]
    conf_text_templates = [
        "Work completed on equipment {equipmentId}. Actual work: {actualWork} h. No issues.",
        "Completed. Hours: {actualWork}. Machine {equipmentId}.",
        "Job done. Actual hrs: {actualWork}. Eq: {equipmentId}.",
        "Maintenance finished. Equipment {equipmentId}, {actualWork} hours logged.",
        "OK. {actualWork} h on {equipmentId}. All steps performed.",
    ]
    conf_text_vague = [
        "Work done.",
        "Completed as per WO.",
        "Finished. See notes.",
        "Done.",
        "Completed.",
    ]

    for i in range(NUM_WORK_ORDERS):
        # Bias toward unstable machines (60%) for more failure-linked examples
        machine_id = random.choices(
            [random.choice(unstable_machine_ids), random.choice(all_machine_ids)],
            weights=[0.6, 0.4],
            k=1,
        )[0]
        order_id = f"WO-{10000 + i}"
        order_date = base_time + timedelta(
            days=random.randint(0, ORDER_DATE_DAYS_BACK - 1),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )
        status = random.choices(statuses, weights=STATUS_WEIGHTS, k=1)[0]
        priority = random.choices([1, 2, 3, 4, 5], weights=[5, 15, 45, 28, 7], k=1)[0]
        actual_work_wo = round(random.uniform(0.5, 24.0), 2)

        wo = {
            "orderId": order_id,
            "status": status,
            "priority": priority,
            "equipmentId": machine_id,
            "actualWork": actual_work_wo,
            "orderDate": order_date,
            "createdAt": order_date,
            "updatedAt": _utc_now(),
        }
        work_orders.append(wo)

        num_ops = random.randint(1, 5)
        op_actual_total = 0.0
        for seq in range(1, num_ops + 1):
            op_work = round(actual_work_wo * (random.uniform(0.15, 0.45) if num_ops > 1 else 1.0), 2)
            if seq == num_ops and num_ops > 1:
                op_work = round(actual_work_wo - op_actual_total, 2)
            op_actual_total += op_work
            op_status = "Completed" if status == "Completed" else ("In Progress" if status == "In Progress" and seq == 1 else "Pending")
            if status == "Cancelled":
                op_status = "Cancelled" if seq <= 2 else "Pending"
            operations.append({
                "orderId": order_id,
                "operationId": f"OP-{order_id}-{seq:02d}",
                "status": op_status,
                "priority": priority,
                "equipmentId": machine_id,
                "actualWork": op_work,
                "description": random.choice(op_descriptions),
                "sequence": seq,
                "createdAt": order_date,
                "updatedAt": _utc_now(),
            })

        num_confirmations = 0
        if status == "Completed":
            num_confirmations = random.choice([1, 1, 1, 2])
        elif status in ("In Progress", "Released"):
            num_confirmations = random.choice([0, 0, 1])
        for cf_seq in range(1, num_confirmations + 1):
            use_discrepancy = random.random() < CONFIRMATION_DISCREPANCY_FRAC
            reported_work = actual_work_wo
            if use_discrepancy:
                reported_work = round(actual_work_wo * random.uniform(0.7, 1.35), 2)
                if random.random() < 0.3:
                    reported_work = round(actual_work_wo + random.uniform(-2, 3), 2)
            use_vague = random.random() < CONFIRMATION_VAGUE_TEXT_FRAC
            if use_vague:
                conf_text = random.choice(conf_text_vague)
            else:
                conf_text = random.choice(conf_text_templates).format(
                    equipmentId=machine_id, actualWork=reported_work
                )
            conf_status = random.choices(["Draft", "Submitted", "Approved"], weights=[5, 60, 35], k=1)[0]
            confirmed_at = order_date + timedelta(hours=random.randint(0, 4), minutes=random.randint(0, 59))
            confirmations.append({
                "orderId": order_id,
                "confirmationId": f"CF-{order_id}-{cf_seq:02d}",
                "confirmationText": conf_text,
                "status": conf_status,
                "equipmentId": machine_id,
                "actualWork": reported_work,
                "confirmedAt": confirmed_at,
                "createdAt": confirmed_at,
                "updatedAt": _utc_now(),
            })

        # Only a fraction of Completed WOs get a preceding failure log (ML positive examples)
        if status == "Completed" and random.random() < COMPLETED_WITH_PRECEDING_FAILURE_FRAC:
            log_before = order_date - timedelta(hours=random.randint(1, 48))
            machine_rows = machine_logs_df[machine_logs_df[COL_MACHINE_ID].astype(str) == machine_id]
            failure_rows = machine_rows[
                machine_rows[COL_FAILURE_TYPE].astype(str).str.strip().isin(failure_types)
            ] if COL_FAILURE_TYPE in machine_rows.columns else machine_rows
            if len(failure_rows) > 0:
                row = failure_rows.sample(1).iloc[0]
            else:
                row = machine_rows.sample(1).iloc[0] if len(machine_rows) > 0 else machine_logs_df.sample(1).iloc[0]
                row = row.copy()
                row[COL_MACHINE_ID] = machine_id
                row[COL_FAILURE_TYPE] = random.choice(["Tool Wear Failure", "High Tool Wear"])
            extra_logs.append(build_machine_log_doc(row, log_before))

    return work_orders, operations, confirmations, extra_logs


def main() -> None:
    df = load_and_normalize_machine_logs()
    print(f"Loaded {len(df)} machine log rows. Columns: {list(df.columns)}")

    unstable = get_unstable_machines(df)
    all_machines = get_all_machine_ids(df)
    print(f"Unstable machines: {len(unstable)}. All machines: {len(all_machines)}.")

    # Build all MachineLog documents from dataset (timestamps spread over ORDER_DATE_DAYS_BACK)
    base_ts = _utc_now() - timedelta(days=ORDER_DATE_DAYS_BACK)
    all_logs: list[dict] = []
    for idx, row in df.iterrows():
        log_ts = base_ts + timedelta(minutes=idx * 30)
        all_logs.append(build_machine_log_doc(row, log_ts))

    work_orders, operations, confirmations, extra_logs = generate_sap_documents(unstable, all_machines, df)
    all_logs.extend(extra_logs)

    print(f"Generated {len(work_orders)} WorkOrders, {len(operations)} Operations, {len(confirmations)} Confirmations.")
    print(f"Total MachineLogs to insert: {len(all_logs)}.")

    if "<db_password>" in MONGODB_URI:
        print("ERROR: Set MONGODB_PASSWORD in environment or replace <db_password> in MONGODB_URI.")
        return

    client: MongoClient = pymongo.MongoClient(MONGODB_URI)
    db = client[DB_NAME]

    # Insert collections (optionally clear first for idempotent run)
    clear_first = os.environ.get("CLEAR_COLLECTIONS", "0").strip().lower() in ("1", "true", "yes")
    if clear_first:
        db[WORK_ORDERS_COLLECTION].delete_many({})
        db[OPERATIONS_COLLECTION].delete_many({})
        db[CONFIRMATIONS_COLLECTION].delete_many({})
        db[MACHINE_LOGS_COLLECTION].delete_many({})
        print("Cleared existing collections.")

    db[MACHINE_LOGS_COLLECTION].insert_many(all_logs)
    db[WORK_ORDERS_COLLECTION].insert_many(work_orders)
    db[OPERATIONS_COLLECTION].insert_many(operations)
    db[CONFIRMATIONS_COLLECTION].insert_many(confirmations)

    print("Insert complete.")
    for coll_name in [WORK_ORDERS_COLLECTION, OPERATIONS_COLLECTION, CONFIRMATIONS_COLLECTION, MACHINE_LOGS_COLLECTION]:
        n = db[coll_name].count_documents({})
        print(f"  {coll_name}: {n}")
    client.close()


if __name__ == "__main__":
    main()
