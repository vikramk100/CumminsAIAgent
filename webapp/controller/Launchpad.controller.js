sap.ui.define(["sap/ui/core/mvc/Controller"], function (Controller) {
  "use strict";

  return Controller.extend("cummins.dispatcher.controller.Launchpad", {
    _getApiBase: function () {
      var fromStorage = localStorage.getItem("apiBase");
      if (fromStorage) return fromStorage.replace(/\/+$/, "");
      // Use relative URLs in production, localhost:8000 for local dev
      var host = window.location.hostname;
      if (host === "localhost" || host === "127.0.0.1") {
        return "http://localhost:8000";
      }
      return ""; // Relative URLs for production (same origin)
    },

    onInit: function () {
      var sBase = this._getApiBase();
      var oView = this.getView();

      fetch(sBase + "/api/v1/workorders?limit=5000")
        .then(function (r) { return r.json(); })
        .then(function (data) {
          var count = Array.isArray(data) ? data.length : (data.results ? data.results.length : "—");
          oView.byId("kpiWoCount").setValue(String(count));
        })
        .catch(function () { oView.byId("kpiWoCount").setValue("—"); });

      fetch(sBase + "/api/v1/equipments?limit=5000")
        .then(function (r) { return r.json(); })
        .then(function (data) {
          var count = Array.isArray(data) ? data.length : "—";
          oView.byId("kpiEqCount").setValue(String(count));
        })
        .catch(function () { oView.byId("kpiEqCount").setValue("—"); });
    },

    onNavToWorkOrders: function () {
      this.getOwnerComponent().getRouter().navTo("workOrders");
    },

    onNavToEquipments: function () {
      this.getOwnerComponent().getRouter().navTo("equipments");
    },

    onNavToNotifications: function () {
      this.getOwnerComponent().getRouter().navTo("notifications");
    },

    onNavToSettings: function () {
      this.getOwnerComponent().getRouter().navTo("settings");
    }
  });
});
