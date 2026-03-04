"""
Orchestrator agent: routes user messages to one of three sub-agents
(`research`, `data`, `writer`) using LangChain and FastMCP tools.
"""
import asyncio
import os

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from .sub_agents import run_sub_agent

ORCHESTRATOR_SYSTEM = """You are an orchestrator. Given the user message, reply with exactly one word:
- research (for questions, lookup, "find", "search", "what is")
- data (for metrics, numbers, "get data", "analytics", "metrics")
- writer (for summarization, "write", "format", "report", "summarize")

Reply only that one word, nothing else."""


def _get_llm() -> ChatGoogleGenerativeAI:
    """
    Configure and return the LangChain chat model for Gemini.
    """
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    if not api_key:
        raise ValueError("Set GEMINI_API_KEY in .env")
    return ChatGoogleGenerativeAI(model=model, google_api_key=api_key)


def _route_to_agent(user_message: str) -> str:
    """
    Use a lightweight LangChain chain to select which sub-agent should handle
    the request.
    """
    llm = _get_llm()
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", ORCHESTRATOR_SYSTEM),
            ("user", "{input}"),
        ]
    )
    chain = prompt | llm | StrOutputParser()
    choice = chain.invoke({"input": user_message}).strip().lower()
    for key in ("research", "data", "writer"):
        if key in choice:
            return key
    return "research"


def run_orchestrator(user_message: str) -> str:
    """
    Sync entry: pick a sub-agent via orchestrator chain, then run that
    sub-agent with MCP tools using LangChain.
    """
    print(f"Orchestrator received message: {user_message}")
    llm = _get_llm()
    print(f"Orchestrator using model: {llm.model}")
    choice = _route_to_agent(user_message)
    print(f"Orchestrator routing to agent: {choice}")
    reply = asyncio.run(run_sub_agent(choice, user_message, llm))
    print(f"Orchestrator reply: {reply}")
    return reply
