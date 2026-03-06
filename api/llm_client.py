"""
LLM Client Module - Dual LLM Setup

Primary LLM: Google Vertex AI (Gemini) - used for main agents (Orchestrator, Diagnostic, Prescription)
Vision LLM: Ollama (llava) - used locally for image-based CV analysis by VisionAgent

Requires:
- GCP credentials for Vertex AI (GOOGLE_APPLICATION_CREDENTIALS)
- Ollama running at http://localhost:11434 with llava model for vision
"""

import os
import logging

logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Vertex AI Configuration ───────────────────────────────────────────────────

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "workorderaiagent")
GCP_REGION = os.environ.get("GCP_REGION", "us-central1")
VERTEX_MODEL = os.environ.get("VERTEX_MODEL", "gemini-2.0-flash-001")

# ── Ollama Configuration (for VisionAgent) ────────────────────────────────────

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llava")

_vertex_client = None
_ollama_client = None


# ── Vertex AI Functions ───────────────────────────────────────────────────────

def get_vertex_client():
    """
    Initialize and return a LangChain ChatVertexAI client for main LLM tasks.
    """
    global _vertex_client
    if _vertex_client is not None:
        return _vertex_client

    try:
        from langchain_google_vertexai import ChatVertexAI
    except ImportError:
        raise ImportError(
            "langchain-google-vertexai not found. "
            "Run: pip install langchain-google-vertexai"
        )

    _vertex_client = ChatVertexAI(
        model=VERTEX_MODEL,
        project=GCP_PROJECT_ID,
        location=GCP_REGION,
        temperature=0.2,
        max_output_tokens=4096,
    )
    logger.info(f"[LLM] Vertex AI initialized: {VERTEX_MODEL}")
    return _vertex_client


def get_llm_for_agents():
    """
    Get LLM instance configured for use with LangChain agents.
    Uses Vertex AI (Gemini) for main agent tasks.
    """
    return get_vertex_client()


def generate_content(prompt: str, temperature: float = 0.2) -> str:
    """
    Generate content using Vertex AI.
    Returns the text response.
    """
    client = get_vertex_client()
    response = client.invoke(prompt)
    return response.content


# ── Ollama Functions (for VisionAgent) ────────────────────────────────────────

def get_ollama_client():
    """
    Initialize and return a LangChain ChatOllama client for vision tasks.
    Used by VisionAgent for llava multimodal image analysis.
    """
    global _ollama_client
    if _ollama_client is not None:
        return _ollama_client

    try:
        from langchain_ollama import ChatOllama
    except ImportError:
        try:
            from langchain_community.chat_models import ChatOllama
        except ImportError:
            raise ImportError(
                "Ollama LangChain package not found. "
                "Run: pip install langchain-ollama"
            )

    _ollama_client = ChatOllama(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=0.1,
        num_predict=2048,
    )
    logger.info(f"[LLM] Ollama initialized: {OLLAMA_MODEL} @ {OLLAMA_BASE_URL}")
    return _ollama_client


# Legacy alias
generate_content_raw = generate_content
