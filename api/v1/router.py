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


@router.get("/workorders")
def list_workorders(limit: int = 100):
  """
  Returns a list of WorkOrders with embedded Confirmations.
  Shape:
  [
    {
      orderId, status, priority, equipmentId, actualWork, orderDate, confirmations: [...]
    }
  ]
  """
  db = _get_db()
  # Base work orders list
  workorders = list(
    db["workorders"]
    .find({}, {"_id": 0})
    .sort("orderDate", -1)
    .limit(limit)
  )
  # All confirmations grouped by orderId
  confirmations = list(db["confirmations"].find({}, {"_id": 0}))
  conf_by_order = {}
  for c in confirmations:
    oid = c.get("orderId")
    if not oid:
      continue
    conf_by_order.setdefault(oid, []).append(c)
  for wo in workorders:
    oid = wo.get("orderId")
    wo["confirmations"] = conf_by_order.get(oid, [])
  return {"results": workorders}


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
