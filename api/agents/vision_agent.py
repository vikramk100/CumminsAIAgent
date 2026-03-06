"""
Vision Agent (Sub-agent 3) - Image-based CV Analysis via Ollama (llava)

Responsible for:
- Accepting images uploaded by technicians for a work order
- Sending images to llava (local multimodal model) via Ollama
- Extracting: component identification, damage type, severity, defects, repair actions
- Storing results via MCP and incorporating findings into the Mission Briefing
"""

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

SEVERITY_LEVELS = ["None", "Low", "Medium", "High", "Critical"]

VISION_SYSTEM_PROMPT = """You are an industrial equipment visual inspection AI for Cummins diesel engines.
Analyze the provided image(s) and produce a structured JSON inspection report.

For each image, identify:
1. Components visible (e.g., "turbocharger", "fuel injector", "heat exchanger", "oil filter", "exhaust manifold")
2. Damage or anomalies observed (e.g., "corrosion", "oil leak", "crack", "worn seal", "carbon buildup", "loose fastener")
3. Overall severity: one of [None, Low, Medium, High, Critical]
4. Recommended repair actions (specific, actionable steps)
5. Confidence score 0.0-1.0 based on image clarity and certainty of findings

Return ONLY a valid JSON object - no markdown, no extra text:
{
  "components_identified": ["list of components visible"],
  "defects_found": ["list of specific defects or anomalies"],
  "damage_assessment": "one paragraph describing what you see and why it matters",
  "severity": "None|Low|Medium|High|Critical",
  "recommended_actions": ["list of specific repair or inspection steps"],
  "confidence": 0.85,
  "image_count": 1
}"""


class VisionAgent:
    """
    Sub-agent 3: Visual Inspection via Ollama llava multimodal model.
    """

    def __init__(self):
        from api.llm_client import get_ollama_client, OLLAMA_MODEL, OLLAMA_BASE_URL
        # Use llava specifically for vision; fall back to whatever is configured
        try:
            from langchain_ollama import ChatOllama
        except ImportError:
            from langchain_community.chat_models import ChatOllama

        model = OLLAMA_MODEL if "llava" in OLLAMA_MODEL else "llava"
        self._client = ChatOllama(
            model=model,
            base_url=OLLAMA_BASE_URL,
            temperature=0.1,
            num_predict=2048,
        )

    def analyze_images(
        self,
        images_b64: list[str],
        mime_types: list[str],
        work_order: Optional[dict] = None,
    ) -> dict[str, Any]:
        """
        Run CV analysis on a list of base64-encoded images.

        Args:
            images_b64: List of base64-encoded image strings
            mime_types: Corresponding MIME types (e.g. "image/jpeg")
            work_order: Optional work order context

        Returns:
            Structured analysis dict
        """
        if not images_b64:
            return self._empty_result("No images provided")

        try:
            from langchain_core.messages import HumanMessage

            prompt_text = VISION_SYSTEM_PROMPT
            if work_order:
                eq_id = work_order.get("equipmentId", "")
                issue = work_order.get("issueDescription", "")
                prompt_text += (
                    f"\n\nWork Order Context:\n"
                    f"Equipment: {eq_id}\n"
                    f"Reported Issue: {issue}\n"
                    f"Focus your analysis on defects related to this reported issue."
                )

            # Build content blocks: text + images
            content = [{"type": "text", "text": prompt_text}]
            for b64, mime in zip(images_b64, mime_types):
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"},
                })

            response = self._client.invoke([HumanMessage(content=content)])
            raw = response.content.strip()
            return self._parse_response(raw, len(images_b64))

        except Exception as e:
            logger.error(f"[VisionAgent] llava call failed: {e}")
            return self._fallback_result(len(images_b64), str(e))

    def get_analyses_for_order(self, order_id: str) -> list[dict[str, Any]]:
        from api.mcp_server import get_image_analyses
        return get_image_analyses(order_id)

    def _parse_response(self, raw: str, image_count: int) -> dict[str, Any]:
        text = raw
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        try:
            result = json.loads(text)
        except Exception:
            return {
                "components_identified": [],
                "defects_found": [],
                "damage_assessment": raw[:500],
                "severity": "Low",
                "recommended_actions": ["Manual inspection required — AI could not parse structured output."],
                "confidence": 0.3,
                "image_count": image_count,
                "parse_error": True,
            }

        if result.get("severity") not in SEVERITY_LEVELS:
            result["severity"] = "Low"
        result["image_count"] = image_count
        return result

    def _empty_result(self, reason: str) -> dict[str, Any]:
        return {
            "components_identified": [],
            "defects_found": [],
            "damage_assessment": reason,
            "severity": "None",
            "recommended_actions": [],
            "confidence": 0.0,
            "image_count": 0,
        }

    def _fallback_result(self, image_count: int, error: str) -> dict[str, Any]:
        return {
            "components_identified": [],
            "defects_found": [],
            "damage_assessment": f"Image analysis unavailable: {error}",
            "severity": "Low",
            "recommended_actions": ["Physical inspection required — automated vision analysis failed."],
            "confidence": 0.0,
            "image_count": image_count,
            "error": error,
        }
