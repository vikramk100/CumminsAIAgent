sap.ui.define([], function () {
  "use strict";

  function _escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  return {
    criticalityFrom: function (failureLabel, confidence) {
      const c = Number(confidence || 0);
      if (!failureLabel || failureLabel === "No_Failure") {
        return c >= 0.5 ? 3 : 0;
      }
      if (c >= 0.85) return 1;
      if (c >= 0.6) return 2;
      return 0;
    },

    criticalityText: function (criticality) {
      switch (Number(criticality)) {
        case 1:
          return "Error";
        case 2:
          return "Warning";
        case 3:
          return "Success";
        default:
          return "Information";
      }
    },

    criticalityState: function (criticality) {
      // sap.m.ObjectStatus state
      switch (Number(criticality)) {
        case 1:
          return "Error";
        case 2:
          return "Warning";
        case 3:
          return "Success";
        default:
          return "Information";
      }
    },

    confidencePercent: function (confidence) {
      const c = Math.max(0, Math.min(1, Number(confidence || 0)));
      return Math.round(c * 100);
    },

    confidenceDisplay: function (confidence) {
      const p = this.confidencePercent(confidence);
      return p + "%";
    },

    snippetToHtml: function (snippet) {
      const safe = _escapeHtml(snippet || "").replace(/\n/g, "<br/>");
      return "<div style='white-space:normal'>" + safe + "</div>";
    }
  };
});

