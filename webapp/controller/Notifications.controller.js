sap.ui.define(["sap/ui/core/mvc/Controller", "sap/m/MessageToast"], function (Controller, MessageToast) {
  "use strict";

  return Controller.extend("cummins.dispatcher.controller.Notifications", {
    onNavBack: function () {
      this.getOwnerComponent().getRouter().navTo("launchpad");
    },

    onMarkAllRead: function () {
      MessageToast.show("All notifications marked as read.");
    }
  });
});
