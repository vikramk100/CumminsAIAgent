sap.ui.define(["sap/ui/core/mvc/Controller"], function (Controller) {
  "use strict";

  return Controller.extend("cummins.dispatcher.controller.Launchpad", {
    onNavToWorkOrders: function () {
      this.getOwnerComponent().getRouter().navTo("workOrders");
    },
  });
});

