"""
LangGraph Multi-Agent Orchestration

Graph topology (dispatch):

  START
    │
    ▼
  load_work_order
    │
    ▼
  diagnostic  ──────────────────────────────┐
    │                                        │
    ├──► prescription (manual + tool list)   │  parallel
    ├──► vision       (stored image analyses)│  branches
    └──► load_supporting_data (ops/audit)    │
                                             │
         (all three complete, then fan-in)   │
                                             ▼
                                         synthesize
                                             │
                                            END

Graph topology (chat):

  START → gather_context → llm_answer → END
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional, TypedDict

from langgraph.graph import StateGraph, START, END

logger = logging.getLogger(__name__)


# ── State schemas ──────────────────────────────────────────────────────────────

class DispatchState(TypedDict, total=False):
    order_id: str
    work_order: dict
    equipment_id: str
    diagnostic_result: dict
    prescription_result: dict
    image_analyses: list
    operations: list
    confirmations: list
    audit_events: list
    work_order_detail: dict
    mission_briefing: dict
    llm_explanation: str
    error: Optional[str]


class ChatState(TypedDict, total=False):
    order_id: str
    question: str
    work_order: dict
    equipment_id: str
    full_context: dict
    tools_used: list
    answer: str
    thought_process: str


# ── Dispatch nodes ─────────────────────────────────────────────────────────────

def load_work_order_node(state: DispatchState) -> dict:
    """Fetch the work order from MongoDB."""
    from api.mcp_server import get_work_order
    work_order = get_work_order(state["order_id"])
    if work_order.get("error"):
        return {"error": work_order["error"], "work_order": {}, "equipment_id": ""}
    return {
        "work_order": work_order,
        "equipment_id": work_order.get("equipmentId", ""),
    }


def diagnostic_node(state: DispatchState) -> dict:
    """
    DiagnosticAgent: run ML classifier on equipment telemetry,
    look up the fault code, determine the affected system.
    """
    if state.get("error"):
        return {}
    from api.agents.diagnostic_agent import DiagnosticAgent
    agent = DiagnosticAgent()
    result = agent.analyze(state["equipment_id"], state["order_id"])
    logger.info(f"[diagnostic_node] fault={result.get('ml_prediction', {}).get('fault_code')} "
                f"system={result.get('system_affected')}")
    return {"diagnostic_result": result}


def prescription_node(state: DispatchState) -> dict:
    """
    PrescriptionAgent: search engine manuals and historical fixes
    for the fault code, build tool list and estimate repair time.
    Runs in parallel with vision_node and load_supporting_data_node.
    """
    if state.get("error"):
        return {}
    from api.agents.prescription_agent import PrescriptionAgent
    diag = state.get("diagnostic_result", {})
    ml = diag.get("ml_prediction", {})
    agent = PrescriptionAgent()
    result = agent.prescribe(
        fault_code=ml.get("fault_code", ""),
        system_affected=diag.get("system_affected", "Engine"),
        engine_model=diag.get("telemetry", {}).get("engineModel", "X15"),
        order_id=state["order_id"],
    )
    logger.info(f"[prescription_node] tools={result.get('required_tools', [])[:3]}")
    return {"prescription_result": result}


def vision_node(state: DispatchState) -> dict:
    """
    VisionAgent: retrieve any previously stored image analyses for this work order.
    Runs in parallel with prescription_node and load_supporting_data_node.
    """
    if state.get("error"):
        return {}
    from api.agents.vision_agent import VisionAgent
    agent = VisionAgent()
    analyses = agent.get_analyses_for_order(state["order_id"])
    logger.info(f"[vision_node] image_analyses={len(analyses)}")
    return {"image_analyses": analyses}


def load_supporting_data_node(state: DispatchState) -> dict:
    """
    Fetch operations, confirmations, and audit trail for the work order.
    Runs in parallel with prescription_node and vision_node.
    """
    if state.get("error"):
        return {}
    from api.mcp_server import (
        get_operations_for_order,
        get_confirmations_for_order,
        get_audit_trail,
    )
    return {
        "operations": get_operations_for_order(state["order_id"]),
        "confirmations": get_confirmations_for_order(state["order_id"]),
        "audit_events": get_audit_trail(state["order_id"]),
    }


def synthesize_node(state: DispatchState) -> dict:
    """
    Assemble the Mission Briefing from all sub-agent results.
    Runs after prescription_node, vision_node, and load_supporting_data_node all complete.
    """
    if state.get("error"):
        return {}

    work_order = state.get("work_order", {})
    diagnostic_result = state.get("diagnostic_result", {})
    prescription_result = state.get("prescription_result", {})
    image_analyses = state.get("image_analyses", [])

    work_order_detail = _build_work_order_detail(
        order_id=state["order_id"],
        work_order=work_order,
        operations=state.get("operations", []),
        confirmations=state.get("confirmations", []),
        audit_events=state.get("audit_events", []),
        telemetry=diagnostic_result.get("telemetry", {}),
    )

    mission_briefing = _synthesize_briefing(
        diagnostic_result=diagnostic_result,
        prescription_result=prescription_result,
        work_order=work_order,
    )

    if image_analyses:
        mission_briefing["vision_analyses"] = image_analyses

    logger.info(f"[synthesize_node] briefing assembled for {state['order_id']}")
    return {
        "work_order_detail": work_order_detail,
        "mission_briefing": mission_briefing,
    }


def explain_node(state: DispatchState) -> dict:
    """
    Ask llava to write a plain-English explanation of what the agents found.
    Runs after synthesize so it has the full picture.
    """
    if state.get("error"):
        return {"llm_explanation": ""}

    diag = state.get("diagnostic_result", {})
    ml = diag.get("ml_prediction", {})
    presc = state.get("prescription_result", {})
    wo = state.get("work_order", {})
    image_analyses = state.get("image_analyses", [])

    failure_label = ml.get("failure_label", "No_Failure")
    confidence = ml.get("confidence", 0.0)
    fault_code = ml.get("fault_code", "none")
    system_affected = diag.get("system_affected", "unknown")
    tools = presc.get("required_tools", [])
    repair_time = presc.get("estimated_repair_time", 60)
    issue = wo.get("issueDescription", "not specified")
    equipment = state.get("equipment_id", "unknown")

    vision_summary = ""
    if image_analyses:
        v = image_analyses[0]
        vision_summary = (
            f"\nImage analysis also ran: severity={v.get('severity')}, "
            f"components={v.get('components_identified', [])}, "
            f"defects={v.get('defects_found', [])}."
        )

    prompt = f"""You are explaining what an AI diagnostic system did when it analysed a maintenance work order. Write in plain, conversational English — no bullet points, no JSON, no headers.

Work order details:
- Equipment: {equipment}
- Reported issue: {issue}

What the agents found:
- The ML model predicted: {failure_label} (fault code: {fault_code}) with {confidence*100:.0f}% confidence
- System affected: {system_affected}
- Recommended tools: {', '.join(tools) if tools else 'none identified'}
- Estimated repair time: {repair_time} minutes{vision_summary}

Write 2–3 short paragraphs explaining: (1) what the diagnostic agent did and found, (2) what the prescription agent looked up and recommended, and (3) what a technician should take away from this. Be specific — use the actual values above. Write as if talking directly to the technician."""

    try:
        from api.llm_client import get_llm_for_agents
        llm = get_llm_for_agents()
        response = llm.invoke(prompt)
        explanation = response.content.strip()
        logger.info(f"[explain_node] generated explanation ({len(explanation)} chars)")
        return {"llm_explanation": explanation}
    except Exception as e:
        logger.error(f"[explain_node] LLM call failed: {e}")
        return {"llm_explanation": ""}


# ── Chat nodes ─────────────────────────────────────────────────────────────────

def gather_context_node(state: ChatState) -> dict:
    """
    Fetch relevant data from MongoDB based on question keywords.
    """
    from api.mcp_server import (
        get_work_order,
        get_work_orders_for_equipment,
        count_issues_for_equipment,
        find_similar_issues,
        get_equipment_maintenance_history,
        count_similar_issues,
        get_historical_fixes,
        get_confirmations_for_order,
    )

    order_id = state["order_id"]
    question = state["question"]
    question_lower = question.lower()

    work_order = state.get("work_order") or get_work_order(order_id)
    equipment_id = work_order.get("equipmentId", "")

    context: dict = {"work_order": work_order}
    tools_used: list = []

    history_kw = ["how many times", "occurred before", "happened before", "previous",
                  "historical", "history", "past", "frequent", "often", "pattern",
                  "recurring", "repeat"]
    if any(kw in question_lower for kw in history_kw):
        tools_used.append("Equipment Maintenance History")
        context["equipment_history"] = get_equipment_maintenance_history(equipment_id)
        tools_used.append("Issue Count for Equipment")
        context["issue_statistics"] = count_issues_for_equipment(equipment_id)
        issue_desc = work_order.get("issueDescription", "")
        if issue_desc:
            keywords = " ".join(w for w in issue_desc.split() if len(w) > 3)[:50]
            tools_used.append("Similar Issues Search")
            context["similar_issues_count"] = count_similar_issues(keywords)

    report_kw = ["report", "summary", "overview", "status", "all work orders", "maintenance record"]
    if any(kw in question_lower for kw in report_kw):
        tools_used.append("Equipment Work Orders")
        context["equipment_work_orders"] = get_work_orders_for_equipment(equipment_id, limit=20)
        tools_used.append("Confirmations")
        context["confirmations"] = get_confirmations_for_order(order_id)

    similar_kw = ["similar", "same issue", "other equipment", "other machines", "related problems"]
    if any(kw in question_lower for kw in similar_kw):
        issue_desc = work_order.get("issueDescription", "")
        if issue_desc:
            keywords = " ".join(w for w in issue_desc.split() if len(w) > 3)[:50]
            tools_used.append("Similar Issues Search")
            context["similar_issues"] = find_similar_issues(keywords, limit=15)

    fix_kw = ["fix", "resolve", "solution", "repair", "fixed before", "how to repair"]
    if any(kw in question_lower for kw in fix_kw):
        system = (work_order.get("issueDescription") or "Engine").split()[0]
        tools_used.append("Historical Fixes")
        context["historical_fixes"] = get_historical_fixes(system, limit=10)

    if not tools_used:
        tools_used.append("Equipment Maintenance History (default)")
        context["equipment_history"] = get_equipment_maintenance_history(equipment_id)

    logger.info(f"[gather_context_node] tools={tools_used}")
    return {
        "work_order": work_order,
        "equipment_id": equipment_id,
        "full_context": context,
        "tools_used": tools_used,
    }


def llm_answer_node(state: ChatState) -> dict:
    """
    Call llava with the gathered context to answer the technician's question.
    """
    from api.llm_client import get_llm_for_agents

    order_id = state["order_id"]
    equipment_id = state.get("equipment_id", "")
    question = state["question"]
    full_context = state.get("full_context", {})
    tools_used = state.get("tools_used", [])

    prompt = f"""You are an AI assistant helping a maintenance technician answer questions about work orders and equipment.

WORK ORDER: {order_id}
EQUIPMENT: {equipment_id}

DATA AVAILABLE:
{json.dumps(full_context, indent=2, default=str)[:15000]}

QUESTION: {question}

Answer the question thoroughly using the data above. Be specific — include numbers, work order IDs, dates, and status details from the data. If the data doesn't contain an answer, say so clearly.

Respond ONLY with a JSON object in this exact format (no markdown, no extra text):
{{"answer": "your detailed answer here", "thought_process": "brief note on what data you used"}}"""

    raw_text = None
    try:
        llm = get_llm_for_agents()
        response = llm.invoke(prompt)
        raw_text = response.content.strip()
    except Exception as e:
        logger.error(f"[llm_answer_node] LLM call failed: {e}")
        return {
            "answer": f"LLM call failed: {e}",
            "thought_process": f"Tools used: {', '.join(tools_used)}",
        }

    text = raw_text
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        result = json.loads(text)
        return {
            "answer": result.get("answer", raw_text),
            "thought_process": result.get("thought_process", ""),
        }
    except Exception:
        return {
            "answer": raw_text,
            "thought_process": f"Tools used: {', '.join(tools_used)}",
        }


# ── Graph builders ─────────────────────────────────────────────────────────────

def build_dispatch_graph():
    """
    Compile the dispatch graph.

    load_work_order → diagnostic → [prescription, vision, load_supporting_data] → synthesize
                                    └── these three run in parallel ──────────────┘
    """
    g = StateGraph(DispatchState)

    g.add_node("load_work_order", load_work_order_node)
    g.add_node("diagnostic", diagnostic_node)
    g.add_node("prescription", prescription_node)
    g.add_node("vision", vision_node)
    g.add_node("load_supporting_data", load_supporting_data_node)
    g.add_node("synthesize", synthesize_node)
    g.add_node("explain", explain_node)

    g.add_edge(START, "load_work_order")
    g.add_edge("load_work_order", "diagnostic")

    # Fan-out: diagnostic → three parallel nodes
    g.add_edge("diagnostic", "prescription")
    g.add_edge("diagnostic", "vision")
    g.add_edge("diagnostic", "load_supporting_data")

    # Fan-in: all three → synthesize (LangGraph waits for all incoming edges)
    g.add_edge("prescription", "synthesize")
    g.add_edge("vision", "synthesize")
    g.add_edge("load_supporting_data", "synthesize")

    # explain runs after synthesize has the full picture
    g.add_edge("synthesize", "explain")
    g.add_edge("explain", END)

    return g.compile()


def build_chat_graph():
    """
    Compile the chat graph.

    gather_context → llm_answer
    """
    g = StateGraph(ChatState)

    g.add_node("gather_context", gather_context_node)
    g.add_node("llm_answer", llm_answer_node)

    g.add_edge(START, "gather_context")
    g.add_edge("gather_context", "llm_answer")
    g.add_edge("llm_answer", END)

    return g.compile()


# Compiled graphs (lazy singleton)
_dispatch_graph = None
_chat_graph = None


def get_dispatch_graph():
    global _dispatch_graph
    if _dispatch_graph is None:
        _dispatch_graph = build_dispatch_graph()
    return _dispatch_graph


def get_chat_graph():
    global _chat_graph
    if _chat_graph is None:
        _chat_graph = build_chat_graph()
    return _chat_graph


# ── Helper functions (shared between nodes and public API) ─────────────────────

def _build_work_order_detail(
    order_id: str,
    work_order: dict,
    operations: list,
    confirmations: list,
    audit_events: list,
    telemetry: dict,
) -> dict:
    from api.agents.base import build_timeline

    order_date = work_order.get("orderDate")

    last_conf_dt: Optional[datetime] = None
    for c in confirmations:
        dt = c.get("confirmedAt")
        if isinstance(dt, datetime) and (last_conf_dt is None or dt > last_conf_dt):
            last_conf_dt = dt
    end_dt = last_conf_dt or datetime.now(timezone.utc)

    days_to_solve: Optional[int] = None
    if isinstance(order_date, datetime):
        try:
            od = order_date.replace(tzinfo=timezone.utc) if order_date.tzinfo is None else order_date
            ed = end_dt.replace(tzinfo=timezone.utc) if end_dt.tzinfo is None else end_dt
            days_to_solve = (ed - od).days
        except Exception:
            pass

    issue_description = (work_order.get("issueDescription") or "").strip()
    if not issue_description and operations:
        issue_description = operations[0].get("description") or ""

    technician = None
    if audit_events:
        first_user = audit_events[0].get("userId")
        if first_user:
            technician = f"Technician {first_user}"
    if not technician:
        technician = f"Technician {abs(hash(order_id)) % 50 + 1}"

    timeline = build_timeline(
        order_date,
        operations,
        confirmations,
        audit_events,
        work_order.get("status", ""),
    )

    return {
        "orderId": order_id,
        "status": work_order.get("status"),
        "priority": work_order.get("priority"),
        "equipmentId": work_order.get("equipmentId", ""),
        "actualWork": work_order.get("actualWork"),
        "orderDate": order_date,
        "daysToSolve": days_to_solve,
        "issueDescription": issue_description,
        "technician": technician,
        "operations": operations,
        "confirmations": confirmations,
        "timeline": timeline,
        "telemetry": telemetry,
    }


def _synthesize_briefing(
    diagnostic_result: dict,
    prescription_result: dict,
    work_order: dict,
) -> dict:
    ml = diagnostic_result.get("ml_prediction", {})
    fault_code = ml.get("fault_code", "")
    failure_label = ml.get("failure_label", "No_Failure")
    confidence = ml.get("confidence", 0.0)
    symptom = diagnostic_result.get("symptom", "")
    system_affected = diagnostic_result.get("system_affected", "Engine")
    telemetry = diagnostic_result.get("telemetry", {})

    required_tools = prescription_result.get("required_tools", [])
    manual_snippet = prescription_result.get("manual_reference_snippet", "")
    repair_time = prescription_result.get("estimated_repair_time", 60)
    historical_context = prescription_result.get("historical_context", "")

    # Build detailed root cause analysis
    issue_desc = work_order.get("issueDescription", "equipment malfunction")
    equipment_id = work_order.get("equipmentId", "")
    
    root_cause_parts = []
    
    # Opening context
    root_cause_parts.append(f"**Issue Overview:** Equipment {equipment_id} reported '{issue_desc}'.")
    
    # ML prediction findings
    if fault_code and fault_code != "No_Failure":
        confidence_level = "high" if confidence >= 0.8 else "moderate" if confidence >= 0.6 else "low"
        root_cause_parts.append(
            f"\n\n**AI Diagnostic Finding:** Our machine learning model predicts fault code **{fault_code}** "
            f"(classification: {failure_label}) with **{confidence_level} confidence ({confidence * 100:.0f}%)**."
        )
    else:
        root_cause_parts.append(
            "\n\n**AI Diagnostic Finding:** No specific failure pattern detected by ML classifier. "
            "Manual inspection recommended."
        )
    
    # Symptom explanation
    if symptom:
        root_cause_parts.append(f"\n\n**Symptom Analysis:** {symptom}")
    
    # System affected
    if system_affected:
        root_cause_parts.append(
            f"\n\n**Affected System:** The **{system_affected}** system requires attention. "
            f"Focus diagnostic efforts on {system_affected.lower()}-related components."
        )
    
    # Telemetry insights
    if telemetry:
        telemetry_insights = []
        if telemetry.get("Process_Temperature"):
            temp = telemetry["Process_Temperature"]
            status = "⚠️ elevated" if temp > 320 else "normal"
            telemetry_insights.append(f"Process Temperature: {temp}°K ({status})")
        if telemetry.get("Torque"):
            torque = telemetry["Torque"]
            status = "⚠️ high" if torque > 50 else "normal"
            telemetry_insights.append(f"Torque: {torque} Nm ({status})")
        if telemetry.get("Rotational_Speed"):
            rpm = telemetry["Rotational_Speed"]
            telemetry_insights.append(f"Rotational Speed: {rpm} RPM")
        if telemetry.get("Tool_Wear") is not None:
            wear = telemetry["Tool_Wear"]
            status = "⚠️ significant wear" if wear and wear > 150 else "acceptable"
            telemetry_insights.append(f"Tool Wear: {wear or 'N/A'} min ({status})")
        
        if telemetry_insights:
            root_cause_parts.append("\n\n**Recent Telemetry Readings:**\n• " + "\n• ".join(telemetry_insights))
    
    # Historical context
    if historical_context:
        root_cause_parts.append(
            f"\n\n**Historical Patterns:** Similar issues on this equipment have been resolved through: {historical_context[:200]}..."
        )
    
    # Recommendation
    if required_tools:
        top_tools = required_tools[:4]
        root_cause_parts.append(
            f"\n\n**Recommended Approach:** Begin with visual inspection of the {system_affected.lower()} system. "
            f"Key tools needed: {', '.join(top_tools)}. Estimated repair time: ~{repair_time} minutes."
        )

    root_cause = "".join(root_cause_parts)

    # Build detailed thought process showing agent workflow
    thought_process_parts = [
        "**🔄 Agent Workflow Executed:**",
        "",
        "**Step 1 - Data Retrieval:**",
        f"• Loaded work order {work_order.get('orderId', 'N/A')} from MongoDB",
        f"• Retrieved equipment telemetry for {equipment_id}",
        "",
        "**Step 2 - Diagnostic Analysis (DiagnosticAgent):**",
        f"• Ran ML failure classifier on telemetry data",
        f"• Prediction: {failure_label} (confidence: {confidence:.0%})",
        f"• Mapped fault code {fault_code} to system: {system_affected}",
        "",
        "**Step 3 - Prescription & Research (PrescriptionAgent):**",
        f"• Searched Cummins repair manuals for '{fault_code}' procedures",
        f"• Queried historical fixes for {system_affected} issues",
        f"• Compiled tool checklist: {len(required_tools)} items",
        f"• Estimated repair duration: {repair_time} minutes",
        "",
        "**Step 4 - Visual Analysis (VisionAgent):**",
        "• Checked for uploaded inspection images",
        "• Ready to analyze equipment photos via Ollama llava model",
        "",
        "**Step 5 - Synthesis:**",
        "• Combined all agent outputs into Mission Briefing",
        "• Generated root cause analysis and recommendations",
    ]
    
    if historical_context:
        thought_process_parts.append(f"\n**📊 Historical Data Used:** {historical_context[:100]}...")

    thought_process = "\n".join(thought_process_parts)

    return {
        "root_cause_analysis": root_cause,
        "required_tools": required_tools,
        "estimated_repair_time": repair_time,
        "manual_reference_snippet": manual_snippet or "Refer to the official Cummins engine service manual for detailed step-by-step repair procedures.",
        "thought_process": thought_process,
    }
