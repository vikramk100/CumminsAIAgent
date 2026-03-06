sap.ui.define(["sap/ui/core/mvc/Controller", "sap/m/MessageToast", "sap/m/MessageBox"], function (Controller, MessageToast, MessageBox) {
  "use strict";

  return Controller.extend("cummins.dispatcher.controller.SupportCenter", {
    onNavBack: function () {
      this.getOwnerComponent().getRouter().navTo("launchpad");
    },

    onSubmitTicket: function () {
      var oView = this.getView();
      var subject = oView.byId("ticketSubject").getValue().trim();
      var desc = oView.byId("ticketDescription").getValue().trim();
      var category = oView.byId("ticketCategory").getSelectedKey();

      if (!subject || !desc) {
        MessageToast.show("Please fill in Subject and Description.");
        return;
      }

      MessageBox.success(
        "Your support ticket has been submitted.\n\nCategory: " + category + "\nSubject: " + subject + "\n\nYou will receive a confirmation email shortly.",
        {
          title: "Ticket Submitted",
          onClose: function () {
            oView.byId("ticketSubject").setValue("");
            oView.byId("ticketDescription").setValue("");
          }
        }
      );
    },

    onRefreshStatus: function () {
      var sBase = localStorage.getItem("apiBase") || "http://localhost:8000";
      var oLabel = this.getView().byId("statusLastChecked");
      oLabel.setText("Checking…");

      fetch(sBase + "/health")
        .then(function (r) {
          var now = new Date().toLocaleTimeString();
          if (r.ok) {
            oLabel.setText(now + " — all systems operational");
          } else {
            oLabel.setText(now + " — backend returned " + r.status);
          }
        })
        .catch(function () {
          oLabel.setText(new Date().toLocaleTimeString() + " — backend unreachable");
        });
    }
  });
});
