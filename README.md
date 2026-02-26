# Cummins AI Diagnostic Agent

A minimal multi-agent enterprise AI MVP for engine fault diagnosis.

## System Architecture

```
Technician (Browser)
    │
    ▼
React Frontend (port 3000)
    │  POST /cases  multipart/form-data
    ▼
Express Backend (port 3001)
    │
    ▼
Orchestrator
    ├── 1. MCPServer.writeCaseRecord()       → SQLite Cases
    ├── 2. VisionFaultAgent.analyze()        → Ollama llava (multimodal)
    │       └── MCPServer.writeDecisionLog()
    ├── 3. RiskScoringAgent.score()          → deterministic rules
    │       └── MCPServer.writeDecisionLog()
    └── 4. RoutingAgent.route()              → deterministic threshold
            └── MCPServer.writeDecisionLog()

All DB writes go exclusively through MCPServer (MCP layer).
Agents never touch the database directly.
```

## Agent Responsibilities

| Agent | Type | Logic |
|-------|------|-------|
| VisionFaultAgent | Multimodal LLM | Calls Ollama llava with base64 image |
| RiskScoringAgent | Deterministic | CRITICAL→90, HIGH→75, MEDIUM→40, LOW→20 |
| RoutingAgent | Deterministic | risk_score > 70 → MANAGER_REVIEW |

## Prerequisites

- Node.js 18+
- [Ollama](https://ollama.ai) installed and running

## Quick Start

### 1. Install Ollama

```bash
# macOS
brew install ollama

# Or download from https://ollama.ai
```

### 2. Pull the multimodal model

```bash
ollama pull llava
```

> If `llava` is unavailable, try `ollama pull llama3.2-vision` and update
> `MODEL` in `backend/src/agents/VisionFaultAgent.js` accordingly.

### 3. Start Ollama

```bash
ollama serve
# Runs on http://localhost:11434
```

### 4. Install and start the backend

```bash
cd backend
npm install
npm run dev
# Runs on http://localhost:3001
```

### 5. Install and start the frontend

```bash
cd frontend
npm install
npm run dev
# Runs on http://localhost:3000
```

### 6. Open the app

Navigate to **http://localhost:3000**

## Usage

### Technician View
1. Click "Technician" tab
2. Upload an engine component image (JPG/PNG/WEBP)
3. Add observation notes (optional but improves accuracy)
4. Click "Submit for Analysis"
5. View fault category, severity, risk score, routing decision, and full agent timeline

### Manager View
1. Click "Manager Review" tab
2. Cases with risk score > 70 appear here
3. Click a case to inspect the full audit trail
4. Choose "Approve" or "Override" (override requires a written reason)
5. All decisions are logged via MCP and persisted to SQLite

## Database

SQLite file is created automatically at `backend/data/cases.db`

**Cases table**: id, image_path, raw_description, visible_damage, fault_category, severity, risk_score, route, final_status, created_at

**DecisionLogs table**: id, case_id, agent_name, input_summary, output_json, confidence, rationale, timestamp

## Project Structure

```
├── backend/
│   ├── src/
│   │   ├── server.js
│   │   ├── db/
│   │   │   ├── database.js        # SQLite connection
│   │   │   └── setup.js           # Schema init
│   │   ├── mcp/
│   │   │   └── MCPServer.js       # MCP tool layer — all DB access
│   │   ├── agents/
│   │   │   ├── VisionFaultAgent.js
│   │   │   ├── RiskScoringAgent.js
│   │   │   └── RoutingAgent.js
│   │   ├── orchestrator/
│   │   │   └── orchestrator.js
│   │   └── routes/
│   │       └── cases.js
│   ├── data/                      # SQLite DB (auto-created)
│   ├── uploads/                   # Uploaded images
│   └── package.json
│
└── frontend/
    ├── src/
    │   ├── App.jsx
    │   ├── App.css
    │   ├── main.jsx
    │   └── components/
    │       ├── TechnicianView.jsx
    │       ├── ManagerView.jsx
    │       └── CaseTimeline.jsx
    ├── index.html
    ├── vite.config.js
    └── package.json
```

## Configuration

| Setting | Location | Default |
|---------|----------|---------|
| Ollama model | `backend/src/agents/VisionFaultAgent.js` | `llava` |
| Ollama URL | `backend/src/agents/VisionFaultAgent.js` | `http://localhost:11434` |
| Backend port | `backend/src/server.js` | `3001` |
| Frontend port | `frontend/vite.config.js` | `3000` |
| Routing threshold | `backend/src/agents/RoutingAgent.js` | `70` |
