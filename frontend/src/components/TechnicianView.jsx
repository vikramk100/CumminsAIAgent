import React, { useState, useRef } from 'react';
import CaseTimeline from './CaseTimeline.jsx';

const SEV_CLASS = { CRITICAL: 'sev-critical', HIGH: 'sev-high', MEDIUM: 'sev-medium', LOW: 'sev-low' };

export default function TechnicianView() {
  const [image, setImage] = useState(null);
  const [preview, setPreview] = useState(null);
  const [description, setDescription] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const fileRef = useRef();

  const handleImageChange = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setImage(file);
    setPreview(URL.createObjectURL(file));
    setResult(null);
    setError(null);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (!file || !file.type.startsWith('image/')) return;
    setImage(file);
    setPreview(URL.createObjectURL(file));
    setResult(null);
    setError(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!image) { setError('Please select an image'); return; }
    setLoading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append('image', image);
    formData.append('description', description);

    try {
      const res = await fetch('/cases', { method: 'POST', body: formData });
      if (!res.ok) {
        const d = await res.json();
        throw new Error(d.error || `Server error ${res.status}`);
      }
      setResult(await res.json());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setImage(null);
    setPreview(null);
    setDescription('');
    setResult(null);
    setError(null);
  };

  return (
    <div className="view">
      <div className="view-title">
        <h2>Technician Fault Submission</h2>
        <p>Upload an engine component image for multi-agent AI diagnosis</p>
      </div>

      <div className="two-col">
        {/* Left: form */}
        <div className="panel">
          <h3>New Case</h3>
          <form onSubmit={handleSubmit} className="submit-form">
            <div
              className="upload-area"
              onClick={() => fileRef.current.click()}
              onDrop={handleDrop}
              onDragOver={(e) => e.preventDefault()}
            >
              {preview ? (
                <img src={preview} alt="Engine component" className="img-preview" />
              ) : (
                <div className="upload-placeholder">
                  <span className="upload-icon">📷</span>
                  <p>Click or drag image here</p>
                  <small>JPG · PNG · WEBP · up to 20MB</small>
                </div>
              )}
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                onChange={handleImageChange}
                style={{ display: 'none' }}
              />
            </div>

            <div className="form-group">
              <label>Technician Observation Notes</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe symptoms: unusual sounds, fluid leaks, performance issues, recent events..."
                rows={4}
              />
            </div>

            {error && <div className="alert alert-error">{error}</div>}

            <div className="form-actions">
              <button type="submit" className="btn-primary" disabled={loading || !image}>
                {loading ? <><span className="spinner" /> Analyzing...</> : 'Submit for Analysis'}
              </button>
              {(image || result) && (
                <button type="button" className="btn-ghost" onClick={reset}>
                  Reset
                </button>
              )}
            </div>
          </form>
        </div>

        {/* Right: results */}
        <div className="panel">
          {loading && (
            <div className="loading-state">
              <p className="loading-label">Running agent pipeline...</p>
              <div className="pipeline-steps">
                {[
                  { icon: '👁', name: 'VisionFaultAgent', desc: 'Analyzing image with Ollama multimodal model' },
                  { icon: '📊', name: 'RiskScoringAgent', desc: 'Applying deterministic risk scoring rules' },
                  { icon: '🔀', name: 'RoutingAgent', desc: 'Determining approval routing' }
                ].map((s) => (
                  <div key={s.name} className="pipeline-step">
                    <span className="step-icon">{s.icon}</span>
                    <div>
                      <strong>{s.name}</strong>
                      <p>{s.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {result && !loading && (
            <div className="result-panel">
              <div className="result-head">
                <h3>Analysis Complete</h3>
                <code className="case-id">{result.case?.id?.substring(0, 8)}...</code>
              </div>

              <div className="stat-grid">
                <div className="stat-card">
                  <label>Fault Category</label>
                  <span>{result.case?.fault_category}</span>
                </div>
                <div className="stat-card">
                  <label>Severity</label>
                  <span className={`badge ${SEV_CLASS[result.case?.severity] || ''}`}>
                    {result.case?.severity}
                  </span>
                </div>
                <div className="stat-card">
                  <label>Risk Score</label>
                  <span className="risk-score">{result.case?.risk_score}<span className="risk-max">/100</span></span>
                </div>
                <div className="stat-card">
                  <label>Routing</label>
                  <span className={`badge ${result.case?.route === 'MANAGER_REVIEW' ? 'route-review' : 'route-approved'}`}>
                    {result.case?.route}
                  </span>
                </div>
              </div>

              {result.risk?.estimated_cost && (
                <div className="info-block">
                  <label>Estimated Repair Cost</label>
                  <span className="cost-value">${result.risk.estimated_cost.toLocaleString()}</span>
                </div>
              )}

              <div className="info-block">
                <label>Visible Damage</label>
                <p>{result.case?.visible_damage}</p>
              </div>

              <div className="info-block">
                <label>Diagnostic Rationale</label>
                <p>{result.vision?.rationale}</p>
              </div>

              <CaseTimeline logs={result.timeline} />
            </div>
          )}

          {!loading && !result && (
            <div className="empty-state">
              <span>⚙</span>
              <p>Submit a case to see the analysis</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
