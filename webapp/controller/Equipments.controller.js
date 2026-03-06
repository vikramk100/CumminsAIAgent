sap.ui.define(
  [
    "sap/ui/core/mvc/Controller",
    "sap/ui/model/json/JSONModel",
    "sap/m/MessageToast",
    "sap/ui/model/Filter",
    "sap/ui/model/FilterOperator",
  ],
  function (Controller, JSONModel, MessageToast, Filter, FilterOperator) {
    "use strict";

    return Controller.extend("cummins.dispatcher.controller.Equipments", {
      onInit: function () {
        this._woModel = this.getOwnerComponent().getModel("wo");
        if (!this._woModel) {
          this._woModel = new JSONModel({
            equipments: [],
          });
          this.getOwnerComponent().setModel(this._woModel, "wo");
        }
        this._loadEquipments();
      },

      _getApiBase: function () {
        var params = new URLSearchParams(window.location.search);
        var fromQuery = params.get("apiBase");
        if (fromQuery) {
          return fromQuery.replace(/\/+$/, "");
        }
        var fromStorage = window.localStorage.getItem("API_BASE");
        if (fromStorage) {
          return fromStorage.replace(/\/+$/, "");
        }
        // Use relative URLs in production, localhost:8000 for local dev
        var host = window.location.hostname;
        if (host === "localhost" || host === "127.0.0.1") {
          return "http://localhost:8000";
        }
        return ""; // Relative URLs for production (same origin)
      },

      _loadEquipments: async function () {
        var base = this._getApiBase();
        try {
          var res = await fetch(base + "/api/v1/equipments", {
            method: "GET",
            headers: { Accept: "application/json" },
          });
          if (!res.ok) {
            var t = await res.text();
            throw new Error("API error " + res.status + ": " + t);
          }
          var data = await res.json();
          this._woModel.setProperty("/equipments", data.results || []);
        } catch (e) {
          // eslint-disable-next-line no-console
          console.error("Failed to load equipments", e);
          MessageToast.show("Failed to load equipments.");
        }
      },

      onSearch: function (oEvent) {
        var sQuery =
          oEvent.getParameter("query") || oEvent.getParameter("newValue") || "";
        var oTable = this.byId("EquipmentsTable");
        if (!oTable) {
          return;
        }
        var aFilters = [];
        if (sQuery) {
          aFilters.push(
            new Filter("equipmentId", FilterOperator.Contains, sQuery)
          );
        }
        var oBinding = oTable.getBinding("items");
        if (oBinding) {
          oBinding.filter(aFilters);
        }
      },

      onNavBack: function () {
        this.getOwnerComponent().getRouter().navTo("launchpad");
      },
    });
  }
);

