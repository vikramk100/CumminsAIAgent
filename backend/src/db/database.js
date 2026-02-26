import Database from 'better-sqlite3';
import { fileURLToPath } from 'url';
import path from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const dbPath = path.join(__dirname, '../../data/cases.db');

const db = new Database(dbPath);
db.pragma('journal_mode = WAL');

export default db;
