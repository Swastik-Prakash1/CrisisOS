import React from 'react';
import useSimStore from '../../store/useSimStore';

export default function BottomBar() {
  const { metrics, simPhase } = useSimStore();

  const items = [
    { label: 'Victims', value: metrics.victims_total, color: 'var(--text-primary)' },
    { label: 'Rescued', value: metrics.victims_rescued, color: 'var(--accent-green)' },
    { label: 'Critical', value: metrics.victims_critical_active, color: 'var(--accent-amber)' },
    { label: 'Casualties', value: metrics.victims_deceased, color: 'var(--accent-red)' },
    { label: 'Decisions', value: metrics.decisions_made, color: 'var(--accent-cyan)' },
    { label: 'Conflicts', value: metrics.conflicts_resolved, color: 'var(--accent-purple)' },
  ];

  return (
    <div className="bottom-bar">
      {items.map((item, i) => (
        <React.Fragment key={item.label}>
          {i > 0 && <div className="metric-divider" />}
          <div className="metric-item">
            <span className="metric-label">{item.label}</span>
            <span className="metric-value font-mono" style={{ color: item.color }}>
              {item.value}
            </span>
          </div>
        </React.Fragment>
      ))}
    </div>
  );
}
