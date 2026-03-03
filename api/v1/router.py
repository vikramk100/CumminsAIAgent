"""
API v1: Agentic dispatch briefing endpoint.
"""

from fastapi import APIRouter, HTTPException

from api.dispatch_agent import get_dispatch_brief

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
