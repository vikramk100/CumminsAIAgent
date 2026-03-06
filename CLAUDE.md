# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend (Python / FastAPI)
```bash
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
pip install -r requirements.txt

uvicorn api.main:app --reload    # http://localhost:8000, docs at /docs
```

### Frontend (SAP UI5)
```bash
npm install
npm start                        # http://localhost:8083/index.html
```

### Tests
```bash
pytest -q                        # Runs all tests against sap_bnac_test database
pytest tests/test_ml_and_agent.py -q   # Single test file
```
Tests use real MongoDB on a separate `sap_bnac_test` database (override with `MONGODB_DB_TEST`). Requires `MONGODB_URI` and `MONGODB_PASSWORD` in `.env`.

### ML Pipeline
```bash
python scripts/extract_ml_dataset.py -o data/ml_dataset.csv
python scripts/train_failure_classifier.py      # outputs models/failure_classifier.joblib
```

### Data Loading
```bash
python scripts/load_and_insert_mongodb.py       # MachineLogs + synthetic SAP work orders
python scripts/load_manuals_mongodb.py          # Cummins PDF manual chunks
python scripts/integrate_vehicle_diagnostics_mongodb.py
python scripts/create_demo_work_orders.py       # 5 demo orders for presentation
```

## Environment Setup

Copy `.env.example` to `.env`. Key variables:
- `MONGODB_URI` / `MONGODB_PASSWORD` — Atlas connection (URI uses `<db_password>` placeholder replaced at runtime)
- `MONGODB_DB` — default `sap_bnac`
- `GCP_PROJECT_ID`, `GCP_REGION`, `GOOGLE_APPLICATION_CREDENTIALS`, `VERTEX_MODEL` — Vertex AI (`gemini-2.0-flash-001`)
- `GEMINI_API_KEY` — legacy, used only by `dispatch_agent.py` if Vertex AI is not configured

## Architecture

### System Components

```
Browser → SAP UI5 (webapp/, port 8083)
            ↓ HTTP
FastAPI (api/, port 8000)
  ├── /api/predictions         # OData-style ML predictions
  ├── /api/v1/dispatch-brief   # Multi-agent briefing (main AI feature)
  ├── /api/v1/workorders       # CRUD
  ├── /api/v1/chat             # Chat Q&A
  └── /api/v1/...              # Other endpoints
            ↓
OrchestratorAgent → DiagnosticAgent + PrescriptionAgent
                              ↓
                    MCP Server (api/mcp_server.py)
                              ↓
                    MongoDB Atlas (sap_bnac)
```

### Multi-Agent System (critical)

The `/api/v1/dispatch-brief/{orderId}` endpoint drives the core AI feature:

1. **OrchestratorAgent** (`api/agents/orchestrator.py`) — delegates to sub-agents, synthesizes Mission Briefing JSON
2. **DiagnosticAgent** (`api/agents/diagnostic_agent.py`) — ML predictions, telemetry analysis, fault code lookup
3. **PrescriptionAgent** (`api/agents/prescription_agent.py`) — manual search, historical fixes, tool-kit list
4. **MCP Server** (`api/mcp_server.py`) — all MongoDB queries are wrapped as FastMCP tools; agents never query DB directly
5. **LLM Client** (`api/llm_client.py`) — GCP Vertex AI via `langchain-google-vertexai`; `get_llm_for_agents()` is the entry point

Agents communicate through LangChain message passing. The response includes an `agent_trace` showing which sub-agents and MCP tools were invoked.

### MCP Pattern (important)

`api/mcp_server.py` is the single point of database access for agents. Tools: `get_work_order`, `get_ml_prediction`, `query_manuals`, `get_historical_fixes`, `get_diagnostic_info`, `get_operations_for_order`, `get_confirmations_for_order`, `get_audit_trail`, and several historical/similarity tools. When adding new data retrieval, add an MCP tool here rather than querying MongoDB directly in agent code.

### ML Prediction

`scripts/train_failure_classifier.py` exports `predict_failure(telemetry_data)` → `(failure_label, confidence)`. The API lazy-loads this at runtime via `sys.path` injection from `api/main.py`. Trained model is saved to `models/failure_classifier.joblib`.

### Frontend (SAP UI5)

Located in `webapp/`. Uses SAP UI5 MVC with hash-based routing. Routes: `Launchpad` → `WorkOrders` → `WorkOrderDetail` (view: `Main`), `Equipments`. The Work Order Detail view (`webapp/controller/Main.controller.js`) calls `GET /api/v1/dispatch-brief/{orderId}` and binds the result to display telemetry, the AI mission briefing, tool checklists (audited via POST `/api/v1/audit-trail`), and thumbs-up/down feedback (POST `/api/v1/insight-feedback`).

The API base URL defaults to `http://localhost:8000` and can be overridden with `?apiBase=...` query param or `localStorage`.

### Legacy Files

- `api/dispatch_agent.py` — original monolithic agent, kept for reference; replaced by the multi-agent system
- `api/agent_tools.py` — direct MongoDB queries, superseded by `api/mcp_server.py`
- `backend/` and `frontend/` — separate Express+React prototype; not the active codebase (active = FastAPI + UI5)

## Deployment

**GCP Cloud Run** (production): every push to `main` triggers `cloudbuild.yaml`.

```bash
# Manual deploy
gcloud builds submit --config cloudbuild.yaml --substitutions=COMMIT_SHA=latest
```

Secrets stored in GCP Secret Manager: `mongodb-password`, `mongodb-uri`.
