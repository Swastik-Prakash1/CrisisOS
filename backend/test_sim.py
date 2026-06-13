"""Quick test: verify simulation runs, victims spawn, disasters trigger."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from simulation.city import SimulationState
from simulation.victims import VictimManager
from simulation.disaster import DisasterEngine
from simulation.vehicles import VehicleManager

state = SimulationState()
state.initialize()
state.start()

victim_manager = VictimManager(state)
disaster_engine = DisasterEngine(state, victim_manager)
vehicle_manager = VehicleManager(state)

async def test():
    for i in range(50):
        state.advance_tick()
        await disaster_engine.tick()
        await victim_manager.tick_countdowns()
        await vehicle_manager.tick()
        state.update_metrics()
        if state.tick % 5 == 0:
            m = state.metrics
            print(f"Tick {state.tick:3d} | Phase: {state.phase:12s} | "
                  f"Victims: {len(state.victims):3d} | "
                  f"Disasters: {len([d for d in state.disasters if d.active]):2d} | "
                  f"Roads blocked: {len([r for r in state.roads.values() if r.blocked]):2d} | "
                  f"Rescued: {m.victims_rescued:3d} | Deceased: {m.victims_deceased:3d}")

    print("\n--- FINAL STATE ---")
    print(f"Total victims: {len(state.victims)}")
    print(f"  Waiting: {len(state.get_waiting_victims())}")
    print(f"  Critical: {len(state.get_critical_victims())}")
    print(f"  Rescued: {state.metrics.victims_rescued}")
    print(f"  Deceased: {state.metrics.victims_deceased}")
    print(f"Active disasters: {len([d for d in state.disasters if d.active])}")
    print(f"Blocked roads: {len([r for r in state.roads.values() if r.blocked])}")
    for h in state.hospitals:
        print(f"  {h.id} {h.name}: {h.capacity_percent}% [{h.status}]")
    print("\nDisasters triggered:")
    for d in state.disasters:
        print(f"  [{d.type}] {d.name} (tick {d.tick_started}, severity {d.severity})")
    print("\nSIMULATION ENGINE: OK")

asyncio.run(test())
