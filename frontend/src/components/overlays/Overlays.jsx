import React, { useState } from 'react';
import useSimStore from '../../store/useSimStore';

export function HumanOverride() {
  const {
    humanOverrideActive, overrideWarning,
    sendHumanCommand, confirmOverride, cancelOverride,
  } = useSimStore();
  const [action, setAction] = useState('send_all_units');
  const [target, setTarget] = useState('A');

  if (!humanOverrideActive) return null;

  return (
    <div style={{
      position: 'absolute', bottom: 64, left: '50%', transform: 'translateX(-50%)',
      background: 'var(--bg-secondary)', border: '1px solid var(--accent-amber)',
      borderRadius: 8, padding: 16, zIndex: 500, width: 420,
      boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <span style={{ fontSize: 18 }}>👤</span>
        <span className="font-mono" style={{ fontSize: 12, fontWeight: 700, color: 'var(--accent-amber)', letterSpacing: 1 }}>
          HUMAN COMMAND MODE
        </span>
        <span className="badge badge-warning" style={{ marginLeft: 'auto' }}>ACTIVE</span>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <select
          value={action}
          onChange={e => setAction(e.target.value)}
          style={{
            flex: 1, background: 'var(--bg-card)', border: '1px solid var(--border-accent)',
            color: 'var(--text-primary)', padding: '6px 8px', borderRadius: 4,
            fontFamily: "'JetBrains Mono', monospace", fontSize: 11,
          }}
        >
          <option value="send_all_units">Send all units to sector</option>
          <option value="evacuate_hospital">Evacuate hospital</option>
          <option value="block_allocation">Block resource allocation</option>
        </select>
        <select
          value={target}
          onChange={e => setTarget(e.target.value)}
          style={{
            width: 80, background: 'var(--bg-card)', border: '1px solid var(--border-accent)',
            color: 'var(--text-primary)', padding: '6px 8px', borderRadius: 4,
            fontFamily: "'JetBrains Mono', monospace", fontSize: 11,
          }}
        >
          {action === 'evacuate_hospital'
            ? <>
                <option value="H1">H1</option>
                <option value="H2">H2</option>
                <option value="H3">H3</option>
              </>
            : <>
                <option value="A">Sector A</option>
                <option value="B">Sector B</option>
                <option value="C">Sector C</option>
                <option value="D">Sector D</option>
              </>
          }
        </select>
        <button
          className="btn btn-amber"
          onClick={() => sendHumanCommand(action, target)}
        >
          EXECUTE
        </button>
      </div>

      {overrideWarning && (
        <div className="override-warning">
          <div className="warning-title">
            <span>⚠</span>
            <span>AI ADVISORY</span>
          </div>
          <p style={{ color: 'var(--text-primary)', fontSize: 12, marginBottom: 8 }}>
            This command is predicted to increase casualties by{' '}
            <span className="casualty-delta">+{overrideWarning.projected_casualties_delta}</span>
          </p>
          <div className="recommendation">
            <strong style={{ color: 'var(--accent-cyan)' }}>Recommended alternative:</strong><br />
            {overrideWarning.recommendation}
          </div>
          <div className="override-actions">
            <button className="btn btn-danger" onClick={confirmOverride}>
              EXECUTE ANYWAY
            </button>
            <button className="btn btn-safe" onClick={cancelOverride}>
              FOLLOW AI RECOMMENDATION
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export function JudgeReplay() {
  const { judgeReplayOpen, closeJudgeReplay, decisionLedger } = useSimStore();
  const [currentIndex, setCurrentIndex] = useState(0);

  if (!judgeReplayOpen) return null;

  const critical = decisionLedger.filter(d => d.scenario_type && d.scenario_type !== 'routine');
  const allDecisions = critical.length > 0 ? critical : decisionLedger.slice(-5);

  if (allDecisions.length === 0) {
    return (
      <div className="modal-overlay" onClick={closeJudgeReplay}>
        <div className="modal-content" onClick={e => e.stopPropagation()}>
          <div className="modal-header">
            <span>DECISION REPLAY</span>
            <button className="modal-close" onClick={closeJudgeReplay}>✕</button>
          </div>
          <p style={{ color: 'var(--text-secondary)' }}>No decisions recorded yet. Start a simulation first.</p>
        </div>
      </div>
    );
  }

  const current = allDecisions[Math.min(currentIndex, allDecisions.length - 1)];

  return (
    <div className="modal-overlay" onClick={closeJudgeReplay}>
      <div className="modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: 650 }}>
        <div className="modal-header">
          <span>DECISION REPLAY</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span className="replay-counter">
              {currentIndex + 1} / {allDecisions.length}
            </span>
            <button className="modal-close" onClick={closeJudgeReplay}>✕</button>
          </div>
        </div>

        <div className="replay-decision-card">
          <div className="replay-number">Decision #{currentIndex + 1}</div>
          <div className="replay-action">{current.action}</div>
          <span className="scenario-badge">{(current.scenario_type || 'routine').replace(/_/g, ' ')}</span>

          <div className="tradeoff-row">
            <div className="tradeoff-chosen">
              <div className="tradeoff-label" style={{ color: 'var(--accent-green)' }}>✓ CHOSEN</div>
              <div style={{ fontSize: 12, color: 'var(--text-primary)', marginTop: 4 }}>{current.action}</div>
              <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 4 }}>
                Confidence: {((current.confidence || 0) * 100).toFixed(0)}%
              </div>
            </div>
            <div className="tradeoff-rejected">
              <div className="tradeoff-label" style={{ color: 'var(--accent-red)' }}>✗ REJECTED</div>
              <div style={{ fontSize: 12, color: 'var(--text-primary)', marginTop: 4 }}>
                {current.alternative_considered || 'No alternative'}
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 4 }}>
                {current.alternative_rejected_because}
              </div>
            </div>
          </div>

          {current.predicted_outcome && (
            <div style={{ marginTop: 12, padding: 10, background: 'var(--bg-tertiary)', borderRadius: 4 }}>
              <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 4 }}>PREDICTED OUTCOME</div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{current.predicted_outcome}</div>
              {current.actual_outcome && (
                <>
                  <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 8, marginBottom: 4 }}>ACTUAL OUTCOME</div>
                  <div style={{ fontSize: 11, color: 'var(--accent-green)' }}>{current.actual_outcome}</div>
                </>
              )}
            </div>
          )}

          {(current.gemini_explanation || current.alternative_rejected_because) && (
            <div style={{ marginTop: 12 }}>
              <span className="agent-tag commander">COMMANDER</span>
              <p className="commander-explanation" style={{ marginTop: 6 }}>
                {current.gemini_explanation || current.alternative_rejected_because}
              </p>
            </div>
          )}
        </div>

        <div className="replay-nav">
          <button
            className="btn"
            onClick={() => setCurrentIndex(i => Math.max(0, i - 1))}
            disabled={currentIndex === 0}
          >
            ← PREV
          </button>
          <button
            className="btn btn-primary"
            onClick={() => setCurrentIndex(i => Math.min(allDecisions.length - 1, i + 1))}
            disabled={currentIndex >= allDecisions.length - 1}
          >
            NEXT →
          </button>
        </div>
      </div>
    </div>
  );
}

export function AfterAction() {
  const { afterActionOpen, closeAfterAction, afterActionReport, metrics } = useSimStore();

  if (!afterActionOpen) return null;

  const report = afterActionReport || {};
  const m = report.metrics || metrics;

  return (
    <div className="modal-overlay" onClick={closeAfterAction}>
      <div className="modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: 700 }}>
        <div className="modal-header">
          <span>⬡ CRISISOS — CRISIS RESPONSE REPORT</span>
          <button className="modal-close" onClick={closeAfterAction}>✕</button>
        </div>

        <div className="report-section">
          <div className="report-section-title">CASUALTY SUMMARY</div>
          <div className="report-stat-grid">
            <div className="report-stat">
              <div className="report-stat-value" style={{ color: 'var(--text-primary)' }}>{m.victims_total || 0}</div>
              <div className="report-stat-label">Total Victims</div>
            </div>
            <div className="report-stat">
              <div className="report-stat-value" style={{ color: 'var(--accent-green)' }}>{m.victims_rescued || 0}</div>
              <div className="report-stat-label">Rescued</div>
            </div>
            <div className="report-stat">
              <div className="report-stat-value" style={{ color: 'var(--accent-red)' }}>{m.victims_deceased || 0}</div>
              <div className="report-stat-label">Casualties</div>
            </div>
            <div className="report-stat">
              <div className="report-stat-value" style={{ color: 'var(--accent-cyan)' }}>
                {m.victims_total > 0 ? ((m.victims_rescued / m.victims_total) * 100).toFixed(1) : 0}%
              </div>
              <div className="report-stat-label">Survival Rate</div>
            </div>
          </div>
        </div>

        <div className="report-section">
          <div className="report-section-title">DECISION ANALYSIS</div>
          <div className="report-stat-grid">
            <div className="report-stat">
              <div className="report-stat-value" style={{ color: 'var(--accent-cyan)' }}>{m.decisions_made || 0}</div>
              <div className="report-stat-label">Total Decisions</div>
            </div>
            <div className="report-stat">
              <div className="report-stat-value" style={{ color: 'var(--accent-purple)' }}>{m.conflicts_resolved || 0}</div>
              <div className="report-stat-label">Conflicts Resolved</div>
            </div>
          </div>
        </div>

        {report.text && (
          <div className="report-section">
            <div className="report-section-title">AI ANALYSIS</div>
            <div className="report-narrative">{report.text}</div>
          </div>
        )}

        {report.weather && (
          <div className="report-section">
            <div className="report-section-title">WEATHER CONDITIONS</div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', fontFamily: "'JetBrains Mono', monospace" }}>
              Wind: {report.weather.wind_speed}km/h @ {report.weather.wind_direction}° |
              Temp: {report.weather.temperature}°C |
              Rain: {report.weather.precipitation}mm
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
