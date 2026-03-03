const mongoose = require('mongoose');

/**
 * Manuals collection: chunked engine manual content from Cummins Document Library.
 * Links to engine models (e.g. X15, B6.7, ISB); content is 500-word chunks with overlap.
 */
const manualSchema = new mongoose.Schema(
  {
    manualId: { type: String, required: true, unique: true, index: true },
    engineModel: { type: String, required: true, index: true },
    section: { type: String, required: true, index: true },
    content: { type: String, required: true },
    pageNumber: { type: Number, required: true, index: true },
    metadata: {
      url: { type: String },
      version: { type: String },
    },
  },
  { timestamps: true }
);

manualSchema.index({ engineModel: 1, section: 1 });

module.exports = mongoose.model('Manual', manualSchema);
