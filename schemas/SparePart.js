const mongoose = require('mongoose');

/**
 * SparePart Schema
 * Master catalog of spare parts with availability and pricing.
 * Used for AI-recommended parts based on historical fixes.
 */
const sparePartSchema = new mongoose.Schema(
  {
    partId: { type: String, required: true, unique: true, index: true },
    partNumber: { type: String, required: true, index: true }, // OEM part number
    name: { type: String, required: true },
    category: {
      type: String,
      required: true,
      enum: ['Gaskets', 'Filters', 'Sensors', 'Belts', 'Hoses', 'Electrical', 'Bearings', 'Seals', 'Valves', 'Pumps', 'Other'],
      index: true
    },
    description: { type: String },
    engineModels: [{ type: String }], // Compatible engine models e.g., ["X15", "ISX15", "B6.7"]
    availability: {
      type: String,
      required: true,
      enum: ['in_stock', 'low_stock', 'out_of_stock'],
      default: 'in_stock',
      index: true
    },
    quantity: { type: Number, default: 0, min: 0 },
    unitPrice: { type: Number, default: 0, min: 0 }, // Price in USD
    location: { type: String }, // e.g., "Parts Bay B-5"
    leadTimeDays: { type: Number, default: 0 }, // Days to restock if out
    createdAt: { type: Date, default: Date.now },
    updatedAt: { type: Date, default: Date.now },
  },
  { timestamps: true }
);

module.exports = mongoose.model('SparePart', sparePartSchema);
