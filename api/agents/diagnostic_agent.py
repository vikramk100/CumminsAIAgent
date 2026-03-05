"""
Diagnostic & Telemetry Agent (Sub-agent 1)

Responsible for:
- Retrieving ML failure predictions for equipment
- Analyzing telemetry snapshots
- Getting diagnostic information for fault codes
- Determining system affected and severity
"""

import json
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from api.agents.base import (
    DIAGNOSTIC_TOOLS,
    mcp_get_ml_prediction,
    mcp_get_diagnostic_info,
    mcp_get_machine_log,
    mcp_get_engine_models,
)


DIAGNOSTIC_AGENT_PROMPT = """You are a Diagnostic & Telemetry Analysis Agent for industrial equipment maintenance.

Your responsibilities:
1. Retrieve ML failure predictions for the given equipment using mcp_get_ml_prediction
2. Analyze telemetry data (temperatures, rotational speed, torque, tool wear)
3. Look up diagnostic information for any fault codes using mcp_get_diagnostic_info
4. Determine the system affected and severity level

When analyzing, focus on:
- The ML prediction confidence level
- Key telemetry indicators (high temperatures, abnormal speeds, excessive torque)
- The predicted fault code and its severity
- The system affected (Engine, Cooling, Fuel, etc.)

Always return structured analysis in JSON format."""


class DiagnosticAgent:
    """
    Sub-agent 1: Diagnostic & Telemetry Analysis
    Invokes MCP tools to get ML predictions and telemetry data.
    """
    
    def __init__(self, llm=None):
        """
        Initialize the Diagnostic Agent.
        
        Args:
            llm: LangChain LLM instance (uses Vertex AI if not provided)
        """
        if llm is None:
            from api.llm_client import get_llm_for_agents
            llm = get_llm_for_agents()
        
        self.llm = llm
        self.tools = DIAGNOSTIC_TOOLS
    
    def analyze(self, equipment_id: str, order_id: Optional[str] = None) -> dict[str, Any]:
        """
        Run diagnostic analysis for the given equipment.
        
        Args:
            equipment_id: The equipment/machine ID to analyze
            order_id: Optional work order ID for context
            
        Returns:
            Diagnostic analysis with ML prediction, telemetry, fault code, system affected
        """
        try:
            # Step 1: Get ML prediction via MCP tool
            ml_result = mcp_get_ml_prediction.invoke(equipment_id)
            
            fault_code = ml_result.get("fault_code", "")
            
            # Step 2: Get diagnostic info if we have a fault code
            diag_info = {}
            if fault_code and fault_code != "No_Failure":
                diag_info = mcp_get_diagnostic_info.invoke(fault_code)
            
            # Step 3: Determine system affected
            system_affected = self._determine_system_affected(fault_code, diag_info)
            
            # Step 4: Use LLM to synthesize analysis (optional enhancement)
            diagnostic_summary = self._generate_summary(ml_result, diag_info, system_affected)
            
            return {
                "equipment_id": equipment_id,
                "ml_prediction": {
                    "failure_label": ml_result.get("failure_label", "No_Failure"),
                    "confidence": ml_result.get("confidence", 0.0),
                    "fault_code": fault_code,
                    "severity": ml_result.get("severity", 3),
                },
                "telemetry": ml_result.get("telemetry", {}),
                "system_affected": system_affected,
                "symptom": ml_result.get("symptom", ""),
                "diagnostic_summary": diagnostic_summary,
            }
            
        except Exception as e:
            return self._fallback_analyze(equipment_id, str(e))
    
    def _determine_system_affected(self, fault_code: str, diag_info: dict) -> str:
        """Determine the affected system from fault code or diagnostic info."""
        # Try diagnostic info first
        system = diag_info.get("system_affected", "")
        if system:
            return system
        
        # Derive from fault code pattern
        if not fault_code or fault_code == "No_Failure":
            return "Engine"
        
        fault_upper = fault_code.upper()
        if fault_upper.startswith("OSF"):
            return "All Systems"
        elif fault_upper.startswith("HDF"):
            return "Heat Dissipation"
        elif fault_upper.startswith("PWF"):
            return "Power / Mechanical"
        elif fault_upper.startswith("RNF"):
            return "Operational"
        elif "FUEL" in fault_upper:
            return "Fuel System"
        elif "COOL" in fault_upper:
            return "Cooling"
        elif "ELEC" in fault_upper:
            return "Electrical"
        
        return "Engine"
    
    def _generate_summary(self, ml_result: dict, diag_info: dict, system_affected: str) -> str:
        """Generate a human-readable diagnostic summary."""
        failure_label = ml_result.get("failure_label", "No_Failure")
        confidence = ml_result.get("confidence", 0.0)
        fault_code = ml_result.get("fault_code", "")
        
        if failure_label == "No_Failure":
            return "No failure predicted. Equipment appears to be operating normally."
        
        parts = [f"ML prediction: {failure_label}"]
        if fault_code:
            parts.append(f"(fault code: {fault_code})")
        parts.append(f"with {confidence*100:.0f}% confidence.")
        parts.append(f"System affected: {system_affected}.")
        
        if diag_info.get("resolution"):
            parts.append(f"Recommended action: {diag_info['resolution'][:100]}...")
        
        return " ".join(parts)
    
    def _fallback_analyze(self, equipment_id: str, error: Optional[str] = None) -> dict[str, Any]:
        """Fallback when analysis fails."""
        return {
            "equipment_id": equipment_id,
            "ml_prediction": {
                "failure_label": "No_Failure",
                "confidence": 0.0,
                "fault_code": "",
                "severity": 3,
            },
            "telemetry": {},
            "system_affected": "Engine",
            "symptom": "",
            "diagnostic_summary": f"Analysis unavailable: {error}",
            "error": error,
        }


# Convenience function for direct use
def run_diagnostic_analysis(equipment_id: str, order_id: Optional[str] = None) -> dict[str, Any]:
    """
    Run diagnostic analysis using the Diagnostic Agent.
    
    Args:
        equipment_id: Equipment to analyze
        order_id: Optional work order ID
        
    Returns:
        Diagnostic analysis results
    """
    agent = DiagnosticAgent()
    return agent.analyze(equipment_id, order_id)
