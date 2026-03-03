sap.ui.define(["sap/ui/core/UIComponent", "sap/ui/model/json/JSONModel"], function (UIComponent, JSONModel) {
  "use strict";

  return UIComponent.extend("cummins.dispatcher.Component", {
    metadata: {
      manifest: "json",
    },

    init: function () {
      UIComponent.prototype.init.apply(this, arguments);

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
        },
      });
      this.setModel(oDispatchModel, "dispatch");
    },
  });
});

