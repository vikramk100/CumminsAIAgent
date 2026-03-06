sap.ui.define(
  [
    "sap/ui/core/mvc/Controller",
    "sap/ui/model/json/JSONModel",
    "sap/m/MessageToast",
    "cummins/dispatcher/model/formatter",
  ],
  function (Controller, JSONModel, MessageToast, formatter) {
    "use strict";

    return Controller.extend("cummins.dispatcher.controller.Main", {
      formatter: formatter,

      onInit: function () {
        this._dispatchModel = this.getOwnerComponent().getModel("dispatch");
        this._editingConfirmationId = null;
        
        // Initialize prep model for Preparation tab
        this._prepModel = new JSONModel({
          workOrderId: "",
          equipmentId: "",
          recommendedTools: [],
          recommendedParts: [],
          selectedToolsCount: 0,
          selectedPartsCount: 0,
          selectedPartsTotal: 0,
          checkoutTools: [],
          checkoutParts: [],
          lastOrderId: ""
        });
        this.getView().setModel(this._prepModel, "prep");
        
        // Initialize models for all tools/parts (for Add dialogs)
        this._allToolsModel = new JSONModel({ results: [] });
        this._allPartsModel = new JSONModel({ results: [] });
        this.getView().setModel(this._allToolsModel, "allTools");
        this.getView().setModel(this._allPartsModel, "allParts");
        
        this._loadDispatchBrief();
      },

      onNavBack: function () {
        var router = this.getOwnerComponent().getRouter();
        router.navTo("workOrders");
      },

      onEditWorkOrder: function () {
        var detail = this._dispatchModel.getProperty("/workOrderDetail") || {};
        this.byId("EditWO_equipmentId")?.setValue(detail.equipmentId || "");
        this.byId("EditWO_status")?.setSelectedKey(detail.status || "Created");
        this.byId("EditWO_priority")?.setSelectedKey(String(detail.priority != null ? detail.priority : 2));
        this.byId("EditWO_actualWork")?.setValue(String(detail.actualWork != null ? detail.actualWork : 0));
        this.byId("EditWorkOrderDialog")?.open();
      },

      onCloseEditWorkOrder: function () {
        this.byId("EditWorkOrderDialog")?.close();
      },

      onSaveWorkOrder: async function () {
        var base = this._getApiBase();
        var orderId = this._dispatchModel.getProperty("/orderId");
        var equipmentId = (this.byId("EditWO_equipmentId")?.getValue() || "").trim();
        var status = this.byId("EditWO_status")?.getSelectedKey() || "Created";
        var priority = parseInt(this.byId("EditWO_priority")?.getSelectedKey() || "2", 10);
        var actualWork = parseFloat(this.byId("EditWO_actualWork")?.getValue() || "0") || 0;
        try {
          var res = await fetch(base + "/api/v1/workorders/" + encodeURIComponent(orderId), {
            method: "PUT",
            headers: { "Content-Type": "application/json", "Accept": "application/json" },
            body: JSON.stringify({ equipmentId: equipmentId, status: status, priority: priority, actualWork: actualWork })
          });
          if (!res.ok) throw new Error(await res.text());
          MessageToast.show("Work order updated.");
          this.byId("EditWorkOrderDialog")?.close();
          this._loadDispatchBrief();
        } catch (e) {
          // eslint-disable-next-line no-console
          console.error(e);
          MessageToast.show("Failed to update work order.");
        }
      },

      onDeleteWorkOrder: async function () {
        if (!window.confirm("Delete this work order and all its confirmations?")) return;
        var base = this._getApiBase();
        var orderId = this._dispatchModel.getProperty("/orderId");
        try {
          var res = await fetch(base + "/api/v1/workorders/" + encodeURIComponent(orderId), { method: "DELETE" });
          if (!res.ok) throw new Error(await res.text());
          MessageToast.show("Work order deleted.");
          this.getOwnerComponent().getRouter().navTo("workOrders");
        } catch (e) {
          // eslint-disable-next-line no-console
          console.error(e);
          MessageToast.show("Failed to delete work order.");
        }
      },

      _getOrderId: function () {
        const params = new URLSearchParams(window.location.search);
        const fromQuery = params.get("orderId");
        if (fromQuery) return fromQuery;
        const hash = (window.location.hash || "").replace(/^#\/?/, "");
        if (hash) {
          const segments = hash.split("/");
          return segments[segments.length - 1] || "WO-10000";
        }
        return "WO-10000";
      },

      _getApiBase: function () {
        const params = new URLSearchParams(window.location.search);
        const fromQuery = params.get("apiBase");
        if (fromQuery) return fromQuery.replace(/\/+$/, "");
        const fromStorage = window.localStorage.getItem("API_BASE");
        if (fromStorage) return fromStorage.replace(/\/+$/, "");
        // Use relative URLs in production, localhost:8000 for local dev
        const host = window.location.hostname;
        if (host === "localhost" || host === "127.0.0.1") {
          return "http://localhost:8000";
        }
        return ""; // Relative URLs for production (same origin)
      },

      _loadDispatchBrief: async function () {
        const orderId = this._getOrderId();
        const base = this._getApiBase();

        this._dispatchModel.setProperty("/loading", true);
        this._dispatchModel.setProperty("/error", null);
        this._dispatchModel.setProperty("/orderId", orderId);

        try {
          const res = await fetch(`${base}/api/v1/dispatch-brief/${encodeURIComponent(orderId)}`, {
            method: "GET",
            headers: { "Accept": "application/json" }
          });
          if (!res.ok) {
            const t = await res.text();
            throw new Error(`API error ${res.status}: ${t}`);
          }
          const data = await res.json();

          // Normalize backend snake_case fields into camelCase for the view model
          const workOrderDetailRaw = data.work_order_detail || data.workOrderDetail || {};
          const orderIdFromApi = data.orderId || workOrderDetailRaw.orderId || orderId;

          // Ensure we always have a usable workOrderDetail object
          const telemetryRaw =
            workOrderDetailRaw.telemetry ||
            data.ml_prediction?.telemetry ||
            {};
          const telemetry = {
            Process_Temperature:
              telemetryRaw.Process_Temperature ?? 0,
            Air_Temperature:
              telemetryRaw.Air_Temperature ?? 0,
            Rotational_Speed:
              telemetryRaw.Rotational_Speed ?? 0,
            Torque:
              telemetryRaw.Torque ?? 0,
            Tool_Wear:
              telemetryRaw.Tool_Wear ?? 0,
          };
          const workOrderDetail = {
            orderId: workOrderDetailRaw.orderId || orderIdFromApi,
            status: workOrderDetailRaw.status || data.work_order?.status,
            priority: workOrderDetailRaw.priority ?? data.work_order?.priority ?? "",
            equipmentId:
              workOrderDetailRaw.equipmentId ||
              data.work_order?.equipmentId ||
              data.context_summary?.equipmentId ||
              "",
            actualWork: workOrderDetailRaw.actualWork ?? data.work_order?.actualWork ?? "",
            orderDate: workOrderDetailRaw.orderDate || data.work_order?.orderDate || "",
            daysToSolve:
              workOrderDetailRaw.daysToSolve != null
                ? workOrderDetailRaw.daysToSolve
                : "",
            issueDescription:
              workOrderDetailRaw.issueDescription ||
              "Placeholder issue description for this work order. In a real system this would summarize the fault, affected subsystem, and key findings from diagnostics and technician notes.",
            technician:
              workOrderDetailRaw.technician ||
              "Technician (unassigned)",
            telemetry: telemetry,
            operations: workOrderDetailRaw.operations || [],
            confirmations: workOrderDetailRaw.confirmations || [],
            timeline: workOrderDetailRaw.timeline || [],
          };
          data.workOrderDetail = workOrderDetail;

          // Normalize UI bindings
          const failureLabel = data?.context_summary?.failure_label || "No_Failure";
          const confidence = Number(data?.context_summary?.confidence || 0);
          const crit = formatter.criticalityFrom(failureLabel, confidence);
          const critText = formatter.criticalityText(crit);
          const critState = formatter.criticalityState(crit);
          const confPct = formatter.confidencePercent(confidence);
          const confDisplay = formatter.confidenceDisplay(confidence);

          const tools = (data?.mission_briefing?.required_tools || []).map((t) => ({ name: t, checked: false }));
          const snippet = data?.mission_briefing?.manual_reference_snippet || "";
          const manualSnippetHtml = formatter.snippetToHtml(snippet);

          data.ui = {
            criticality: crit,
            criticalityText: critText,
            criticalityState: critState,
            confidencePercent: confPct,
            confidenceDisplay: confDisplay,
            tools: tools,
            manualSnippetHtml: manualSnippetHtml,
            chatLastAnswer: "",
            thoughtFeedback: null
          };

          this._dispatchModel.setData({ ...this._dispatchModel.getData(), ...data }, true);
          
          // Also load preparation recommendations
          this._loadRecommendedPrep();
        } catch (e) {
          this._dispatchModel.setProperty("/error", String(e?.message || e));
          MessageToast.show("Failed to load dispatch brief.");
        } finally {
          this._dispatchModel.setProperty("/loading", false);
        }
      },

      onOpenAiChat: function () {
        const oDialog = this.byId("AiChatDialog");
        if (oDialog) {
          oDialog.open();
        }
      },

      onCloseAiChat: function () {
        const oDialog = this.byId("AiChatDialog");
        if (oDialog) {
          oDialog.close();
        }
      },

      onSendAiQuestion: async function () {
        const base = this._getApiBase();
        const orderId = this._dispatchModel.getProperty("/orderId");
        const equipmentId =
          this._dispatchModel.getProperty("/workOrderDetail/equipmentId") ||
          this._dispatchModel.getProperty("/context_summary/equipmentId") ||
          "";
        const oInput = this.byId("AiChatInput");
        const question = (oInput && oInput.getValue && oInput.getValue()) || "";
        if (!question.trim()) {
          MessageToast.show("Please enter a question for the AI assistant.");
          return;
        }

        this._dispatchModel.setProperty("/ui/chatLastAnswer", "Thinking...");

        try {
          const res = await fetch(`${base}/api/v1/chat`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Accept: "application/json",
            },
            body: JSON.stringify({
              orderId: orderId,
              equipmentId: equipmentId,
              question: question,
            }),
          });
          if (!res.ok) {
            const t = await res.text();
            throw new Error(`API error ${res.status}: ${t}`);
          }
          const data = await res.json();
          this._dispatchModel.setProperty(
            "/ui/chatLastAnswer",
            data.answer || "No answer was returned."
          );
        } catch (e) {
          // eslint-disable-next-line no-console
          console.error("AI chat failed", e);
          this._dispatchModel.setProperty(
            "/ui/chatLastAnswer",
            "The AI assistant is currently unavailable."
          );
          MessageToast.show("AI assistant is currently unavailable.");
        }
      },

      onShowThoughtProcess: function () {
        const dialog = this.byId("ThoughtProcessDialog");
        if (dialog) {
          dialog.open();
        }
      },

      onCloseThoughtProcess: function () {
        const dialog = this.byId("ThoughtProcessDialog");
        if (dialog) {
          dialog.close();
        }
      },

      onThoughtFeedbackUp: function () {
        this._sendInsightFeedback("up");
      },

      onThoughtFeedbackDown: function () {
        this._sendInsightFeedback("down");
      },

      _sendInsightFeedback: async function (rating) {
        const base = this._getApiBase();
        const orderId = this._dispatchModel.getProperty("/orderId");
        const equipmentId =
          this._dispatchModel.getProperty("/workOrderDetail/equipmentId") ||
          this._dispatchModel.getProperty("/context_summary/equipmentId") ||
          "";
        const feedbackText = this._dispatchModel.getProperty("/mission_briefing/thought_process") || "";
        const rootCauseAnalysis = this._dispatchModel.getProperty("/mission_briefing/root_cause_analysis") || "";

        this._dispatchModel.setProperty("/ui/thoughtFeedback", rating);

        try {
          const res = await fetch(`${base}/api/v1/insight-feedback`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Accept: "application/json",
            },
            body: JSON.stringify({
              orderId: orderId,
              equipmentId: equipmentId,
              rating: rating,
              source: "thought_process",
              feedbackText: feedbackText,
              rootCauseAnalysis: rootCauseAnalysis,
              userId: window.localStorage.getItem("USER_ID") || null,
            }),
          });
          if (!res.ok) {
            const t = await res.text();
            throw new Error(t || "Feedback failed");
          }
          MessageToast.show("Thanks for your feedback. It will be used for model improvement.");
        } catch (e) {
          // eslint-disable-next-line no-console
          console.error("Insight feedback failed", e);
          MessageToast.show("Could not save feedback. Please try again.");
        }
      },

      onAddConfirmation: function () {
        this._editingConfirmationId = null;
        this.byId("ConfirmationDialog")?.setTitle("Add Confirmation");
        this.byId("Confirmation_Text")?.setValue("");
        this.byId("Confirmation_Status")?.setSelectedKey("Submitted");
        this.byId("Confirmation_ActualWork")?.setValue("0");
        this.byId("ConfirmationDialog")?.open();
      },

      onEditConfirmation: function (oEvent) {
        var ctx = oEvent.getSource().getBindingContext("dispatch");
        if (!ctx) return;
        var confirmationId = ctx.getProperty("confirmationId");
        var conf = ctx.getObject();
        if (!conf || !confirmationId) return;
        this._editingConfirmationId = confirmationId;
        this.byId("ConfirmationDialog")?.setTitle("Edit Confirmation");
        this.byId("Confirmation_Text")?.setValue(conf.confirmationText || "");
        this.byId("Confirmation_Status")?.setSelectedKey(conf.status || "Submitted");
        this.byId("Confirmation_ActualWork")?.setValue(String(conf.actualWork != null ? conf.actualWork : 0));
        this.byId("ConfirmationDialog")?.open();
      },

      onCloseConfirmationDialog: function () {
        this._editingConfirmationId = null;
        this.byId("ConfirmationDialog")?.close();
      },

      onSaveConfirmation: async function () {
        var base = this._getApiBase();
        var orderId = this._dispatchModel.getProperty("/orderId");
        var text = (this.byId("Confirmation_Text")?.getValue() || "").trim();
        if (!text) {
          MessageToast.show("Please enter confirmation text.");
          return;
        }
        var status = this.byId("Confirmation_Status")?.getSelectedKey() || "Submitted";
        var actualWork = parseFloat(this.byId("Confirmation_ActualWork")?.getValue() || "0") || 0;

        try {
          if (this._editingConfirmationId) {
            var putRes = await fetch(
              base + "/api/v1/workorders/" + encodeURIComponent(orderId) + "/confirmations/" + encodeURIComponent(this._editingConfirmationId),
              {
                method: "PUT",
                headers: { "Content-Type": "application/json", "Accept": "application/json" },
                body: JSON.stringify({ confirmationText: text, status: status, actualWork: actualWork })
              }
            );
            if (!putRes.ok) throw new Error(await putRes.text());
            MessageToast.show("Confirmation updated.");
          } else {
            var postRes = await fetch(base + "/api/v1/workorders/" + encodeURIComponent(orderId) + "/confirmations", {
              method: "POST",
              headers: { "Content-Type": "application/json", "Accept": "application/json" },
              body: JSON.stringify({ confirmationText: text, status: status, actualWork: actualWork })
            });
            if (!postRes.ok) throw new Error(await postRes.text());
            MessageToast.show("Confirmation added.");
          }
          this.onCloseConfirmationDialog();
          this._loadDispatchBrief();
        } catch (e) {
          // eslint-disable-next-line no-console
          console.error(e);
          MessageToast.show("Failed to save confirmation.");
        }
      },

      onDeleteConfirmation: async function (oEvent) {
        var ctx = oEvent.getSource().getBindingContext("dispatch");
        if (!ctx) return;
        var confirmationId = ctx.getProperty("confirmationId");
        if (!confirmationId) return;
        if (!window.confirm("Delete this confirmation?")) return;
        var base = this._getApiBase();
        var orderId = this._dispatchModel.getProperty("/orderId");
        try {
          var res = await fetch(
            base + "/api/v1/workorders/" + encodeURIComponent(orderId) + "/confirmations/" + encodeURIComponent(confirmationId),
            { method: "DELETE" }
          );
          if (!res.ok) throw new Error(await res.text());
          MessageToast.show("Confirmation deleted.");
          this._loadDispatchBrief();
        } catch (e) {
          // eslint-disable-next-line no-console
          console.error(e);
          MessageToast.show("Failed to delete confirmation.");
        }
      },

      onPressToolKitCheck: async function (oEvent) {
        const oCb = oEvent.getSource();
        const checked = !!oEvent.getParameter("selected");
        const toolName = oCb.data("toolName") || "";
        const base = this._getApiBase();
        const orderId = this._dispatchModel.getProperty("/orderId");
        const equipmentId = this._dispatchModel.getProperty("/context_summary/equipmentId");

        // Update local model state
        const path = oCb.getBindingContext("dispatch")?.getPath();
        if (path) {
          this._dispatchModel.setProperty(path + "/checked", checked);
        }

        try {
          await fetch(`${base}/api/v1/audit-trail`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              orderId: orderId,
              equipmentId: equipmentId,
              toolName: toolName,
              checked: checked,
              userId: window.localStorage.getItem("USER_ID") || null,
              source: "ui5"
            })
          });
          MessageToast.show(checked ? `Confirmed: ${toolName}` : `Unchecked: ${toolName}`);
        } catch (e) {
          // Non-blocking: UI can continue even if audit fails
          // eslint-disable-next-line no-console
          console.log("Audit trail failed", e);
        }
      },

      // ========================================
      // Preparation Tab - Tools & Spare Parts
      // ========================================

      _loadRecommendedPrep: async function () {
        const orderId = this._getOrderId();
        const base = this._getApiBase();
        
        try {
          const res = await fetch(`${base}/api/v1/workorders/${encodeURIComponent(orderId)}/recommended-prep`, {
            method: "GET",
            headers: { "Accept": "application/json" }
          });
          
          if (!res.ok) {
            throw new Error(`API error ${res.status}`);
          }
          
          const data = await res.json();
          
          // Use the data as-is (already has selected/hasItem from API)
          const tools = data.recommendedTools || [];
          const parts = data.recommendedParts || [];
          
          this._prepModel.setProperty("/workOrderId", orderId);
          this._prepModel.setProperty("/equipmentId", data.equipmentId || "");
          this._prepModel.setProperty("/recommendedTools", tools);
          this._prepModel.setProperty("/recommendedParts", parts);
          this._updateCheckoutSummary();
          
        } catch (e) {
          // eslint-disable-next-line no-console
          console.error("Failed to load recommended prep", e);
          MessageToast.show("Failed to load preparation recommendations.");
        }
      },

      _loadAllToolsAndParts: async function () {
        const base = this._getApiBase();
        
        try {
          const [toolsRes, partsRes] = await Promise.all([
            fetch(`${base}/api/v1/tools`, { headers: { "Accept": "application/json" } }),
            fetch(`${base}/api/v1/spare-parts`, { headers: { "Accept": "application/json" } })
          ]);
          
          if (toolsRes.ok) {
            const toolsData = await toolsRes.json();
            this._allToolsModel.setProperty("/results", toolsData.results || []);
          }
          
          if (partsRes.ok) {
            const partsData = await partsRes.json();
            this._allPartsModel.setProperty("/results", partsData.results || []);
          }
        } catch (e) {
          // eslint-disable-next-line no-console
          console.error("Failed to load all tools/parts", e);
        }
      },

      _updateCheckoutSummary: function () {
        const tools = this._prepModel.getProperty("/recommendedTools") || [];
        const parts = this._prepModel.getProperty("/recommendedParts") || [];
        
        const selectedTools = tools.filter(t => t.selected && !t.hasItem);
        const selectedParts = parts.filter(p => p.selected && !p.hasItem);
        
        const partsTotal = selectedParts.reduce((sum, p) => sum + (p.unitPrice || 0), 0);
        
        this._prepModel.setProperty("/selectedToolsCount", selectedTools.length);
        this._prepModel.setProperty("/selectedPartsCount", selectedParts.length);
        this._prepModel.setProperty("/selectedPartsTotal", partsTotal.toFixed(2));
        this._prepModel.setProperty("/checkoutTools", selectedTools);
        this._prepModel.setProperty("/checkoutParts", selectedParts);
      },

      onSelectAllTools: function () {
        const tools = this._prepModel.getProperty("/recommendedTools") || [];
        tools.forEach(t => { t.selected = true; });
        this._prepModel.setProperty("/recommendedTools", tools);
        this._updateCheckoutSummary();
        
        // Update table selection
        const table = this.byId("ToolsTable");
        if (table) {
          table.selectAll();
        }
      },

      onDeselectAllTools: function () {
        const tools = this._prepModel.getProperty("/recommendedTools") || [];
        tools.forEach(t => { t.selected = false; });
        this._prepModel.setProperty("/recommendedTools", tools);
        this._updateCheckoutSummary();
        
        // Update table selection
        const table = this.byId("ToolsTable");
        if (table) {
          table.removeSelections(true);
        }
      },

      onSelectAllParts: function () {
        const parts = this._prepModel.getProperty("/recommendedParts") || [];
        parts.forEach(p => { p.selected = true; });
        this._prepModel.setProperty("/recommendedParts", parts);
        this._updateCheckoutSummary();
        
        // Update table selection
        const table = this.byId("PartsTable");
        if (table) {
          table.selectAll();
        }
      },

      onDeselectAllParts: function () {
        const parts = this._prepModel.getProperty("/recommendedParts") || [];
        parts.forEach(p => { p.selected = false; });
        this._prepModel.setProperty("/recommendedParts", parts);
        this._updateCheckoutSummary();
        
        // Update table selection
        const table = this.byId("PartsTable");
        if (table) {
          table.removeSelections(true);
        }
      },

      onToolSelectionChange: function (oEvent) {
        const table = oEvent.getSource();
        const selectedItems = table.getSelectedItems();
        const tools = this._prepModel.getProperty("/recommendedTools") || [];
        
        // Reset all selections
        tools.forEach(t => { t.selected = false; });
        
        // Mark selected items
        selectedItems.forEach(item => {
          const ctx = item.getBindingContext("prep");
          if (ctx) {
            const idx = parseInt(ctx.getPath().split("/").pop(), 10);
            if (!isNaN(idx) && tools[idx]) {
              tools[idx].selected = true;
            }
          }
        });
        
        this._prepModel.setProperty("/recommendedTools", tools);
        this._updateCheckoutSummary();
      },

      onPartSelectionChange: function (oEvent) {
        const table = oEvent.getSource();
        const selectedItems = table.getSelectedItems();
        const parts = this._prepModel.getProperty("/recommendedParts") || [];
        
        // Reset all selections
        parts.forEach(p => { p.selected = false; });
        
        // Mark selected items
        selectedItems.forEach(item => {
          const ctx = item.getBindingContext("prep");
          if (ctx) {
            const idx = parseInt(ctx.getPath().split("/").pop(), 10);
            if (!isNaN(idx) && parts[idx]) {
              parts[idx].selected = true;
            }
          }
        });
        
        this._prepModel.setProperty("/recommendedParts", parts);
        this._updateCheckoutSummary();
      },

      onToolHasItemChange: function (oEvent) {
        const checkbox = oEvent.getSource();
        const selected = oEvent.getParameter("selected");
        const ctx = checkbox.getBindingContext("prep");
        
        if (ctx) {
          const path = ctx.getPath();
          this._prepModel.setProperty(path + "/hasItem", selected);
          this._updateCheckoutSummary();
          
          if (selected) {
            const toolName = this._prepModel.getProperty(path + "/name");
            MessageToast.show(`Marked "${toolName}" as already available`);
          }
        }
      },

      onPartHasItemChange: function (oEvent) {
        const checkbox = oEvent.getSource();
        const selected = oEvent.getParameter("selected");
        const ctx = checkbox.getBindingContext("prep");
        
        if (ctx) {
          const path = ctx.getPath();
          this._prepModel.setProperty(path + "/hasItem", selected);
          this._updateCheckoutSummary();
          
          if (selected) {
            const partName = this._prepModel.getProperty(path + "/name");
            MessageToast.show(`Marked "${partName}" as already in stock`);
          }
        }
      },

      // Add Tool Dialog
      onAddTool: function () {
        this._loadAllToolsAndParts();
        this.byId("AddToolDialog")?.open();
      },

      onConfirmAddTool: function () {
        const select = this.byId("addToolSelect");
        const selectedKey = select?.getSelectedKey();
        
        if (!selectedKey) {
          MessageToast.show("Please select a tool.");
          return;
        }
        
        const allTools = this._allToolsModel.getProperty("/results") || [];
        const tool = allTools.find(t => t.toolId === selectedKey);
        
        if (tool) {
          const currentTools = this._prepModel.getProperty("/recommendedTools") || [];
          
          // Check if already in list
          if (currentTools.some(t => t.toolId === tool.toolId)) {
            MessageToast.show("This tool is already in the list.");
          } else {
            currentTools.push({
              ...tool,
              selected: true,
              hasItem: false
            });
            this._prepModel.setProperty("/recommendedTools", currentTools);
            this._updateCheckoutSummary();
            MessageToast.show(`Added "${tool.name}" to preparation list.`);
          }
        }
        
        this.byId("AddToolDialog")?.close();
      },

      onCancelAddTool: function () {
        this.byId("AddToolDialog")?.close();
      },

      // Add Part Dialog
      onAddPart: function () {
        this._loadAllToolsAndParts();
        this.byId("AddPartDialog")?.open();
      },

      onConfirmAddPart: function () {
        const select = this.byId("addPartSelect");
        const selectedKey = select?.getSelectedKey();
        
        if (!selectedKey) {
          MessageToast.show("Please select a spare part.");
          return;
        }
        
        const allParts = this._allPartsModel.getProperty("/results") || [];
        const part = allParts.find(p => p.partId === selectedKey);
        
        if (part) {
          const currentParts = this._prepModel.getProperty("/recommendedParts") || [];
          
          // Check if already in list
          if (currentParts.some(p => p.partId === part.partId)) {
            MessageToast.show("This part is already in the list.");
          } else {
            currentParts.push({
              ...part,
              selected: true,
              hasItem: false
            });
            this._prepModel.setProperty("/recommendedParts", currentParts);
            this._updateCheckoutSummary();
            MessageToast.show(`Added "${part.name}" to preparation list.`);
          }
        }
        
        this.byId("AddPartDialog")?.close();
      },

      onCancelAddPart: function () {
        this.byId("AddPartDialog")?.close();
      },

      // Checkout
      onProceedToCheckout: function () {
        const toolsCount = this._prepModel.getProperty("/selectedToolsCount") || 0;
        const partsCount = this._prepModel.getProperty("/selectedPartsCount") || 0;
        
        if (toolsCount === 0 && partsCount === 0) {
          MessageToast.show("Please select at least one tool or spare part.");
          return;
        }
        
        this.byId("CheckoutDialog")?.open();
      },

      onCloseCheckout: function () {
        this.byId("CheckoutDialog")?.close();
      },

      onPlaceOrder: async function () {
        const base = this._getApiBase();
        const workOrderId = this._prepModel.getProperty("/workOrderId");
        const checkoutTools = this._prepModel.getProperty("/checkoutTools") || [];
        const checkoutParts = this._prepModel.getProperty("/checkoutParts") || [];
        const notes = this.byId("checkoutNotes")?.getValue() || "";
        
        // Build items array
        const items = [];
        
        checkoutTools.forEach(tool => {
          items.push({
            itemType: "tool",
            itemId: tool.toolId,
            name: tool.name,
            quantity: 1,
            unitPrice: 0,
            status: "pending"
          });
        });
        
        checkoutParts.forEach(part => {
          items.push({
            itemType: "spare_part",
            itemId: part.partId,
            name: part.name,
            quantity: 1,
            unitPrice: part.unitPrice || 0,
            status: "pending"
          });
        });
        
        try {
          const res = await fetch(`${base}/api/v1/prep-orders`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "Accept": "application/json"
            },
            body: JSON.stringify({
              workOrderId: workOrderId,
              items: items,
              notes: notes,
              technicianId: window.localStorage.getItem("USER_ID") || "technician-01"
            })
          });
          
          if (!res.ok) {
            const t = await res.text();
            throw new Error(`API error ${res.status}: ${t}`);
          }
          
          const orderData = await res.json();
          this._prepModel.setProperty("/lastOrderId", orderData.prepOrderId || "ORD-" + Date.now());
          
          // Close checkout and show success
          this.byId("CheckoutDialog")?.close();
          this.byId("OrderSuccessDialog")?.open();
          
          // Clear selections
          const tools = this._prepModel.getProperty("/recommendedTools") || [];
          const parts = this._prepModel.getProperty("/recommendedParts") || [];
          tools.forEach(t => { t.selected = false; });
          parts.forEach(p => { p.selected = false; });
          this._prepModel.setProperty("/recommendedTools", tools);
          this._prepModel.setProperty("/recommendedParts", parts);
          this._updateCheckoutSummary();
          
          // Clear table selections
          this.byId("ToolsTable")?.removeSelections(true);
          this.byId("PartsTable")?.removeSelections(true);
          this.byId("checkoutNotes")?.setValue("");
          
        } catch (e) {
          // eslint-disable-next-line no-console
          console.error("Failed to place order", e);
          MessageToast.show("Failed to place order. Please try again.");
        }
      },

      onCloseOrderSuccess: function () {
        this.byId("OrderSuccessDialog")?.close();
      }
    });
  }
);

