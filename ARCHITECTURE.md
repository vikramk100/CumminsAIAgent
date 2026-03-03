# Software Architecture

High-level structure of the Cummins AI Agent: backend API, agentic dispatcher, ML pipeline, data scripts, and SAP UI5 frontend.

---

## Overview

```
CumminsAIAgent/
├── api/                    # FastAPI backend
│   ├── main.py             # App entry, CORS, /api/predictions, /api/predict, /api/triggerWorkOrder
│   ├── criticality.py      # confidence + severity → criticality (0–3)
│   ├── dispatch_agent.py   # Agentic flow: tools + LLM → Mission Briefing
│   ├── agent_tools.py      # get_ml_prediction, query_manuals, get_historical_fixes
│   └── v1/
│       └── router.py       # GET /api/v1/dispatch-brief/{orderId}, POST /api/v1/audit-trail
├── scripts/                # Data & ML scripts (Python)
├── schemas/                # Mongoose schemas (Node) for reference
├── models/                 # Trained model (e.g. failure_classifier.joblib)
├── webapp/                 # SAP UI5 frontend (ObjectPageLayout, dispatch briefing)
└── tests/                  # Pytest (ML, tools, API)
```

---

## Backend (Python / FastAPI)

- **Entry:** `uvicorn api.main:app --reload` (default port 8000).
- **CORS:** Allow all origins for local/dev.
- **Environment:** `.env` (from `.env.example`): `MONGODB_URI`, `MONGODB_PASSWORD`, `MONGODB_DB`, `OPENAI_API_KEY`, `OPENAI_MODEL`.

### API surface

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/predictions` | GET | Fiori-style `d.results`; $top, $skip, $filter (equipmentId); ML prediction + criticality, suggestedOperation, manualReference |
| `/api/predict` | POST | Single prediction from telemetry body |
| `/api/triggerWorkOrder` | POST | Create work order in MongoDB from prediction |
| `/api/v1/dispatch-brief/{orderId}` | GET | Agentic Mission Briefing (root_cause_analysis, required_tools, estimated_repair_time, manual_reference_snippet) |
| `/api/v1/audit-trail` | POST | Persist tool/step audit events to `audit_trail` |

### Agentic flow

- **dispatch_agent.py:** Loads work order + equipment; calls **agent_tools** (ML prediction, manuals search, historical fixes); uses OpenAI to produce Mission Briefing JSON.
- **agent_tools.py:** `get_ml_prediction(machine_id)`, `query_manuals(fault_code)`, `get_historical_fixes(system_affected)`; shared MongoDB connection.

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

---

## Frontend (SAP UI5)

- **Location:** `webapp/` (sap_horizon theme; libs: sap.m, sap.uxap, sap.ui.layout).
- **Entry:** `index.html` → `init.js` → Component + Main view.
- **Main view:** ObjectPageLayout — header (EquipmentID, FailureLabel, ObjectStatus by criticality, ProgressIndicator for confidence); Insights (root_cause_analysis); Preparation (required_tools with checkboxes); Documentation (manual_reference_snippet).
- **Controller:** Loads GET `/api/v1/dispatch-brief/{orderId}`; POST `/api/v1/audit-trail` on tool check. API base configurable via `?apiBase=...` and `?orderId=...` (default `http://localhost:8000`).
- **Serve:** `npm start` (UI5 tooling) or any static server pointing at `webapp/`.

---

## Tests

- **Pytest:** `tests/conftest.py` adds project root to `sys.path`. `tests/test_ml_and_agent.py`: `predict_failure`, manual-query extraction, MongoDB reuse. Run: `pytest -q` from project root with venv. OpenAI key optional (fallback/skip when missing).

---

## External / Config

- **MongoDB:** Atlas (or other); connection string and DB name from env.
- **OpenAI:** Used only for agentic briefing (`OPENAI_API_KEY`, `OPENAI_MODEL`).
- **Node:** Optional for Mongoose schemas; UI5 uses `npm` for tooling only.
