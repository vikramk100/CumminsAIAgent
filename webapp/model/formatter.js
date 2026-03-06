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
      const c = Math.max(0, Math.min(1, Number(confidence || 0)));
      return Math.round(c * 100) + "%";
    },

    confidenceState: function (confidence) {
      const c = Number(confidence || 0);
      if (c >= 0.8) return "Success";
      if (c >= 0.6) return "Warning";
      return "Error";
    },

    arrayLength: function (arr) {
      return Array.isArray(arr) ? arr.length : 0;
    },

    snippetToHtml: function (snippet) {
      const safe = _escapeHtml(snippet || "").replace(/\n/g, "<br/>");
      return "<div style='white-space:normal'>" + safe + "</div>";
    },

    /**
     * Convert plain text to HTML with proper formatting.
     * Uses only FormattedText-allowed tags: a, abbr, blockquote, br, cite, 
     * code, em, h1-h6, p, pre, strong, span, u, ul, ol, li
     */
    textToHtml: function (text) {
      if (!text) return "<p><em>No content available</em></p>";
      
      let safe = _escapeHtml(text);
      
      // Convert markdown-style headers (h1-h6 are allowed)
      safe = safe.replace(/^### (.+)$/gm, "<h4>$1</h4>");
      safe = safe.replace(/^## (.+)$/gm, "<h3>$1</h3>");
      safe = safe.replace(/^# (.+)$/gm, "<h2>$1</h2>");
      
      // Convert markdown bold **text** (strong is allowed)
      safe = safe.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
      
      // Convert bullet points to list items (ul, li are allowed)
      safe = safe.replace(/^[\-\*•] (.+)$/gm, "<li>$1</li>");
      
      // Convert numbered lists
      safe = safe.replace(/^\d+\. (.+)$/gm, "<li>$1</li>");
      
      // Convert double newlines to paragraph breaks (p is allowed)
      safe = safe.replace(/\n\n/g, "</p><p>");
      
      // Convert single newlines to line breaks (br is allowed)
      safe = safe.replace(/\n/g, "<br>");
      
      return "<p>" + safe + "</p>";
    }
  };
});

