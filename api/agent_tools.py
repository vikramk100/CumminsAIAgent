"""
Agent tools (function-calling): ML prediction, manual search, historical fixes.
"""

import os
import re
from pathlib import Path
from typing import Any, Optional

import pymongo
from pymongo.errors import PyMongoError

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
import sys
sys.path.insert(0, str(SCRIPT_DIR))

MONGODB_URI = os.environ.get(
    "MONGODB_URI",
    "mongodb+srv://sankethrp_db_user:<db_password>@workorderandconfirmatio.gfkc6h6.mongodb.net/?appName=WorkOrderAndConfirmations",
)
if "<db_password>" in MONGODB_URI and "MONGODB_PASSWORD" in os.environ:
    MONGODB_URI = MONGODB_URI.replace("<db_password>", os.environ["MONGODB_PASSWORD"])
DB_NAME = os.environ.get("MONGODB_DB", "sap_bnac")
MANUALS_COLLECTION = "manuals"
CONFIRMATIONS_COLLECTION = "confirmations"
DIAGNOSTICS_COLLECTION = "diagnostics"
MACHINE_LOGS_COLLECTION = "machinelogs"
WORK_ORDERS_COLLECTION = "workorders"

_client: Optional[pymongo.MongoClient] = None


def _get_db():
    """
    Returns a MongoDB database handle.

    In local/demo setups where MongoDB is not configured (placeholder password
    still present and no MONGODB_PASSWORD provided), this function raises a
    RuntimeError quickly instead of hanging on a remote connection attempt.
    """
    global _client

    if _client is not None:
        return _client[DB_NAME]

    # Detect unconfigured connection string and fail fast (used by demo fallback).
    if "<db_password>" in MONGODB_URI and not os.environ.get("MONGODB_PASSWORD"):
        raise RuntimeError("MongoDB not configured: MONGODB_URI still contains <db_password>.")

    # Use reasonable timeouts: Atlas DNS + TLS handshake can exceed 1-2s on some networks.
    _client = pymongo.MongoClient(MONGODB_URI, serverSelectionTimeoutMS=10000, connectTimeoutMS=10000)
    try:
        # Trigger server selection once; failures will surface immediately.
        _client.admin.command("ping")
    except PyMongoError as exc:
        # Reset client so future calls can retry or fall back.
        _client = None
        raise RuntimeError(f"MongoDB connection failed: {exc}") from exc

    return _client[DB_NAME]


def get_ml_prediction(machine_id: str) -> dict[str, Any]:
    """
    Calls the ML classification model for the given machine.
    Returns failure_label, confidence, fault_code, and telemetry summary.
    """
    db = _get_db()
    log = db[MACHINE_LOGS_COLLECTION].find_one(
        {"MachineID": machine_id},
        sort=[("logTimestamp", -1)],
        projection={
            "Process_Temperature": 1, "Air_Temperature": 1, "Rotational_Speed": 1,
            "Torque": 1, "Tool_Wear": 1, "failure_label": 1, "symptom": 1,
        },
    )
    if not log:
        return {"failure_label": "No_Failure", "confidence": 0.0, "fault_code": "", "symptom": "", "message": "No log for machine"}
    engine_models = db[MANUALS_COLLECTION].distinct("engineModel")
    engine_model = engine_models[hash(machine_id) % max(1, len(engine_models))] if engine_models else "X15"
    telemetry = {
        "Process_Temperature": log.get("Process_Temperature", 0),
        "Air_Temperature": log.get("Air_Temperature", 0),
        "Rotational_Speed": log.get("Rotational_Speed", 0),
        "Torque": log.get("Torque", 0),
        "Tool_Wear": log.get("Tool_Wear", 0),
        "engineModel": engine_model,
    }
    try:
        from train_failure_classifier import predict_failure, failure_label_to_fault_code_and_severity
        label, confidence = predict_failure(telemetry)
        fault_code, severity = failure_label_to_fault_code_and_severity(label)
    except Exception as e:
        label = log.get("failure_label", "No_Failure")
        confidence = 0.8
        fault_code = label.split("_S")[0] if "_S" in str(label) else (label or "")
        severity = 3
    return {
        "failure_label": label,
        "confidence": round(float(confidence), 2),
        "fault_code": fault_code,
        "severity": severity,
        "symptom": log.get("symptom") or "",
        "telemetry": telemetry,
    }


def query_manuals(fault_code: str, engine_model: Optional[str] = None, limit: int = 5) -> list[dict[str, Any]]:
    """
    Keyword search on Manuals collection for repair steps related to fault_code.
    Returns list of { content, section, pageNumber, engineModel }.
    """
    db = _get_db()
    if not fault_code or fault_code == "No_Failure":
        return []
    query = {"$or": [
        {"content": {"$regex": re.escape(fault_code), "$options": "i"}},
        {"content": {"$regex": "repair|maintenance|inspect|replace|torque|wrench", "$options": "i"}},
    ]}
    if engine_model:
        query["engineModel"] = engine_model
    cursor = db[MANUALS_COLLECTION].find(query, {"content": 1, "section": 1, "pageNumber": 1, "engineModel": 1}).limit(limit)
    return [{"content": d.get("content", "")[:1500], "section": d.get("section"), "pageNumber": d.get("pageNumber"), "engineModel": d.get("engineModel")} for d in cursor]


def get_historical_fixes(system_affected: str, limit: int = 10) -> list[dict[str, Any]]:
    """
    Searches Diagnostics and Confirmations for tools/steps used in similar successful repairs.
    Returns list of { resolution, diagnostic_steps, confirmationText }.
    """
    db = _get_db()
    if not system_affected:
        return []
    diag_cursor = db[DIAGNOSTICS_COLLECTION].find(
        {"system_affected": {"$regex": re.escape(system_affected), "$options": "i"}},
        {"resolution": 1, "diagnostic_steps": 1},
    ).limit(limit)
    results = []
    for d in diag_cursor:
        results.append({
            "source": "diagnostic",
            "resolution": (d.get("resolution") or "")[:500],
            "diagnostic_steps": (d.get("diagnostic_steps") or "")[:500],
        })
    conf_cursor = db[CONFIRMATIONS_COLLECTION].find(
        {"confirmationText": {"$regex": "completed|replaced|inspected|repair", "$options": "i"}},
        {"confirmationText": 1, "actualWork": 1},
    ).limit(limit)
    for c in conf_cursor:
        results.append({
            "source": "confirmation",
            "confirmationText": (c.get("confirmationText") or "")[:500],
            "actualWork": c.get("actualWork"),
        })
    return results[:limit]
