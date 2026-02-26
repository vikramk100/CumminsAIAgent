import { v4 as uuidv4 } from 'uuid';
import mcp from '../mcp/MCPServer.js';
import VisionFaultAgent from '../agents/VisionFaultAgent.js';
import RiskScoringAgent from '../agents/RiskScoringAgent.js';
import RoutingAgent from '../agents/RoutingAgent.js';

class Orchestrator {
  async processCase({ imageBase64, imagePath, description }) {
    const caseId = uuidv4();
    console.log(`\n${'='.repeat(60)}`);
    console.log(`[Orchestrator] ▶ New case: ${caseId}`);
    console.log(`${'='.repeat(60)}`);

    // Step 1: Persist raw case via MCP
    mcp.invoke('writeCaseRecord', {
      id: caseId,
      image_path: imagePath,
      raw_description: description
    });

    // Step 2: Vision fault analysis (LLM)
    const visionResult = await VisionFaultAgent.analyze({
      caseId,
      imageBase64,
      description
    });

    // Step 3: Deterministic risk scoring
    const riskResult = RiskScoringAgent.score({
      caseId,
      fault_category: visionResult.fault_category,
      severity: visionResult.severity,
      warranty_likelihood: visionResult.warranty_likelihood
    });

    // Step 4: Deterministic routing
    const routingResult = RoutingAgent.route({
      caseId,
      risk_score: riskResult.risk_score
    });

    // Step 5: Fetch full case + audit timeline
    const { case: caseRecord, logs } = mcp.invoke('fetchCase', { id: caseId });

    console.log(`\n[Orchestrator] ✓ Case ${caseId} complete — route: ${routingResult.route}`);
    console.log(`${'='.repeat(60)}\n`);

    return {
      case: caseRecord,
      timeline: logs,
      vision: visionResult,
      risk: riskResult,
      routing: routingResult
    };
  }
}

export default new Orchestrator();
