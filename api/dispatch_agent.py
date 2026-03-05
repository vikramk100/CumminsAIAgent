"""
Agentic AI Dispatcher: builds context from tools and produces Technician Mission Briefing via Google Gemini.
"""

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from api.agent_tools import get_ml_prediction, query_manuals, get_historical_fixes, _get_db

DB_NAME = os.environ.get("MONGODB_DB", "sap_bnac")
DIAGNOSTICS_COLLECTION = "diagnostics"
WORK_ORDERS_COLLECTION = "workorders"
MANUALS_COLLECTION = "manuals"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

MISSION_BRIEFING_SCHEMA = {
    "root_cause_analysis": "string",
    "required_tools": "list of strings, e.g. [Torque Wrench, Multimeter, 10mm Socket]",
    "estimated_repair_time": "number (minutes)",
    "manual_reference_snippet": "string",
    "thought_process": "string explaining which signals (ML prediction, manuals, historical fixes, timeline) were used",
}


def _fault_code_to_system_affected(fault_code: str) -> str:
    db = _get_db()
    d = db[DIAGNOSTICS_COLLECTION].find_one({"fault_code": fault_code}, {"system_affected": 1})
    return (d.get("system_affected") or "Engine") if d else "Engine"


def build_context_package(order_id: str) -> dict[str, Any]:
    """Load WorkOrder/MachineLog, run tools, return context for the LLM."""
    db = _get_db()
    wo = db[WORK_ORDERS_COLLECTION].find_one({"orderId": order_id})
    if not wo:
        return {"error": f"WorkOrder {order_id} not found", "orderId": order_id}
    equipment_id = wo.get("equipmentId") or ""
    ml_result = get_ml_prediction(equipment_id)
    fault_code = ml_result.get("fault_code") or ""
    system_affected = _fault_code_to_system_affected(fault_code) if fault_code else "Engine"
    engine_models = db[MANUALS_COLLECTION].distinct("engineModel")
    engine_model = engine_models[hash(equipment_id) % max(1, len(engine_models))] if engine_models else "X15"
    manuals = query_manuals(fault_code, engine_model=engine_model, limit=5)
    historical = get_historical_fixes(system_affected, limit=5)

    # Extended work order context for UI detail view
    operations = list(db["operations"].find({"orderId": order_id}, {"_id": 0}))
    confirmations = list(db["confirmations"].find({"orderId": order_id}, {"_id": 0}))
    audit_events = list(
        db["audit_trail"]
        .find({"orderId": order_id}, {"_id": 0})
        .sort("timestamp", 1)
    )

    order_date = wo.get("orderDate")
    last_conf_dt: Optional[datetime] = None
    for c in confirmations:
        dt = c.get("confirmedAt")
        if isinstance(dt, datetime) and (last_conf_dt is None or dt > last_conf_dt):
            last_conf_dt = dt
    end_dt = last_conf_dt or datetime.now(timezone.utc)
    days_to_solve: Optional[int] = None
    if isinstance(order_date, datetime):
        try:
            # Normalize naive datetimes to UTC to avoid offset-naive vs offset-aware errors
            od = order_date
            if od.tzinfo is None:
                od = od.replace(tzinfo=timezone.utc)
            ed = end_dt
            if ed.tzinfo is None:
                ed = ed.replace(tzinfo=timezone.utc)
            days_to_solve = (ed - od).days
        except Exception:
            days_to_solve = None

    issue_description = (wo.get("issueDescription") or "").strip()
    if not issue_description and operations:
        # Prefer the first operation description as issue summary
        issue_description = operations[0].get("description") or ""

    technician = None
    if audit_events:
        first_user = audit_events[0].get("userId")
        if first_user:
            technician = f"Technician {first_user}"
    if not technician:
        technician = f"Technician {abs(hash(order_id)) % 50 + 1}"

    timeline: list[dict[str, Any]] = []
    if isinstance(order_date, datetime):
        timeline.append(
            {
                "type": "status",
                "title": "Work order created",
                "description": f"Status: {wo.get('status')}",
                "at": order_date,
            }
        )
    for op in operations:
        timeline.append(
            {
                "type": "operation",
                "title": op.get("description") or "Operation",
                "description": f"Operation {op.get('operationId', '')} - Status: {op.get('status', '')}",
                "at": op.get("plannedStart") or order_date,
            }
        )
    for c in confirmations:
        timeline.append(
            {
                "type": "confirmation",
                "title": "Confirmation recorded",
                "description": c.get("confirmationText") or "",
                "at": c.get("confirmedAt") or order_date,
            }
        )
    for ev in audit_events:
        timeline.append(
            {
                "type": "audit",
                "title": "Tool checklist updated",
                "description": f"{ev.get('toolName')} marked "
                f"{'checked' if ev.get('checked') else 'unchecked'}"
                f"{' by ' + str(ev.get('userId')) if ev.get('userId') else ''}",
                "at": ev.get("timestamp") or order_date,
            }
        )
    # Sort by timestamp where available
    timeline.sort(key=lambda e: e.get("at") or order_date or datetime.now(timezone.utc))

    work_order_detail = {
        "orderId": order_id,
        "status": wo.get("status"),
        "priority": wo.get("priority"),
        "equipmentId": equipment_id,
        "actualWork": wo.get("actualWork"),
        "orderDate": order_date,
        "daysToSolve": days_to_solve,
        "issueDescription": issue_description,
        "technician": technician,
        "operations": operations,
        "confirmations": confirmations,
        "timeline": timeline,
        "telemetry": ml_result.get("telemetry") or {},
    }

    return {
        "orderId": order_id,
        "workOrder": {
            "status": wo.get("status"),
            "priority": wo.get("priority"),
            "equipmentId": equipment_id,
            "actualWork": wo.get("actualWork"),
        },
        "workOrderDetail": work_order_detail,
        "ml_prediction": ml_result,
        "manuals": manuals,
        "historical_fixes": historical,
        "system_affected": system_affected,
    }


def run_agent_and_produce_briefing(context: dict[str, Any]) -> dict[str, Any]:
    """
    Call Google Gemini to produce Technician Mission Briefing JSON from context.
    If GEMINI_API_KEY is missing, returns a structured fallback from rules.
    """
    if not GEMINI_API_KEY:
        return _fallback_briefing(context)
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = f"""You are a senior technician dispatcher. Given the following context package, produce a Technician Mission Briefing in valid JSON with exactly these keys: root_cause_analysis (string), required_tools (list of tool names, e.g. Torque Wrench, Multimeter, 10mm Socket), estimated_repair_time (number, minutes), manual_reference_snippet (string, a short quote from the manual content provided), thought_process (string explaining in plain language which signals from the context you relied on, such as ML prediction, manuals, historical fixes, and work order timeline).

Context:
{json.dumps(context, indent=2, default=str)}

Respond with ONLY a single JSON object, no markdown code fences or explanation."""

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
            ),
        )
        text = (response.text or "").strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        brief = json.loads(text)
        return {
            "root_cause_analysis": brief.get("root_cause_analysis", ""),
            "required_tools": brief.get("required_tools", []),
            "estimated_repair_time": brief.get("estimated_repair_time", 60),
            "manual_reference_snippet": brief.get("manual_reference_snippet", ""),
            "thought_process": brief.get("thought_process", ""),
        }
    except Exception as e:
        return _fallback_briefing(context, error=str(e))


def _fallback_briefing(context: dict[str, Any], error: Optional[str] = None) -> dict[str, Any]:
    """Rule-based fallback when Gemini is unavailable."""
    ml = context.get("ml_prediction") or {}
    manuals = context.get("manuals") or []
    historical = context.get("historical_fixes") or []
    fault_code = ml.get("fault_code") or ""
    symptom = ml.get("symptom") or ""
    snippet = ""
    if manuals:
        snippet = (manuals[0].get("content") or "")[:400] + "..."
    tools_text = " ".join(
        [
            (m.get("content") or "") for m in manuals
        ]
        + [
            (h.get("resolution") or "") + " " + (h.get("diagnostic_steps") or "") + " " + (h.get("confirmationText") or "")
            for h in historical
        ]
    )
    extracted = extract_tools_from_text(tools_text)
    tools = extracted or ["Torque Wrench", "Multimeter", "Socket Set", "Screwdriver Set"]
    if "fuel" in (context.get("system_affected") or "").lower():
        tools.extend(["Fuel Pressure Gauge", "Line Wrenches"])
    if "cooling" in (context.get("system_affected") or "").lower():
        tools.extend(["Coolant Tester", "Hose Pliers"])
    return {
        "root_cause_analysis": f"ML prediction: {fault_code or 'No_Failure'}. {symptom}".strip() or "Inspection required.",
        "required_tools": tools[:8],
        "estimated_repair_time": 60,
        "manual_reference_snippet": snippet or "See manual for engine model.",
        "thought_process": "This briefing was generated from the ML prediction (failure label and confidence), diagnostics/engine manuals, historical fixes for similar systems, and the work order timeline (status, operations, confirmations, and tool checklist).",
        "fallback": True,
        "error": error,
    }


def run_chat(context: dict[str, Any], question: str) -> dict[str, Any]:
    """
    Lightweight chat-style Q&A over the same context package used for the mission briefing.
    Returns JSON with: answer (string), thought_process (string).
    """
    if not GEMINI_API_KEY:
        return _fallback_chat(context, question)
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = f"""You are an AI assistant helping a technician and dispatcher.
You can only answer questions about the following work order, equipment, ML prediction, manuals and historical fixes.

Context:
{json.dumps(context, indent=2, default=str)}

User question:
{question}

Respond with ONLY a single JSON object with exactly these keys:
- answer: string with a concise, helpful answer focused on this work order / equipment
- thought_process: string explaining at a high level which parts of the context you relied on (for example: ML prediction and confidence, manuals, historical fixes, work order fields, operations, confirmations, or timeline)."""

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
            ),
        )
        text = (response.text or "").strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        parsed = json.loads(text)
        return {
            "answer": parsed.get("answer", "I'm sorry, I couldn't generate an answer for that question."),
            "thought_process": parsed.get("thought_process", ""),
        }
    except Exception as e:
        return _fallback_chat(context, question, error=str(e))


def _fallback_chat(context: dict[str, Any], question: str, error: Optional[str] = None) -> dict[str, Any]:
    """
    Simple, non-LLM fallback answer based on context fields.
    Does NOT reveal any hidden chain-of-thought – only surfaces explicit signals from data.
    """
    work_order = context.get("workOrder") or {}
    ml = context.get("ml_prediction") or {}
    failure_label = ml.get("failure_label") or "No_Failure"
    equipment_id = work_order.get("equipmentId") or context.get("workOrderDetail", {}).get("equipmentId") or ""
    status = work_order.get("status") or context.get("workOrderDetail", {}).get("status") or ""

    answer_lines = []
    if equipment_id:
        answer_lines.append(f"The question appears to be about equipment {equipment_id}.")
    if status:
        answer_lines.append(f"The current work order status is {status}.")
    if failure_label and failure_label != "No_Failure":
        answer_lines.append(f"The ML model predicts failure type: {failure_label}.")
    if not answer_lines:
        answer_lines.append("I can answer questions about the work order, its equipment, predicted failure, and related manuals.")

    thought = "This answer is based only on visible fields from the work order (equipmentId, status) and the ML prediction label; no additional hidden reasoning was used."
    if error:
        thought += f" (The Gemini API was unavailable: {error})"

    return {
        "answer": " ".join(answer_lines),
        "thought_process": thought,
    }


def extract_tools_from_text(text: str) -> list[str]:
    """
    Lightweight tool extraction for unit tests and fallback behavior.
    Finds common tools and socket sizes like 10mm.
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
    ]
    found = []
    for needle, label in candidates:
        if needle in t and label not in found:
            found.append(label)
    for m in re.findall(r"\b(\d{1,2})\s*mm\b", t):
        s = f"{m}mm Socket"
        if s not in found:
            found.append(s)
    return found[:10]


def suggest_categories_from_description(issue_description: str) -> list[str]:
    """
    Use Gemini to suggest work order categories from an issue description (ML classification step).
    Returns a list of category labels, e.g. ["Engine", "Cooling", "Electrical"].
    """
    if not (issue_description or "").strip():
        return []
    if not GEMINI_API_KEY:
        return _fallback_suggest_categories(issue_description)
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = f"""Given this technician issue description for a work order, suggest 3 to 7 category labels that could classify this issue (e.g. Engine, Cooling, Electrical, Fuel System, Exhaust, Sensors, Hydraulics, Belts, Filters).
Issue description:
{issue_description.strip()}

Respond with ONLY a JSON array of strings, no other text. Example: ["Engine", "Cooling"]"""

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.2),
        )
        text = (response.text or "").strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        arr = json.loads(text)
        return [str(x).strip() for x in arr if x][:10]
    except Exception:
        return _fallback_suggest_categories(issue_description)


def _fallback_suggest_categories(issue_description: str) -> list[str]:
    """Rule-based category suggestions when Gemini is unavailable."""
    t = (issue_description or "").lower()
    out = []
    if any(x in t for x in ["engine", "overheat", "temperature"]):
        out.append("Engine")
    if any(x in t for x in ["coolant", "cooling", "radiator"]):
        out.append("Cooling")
    if any(x in t for x in ["electr", "sensor", "wire", "battery"]):
        out.append("Electrical")
    if any(x in t for x in ["fuel", "injector", "tank"]):
        out.append("Fuel System")
    if any(x in t for x in ["exhaust", "emission"]):
        out.append("Exhaust")
    if any(x in t for x in ["belt", "hose", "filter"]):
        out.extend(["Belts", "Filters"])
    return out if out else ["Engine", "General"]


def get_dispatch_brief(order_id: str) -> dict[str, Any]:
    """Full agentic flow: build context, run agent, return Mission Briefing."""
    context = build_context_package(order_id)
    if context.get("error"):
        return {"error": context["error"], "orderId": order_id}
    briefing = run_agent_and_produce_briefing(context)
    return {
        "orderId": order_id,
        "context_summary": {
            "equipmentId": context.get("workOrder", {}).get("equipmentId"),
            "failure_label": context.get("ml_prediction", {}).get("failure_label"),
            "confidence": context.get("ml_prediction", {}).get("confidence"),
        },
        "work_order": context.get("workOrder"),
        "work_order_detail": context.get("workOrderDetail"),
        "ml_prediction": context.get("ml_prediction"),
        "mission_briefing": briefing,
    }
