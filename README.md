# Cummins AI Agent – SAP BNAC + Machine Logs

MongoDB schema and data pipeline that replicates an SAP BNAC environment integrated with external machine failure logs. Features **multi-agent AI orchestration** for intelligent work order dispatch briefings.

- **[Database summary](DATABASE.md)** – Collections, relationships, and schema overview.
- **[Software architecture](ARCHITECTURE.md)** – Backend, ML pipeline, scripts, and UI5 frontend.

---

## Quick Start

### Local Development

```bash
# 1. Clone and setup
git clone <repo-url>
cd CumminsAIAgent

# 2. Backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # Configure MongoDB and GCP credentials
uvicorn api.main:app --reload  # http://localhost:8000

# 3. Frontend
npm install
npm start  # http://localhost:8083/index.html
```

### Production (GCP Cloud Run)

The application auto-deploys to GCP Cloud Run on every push to `main`:

| Service | URL |
|---------|-----|
| **Backend API** | `https://cummins-ai-agent-XXXXX-uc.a.run.app` |
| **API Docs** | `https://cummins-ai-agent-XXXXX-uc.a.run.app/docs` |

---

## How to run locally

### 1. Clone and set up environment

```bash
git clone <repo-url>
cd CumminsAIAgent
```

### 2. Python backend (API + ML)

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

### 2.1 Configure `.env` (MongoDB + GCP Vertex AI)

Copy `.env.example` to `.env` (never commit `.env` to git) and set:

- **MongoDB connection**
  - Either use the placeholder form and a separate password:

    ```env
    MONGODB_URI=mongodb+srv://sankethrp_db_user:<db_password>@workorderandconfirmatio.gfkc6h6.mongodb.net/?appName=WorkOrderAndConfirmations
    MONGODB_PASSWORD=YOUR_ATLAS_PASSWORD
    MONGODB_DB=sap_bnac
    ```

    The backend replaces `<db_password>` with `MONGODB_PASSWORD` at runtime.

  - Or put the password directly in the URI (then `MONGODB_PASSWORD` is optional):

    ```env
    MONGODB_URI=mongodb+srv://sankethrp_db_user:YOUR_ATLAS_PASSWORD@workorderandconfirmatio.gfkc6h6.mongodb.net/sap_bnac?retryWrites=true&w=majority
    MONGODB_DB=sap_bnac
    ```

- **GCP Vertex AI (for multi-agent dispatch briefing)**

  ```env
  GCP_PROJECT_ID=workorderaiagent
  GCP_REGION=us-central1
  GOOGLE_APPLICATION_CREDENTIALS=D:\path\to\service-account.json
  VERTEX_MODEL=gemini-2.0-flash-001
  ```

  Create a service account in GCP Console with Vertex AI permissions and download the JSON key. The system uses GCP Vertex AI with LangChain for the multi-agent orchestration.

- **Legacy Gemini (optional, for backward compatibility)**

  ```env
  GEMINI_API_KEY=your_gemini_api_key
  GEMINI_MODEL=gemini-2.0-flash
  ```

  Get an API key at [Google AI Studio](https://aistudio.google.com/apikey). The legacy `dispatch_agent.py` can still use this if Vertex AI is not configured.

Start the API:

```bash
uvicorn api.main:app --reload
```

API runs at **http://localhost:8000**. Docs: http://localhost:8000/docs.

### 3. (Optional) Load data into MongoDB

Run from project root with venv active:

```bash
python scripts/load_and_insert_mongodb.py
python scripts/load_manuals_mongodb.py
python scripts/integrate_vehicle_diagnostics_mongodb.py
```

For ML predictions, extract and train once:

```bash
python scripts/extract_ml_dataset.py -o data/ml_dataset.csv
python scripts/train_failure_classifier.py
```

### 4. SAP UI5 frontend (Work Orders + Dispatcher)

```bash
npm install
npm start
```

The UI5 dev server will start at: **http://localhost:8083/index.html**

#### 4.1 Launchpad → Work Orders / Equipments

- Open the URL in a browser.
- You will see a **Launchpad** with two **Fiori-style tiles**: **“Work Orders and Confirmations”** and **“Equipments”**.
- **Work Orders:** Click the Work Orders tile to open the Work Orders page:
  - A **table** of work orders with columns (Work Order, Equipment, Status, Priority, Actual Work, Confirmations).
  - A **filter bar** above the table:
    - Status filter (Created / Released / In Progress / Completed / Cancelled)
    - Priority filter (1–5)
    - Search by Work Order ID or Equipment ID
    - Reset button to clear all filters.
  - **Confirmations:** Expand a row to see confirmations in an in-row panel; **click the row** to open the work order detail page.
- **Equipments:** Click the Equipments tile to open a table of equipments (Equipment ID, Engine Model, Criticality).

#### 4.2 Work order detail (dispatcher view)

- Click a row in the Work Orders table to navigate to the **dispatcher detail page** for that order.
- The detail page shows:
  - **Work Order overview**: order ID, equipment, status, priority, technician, days to resolve.
  - **Issue & equipment details**: issue description and a telemetry snapshot (temperatures, speed, torque, tool wear).
  - **Insights**: AI-generated mission briefing (root cause, tools, estimated repair time).
  - **Documentation**: manual reference snippet.
  - **Timeline**: chronological list of operations, confirmations, and tool checklist events.

By default, the UI5 app talks to the backend at `http://localhost:8000`. You can override this by passing `?apiBase=http://your-api-host:port` in the URL if needed.

### 5. Run tests

Tests use **real MongoDB**. The test run uses a separate database so production data is never touched: database name is `sap_bnac_test` (override with `MONGODB_DB_TEST`). Ensure `MONGODB_URI` and `MONGODB_PASSWORD` (if needed) are set in `.env`, then:

```bash
pytest -q
```

### 6. Demo Work Orders

Create realistic demo work orders for presentation:

```bash
python scripts/create_demo_work_orders.py
```

This creates 5 detailed work orders with full telemetry, diagnostics, operations, and confirmations:

| Order ID | Scenario |
|----------|----------|
| WO-DEMO-001 | Highway breakdown - Gasket failure |
| WO-DEMO-002 | Data center generator emergency |
| WO-DEMO-003 | Municipal bus cooling system failure |
| WO-DEMO-004 | Combine harvester - Harvest emergency |
| WO-DEMO-005 | Concrete pump - Project deadline |

---

## Deploy to GCP Cloud Run

### Prerequisites

1. Install [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
2. Authenticate: `gcloud auth login`
3. Set project: `gcloud config set project workorderaiagent`

### Manual Deployment

```bash
# Enable required APIs
gcloud services enable cloudbuild.googleapis.com run.googleapis.com secretmanager.googleapis.com aiplatform.googleapis.com

# Create secrets (first time only)
echo "YOUR_MONGODB_PASSWORD" | gcloud secrets create mongodb-password --data-file=-
echo "YOUR_FULL_MONGODB_URI" | gcloud secrets create mongodb-uri --data-file=-

# Deploy
gcloud builds submit --config cloudbuild.yaml --substitutions=COMMIT_SHA=latest
```

### CI/CD (Automatic Deployment)

Every push to `main` triggers automatic deployment via Cloud Build. Set up the trigger:

```bash
gcloud builds triggers create github \
  --repo-name=CumminsAIAgent \
  --repo-owner=YOUR_GITHUB_USERNAME \
  --branch-pattern=^main$ \
  --build-config=cloudbuild.yaml
```

Or use the GCP Console: **Cloud Build → Triggers → Create Trigger**

---

## Data model (the bridge)

| SAP BNAC | External logs | Link |
|----------|----------------|------|
| **WorkOrders** (orderId, status, priority, equipmentId, actualWork, orderDate) | **MachineLogs** (MachineID, Tool_ID, Process_Temperature, Air_Temperature, Rotational_Speed, Torque, Tool_Wear, Failure_Type) | `equipmentId` ↔ `MachineID` |
| **Operations** (per work order) | | `orderId` → WorkOrder |
| **Confirmations** (confirmationText, actualWork) | | `orderId` → WorkOrder |

- Every **Completed** WorkOrder has at least one MachineLog with **Failure** or **High Tool Wear** shortly before `orderDate` (generated by the script).

## Mongoose schemas (Node)

- `schemas/WorkOrder.js` – SAP work order
- `schemas/Operation.js` – SAP operation
- `schemas/Confirmation.js` – SAP confirmation
- `schemas/MachineLog.js` – Machine log (aligned with pgurazada1/machine-failure-logs)
- `schemas/Manual.js` – Manual chunks (engine manuals from Cummins Document Library)
- `schemas/Diagnostic.js` – Diagnostics (fault_code, symptoms, system_affected, resolution) for ML/API

```bash
npm install mongoose
# Use: const { WorkOrder, Operation, Confirmation, MachineLog, Manual, Diagnostic } = require('./schemas');
```

## Python: load dataset and insert into MongoDB

1. **Create a virtualenv and install dependencies**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   pip install -r requirements.txt
   ```

2. **Set MongoDB password** (do not commit `.env`)
   - Copy `.env.example` to `.env`
   - Set `MONGODB_PASSWORD=your_password`
   - Or: `set MONGODB_PASSWORD=jpFU2ln7w0Ygd7vB` (Windows) before running

3. **Run the script**
   ```bash
   cd scripts
   python load_and_insert_mongodb.py
   ```

   The script will:
   - Load **pgurazada1/machine-failure-logs** via Hugging Face `datasets`
   - Normalize columns to MachineID, Tool_ID, Process_Temperature, Air_Temperature, Rotational_Speed, Torque, Tool_Wear, Failure_Type
   - Select “unstable” machines (those with failure/high-tool-wear flags)
   - Generate synthetic SAP WorkOrders (default 2500), Operations, and Confirmations linked to those machines
   - Ensure a subset of Completed WorkOrders have a corresponding MachineLog (Failure or High Tool Wear) shortly before `orderDate`
   - Insert all MachineLogs and SAP documents into your MongoDB cluster

4. **Optional: clear collections before insert**
   ```bash
   set CLEAR_COLLECTIONS=1
   python load_and_insert_mongodb.py
   ```

## MongoDB collections

See **[DATABASE.md](DATABASE.md)** for the full database summary. In short:

- `workorders` – SAP work orders
- `operations` – SAP operations
- `confirmations` – SAP confirmations  
- `machinelogs` – External machine logs (dataset + synthetic “before order” logs)
- `manuals` – Engine manual text chunks (X15, B6.7, ISB) from Cummins Document Library PDFs
- `diagnostics` – Vehicle diagnostics (fault codes, symptoms, resolution)
- `audit_trail` – UI audit events (e.g. tool checklist)
- `insight_feedback` – Thumbs up/down on AI insights for model improvement; export with `python scripts/export_insight_feedback.py`

Database name: `sap_bnac` (override with `MONGODB_DB`).

## Manuals collection (engine PDFs)

`scripts/load_manuals_mongodb.py` scrapes the Cummins Document Library for PDFs (X15, B6.7, ISB), extracts text with PyMuPDF, and stores 500-word chunks (50-word overlap) in `manuals`. Schema: `manualId`, `engineModel`, `section`, `content`, `pageNumber`, `metadata` (url, version). Run with `CLEAR_MANUALS=1` to clear first; optional `CUMMINS_SEED_PDF_URLS` for extra PDF URLs.

## ML failure classification and SAP-style API

- **Extract:** `python scripts/extract_ml_dataset.py -o data/ml_dataset.csv` – flattens MachineLogs + engineModel to CSV.
- **Train:** `python scripts/train_failure_classifier.py` (or add `xgb` for XGBoost). Saves `models/failure_classifier.joblib`. Use `predict_failure(telemetry_data)` → (failure_label, confidence).
- **API:** `uvicorn api.main:app --reload`. GET `/api/predictions` returns Fiori-style `d.results` with criticality, confidence, suggestedOperation, manualReference; supports `$top`, `$skip`, `$filter`. GET `/api/v1/equipments` and GET `/api/v1/workorders` list equipments and work orders. GET `/api/v1/dispatch-brief/{orderId}` returns the agentic mission briefing and work order detail (overview, telemetry, timeline). POST `/api/predict` for single prediction; POST `/api/triggerWorkOrder` to create a WorkOrder from a prediction; POST `/api/v1/audit-trail` to persist tool checklist events.
