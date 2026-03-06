sap.ui.define(["sap/ui/core/UIComponent", "sap/ui/model/json/JSONModel"], function (UIComponent, JSONModel) {
  "use strict";

  return UIComponent.extend("cummins.dispatcher.Component", {
    metadata: {
      manifest: "json",
    },

    init: function () {
      UIComponent.prototype.init.apply(this, arguments);

      // Model for the dispatch / mission briefing detail view
      const oDispatchModel = new JSONModel({
        loading: true,
        error: null,
        orderId: null,
        context_summary: {},
        mission_briefing: {},
        ui: {
          criticality: 0,
          criticalityText: "Information",
          confidencePercent: 0,
          confidenceDisplay: "0%",
          tools: [],
          manualSnippetHtml: "",
          chatLastAnswer: "",
          chatLastAnswerHtml: "<p><em>Ask a question about this work order and the AI will respond here.</em></p>",
          thoughtFeedback: null
        },
      });
      this.setModel(oDispatchModel, "dispatch");

      // Model for Work Orders + Confirmations overview
      const oWorkOrdersModel = new JSONModel({
        workOrders: [],
      });
      this.setModel(oWorkOrdersModel, "wo");

      // Initialize router for navigation between Launchpad, Work Orders list, and detail
      this.getRouter().initialize();
    },
  });
});

