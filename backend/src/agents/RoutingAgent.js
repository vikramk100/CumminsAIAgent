import mcp from '../mcp/MCPServer.js';

const REVIEW_THRESHOLD = 70;

class RoutingAgent {
  route({ caseId, risk_score }) {
    console.log(`\n[RoutingAgent] ▶ Routing — case: ${caseId}`);
    console.log(`[RoutingAgent]   Risk score: ${risk_score}`);

    const route = risk_score > REVIEW_THRESHOLD ? 'MANAGER_REVIEW' : 'AUTO_APPROVE';
    const final_status = route === 'AUTO_APPROVE' ? 'APPROVED' : 'PENDING';
    const confidence = 1.0;
    const rationale = `Risk score ${risk_score} ${risk_score > REVIEW_THRESHOLD ? `> ${REVIEW_THRESHOLD}` : `≤ ${REVIEW_THRESHOLD}`} → ${route}.`;

    const output = { route, confidence, rationale };

    console.log(`[RoutingAgent]   Output:`, output);

    mcp.invoke('updateCaseStatus', {
      id: caseId,
      updates: { route, final_status }
    });

    mcp.invoke('writeDecisionLog', {
      case_id: caseId,
      agent_name: 'RoutingAgent',
      input_summary: `risk_score=${risk_score}`,
      output_json: output,
      confidence,
      rationale
    });

    return output;
  }
}

export default new RoutingAgent();
