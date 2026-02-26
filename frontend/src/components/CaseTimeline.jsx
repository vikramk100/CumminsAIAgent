import React from 'react';

const AGENT_META = {
  VisionFaultAgent: { icon: '👁', label: 'Vision Analysis', colorClass: 'tl-vision' },
  RiskScoringAgent: { icon: '📊', label: 'Risk Scoring', colorClass: 'tl-risk' },
  RoutingAgent: { icon: '🔀', label: 'Routing Decision', colorClass: 'tl-routing' },
  ManagerDecision: { icon: '👤', label: 'Manager Decision', colorClass: 'tl-manager' }
};

export default function CaseTimeline({ logs }) {
  if (!logs || logs.length === 0) return null;

  return (
    <div className="timeline">
      <h4>Agent Decision Timeline</h4>
      <div className="timeline-items">
        {logs.map((log) => {
          const meta = AGENT_META[log.agent_name] || { icon: '🤖', label: log.agent_name, colorClass: '' };
          let output = {};
          try {
            output = typeof log.output_json === 'string' ? JSON.parse(log.output_json) : log.output_json;
          } catch {}

          return (
            <div key={log.id} className={`timeline-item ${meta.colorClass}`}>
              <div className="tl-marker">{meta.icon}</div>
              <div className="tl-body">
                <div className="tl-head">
                  <strong>{meta.label}</strong>
                  <span className="tl-confidence">
                    {(log.confidence * 100).toFixed(0)}% confidence
                  </span>
                  <span className="tl-time">
                    {new Date(log.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                <p className="tl-rationale">{log.rationale}</p>
                <details className="tl-details">
                  <summary>Full output</summary>
                  <pre>{JSON.stringify(output, null, 2)}</pre>
                </details>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
