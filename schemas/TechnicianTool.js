const mongoose = require('mongoose');

/**
 * TechnicianTool Schema
 * Master catalog of tools available for technicians.
 * Includes availability status for color-coded display.
 */
const technicianToolSchema = new mongoose.Schema(
  {
    toolId: { type: String, required: true, unique: true, index: true },
    name: { type: String, required: true },
    category: { 
      type: String, 
      required: true,
      enum: ['Hand Tools', 'Power Tools', 'Diagnostic', 'Specialty', 'Safety', 'Lifting'],
      index: true 
    },
    description: { type: String },
    availability: {
      type: String,
      required: true,
      enum: ['in_stock', 'low_stock', 'out_of_stock'],
      default: 'in_stock',
      index: true
    },
    quantity: { type: Number, default: 0, min: 0 },
    location: { type: String }, // e.g., "Tool Bay A-12"
    engineModels: [{ type: String }], // Compatible engine models
    createdAt: { type: Date, default: Date.now },
    updatedAt: { type: Date, default: Date.now },
  },
  { timestamps: true }
);

module.exports = mongoose.model('TechnicianTool', technicianToolSchema);
