import { create } from 'zustand';

const useSimStore = create((set, get) => ({
  // ── Connection ────────────────────────────────────────────────────
  wsConnected: false,
  ws: null,

  // ── Simulation ────────────────────────────────────────────────────
  simPhase: 'standby', // standby | active | paused | ended
  tick: 0,
  elapsedSeconds: 0,

  // ── Map Data ──────────────────────────────────────────────────────
  disasters: [],
  blockedRoads: [],
  vehicles: [],
  victims: [],
  hospitals: [],
  activeRoutes: [],

  // ── Agent Activity (right panel) ──────────────────────────────────
  activeDecision: null,
  activityLog: [],
  predictionAlerts: [],

  // ── Decision Ledger (Judge Replay) ────────────────────────────────
  decisionLedger: [],

  // ── Metrics ───────────────────────────────────────────────────────
  metrics: {
    victims_total: 0,
    victims_rescued: 0,
    victims_deceased: 0,
    victims_critical_active: 0,
    casualties_avoided: 0,
    baseline_casualties: 0,
    ambulances_deployed: 0,
    decisions_made: 0,
    conflicts_resolved: 0,
    human_overrides: 0,
    human_override_warnings_accepted: 0,
  },

  // ── UI State ──────────────────────────────────────────────────────
  humanOverrideActive: false,
  overrideWarning: null,
  judgeReplayOpen: false,
  afterActionOpen: false,
  afterActionReport: null,

  // ── Actions ───────────────────────────────────────────────────────

  setWs: (ws) => set({ ws }),
  setConnected: (connected) => set({ wsConnected: connected }),

  handleWSMessage: (message) => {
    const { type, data, tick } = message;
    const state = get();

    switch (type) {
      case 'initial_state':
        set({
          victims: data.victims || [],
          vehicles: data.vehicles || [],
          hospitals: data.hospitals || [],
          disasters: data.disasters || [],
          metrics: data.metrics || state.metrics,
          tick: data.simulation?.tick || 0,
          simPhase: data.simulation?.running ? 'active' : 'standby',
        });
        break;

      case 'sim_started':
        set({
          simPhase: 'active',
          tick: tick || 0,
          hospitals: data.city?.hospitals || state.hospitals,
          vehicles: data.city?.vehicles || state.vehicles,
          activityLog: [{
            id: `log-start`,
            timestamp: new Date().toLocaleTimeString('en-US', { hour12: false }),
            agent: 'SYSTEM',
            message: 'Simulation started — all agents activated',
            tick: 0,
          }, ...state.activityLog].slice(0, 50),
        });
        break;

      case 'sim_paused':
        set({ simPhase: 'paused' });
        break;

      case 'sim_ended':
        set({
          simPhase: 'ended',
          metrics: data.final_metrics || state.metrics,
        });
        break;

      case 'sim_tick':
        set({ tick: data.tick, elapsedSeconds: data.elapsed_seconds });
        break;

      case 'disaster_triggered': {
        const disaster = data.disaster;
        set({
          disasters: [...state.disasters, disaster],
          activityLog: [{
            id: `log-${Date.now()}-disaster`,
            timestamp: formatTick(tick),
            agent: 'SYSTEM',
            message: `🔴 ${disaster.name}`,
            tick,
            color: '#FF4444',
          }, ...state.activityLog].slice(0, 50),
        });
        break;
      }

      case 'road_blocked':
        set({
          blockedRoads: [...state.blockedRoads, data],
          activityLog: [{
            id: `log-${Date.now()}-road`,
            timestamp: formatTick(tick),
            agent: 'INTELLIGENCE',
            message: `Road blocked: ${data.name || data.edge_id}`,
            tick,
            color: '#3B82F6',
          }, ...state.activityLog].slice(0, 50),
        });
        break;

      case 'fire_spreading':
        set({
          disasters: state.disasters.map(d =>
            d.id === data.disaster_id
              ? { ...d, spread_radius: data.new_radius, severity: data.severity }
              : d
          ),
        });
        break;

      case 'hospital_status_change':
        set({
          hospitals: state.hospitals.map(h =>
            h.id === data.hospital_id
              ? { ...h, capacity_percent: data.capacity_percent, status: data.status }
              : h
          ),
        });
        break;

      case 'victim_spawned':
        set({
          victims: [...state.victims, data],
        });
        break;

      case 'victim_status_changed':
        set({
          victims: state.victims.map(v =>
            v.id === data.victim_id ? { ...v, status: data.status } : v
          ),
        });
        break;

      case 'victim_rescued':
        set({
          victims: state.victims.map(v =>
            v.id === data.victim_id ? { ...v, status: 'rescued' } : v
          ),
          activityLog: [{
            id: `log-${Date.now()}-rescue`,
            timestamp: formatTick(tick || data.tick),
            agent: 'MEDICAL',
            message: `✅ Victim ${data.victim_id} rescued`,
            tick: tick || data.tick,
            color: '#00FF88',
          }, ...state.activityLog].slice(0, 50),
        });
        break;

      case 'victim_deceased':
        set({
          victims: state.victims.map(v =>
            v.id === data.victim_id ? { ...v, status: 'deceased' } : v
          ),
          activityLog: [{
            id: `log-${Date.now()}-deceased`,
            timestamp: formatTick(tick || data.tick),
            agent: 'MEDICAL',
            message: `💀 Victim ${data.victim_id} (sev ${data.severity}) deceased near ${data.landmark || 'unknown'}`,
            tick: tick || data.tick,
            color: '#FF4444',
          }, ...state.activityLog].slice(0, 50),
        });
        break;

      case 'vehicle_moved': {
        const newStatus = data.status;
        const clearRoute = newStatus === 'on_scene' || newStatus === 'returning' || newStatus === 'available';
        set({
          vehicles: state.vehicles.map(v =>
            v.id === data.vehicle_id
              ? { ...v, location: data.location, status: data.status }
              : v
          ),
          ...(clearRoute ? {
            activeRoutes: state.activeRoutes.filter(r => r.vehicle_id !== data.vehicle_id),
          } : {}),
        });
        break;
      }

      case 'vehicle_assigned':
        set({
          vehicles: state.vehicles.map(v =>
            v.id === data.vehicle_id
              ? {
                  ...v,
                  assignedRoute: data.route || [],
                  routeStartTick: tick || state.tick,
                  estimatedTicks: (data.estimated_seconds || 0) / 2,
                  assignedVictim: data.target_victim_id,
                }
              : v
          ),
          activeRoutes: [...state.activeRoutes.filter(r => r.vehicle_id !== data.vehicle_id), {
            vehicle_id: data.vehicle_id,
            target_victim_id: data.target_victim_id,
            route: data.route,
          }],
          activityLog: [{
            id: `log-${Date.now()}-assign`,
            timestamp: formatTick(tick),
            agent: 'LOGISTICS',
            message: `🚑 ${data.vehicle_id} dispatched to ${data.target_victim_id}`,
            tick,
            color: '#FFB020',
          }, ...state.activityLog].slice(0, 50),
        });
        break;

      case 'vehicle_rerouted':
        set({
          vehicles: state.vehicles.map(v =>
            v.id === data.vehicle_id
              ? {
                  ...v,
                  assignedRoute: data.new_route || v.assignedRoute,
                  routeStartTick: tick || state.tick,
                  rerouteFlash: true,
                }
              : v
          ),
          activeRoutes: state.activeRoutes.map(r =>
            r.vehicle_id === data.vehicle_id
              ? { ...r, route: data.new_route || r.route, rerouted: true }
              : r
          ),
          activityLog: [{
            id: `log-${Date.now()}-reroute`,
            timestamp: formatTick(tick),
            agent: 'LOGISTICS',
            message: `🔄 ${data.vehicle_id} rerouted: ${data.reason}`,
            tick,
            color: '#FFB020',
          }, ...state.activityLog].slice(0, 50),
        });
        // Clear reroute flash after 2 seconds
        setTimeout(() => {
          const s = get();
          set({
            vehicles: s.vehicles.map(v =>
              v.id === data.vehicle_id ? { ...v, rerouteFlash: false } : v
            ),
            activeRoutes: s.activeRoutes.map(r =>
              r.vehicle_id === data.vehicle_id ? { ...r, rerouted: false } : r
            ),
          });
        }, 2000);
        break;

      case 'agent_proposal':
        set({
          activityLog: [{
            id: `log-${Date.now()}-prop`,
            timestamp: formatTick(tick || data.tick),
            agent: data.agent,
            message: data.proposal?.action || 'Proposal submitted',
            tick: tick || data.tick,
          }, ...state.activityLog].slice(0, 50),
        });
        break;

      case 'conflict_detected':
        set({
          activityLog: [{
            id: `log-${Date.now()}-conflict`,
            timestamp: formatTick(tick),
            agent: 'COMMANDER',
            message: `⚡ Conflict detected: ${data.conflict?.description || 'Agent disagreement'}`,
            tick,
            color: '#FF4444',
          }, ...state.activityLog].slice(0, 50),
        });
        break;

      case 'decision_made': {
        const decision = data.decision;
        set({
          activeDecision: decision,
          decisionLedger: [...state.decisionLedger, decision],
          activityLog: [{
            id: `log-${Date.now()}-decision`,
            timestamp: formatTick(decision.tick || tick),
            agent: 'COMMANDER',
            message: `⚖ Decision: ${decision.action}`,
            tick: decision.tick || tick,
            color: '#00D4FF',
          }, ...state.activityLog].slice(0, 50),
        });
        break;
      }

      case 'decision_explanation_ready':
        set({
          activeDecision: state.activeDecision?.id === data.decision_id
            ? { ...state.activeDecision, gemini_explanation: data.explanation }
            : state.activeDecision,
          decisionLedger: state.decisionLedger.map(d =>
            d.id === data.decision_id
              ? { ...d, gemini_explanation: data.explanation }
              : d
          ),
        });
        break;

      case 'prediction_alert':
        set({
          predictionAlerts: [data.alert, ...state.predictionAlerts].slice(0, 10),
        });
        break;

      case 'metrics_update':
        set({
          metrics: data.metrics,
          tick: tick || state.tick,
          elapsedSeconds: (tick || state.tick) * 2,
        });
        break;

      case 'override_warning':
        set({ overrideWarning: data });
        break;

      case 'report_ready':
        set({
          afterActionReport: data.report,
          afterActionOpen: true,
        });
        break;

      case 'judge_replay_data':
        set({
          decisionLedger: data.decisions || state.decisionLedger,
          judgeReplayOpen: true,
        });
        break;

      default:
        break;
    }
  },

  // ── UI Actions ────────────────────────────────────────────────────

  sendCommand: (type, data = {}) => {
    const ws = get().ws;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type, data }));
    }
  },

  startSimulation: () => {
    get().sendCommand('start_simulation');
  },

  pauseSimulation: () => {
    get().sendCommand('pause_simulation');
  },

  resumeSimulation: () => {
    get().sendCommand('resume_simulation');
  },

  sendHumanCommand: (action, target, params = {}) => {
    get().sendCommand('human_command', { action, target, params });
  },

  confirmOverride: () => {
    get().sendCommand('override_confirm');
    set({ overrideWarning: null });
  },

  cancelOverride: () => {
    set({ overrideWarning: null });
  },

  requestJudgeReplay: () => {
    get().sendCommand('request_judge_replay');
    set({ judgeReplayOpen: true });
  },

  requestAfterAction: () => {
    get().sendCommand('request_after_action');
  },

  toggleHumanOverride: () => {
    set(s => ({ humanOverrideActive: !s.humanOverrideActive }));
  },

  closeJudgeReplay: () => set({ judgeReplayOpen: false }),
  closeAfterAction: () => set({ afterActionOpen: false }),
  closeOverrideWarning: () => set({ overrideWarning: null }),
}));

// ── Helpers ─────────────────────────────────────────────────────────────

function formatTick(tick) {
  const seconds = (tick || 0) * 2;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

export default useSimStore;
