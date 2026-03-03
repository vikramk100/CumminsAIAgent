sap.ui.define(["sap/ui/core/ComponentContainer"], function (ComponentContainer) {
  "use strict";

  new ComponentContainer({
    name: "cummins.dispatcher",
    settings: {
      id: "dispatcher",
    },
    async: true,
  }).placeAt("content");
});

