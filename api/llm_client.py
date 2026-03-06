"""
Ollama LLM Client - Local inference via Ollama (llava multimodal model).
Replaces Vertex AI. Requires Ollama running at http://localhost:11434.
"""

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llava")

_llm_client = None


def get_ollama_client():
    """
    Initialize and return a LangChain ChatOllama client.
    """
    global _llm_client
    if _llm_client is not None:
        return _llm_client

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

    _llm_client = ChatOllama(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=0.2,
        num_predict=4096,
    )
    return _llm_client


def generate_content(prompt: str, temperature: float = 0.2) -> str:
    """
    Generate content using Ollama.
    Returns the text response.
    """
    client = get_ollama_client()
    response = client.invoke(prompt)
    return response.content


def get_llm_for_agents():
    """
    Get LLM instance configured for use with LangChain agents.
    """
    return get_ollama_client()


# Legacy alias
generate_content_raw = generate_content
