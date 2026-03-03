"""
Agentic AI Dispatcher: builds context from tools and produces Technician Mission Briefing via OpenAI.
"""

import json
import os
import re
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

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")

MISSION_BRIEFING_SCHEMA = {
    "root_cause_analysis": "string",
    "required_tools": "list of strings, e.g. [Torque Wrench, Multimeter, 10mm Socket]",
    "estimated_repair_time": "number (minutes)",
    "manual_reference_snippet": "string",
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
    return {
        "orderId": order_id,
        "workOrder": {
            "status": wo.get("status"),
            "priority": wo.get("priority"),
            "equipmentId": equipment_id,
            "actualWork": wo.get("actualWork"),
        },
        "ml_prediction": ml_result,
        "manuals": manuals,
        "historical_fixes": historical,
        "system_affected": system_affected,
    }


def run_agent_and_produce_briefing(context: dict[str, Any]) -> dict[str, Any]:
    """
    Call OpenAI to produce Technician Mission Briefing JSON from context.
    If OPENAI_API_KEY is missing, returns a structured fallback from rules.
    """
    if not OPENAI_API_KEY:
        return _fallback_briefing(context)
    try:
        import openai
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        prompt = f"""You are a senior technician dispatcher. Given the following context package, produce a Technician Mission Briefing in valid JSON with exactly these keys: root_cause_analysis (string), required_tools (list of tool names, e.g. Torque Wrench, Multimeter, 10mm Socket), estimated_repair_time (number, minutes), manual_reference_snippet (string, a short quote from the manual content provided).

Context:
{json.dumps(context, indent=2, default=str)}

Respond with ONLY a single JSON object, no markdown or explanation."""

        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        text = resp.choices[0].message.content.strip()
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
        }
    except Exception as e:
        return _fallback_briefing(context, error=str(e))


def _fallback_briefing(context: dict[str, Any], error: Optional[str] = None) -> dict[str, Any]:
    """Rule-based fallback when OpenAI is unavailable."""
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
        "fallback": True,
        "error": error,
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
        "mission_briefing": briefing,
    }
