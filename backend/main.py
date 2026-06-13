"""
CrisisOS — Main Entry Point
FastAPI application with full simulation loop, agent orchestration,
WebSocket hub, and REST API.
"""

import asyncio
import json
import sys
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from config import (
    HOST,
    PORT,
    CORS_ORIGINS,
    TICK_INTERVAL_SECONDS,
    SIMULATION_DURATION_TICKS,
    AGENT_CYCLE_INTELLIGENCE,
    AGENT_CYCLE_LOGISTICS,
    AGENT_CYCLE_MEDICAL,
    AGENT_CYCLE_PREDICTION,
    AGENT_CYCLE_COMMANDER,
    WS_EVENTS,
)
from simulation.city import SimulationState
from simulation.victims import VictimManager
from simulation.disaster import DisasterEngine
from simulation.vehicles import VehicleManager
from agents.intelligence import IntelligenceAgent
from agents.logistics import LogisticsAgent
from agents.medical import MedicalAgent
from agents.prediction import PredictionAgent
from agents.commander import CommanderAgent
from engine.decision_ledger import DecisionLedger
from engine.conflict_engine import ConflictEngine
from engine.gemini_explainer import GeminiExplainer


# ── Global State ─────────────────────────────────────────────────────────────
state = SimulationState()
victim_manager = VictimManager(state)
disaster_engine = DisasterEngine(state, victim_manager)
vehicle_manager = VehicleManager(state)

# Agents
intel_agent = IntelligenceAgent(state)
logistics_agent = LogisticsAgent(state)
medical_agent = MedicalAgent(state)
prediction_agent = PredictionAgent(state)
commander_agent = CommanderAgent(state)

# Engine
decision_ledger = DecisionLedger()
decision_ledger.set_state(state)
conflict_engine = ConflictEngine(state, victim_manager, disaster_engine)
gemini_explainer = GeminiExplainer(state)

# WebSocket connection manager
connected_clients: list[WebSocket] = []

# Simulation task reference
sim_task: asyncio.Task = None


# ── WebSocket Broadcasting ───────────────────────────────────────────────────

async def broadcast(message: dict):
    """Broadcast a message to all connected WebSocket clients."""
    if not connected_clients:
        return
    data = json.dumps(message, default=str)
    disconnected = []
    for ws in connected_clients:
        try:
            await ws.send_text(data)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        if ws in connected_clients:
            connected_clients.remove(ws)


async def event_broadcaster():
    """Background task: drain the event queue and broadcast to all clients."""
    while True:
        try:
            if state.has_events():
                event = await asyncio.wait_for(state.get_event(), timeout=0.1)
                await broadcast(event)
            else:
                await asyncio.sleep(0.05)
        except asyncio.TimeoutError:
            await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            break
        except Exception as e:
            await asyncio.sleep(0.1)


# ── Agent Orchestration ──────────────────────────────────────────────────────

async def run_agent_cycle():
    """
    Run agent decision cycles based on configured intervals.
    Each agent runs at its own frequency (Intel fastest, Prediction slowest).
    Commander collects all proposals and arbitrates.
    """
    tick = state.tick
    all_proposals = []

    # Intelligence Agent — every 3 ticks (6s)
    if tick % AGENT_CYCLE_INTELLIGENCE == 0:
        try:
            proposals = intel_agent.propose()
            all_proposals.extend(proposals)
            for p in proposals:
                await state.emit_event(WS_EVENTS["AGENT_PROPOSAL"], {
                    "agent": p.agent_name,
                    "proposal": p.to_dict(),
                    "tick": tick,
                })
        except Exception as e:
            print(f"  ⚠ Intelligence agent error: {e}")

    # Medical Agent — every 5 ticks (10s)
    if tick % AGENT_CYCLE_MEDICAL == 0:
        try:
            proposals = medical_agent.propose()
            all_proposals.extend(proposals)
            for p in proposals:
                await state.emit_event(WS_EVENTS["AGENT_PROPOSAL"], {
                    "agent": p.agent_name,
                    "proposal": p.to_dict(),
                    "tick": tick,
                })
        except Exception as e:
            print(f"  ⚠ Medical agent error: {e}")

    # Logistics Agent — every 4 ticks (8s)
    if tick % AGENT_CYCLE_LOGISTICS == 0:
        try:
            proposals = logistics_agent.propose()
            all_proposals.extend(proposals)
            for p in proposals:
                await state.emit_event(WS_EVENTS["AGENT_PROPOSAL"], {
                    "agent": p.agent_name,
                    "proposal": p.to_dict(),
                    "tick": tick,
                })
        except Exception as e:
            print(f"  ⚠ Logistics agent error: {e}")

    # Prediction Agent — every 8 ticks (16s)
    if tick % AGENT_CYCLE_PREDICTION == 0:
        try:
            proposals = prediction_agent.propose()
            all_proposals.extend(proposals)
            for p in proposals:
                await state.emit_event(WS_EVENTS["AGENT_PROPOSAL"], {
                    "agent": p.agent_name,
                    "proposal": p.to_dict(),
                    "tick": tick,
                })
        except Exception as e:
            print(f"  ⚠ Prediction agent error: {e}")

    # Commander Agent — every 4 ticks (8s), arbitrates collected proposals
    if tick % AGENT_CYCLE_COMMANDER == 0 and all_proposals:
        try:
            commander_agent.receive_proposals(all_proposals)
            decisions = commander_agent.arbitrate()

            for decision in decisions:
                # Log to ledger
                await decision_ledger.log(decision)

                # Execute the decision (dispatch vehicles, etc.)
                await execute_decision(decision)

                # Request async Gemini explanation for non-routine decisions
                if decision.scenario_type != "routine":
                    asyncio.create_task(
                        explain_decision_async(decision)
                    )
        except Exception as e:
            print(f"  ⚠ Commander agent error: {e}")


async def execute_decision(decision):
    """
    Execute a Commander decision — dispatch vehicles, update state.
    """
    # Find the winning proposal's metadata
    winner_meta = None
    for p in decision.proposals:
        p_dict = p if isinstance(p, dict) else p
        if p_dict.get("agent_name") == decision.agent_winner:
            winner_meta = p_dict.get("metadata", {})
            break

    if not winner_meta:
        return

    action_type = winner_meta.get("type", "")

    if action_type == "dispatch" or action_type == "rescue":
        vehicle_id = winner_meta.get("vehicle_id")
        victim_id = winner_meta.get("victim_id")
        victim_loc = winner_meta.get("victim_location")

        if vehicle_id and victim_id and victim_loc:
            vehicle = state.get_vehicle(vehicle_id)
            victim = state.get_victim(victim_id)

            if vehicle and victim and vehicle.status == "available" and victim.status == "waiting":
                # Assign vehicle to victim
                victim.status = "en_route"
                victim.assigned_vehicle = vehicle_id

                # Generate route
                route = await logistics_agent.find_optimal_route(vehicle.location, victim.location)
                if not route:
                    route = vehicle_manager.generate_simple_route(vehicle.location, victim.location)

                vehicle_manager.assign_route(vehicle_id, route, victim_id)

                await state.emit_event(WS_EVENTS["VEHICLE_ASSIGNED"], {
                    "vehicle_id": vehicle_id,
                    "target_victim_id": victim_id,
                    "route": route,
                    "estimated_seconds": winner_meta.get("eta_seconds", 60),
                })

                print(f"  🚑 DISPATCH: {vehicle_id} → {victim_id} near {victim.nearest_landmark}")


async def explain_decision_async(decision):
    """Non-blocking Gemini explanation request."""
    try:
        snapshot = state.compact_snapshot()
        explanation = await gemini_explainer.explain_decision(decision, snapshot)
        decision.gemini_explanation = explanation
    except Exception as e:
        print(f"  ⚠ Gemini explanation error: {e}")


# ── Simulation Loop ─────────────────────────────────────────────────────────

async def simulation_loop():
    """
    Main simulation loop. Orchestrates:
    disasters → conflict engine → victim countdowns → agents → vehicles → metrics
    """
    print("\n" + "═" * 70)
    print("  ⬡ CrisisOS — Simulation Engine v1.0")
    print("═" * 70)
    print(f"  City: Delhi | Tick interval: {TICK_INTERVAL_SECONDS}s")
    print(f"  Vehicles: {len(state.vehicles)} | Hospitals: {len(state.hospitals)}")
    print(f"  Agents: INTEL, MEDICAL, LOGISTICS, PREDICTION, COMMANDER")
    print(f"  Gemini: {'Online' if gemini_explainer.is_available else 'Fallback mode'}")
    print("═" * 70 + "\n")

    # Load weather data at start
    await prediction_agent.load_weather_context()

    # Emit simulation start
    await state.emit_event(
        WS_EVENTS["SIM_STARTED"],
        {
            "tick": 0,
            "city": {
                "name": "Delhi",
                "center": {"lat": 28.6139, "lng": 77.2090},
                "hospitals": [h.to_dict() for h in state.hospitals],
                "vehicles": [v.to_dict() for v in state.vehicles],
            },
        },
    )

    while state.running and not state.paused:
        tick_start = time.time()

        try:
            # Advance tick
            state.advance_tick()

            # ── Phase 1: Process disasters ──
            await disaster_engine.tick()

            # ── Phase 2: Process conflict scenarios ──
            await conflict_engine.tick()

            # Fallback: force conflict scenarios if they haven't triggered
            if state.tick == 38 and not conflict_engine._road_sacrifice_triggered:
                print("  ⚠ Road Sacrifice missed — forcing at tick 38")
                await conflict_engine.force_scenario("road_sacrifice")
            if state.tick == 67 and not conflict_engine._resource_exhaustion_triggered:
                print("  ⚠ Resource Exhaustion missed — forcing at tick 67")
                await conflict_engine.force_scenario("resource_exhaustion")

            # Drain injected conflict proposals → feed directly to Commander
            injected = getattr(conflict_engine, '_injected_proposals', [])
            if injected:
                conflict_engine._injected_proposals = []
                print(f"  ⚡ Injecting {len(injected)} conflict proposals into Commander")
                commander_agent.receive_proposals(injected)
                decisions = commander_agent.arbitrate()
                for decision in decisions:
                    await decision_ledger.log(decision)
                    await execute_decision(decision)
                    if decision.scenario_type != "routine":
                        asyncio.create_task(explain_decision_async(decision))
                    print(f"  ⚖ CONFLICT DECISION: {decision.action} (conf: {decision.confidence:.0%}, scenario: {decision.scenario_type})")

            # ── Phase 3: Tick victim countdowns ──
            deceased = await victim_manager.tick_countdowns()
            if deceased:
                for v in deceased:
                    print(f"  💀 Victim {v.id} (sev {v.severity}) deceased near {v.nearest_landmark}")

            # ── Phase 4: Run agent decision cycles ──
            await run_agent_cycle()

            # ── Phase 5: Move vehicles ──
            await vehicle_manager.tick()

            # ── Phase 6: Update metrics ──
            state.update_metrics()

            # ── Phase 7: Broadcast metrics ──
            await state.emit_event(
                WS_EVENTS["METRICS_UPDATE"],
                {"metrics": state.metrics.to_dict()},
            )

            # ── Console Status (every 5 ticks) ──
            if state.tick % 5 == 0:
                elapsed = state.elapsed_seconds
                minutes = elapsed // 60
                seconds = elapsed % 60
                waiting = sum(1 for v in state.victims if v.status == "waiting")
                en_route = sum(1 for v in state.victims if v.status == "en_route")
                rescued = state.metrics.victims_rescued
                dead = state.metrics.victims_deceased
                print(f"\n  ┌─ T+{minutes:02d}:{seconds:02d} [Tick {state.tick}] ─ Phase: {state.phase.upper()}")
                print(f"  │ Victims: {len(state.victims)} total | {waiting} waiting | {en_route} en_route | {rescued} rescued | {dead} deceased")
                print(f"  │ {vehicle_manager.get_status_summary()}")
                print(f"  │ Hospitals: {' | '.join(f'{h.id}:{h.capacity_percent:.0f}%[{h.status}]' for h in state.hospitals)}")
                print(f"  │ Decisions: {state.metrics.decisions_made} total | {state.metrics.conflicts_resolved} conflicts")
                print(f"  │ Conflicts triggered: {conflict_engine._scenarios_executed}")
                if prediction_agent.active_alerts:
                    print(f"  │ Alerts: {len(prediction_agent.active_alerts)} active predictions")
                print(f"  └─────────────────────────────────────────")

            # ── Check simulation end ──
            if state.tick >= SIMULATION_DURATION_TICKS:
                state.stop()
                await state.emit_event(
                    WS_EVENTS["SIM_ENDED"],
                    {"final_metrics": state.metrics.to_dict()},
                )
                print("\n" + "═" * 70)
                print("  ⬡ SIMULATION COMPLETE")
                print(f"  Total victims: {state.metrics.victims_total}")
                print(f"  Rescued: {state.metrics.victims_rescued}")
                print(f"  Deceased: {state.metrics.victims_deceased}")
                print(f"  Decisions made: {state.metrics.decisions_made}")
                print(f"  Conflicts resolved: {state.metrics.conflicts_resolved}")
                ledger_stats = decision_ledger.get_statistics()
                if ledger_stats.get("total", 0) > 0:
                    print(f"  Avg confidence: {ledger_stats.get('avg_confidence', 0):.0%}")
                    print(f"  Scenario breakdown: {ledger_stats.get('scenario_counts', {})}")
                print("═" * 70 + "\n")
                break

        except Exception as e:
            print(f"[TICK ERROR] Tick {state.tick}: {e}")
            import traceback
            traceback.print_exc()

        # ── Maintain tick rate ──
        tick_elapsed = time.time() - tick_start
        sleep_time = max(0, TICK_INTERVAL_SECONDS - tick_elapsed)
        await asyncio.sleep(sleep_time)


# ── FastAPI Application ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background broadcaster on app startup."""
    broadcaster_task = asyncio.create_task(event_broadcaster())
    yield
    broadcaster_task.cancel()


app = FastAPI(
    title="CrisisOS",
    description="Autonomous Multi-Agent Decision Support for Disaster Response",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",        # local dev
        "http://localhost:3000",        # local dev alt
        "https://*.netlify.app",        # Netlify preview deployments
        # Add your actual Netlify URL after first deploy:
        # "https://crisisos.netlify.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── REST Endpoints ───────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "CrisisOS", "version": "1.0.0"}


@app.get("/state")
async def get_state():
    """Full simulation state snapshot."""
    return state.to_dict()


@app.get("/decisions")
async def get_decisions():
    """Full decision ledger."""
    return {"decisions": decision_ledger.to_dict(), "statistics": decision_ledger.get_statistics()}


@app.get("/decisions/critical")
async def get_critical_decisions():
    """Critical decisions only (for Judge Replay)."""
    return {"decisions": [d.to_dict() for d in decision_ledger.get_critical_decisions()]}


@app.post("/simulation/start")
async def start_simulation():
    """Initialize and start the simulation."""
    global sim_task

    if state.running:
        return {"status": "already_running"}

    state.initialize()
    state.start()

    # Reset engine state
    decision_ledger.decisions = []
    conflict_engine._road_sacrifice_triggered = False
    conflict_engine._resource_exhaustion_triggered = False
    conflict_engine._scenarios_executed = []
    conflict_engine._injected_proposals = []

    sim_task = asyncio.create_task(simulation_loop())
    return {"status": "started", "tick": state.tick}


@app.post("/simulation/pause")
async def pause_simulation():
    """Pause the simulation."""
    if not state.running:
        return {"status": "not_running"}
    state.pause()
    await state.emit_event(WS_EVENTS["SIM_PAUSED"], {"tick": state.tick})
    return {"status": "paused", "tick": state.tick}


@app.post("/simulation/resume")
async def resume_simulation():
    """Resume the simulation."""
    global sim_task
    if not state.running:
        return {"status": "not_running"}
    state.resume()
    sim_task = asyncio.create_task(simulation_loop())
    return {"status": "resumed", "tick": state.tick}


@app.post("/simulation/stop")
async def stop_simulation():
    """Stop the simulation."""
    state.stop()
    if sim_task:
        sim_task.cancel()
    return {"status": "stopped", "tick": state.tick, "metrics": state.metrics.to_dict()}


@app.post("/override")
async def human_override(command: dict):
    """Process a human override command with safety check."""
    action = command.get("action", "")
    target = command.get("target", "")
    params = command.get("params", {})

    # Evaluate command safety
    warning = conflict_engine.evaluate_human_command(action, target, params)

    if warning:
        state.metrics.human_overrides += 1
        await state.emit_event(WS_EVENTS["OVERRIDE_WARNING"], warning)
        return {"status": "warning", "warning": warning}

    return {"status": "safe", "message": "Command approved"}


@app.post("/override/confirm")
async def confirm_override(command: dict):
    """Execute an override command after warning was acknowledged."""
    state.metrics.human_override_warnings_accepted += 1
    # Execute the command
    # (In full implementation, this would modify vehicle assignments)
    return {"status": "executed", "message": "Human override executed"}


@app.get("/report")
async def get_after_action_report():
    """Generate after-action report."""
    ledger_export = decision_ledger.export_for_report()
    final_metrics = state.metrics.to_dict()

    report_text = await gemini_explainer.generate_after_action_report(
        ledger_export, final_metrics
    )

    report = {
        "text": report_text,
        "metrics": final_metrics,
        "statistics": decision_ledger.get_statistics(),
        "weather": state.weather,
    }

    await state.emit_event(WS_EVENTS["REPORT_READY"], {"report": report})
    return report


# ── WebSocket Endpoint ───────────────────────────────────────────────────────

async def websocket_heartbeat(websocket: WebSocket):
    while True:
        try:
            await websocket.send_text(json.dumps({"type": "heartbeat", "tick": state.tick}))
            await asyncio.sleep(5)
        except Exception:
            break  # client disconnected, stop heartbeat

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_clients.append(ws)
    print(f"  📡 WebSocket client connected ({len(connected_clients)} total)")
    asyncio.create_task(websocket_heartbeat(ws))

    try:
        # Send current state on connect
        await ws.send_text(json.dumps({
            "type": "initial_state",
            "data": state.to_dict(),
            "tick": state.tick,
        }, default=str))

        # Listen for client messages
        while True:
            data = await ws.receive_text()
            message = json.loads(data)
            event_type = message.get("type", "")

            if event_type == "start_simulation":
                if not state.running:
                    await start_simulation()

            elif event_type == "pause_simulation":
                await pause_simulation()

            elif event_type == "resume_simulation":
                await resume_simulation()

            elif event_type == "human_command":
                cmd_data = message.get("data", {})
                warning = conflict_engine.evaluate_human_command(
                    cmd_data.get("action", ""),
                    cmd_data.get("target", ""),
                    cmd_data.get("params", {}),
                )
                if warning:
                    state.metrics.human_overrides += 1
                    await ws.send_text(json.dumps({
                        "type": WS_EVENTS["OVERRIDE_WARNING"],
                        "data": warning,
                    }))

            elif event_type == "override_confirm":
                state.metrics.human_override_warnings_accepted += 1
                print(f"  👤 Human override confirmed")

            elif event_type == "request_after_action":
                report = await get_after_action_report()
                await ws.send_text(json.dumps({
                    "type": WS_EVENTS["REPORT_READY"],
                    "data": {"report": report},
                }, default=str))

            elif event_type == "request_judge_replay":
                critical = decision_ledger.get_critical_decisions()
                await ws.send_text(json.dumps({
                    "type": "judge_replay_data",
                    "data": {
                        "decisions": [d.to_dict() for d in critical],
                        "statistics": decision_ledger.get_statistics(),
                    },
                }, default=str))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"  ⚠ WebSocket error: {e}")
    finally:
        if ws in connected_clients:
            connected_clients.remove(ws)
        print(f"  📡 WebSocket client disconnected ({len(connected_clients)} total)")


# ── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    # If --console flag, run simulation without server
    if "--console" in sys.argv:
        print("Running in console mode (no HTTP server)...")
        state.initialize()
        state.start()
        asyncio.run(simulation_loop())
    else:
        print(f"\n  ⬡ CrisisOS Server starting on {HOST}:{PORT}")
        print(f"  WebSocket: ws://{HOST}:{PORT}/ws")
        print(f"  API: http://{HOST}:{PORT}/docs\n")
        uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
