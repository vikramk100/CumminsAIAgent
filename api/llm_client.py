"""
Vertex AI LLM Client - Replaces GEMINI_API_KEY with GCP Vertex AI.
"""

import os
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# GCP Vertex AI Configuration
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "workorderaiagent")
GCP_REGION = os.environ.get("GCP_REGION", "us-central1")
GCP_SERVICE_ACCOUNT_JSON = os.environ.get(
    "GOOGLE_APPLICATION_CREDENTIALS",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "workorderaiagent-78d1803b165f.json")
)
VERTEX_MODEL = os.environ.get("VERTEX_MODEL", "gemini-2.0-flash-001")

# Set credentials environment variable if not already set
if os.path.exists(GCP_SERVICE_ACCOUNT_JSON):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GCP_SERVICE_ACCOUNT_JSON

_llm_client = None


def get_vertex_client():
    """
    Initialize and return the Vertex AI Generative Model client.
    Uses LangChain's ChatVertexAI for compatibility with agent frameworks.
    """
    global _llm_client
    if _llm_client is not None:
        return _llm_client
    
    try:
        from langchain_google_vertexai import ChatVertexAI
        import vertexai
        
        # Initialize Vertex AI
        vertexai.init(project=GCP_PROJECT_ID, location=GCP_REGION)
        
        _llm_client = ChatVertexAI(
            model=VERTEX_MODEL,
            project=GCP_PROJECT_ID,
            location=GCP_REGION,
            temperature=0.2,
            max_tokens=4096,
        )
        return _llm_client
    except ImportError as e:
        raise ImportError(
            f"Required packages not installed: {e}. "
            "Run: pip install google-cloud-aiplatform langchain-google-vertexai"
        )


def generate_content(prompt: str, temperature: float = 0.2) -> str:
    """
    Generate content using Vertex AI.
    Returns the text response.
    """
    client = get_vertex_client()
    response = client.invoke(prompt)
    return response.content


def get_llm_for_agents():
    """
    Get LLM instance configured for use with LangChain agents.
    """
    return get_vertex_client()


# Legacy compatibility: direct generation without LangChain
def generate_content_raw(prompt: str, temperature: float = 0.2) -> str:
    """
    Direct Vertex AI generation using google-cloud-aiplatform SDK.
    Fallback for non-agent use cases.
    """
    try:
        from vertexai.generative_models import GenerativeModel, GenerationConfig
        import vertexai
        
        vertexai.init(project=GCP_PROJECT_ID, location=GCP_REGION)
        
        model = GenerativeModel(VERTEX_MODEL)
        config = GenerationConfig(temperature=temperature, max_output_tokens=4096)
        response = model.generate_content(prompt, generation_config=config)
        return response.text
    except Exception as e:
        raise RuntimeError(f"Vertex AI generation failed: {e}")
