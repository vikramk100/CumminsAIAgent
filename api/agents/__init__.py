"""
Multi-Agent System for Work Order AI Agent.

This module implements a multi-agent architecture with:
- Orchestrator Agent: Coordinates sub-agents and synthesizes final briefing
- Diagnostic Agent: Handles ML predictions and telemetry analysis
- Prescription Agent: Searches manuals and historical fixes for repair guidance
"""

from api.agents.orchestrator import OrchestratorAgent, get_dispatch_brief
from api.agents.diagnostic_agent import DiagnosticAgent
from api.agents.prescription_agent import PrescriptionAgent

__all__ = [
    "OrchestratorAgent",
    "DiagnosticAgent", 
    "PrescriptionAgent",
    "get_dispatch_brief",
]
