"""
Orchestrator Agent - Primary Agent for Multi-Agent Coordination

Responsible for:
- Receiving dispatch-brief requests
- Delegating tasks to sub-agents (Diagnostic, Prescription)
- Synthesizing sub-agent outputs into final Mission Briefing JSON
- Building complete work order detail context for the UI
"""

import json
from datetime import datetime, timezone
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from api.agents.base import _get_db, build_timeline
from api.agents.diagnostic_agent import DiagnosticAgent, run_diagnostic_analysis
from api.agents.prescription_agent import PrescriptionAgent, run_prescription
from api.agents.vision_agent import VisionAgent


ORCHESTRATOR_PROMPT = """You are the Orchestrator Agent for the Work Order AI Dispatch System.

Your role is to coordinate sub-agents and synthesize their outputs into a complete Technician Mission Briefing.

Sub-agents available:
1. Diagnostic Agent: Analyzes equipment telemetry and ML predictions
2. Prescription Agent: Searches manuals and historical fixes for repair guidance

Your workflow:
1. Receive a work order ID
2. Delegate diagnostic analysis to the Diagnostic Agent
3. Use diagnostic results to request prescription from Prescription Agent  
4. Synthesize all information into the final Mission Briefing

The Mission Briefing must include:
- root_cause_analysis: String explaining the likely cause based on ML and diagnostics
- required_tools: List of specific tools needed (e.g., ["Torque Wrench", "10mm Socket"])
- estimated_repair_time: Number in minutes
- manual_reference_snippet: Relevant excerpt from repair manual
- thought_process: Explanation of how you arrived at conclusions

Always ensure the final output maintains the exact JSON structure required by the SAP UI5 frontend."""


class OrchestratorAgent:
    """
    Primary Orchestrator Agent for multi-agent coordination.
    Delegates to Diagnostic and Prescription sub-agents.
    """
    
    def __init__(self, llm=None):
        """
        Initialize the Orchestrator Agent and sub-agents.
        
        Args:
            llm: LangChain LLM instance (uses Vertex AI if not provided)
        """
        if llm is None:
            from api.llm_client import get_llm_for_agents
            llm = get_llm_for_agents()
        
        self.llm = llm
        self.diagnostic_agent = DiagnosticAgent(llm)
        self.prescription_agent = PrescriptionAgent(llm)
        self.vision_agent = VisionAgent()
    
    def dispatch(self, order_id: str) -> dict[str, Any]:
        """
        Full orchestrated dispatch flow for a work order.
        
        Args:
            order_id: The work order ID to process
            
        Returns:
            Complete dispatch brief with context and mission briefing
        """
        # Step 1: Get work order from database via MCP
        from api.mcp_server import get_work_order, get_operations_for_order, get_confirmations_for_order, get_audit_trail
        
        work_order = get_work_order(order_id)
        if work_order.get("error"):
            return {"error": work_order["error"], "orderId": order_id}
        
        equipment_id = work_order.get("equipmentId", "")
        
        # Step 2: Delegate to Diagnostic Agent
        diagnostic_result = self.diagnostic_agent.analyze(equipment_id, order_id)
        
        # Extract diagnostic info
        ml_prediction = diagnostic_result.get("ml_prediction", {})
        fault_code = ml_prediction.get("fault_code", "")
        system_affected = diagnostic_result.get("system_affected", "Engine")
        telemetry = diagnostic_result.get("telemetry", {})
        engine_model = telemetry.get("engineModel", "X15")
        
        # Step 3: Delegate to Prescription Agent
        prescription_result = self.prescription_agent.prescribe(
            fault_code=fault_code,
            system_affected=system_affected,
            engine_model=engine_model,
            order_id=order_id,
        )

        # Step 3b: Check for existing image analyses (VisionAgent results)
        image_analyses = self.vision_agent.get_analyses_for_order(order_id)

        # Step 4: Build work order detail context
        operations = get_operations_for_order(order_id)
        confirmations = get_confirmations_for_order(order_id)
        audit_events = get_audit_trail(order_id)
        
        work_order_detail = self._build_work_order_detail(
            order_id=order_id,
            work_order=work_order,
            operations=operations,
            confirmations=confirmations,
            audit_events=audit_events,
            telemetry=telemetry,
        )
        
        # Step 5: Synthesize Mission Briefing (incorporating image analysis when available)
        mission_briefing = self._synthesize_briefing(
            diagnostic_result=diagnostic_result,
            prescription_result=prescription_result,
            work_order=work_order,
            image_analyses=image_analyses,
        )
        
        # Step 6: Return complete dispatch response
        return {
            "orderId": order_id,
            "context_summary": {
                "equipmentId": equipment_id,
                "failure_label": ml_prediction.get("failure_label"),
                "confidence": ml_prediction.get("confidence"),
            },
            "work_order": {
                "status": work_order.get("status"),
                "priority": work_order.get("priority"),
                "equipmentId": equipment_id,
                "actualWork": work_order.get("actualWork"),
            },
            "work_order_detail": work_order_detail,
            "ml_prediction": ml_prediction,
            "mission_briefing": mission_briefing,
            "image_analyses": image_analyses,
            "agent_trace": {
                "orchestrator": "OrchestratorAgent",
                "sub_agents_invoked": (
                    ["DiagnosticAgent", "PrescriptionAgent", "VisionAgent"]
                    if image_analyses
                    else ["DiagnosticAgent", "PrescriptionAgent"]
                ),
                "mcp_tools_used": [
                    "get_work_order",
                    "get_ml_prediction",
                    "query_manuals",
                    "get_historical_fixes",
                    "get_operations_for_order",
                    "get_confirmations_for_order",
                    "get_audit_trail",
                    "get_image_analyses",
                ],
                "vision_analyses_count": len(image_analyses),
            },
        }
    
    def _build_work_order_detail(
        self,
        order_id: str,
        work_order: dict,
        operations: list,
        confirmations: list,
        audit_events: list,
        telemetry: dict,
    ) -> dict[str, Any]:
        """Build the detailed work order context for UI."""
        order_date = work_order.get("orderDate")
        equipment_id = work_order.get("equipmentId", "")
        
        # Calculate days to solve
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
        
        # Get issue description
        issue_description = (work_order.get("issueDescription") or "").strip()
        if not issue_description and operations:
            issue_description = operations[0].get("description") or ""
        
        # Get technician
        technician = None
        if audit_events:
            first_user = audit_events[0].get("userId")
            if first_user:
                technician = f"Technician {first_user}"
        if not technician:
            technician = f"Technician {abs(hash(order_id)) % 50 + 1}"
        
        # Build timeline
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
            "equipmentId": equipment_id,
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
        self,
        diagnostic_result: dict,
        prescription_result: dict,
        work_order: dict,
        image_analyses: Optional[list] = None,
    ) -> dict[str, Any]:
        """
        Synthesize the final Mission Briefing from sub-agent results.
        Uses LLM for intelligent synthesis when available.
        """
        ml = diagnostic_result.get("ml_prediction", {})
        fault_code = ml.get("fault_code", "")
        failure_label = ml.get("failure_label", "No_Failure")
        confidence = ml.get("confidence", 0.0)
        symptom = diagnostic_result.get("symptom", "")
        system_affected = diagnostic_result.get("system_affected", "Engine")
        
        required_tools = prescription_result.get("required_tools", [])
        manual_snippet = prescription_result.get("manual_reference_snippet", "")
        repair_time = prescription_result.get("estimated_repair_time", 60)
        historical_context = prescription_result.get("historical_context", "")
        
        # Build root cause analysis
        root_cause_parts = []
        if fault_code and fault_code != "No_Failure":
            root_cause_parts.append(f"ML prediction indicates {fault_code} ({failure_label})")
        if confidence:
            root_cause_parts.append(f"with {confidence*100:.0f}% confidence")
        if symptom:
            root_cause_parts.append(f"- {symptom}")
        if system_affected:
            root_cause_parts.append(f"System affected: {system_affected}")
        
        root_cause = ". ".join(root_cause_parts) if root_cause_parts else "Inspection required - no specific failure predicted."

        # Incorporate VisionAgent findings if images were analyzed
        vision_summary = ""
        vision_severity = ""
        if image_analyses:
            latest = image_analyses[0]
            defects = latest.get("defects_found", [])
            components = latest.get("components_identified", [])
            vision_severity = latest.get("severity", "")
            vision_actions = latest.get("recommended_actions", [])
            damage_assessment = latest.get("damage_assessment", "")

            if damage_assessment:
                root_cause += f" Visual inspection ({len(image_analyses)} image set(s)): {damage_assessment[:200]}"
            if defects:
                root_cause += f" Defects observed: {', '.join(defects[:4])}."

            # Merge vision-recommended actions into required tools
            for action in vision_actions[:3]:
                if len(required_tools) < 10 and action not in required_tools:
                    required_tools.append(action)

            vision_summary = (
                f"VisionAgent analyzed {len(image_analyses)} image batch(es). "
                f"Components identified: {', '.join(components[:5]) if components else 'N/A'}. "
                f"Visual severity: {vision_severity}. "
                f"Defects found: {', '.join(defects[:4]) if defects else 'None detected'}."
            )

        # Build thought process
        thought_process = (
            f"This briefing was generated by the multi-agent system. "
            f"The Diagnostic Agent analyzed equipment telemetry and ML predictions "
            f"(failure label: {failure_label}, confidence: {confidence:.2f}). "
            f"The Prescription Agent searched manuals for fault code '{fault_code}' "
            f"and historical fixes for '{system_affected}' system issues. "
            f"Tools were extracted from repair procedures and past confirmations."
        )
        if historical_context:
            thought_process += f" Historical context: {historical_context[:150]}..."
        if vision_summary:
            thought_process += f" {vision_summary}"

        return {
            "root_cause_analysis": root_cause,
            "required_tools": required_tools,
            "estimated_repair_time": repair_time,
            "manual_reference_snippet": manual_snippet or "See engine service manual for detailed procedures.",
            "thought_process": thought_process,
            "vision_severity": vision_severity or None,
            "image_analyses_count": len(image_analyses) if image_analyses else 0,
        }
    
    def chat(self, order_id: str, question: str, context: Optional[dict] = None) -> dict[str, Any]:
        """
        Handle chat queries about a work order with comprehensive historical context.
        
        Args:
            order_id: The work order ID
            question: User's question
            context: Optional pre-built context
            
        Returns:
            Chat response with answer and thought process
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
        
        # Build comprehensive context
        if context is None:
            work_order = get_work_order(order_id)
            equipment_id = work_order.get("equipmentId", "")
            diagnostic_result = self.diagnostic_agent.analyze(equipment_id, order_id)
            context = {
                "work_order": work_order,
                "ml_prediction": diagnostic_result.get("ml_prediction", {}),
            }
        else:
            work_order = context.get("work_order", {})
            equipment_id = work_order.get("equipmentId", "")
        
        question_lower = question.lower()
        
        # Gather additional context based on question type
        additional_context = {}
        tools_used = []
        
        # Check for historical/frequency questions
        history_keywords = ["how many times", "occurred before", "happened before", "previous", "historical", "history", "past", "frequent", "often", "pattern", "recurring", "repeat"]
        if any(kw in question_lower for kw in history_keywords):
            tools_used.append("Equipment Maintenance History")
            equipment_history = get_equipment_maintenance_history(equipment_id)
            additional_context["equipment_history"] = equipment_history
            
            # Also get issue count for this equipment
            tools_used.append("Issue Count for Equipment")
            issue_count = count_issues_for_equipment(equipment_id)
            additional_context["issue_statistics"] = issue_count
            
            # Find similar issues across all equipment
            issue_desc = work_order.get("issueDescription", "")
            if issue_desc:
                tools_used.append("Similar Issues Search")
                # Extract key words from issue description
                keywords = " ".join(word for word in issue_desc.split() if len(word) > 3)[:50]
                similar_count = count_similar_issues(keywords)
                additional_context["similar_issues_count"] = similar_count
        
        # Check for report/summary questions
        report_keywords = ["report", "summary", "overview", "status", "all work orders", "maintenance record"]
        if any(kw in question_lower for kw in report_keywords):
            tools_used.append("Equipment Work Orders")
            equipment_work_orders = get_work_orders_for_equipment(equipment_id, limit=20)
            additional_context["equipment_work_orders"] = equipment_work_orders
            
            tools_used.append("Confirmations")
            confirmations = get_confirmations_for_order(order_id)
            additional_context["confirmations"] = confirmations
        
        # Check for similar issue questions
        similar_keywords = ["similar", "same issue", "other equipment", "other machines", "related problems"]
        if any(kw in question_lower for kw in similar_keywords):
            tools_used.append("Similar Issues Search")
            issue_desc = work_order.get("issueDescription", "")
            if issue_desc:
                keywords = " ".join(word for word in issue_desc.split() if len(word) > 3)[:50]
                similar_issues = find_similar_issues(keywords, limit=15)
                additional_context["similar_issues"] = similar_issues
        
        # Check for resolution/fix questions
        fix_keywords = ["fix", "resolve", "solution", "repair", "fixed before", "how to repair"]
        if any(kw in question_lower for kw in fix_keywords):
            tools_used.append("Historical Fixes")
            system = work_order.get("issueDescription", "Engine").split()[0] if work_order.get("issueDescription") else "Engine"
            historical_fixes = get_historical_fixes(system, limit=10)
            additional_context["historical_fixes"] = historical_fixes
        
        # If no specific context gathered, get general equipment history
        if not additional_context:
            tools_used.append("Equipment Maintenance History (default)")
            equipment_history = get_equipment_maintenance_history(equipment_id)
            additional_context["equipment_history"] = equipment_history
        
        # Merge contexts
        full_context = {**context, **additional_context}
        
        # Use LLM for chat with rich context
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
            response = self.llm.invoke(prompt)
            raw_text = response.content.strip()
        except Exception as e:
            import logging
            logging.error(f"[chat] LLM call failed: {e}")
            fallback_answer = self._build_fallback_answer(question, full_context, tools_used)
            return {
                "answer": fallback_answer,
                "thought_process": f"LLM call failed. Tools used: {', '.join(tools_used)}. Error: {str(e)}",
                "tools_used": tools_used,
            }

        # Try to extract JSON from the response
        text = raw_text
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        try:
            result = json.loads(text)
            result["tools_used"] = tools_used
            return result
        except Exception:
            # Model responded with plain text instead of JSON — use it directly
            return {
                "answer": raw_text,
                "thought_process": f"Tools used: {', '.join(tools_used)}",
                "tools_used": tools_used,
            }
    
    def _build_fallback_answer(self, question: str, context: dict, tools_used: list) -> str:
        """Build a data-driven fallback answer when LLM fails."""
        question_lower = question.lower()
        
        # For "how many times" questions
        if "how many times" in question_lower or "occurred before" in question_lower:
            stats = context.get("issue_statistics", {})
            history = context.get("equipment_history", {})
            total = stats.get("total_work_orders", 0) or history.get("total_work_orders", 0)
            if total:
                issues = stats.get("issues_list", []) or history.get("work_orders", [])
                issue_summary = ", ".join([f"{wo.get('orderId')}" for wo in issues[:5]])
                return f"This equipment has had {total} work orders total. Recent work orders include: {issue_summary}. This includes both similar and different types of issues."
            return "I could not find historical data for this equipment."
        
        # For report questions
        if "report" in question_lower or "summary" in question_lower:
            history = context.get("equipment_history", {})
            total = history.get("total_work_orders", 0)
            completed = history.get("statuses", {}).get("completed", 0)
            if total:
                return f"Equipment maintenance report: {total} total work orders, {completed} completed. Common issues: {history.get('common_issues', [])[:3]}"
            return "No historical data found for generating a report."
        
        return f"Based on the data gathered (using {', '.join(tools_used)}), I have information about this work order and equipment but couldn't format a complete answer. Please try rephrasing your question."


# ============================================================================
# Public API Functions
# ============================================================================

def get_dispatch_brief(order_id: str) -> dict[str, Any]:
    """
    Main entry point for dispatch briefing.
    Uses the Orchestrator Agent to coordinate sub-agents.
    
    Args:
        order_id: The work order ID
        
    Returns:
        Complete dispatch brief with mission briefing
    """
    orchestrator = OrchestratorAgent()
    return orchestrator.dispatch(order_id)


def run_chat(context: dict[str, Any], question: str) -> dict[str, Any]:
    """
    Handle chat queries using the orchestrator.
    
    Args:
        context: Work order context
        question: User's question
        
    Returns:
        Chat response
    """
    order_id = context.get("orderId") or context.get("work_order", {}).get("orderId", "unknown")
    orchestrator = OrchestratorAgent()
    return orchestrator.chat(order_id, question, context)


def suggest_categories_from_description(issue_description: str) -> list[str]:
    """
    Use LLM to suggest work order categories.
    
    Args:
        issue_description: The issue text
        
    Returns:
        List of suggested category labels
    """
    if not (issue_description or "").strip():
        return []
    
    try:
        from api.llm_client import generate_content
        
        prompt = f"""Given this technician issue description for a work order, suggest 3 to 7 category labels that could classify this issue (e.g. Engine, Cooling, Electrical, Fuel System, Exhaust, Sensors, Hydraulics, Belts, Filters).
Issue description:
{issue_description.strip()}

Respond with ONLY a JSON array of strings, no other text. Example: ["Engine", "Cooling"]"""
        
        response = generate_content(prompt, temperature=0.2)
        text = response.strip()
        
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        
        arr = json.loads(text)
        return [str(x).strip() for x in arr if x][:10]
    except Exception:
        return _fallback_suggest_categories(issue_description)


def _fallback_suggest_categories(issue_description: str) -> list[str]:
    """Rule-based category suggestions."""
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
