const mongoose = require('mongoose');

const confirmationSchema = new mongoose.Schema(
  {
    orderId: { type: String, required: true, index: true }, // FK to WorkOrder
    confirmationId: { type: String, required: true, index: true },
    confirmationText: { type: String, required: true },
    status: {
      type: String,
      enum: ['Draft', 'Submitted', 'Approved'],
      default: 'Submitted',
    },
    equipmentId: { type: String, index: true },
    actualWork: { type: Number, default: 0 },
    confirmedAt: { type: Date, default: Date.now },
    createdAt: { type: Date, default: Date.now },
    updatedAt: { type: Date, default: Date.now },
  },
  { timestamps: true }
);

confirmationSchema.index({ orderId: 1, confirmationId: 1 }, { unique: true });

module.exports = mongoose.model('Confirmation', confirmationSchema);
