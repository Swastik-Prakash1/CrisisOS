"""
CrisisOS — Conflict Engine
Deliberately generates the three scenario types that demonstrate
agent reasoning is non-trivial.
These are designed into the simulation for reliable demo flow.
"""

import random
from typing import Optional

from agents.base_agent import Conflict, Proposal
from simulation.city import LatLng, SimulationState
from config import (
    CONFLICT_TICK_ROAD_SACRIFICE,
    CONFLICT_TICK_RESOURCE_EXHAUSTION,
)


class ConflictEngine:
    """
    Creates deliberate conflict scenarios that showcase CrisisOS's
    decision-making capabilities. Three scenario types:

    1. ROAD SACRIFICE: Save one critical victim vs preserve corridor for 15+
    2. RESOURCE EXHAUSTION: 3 ambulances, 4+ critical victims
    3. HUMAN BAD COMMAND: Human override that increases casualties

    Scenarios are pre-scheduled at specific ticks for reliable demo flow.
    """

    def __init__(self, state: SimulationState, victim_manager=None, disaster_engine=None):
        self.state = state
        self.victim_manager = victim_manager
        self.disaster_engine = disaster_engine

        self._road_sacrifice_triggered = False
        self._resource_exhaustion_triggered = False
        self._scenarios_executed: list[str] = []
        self._injected_proposals: list = []

    async def tick(self):
        """Check if any conflict scenarios should trigger this tick."""
        tick = self.state.tick

        # Road Sacrifice — fire at tick 36 (right after fire disaster at 35)
        if tick == CONFLICT_TICK_ROAD_SACRIFICE and not self._road_sacrifice_triggered:
            await self.force_scenario("road_sacrifice")

        # Resource Exhaustion — tick 65
        if tick == CONFLICT_TICK_RESOURCE_EXHAUSTION and not self._resource_exhaustion_triggered:
            await self.force_scenario("resource_exhaustion")

    async def force_scenario(self, scenario_name: str):
        """Force-trigger a specific conflict scenario. Called from tick() or main loop."""
        if scenario_name == "road_sacrifice" and not self._road_sacrifice_triggered:
            await self._trigger_road_sacrifice()
        elif scenario_name == "resource_exhaustion" and not self._resource_exhaustion_triggered:
            await self._trigger_resource_exhaustion()
        else:
            print(f"  ⚠ Scenario '{scenario_name}' already triggered or unknown")

    async def _trigger_road_sacrifice(self):
        """
        SCENARIO: Road Sacrifice
        Setup: Critical victim spawns on a route that, if committed to,
        blocks access to 15+ victims in another sector.

        Expected agent behavior:
        - MedicalAgent: "Assign A1 to critical victim immediately" (high severity)
        - LogisticsAgent: "Hold — this route is the only access to Sector C"
        - Commander: calculates 20-min window expected value, chooses corridor

        The counter-intuitive correct answer: preserve the corridor.
        """
        self._road_sacrifice_triggered = True
        self._scenarios_executed.append("road_sacrifice")

        print("\n  🔴 ═══ CONFLICT SCENARIO: ROAD SACRIFICE ═══")

        # Spawn critical victim on the contested route (near Ring Road)
        critical_location = LatLng(28.6100, 77.2350)  # On Ring Road East
        critical_victim = self.victim_manager.spawn_critical_victim(
            location=critical_location,
            time_to_death=480.0,  # 8 minutes
            sector="D",
        )

        print(f"  │ Critical victim {critical_victim.id} spawned near Ring Road East")
        print(f"  │ Severity: 5 | TTD: 480s | Sector: D")

        # Spawn cluster of 15 moderate victims accessible ONLY via this corridor
        cluster_center = LatLng(28.5950, 77.2400)  # Sector C, south of Ring Road
        cluster_victims = self.victim_manager.spawn_victim_cluster(
            epicenter=cluster_center,
            count=14,
            severity_bias=-0.2,  # Slightly lower severity
            sector_override="C",
        )

        print(f"  │ Victim cluster: {len(cluster_victims)} victims in Sector C")
        print(f"  │ Accessible ONLY via Ring Road East corridor")

        # Ensure the road is currently passable but threatened
        # (The conflict is: committing a vehicle to the critical victim
        #  risks the corridor being fully committed when fire spreads)
        from simulation.city import RoadStatus
        if "ring_road_east" not in self.state.roads:
            self.state.roads["ring_road_east"] = RoadStatus(
                edge_id="ring_road_east",
                blocked=False,
                degraded=0.6,  # Already degraded — vulnerable
                blocked_at_tick=None,
                location=LatLng(28.6100, 77.2350),
                name="Ring Road (East Section)",
            )

        # Emit events for spawned victims
        from config import WS_EVENTS
        await self.state.emit_event(
            WS_EVENTS["VICTIM_SPAWNED"],
            critical_victim.to_dict(),
        )
        for v in cluster_victims:
            await self.state.emit_event(
                WS_EVENTS["VICTIM_SPAWNED"],
                v.to_dict(),
            )

        # INJECT conflicting proposals directly for Commander to arbitrate
        # This guarantees the conflict is visible immediately
        available_ambulance = None
        for v in self.state.vehicles:
            if v.type == "ambulance" and v.status == "available":
                available_ambulance = v
                break
        if not available_ambulance:
            # Pick the one with longest ETA (least urgent current mission)
            ambulances = [v for v in self.state.vehicles if v.type == "ambulance"]
            available_ambulance = max(ambulances, key=lambda v: v.eta_seconds)

        self._injected_proposals = [
            Proposal(
                agent_name="MEDICAL",
                action=f"Dispatch {available_ambulance.id} to critical victim {critical_victim.id} (severity 5, TTD 480s)",
                target=f"victim:{critical_victim.id}",
                confidence=0.9,
                reasoning="Severity-5 victim requires immediate dispatch. Patient will die without intervention within 8 minutes.",
                utility_score=0.85,
                metadata={
                    "type": "dispatch",
                    "vehicle_id": available_ambulance.id,
                    "victim_id": critical_victim.id,
                    "victim_severity": 5,
                    "victim_ttd": 480,
                    "victim_location": critical_victim.location.to_dict(),
                    "route_risk": 0.6,
                },
            ),
            Proposal(
                agent_name="LOGISTICS",
                action=f"Hold {available_ambulance.id} — Ring Road East is the only corridor to {len(cluster_victims)} victims in Sector C",
                target=f"victim:{critical_victim.id}",
                confidence=0.85,
                reasoning=f"Committing {available_ambulance.id} via Ring Road East blocks the only access corridor to {len(cluster_victims)} victims in Sector C. Corridor preservation has higher expected value.",
                utility_score=0.82,
                metadata={
                    "type": "route_hold",
                    "vehicle_id": available_ambulance.id,
                    "victim_id": critical_victim.id,
                    "accessible_victims": len(cluster_victims),
                    "route_risk": 0.6,
                    "victim_severity": 3,
                    "victim_ttd": 900,
                },
            ),
        ]

        # Emit conflict detected event
        await self.state.emit_event(
            WS_EVENTS["CONFLICT_DETECTED"],
            {
                "conflict": {
                    "type": "road_sacrifice",
                    "description": f"MEDICAL vs LOGISTICS: Save 1 critical victim or preserve corridor for {len(cluster_victims)}",
                    "agents": ["MEDICAL", "LOGISTICS"],
                    "tick": self.state.tick,
                }
            },
        )

        print(f"  └─ Road Sacrifice scenario active — 2 conflicting proposals injected")

    async def _trigger_resource_exhaustion(self):
        """
        SCENARIO: Resource Exhaustion
        Setup: All 3 ambulances deployed/en-route.
        4th critical victim spawns in isolated sector.
        Hospital 3 at 91%+ capacity and rising.

        Expected behavior:
        - MedicalAgent: "Priority 1 victim, assign resource!"
        - LogisticsAgent: "No resources available. Nearest ETA 14 min."
        - PredictionAgent: "Hospital 3 overload in 9 min"
        - Commander: must choose — recall from lower-priority, or accept casualty
        """
        self._resource_exhaustion_triggered = True
        self._scenarios_executed.append("resource_exhaustion")

        print("\n  🔴 ═══ CONFLICT SCENARIO: RESOURCE EXHAUSTION ═══")

        # Ensure all ambulances are busy
        for vehicle in self.state.vehicles:
            if vehicle.type == "ambulance" and vehicle.status == "available":
                # Assign to a nearby waiting victim if available
                waiting = self.state.get_waiting_victims()
                if waiting:
                    victim = waiting[0]
                    vehicle.status = "en_route"
                    vehicle.assigned_victim = victim.id
                    victim.status = "en_route"
                    victim.assigned_vehicle = vehicle.id
                    # Give a simple route
                    vehicle.assigned_route = [victim.location.to_dict()]
                    vehicle.route_index = 0
                    print(f"  │ {vehicle.id} deployed to {victim.id}")

        # Spawn critical victim in isolated sector
        isolated_location = LatLng(28.6450, 77.2400)  # Sector D, isolated
        critical_victim = self.victim_manager.spawn_critical_victim(
            location=isolated_location,
            time_to_death=660.0,  # 11 minutes
            sector="D",
        )

        print(f"  │ Critical victim {critical_victim.id} spawned in isolated Sector D")
        print(f"  │ TTD: 660s | All ambulances deployed")

        # Spike Hospital 3 capacity
        h3 = self.state.get_hospital("H3")
        if h3:
            h3.capacity_used = max(h3.capacity_used, int(h3.capacity_total * 0.91))
            print(f"  │ {h3.name}: {h3.capacity_percent}% capacity [{h3.status}]")

        # Spawn 2 more critical victims for maximum pressure
        for i in range(2):
            loc = LatLng(
                28.62 + random.uniform(-0.01, 0.01),
                77.22 + random.uniform(-0.01, 0.01),
            )
            v = self.victim_manager.spawn_critical_victim(
                location=loc,
                time_to_death=random.uniform(400, 700),
            )
            print(f"  │ Additional critical victim {v.id} spawned")

        from config import WS_EVENTS
        await self.state.emit_event(
            WS_EVENTS["VICTIM_SPAWNED"],
            critical_victim.to_dict(),
        )

        # INJECT conflicting proposals for Commander
        # Find the ambulance on the lowest-priority mission
        busy_ambulances = [v for v in self.state.vehicles if v.type == "ambulance" and v.assigned_victim]
        lowest_priority_amb = None
        if busy_ambulances:
            # Find the one assigned to lowest severity victim
            def get_victim_sev(amb):
                victim = self.state.get_victim(amb.assigned_victim)
                return victim.severity if victim else 0
            lowest_priority_amb = min(busy_ambulances, key=get_victim_sev)

        if lowest_priority_amb:
            self._injected_proposals = getattr(self, '_injected_proposals', []) + [
                Proposal(
                    agent_name="MEDICAL",
                    action=f"Recall {lowest_priority_amb.id} from {lowest_priority_amb.assigned_victim} — redirect to critical {critical_victim.id} (sev 5)",
                    target=f"victim:{critical_victim.id}",
                    confidence=0.82,
                    reasoning=f"No ambulances available. {lowest_priority_amb.id} is on a lower-priority mission. Critical victim {critical_victim.id} will die without immediate dispatch.",
                    utility_score=0.78,
                    metadata={
                        "type": "dispatch",
                        "vehicle_id": lowest_priority_amb.id,
                        "victim_id": critical_victim.id,
                        "victim_severity": 5,
                        "victim_ttd": 660,
                        "victim_location": critical_victim.location.to_dict(),
                    },
                ),
                Proposal(
                    agent_name="LOGISTICS",
                    action=f"No resources available — maintain current assignments, accept {critical_victim.id} as expectant casualty",
                    target=f"victim:{critical_victim.id}",
                    confidence=0.75,
                    reasoning=f"All 3 ambulances deployed on active rescues. Recalling any unit abandons their current victim. Accept triage: {critical_victim.id} in Sector D is not reachable in time.",
                    utility_score=0.72,
                    metadata={
                        "type": "abandon",
                        "victim_id": critical_victim.id,
                        "victim_severity": 5,
                        "victim_ttd": 660,
                    },
                ),
            ]

        await self.state.emit_event(
            WS_EVENTS["CONFLICT_DETECTED"],
            {
                "conflict": {
                    "type": "resource_exhaustion",
                    "description": f"All ambulances deployed — critical victim {critical_victim.id} requires impossible choice",
                    "agents": ["MEDICAL", "LOGISTICS"],
                    "tick": self.state.tick,
                }
            },
        )

        print(f"  └─ Resource Exhaustion active — {len(self.state.get_critical_victims())} critical, 0 ambulances available")

    def evaluate_human_command(self, action: str, target: str, params: dict) -> Optional[dict]:
        """
        SCENARIO: Human Bad Command
        Evaluate a human override command and calculate casualty impact.
        Returns warning dict if command is dangerous, None if safe.
        """
        if action == "send_all_units":
            # Calculate impact of concentrating all units in one sector
            target_sector = target

            # Count victims in other sectors that would lose coverage
            victims_abandoned = 0
            sectors_abandoned = []
            for sector_id in ["A", "B", "C", "D"]:
                if sector_id == target_sector:
                    continue
                sector_victims = [
                    v for v in self.state.get_active_victims()
                    if v.sector == sector_id and v.status == "en_route"
                ]
                if sector_victims:
                    victims_abandoned += len(sector_victims)
                    sectors_abandoned.append(sector_id)

            if victims_abandoned > 0:
                # Calculate projected casualty delta
                projected_delta = sum(
                    1 for v in self.state.get_active_victims()
                    if v.sector in sectors_abandoned
                    and v.status == "en_route"
                    and v.time_to_death_seconds < 300  # Would die if vehicle recalled
                )

                # Be conservative — include nearby waiting critical too
                projected_delta += sum(
                    1 for v in self.state.get_active_victims()
                    if v.sector in sectors_abandoned
                    and v.status == "waiting"
                    and v.severity >= 4
                    and v.time_to_death_seconds < 180
                )

                projected_delta = max(projected_delta, int(victims_abandoned * 0.4))

                return {
                    "command": f"Send all units to Sector {target_sector}",
                    "projected_casualties_delta": projected_delta,
                    "sectors_abandoned": sectors_abandoned,
                    "victims_affected": victims_abandoned,
                    "recommendation": (
                        f"Maintain 1 unit each in Sectors {' and '.join(sectors_abandoned)}, "
                        f"redirect 1 unit to Sector {target_sector}. "
                        f"This preserves coverage while increasing Sector {target_sector} response."
                    ),
                }

        elif action == "evacuate_hospital":
            hospital = self.state.get_hospital(target)
            if hospital and hospital.capacity_percent < 70:
                return {
                    "command": f"Evacuate {hospital.name}",
                    "projected_casualties_delta": hospital.capacity_used // 4,
                    "recommendation": (
                        f"{hospital.name} is at {hospital.capacity_percent:.0f}% — "
                        f"evacuation is premature and would displace {hospital.capacity_used} patients. "
                        f"Recommend monitoring until capacity exceeds 90%."
                    ),
                }

        return None  # Command is safe

    def get_active_scenario(self) -> Optional[str]:
        """Get the most recent active scenario type."""
        if self._scenarios_executed:
            return self._scenarios_executed[-1]
        return None

    def get_scenario_status(self) -> dict:
        return {
            "road_sacrifice_triggered": self._road_sacrifice_triggered,
            "resource_exhaustion_triggered": self._resource_exhaustion_triggered,
            "scenarios_executed": self._scenarios_executed,
            "triggered_scenarios": [
                {"name": s, "tick": self.state.tick}
                for s in self._scenarios_executed
            ],
        }
