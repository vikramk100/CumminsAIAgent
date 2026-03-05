"""
Prescription & Inventory Agent (Sub-agent 2)

Responsible for:
- Searching engine manuals for repair procedures
- Finding historical fixes for similar issues
- Building the "Smart Tool-Kit List" based on repair requirements
- Estimating repair time based on historical data
"""

import json
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from api.agents.base import (
    PRESCRIPTION_TOOLS,
    mcp_query_manuals,
    mcp_get_historical_fixes,
    mcp_get_operations,
    mcp_get_confirmations,
    extract_tools_from_text,
)


PRESCRIPTION_AGENT_PROMPT = """You are a Prescription & Inventory Agent for industrial equipment maintenance.

Your responsibilities:
1. Search engine manuals for repair procedures
2. Find historical fixes from past repairs
3. Build a comprehensive "Smart Tool-Kit List" - the exact tools needed for the repair
4. Estimate repair time based on historical data and operation complexity

When building the tool kit:
- Include specific socket sizes mentioned (e.g., "10mm Socket")
- Include diagnostic tools (Multimeter, Scan Tool)
- Include specialized tools for the system (Torque Wrench, Pressure Gauge)
- Limit to 8-10 essential tools

For repair time estimation:
- Simple inspections: 30-45 minutes
- Component replacement: 60-90 minutes
- Complex repairs: 90-180 minutes"""


class PrescriptionAgent:
    """
    Sub-agent 2: Prescription & Inventory Agent
    Invokes MCP tools to search manuals and build repair prescriptions.
    """
    
    def __init__(self, llm=None):
        """
        Initialize the Prescription Agent.
        
        Args:
            llm: LangChain LLM instance (uses Vertex AI if not provided)
        """
        if llm is None:
            from api.llm_client import get_llm_for_agents
            llm = get_llm_for_agents()
        
        self.llm = llm
        self.tools = PRESCRIPTION_TOOLS
    
    def prescribe(
        self,
        fault_code: str,
        system_affected: str,
        engine_model: Optional[str] = None,
        order_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Build repair prescription with tools and manual references.
        
        Args:
            fault_code: The fault code to research
            system_affected: The affected system (Engine, Cooling, etc.)
            engine_model: Optional engine model for manual lookup
            order_id: Optional work order ID for context
            
        Returns:
            Prescription with required_tools, manual_reference, estimated_repair_time
        """
        try:
            # Step 1: Query manuals via MCP tool
            manuals = mcp_query_manuals.invoke({
                "fault_code": fault_code or "maintenance",
                "engine_model": engine_model,
                "limit": 5,
            })
            
            # Step 2: Get historical fixes via MCP tool
            historical = mcp_get_historical_fixes.invoke({
                "system_affected": system_affected or "Engine",
                "limit": 5,
            })
            
            # Step 3: Extract tools from content
            tools = self._extract_tools_from_results(manuals, historical, system_affected)
            
            # Step 4: Build manual reference snippet
            manual_snippet = self._build_manual_snippet(manuals, engine_model)
            
            # Step 5: Build historical context
            historical_context = self._build_historical_context(historical)
            
            # Step 6: Estimate repair time
            repair_time = self._estimate_repair_time(fault_code, system_affected)
            
            return {
                "required_tools": tools[:8],
                "manual_reference_snippet": manual_snippet,
                "estimated_repair_time": repair_time,
                "historical_context": historical_context,
                "prescription_summary": f"Repair prescription for {system_affected} - {fault_code or 'inspection'}",
                "manuals": manuals,
                "historical_fixes": historical,
            }
            
        except Exception as e:
            return self._fallback_prescribe(fault_code, system_affected, engine_model, str(e))
    
    def _extract_tools_from_results(
        self,
        manuals: list,
        historical: list,
        system_affected: str,
    ) -> list[str]:
        """Extract tools from manual and historical content."""
        all_text = ""
        
        if manuals:
            for m in manuals:
                all_text += " " + (m.get("content") or "")
        
        if historical:
            for h in historical:
                all_text += " " + (h.get("resolution") or "")
                all_text += " " + (h.get("diagnostic_steps") or "")
                all_text += " " + (h.get("confirmationText") or "")
        
        tools = extract_tools_from_text(all_text)
        
        if not tools:
            tools = self._default_tools(system_affected)
        
        return tools
    
    def _build_manual_snippet(self, manuals: list, engine_model: Optional[str]) -> str:
        """Build a manual reference snippet."""
        if manuals and manuals[0].get("content"):
            return (manuals[0].get("content") or "")[:400] + "..."
        return f"See {engine_model or 'engine'} service manual for detailed procedures."
    
    def _build_historical_context(self, historical: list) -> str:
        """Build historical context summary."""
        if not historical:
            return "No similar historical repairs found."
        
        context_parts = []
        for h in historical[:3]:
            if h.get("resolution"):
                context_parts.append(h["resolution"][:100])
            elif h.get("confirmationText"):
                context_parts.append(h["confirmationText"][:100])
        
        return "; ".join(context_parts)[:300] if context_parts else "Historical repairs found."
    
    def _estimate_repair_time(self, fault_code: str, system_affected: str) -> int:
        """Estimate repair time in minutes."""
        if not fault_code or fault_code == "No_Failure":
            return 30  # Simple inspection
        
        fault_upper = (fault_code or "").upper()
        system_lower = (system_affected or "").lower()
        
        # Complex failures
        if fault_upper in ["OSF", "PWF"]:
            return 90
        elif fault_upper in ["HDF"]:
            return 75
        
        # System-based estimation
        if "fuel" in system_lower:
            return 120
        elif "cooling" in system_lower:
            return 90
        elif "electrical" in system_lower:
            return 60
        
        return 60  # Default
    
    def _default_tools(self, system_affected: str) -> list[str]:
        """Get default tools based on system affected."""
        base_tools = ["Torque Wrench", "Multimeter", "Socket Set", "Screwdriver Set"]
        
        system_lower = (system_affected or "").lower()
        if "fuel" in system_lower:
            base_tools.extend(["Fuel Pressure Gauge", "Line Wrenches"])
        elif "cooling" in system_lower:
            base_tools.extend(["Coolant Tester", "Hose Pliers"])
        elif "electrical" in system_lower:
            base_tools.extend(["Scan Tool", "Wire Crimper"])
        elif "heat" in system_lower:
            base_tools.extend(["Infrared Thermometer", "Thermal Camera"])
        
        return base_tools[:8]
    
    def _fallback_prescribe(
        self,
        fault_code: str,
        system_affected: str,
        engine_model: Optional[str],
        error: Optional[str] = None,
    ) -> dict[str, Any]:
        """Fallback when prescription fails."""
        return {
            "required_tools": self._default_tools(system_affected),
            "manual_reference_snippet": f"See {engine_model or 'engine'} service manual.",
            "estimated_repair_time": 60,
            "historical_context": "Historical data unavailable.",
            "prescription_summary": f"Basic prescription for {system_affected}",
            "manuals": [],
            "historical_fixes": [],
            "error": error,
        }


# Convenience function for direct use
def run_prescription(
    fault_code: str,
    system_affected: str,
    engine_model: Optional[str] = None,
    order_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Run prescription analysis using the Prescription Agent.
    
    Args:
        fault_code: Fault code to research
        system_affected: Affected system
        engine_model: Optional engine model
        order_id: Optional work order ID
        
    Returns:
        Prescription with tools, manual reference, repair time
    """
    agent = PrescriptionAgent()
    return agent.prescribe(fault_code, system_affected, engine_model, order_id)
