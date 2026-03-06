# Software Architecture

High-level structure of the Cummins AI Agent: backend API, multi-agent dispatcher, MCP server, ML pipeline, data scripts, and SAP UI5 frontend.

---

## Overview

```
CumminsAIAgent/
├── api/                        # FastAPI backend
│   ├── main.py                 # App entry, CORS, health check, /api/predictions, /api/predict
│   ├── criticality.py          # confidence + severity → criticality (0–3)
│   ├── llm_client.py           # GCP Vertex AI LLM client (replaces Gemini API key)
│   ├── mcp_server.py           # Model Context Protocol server (FastMCP) - MongoDB tools
│   ├── agents/                 # Multi-Agent System
│   │   ├── __init__.py         # Package exports
│   │   ├── base.py             # MCP tool wrappers as LangChain tools
│   │   ├── orchestrator.py     # Primary Orchestrator Agent
│   │   ├── diagnostic_agent.py # Sub-agent 1: ML predictions & telemetry
│   │   └── prescription_agent.py # Sub-agent 2: Manuals & historical fixes
│   ├── dispatch_agent.py       # [LEGACY] Original monolithic agent (kept for reference)
│   ├── agent_tools.py          # [LEGACY] Direct MongoDB queries (now in mcp_server.py)
│   └── v1/
│       └── router.py           # GET /api/v1/equipments, /api/v1/workorders, etc.
├── scripts/                    # Data & ML scripts (Python)
│   └── create_demo_work_orders.py  # Creates 5 demo work orders for presentation
├── schemas/                    # Mongoose schemas (Node) for reference
├── models/                     # Trained model (e.g. failure_classifier.joblib)
├── webapp/                     # SAP UI5 frontend
├── tests/                      # Pytest (ML, tools, API)
├── Dockerfile                  # Container image for Cloud Run deployment
├── cloudbuild.yaml             # Cloud Build CI/CD configuration
└── deploy-gcp.ps1              # PowerShell deployment script
```

---

## Deployment

### Local Development
- **Backend:** `uvicorn api.main:app --reload` (port 8000)
- **Frontend:** `npm start` (port 8083)
- **URLs:** http://localhost:8000/docs (API), http://localhost:8083/index.html (UI)

### GCP Cloud Run (Production)

The application is deployed to **Google Cloud Run** with automatic CI/CD:

| Component | Service | URL |
|-----------|---------|-----|
| Backend API | Cloud Run | `https://cummins-ai-agent-XXXXX-uc.a.run.app` |
| Frontend | Cloud Storage | `https://storage.googleapis.com/workorderaiagent-frontend/index.html` |
| LLM | Vertex AI | `gemini-2.0-flash-001` in `us-central1` |
| Database | MongoDB Atlas | Cloud-hosted cluster |

### CI/CD Pipeline

Every push to `main` branch triggers automatic deployment via **Cloud Build**:

```
GitHub (main) → Cloud Build → Docker Build → Container Registry → Cloud Run
```

Configuration: `cloudbuild.yaml`

---

## Backend (Python / FastAPI)

- **Entry:** `uvicorn api.main:app --reload` (default port 8000).
- **CORS:** Allow all origins for local/dev.
- **Environment:** `.env` (from `.env.example`): `MONGODB_URI`, `MONGODB_PASSWORD`, `MONGODB_DB`, `GCP_PROJECT_ID`, `GCP_REGION`, `GOOGLE_APPLICATION_CREDENTIALS`, `VERTEX_MODEL`.

### API surface

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/predictions` | GET | Fiori-style `d.results`; $top, $skip, $filter (equipmentId); ML prediction + criticality, suggestedOperation, manualReference |
| `/api/predict` | POST | Single prediction from telemetry body |
| `/api/triggerWorkOrder` | POST | Create work order in MongoDB from prediction |
| `/api/v1/equipments` | GET | List distinct equipments (equipmentId, engineModel, criticalityText, criticalityState); optional `limit` |
| `/api/v1/workorders` | GET | List work orders with embedded confirmations; optional `limit` |
| `/api/v1/dispatch-brief/{orderId}` | GET | **Multi-Agent** Mission Briefing + work order detail (includes `agent_trace` showing orchestrator, sub-agents, MCP tools used) |
| `/api/v1/audit-trail` | POST | Persist tool/step audit events to `audit_trail` |
| `/api/v1/chat` | POST | Chat Q&A about work order/equipment; returns answer + thought_process (for model improvement) |
| `/api/v1/insight-feedback` | POST | Persist thumbs up/down on AI insights → `insight_feedback` for fine-tuning / RLHF |

---

## Multi-Agent Architecture

The system uses a **multi-agent orchestration pattern** to meet challenge rubric requirements:

### Agent Hierarchy

```
┌─────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR AGENT                        │
│  (api/agents/orchestrator.py)                               │
│  - Receives /dispatch-brief/{orderId} requests              │
│  - Delegates to sub-agents                                  │
│  - Synthesizes final Mission Briefing JSON                  │
└─────────────────────┬───────────────────────────────────────┘
                      │
          ┌───────────┴───────────┐
          │                       │
          ▼                       ▼
┌─────────────────────┐ ┌─────────────────────┐
│  DIAGNOSTIC AGENT   │ │  PRESCRIPTION AGENT │
│  (Sub-agent 1)      │ │  (Sub-agent 2)      │
│                     │ │                     │
│  - ML predictions   │ │  - Manual search    │
│  - Telemetry data   │ │  - Historical fixes │
│  - Fault codes      │ │  - Tool-kit list    │
│  - System affected  │ │  - Repair time      │
└─────────────────────┘ └─────────────────────┘
          │                       │
          └───────────┬───────────┘
                      │
                      ▼
         ┌────────────────────────┐
         │      MCP SERVER        │
         │  (api/mcp_server.py)   │
         │                        │
         │  MongoDB Tools:        │
         │  - get_work_order      │
         │  - get_ml_prediction   │
         │  - query_manuals       │
         │  - get_historical_fixes│
         │  - get_diagnostic_info │
         │  - get_operations      │
         │  - get_confirmations   │
         │  - get_audit_trail     │
         └────────────────────────┘
```

### Components

| Component | File | Responsibility |
|-----------|------|----------------|
| **Orchestrator Agent** | `api/agents/orchestrator.py` | Coordinates sub-agents, builds work_order_detail, synthesizes mission_briefing |
| **Diagnostic Agent** | `api/agents/diagnostic_agent.py` | Invokes MCP tools for ML predictions, telemetry analysis, fault code lookup |
| **Prescription Agent** | `api/agents/prescription_agent.py` | Invokes MCP tools to search manuals, historical fixes, builds tool-kit list |
| **MCP Server** | `api/mcp_server.py` | FastMCP server exposing MongoDB queries as structured tools |
| **LLM Client** | `api/llm_client.py` | GCP Vertex AI integration via LangChain |

### Response Structure

The `/api/v1/dispatch-brief/{orderId}` endpoint returns:

```json
{
  "orderId": "WO-12501",
  "context_summary": { "equipmentId": "1", "failure_label": "HDF", "confidence": 0.85 },
  "work_order": { "status": "CRTD", "priority": "2", "equipmentId": "1" },
  "work_order_detail": { /* full detail with timeline, telemetry */ },
  "ml_prediction": { "failure_label": "HDF", "confidence": 0.85, "fault_code": "HDF" },
  "mission_briefing": {
    "root_cause_analysis": "...",
    "required_tools": ["Torque Wrench", "Multimeter", "..."],
    "estimated_repair_time": 75,
    "manual_reference_snippet": "...",
    "thought_process": "..."
  },
  "agent_trace": {
    "orchestrator": "OrchestratorAgent",
    "sub_agents_invoked": ["DiagnosticAgent", "PrescriptionAgent"],
    "mcp_tools_used": ["get_work_order", "get_ml_prediction", "query_manuals", "..."]
  }
}
```

---

## Model Context Protocol (MCP) Server

The MCP server (`api/mcp_server.py`) wraps all MongoDB database interactions as structured tools using **FastMCP**. Agents do not query the database directly; they invoke MCP tools.

### MCP Tools

| Tool | Description |
|------|-------------|
| `get_work_order(order_id)` | Retrieve work order by ID |
| `get_machine_log(machine_id)` | Get latest telemetry for equipment |
| `get_ml_prediction(machine_id)` | Run ML failure prediction |
| `query_manuals(fault_code, engine_model, limit)` | Search engine manuals |
| `get_historical_fixes(system_affected, limit)` | Search past repairs |
| `get_diagnostic_info(fault_code)` | Get diagnostic details |
| `get_operations_for_order(order_id)` | Get operations for work order |
| `get_confirmations_for_order(order_id)` | Get confirmations for work order |
| `get_audit_trail(order_id)` | Get audit events |
| `get_engine_models()` | List available engine models |
| `list_work_orders(limit, status_filter)` | List work orders |
| `get_work_orders_for_equipment(equipment_id)` | Get all work orders for an equipment (historical) |
| `count_issues_for_equipment(equipment_id)` | Statistics on issues per equipment |
| `find_similar_issues(issue_keywords)` | Find work orders with similar descriptions |
| `get_equipment_maintenance_history(equipment_id)` | Full maintenance history + telemetry trends |
| `count_similar_issues(issue_keywords)` | Count occurrences across all equipment |

---

## GCP Vertex AI Integration

The system uses **Google Cloud Platform Vertex AI** instead of a local Gemini API key.

### Configuration

```env
GCP_PROJECT_ID=workorderaiagent
GCP_REGION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
VERTEX_MODEL=gemini-2.0-flash-001
```

### LLM Client (`api/llm_client.py`)

- Uses `langchain-google-vertexai` for LangChain compatibility
- Provides `get_vertex_client()` for agent use
- Supports both agent workflows and direct generation

---

## ML Pipeline

- **Extract:** `scripts/extract_ml_dataset.py` → CSV (machinelogs + engineModel).
- **Train:** `scripts/train_failure_classifier.py` → `models/failure_classifier.joblib` (RandomForest or XGBoost, SMOTE, StandardScaler). Exposes `predict_failure(telemetry_data)` → (failure_label, confidence).
- **Runtime:** API and agent call into the same `predict_failure` (via script path or packaged module).

---

## Data Scripts (Python)

- **load_and_insert_mongodb.py:** Hugging Face machine-failure-logs → synthetic work orders, operations, confirmations; insert into `machinelogs`, `workorders`, `operations`, `confirmations`.
- **load_manuals_mongodb.py:** Scrape Cummins PDFs, PyMuPDF extract, chunk → `manuals`.
- **integrate_vehicle_diagnostics_mongodb.py:** Load CJJones/Vehicle_Diagnostics_LLM_Training_Sample → `diagnostics`; enrich `operations` and `machinelogs`.

Run from project root with venv active; optional env: `CLEAR_COLLECTIONS`, `CLEAR_MANUALS`.

- **export_insight_feedback.py:** Export `insight_feedback` collection to JSONL (or JSON) for model improvement. Usage: `python scripts/export_insight_feedback.py -o data/insight_feedback.jsonl`; optional `--rating up|down`, `--format jsonl|json`. Use the exported file for fine-tuning or RLHF pipelines (e.g. pair feedbackText/rootCauseAnalysis with rating as preference signal).

---

## Model improvement (insight feedback)

- **Flow:** In the Work Order detail page, users see "Show Thought Process" and rate the AI insight with thumbs up or thumbs down. The UI sends POST `/api/v1/insight-feedback` with `orderId`, `equipmentId`, `rating` ("up" | "down"), `source` ("thought_process"), `feedbackText` (the thought_process content), and `rootCauseAnalysis` (the insight text). Stored in MongoDB collection **insight_feedback**.
- **Export:** Run `python scripts/export_insight_feedback.py` to produce `data/insight_feedback.jsonl` (one JSON object per line). Each record contains the rated content and the rating, suitable for building preference datasets for fine-tuning or reinforcement learning from human feedback (RLHF).
- **DATABASE.md:** See `insight_feedback` collection schema.

---

## Frontend (SAP UI5)

- **Location:** `webapp/` (sap_horizon theme; libs: sap.m, sap.uxap, sap.ui.layout, sap.ui.layout.form).
- **Entry:** `index.html` → `init.js` → ComponentContainer → **App** view (root). App view: top **Bar** titled "SAP - Business Network Portal" with dummy links (Notifications, Help, Settings, User Profile, Support Center); **App** control hosts routed pages.
- **Routing:** Hash-based. Targets: **Launchpad** (default), **WorkOrders**, **WorkOrderDetail** (view: Main), **Equipments**. Router config: `controlId="app"`, `controlAggregation="pages"`.
- **Launchpad:** Two tiles (Work Orders and Confirmations; Equipments). Tiles navigate to `workorders` and `equipments` routes.
- **Work Orders page:** Table of work orders (columns: Work Order, Equipment, Status, Priority, Actual Work, Confirmations). Toolbar: Status filter, Priority filter, Search, Reset. Each row has an expandable Confirmations panel; row press navigates to work order detail (`workorders/{orderId}`). Data: GET `/api/v1/workorders`.
- **Equipments page:** Table of equipments (Equipment ID, Engine Model, Latest Criticality); search. Data: GET `/api/v1/equipments`.
- **Work order detail (Main view):** ObjectPageLayout. Header: Equipment ID, Failure label, Risk level (ObjectStatus), Confidence (ProgressIndicator). Sections: **Work Order Overview** (SimpleForm: orderId, equipmentId, status, priority, technician, daysToSolve); **Issue & Equipment Details** (Issue Description text, Equipment Telemetry Snapshot: Process/Air temperature, Rotational Speed, Torque, Tool Wear); **Insights** (root_cause_analysis, "Talk to AI" button, "Show Thought Process" popup with thumbs up/down); **Preparation** (required_tools with checkboxes + same Talk to AI / Thought Process buttons; audit-trail); **Documentation** (manual_reference_snippet); **Timeline** (operations, confirmations, audit events). Thumbs up/down send feedback via POST `/api/v1/insight-feedback`. Data: GET `/api/v1/dispatch-brief/{orderId}`; controller normalizes `work_order_detail` and telemetry for binding; placeholder issue description when missing.
- **API base:** Configurable via `?apiBase=...` and `localStorage`; default `http://localhost:8000`.
- **Serve:** `npm start` (UI5 tooling); app available at `http://localhost:8083/index.html`.

---

## Demo Work Orders

For presentation purposes, 5 detailed demo work orders are available:

| Order ID | Equipment | Engine | Status | Scenario |
|----------|-----------|--------|--------|----------|
| WO-DEMO-001 | TRUCK-X15-001 | X15 | Completed | Highway breakdown - Gasket failure (two-trip inefficiency) |
| WO-DEMO-002 | GEN-X15-DC01 | X15 | Completed | Data center generator emergency (AI-assisted success) |
| WO-DEMO-003 | BUS-B67-015 | B6.7 | In Progress | Municipal bus cooling system failure |
| WO-DEMO-004 | HARVEST-ISB-007 | ISB | In Progress | Combine harvester - Harvest season emergency |
| WO-DEMO-005 | PUMP-X15-003 | X15 | Released | Concrete pump - Project deadline at risk |

Create demo data: `python scripts/create_demo_work_orders.py`

---

## Tests

- **Pytest:** `tests/conftest.py` adds project root to `sys.path`. `tests/test_ml_and_agent.py`: `predict_failure`, manual-query extraction, MongoDB reuse. Run: `pytest -q` from project root with venv. Gemini key optional (fallback/skip when missing).

---

## External / Config

- **MongoDB:** Atlas (or other); connection string and DB name from env. No schema changes; see DATABASE.md for collections.
- **Gemini:** Used only for agentic briefing (`GEMINI_API_KEY`, `GEMINI_MODEL`). Free tier available via Google AI Studio.
- **Node:** Optional for Mongoose schemas; UI5 uses `npm` for tooling only.
