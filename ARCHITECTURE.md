# Software Architecture

High-level structure of the Cummins AI Agent: backend API, agentic dispatcher, ML pipeline, data scripts, and SAP UI5 frontend.

---

## Overview

```
CumminsAIAgent/
├── api/                        # FastAPI backend
│   ├── main.py                 # App entry, CORS, /api/predictions, /api/predict, /api/triggerWorkOrder
│   ├── criticality.py         # confidence + severity → criticality (0–3)
│   ├── dispatch_agent.py      # Agentic flow: build_context_package, work_order_detail, Mission Briefing
│   ├── agent_tools.py         # get_ml_prediction, query_manuals, get_historical_fixes
│   └── v1/
│       └── router.py          # GET /api/v1/equipments, /api/v1/workorders, /api/v1/dispatch-brief/{orderId}, POST /api/v1/audit-trail
├── scripts/                    # Data & ML scripts (Python)
├── schemas/                    # Mongoose schemas (Node) for reference
├── models/                     # Trained model (e.g. failure_classifier.joblib)
├── webapp/                     # SAP UI5 frontend (routed app: Launchpad → Work Orders / Equipments → Detail)
│   ├── Component.js            # Root component; models: dispatch, wo; router.initialize()
│   ├── init.js                 # ComponentContainer loads cummins.dispatcher
│   ├── manifest.json          # Root view: App; routing: launchpad, workorders, workorders/{orderId}, equipments
│   ├── view/
│   │   ├── App.view.xml       # Shell: Bar "SAP - Business Network Portal" + App (pages)
│   │   ├── Launchpad.view.xml # Tiles: Work Orders and Confirmations, Equipments
│   │   ├── WorkOrders.view.xml# Table with filters; per-row expandable confirmations; row → detail
│   │   ├── Equipments.view.xml# Equipment list (equipmentId, engineModel, criticality)
│   │   └── Main.view.xml      # Work order detail: ObjectPageLayout (overview, telemetry, insights, timeline)
│   └── controller/            # App, Launchpad, WorkOrders, Equipments, Main
└── tests/                      # Pytest (ML, tools, API)
```

---

## Backend (Python / FastAPI)

- **Entry:** `uvicorn api.main:app --reload` (default port 8000).
- **CORS:** Allow all origins for local/dev.
- **Environment:** `.env` (from `.env.example`): `MONGODB_URI`, `MONGODB_PASSWORD`, `MONGODB_DB`, `GEMINI_API_KEY`, `GEMINI_MODEL`.

### API surface

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/predictions` | GET | Fiori-style `d.results`; $top, $skip, $filter (equipmentId); ML prediction + criticality, suggestedOperation, manualReference |
| `/api/predict` | POST | Single prediction from telemetry body |
| `/api/triggerWorkOrder` | POST | Create work order in MongoDB from prediction |
| `/api/v1/equipments` | GET | List distinct equipments (equipmentId, engineModel, criticalityText, criticalityState); optional `limit` |
| `/api/v1/workorders` | GET | List work orders with embedded confirmations; optional `limit` |
| `/api/v1/dispatch-brief/{orderId}` | GET | Agentic Mission Briefing + work order detail (orderId, status, equipmentId, daysToSolve, issueDescription, technician, operations, confirmations, timeline, telemetry) |
| `/api/v1/audit-trail` | POST | Persist tool/step audit events to `audit_trail` |
| `/api/v1/chat` | POST | Chat Q&A about work order/equipment; returns answer + thought_process (for model improvement) |
| `/api/v1/insight-feedback` | POST | Persist thumbs up/down on AI insights → `insight_feedback` for fine-tuning / RLHF |

### Agentic flow

- **dispatch_agent.py:** Loads work order + equipment; builds extended context (operations, confirmations, audit_trail); computes daysToSolve, issueDescription, technician, timeline; builds **work_order_detail**; calls **agent_tools** (ML prediction, manuals search, historical fixes); uses **Google Gemini** to produce Mission Briefing JSON. Response includes `context_summary`, `work_order_detail`, `mission_briefing`.
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
- **Serve:** `npm start` (UI5 tooling); app often available at `http://localhost:8080/index.html` or `http://localhost:8080/webapp/index.html`.

---

## Tests

- **Pytest:** `tests/conftest.py` adds project root to `sys.path`. `tests/test_ml_and_agent.py`: `predict_failure`, manual-query extraction, MongoDB reuse. Run: `pytest -q` from project root with venv. Gemini key optional (fallback/skip when missing).

---

## External / Config

- **MongoDB:** Atlas (or other); connection string and DB name from env. No schema changes; see DATABASE.md for collections.
- **Gemini:** Used only for agentic briefing (`GEMINI_API_KEY`, `GEMINI_MODEL`). Free tier available via Google AI Studio.
- **Node:** Optional for Mongoose schemas; UI5 uses `npm` for tooling only.
