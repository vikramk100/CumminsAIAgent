import mcp from '../mcp/MCPServer.js';

const SEVERITY_SCORES = {
  CRITICAL: 90,
  HIGH: 75,
  MEDIUM: 40,
  LOW: 20
};

const COST_BASE = {
  CRITICAL: 15000,
  HIGH: 7500,
  MEDIUM: 2500,
  LOW: 500
};

const CATEGORY_MULTIPLIERS = {
  STRUCTURAL: 2.0,
  MECHANICAL: 1.5,
  THERMAL: 1.3,
  ELECTRICAL: 1.2,
  FLUID_LEAK: 1.0,
  WEAR: 0.8,
  UNKNOWN: 1.0
};

class RiskScoringAgent {
  score({ caseId, fault_category, severity, warranty_likelihood }) {
    console.log(`\n[RiskScoringAgent] ▶ Scoring — case: ${caseId}`);
    console.log(`[RiskScoringAgent]   Input: severity=${severity}, category=${fault_category}, warranty=${warranty_likelihood}`);

    let risk_score = SEVERITY_SCORES[severity] ?? 20;

    // Warranty adjustment: HIGH warranty likelihood bumps score
    if (warranty_likelihood === 'HIGH') {
      risk_score = Math.min(risk_score + 5, 100);
    }

    const baseCost = COST_BASE[severity] ?? 1000;
    const multiplier = CATEGORY_MULTIPLIERS[fault_category] ?? 1.0;
    const estimated_cost = Math.round(baseCost * multiplier);

    const confidence = 0.95;
    const rationale = `Severity=${severity} → base score ${SEVERITY_SCORES[severity] ?? 20}${warranty_likelihood === 'HIGH' ? ' +5 warranty adj' : ''}. Category=${fault_category} (×${multiplier}). Estimated repair cost: $${estimated_cost.toLocaleString()}.`;

    const output = { risk_score, estimated_cost, confidence, rationale };

    console.log(`[RiskScoringAgent]   Output:`, output);

    mcp.invoke('updateCaseStatus', {
      id: caseId,
      updates: { risk_score }
    });

    mcp.invoke('writeDecisionLog', {
      case_id: caseId,
      agent_name: 'RiskScoringAgent',
      input_summary: `fault_category=${fault_category}, severity=${severity}, warranty_likelihood=${warranty_likelihood}`,
      output_json: output,
      confidence,
      rationale
    });

    return output;
  }
}

export default new RiskScoringAgent();
