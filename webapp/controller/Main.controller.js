sap.ui.define(
  ["sap/ui/core/mvc/Controller", "sap/ui/model/json/JSONModel", "sap/m/MessageToast", "cummins/dispatcher/model/formatter"],
  function (Controller, JSONModel, MessageToast, formatter) {
    "use strict";

    return Controller.extend("cummins.dispatcher.controller.Main", {
      formatter: formatter,

      onInit: function () {
        this._dispatchModel = this.getOwnerComponent().getModel("dispatch");
        this._loadDispatchBrief();
      },

      _getOrderId: function () {
        const params = new URLSearchParams(window.location.search);
        const fromQuery = params.get("orderId");
        if (fromQuery) return fromQuery;
        const hash = (window.location.hash || "").replace(/^#\/?/, "");
        return hash || "WO-10000";
      },

      _getApiBase: function () {
        const params = new URLSearchParams(window.location.search);
        const fromQuery = params.get("apiBase");
        if (fromQuery) return fromQuery.replace(/\/+$/, "");
        const fromStorage = window.localStorage.getItem("API_BASE");
        if (fromStorage) return fromStorage.replace(/\/+$/, "");
        return "http://localhost:8000";
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
            manualSnippetHtml: manualSnippetHtml
          };

          this._dispatchModel.setData({ ...this._dispatchModel.getData(), ...data }, true);
        } catch (e) {
          this._dispatchModel.setProperty("/error", String(e?.message || e));
          MessageToast.show("Failed to load dispatch brief.");
        } finally {
          this._dispatchModel.setProperty("/loading", false);
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

