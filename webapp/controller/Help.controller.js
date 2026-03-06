sap.ui.define(["sap/ui/core/mvc/Controller"], function (Controller) {
  "use strict";

  return Controller.extend("cummins.dispatcher.controller.Help", {
    onNavBack: function () {
      this.getOwnerComponent().getRouter().navTo("launchpad");
    }
  });
});
