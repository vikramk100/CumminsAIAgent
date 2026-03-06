const mongoose = require('mongoose');

/**
 * PrepOrder Schema
 * Orders placed by technicians for tools and spare parts.
 * Tracks the checkout/order workflow.
 */
const prepOrderItemSchema = new mongoose.Schema({
  itemType: {
    type: String,
    required: true,
    enum: ['tool', 'spare_part']
  },
  itemId: { type: String, required: true }, // toolId or partId
  name: { type: String, required: true },
  quantity: { type: Number, required: true, default: 1, min: 1 },
  unitPrice: { type: Number, default: 0 }, // For spare parts
  status: {
    type: String,
    enum: ['requested', 'picked', 'returned', 'cancelled'],
    default: 'requested'
  }
}, { _id: false });

const prepOrderSchema = new mongoose.Schema(
  {
    prepOrderId: { type: String, required: true, unique: true, index: true },
    workOrderId: { type: String, required: true, index: true }, // Links to work order
    orderDate: { type: Date, default: Date.now, index: true },
    status: {
      type: String,
      required: true,
      enum: ['pending', 'approved', 'fulfilled', 'cancelled'],
      default: 'pending',
      index: true
    },
    items: [prepOrderItemSchema],
    technicianId: { type: String }, // Optional technician identifier
    technicianName: { type: String },
    totalAmount: { type: Number, default: 0 }, // Total for spare parts
    notes: { type: String },
    createdAt: { type: Date, default: Date.now },
    updatedAt: { type: Date, default: Date.now },
  },
  { timestamps: true }
);

module.exports = mongoose.model('PrepOrder', prepOrderSchema);
