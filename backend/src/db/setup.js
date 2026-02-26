import db from './database.js';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const dataDir = path.join(__dirname, '../../data');

export function setupDatabase() {
  if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true });
  }

  db.exec(`
    CREATE TABLE IF NOT EXISTS Cases (
      id TEXT PRIMARY KEY,
      image_path TEXT,
      raw_description TEXT,
      visible_damage TEXT,
      fault_category TEXT,
      severity TEXT,
      risk_score INTEGER,
      route TEXT,
      final_status TEXT DEFAULT 'PENDING',
      created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS DecisionLogs (
      id TEXT PRIMARY KEY,
      case_id TEXT,
      agent_name TEXT,
      input_summary TEXT,
      output_json TEXT,
      confidence REAL,
      rationale TEXT,
      timestamp TEXT DEFAULT (datetime('now')),
      FOREIGN KEY (case_id) REFERENCES Cases(id)
    );
  `);

  console.log('[DB] Database initialized');
}
