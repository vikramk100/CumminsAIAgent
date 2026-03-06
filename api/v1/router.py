"""
API v1: Agentic dispatch briefing endpoint + audit trail + Work Order & Confirmations CRUD.

Updated to use Multi-Agent Architecture with MCP Server integration.
"""

from datetime import datetime, timezone
from typing import Optional

import base64

from fastapi import APIRouter, File, HTTPException, UploadFile
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
    """Create a new work order. orderId is auto-generated. Auto-generates prep recommendations."""
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
    
    # Auto-generate prep recommendations for this work order
    _generate_prep_for_work_order(db, order_id, body.equipmentId)
    
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


# ---------- Visual Inspection (Image Agent) ----------

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGES = 5


@router.post("/workorders/{orderId}/analyze-images")
async def analyze_images(orderId: str, files: list[UploadFile] = File(...)):
    """
    Accept up to 5 images for a work order and run VisionAgent CV analysis.

    The VisionAgent sends each image to Gemini 2.0 Flash (multimodal) via Vertex AI.
    Results are stored in MongoDB via the MCP store_image_analysis tool so the
    Orchestrator can incorporate visual findings into the Mission Briefing.
    """
    db = _get_db()
    wo = db["workorders"].find_one({"orderId": orderId})
    if not wo:
        raise HTTPException(status_code=404, detail=f"Work order {orderId} not found")

    if len(files) > MAX_IMAGES:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_IMAGES} images allowed per request")

    # Read and encode each uploaded file
    images_b64: list[str] = []
    mime_types: list[str] = []
    for f in files:
        content_type = f.content_type or "image/jpeg"
        if content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail=f"File '{f.filename}' has unsupported type '{content_type}'. Allowed: jpeg, png, webp, gif")
        raw = await f.read()
        images_b64.append(base64.b64encode(raw).decode("utf-8"))
        mime_types.append(content_type)

    # Run VisionAgent
    from api.agents.vision_agent import VisionAgent
    from api.mcp_server import store_image_analysis

    agent = VisionAgent()
    work_order_context = {
        "equipmentId": wo.get("equipmentId", ""),
        "issueDescription": wo.get("issueDescription", ""),
    }
    analysis = agent.analyze_images(images_b64, mime_types, work_order_context)

    # Store via MCP tool (single source of truth for all DB writes)
    analysis["file_count"] = len(files)
    store_image_analysis(orderId, analysis)

    return {
        "orderId": orderId,
        "analysis": analysis,
        "agent": "VisionAgent",
        "model": "gemini-2.0-flash-001 (multimodal)",
    }


@router.get("/workorders/{orderId}/image-analyses")
def get_image_analyses(orderId: str):
    """Return all stored image analyses for a work order."""
    from api.mcp_server import get_image_analyses as _get_analyses
    db = _get_db()
    if not db["workorders"].find_one({"orderId": orderId}):
        raise HTTPException(status_code=404, detail=f"Work order {orderId} not found")
    return {"results": _get_analyses(orderId)}


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


# =============================================================================
# Technician Helper: Tools, Spare Parts, and Prep Orders
# =============================================================================

TECHNICIAN_TOOLS_COLLECTION = "technician_tools"
SPARE_PARTS_COLLECTION = "spare_parts"
PREP_ORDERS_COLLECTION = "prep_orders"
WORK_ORDER_PREP_COLLECTION = "work_order_prep"


def _generate_prep_for_work_order(db, order_id: str, equipment_id: str, force: bool = False):
    """
    Generate and store recommended tools/parts for a work order.
    Called automatically when work order is created.
    If force=True, regenerates even if recommendations exist.
    """
    prep_coll = db[WORK_ORDER_PREP_COLLECTION]
    
    # Check if already exists
    existing = prep_coll.find_one({"orderId": order_id})
    if existing and not force:
        return existing
    
    # Get equipment's engine model from machine logs or default
    machine_log = db["machinelogs"].find_one({"MachineID": equipment_id})
    engine_model = "X15"  # Default
    
    # Get tools compatible with this engine
    tools = list(
        db[TECHNICIAN_TOOLS_COLLECTION]
        .find({"engineModels": engine_model}, {"_id": 0})
        .limit(15)
    )
    
    # Get parts compatible with this engine
    parts = list(
        db[SPARE_PARTS_COLLECTION]
        .find({"engineModels": engine_model}, {"_id": 0})
        .limit(15)
    )
    
    # Add selection state (for UI)
    # hasItem = false means technician doesn't have it yet (needs checkout)
    # availability shows stock status separately
    for tool in tools:
        tool["selected"] = False
        tool["hasItem"] = False  # Technician doesn't have it yet
    
    for part in parts:
        part["selected"] = False
        part["hasItem"] = False  # Technician doesn't have it yet
    
    now = datetime.now(timezone.utc)
    prep_doc = {
        "orderId": order_id,
        "equipmentId": equipment_id,
        "engineModel": engine_model,
        "recommendedTools": tools,
        "recommendedParts": parts,
        "generatedAt": now,
        "updatedAt": now
    }
    
    if existing:
        prep_coll.update_one({"orderId": order_id}, {"$set": prep_doc})
    else:
        prep_coll.insert_one(prep_doc)
    
    # Remove _id for return
    prep_doc.pop("_id", None)
    return prep_doc


# ---------- Technician Tools CRUD ----------

@router.get("/tools")
def list_tools(category: Optional[str] = None, availability: Optional[str] = None, limit: int = 200):
    """List all technician tools with optional filters."""
    db = _get_db()
    query = {}
    if category:
        query["category"] = category
    if availability:
        query["availability"] = availability
    tools = list(
        db[TECHNICIAN_TOOLS_COLLECTION]
        .find(query, {"_id": 0})
        .sort("name", 1)
        .limit(limit)
    )
    return {"results": tools}


@router.get("/tools/{toolId}")
def get_tool(toolId: str):
    """Get a single tool by ID."""
    db = _get_db()
    tool = db[TECHNICIAN_TOOLS_COLLECTION].find_one({"toolId": toolId}, {"_id": 0})
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool {toolId} not found")
    return tool


class CreateToolBody(BaseModel):
    name: str
    category: str
    description: Optional[str] = None
    quantity: int = 0
    location: Optional[str] = None
    engineModels: Optional[list[str]] = None


@router.post("/tools")
def create_tool(body: CreateToolBody):
    """Create a new tool."""
    db = _get_db()
    coll = db[TECHNICIAN_TOOLS_COLLECTION]
    count = coll.count_documents({})
    tool_id = f"TL-{200 + count:03d}"
    now = datetime.now(timezone.utc)
    
    # Determine availability
    if body.quantity == 0:
        availability = "out_of_stock"
    elif body.quantity <= 5:
        availability = "low_stock"
    else:
        availability = "in_stock"
    
    doc = {
        "toolId": tool_id,
        "name": body.name,
        "category": body.category,
        "description": body.description,
        "quantity": body.quantity,
        "availability": availability,
        "location": body.location,
        "engineModels": body.engineModels or [],
        "createdAt": now,
        "updatedAt": now,
    }
    coll.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


class UpdateToolBody(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    quantity: Optional[int] = None
    location: Optional[str] = None
    engineModels: Optional[list[str]] = None


@router.put("/tools/{toolId}")
def update_tool(toolId: str, body: UpdateToolBody):
    """Update a tool."""
    db = _get_db()
    coll = db[TECHNICIAN_TOOLS_COLLECTION]
    tool = coll.find_one({"toolId": toolId})
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool {toolId} not found")
    
    update = {"updatedAt": datetime.now(timezone.utc)}
    if body.name is not None:
        update["name"] = body.name
    if body.category is not None:
        update["category"] = body.category
    if body.description is not None:
        update["description"] = body.description
    if body.location is not None:
        update["location"] = body.location
    if body.engineModels is not None:
        update["engineModels"] = body.engineModels
    if body.quantity is not None:
        update["quantity"] = body.quantity
        if body.quantity == 0:
            update["availability"] = "out_of_stock"
        elif body.quantity <= 5:
            update["availability"] = "low_stock"
        else:
            update["availability"] = "in_stock"
    
    coll.update_one({"toolId": toolId}, {"$set": update})
    updated = coll.find_one({"toolId": toolId}, {"_id": 0})
    return updated


@router.delete("/tools/{toolId}")
def delete_tool(toolId: str):
    """Delete a tool."""
    db = _get_db()
    result = db[TECHNICIAN_TOOLS_COLLECTION].delete_one({"toolId": toolId})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail=f"Tool {toolId} not found")
    return {"ok": True, "toolId": toolId}


# ---------- Spare Parts CRUD ----------

@router.get("/spare-parts")
def list_spare_parts(category: Optional[str] = None, availability: Optional[str] = None, engineModel: Optional[str] = None, limit: int = 200):
    """List all spare parts with optional filters."""
    db = _get_db()
    query = {}
    if category:
        query["category"] = category
    if availability:
        query["availability"] = availability
    if engineModel:
        query["engineModels"] = engineModel
    parts = list(
        db[SPARE_PARTS_COLLECTION]
        .find(query, {"_id": 0})
        .sort("name", 1)
        .limit(limit)
    )
    return {"results": parts}


@router.get("/spare-parts/{partId}")
def get_spare_part(partId: str):
    """Get a single spare part by ID."""
    db = _get_db()
    part = db[SPARE_PARTS_COLLECTION].find_one({"partId": partId}, {"_id": 0})
    if not part:
        raise HTTPException(status_code=404, detail=f"Spare part {partId} not found")
    return part


class CreateSparePartBody(BaseModel):
    partNumber: str
    name: str
    category: str
    description: Optional[str] = None
    engineModels: Optional[list[str]] = None
    quantity: int = 0
    unitPrice: float = 0.0
    location: Optional[str] = None
    leadTimeDays: int = 0


@router.post("/spare-parts")
def create_spare_part(body: CreateSparePartBody):
    """Create a new spare part."""
    db = _get_db()
    coll = db[SPARE_PARTS_COLLECTION]
    count = coll.count_documents({})
    part_id = f"SP-{200 + count:03d}"
    now = datetime.now(timezone.utc)
    
    # Determine availability
    if body.quantity == 0:
        availability = "out_of_stock"
    elif body.quantity <= 5:
        availability = "low_stock"
    else:
        availability = "in_stock"
    
    doc = {
        "partId": part_id,
        "partNumber": body.partNumber,
        "name": body.name,
        "category": body.category,
        "description": body.description,
        "engineModels": body.engineModels or [],
        "quantity": body.quantity,
        "unitPrice": body.unitPrice,
        "availability": availability,
        "location": body.location,
        "leadTimeDays": body.leadTimeDays,
        "createdAt": now,
        "updatedAt": now,
    }
    coll.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


class UpdateSparePartBody(BaseModel):
    partNumber: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    engineModels: Optional[list[str]] = None
    quantity: Optional[int] = None
    unitPrice: Optional[float] = None
    location: Optional[str] = None
    leadTimeDays: Optional[int] = None


@router.put("/spare-parts/{partId}")
def update_spare_part(partId: str, body: UpdateSparePartBody):
    """Update a spare part."""
    db = _get_db()
    coll = db[SPARE_PARTS_COLLECTION]
    part = coll.find_one({"partId": partId})
    if not part:
        raise HTTPException(status_code=404, detail=f"Spare part {partId} not found")
    
    update = {"updatedAt": datetime.now(timezone.utc)}
    if body.partNumber is not None:
        update["partNumber"] = body.partNumber
    if body.name is not None:
        update["name"] = body.name
    if body.category is not None:
        update["category"] = body.category
    if body.description is not None:
        update["description"] = body.description
    if body.engineModels is not None:
        update["engineModels"] = body.engineModels
    if body.unitPrice is not None:
        update["unitPrice"] = body.unitPrice
    if body.location is not None:
        update["location"] = body.location
    if body.leadTimeDays is not None:
        update["leadTimeDays"] = body.leadTimeDays
    if body.quantity is not None:
        update["quantity"] = body.quantity
        if body.quantity == 0:
            update["availability"] = "out_of_stock"
        elif body.quantity <= 5:
            update["availability"] = "low_stock"
        else:
            update["availability"] = "in_stock"
    
    coll.update_one({"partId": partId}, {"$set": update})
    updated = coll.find_one({"partId": partId}, {"_id": 0})
    return updated


@router.delete("/spare-parts/{partId}")
def delete_spare_part(partId: str):
    """Delete a spare part."""
    db = _get_db()
    result = db[SPARE_PARTS_COLLECTION].delete_one({"partId": partId})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail=f"Spare part {partId} not found")
    return {"ok": True, "partId": partId}


# ---------- Prep Orders CRUD ----------

class PrepOrderItem(BaseModel):
    itemType: str  # "tool" or "spare_part"
    itemId: str
    name: str
    quantity: int = 1
    unitPrice: float = 0.0


class CreatePrepOrderBody(BaseModel):
    workOrderId: str
    items: list[PrepOrderItem]
    technicianId: Optional[str] = None
    technicianName: Optional[str] = None
    notes: Optional[str] = None


@router.get("/prep-orders")
def list_prep_orders(workOrderId: Optional[str] = None, status: Optional[str] = None, limit: int = 100):
    """List prep orders with optional filters."""
    db = _get_db()
    query = {}
    if workOrderId:
        query["workOrderId"] = workOrderId
    if status:
        query["status"] = status
    orders = list(
        db[PREP_ORDERS_COLLECTION]
        .find(query, {"_id": 0})
        .sort("orderDate", -1)
        .limit(limit)
    )
    return {"results": orders}


@router.get("/prep-orders/{prepOrderId}")
def get_prep_order(prepOrderId: str):
    """Get a single prep order by ID."""
    db = _get_db()
    order = db[PREP_ORDERS_COLLECTION].find_one({"prepOrderId": prepOrderId}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail=f"Prep order {prepOrderId} not found")
    return order


@router.post("/prep-orders")
def create_prep_order(body: CreatePrepOrderBody):
    """Create a new prep order (checkout)."""
    db = _get_db()
    coll = db[PREP_ORDERS_COLLECTION]
    
    # Verify work order exists
    wo = db[WORK_ORDERS_COLLECTION].find_one({"orderId": body.workOrderId})
    if not wo:
        raise HTTPException(status_code=404, detail=f"Work order {body.workOrderId} not found")
    
    count = coll.count_documents({})
    prep_order_id = f"PO-{10000 + count}"
    now = datetime.now(timezone.utc)
    
    # Calculate total amount from spare parts
    total_amount = sum(
        item.unitPrice * item.quantity 
        for item in body.items 
        if item.itemType == "spare_part"
    )
    
    items_data = [
        {
            "itemType": item.itemType,
            "itemId": item.itemId,
            "name": item.name,
            "quantity": item.quantity,
            "unitPrice": item.unitPrice,
            "status": "requested"
        }
        for item in body.items
    ]
    
    doc = {
        "prepOrderId": prep_order_id,
        "workOrderId": body.workOrderId,
        "orderDate": now,
        "status": "pending",
        "items": items_data,
        "technicianId": body.technicianId,
        "technicianName": body.technicianName,
        "totalAmount": total_amount,
        "notes": body.notes,
        "createdAt": now,
        "updatedAt": now,
    }
    coll.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


class UpdatePrepOrderBody(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


@router.put("/prep-orders/{prepOrderId}")
def update_prep_order(prepOrderId: str, body: UpdatePrepOrderBody):
    """Update prep order status."""
    db = _get_db()
    coll = db[PREP_ORDERS_COLLECTION]
    order = coll.find_one({"prepOrderId": prepOrderId})
    if not order:
        raise HTTPException(status_code=404, detail=f"Prep order {prepOrderId} not found")
    
    update = {"updatedAt": datetime.now(timezone.utc)}
    if body.status is not None:
        if body.status not in ("pending", "approved", "fulfilled", "cancelled"):
            raise HTTPException(status_code=400, detail="Invalid status")
        update["status"] = body.status
    if body.notes is not None:
        update["notes"] = body.notes
    
    coll.update_one({"prepOrderId": prepOrderId}, {"$set": update})
    updated = coll.find_one({"prepOrderId": prepOrderId}, {"_id": 0})
    return updated


@router.delete("/prep-orders/{prepOrderId}")
def delete_prep_order(prepOrderId: str):
    """Delete a prep order."""
    db = _get_db()
    result = db[PREP_ORDERS_COLLECTION].delete_one({"prepOrderId": prepOrderId})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail=f"Prep order {prepOrderId} not found")
    return {"ok": True, "prepOrderId": prepOrderId}


# ---------- Recommended Items for Work Order ----------

@router.get("/workorders/{orderId}/recommended-prep")
def get_recommended_prep(orderId: str):
    """
    Get recommended tools and spare parts for a work order.
    Returns pre-generated recommendations stored when work order was created.
    If not found, generates and stores them on-the-fly.
    """
    db = _get_db()
    
    # Get work order
    wo = db[WORK_ORDERS_COLLECTION].find_one({"orderId": orderId}, {"_id": 0})
    if not wo:
        raise HTTPException(status_code=404, detail=f"Work order {orderId} not found")
    
    # Check for stored prep recommendations
    prep = db[WORK_ORDER_PREP_COLLECTION].find_one({"orderId": orderId}, {"_id": 0})
    
    if not prep:
        # Generate if not exists (for older work orders)
        equipment_id = wo.get("equipmentId", "")
        prep = _generate_prep_for_work_order(db, orderId, equipment_id)
    
    return prep


@router.post("/workorders/{orderId}/regenerate-prep")
def regenerate_prep(orderId: str):
    """
    Regenerate prep recommendations for a work order.
    Useful if tools/parts inventory has changed.
    """
    db = _get_db()
    
    wo = db[WORK_ORDERS_COLLECTION].find_one({"orderId": orderId}, {"_id": 0})
    if not wo:
        raise HTTPException(status_code=404, detail=f"Work order {orderId} not found")
    
    equipment_id = wo.get("equipmentId", "")
    prep = _generate_prep_for_work_order(db, orderId, equipment_id, force=True)
    return prep


@router.post("/workorders/backfill-prep")
def backfill_prep_recommendations():
    """
    Backfill prep recommendations for all existing work orders that don't have them.
    Run this once after deploying the auto-generation feature.
    """
    db = _get_db()
    
    workorders = list(db[WORK_ORDERS_COLLECTION].find({}, {"orderId": 1, "equipmentId": 1, "_id": 0}))
    
    generated = 0
    skipped = 0
    
    for wo in workorders:
        order_id = wo.get("orderId")
        equipment_id = wo.get("equipmentId", "")
        
        # Check if already exists
        existing = db[WORK_ORDER_PREP_COLLECTION].find_one({"orderId": order_id})
        if existing:
            skipped += 1
            continue
        
        _generate_prep_for_work_order(db, order_id, equipment_id)
        generated += 1
    
    return {
        "ok": True,
        "generated": generated,
        "skipped": skipped,
        "total": len(workorders)
    }
