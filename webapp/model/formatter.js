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
    },

    /**
     * Convert plain text to HTML with proper formatting.
     * Handles newlines, bullet points, and numbered lists.
     */
    textToHtml: function (text) {
      if (!text) return "<span style='color:#666;font-style:italic'>No content available</span>";
      
      let safe = _escapeHtml(text);
      
      // Convert markdown-style headers
      safe = safe.replace(/^### (.+)$/gm, "<h4 style='margin:12px 0 6px 0;color:#0854a0'>$1</h4>");
      safe = safe.replace(/^## (.+)$/gm, "<h3 style='margin:14px 0 8px 0;color:#0854a0'>$1</h3>");
      safe = safe.replace(/^# (.+)$/gm, "<h2 style='margin:16px 0 10px 0;color:#0854a0'>$1</h2>");
      
      // Convert markdown bold **text**
      safe = safe.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
      
      // Convert bullet points (- or * at start of line)
      safe = safe.replace(/^[\-\*] (.+)$/gm, "<li style='margin-left:16px;margin-bottom:4px'>$1</li>");
      
      // Convert numbered lists (1. 2. etc)
      safe = safe.replace(/^\d+\. (.+)$/gm, "<li style='margin-left:16px;margin-bottom:4px;list-style-type:decimal'>$1</li>");
      
      // Convert double newlines to paragraph breaks
      safe = safe.replace(/\n\n/g, "</p><p style='margin:8px 0'>");
      
      // Convert single newlines to line breaks
      safe = safe.replace(/\n/g, "<br/>");
      
      return "<div style='line-height:1.5;font-size:14px'><p style='margin:0'>" + safe + "</p></div>";
    }
  };
});

