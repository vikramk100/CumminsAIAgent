import express from 'express';
import cors from 'cors';
import path from 'path';
import { fileURLToPath } from 'url';
import { setupDatabase } from './db/setup.js';
import casesRouter from './routes/cases.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = 3001;

setupDatabase();

const app = express();

app.use(cors());
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true, limit: '50mb' }));
app.use('/uploads', express.static(path.join(__dirname, '../uploads')));

app.use('/cases', casesRouter);

app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

const server = app.listen(PORT, () => {
  console.log(`\n[Server] Cummins AI Diagnostic Agent`);
  console.log(`[Server] Backend running on http://localhost:${PORT}`);
  console.log(`[Server] Health check: http://localhost:${PORT}/health\n`);
});

server.on('error', (err) => {
  if (err.code === 'EADDRINUSE') {
    console.error(`\n[Server] ERROR: Port ${PORT} is already in use.`);
    console.error(`[Server] Run this to free it: kill $(lsof -ti :${PORT})\n`);
    process.exit(1);
  }
  throw err;
});
