const mongoose = require('mongoose');

const workOrderSchema = new mongoose.Schema(
  {
    orderId: { type: String, required: true, unique: true, index: true },
    status: {
      type: String,
      required: true,
      enum: ['Created', 'Released', 'In Progress', 'Completed', 'Cancelled'],
      index: true,
    },
    priority: { type: Number, required: true, min: 1, max: 5, default: 3 },
    equipmentId: { type: String, required: true, index: true }, // maps to MachineID in MachineLogs
    actualWork: { type: Number, default: 0 }, // e.g. hours or quantity
    orderDate: { type: Date, default: Date.now, index: true },
    createdAt: { type: Date, default: Date.now },
    updatedAt: { type: Date, default: Date.now },
  },
  { timestamps: true }
);

module.exports = mongoose.model('WorkOrder', workOrderSchema);
