import React from 'react';
import useSimStore from '../../store/useSimStore';

export default function Header() {
  const {
    simPhase, tick, wsConnected,
    startSimulation, pauseSimulation, resumeSimulation,
    toggleHumanOverride, humanOverrideActive,
    requestJudgeReplay, requestAfterAction,
  } = useSimStore();

  const elapsed = tick * 2;
  const minutes = Math.floor(elapsed / 60);
  const seconds = elapsed % 60;
  const timer = `T+${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;

  const statusConfig = {
    standby: { label: 'STANDBY', dotClass: 'amber', textColor: '#FFB020' },
    active: { label: 'DISASTER ACTIVE', dotClass: 'red', textColor: '#FF4444' },
    paused: { label: 'PAUSED', dotClass: 'amber', textColor: '#FFB020' },
    ended: { label: 'SIMULATION ENDED', dotClass: 'cyan', textColor: '#00D4FF' },
  };

  const status = statusConfig[simPhase] || statusConfig.standby;
  const isActive = simPhase === 'active';

  // Override phase for UI: show "SYSTEM ACTIVE" before any disaster
  const displayStatus = simPhase === 'active' && tick < 15
    ? { label: 'SYSTEM ACTIVE', dotClass: 'green', textColor: '#00FF88' }
    : status;

  return (
    <header className="header">
      <div className="header-logo">
        <span className="hex">⬡</span>
        <span>CrisisOS</span>
        <span className="version">v1.0</span>
      </div>

      <div className="header-center">
        <div className="system-status">
          <span className={`status-dot ${displayStatus.dotClass}`} />
          <span style={{ color: displayStatus.textColor }}>{displayStatus.label}</span>
          {!wsConnected && (
            <span style={{ color: '#FF4444', marginLeft: 8, fontSize: 9 }}>● OFFLINE</span>
          )}
        </div>

        <div className="sim-timer font-mono">{timer}</div>
      </div>

      <div className="header-controls">
        {simPhase === 'standby' && (
          <button className="btn btn-primary" onClick={startSimulation}>
            ▶ START SIM
          </button>
        )}
        {simPhase === 'active' && (
          <button className="btn btn-amber" onClick={pauseSimulation}>
            ⏸ PAUSE
          </button>
        )}
        {simPhase === 'paused' && (
          <button className="btn btn-primary" onClick={resumeSimulation}>
            ▶ RESUME
          </button>
        )}
        <button
          className={`btn ${humanOverrideActive ? 'btn-danger' : ''}`}
          onClick={toggleHumanOverride}
        >
          👤 {humanOverrideActive ? 'EXIT OVERRIDE' : 'HUMAN OVERRIDE'}
        </button>
        <button className="btn" onClick={requestJudgeReplay}>
          🔄 REPLAY
        </button>
        <button className="btn" onClick={requestAfterAction}>
          📊 REPORT
        </button>
      </div>
    </header>
  );
}
