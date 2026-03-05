"""
API v1: Agentic dispatch briefing endpoint + audit trail + Work Order & Confirmations CRUD.

Updated to use Multi-Agent Architecture with MCP Server integration.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Import from new multi-agent system
from api.agents.orchestrator import get_dispatch_brief, run_chat, suggest_categories_from_description
from api.mcp_server import _get_db

router = APIRouter(prefix="/api/v1", tags=["v1"])

WORK_ORDERS_COLLECTION = "workorders"
CONFIRMATIONS_COLLECTION = "confirmations"
OPERATIONS_COLLECTION = "operations"


@router.get("/equipments")
def list_equipments(limit: int = 200):
    """
    Returns a list of distinct equipments with simple summary:
    equipmentId, engineModel (if available), latest criticality text/state.
    """
    db = _get_db()
    # Distinct equipment IDs from workorders
    equipment_ids = db["workorders"].distinct("equipmentId")
    results = []
    manuals_coll = db["manuals"]
    diag_coll = db["diagnostics"]

    for eid in equipment_ids[:limit]:
        if not eid:
            continue
        # Simple engine model lookup from manuals
        manual = manuals_coll.find_one({"engineModel": {"$exists": True}}, {"engineModel": 1})
        engine_model = manual.get("engineModel") if manual else "X15"

        # Derive a rough "criticality" from diagnostics if available
        diag = diag_coll.find_one({}, {"severity": 1})
        severity = (diag or {}).get("severity", 3)
        if severity <= 2:
            crit_text, crit_state = "High", "Error"
        elif severity == 3:
            crit_text, crit_state = "Medium", "Warning"
        else:
            crit_text, crit_state = "Low", "Success"

        results.append(
            {
                "equipmentId": eid,
                "engineModel": engine_model,
                "criticalityText": crit_text,
                "criticalityState": crit_state,
            }
        )

    return {"results": results}


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


# ---------- Work Order CRUD ----------


class CreateWorkOrderBody(BaseModel):
    equipmentId: str
    status: str = "Created"
    priority: int = 2
    actualWork: float = 0.0
    issueDescription: Optional[str] = None
    selectedCategories: Optional[list[str]] = None


class UpdateWorkOrderBody(BaseModel):
    status: Optional[str] = None
    priority: Optional[int] = None
    equipmentId: Optional[str] = None
    actualWork: Optional[float] = None
    issueDescription: Optional[str] = None
    selectedCategories: Optional[list[str]] = None


@router.post("/workorders")
def create_workorder(body: CreateWorkOrderBody):
    """Create a new work order. orderId is auto-generated."""
    db = _get_db()
    coll = db[WORK_ORDERS_COLLECTION]
    count = coll.count_documents({})
    order_id = f"WO-{10000 + count}"
    now = datetime.now(timezone.utc)
    doc = {
        "orderId": order_id,
        "status": body.status,
        "priority": body.priority,
        "equipmentId": body.equipmentId,
        "actualWork": body.actualWork,
        "orderDate": now,
        "createdAt": now,
        "updatedAt": now,
    }
    if body.issueDescription is not None:
        doc["issueDescription"] = body.issueDescription
    if body.selectedCategories is not None:
        doc["selectedCategories"] = body.selectedCategories
    coll.insert_one(doc)
    out = {k: v for k, v in doc.items() if k != "_id"}
    return out


@router.get("/workorders/{orderId}")
def get_workorder(orderId: str):
    """Get a single work order with its confirmations."""
    db = _get_db()
    wo = db[WORK_ORDERS_COLLECTION].find_one({"orderId": orderId}, {"_id": 0})
    if not wo:
        raise HTTPException(status_code=404, detail=f"Work order {orderId} not found")
    confirmations = list(db[CONFIRMATIONS_COLLECTION].find({"orderId": orderId}, {"_id": 0}))
    wo["confirmations"] = confirmations
    return wo


@router.put("/workorders/{orderId}")
def update_workorder(orderId: str, body: UpdateWorkOrderBody):
    """Update a work order (partial update)."""
    db = _get_db()
    wo = db[WORK_ORDERS_COLLECTION].find_one({"orderId": orderId})
    if not wo:
        raise HTTPException(status_code=404, detail=f"Work order {orderId} not found")
    update = {"updatedAt": datetime.now(timezone.utc)}
    if body.status is not None:
        update["status"] = body.status
    if body.priority is not None:
        update["priority"] = body.priority
    if body.equipmentId is not None:
        update["equipmentId"] = body.equipmentId
    if body.actualWork is not None:
        update["actualWork"] = body.actualWork
    if body.issueDescription is not None:
        update["issueDescription"] = body.issueDescription
    if body.selectedCategories is not None:
        update["selectedCategories"] = body.selectedCategories
    db[WORK_ORDERS_COLLECTION].update_one({"orderId": orderId}, {"$set": update})
    updated = db[WORK_ORDERS_COLLECTION].find_one({"orderId": orderId}, {"_id": 0})
    return updated


@router.delete("/workorders/{orderId}")
def delete_workorder(orderId: str):
    """Delete a work order and its confirmations and operations."""
    db = _get_db()
    wo = db[WORK_ORDERS_COLLECTION].find_one({"orderId": orderId})
    if not wo:
        raise HTTPException(status_code=404, detail=f"Work order {orderId} not found")
    db[CONFIRMATIONS_COLLECTION].delete_many({"orderId": orderId})
    db[OPERATIONS_COLLECTION].delete_many({"orderId": orderId})
    db[WORK_ORDERS_COLLECTION].delete_one({"orderId": orderId})
    return {"ok": True, "orderId": orderId}


# ---------- Confirmations CRUD (under work order) ----------


class CreateConfirmationBody(BaseModel):
    confirmationText: str
    status: str = "Submitted"
    equipmentId: Optional[str] = None
    actualWork: Optional[float] = None


class UpdateConfirmationBody(BaseModel):
    confirmationText: Optional[str] = None
    status: Optional[str] = None
    equipmentId: Optional[str] = None
    actualWork: Optional[float] = None


@router.get("/workorders/{orderId}/confirmations")
def list_confirmations(orderId: str):
    """List all confirmations for a work order."""
    db = _get_db()
    wo = db[WORK_ORDERS_COLLECTION].find_one({"orderId": orderId})
    if not wo:
        raise HTTPException(status_code=404, detail=f"Work order {orderId} not found")
    confirmations = list(db[CONFIRMATIONS_COLLECTION].find({"orderId": orderId}, {"_id": 0}).sort("confirmedAt", 1))
    return {"results": confirmations}


@router.post("/workorders/{orderId}/confirmations")
def create_confirmation(orderId: str, body: CreateConfirmationBody):
    """Create a confirmation for a work order. confirmationId is auto-generated."""
    db = _get_db()
    wo = db[WORK_ORDERS_COLLECTION].find_one({"orderId": orderId})
    if not wo:
        raise HTTPException(status_code=404, detail=f"Work order {orderId} not found")
    count = db[CONFIRMATIONS_COLLECTION].count_documents({"orderId": orderId})
    confirmation_id = f"CF-{orderId}-{count + 1:02d}"
    now = datetime.now(timezone.utc)
    equipment_id = body.equipmentId or wo.get("equipmentId") or ""
    actual_work = body.actualWork if body.actualWork is not None else 0.0
    doc = {
        "orderId": orderId,
        "confirmationId": confirmation_id,
        "confirmationText": body.confirmationText,
        "status": body.status,
        "equipmentId": equipment_id,
        "actualWork": actual_work,
        "confirmedAt": now,
        "createdAt": now,
        "updatedAt": now,
    }
    db[CONFIRMATIONS_COLLECTION].insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


@router.get("/workorders/{orderId}/confirmations/{confirmationId}")
def get_confirmation(orderId: str, confirmationId: str):
    """Get a single confirmation."""
    db = _get_db()
    c = db[CONFIRMATIONS_COLLECTION].find_one(
        {"orderId": orderId, "confirmationId": confirmationId},
        {"_id": 0},
    )
    if not c:
        raise HTTPException(status_code=404, detail=f"Confirmation {confirmationId} not found")
    return c


@router.put("/workorders/{orderId}/confirmations/{confirmationId}")
def update_confirmation(orderId: str, confirmationId: str, body: UpdateConfirmationBody):
    """Update a confirmation (partial update)."""
    db = _get_db()
    c = db[CONFIRMATIONS_COLLECTION].find_one({"orderId": orderId, "confirmationId": confirmationId})
    if not c:
        raise HTTPException(status_code=404, detail=f"Confirmation {confirmationId} not found")
    update = {"updatedAt": datetime.now(timezone.utc)}
    if body.confirmationText is not None:
        update["confirmationText"] = body.confirmationText
    if body.status is not None:
        update["status"] = body.status
    if body.equipmentId is not None:
        update["equipmentId"] = body.equipmentId
    if body.actualWork is not None:
        update["actualWork"] = body.actualWork
    db[CONFIRMATIONS_COLLECTION].update_one(
        {"orderId": orderId, "confirmationId": confirmationId},
        {"$set": update},
    )
    updated = db[CONFIRMATIONS_COLLECTION].find_one(
        {"orderId": orderId, "confirmationId": confirmationId},
        {"_id": 0},
    )
    return updated


@router.delete("/workorders/{orderId}/confirmations/{confirmationId}")
def delete_confirmation(orderId: str, confirmationId: str):
    """Delete a confirmation."""
    db = _get_db()
    result = db[CONFIRMATIONS_COLLECTION].delete_one(
        {"orderId": orderId, "confirmationId": confirmationId},
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail=f"Confirmation {confirmationId} not found")
    return {"ok": True, "confirmationId": confirmationId}


# ---------- Dispatch brief (existing) ----------


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


class ChatBody(BaseModel):
    orderId: str
    question: str


@router.post("/chat")
def chat(body: ChatBody):
    """
    Chat-style Q&A endpoint for the dispatcher UI.
    Answers questions about a specific work order / equipment using the multi-agent system.
    """
    # Build minimal context for chat - full dispatch context is built by the orchestrator
    from api.mcp_server import get_work_order
    work_order = get_work_order(body.orderId)
    if work_order.get("error"):
        raise HTTPException(status_code=404, detail=work_order["error"])
    
    context = {"orderId": body.orderId, "work_order": work_order}
    result = run_chat(context, body.question)
    return result


class SuggestCategoriesBody(BaseModel):
    issueDescription: str


@router.post("/suggest-categories")
def suggest_categories(body: SuggestCategoriesBody):
    """
    ML classification step: given an issue description, suggest category labels (e.g. Engine, Cooling)
    using Gemini. Frontend shows these as checkboxes for the user to select before creating the work order.
    """
    suggestions = suggest_categories_from_description(body.issueDescription or "")
    return {"suggestions": suggestions}


INSIGHT_FEEDBACK_COLLECTION = "insight_feedback"


class InsightFeedbackBody(BaseModel):
    orderId: str
    equipmentId: Optional[str] = None
    rating: str  # "up" | "down"
    source: str = "thought_process"
    feedbackText: Optional[str] = None
    rootCauseAnalysis: Optional[str] = None
    userId: Optional[str] = None


@router.post("/insight-feedback")
def insight_feedback(body: InsightFeedbackBody):
    """
    Persist user feedback (thumbs up/down) on AI-generated insights for model improvement.
    Stored in MongoDB collection: insight_feedback.
    Use scripts/export_insight_feedback.py to export for fine-tuning or RLHF.
    """
    if body.rating not in ("up", "down"):
        raise HTTPException(status_code=400, detail="rating must be 'up' or 'down'")
    db = _get_db()
    doc = {
        "orderId": body.orderId,
        "equipmentId": body.equipmentId,
        "rating": body.rating,
        "source": body.source,
        "feedbackText": body.feedbackText,
        "rootCauseAnalysis": body.rootCauseAnalysis,
        "userId": body.userId,
        "timestamp": datetime.now(timezone.utc),
    }
    db[INSIGHT_FEEDBACK_COLLECTION].insert_one(doc)
    return {"ok": True}
