# Database Summary

MongoDB database **`sap_bnac`** (configurable via `MONGODB_DB`) holds SAP BNAC–style work orders, operations, confirmations, machine logs, engine manuals, diagnostics, and audit events.

---

## Collections

| Collection       | Purpose |
|------------------|---------|
| `workorders`     | SAP work orders (orderId, status, equipmentId, orderDate, etc.) |
| `operations`     | Operations per work order; optionally enriched with diagnostic_steps/resolution |
| `confirmations`  | Confirmations per work order (confirmationText, actualWork) |
| `machinelogs`    | Telemetry/failure logs; linked to work orders via MachineID and equipmentId |
| `manuals`        | Chunked engine manual content (X15, B6.7, ISB) from Cummins Document Library |
| `diagnostics`    | Vehicle/engine diagnostics (fault_code, symptoms, system_affected, resolution) |
| `audit_trail`    | Audit events from the UI (e.g. tool-kit checkboxes) for dispatch briefing |
| `insight_feedback` | User ratings (thumbs up/down) on AI insights for model improvement (fine-tuning / RLHF) |

---

## Demo Work Orders

For presentation/testing, run `python scripts/create_demo_work_orders.py` to create 5 detailed work orders:

| Order ID | Equipment | Engine | Fault Code | Status | Description |
|----------|-----------|--------|------------|--------|-------------|
| WO-DEMO-001 | TRUCK-X15-001 | X15 | P0300_S3 | Completed | Highway breakdown - Gasket failure (3 confirmations) |
| WO-DEMO-002 | GEN-X15-DC01 | X15 | TWF_S3 | Completed | Data center generator emergency (2 confirmations) |
| WO-DEMO-003 | BUS-B67-015 | B6.7 | HDF_S2 | In Progress | Municipal bus cooling system failure (2 confirmations) |
| WO-DEMO-004 | HARVEST-ISB-007 | ISB | PWF_S3 | In Progress | Combine harvester - Harvest season (2 confirmations) |
| WO-DEMO-005 | PUMP-X15-003 | X15 | RNF_S2 | Released | Concrete pump - Project deadline (0 confirmations) |

Each demo work order includes:
- Detailed customer complaint narrative
- Telematics data and fault codes
- Machine logs showing telemetry progression to failure
- Diagnostics with resolution steps and required tools
- Operations with planned vs actual durations
- Confirmations documenting the repair journey

---

## Key Relationships

- **WorkOrder and MachineLog:** `WorkOrder.equipmentId` = `MachineLog.MachineID`
- **WorkOrder to Operations / Confirmations:** `Operation.orderId`, `Confirmation.orderId` reference `WorkOrder.orderId`
- **ML / API:** Predictions use latest `machinelogs` per equipment; `diagnostics` and `manuals` drive suggested operations and manual references.

---

## Schema Overview (Mongoose / API usage)

### workorders
- `orderId` (unique), `status` (Created, Released, In Progress, Completed, Cancelled), `priority`, `equipmentId`, `actualWork`, `orderDate`, timestamps. Optional: `triggeredFromPrediction`, `predictedFailure`, `faultCode`, `suggestedOperation`, `issueDescription` (user-entered issue text for ML category suggestion), `selectedCategories` (array of category labels chosen from ML suggestions).

### operations
- `orderId`, `operationId`, `status`, `equipmentId`, `actualWork`, `description`, `sequence`. Enriched: `diagnostic_steps`, `resolution`.

### confirmations
- `orderId`, `confirmationId`, `confirmationText`, `status`, `equipmentId`, `actualWork`, `confirmedAt`.

### machinelogs
- `MachineID`, `Tool_ID`, `Process_Temperature`, `Air_Temperature`, `Rotational_Speed`, `Torque`, `Tool_Wear`, `Failure_Type`, `logTimestamp`. Enriched: `symptom`, `failure_label` (ML target). Optional: `Machine_failure`.

### manuals
- `manualId`, `engineModel`, `section`, `content` (500-word chunks, 50-word overlap), `pageNumber`, `metadata` (url, version).

### diagnostics
- `fault_code`, `symptoms`, `system_affected`, `resolution`, `diagnostic_steps`, `severity`, `source_text`.

### audit_trail
- `orderId`, `equipmentId`, `toolName`, `checked`, `userId` (optional), `source`, `timestamp`. Written by POST `/api/v1/audit-trail`.

### insight_feedback
- `orderId`, `equipmentId` (optional), `rating` ("up" | "down"), `source` (e.g. "thought_process"), `feedbackText` (the content that was rated), `rootCauseAnalysis` (insight text), `userId` (optional), `timestamp`. Written by POST `/api/v1/insight-feedback`. Export with `scripts/export_insight_feedback.py` for fine-tuning or RLHF.

---

## Mongoose Schemas (Node)

Defined under `schemas/` for reference and optional Node usage:

- `schemas/WorkOrder.js`
- `schemas/Operation.js`
- `schemas/Confirmation.js`
- `schemas/MachineLog.js`
- `schemas/Manual.js`
- `schemas/Diagnostic.js`

Use: `const { WorkOrder, Operation, Confirmation, MachineLog, Manual, Diagnostic } = require('./schemas');` after `npm install mongoose`.

---

## Data Loading Scripts (Python)

| Script | Collections populated |
|--------|------------------------|
| `scripts/load_and_insert_mongodb.py` | `machinelogs`, `workorders`, `operations`, `confirmations` (from pgurazada1/machine-failure-logs plus synthetic SAP data) |
| `scripts/load_manuals_mongodb.py`    | `manuals` (Cummins PDFs to chunks) |
| `scripts/integrate_vehicle_diagnostics_mongodb.py` | `diagnostics`; enriches `operations` and `machinelogs` |

`audit_trail` is written only by the API when the UI posts audit events.
