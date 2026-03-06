"""
SAP Fiori–style API: predictions in OData-like format, $top/$skip/$filter, triggerWorkOrder.
"""

import os
import re
from pathlib import Path
from typing import Any, Optional

import pymongo
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Import prediction and criticality from project (lazy to allow app start without model)
SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
import sys
sys.path.insert(0, str(SCRIPT_DIR))

def _predict_failure(telemetry_data):
    from train_failure_classifier import predict_failure
    return predict_failure(telemetry_data)

def _failure_label_to_fault_code_and_severity(label):
    from train_failure_classifier import failure_label_to_fault_code_and_severity
    return failure_label_to_fault_code_and_severity(label)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from criticality import confidence_severity_to_criticality

from api.v1.router import router as v1_router

MONGODB_URI = os.environ.get(
    "MONGODB_URI",
    "mongodb+srv://sankethrp_db_user:<db_password>@workorderandconfirmatio.gfkc6h6.mongodb.net/?appName=WorkOrderAndConfirmations",
)
if "<db_password>" in MONGODB_URI and "MONGODB_PASSWORD" in os.environ:
    MONGODB_URI = MONGODB_URI.replace("<db_password>", os.environ["MONGODB_PASSWORD"])
DB_NAME = os.environ.get("MONGODB_DB", "sap_bnac")
DIAGNOSTICS_COLLECTION = "diagnostics"
MANUALS_COLLECTION = "manuals"
WORK_ORDERS_COLLECTION = "workorders"

# CORS origins (comma-separated in env, or * for all)
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")
if CORS_ORIGINS == ["*"]:
    CORS_ORIGINS = ["*"]

app = FastAPI(title="Cummins SAP-Style Predictions API")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"], allow_credentials=True)
app.include_router(v1_router)

# Webapp path for serving frontend
_webapp_path = Path(__file__).resolve().parent.parent / "webapp"


# Health check endpoint for Cloud Run
@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run and load balancers."""
    return {"status": "healthy", "service": "cummins-ai-agent"}


@app.get("/")
async def root():
    """Serve the frontend index.html or API info."""
    # Check if webapp folder exists (production deployment)
    webapp_path = Path(__file__).resolve().parent.parent / "webapp"
    index_file = webapp_path / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    # Fallback to API info if no frontend
    return {
        "service": "Cummins AI Agent API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


def _db():
    return pymongo.MongoClient(MONGODB_URI)[DB_NAME]


def _fault_code_to_predicted_failure(fault_code: str, db) -> str:
    d = db[DIAGNOSTICS_COLLECTION].find_one({"fault_code": fault_code})
    if d and d.get("symptoms"):
        return d["symptoms"].strip()
    if d and d.get("system_affected"):
        return f"{d['system_affected']} Issue"
    return fault_code or "Unknown"


def _suggested_operation_and_manual(fault_code: str, engine_model: str, db) -> tuple[str, str]:
    d = db[DIAGNOSTICS_COLLECTION].find_one({"fault_code": fault_code})
    suggested = (d.get("resolution") or d.get("diagnostic_steps") or "Inspect and diagnose.").strip()
    manual = db[MANUALS_COLLECTION].find_one({"engineModel": engine_model}, {"pageNumber": 1})
    ref = f"Manual {engine_model} - Page {manual['pageNumber']}" if manual else f"Manual {engine_model}"
    return suggested[:200], ref


@app.get("/api/predictions")
def get_predictions(
    equipmentId: Optional[str] = None,
    top: int = Query(20, alias="$top", ge=1, le=500),
    skip: int = Query(0, alias="$skip", ge=0),
    filter_eq: Optional[str] = Query(None, alias="$filter"),
):
    """
    Fiori-ready: returns { "d": { "results": [ ... ] } }.
    $top, $skip: pagination. $filter: optional eq filter on equipmentId (e.g. equipmentId eq '1').
    """
    db = _db()
    results = []
    # Optional $filter: simple "equipmentId eq 'value'" or substring
    filter_equipment = None
    if filter_eq and "equipmentId" in (filter_eq or ""):
        m = re.search(r"equipmentId\s+eq\s+['\"]?([^'\"]+)['\"]?", filter_eq, re.I)
        if m:
            filter_equipment = m.group(1).strip()
    if equipmentId:
        filter_equipment = equipmentId
        # Get latest machine log for this equipment and predict
        log = db["machinelogs"].find_one(
            {"MachineID": equipmentId},
            sort=[("logTimestamp", -1)],
            projection={"Process_Temperature": 1, "Air_Temperature": 1, "Rotational_Speed": 1, "Torque": 1, "Tool_Wear": 1},
        )
        engine_models = db[MANUALS_COLLECTION].distinct("engineModel")
        engine_model = engine_models[hash(equipmentId) % max(1, len(engine_models))] if engine_models else "X15"
        if log:
            telemetry = {k: log.get(k, 0) for k in ["Process_Temperature", "Air_Temperature", "Rotational_Speed", "Torque", "Tool_Wear"]}
            telemetry["engineModel"] = engine_model
            try:
                label, confidence = _predict_failure(telemetry)
            except Exception:
                label, confidence = "No_Failure", 0.99
            fault_code, severity = _failure_label_to_fault_code_and_severity(label)
            criticality = confidence_severity_to_criticality(confidence, severity)
            predicted_failure = _fault_code_to_predicted_failure(fault_code, db) if fault_code else "No Failure"
            suggested_op, manual_ref = _suggested_operation_and_manual(fault_code, engine_model, db) if fault_code else ("None", f"Manual {engine_model}")
            results.append({
                "equipmentId": equipmentId,
                "predictedFailure": predicted_failure,
                "faultCode": fault_code or "",
                "criticality": criticality,
                "confidence": round(confidence, 2),
                "suggestedOperation": suggested_op,
                "manualReference": manual_ref,
            })
    else:
        # Pageable list: work orders with predictions
        query = {}
        if filter_equipment:
            query["equipmentId"] = filter_equipment
        cursor = db[WORK_ORDERS_COLLECTION].find(query).sort("orderDate", -1).skip(skip).limit(top)
        for wo in cursor:
            eid = wo.get("equipmentId", "")
            if not eid:
                continue
            log = db["machinelogs"].find_one({"MachineID": eid}, sort=[("logTimestamp", -1)], projection={"Process_Temperature": 1, "Air_Temperature": 1, "Rotational_Speed": 1, "Torque": 1, "Tool_Wear": 1})
            engine_models = db[MANUALS_COLLECTION].distinct("engineModel")
            engine_model = engine_models[hash(eid) % max(1, len(engine_models))] if engine_models else "X15"
            if log:
                telemetry = {k: log.get(k, 0) for k in ["Process_Temperature", "Air_Temperature", "Rotational_Speed", "Torque", "Tool_Wear"]}
                telemetry["engineModel"] = engine_model
                try:
                    label, confidence = _predict_failure(telemetry)
                except Exception:
                    label, confidence = "No_Failure", 0.99
                fault_code, severity = _failure_label_to_fault_code_and_severity(label)
                criticality = confidence_severity_to_criticality(confidence, severity)
                predicted_failure = _fault_code_to_predicted_failure(fault_code, db) if fault_code else "No Failure"
                suggested_op, manual_ref = _suggested_operation_and_manual(fault_code, engine_model, db) if fault_code else ("None", f"Manual {engine_model}")
            else:
                predicted_failure, fault_code, criticality, confidence = "No Failure", "", 3, 0.99
                suggested_op, manual_ref = "None", f"Manual {engine_model}"
            results.append({
                "equipmentId": eid,
                "predictedFailure": predicted_failure,
                "faultCode": fault_code or "",
                "criticality": criticality,
                "confidence": round(confidence, 2),
                "suggestedOperation": suggested_op,
                "manualReference": manual_ref,
            })
    return {"d": {"results": results}}


class TelemetryBody(BaseModel):
    Process_Temperature: Optional[float] = None
    Air_Temperature: Optional[float] = None
    Rotational_Speed: Optional[float] = None
    Torque: Optional[float] = None
    Tool_Wear: Optional[float] = None
    engineModel: Optional[str] = "X15"


@app.post("/api/predict")
def predict_single(body: TelemetryBody):
    """Integration hook: predict failure_label and confidence for telemetry_data."""
    telemetry = body.model_dump()
    try:
        label, confidence = _predict_failure(telemetry)
        fault_code, severity = _failure_label_to_fault_code_and_severity(label)
        criticality = confidence_severity_to_criticality(confidence, severity)
        return {
            "failure_label": label,
            "confidence": round(confidence, 2),
            "faultCode": fault_code,
            "severity": severity,
            "criticality": criticality,
        }
    except FileNotFoundError as e:
        return {"error": str(e), "failure_label": "No_Failure", "confidence": 0.0}


class TriggerWorkOrderBody(BaseModel):
    equipmentId: str
    predictedFailure: Optional[str] = None
    faultCode: Optional[str] = None
    suggestedOperation: Optional[str] = None


@app.post("/api/triggerWorkOrder")
def trigger_work_order(body: TriggerWorkOrderBody):
    """Create a new WorkOrder in DB (SAP Action: Create Work Order)."""
    from datetime import datetime, timezone
    db = _db()
    order_id = f"WO-{10000 + db[WORK_ORDERS_COLLECTION].count_documents({})}"
    wo = {
        "orderId": order_id,
        "status": "Created",
        "priority": 2,
        "equipmentId": body.equipmentId,
        "actualWork": 0,
        "orderDate": datetime.now(timezone.utc),
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
        "triggeredFromPrediction": True,
        "predictedFailure": body.predictedFailure,
        "faultCode": body.faultCode,
        "suggestedOperation": body.suggestedOperation,
    }
    db[WORK_ORDERS_COLLECTION].insert_one(wo)
    return {"d": {"orderId": order_id, "message": "Work order created."}}


# Mount static files for the frontend (webapp folder) - MUST be at end after all API routes
# This serves UI5 frontend at root level
if _webapp_path.exists():
    app.mount("/", StaticFiles(directory=str(_webapp_path), html=True), name="webapp")
