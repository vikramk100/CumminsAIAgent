import mcp from '../mcp/MCPServer.js';

const OLLAMA_URL = 'http://localhost:11434/api/chat';
const MODEL = 'llava';

const PROMPT = `You are an industrial diesel engine diagnostic assistant.
Analyze the provided image and the technician's description carefully.

Technician Description: "DESCRIPTION_PLACEHOLDER"

Identify and return ONLY a valid JSON object with these exact fields:
{
  "visible_damage": "description of visible damage or anomalies observed in the image",
  "fault_category": "one of: MECHANICAL, ELECTRICAL, THERMAL, FLUID_LEAK, STRUCTURAL, WEAR, UNKNOWN",
  "severity": "one of: LOW, MEDIUM, HIGH, CRITICAL",
  "warranty_likelihood": "one of: LOW, MEDIUM, HIGH",
  "confidence": <number between 0.0 and 1.0>,
  "rationale": "brief clinical explanation of your diagnosis"
}

Return ONLY the JSON object. No explanation. No markdown. No code blocks. No preamble.`;

class VisionFaultAgent {
  async analyze({ caseId, imageBase64, description }) {
    console.log(`\n[VisionFaultAgent] ▶ Starting analysis — case: ${caseId}`);
    console.log(`[VisionFaultAgent]   Description: "${description || 'none'}"`);

    const prompt = PROMPT.replace('DESCRIPTION_PLACEHOLDER', description || 'No description provided');

    let parsed = null;

    try {
      const payload = {
        model: MODEL,
        messages: [
          {
            role: 'user',
            content: prompt,
            images: [imageBase64]
          }
        ],
        stream: false
      };

      console.log(`[VisionFaultAgent]   Calling Ollama (${MODEL}) at ${OLLAMA_URL}`);

      const response = await fetch(OLLAMA_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        throw new Error(`Ollama HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      const rawText = data.message?.content || '';

      console.log(`[VisionFaultAgent]   Raw model output:\n${rawText}`);

      parsed = this._parseJSON(rawText);
    } catch (err) {
      console.error(`[VisionFaultAgent]   ✗ Ollama error:`, err.message);
      parsed = {
        visible_damage: 'Image analysis unavailable — model unreachable',
        fault_category: 'UNKNOWN',
        severity: 'MEDIUM',
        warranty_likelihood: 'LOW',
        confidence: 0.1,
        rationale: `Model inference failed: ${err.message}. Manual inspection required.`
      };
    }

    console.log(`[VisionFaultAgent]   Parsed output:`, parsed);
    console.log(`[VisionFaultAgent]   Confidence: ${parsed.confidence}`);

    mcp.invoke('updateCaseStatus', {
      id: caseId,
      updates: {
        visible_damage: parsed.visible_damage,
        fault_category: parsed.fault_category,
        severity: parsed.severity
      }
    });

    mcp.invoke('writeDecisionLog', {
      case_id: caseId,
      agent_name: 'VisionFaultAgent',
      input_summary: `Multimodal image analysis. Technician description: "${description || 'none'}"`,
      output_json: parsed,
      confidence: parsed.confidence,
      rationale: parsed.rationale
    });

    return parsed;
  }

  _parseJSON(text) {
    // Attempt 1: direct parse
    try {
      return JSON.parse(text.trim());
    } catch {}

    // Attempt 2: extract JSON block from surrounding text
    try {
      const match = text.match(/\{[\s\S]*\}/);
      if (match) return JSON.parse(match[0]);
    } catch {}

    // Fallback
    return {
      visible_damage: 'Could not parse model output — raw response stored in logs',
      fault_category: 'UNKNOWN',
      severity: 'MEDIUM',
      warranty_likelihood: 'LOW',
      confidence: 0.1,
      rationale: 'JSON parsing failed. Raw output: ' + text.substring(0, 200)
    };
  }
}

export default new VisionFaultAgent();
