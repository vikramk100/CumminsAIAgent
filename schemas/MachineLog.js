const mongoose = require('mongoose');

/**
 * Replicates schema from pgurazada1/machine-failure-logs.
 * Links to SAP BNAC via MachineID <-> WorkOrder.equipmentId
 */
const machineLogSchema = new mongoose.Schema(
  {
    MachineID: { type: String, required: true, index: true },
    Tool_ID: { type: String, index: true },
    Process_Temperature: { type: Number }, // K or °C depending on source
    Air_Temperature: { type: Number },
    Rotational_Speed: { type: Number }, // rpm
    Torque: { type: Number }, // Nm
    Tool_Wear: { type: Number }, // minutes
    Failure_Type: {
      type: String,
      index: true,
      // Typical values: No Failure, Tool Wear Failure, Heat Dissipation Failure,
      // Power Failure, Overstrain Failure, Random Failures, High Tool Wear
    },
    symptom: { type: String },
    failure_label: { type: String, index: true }, // ML target: e.g. fault_code + severity
    Machine_failure: { type: Number, min: 0, max: 1 },
    logTimestamp: { type: Date, default: Date.now, index: true },
    createdAt: { type: Date, default: Date.now },
  },
  { timestamps: true }
);

machineLogSchema.index({ MachineID: 1, logTimestamp: -1 });

module.exports = mongoose.model('MachineLog', machineLogSchema);
