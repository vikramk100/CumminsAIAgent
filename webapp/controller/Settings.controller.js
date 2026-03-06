sap.ui.define(["sap/ui/core/mvc/Controller", "sap/m/MessageToast"], function (Controller, MessageToast) {
  "use strict";

  return Controller.extend("cummins.dispatcher.controller.Settings", {
    _getDefaultApiBase: function () {
      // Use relative URLs in production, localhost:8000 for local dev
      var host = window.location.hostname;
      if (host === "localhost" || host === "127.0.0.1") {
        return "http://localhost:8000";
      }
      return window.location.origin; // Show full origin for clarity in settings
    },

    onInit: function () {
      var saved = localStorage.getItem("apiBase") || this._getDefaultApiBase();
      this.getView().byId("apiBaseInput").setValue(saved);
    },

    onNavBack: function () {
      this.getOwnerComponent().getRouter().navTo("launchpad");
    },

    onSaveApiBase: function () {
      var val = this.getView().byId("apiBaseInput").getValue().trim();
      if (!val) {
        MessageToast.show("Please enter a valid URL.");
        return;
      }
      localStorage.setItem("apiBase", val);
      MessageToast.show("API Base URL saved.");
    },

    onTestConnection: function () {
      var val = this.getView().byId("apiBaseInput").getValue().trim() || this._getDefaultApiBase();
      var oStatus = this.getView().byId("connectionStatus");
      oStatus.setText("Testing…");
      fetch(val + "/health")
        .then(function (r) {
          if (r.ok) {
            oStatus.setText("✔ Connection successful (" + r.status + ")");
          } else {
            oStatus.setText("⚠ Server responded with status " + r.status);
          }
        })
        .catch(function () {
          oStatus.setText("✘ Could not reach " + val);
        });
    },

    onPageSizeChange: function () {
      var val = this.getView().byId("pageSize").getSelectedKey();
      localStorage.setItem("pageSize", val);
      MessageToast.show("Page size set to " + val + ".");
    },

    onDefaultStatusChange: function () {
      var val = this.getView().byId("defaultStatus").getSelectedKey();
      localStorage.setItem("defaultStatus", val);
    }
  });
});
