"""
API v1: Agentic dispatch briefing endpoint + audit trail.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.dispatch_agent import get_dispatch_brief
from api.agent_tools import _get_db

router = APIRouter(prefix="/api/v1", tags=["v1"])


@router.get("/dispatch-brief/{orderId}")
def dispatch_brief(orderId: str):
    """
    Trigger the agentic flow for the given WorkOrder.
    Returns context package + Technician Mission Briefing (root_cause_analysis, required_tools, estimated_repair_time, manual_reference_snippet).
    """
    result = get_dispatch_brief(orderId)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


class AuditTrailBody(BaseModel):
    orderId: str
    equipmentId: str
    toolName: str
    checked: bool
    userId: Optional[str] = None
    source: str = "ui5"


@router.post("/audit-trail")
def audit_trail(body: AuditTrailBody):
    """
    Persist an audit event when a technician confirms tools / steps.
    Stored in MongoDB collection: audit_trail
    """
    db = _get_db()
    doc = body.model_dump()
    doc["timestamp"] = datetime.now(timezone.utc)
    db["audit_trail"].insert_one(doc)
    return {"ok": True}
