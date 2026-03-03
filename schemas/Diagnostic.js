const mongoose = require('mongoose');

/**
 * Vehicle/engine diagnostics from CJJones/Vehicle_Diagnostics_LLM_Training_Sample.
 * Used to enrich Operations and MachineLogs; failure_label links to ML target.
 */
const diagnosticSchema = new mongoose.Schema(
  {
    fault_code: { type: String, required: true, index: true },
    symptoms: { type: String, required: true },
    system_affected: { type: String, required: true, index: true },
    resolution: { type: String },
    diagnostic_steps: { type: String },
    severity: { type: Number, min: 1, max: 5 }, // 1=low, 5=critical; for ML target
    source_text: { type: String },
  },
  { timestamps: true }
);

diagnosticSchema.index({ system_affected: 1, fault_code: 1 });

module.exports = mongoose.model('Diagnostic', diagnosticSchema);
