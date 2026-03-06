sap.ui.define(["sap/ui/core/mvc/Controller"], function (Controller) {
  "use strict";

  return Controller.extend("cummins.dispatcher.controller.Launchpad", {
    onInit: function () {
      var sBase = localStorage.getItem("apiBase") || "http://localhost:8000";
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
