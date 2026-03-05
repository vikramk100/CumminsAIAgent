"""
Base Agent Configuration - Shared setup for all agents.
Provides MCP client tools and LLM configuration.
"""

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
import pymongo

# Import from our MCP server (using tools directly for in-process calls)
# In production, these would be MCP client calls
MONGODB_URI = os.environ.get(
    "MONGODB_URI",
    "mongodb+srv://sankethrp_db_user:<db_password>@workorderandconfirmatio.gfkc6h6.mongodb.net/?appName=WorkOrderAndConfirmations",
)
if "<db_password>" in MONGODB_URI and "MONGODB_PASSWORD" in os.environ:
    MONGODB_URI = MONGODB_URI.replace("<db_password>", os.environ["MONGODB_PASSWORD"])
DB_NAME = os.environ.get("MONGODB_DB", "sap_bnac")

_mongo_client: Optional[pymongo.MongoClient] = None


def _get_db():
    """Get MongoDB database connection."""
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = pymongo.MongoClient(MONGODB_URI)
    return _mongo_client[DB_NAME]


# ============================================================================
# MCP Tool Wrappers - These wrap MCP server calls as LangChain tools
# In production, these would use an MCP client to call the MCP server
# ============================================================================

@tool
def mcp_get_work_order(order_id: str) -> dict[str, Any]:
    """
    [MCP Tool] Retrieve a work order from the database.
    Args:
        order_id: The work order ID
    Returns:
        Work order data including status, priority, equipmentId
    """
    from api.mcp_server import get_work_order
    return get_work_order(order_id)


@tool
def mcp_get_machine_log(machine_id: str) -> dict[str, Any]:
    """
    [MCP Tool] Get latest telemetry data for an equipment.
    Args:
        machine_id: The equipment/machine ID
    Returns:
        Telemetry snapshot with temperatures, speed, torque, tool wear
    """
    from api.mcp_server import get_machine_log
    return get_machine_log(machine_id)


@tool
def mcp_get_ml_prediction(machine_id: str) -> dict[str, Any]:
    """
    [MCP Tool] Run ML failure prediction for equipment.
    Args:
        machine_id: The equipment ID to analyze
    Returns:
        ML prediction with failure_label, confidence, fault_code, severity, telemetry
    """
    from api.mcp_server import get_ml_prediction
    return get_ml_prediction(machine_id)


@tool
def mcp_query_manuals(fault_code: str, engine_model: Optional[str] = None, limit: int = 5) -> list[dict[str, Any]]:
    """
    [MCP Tool] Search engine manuals for repair procedures.
    Args:
        fault_code: Fault code to search (e.g., "OSF", "HDF")
        engine_model: Optional engine model filter
        limit: Max results
    Returns:
        List of manual entries with repair content, section, page number
    """
    from api.mcp_server import query_manuals
    return query_manuals(fault_code, engine_model, limit)


@tool
def mcp_get_historical_fixes(system_affected: str, limit: int = 10) -> list[dict[str, Any]]:
    """
    [MCP Tool] Search historical repair data for similar issues.
    Args:
        system_affected: System type (e.g., "Engine", "Cooling", "Fuel")
        limit: Max results
    Returns:
        List of historical fixes with resolutions and diagnostic steps
    """
    from api.mcp_server import get_historical_fixes
    return get_historical_fixes(system_affected, limit)


@tool
def mcp_get_diagnostic_info(fault_code: str) -> dict[str, Any]:
    """
    [MCP Tool] Get diagnostic details for a fault code.
    Args:
        fault_code: The fault code to look up
    Returns:
        Diagnostic info with system_affected, symptoms, resolution, severity
    """
    from api.mcp_server import get_diagnostic_info
    return get_diagnostic_info(fault_code)


@tool
def mcp_get_operations(order_id: str) -> list[dict[str, Any]]:
    """
    [MCP Tool] Get operations for a work order.
    Args:
        order_id: The work order ID
    Returns:
        List of operations with descriptions and status
    """
    from api.mcp_server import get_operations_for_order
    return get_operations_for_order(order_id)


@tool
def mcp_get_confirmations(order_id: str) -> list[dict[str, Any]]:
    """
    [MCP Tool] Get confirmations for a work order.
    Args:
        order_id: The work order ID
    Returns:
        List of recorded confirmations
    """
    from api.mcp_server import get_confirmations_for_order
    return get_confirmations_for_order(order_id)


@tool
def mcp_get_audit_trail(order_id: str) -> list[dict[str, Any]]:
    """
    [MCP Tool] Get audit trail for a work order.
    Args:
        order_id: The work order ID
    Returns:
        List of audit events (tool checklist updates)
    """
    from api.mcp_server import get_audit_trail
    return get_audit_trail(order_id)


@tool
def mcp_get_engine_models() -> list[str]:
    """
    [MCP Tool] Get list of available engine models.
    Returns:
        List of engine model names
    """
    from api.mcp_server import get_engine_models
    return get_engine_models()


# ============================================================================
# Agent Tool Sets
# ============================================================================

DIAGNOSTIC_TOOLS = [
    mcp_get_work_order,
    mcp_get_machine_log,
    mcp_get_ml_prediction,
    mcp_get_diagnostic_info,
    mcp_get_engine_models,
]

PRESCRIPTION_TOOLS = [
    mcp_query_manuals,
    mcp_get_historical_fixes,
    mcp_get_operations,
    mcp_get_confirmations,
    mcp_get_audit_trail,
]

ALL_MCP_TOOLS = DIAGNOSTIC_TOOLS + PRESCRIPTION_TOOLS


# ============================================================================
# Tool Extraction Utilities
# ============================================================================

def extract_tools_from_text(text: str) -> list[str]:
    """
    Extract tool names from text content.
    Finds common tools and socket sizes.
    """
    if not text:
        return []
    t = text.lower()
    candidates = [
        ("torque wrench", "Torque Wrench"),
        ("multimeter", "Multimeter"),
        ("socket", "Socket Set"),
        ("screwdriver", "Screwdriver Set"),
        ("fuel pressure", "Fuel Pressure Gauge"),
        ("coolant tester", "Coolant Tester"),
        ("hose pliers", "Hose Pliers"),
        ("line wrench", "Line Wrenches"),
        ("pressure gauge", "Pressure Gauge"),
        ("scan tool", "Scan Tool"),
        ("wrench", "Wrench Set"),
        ("pliers", "Pliers"),
    ]
    found = []
    for needle, label in candidates:
        if needle in t and label not in found:
            found.append(label)
    # Extract socket sizes like "10mm"
    for m in re.findall(r"\b(\d{1,2})\s*mm\b", t):
        s = f"{m}mm Socket"
        if s not in found:
            found.append(s)
    return found[:10]


def build_timeline(
    order_date: Optional[datetime],
    operations: list[dict],
    confirmations: list[dict],
    audit_events: list[dict],
    status: str,
) -> list[dict[str, Any]]:
    """Build a chronological timeline of work order events."""
    timeline: list[dict[str, Any]] = []
    
    if isinstance(order_date, datetime):
        timeline.append({
            "type": "status",
            "title": "Work order created",
            "description": f"Status: {status}",
            "at": order_date,
        })
    
    for op in operations:
        timeline.append({
            "type": "operation",
            "title": op.get("description") or "Operation",
            "description": f"Operation {op.get('operationId', '')} - Status: {op.get('status', '')}",
            "at": op.get("plannedStart") or order_date,
        })
    
    for c in confirmations:
        timeline.append({
            "type": "confirmation",
            "title": "Confirmation recorded",
            "description": c.get("confirmationText") or "",
            "at": c.get("confirmedAt") or order_date,
        })
    
    for ev in audit_events:
        timeline.append({
            "type": "audit",
            "title": "Tool checklist updated",
            "description": f"{ev.get('toolName')} marked "
            f"{'checked' if ev.get('checked') else 'unchecked'}"
            f"{' by ' + str(ev.get('userId')) if ev.get('userId') else ''}",
            "at": ev.get("timestamp") or order_date,
        })
    
    # Sort by timestamp
    timeline.sort(key=lambda e: e.get("at") or order_date or datetime.now(timezone.utc))
    return timeline
