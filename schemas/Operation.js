const mongoose = require('mongoose');

const operationSchema = new mongoose.Schema(
  {
    orderId: { type: String, required: true, index: true }, // FK to WorkOrder
    operationId: { type: String, required: true, index: true },
    status: {
      type: String,
      required: true,
      enum: ['Pending', 'In Progress', 'Completed', 'Cancelled'],
      default: 'Pending',
    },
    priority: { type: Number, min: 1, max: 5, default: 3 },
    equipmentId: { type: String, required: true, index: true },
    actualWork: { type: Number, default: 0 },
    description: { type: String },
    diagnostic_steps: { type: String },
    resolution: { type: String },
    sequence: { type: Number, default: 0 },
    createdAt: { type: Date, default: Date.now },
    updatedAt: { type: Date, default: Date.now },
  },
  { timestamps: true }
);

operationSchema.index({ orderId: 1, operationId: 1 }, { unique: true });

module.exports = mongoose.model('Operation', operationSchema);
