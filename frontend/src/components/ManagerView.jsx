import React, { useState, useEffect } from 'react';
import CaseTimeline from './CaseTimeline.jsx';

const SEV_CLASS = { CRITICAL: 'sev-critical', HIGH: 'sev-high', MEDIUM: 'sev-medium', LOW: 'sev-low' };

export default function ManagerView() {
  const [cases, setCases] = useState([]);
  const [selected, setSelected] = useState(null);
  const [overrideReason, setOverrideReason] = useState('');
  const [showOverride, setShowOverride] = useState(false);
  const [loading, setLoading] = useState(true);
  const [actionBusy, setActionBusy] = useState(false);
  const [message, setMessage] = useState(null);

  useEffect(() => { fetchQueue(); }, []);

  const fetchQueue = async () => {
    setLoading(true);
    try {
      const res = await fetch('/cases/review');
      setCases(await res.json());
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const selectCase = async (id) => {
    setMessage(null);
    setShowOverride(false);
    setOverrideReason('');
    try {
      const res = await fetch(`/cases/${id}`);
      setSelected(await res.json());
    } catch (err) {
      console.error(err);
    }
  };

  const submitDecision = async (overrideReason = null) => {
    if (!selected) return;
    setActionBusy(true);
    try {
      const body = overrideReason ? { override_reason: overrideReason } : {};
      const res = await fetch(`/cases/${selected.case.id}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      const data = await res.json();
      setSelected(data);
      setMessage({ type: 'success', text: overrideReason ? 'Override recorded.' : 'Case approved.' });
      fetchQueue();
    } catch (err) {
      setMessage({ type: 'error', text: err.message });
    } finally {
      setActionBusy(false);
    }
  };

  const handleOverrideSubmit = () => {
    if (!overrideReason.trim()) {
      setMessage({ type: 'error', text: 'Override reason is required.' });
      return;
    }
    submitDecision(overrideReason);
  };

  const isPending = selected?.case?.final_status === 'PENDING';

  return (
    <div className="view">
      <div className="view-title">
        <h2>Manager Review Queue</h2>
        <p>Cases routed for human approval — risk score exceeded threshold</p>
      </div>

      <div className="two-col">
        {/* Queue list */}
        <div className="panel">
          <div className="panel-header">
            <h3>Pending ({cases.length})</h3>
            <button className="btn-ghost" onClick={fetchQueue}>Refresh</button>
          </div>

          {loading ? (
            <p className="muted-text">Loading...</p>
          ) : cases.length === 0 ? (
            <div className="empty-state">
              <span>✓</span>
              <p>No cases pending review</p>
            </div>
          ) : (
            <div className="case-list">
              {cases.map((c) => (
                <div
                  key={c.id}
                  className={`case-card ${selected?.case?.id === c.id ? 'case-card-active' : ''}`}
                  onClick={() => selectCase(c.id)}
                >
                  <div className="case-card-top">
                    <span className={`badge ${SEV_CLASS[c.severity] || ''}`}>{c.severity}</span>
                    <span className="muted-text small">{new Date(c.created_at).toLocaleDateString()}</span>
                  </div>
                  <div className="case-card-mid">
                    <strong>{c.fault_category}</strong>
                    <span className="muted-text">Risk: {c.risk_score}/100</span>
                  </div>
                  <code className="tiny-id">{c.id.substring(0, 8)}...</code>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Case detail */}
        <div className="panel">
          {!selected ? (
            <div className="empty-state">
              <span>←</span>
              <p>Select a case to review</p>
            </div>
          ) : (
            <div className="result-panel">
              <div className="result-head">
                <h3>Case Detail</h3>
                <code className="case-id">{selected.case?.id?.substring(0, 8)}...</code>
              </div>

              <div className="stat-grid">
                <div className="stat-card">
                  <label>Fault Category</label>
                  <span>{selected.case?.fault_category}</span>
                </div>
                <div className="stat-card">
                  <label>Severity</label>
                  <span className={`badge ${SEV_CLASS[selected.case?.severity] || ''}`}>
                    {selected.case?.severity}
                  </span>
                </div>
                <div className="stat-card">
                  <label>Risk Score</label>
                  <span className="risk-score">
                    {selected.case?.risk_score}<span className="risk-max">/100</span>
                  </span>
                </div>
                <div className="stat-card">
                  <label>Status</label>
                  <span className={`badge ${selected.case?.final_status === 'APPROVED' || selected.case?.final_status === 'OVERRIDDEN' ? 'route-approved' : 'route-review'}`}>
                    {selected.case?.final_status}
                  </span>
                </div>
              </div>

              {selected.case?.visible_damage && (
                <div className="info-block">
                  <label>Visible Damage</label>
                  <p>{selected.case.visible_damage}</p>
                </div>
              )}

              {selected.case?.raw_description && (
                <div className="info-block">
                  <label>Technician Description</label>
                  <p>{selected.case.raw_description}</p>
                </div>
              )}

              {message && (
                <div className={`alert ${message.type === 'success' ? 'alert-success' : 'alert-error'}`}>
                  {message.text}
                </div>
              )}

              {isPending && (
                <div className="action-block">
                  <h4>Manager Decision</h4>
                  <div className="action-row">
                    <button
                      className="btn-approve"
                      onClick={() => submitDecision()}
                      disabled={actionBusy}
                    >
                      Approve
                    </button>
                    <button
                      className="btn-override"
                      onClick={() => { setShowOverride(!showOverride); setMessage(null); }}
                    >
                      Override
                    </button>
                  </div>

                  {showOverride && (
                    <div className="override-block">
                      <label>Override Reason <span className="required">*</span></label>
                      <textarea
                        value={overrideReason}
                        onChange={(e) => setOverrideReason(e.target.value)}
                        placeholder="Justify the override decision for audit trail..."
                        rows={3}
                      />
                      <button
                        className="btn-primary"
                        onClick={handleOverrideSubmit}
                        disabled={actionBusy || !overrideReason.trim()}
                      >
                        Confirm Override
                      </button>
                    </div>
                  )}
                </div>
              )}

              <CaseTimeline logs={selected.logs} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
