"""
Adapt FastMCP tools to LangChain tools so they can be used by the
multi‑agent orchestrator.
"""
from typing import List

from langchain_core.tools import StructuredTool

from mcp_tools import format_report, get_metrics, search_kb


def get_langchain_tools_from_mcp() -> List[StructuredTool]:
    """
    Return LangChain tools that wrap the FastMCP-registered functions.

    These tools can be passed to a LangChain LLM via ``bind_tools`` to
    enable tool-calling for MCP tools.
    """
    return [
        StructuredTool.from_function(search_kb),
        StructuredTool.from_function(get_metrics),
        StructuredTool.from_function(format_report),
    ]
