import db from '../db/database.js';
import { v4 as uuidv4 } from 'uuid';

class MCPServer {
  invoke(toolName, params) {
    console.log(`\n[MCP] ► Tool: ${toolName}`);
    console.log(`[MCP]   Params:`, JSON.stringify(params, null, 2));

    const timestamp = new Date().toISOString();

    switch (toolName) {
      case 'writeCaseRecord':
        return this.writeCaseRecord(params);
      case 'writeDecisionLog':
        return this.writeDecisionLog({ ...params, timestamp });
      case 'updateCaseStatus':
        return this.updateCaseStatus(params);
      case 'fetchCase':
        return this.fetchCase(params);
      default:
        throw new Error(`[MCP] Unknown tool: ${toolName}`);
    }
  }

  writeCaseRecord({ id, image_path, raw_description }) {
    const stmt = db.prepare(`
      INSERT INTO Cases (id, image_path, raw_description, final_status, created_at)
      VALUES (?, ?, ?, 'PENDING', datetime('now'))
    `);
    stmt.run(id, image_path, raw_description);
    console.log(`[MCP]   ✓ Case record written: ${id}`);
    return { success: true, id };
  }

  writeDecisionLog({ case_id, agent_name, input_summary, output_json, confidence, rationale, timestamp }) {
    const id = uuidv4();
    const stmt = db.prepare(`
      INSERT INTO DecisionLogs (id, case_id, agent_name, input_summary, output_json, confidence, rationale, timestamp)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `);
    stmt.run(
      id,
      case_id,
      agent_name,
      input_summary,
      typeof output_json === 'string' ? output_json : JSON.stringify(output_json),
      confidence,
      rationale,
      timestamp
    );
    console.log(`[MCP]   ✓ Decision log written — case: ${case_id}, agent: ${agent_name}`);
    return { success: true, log_id: id };
  }

  updateCaseStatus({ id, updates }) {
    const fields = Object.keys(updates).map((k) => `${k} = ?`).join(', ');
    const values = Object.values(updates);
    db.prepare(`UPDATE Cases SET ${fields} WHERE id = ?`).run(...values, id);
    console.log(`[MCP]   ✓ Case ${id} updated:`, updates);
    return { success: true };
  }

  fetchCase({ id }) {
    const caseRecord = db.prepare('SELECT * FROM Cases WHERE id = ?').get(id);
    const logs = db
      .prepare('SELECT * FROM DecisionLogs WHERE case_id = ? ORDER BY timestamp ASC')
      .all(id);
    return { case: caseRecord, logs };
  }

  fetchAllPendingManagerReview() {
    return db
      .prepare(`SELECT * FROM Cases WHERE route = 'MANAGER_REVIEW' AND final_status = 'PENDING' ORDER BY created_at DESC`)
      .all();
  }

  fetchAllCases() {
    return db.prepare('SELECT * FROM Cases ORDER BY created_at DESC').all();
  }
}

export default new MCPServer();
