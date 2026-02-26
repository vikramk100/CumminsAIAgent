import express from 'express';
import multer from 'multer';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';
import { v4 as uuidv4 } from 'uuid';
import orchestrator from '../orchestrator/orchestrator.js';
import mcp from '../mcp/MCPServer.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const router = express.Router();

const uploadsDir = path.join(__dirname, '../../uploads');
if (!fs.existsSync(uploadsDir)) {
  fs.mkdirSync(uploadsDir, { recursive: true });
}

const storage = multer.diskStorage({
  destination: uploadsDir,
  filename: (req, file, cb) => cb(null, `${uuidv4()}-${file.originalname}`)
});

const upload = multer({
  storage,
  limits: { fileSize: 20 * 1024 * 1024 } // 20MB max
});

// POST /cases — submit a new case
router.post('/', upload.single('image'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'Image file is required' });
    }

    const description = req.body.description || '';
    const imageBuffer = fs.readFileSync(req.file.path);
    const imageBase64 = imageBuffer.toString('base64');

    const result = await orchestrator.processCase({
      imageBase64,
      imagePath: req.file.path,
      description
    });

    res.json(result);
  } catch (err) {
    console.error('[Route /cases POST] Error:', err);
    res.status(500).json({ error: err.message });
  }
});

// GET /cases — list all cases
router.get('/', (req, res) => {
  try {
    res.json(mcp.fetchAllCases());
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /cases/review — cases pending manager review
router.get('/review', (req, res) => {
  try {
    res.json(mcp.fetchAllPendingManagerReview());
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /cases/:id — single case with full timeline
router.get('/:id', (req, res) => {
  try {
    const result = mcp.invoke('fetchCase', { id: req.params.id });
    if (!result.case) {
      return res.status(404).json({ error: 'Case not found' });
    }
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// POST /cases/:id/approve — manager approve or override
router.post('/:id/approve', (req, res) => {
  try {
    const { override_reason } = req.body;
    const isOverride = Boolean(override_reason && override_reason.trim());
    const final_status = isOverride ? 'OVERRIDDEN' : 'APPROVED';

    mcp.invoke('updateCaseStatus', {
      id: req.params.id,
      updates: { final_status }
    });

    mcp.invoke('writeDecisionLog', {
      case_id: req.params.id,
      agent_name: 'ManagerDecision',
      input_summary: `Manager action: ${isOverride ? 'OVERRIDE' : 'APPROVE'}`,
      output_json: {
        action: isOverride ? 'OVERRIDE' : 'APPROVE',
        override_reason: override_reason || null,
        final_status
      },
      confidence: 1.0,
      rationale: override_reason?.trim() || 'Manager approved case after review'
    });

    res.json(mcp.invoke('fetchCase', { id: req.params.id }));
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

export default router;
