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
      _selectedWorkOrder: null,

      onInit: function () {
        this._woModel = this.getOwnerComponent().getModel("wo");
        if (!this._woModel) {
          this._woModel = new JSONModel({
            workOrders: [],
            _search: "",
          });
          this.getOwnerComponent().setModel(this._woModel, "wo");
        }
        var createForm = new JSONModel({ suggestedCategories: [] });
        this.getView().setModel(createForm, "createForm");
        this._loadWorkOrders();
        this._setTableActionsEnabled(false);
      },

      _setTableActionsEnabled: function (enabled) {
        this.byId("btnEditWO")?.setEnabled(enabled);
        this.byId("btnDeleteWO")?.setEnabled(enabled);
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
            _search: "",
          });
        } catch (e) {
          // eslint-disable-next-line no-console
          console.error("Failed to load work orders", e);
          MessageToast.show("Failed to load work orders.");
        }
      },

      onWorkOrderPress: function (oEvent) {
        var oItem = oEvent.getSource();
        var oCtx = oItem.getBindingContext("wo");
        if (!oCtx) {
          return;
        }
        var orderId = oCtx.getProperty("orderId");
        if (orderId) {
          this.getOwnerComponent()
            .getRouter()
            .navTo("workOrderDetail", {
              orderId: orderId,
            });
        }
      },

      onWorkOrderSelectionChange: function (oEvent) {
        var oTable = oEvent.getSource();
        var oSelected = oTable.getSelectedItem();
        this._selectedWorkOrder = oSelected ? oSelected.getBindingContext("wo").getObject() : null;
        this._setTableActionsEnabled(!!this._selectedWorkOrder);
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

      onOpenCreateWorkOrder: function () {
        var dlg = this.byId("CreateWorkOrderDialog");
        if (dlg) {
          this.byId("CreateWO_equipmentId")?.setValue("");
          this.byId("CreateWO_issueDescription")?.setValue("");
          this.byId("CreateWO_status")?.setSelectedKey("Created");
          this.byId("CreateWO_priority")?.setSelectedKey("2");
          this.byId("CreateWO_actualWork")?.setValue("0");
          this.getView().getModel("createForm").setData({ suggestedCategories: [] });
          this.byId("CreateWO_categoriesList")?.setVisible(false);
          dlg.open();
        }
      },

      onSuggestCategories: async function () {
        var desc = (this.byId("CreateWO_issueDescription")?.getValue() || "").trim();
        if (!desc) {
          MessageToast.show("Please enter an issue description first.");
          return;
        }
        var base = this._getApiBase();
        try {
          var res = await fetch(base + "/api/v1/suggest-categories", {
            method: "POST",
            headers: { "Content-Type": "application/json", "Accept": "application/json" },
            body: JSON.stringify({ issueDescription: desc })
          });
          if (!res.ok) {
            var t = await res.text();
            throw new Error(t || "Suggest failed");
          }
          var data = await res.json();
          var suggestions = (data.suggestions || []).map(function (name) {
            return { name: name, selected: false };
          });
          this.getView().getModel("createForm").setData({ suggestedCategories: suggestions });
          this.byId("CreateWO_categoriesList")?.setVisible(suggestions.length > 0);
          MessageToast.show("Categories suggested. Select the ones that apply.");
        } catch (e) {
          // eslint-disable-next-line no-console
          console.error(e);
          MessageToast.show("Failed to suggest categories.");
        }
      },

      onCloseCreateWorkOrder: function () {
        var dlg = this.byId("CreateWorkOrderDialog");
        if (dlg) dlg.close();
      },

      onCreateWorkOrderSubmit: async function () {
        var equipmentId = (this.byId("CreateWO_equipmentId")?.getValue() || "").trim();
        if (!equipmentId) {
          MessageToast.show("Please enter Equipment ID.");
          return;
        }
        var issueDescription = (this.byId("CreateWO_issueDescription")?.getValue() || "").trim();
        if (!issueDescription) {
          MessageToast.show("Please enter an Issue Description.");
          return;
        }
        var createForm = this.getView().getModel("createForm");
        var suggestedCategories = createForm.getProperty("/suggestedCategories") || [];
        var selectedCategories = suggestedCategories
          .filter(function (c) { return c.selected; })
          .map(function (c) { return c.name; });
        var status = this.byId("CreateWO_status")?.getSelectedKey() || "Created";
        var priority = parseInt(this.byId("CreateWO_priority")?.getSelectedKey() || "2", 10);
        var actualWork = parseFloat(this.byId("CreateWO_actualWork")?.getValue() || "0") || 0;
        var base = this._getApiBase();
        try {
          var res = await fetch(base + "/api/v1/workorders", {
            method: "POST",
            headers: { "Content-Type": "application/json", "Accept": "application/json" },
            body: JSON.stringify({
              equipmentId: equipmentId,
              issueDescription: issueDescription,
              selectedCategories: selectedCategories.length ? selectedCategories : undefined,
              status: status,
              priority: priority,
              actualWork: actualWork
            })
          });
          if (!res.ok) {
            var t = await res.text();
            throw new Error(t || "Create failed");
          }
          var data = await res.json();
          this.byId("CreateWorkOrderDialog")?.close();
          MessageToast.show("Work order " + data.orderId + " created.");
          this._loadWorkOrders();
          this.getOwnerComponent().getRouter().navTo("workOrderDetail", { orderId: data.orderId });
        } catch (e) {
          // eslint-disable-next-line no-console
          console.error(e);
          MessageToast.show("Failed to create work order.");
        }
      },

      onEditWorkOrder: function () {
        if (!this._selectedWorkOrder || !this._selectedWorkOrder.orderId) {
          MessageToast.show("Please select a work order.");
          return;
        }
        var wo = this._selectedWorkOrder;
        this.byId("EditWO_equipmentId")?.setValue(wo.equipmentId || "");
        this.byId("EditWO_issueDescription")?.setValue(wo.issueDescription || "");
        this.byId("EditWO_status")?.setSelectedKey(wo.status || "Created");
        this.byId("EditWO_priority")?.setSelectedKey(String(wo.priority != null ? wo.priority : 2));
        this.byId("EditWO_actualWork")?.setValue(String(wo.actualWork != null ? wo.actualWork : 0));
        this.byId("EditWorkOrderDialog")?.open();
      },

      onCloseEditWorkOrder: function () {
        this.byId("EditWorkOrderDialog")?.close();
      },

      onSaveWorkOrder: async function () {
        if (!this._selectedWorkOrder || !this._selectedWorkOrder.orderId) {
          return;
        }
        var orderId = this._selectedWorkOrder.orderId;
        var equipmentId = (this.byId("EditWO_equipmentId")?.getValue() || "").trim();
        if (!equipmentId) {
          MessageToast.show("Equipment ID is required.");
          return;
        }
        var issueDescription = (this.byId("EditWO_issueDescription")?.getValue() || "").trim();
        var status = this.byId("EditWO_status")?.getSelectedKey() || "Created";
        var priority = parseInt(this.byId("EditWO_priority")?.getSelectedKey() || "2", 10);
        var actualWork = parseFloat(this.byId("EditWO_actualWork")?.getValue() || "0") || 0;
        var base = this._getApiBase();
        try {
          var res = await fetch(base + "/api/v1/workorders/" + encodeURIComponent(orderId), {
            method: "PUT",
            headers: { "Content-Type": "application/json", "Accept": "application/json" },
            body: JSON.stringify({
              equipmentId: equipmentId,
              issueDescription: issueDescription || undefined,
              status: status,
              priority: priority,
              actualWork: actualWork
            })
          });
          if (!res.ok) {
            var t = await res.text();
            throw new Error(t || "Update failed");
          }
          this.byId("EditWorkOrderDialog")?.close();
          MessageToast.show("Work order updated.");
          this._loadWorkOrders();
        } catch (e) {
          // eslint-disable-next-line no-console
          console.error(e);
          MessageToast.show("Failed to update work order.");
        }
      },

      onDeleteSelectedWorkOrder: async function () {
        if (!this._selectedWorkOrder || !this._selectedWorkOrder.orderId) {
          MessageToast.show("Please select a work order to delete.");
          return;
        }
        var orderId = this._selectedWorkOrder.orderId;
        var base = this._getApiBase();
        try {
          var res = await fetch(base + "/api/v1/workorders/" + encodeURIComponent(orderId), {
            method: "DELETE",
            headers: { "Accept": "application/json" }
          });
          if (!res.ok) {
            var t = await res.text();
            throw new Error(t || "Delete failed");
          }
          MessageToast.show("Work order deleted.");
          this._selectedWorkOrder = null;
          this._setTableActionsEnabled(false);
          var oTable = this.byId("WorkOrdersTable");
          if (oTable) {
            oTable.clearSelection();
          }
          this._loadWorkOrders();
        } catch (e) {
          // eslint-disable-next-line no-console
          console.error(e);
          MessageToast.show("Failed to delete work order.");
        }
      }
    });
  }
);

