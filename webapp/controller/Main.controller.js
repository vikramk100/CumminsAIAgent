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
      }
    });
  }
);

