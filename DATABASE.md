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

---

## Key Relationships

- **WorkOrder and MachineLog:** `WorkOrder.equipmentId` = `MachineLog.MachineID`
- **WorkOrder to Operations / Confirmations:** `Operation.orderId`, `Confirmation.orderId` reference `WorkOrder.orderId`
- **ML / API:** Predictions use latest `machinelogs` per equipment; `diagnostics` and `manuals` drive suggested operations and manual references.

---

## Schema Overview (Mongoose / API usage)

### workorders
- `orderId` (unique), `status` (Created, Released, In Progress, Completed, Cancelled), `priority`, `equipmentId`, `actualWork`, `orderDate`, timestamps. Optional: `triggeredFromPrediction`, `predictedFailure`, `faultCode`, `suggestedOperation`.

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
