"""
MCP Server - Model Context Protocol server using FastMCP.
Exposes MongoDB queries as MCP tools for agents to invoke.
"""

import os
import re
from pathlib import Path
from typing import Any, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from mcp.server.fastmcp import FastMCP
import pymongo

# MongoDB Configuration
MONGODB_URI = os.environ.get(
    "MONGODB_URI",
    "mongodb+srv://sankethrp_db_user:<db_password>@workorderandconfirmatio.gfkc6h6.mongodb.net/?appName=WorkOrderAndConfirmations",
)
if "<db_password>" in MONGODB_URI and "MONGODB_PASSWORD" in os.environ:
    MONGODB_URI = MONGODB_URI.replace("<db_password>", os.environ["MONGODB_PASSWORD"])

DB_NAME = os.environ.get("MONGODB_DB", "sap_bnac")

# Collection names
MANUALS_COLLECTION = "manuals"
DIAGNOSTICS_COLLECTION = "diagnostics"
MACHINE_LOGS_COLLECTION = "machinelogs"
WORK_ORDERS_COLLECTION = "workorders"
CONFIRMATIONS_COLLECTION = "confirmations"
OPERATIONS_COLLECTION = "operations"
AUDIT_TRAIL_COLLECTION = "audit_trail"

# Initialize FastMCP server
mcp = FastMCP("WorkOrderAIAgent-MCP")

_mongo_client: Optional[pymongo.MongoClient] = None


def _get_db():
    """Get MongoDB database connection."""
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = pymongo.MongoClient(MONGODB_URI)
    return _mongo_client[DB_NAME]


# ============================================================================
# MCP TOOLS - Database Queries
# ============================================================================

@mcp.tool()
def get_work_order(order_id: str) -> dict[str, Any]:
    """
    Retrieve a work order by its ID from the database.
    
    Args:
        order_id: The unique identifier of the work order
        
    Returns:
        Work order document with status, priority, equipmentId, orderDate, etc.
    """
    db = _get_db()
    wo = db[WORK_ORDERS_COLLECTION].find_one({"orderId": order_id}, {"_id": 0})
    if not wo:
        return {"error": f"Work order {order_id} not found"}
    return wo


@mcp.tool()
def get_machine_log(machine_id: str) -> dict[str, Any]:
    """
    Get the latest telemetry/machine log for an equipment.
    
    Args:
        machine_id: The equipment/machine ID
        
    Returns:
        Latest machine log with Process_Temperature, Air_Temperature, 
        Rotational_Speed, Torque, Tool_Wear, failure_label, symptom
    """
    db = _get_db()
    log = db[MACHINE_LOGS_COLLECTION].find_one(
        {"MachineID": machine_id},
        sort=[("logTimestamp", -1)],
        projection={
            "_id": 0,
            "Process_Temperature": 1, 
            "Air_Temperature": 1, 
            "Rotational_Speed": 1,
            "Torque": 1, 
            "Tool_Wear": 1, 
            "failure_label": 1, 
            "symptom": 1,
            "logTimestamp": 1,
        },
    )
    if not log:
        return {"error": f"No machine log found for {machine_id}"}
    return log


@mcp.tool()
def get_ml_prediction(machine_id: str) -> dict[str, Any]:
    """
    Run ML classification for a machine to predict failure type.
    
    Args:
        machine_id: The equipment/machine ID to analyze
        
    Returns:
        Prediction with failure_label, confidence, fault_code, severity, symptom, telemetry
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
        return {
            "failure_label": "No_Failure", 
            "confidence": 0.0, 
            "fault_code": "", 
            "symptom": "", 
            "message": "No log for machine"
        }
    
    # Get engine model from manuals
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
        # Import ML model from scripts
        import sys
        script_dir = Path(__file__).resolve().parent.parent / "scripts"
        sys.path.insert(0, str(script_dir))
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


@mcp.tool()
def query_manuals(fault_code: str, engine_model: Optional[str] = None, limit: int = 5) -> list[dict[str, Any]]:
    """
    Search engine manuals for repair procedures related to a fault code.
    
    Args:
        fault_code: The fault code to search for (e.g., "OSF", "HDF", "PWF")
        engine_model: Optional specific engine model to filter (e.g., "X15", "ISX")
        limit: Maximum number of results to return
        
    Returns:
        List of manual entries with content, section, pageNumber, engineModel
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
    
    cursor = db[MANUALS_COLLECTION].find(
        query, 
        {"_id": 0, "content": 1, "section": 1, "pageNumber": 1, "engineModel": 1}
    ).limit(limit)
    
    return [
        {
            "content": d.get("content", "")[:1500], 
            "section": d.get("section"), 
            "pageNumber": d.get("pageNumber"), 
            "engineModel": d.get("engineModel")
        } 
        for d in cursor
    ]


@mcp.tool()
def get_historical_fixes(system_affected: str, limit: int = 10) -> list[dict[str, Any]]:
    """
    Search diagnostics and confirmations for historical repair data.
    
    Args:
        system_affected: The system to search for (e.g., "Engine", "Cooling", "Fuel")
        limit: Maximum number of results to return
        
    Returns:
        List of historical fixes with resolution, diagnostic_steps, or confirmationText
    """
    db = _get_db()
    if not system_affected:
        return []
    
    # Search diagnostics collection
    diag_cursor = db[DIAGNOSTICS_COLLECTION].find(
        {"system_affected": {"$regex": re.escape(system_affected), "$options": "i"}},
        {"_id": 0, "resolution": 1, "diagnostic_steps": 1},
    ).limit(limit)
    
    results = []
    for d in diag_cursor:
        results.append({
            "source": "diagnostic",
            "resolution": (d.get("resolution") or "")[:500],
            "diagnostic_steps": (d.get("diagnostic_steps") or "")[:500],
        })
    
    # Search confirmations collection
    conf_cursor = db[CONFIRMATIONS_COLLECTION].find(
        {"confirmationText": {"$regex": "completed|replaced|inspected|repair", "$options": "i"}},
        {"_id": 0, "confirmationText": 1, "actualWork": 1},
    ).limit(limit)
    
    for c in conf_cursor:
        results.append({
            "source": "confirmation",
            "confirmationText": (c.get("confirmationText") or "")[:500],
            "actualWork": c.get("actualWork"),
        })
    
    return results[:limit]


@mcp.tool()
def get_diagnostic_info(fault_code: str) -> dict[str, Any]:
    """
    Get detailed diagnostic information for a fault code.
    
    Args:
        fault_code: The fault code to look up
        
    Returns:
        Diagnostic entry with system_affected, symptoms, resolution, severity
    """
    db = _get_db()
    diag = db[DIAGNOSTICS_COLLECTION].find_one(
        {"fault_code": fault_code},
        {"_id": 0}
    )
    if not diag:
        return {"error": f"No diagnostic info for fault code {fault_code}"}
    return diag


@mcp.tool()
def get_operations_for_order(order_id: str) -> list[dict[str, Any]]:
    """
    Get all operations associated with a work order.
    
    Args:
        order_id: The work order ID
        
    Returns:
        List of operations with operationId, description, status, plannedStart
    """
    db = _get_db()
    ops = list(db[OPERATIONS_COLLECTION].find({"orderId": order_id}, {"_id": 0}))
    return ops


@mcp.tool()
def get_confirmations_for_order(order_id: str) -> list[dict[str, Any]]:
    """
    Get all confirmations recorded for a work order.
    
    Args:
        order_id: The work order ID
        
    Returns:
        List of confirmations with confirmationText, confirmedAt, actualWork
    """
    db = _get_db()
    confs = list(db[CONFIRMATIONS_COLLECTION].find({"orderId": order_id}, {"_id": 0}))
    return confs


@mcp.tool()
def get_audit_trail(order_id: str) -> list[dict[str, Any]]:
    """
    Get audit trail events for a work order (tool checklist updates).
    
    Args:
        order_id: The work order ID
        
    Returns:
        List of audit events sorted by timestamp
    """
    db = _get_db()
    events = list(
        db[AUDIT_TRAIL_COLLECTION]
        .find({"orderId": order_id}, {"_id": 0})
        .sort("timestamp", 1)
    )
    return events


@mcp.tool()
def get_engine_models() -> list[str]:
    """
    Get list of all distinct engine models in the manuals database.
    
    Returns:
        List of engine model names (e.g., ["X15", "ISX", "L9"])
    """
    db = _get_db()
    return db[MANUALS_COLLECTION].distinct("engineModel")


@mcp.tool()
def list_work_orders(limit: int = 50, status_filter: Optional[str] = None) -> list[dict[str, Any]]:
    """
    List work orders with optional filtering.
    
    Args:
        limit: Maximum number of work orders to return
        status_filter: Optional status to filter by (e.g., "OPEN", "CRTD", "COMP")
        
    Returns:
        List of work orders
    """
    db = _get_db()
    query = {}
    if status_filter:
        query["status"] = status_filter
    
    cursor = db[WORK_ORDERS_COLLECTION].find(
        query, {"_id": 0}
    ).sort("orderDate", -1).limit(limit)
    
    return list(cursor)


# ============================================================================
# MCP Server Runner
# ============================================================================

def run_mcp_server():
    """Run the MCP server (for standalone execution)."""
    mcp.run()


if __name__ == "__main__":
    run_mcp_server()
