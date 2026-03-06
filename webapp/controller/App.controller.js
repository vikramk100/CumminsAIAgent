sap.ui.define(["sap/ui/core/mvc/Controller"], function (Controller) {
  "use strict";

  return Controller.extend("cummins.dispatcher.controller.App", {
    onNavNotifications: function () {
      this.getOwnerComponent().getRouter().navTo("notifications");
    },
    onNavHelp: function () {
      this.getOwnerComponent().getRouter().navTo("help");
    },
    onNavSettings: function () {
      this.getOwnerComponent().getRouter().navTo("settings");
    },
    onNavUserProfile: function () {
      this.getOwnerComponent().getRouter().navTo("userProfile");
    },
    onNavSupportCenter: function () {
      this.getOwnerComponent().getRouter().navTo("supportCenter");
    }
  });
});
