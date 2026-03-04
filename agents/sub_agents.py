"""
Three sub-agents: Research, Data, Writer.
Each has a role and access to MCP tools via LangChain.
"""
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool

from .mcp_adapter import get_langchain_tools_from_mcp

SUB_AGENTS = {
    "research": {
        "name": "Research",
        "system": "You are a research agent. Use search_kb to find information. Answer concisely.",
    },
    "data": {
        "name": "Data",
        "system": "You are a data agent. Use get_metrics to fetch metrics. Respond with clear data.",
    },
    "writer": {
        "name": "Writer",
        "system": "You are a writer agent. Use format_report to structure content. Be clear and concise.",
    },
}


async def run_sub_agent(
    agent_key: str,
    user_message: str,
    llm: Any,
    max_tool_rounds: int = 3,
) -> str:
    """
    Run one sub-agent with MCP tools using a LangChain LLM with tool-calling.

    ``llm`` is expected to be a LangChain chat model (e.g. ChatGoogleGenerativeAI).
    """
    if agent_key not in SUB_AGENTS:
        return f"Unknown agent: {agent_key}. Use one of: research, data, writer."

    agent = SUB_AGENTS[agent_key]
    tools: List[BaseTool] = get_langchain_tools_from_mcp()
    tool_map: Dict[str, BaseTool] = {t.name: t for t in tools}
    llm_with_tools = llm.bind_tools(tools)

    messages: List[Any] = [
        SystemMessage(content=agent["system"]),
        HumanMessage(content=user_message),
    ]

    for _ in range(max_tool_rounds):
        ai_msg = await llm_with_tools.ainvoke(messages)
        tool_calls = getattr(ai_msg, "tool_calls", None) or []

        # If the model didn't request a tool, treat this as the final answer.
        if not tool_calls:
            content = ai_msg.content
            if isinstance(content, str):
                return content.strip() or "(No response)"
            return str(content) if content is not None else "(No response)"

        # Execute the first requested tool call.
        call = tool_calls[0]
        name = getattr(call, "name", None) or (call.get("name") if isinstance(call, dict) else "")
        args = getattr(call, "args", None) or (call.get("args") if isinstance(call, dict) else {}) or {}
        if not isinstance(args, dict):
            args = {}

        tool = tool_map.get(name)
        if tool is None:
            return f"Requested unknown tool '{name}'."

        tool_result = await tool.ainvoke(args)

        messages.append(ai_msg)
        tool_call_id = getattr(call, "id", None) or (call.get("id") if isinstance(call, dict) else name)
        messages.append(ToolMessage(content=str(tool_result), tool_call_id=tool_call_id))

    return "(Max tool rounds reached.)"
