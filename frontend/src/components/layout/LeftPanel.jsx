import React from 'react';
import useSimStore from '../../store/useSimStore';

const INCIDENT_ICONS = {
  earthquake: '🔴',
  fire: '🔥',
  road_collapse: '🚧',
  hospital_overload: '🏥',
};

const SEVERITY_CLASS = (severity) => {
  if (severity >= 0.8) return 'critical';
  if (severity >= 0.5) return 'moderate';
  return 'monitored';
};

function IncidentList() {
  const { disasters, tick } = useSimStore();
  const active = disasters.filter(d => d.active !== false);

  return (
    <div className="panel-section">
      <div className="section-header">
        <span>ACTIVE INCIDENTS</span>
        <span className="count">{active.length}</span>
      </div>
      {active.length === 0 ? (
        <div style={{ color: 'var(--text-tertiary)', fontSize: 11, fontStyle: 'italic' }}>
          No active incidents
        </div>
      ) : (
        active.map(d => {
          const elapsed = ((tick || 0) - (d.tick_started || 0)) * 2;
          const m = Math.floor(elapsed / 60);
          const s = elapsed % 60;
          return (
            <div key={d.id} className={`incident-item ${SEVERITY_CLASS(d.severity)}`}>
              <span className="incident-icon">{INCIDENT_ICONS[d.type] || '⚠'}</span>
              <div className="incident-info">
                <div className="incident-name">{d.name || d.type}</div>
                <div className="incident-meta">
                  <span className={`badge badge-${SEVERITY_CLASS(d.severity)}`} style={{ marginRight: 6 }}>
                    {d.severity >= 0.8 ? 'CRITICAL' : d.severity >= 0.5 ? 'MAJOR' : 'MODERATE'}
                  </span>
                  {m > 0 ? `${m}m ${s}s ago` : `${s}s ago`}
                </div>
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}

function ResourceStatus() {
  const { vehicles } = useSimStore();

  const ambulances = vehicles.filter(v => v.type === 'ambulance');
  const firetrucks = vehicles.filter(v => v.type === 'fire_truck');

  return (
    <div className="panel-section">
      <div className="section-header">
        <span>RESOURCE STATUS</span>
        <span className="count">{vehicles.length}</span>
      </div>
      <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 6, fontFamily: "'JetBrains Mono', monospace", letterSpacing: '0.5px' }}>
        AMBULANCES
      </div>
      {ambulances.map(v => (
        <div key={v.id} className="resource-item">
          <span className={`resource-dot ${v.status}`} />
          <span className="resource-id">{v.id}</span>
          <span className="resource-status">{v.status.replace('_', ' ')}</span>
          {v.assigned_victim && (
            <span style={{ color: 'var(--accent-cyan)', fontSize: 9, marginLeft: 'auto' }}>
              → {v.assigned_victim}
            </span>
          )}
        </div>
      ))}
      <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 8, marginBottom: 6, fontFamily: "'JetBrains Mono', monospace", letterSpacing: '0.5px' }}>
        FIRE TRUCKS
      </div>
      {firetrucks.map(v => (
        <div key={v.id} className="resource-item">
          <span className={`resource-dot ${v.status}`} />
          <span className="resource-id">{v.id}</span>
          <span className="resource-status">{v.status.replace('_', ' ')}</span>
        </div>
      ))}
    </div>
  );
}

function HospitalCapacity() {
  const { hospitals } = useSimStore();

  const getBarClass = (pct) => {
    if (pct >= 85) return 'critical';
    if (pct >= 70) return 'warning';
    return 'ok';
  };

  return (
    <div className="panel-section">
      <div className="section-header">
        <span>HOSPITAL CAPACITY</span>
      </div>
      {hospitals.map(h => {
        const pct = h.capacity_percent || 0;
        return (
          <div key={h.id} className="hospital-item">
            <div className="hospital-header">
              <span className="hospital-name">{h.id} {h.name}</span>
              <span className="hospital-pct" style={{
                color: pct >= 85 ? 'var(--accent-red)' : pct >= 70 ? 'var(--accent-amber)' : 'var(--accent-green)'
              }}>
                {pct.toFixed(0)}%
              </span>
            </div>
            <div className="progress-bar">
              <div
                className={`progress-bar-fill ${getBarClass(pct)}`}
                style={{ width: `${Math.min(100, pct)}%` }}
              />
            </div>
            {h.status && h.status !== 'ok' && (
              <span className={`badge badge-${h.status === 'critical' || h.status === 'overloaded' ? 'critical' : 'warning'}`}
                    style={{ marginTop: 4, display: 'inline-block' }}>
                {h.status.toUpperCase()}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default function LeftPanel() {
  return (
    <div className="left-panel">
      <IncidentList />
      <ResourceStatus />
      <HospitalCapacity />
    </div>
  );
}
