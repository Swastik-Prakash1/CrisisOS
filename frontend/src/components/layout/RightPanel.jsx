import React from 'react';
import useSimStore from '../../store/useSimStore';

const AGENT_STYLES = {
  COMMANDER:    { color: '#00D4FF', className: 'commander' },
  MEDICAL:      { color: '#00FF88', className: 'medical' },
  LOGISTICS:    { color: '#FFB020', className: 'logistics' },
  PREDICTION:   { color: '#8B5CF6', className: 'prediction' },
  INTELLIGENCE: { color: '#3B82F6', className: 'intelligence' },
  SYSTEM:       { color: '#7A8BA8', className: '' },
};

function AgentTag({ name }) {
  const style = AGENT_STYLES[name] || AGENT_STYLES.SYSTEM;
  return <span className={`agent-tag ${style.className}`}>{name}</span>;
}

function AgentReasoning() {
  const { activeDecision } = useSimStore();

  if (!activeDecision) {
    return (
      <div className="panel-section" style={{ flex: '0 0 auto' }}>
        <div className="section-header">AGENT REASONING</div>
        <div style={{ color: 'var(--text-tertiary)', fontSize: 11, fontStyle: 'italic', padding: '8px 0' }}>
          Awaiting agent activity...
        </div>
      </div>
    );
  }

  const isConflict = activeDecision.scenario_type && activeDecision.scenario_type !== 'routine';
  const proposals = activeDecision.proposals || [];

  return (
    <div className="panel-section" style={{ flex: '0 0 auto' }}>
      <div className="section-header">
        <span>AGENT REASONING</span>
        {isConflict && <span className="badge badge-critical">CONFLICT</span>}
      </div>

      {isConflict && (
        <div className="conflict-banner">
          <div className="conflict-header">
            <span className="status-dot red" />
            <span>CONFLICT ACTIVE</span>
            <span className="scenario-badge" style={{ marginLeft: 'auto' }}>
              {activeDecision.scenario_type.replace(/_/g, ' ')}
            </span>
          </div>

          {proposals.map((p, i) => (
            <div
              key={p.id || i}
              className={`proposal-card ${p.agent_name === activeDecision.agent_winner ? 'winner' : 'rejected'}`}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <AgentTag name={p.agent_name} />
                {p.agent_name === activeDecision.agent_winner && (
                  <span style={{ color: 'var(--accent-green)', fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }}>
                    ✓ SELECTED
                  </span>
                )}
              </div>
              <div className="proposal-action">{p.action}</div>
              <div className="proposal-reasoning">{p.reasoning}</div>
              <div className="proposal-score">
                Utility: {(p.utility_score || 0).toFixed(3)} | Confidence: {((p.confidence || 0) * 100).toFixed(0)}%
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="commander-decision">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <AgentTag name="COMMANDER" />
          <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
            Tick {activeDecision.tick}
          </span>
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-primary)', fontWeight: 500 }}>
          {activeDecision.action}
        </div>

        <div className="confidence-row">
          <span className="confidence-label">Confidence</span>
          <div className="confidence-bar">
            <div
              className="confidence-fill"
              style={{ width: `${(activeDecision.confidence || 0) * 100}%` }}
            />
          </div>
          <span className="confidence-value text-cyan">
            {((activeDecision.confidence || 0) * 100).toFixed(0)}%
          </span>
        </div>

        {(activeDecision.gemini_explanation || activeDecision.alternative_rejected_because) && (
          <div className="commander-explanation">
            {activeDecision.gemini_explanation || activeDecision.alternative_rejected_because}
          </div>
        )}
      </div>
    </div>
  );
}

function ActivityLog() {
  const { activityLog } = useSimStore();

  return (
    <div className="panel-section" style={{ flex: 1, overflow: 'hidden' }}>
      <div className="section-header">
        <span>SYSTEM ACTIVITY</span>
        <span className="count">{activityLog.length}</span>
      </div>
      <div style={{ overflowY: 'auto', maxHeight: 200 }}>
        {activityLog.slice(0, 25).map((entry) => {
          const agentStyle = AGENT_STYLES[entry.agent] || AGENT_STYLES.SYSTEM;
          return (
            <div key={entry.id} className="log-entry animate-slide-up">
              <span className="log-timestamp">[{entry.timestamp}]</span>
              <span className="log-agent" style={{ color: agentStyle.color }}>
                [{entry.agent}]
              </span>
              <span className="log-message">{entry.message}</span>
            </div>
          );
        })}
        {activityLog.length === 0 && (
          <div style={{ color: 'var(--text-tertiary)', fontSize: 10, fontStyle: 'italic' }}>
            No activity yet
          </div>
        )}
      </div>
    </div>
  );
}

function PredictionAlerts() {
  const { predictionAlerts } = useSimStore();

  if (predictionAlerts.length === 0) return null;

  return (
    <div className="panel-section" style={{ flex: '0 0 auto' }}>
      <div className="section-header">
        <span>PREDICTION ALERTS</span>
        <span className="count">{predictionAlerts.length}</span>
      </div>
      {predictionAlerts.slice(0, 5).map((alert, i) => (
        <div key={alert.id || i} className={`alert-card ${alert.urgency}`}>
          <div className="alert-message">{alert.message}</div>
          <div className="alert-meta">
            {alert.category?.replace(/_/g, ' ')} | {alert.confidence ? `${(alert.confidence * 100).toFixed(0)}% conf` : ''}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function RightPanel() {
  return (
    <div className="right-panel">
      <AgentReasoning />
      <PredictionAlerts />
      <ActivityLog />
    </div>
  );
}
