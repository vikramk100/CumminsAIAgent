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
        
        # Step 5: Synthesize Mission Briefing
        mission_briefing = self._synthesize_briefing(
            diagnostic_result=diagnostic_result,
            prescription_result=prescription_result,
            work_order=work_order,
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
            "agent_trace": {
                "orchestrator": "OrchestratorAgent",
                "sub_agents_invoked": ["DiagnosticAgent", "PrescriptionAgent"],
                "mcp_tools_used": [
                    "get_work_order",
                    "get_ml_prediction",
                    "query_manuals",
                    "get_historical_fixes",
                    "get_operations_for_order",
                    "get_confirmations_for_order",
                    "get_audit_trail",
                ],
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
        
        return {
            "root_cause_analysis": root_cause,
            "required_tools": required_tools,
            "estimated_repair_time": repair_time,
            "manual_reference_snippet": manual_snippet or "See engine service manual for detailed procedures.",
            "thought_process": thought_process,
        }
    
    def chat(self, order_id: str, question: str, context: Optional[dict] = None) -> dict[str, Any]:
        """
        Handle chat queries about a work order.
        
        Args:
            order_id: The work order ID
            question: User's question
            context: Optional pre-built context
            
        Returns:
            Chat response with answer and thought process
        """
        if context is None:
            # Build minimal context
            from api.mcp_server import get_work_order
            work_order = get_work_order(order_id)
            equipment_id = work_order.get("equipmentId", "")
            diagnostic_result = self.diagnostic_agent.analyze(equipment_id, order_id)
            context = {
                "work_order": work_order,
                "ml_prediction": diagnostic_result.get("ml_prediction", {}),
            }
        
        # Use LLM for chat
        prompt = f"""You are an AI assistant helping a technician with work order {order_id}.

Context:
{json.dumps(context, indent=2, default=str)}

Question: {question}

Provide a helpful, concise answer focused on this work order and equipment.
Return JSON with: {{"answer": "...", "thought_process": "..."}}"""
        
        try:
            response = self.llm.invoke(prompt)
            text = response.content.strip()
            
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            return json.loads(text)
        except Exception as e:
            return {
                "answer": f"I can help with work order {order_id}. Please ask about the equipment, predicted failures, or repair procedures.",
                "thought_process": f"Fallback response - LLM error: {str(e)}",
            }


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
