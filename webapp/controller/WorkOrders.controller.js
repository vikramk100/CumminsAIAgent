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

    return Controller.extend("cummins.dispatcher.controller.WorkOrders", {
      onInit: function () {
        this._woModel = this.getOwnerComponent().getModel("wo");
        if (!this._woModel) {
          this._woModel = new JSONModel({
            workOrders: [],
            selectedConfirmations: [],
            _search: "",
          });
          this.getOwnerComponent().setModel(this._woModel, "wo");
        }
        this._loadWorkOrders();
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
        return "http://localhost:8000";
      },

      _loadWorkOrders: async function () {
        var base = this._getApiBase();
        try {
          var res = await fetch(base + "/api/v1/workorders", {
            method: "GET",
            headers: { Accept: "application/json" },
          });
          if (!res.ok) {
            var t = await res.text();
            throw new Error("API error " + res.status + ": " + t);
          }
          var data = await res.json();
          var results = data.results || [];
          this._woModel.setData({
            workOrders: results,
            selectedConfirmations: [],
            _search: "",
          });
        } catch (e) {
          // eslint-disable-next-line no-console
          console.error("Failed to load work orders", e);
          MessageToast.show("Failed to load work orders.");
        }
      },

      onWorkOrderSelect: function (oEvent) {
        var oItem = oEvent.getParameter("listItem");
        if (!oItem) {
          return;
        }
        var oCtx = oItem.getBindingContext("wo");
        if (!oCtx) {
          return;
        }
        var orderId = oCtx.getProperty("orderId");
        var confirmations = oCtx.getProperty("confirmations") || [];

        // Update confirmations panel
        this._woModel.setProperty("/selectedConfirmations", confirmations);

        // Navigate to detail view
        if (orderId) {
          this.getOwnerComponent()
            .getRouter()
            .navTo("workOrderDetail", {
              orderId: orderId,
            });
        }
      },

      _applyFilters: function (sQuery) {
        var oTable = this.byId("WorkOrdersTable");
        if (!oTable) {
          return;
        }
        var aFilters = [];
        var sSearch =
          sQuery !== undefined && sQuery !== null
            ? sQuery
            : this._woModel.getProperty("/_search") || "";

        var oStatusSelect = this.byId("statusFilter");
        var oPrioritySelect = this.byId("priorityFilter");
        var sStatus = oStatusSelect ? oStatusSelect.getSelectedKey() : "";
        var sPriority = oPrioritySelect ? oPrioritySelect.getSelectedKey() : "";

        if (sSearch) {
          var oFilter = new Filter({
            filters: [
              new Filter("orderId", FilterOperator.Contains, sSearch),
              new Filter("equipmentId", FilterOperator.Contains, sSearch),
            ],
            and: false,
          });
          aFilters.push(oFilter);
        }

        if (sStatus) {
          aFilters.push(new Filter("status", FilterOperator.EQ, sStatus));
        }

        if (sPriority) {
          aFilters.push(
            new Filter("priority", FilterOperator.EQ, parseInt(sPriority, 10))
          );
        }

        var oBinding = oTable.getBinding("items");
        if (oBinding) {
          oBinding.filter(aFilters);
        }
      },

      onSearch: function (oEvent) {
        var sQuery =
          oEvent.getParameter("query") || oEvent.getParameter("newValue") || "";
        this._woModel.setProperty("/_search", sQuery || "");
        this._applyFilters(sQuery || "");
      },

      onFilterChange: function () {
        this._applyFilters();
      },

      onClearFilters: function () {
        var oStatusSelect = this.byId("statusFilter");
        var oPrioritySelect = this.byId("priorityFilter");
        var oSearch = this.byId("WorkOrderSearch");

        if (oStatusSelect) {
          oStatusSelect.setSelectedKey("");
        }
        if (oPrioritySelect) {
          oPrioritySelect.setSelectedKey("");
        }
        if (oSearch) {
          oSearch.setValue("");
        }

        this._woModel.setProperty("/_search", "");
        this._applyFilters("");
      },

      onNavBack: function () {
        this.getOwnerComponent().getRouter().navTo("launchpad");
      },
    });
  }
);

