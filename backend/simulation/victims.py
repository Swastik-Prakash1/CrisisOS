"""
CrisisOS — Victim Spawning and Countdown System
Manages victim lifecycle: spawn → wait → en_route → rescued/deceased
Each victim has a real countdown timer that decrements every tick.
"""

import math
import random
import uuid
from typing import Optional

from simulation.city import LatLng, SimulationState, Victim
from config import (
    VICTIM_SEVERITY_DISTRIBUTION,
    VICTIM_TTD_RANGES,
    VICTIM_SPAWN_RADIUS_KM,
    TICK_INTERVAL_SECONDS,
    WS_EVENTS,
)


class VictimManager:
    """
    Manages all victim spawning, countdown timers, and status transitions.
    Victims are spawned near disaster epicenters in realistic clusters.
    """

    def __init__(self, state: SimulationState):
        self.state = state
        self._victim_counter = 0

    def spawn_victim_cluster(
        self,
        epicenter: LatLng,
        count: int,
        severity_bias: float = 0.0,
        sector_override: str = None,
    ) -> list[Victim]:
        """
        Spawn a cluster of victims near a disaster epicenter.

        Args:
            epicenter: Center point for spawning
            count: Number of victims to spawn
            severity_bias: 0.0=normal distribution, positive=more severe
            sector_override: Force sector assignment
        """
        spawned = []

        for _ in range(count):
            # Random offset from epicenter (clustered distribution)
            angle = random.uniform(0, 2 * math.pi)
            # Use sqrt for uniform area distribution
            distance_km = random.uniform(0.05, VICTIM_SPAWN_RADIUS_KM) * math.sqrt(random.random())

            # Convert km offset to lat/lng
            dlat = (distance_km / 111.0) * math.cos(angle)
            dlng = (distance_km / (111.0 * math.cos(math.radians(epicenter.lat)))) * math.sin(angle)

            location = LatLng(
                lat=round(epicenter.lat + dlat, 6),
                lng=round(epicenter.lng + dlng, 6),
            )

            # Determine severity using weighted distribution
            severity = self._roll_severity(severity_bias)

            # Time to death based on severity
            ttd_min, ttd_max = VICTIM_TTD_RANGES[severity]
            time_to_death = random.uniform(ttd_min, ttd_max)

            # Determine sector
            sector = sector_override or self.state.get_sector_for_location(location)
            landmark = self.state.get_nearest_landmark(location)

            self._victim_counter += 1
            victim = Victim(
                id=f"V{self._victim_counter:04d}",
                location=location,
                severity=severity,
                time_to_death_seconds=time_to_death,
                initial_ttd=time_to_death,
                status="waiting",
                assigned_vehicle=None,
                sector=sector,
                spawned_at_tick=self.state.tick,
                nearest_landmark=landmark,
            )

            self.state.victims.append(victim)
            spawned.append(victim)

        # Update metrics
        self.state.update_metrics()
        return spawned

    def spawn_critical_victim(
        self,
        location: LatLng,
        time_to_death: float = 480.0,
        sector: str = None,
    ) -> Victim:
        """
        Spawn a single critical victim at a specific location.
        Used by ConflictEngine for deliberate scenario creation.
        """
        self._victim_counter += 1
        sector = sector or self.state.get_sector_for_location(location)
        landmark = self.state.get_nearest_landmark(location)

        victim = Victim(
            id=f"V{self._victim_counter:04d}",
            location=location,
            severity=5,
            time_to_death_seconds=time_to_death,
            initial_ttd=time_to_death,
            status="waiting",
            assigned_vehicle=None,
            sector=sector,
            spawned_at_tick=self.state.tick,
            nearest_landmark=landmark,
        )

        self.state.victims.append(victim)
        self.state.update_metrics()
        return victim

    async def tick_countdowns(self):
        """
        Decrement time_to_death for all active victims.
        Called every simulation tick (2 seconds).
        Transitions victims to 'deceased' when timer reaches 0.
        """
        newly_deceased = []

        for victim in self.state.victims:
            if victim.status not in ("waiting", "en_route"):
                continue

            # Decrement countdown
            victim.time_to_death_seconds -= TICK_INTERVAL_SECONDS

            # Check for death
            if victim.time_to_death_seconds <= 0:
                victim.time_to_death_seconds = 0
                victim.status = "deceased"

                # If a vehicle was assigned, free it
                if victim.assigned_vehicle:
                    vehicle = self.state.get_vehicle(victim.assigned_vehicle)
                    if vehicle and vehicle.assigned_victim == victim.id:
                        vehicle.status = "available"
                        vehicle.assigned_victim = None
                        vehicle.assigned_route = []
                        vehicle.route_index = 0

                newly_deceased.append(victim)

                # Emit death event
                await self.state.emit_event(
                    WS_EVENTS["VICTIM_DECEASED"],
                    {
                        "victim_id": victim.id,
                        "cause": "time_expired",
                        "severity": victim.severity,
                        "sector": victim.sector,
                        "landmark": victim.nearest_landmark,
                        "tick": self.state.tick,
                    },
                )

        # Update metrics after processing
        if newly_deceased:
            self.state.update_metrics()

        return newly_deceased

    def rescue_victim(self, victim_id: str, hospital_id: str = None) -> bool:
        """
        Mark a victim as rescued. Called when ambulance completes rescue.
        Optionally admit to hospital.
        """
        victim = self.state.get_victim(victim_id)
        if not victim or victim.status == "deceased":
            return False

        victim.status = "rescued"

        # Admit to hospital if specified
        if hospital_id:
            hospital = self.state.get_hospital(hospital_id)
            if hospital:
                hospital.capacity_used = min(
                    hospital.capacity_used + 1,
                    hospital.capacity_total,
                )

        self.state.update_metrics()
        return True

    def assign_vehicle_to_victim(self, victim_id: str, vehicle_id: str) -> bool:
        """Assign a vehicle to a victim, changing both statuses."""
        victim = self.state.get_victim(victim_id)
        vehicle = self.state.get_vehicle(vehicle_id)

        if not victim or not vehicle:
            return False
        if victim.status != "waiting":
            return False
        if vehicle.status != "available":
            return False

        victim.status = "en_route"
        victim.assigned_vehicle = vehicle_id
        vehicle.assigned_victim = victim_id
        vehicle.status = "en_route"

        self.state.update_metrics()
        return True

    def get_victims_in_sector(self, sector: str) -> list[Victim]:
        """Get all active victims in a sector."""
        return [
            v for v in self.state.victims
            if v.sector == sector and v.status in ("waiting", "en_route")
        ]

    def get_victims_near(self, location: LatLng, radius_km: float) -> list[Victim]:
        """Get active victims within radius of a location."""
        return [
            v for v in self.state.victims
            if v.status in ("waiting", "en_route")
            and v.location.distance_km(location) <= radius_km
        ]

    def get_triage_priority(self, victim: Victim) -> int:
        """
        Modified START triage classification.
        Priority 1 (Immediate):   severity >= 4, TTD < 600s
        Priority 2 (Delayed):     severity >= 3, TTD < 1800s
        Priority 3 (Minor):       severity <= 2
        Priority 0 (Expectant):   TTD < 60s AND no vehicle assigned
        """
        if (
            victim.time_to_death_seconds < 60
            and victim.assigned_vehicle is None
        ):
            return 0  # Expectant — don't waste resources

        if victim.severity >= 4 and victim.time_to_death_seconds < 600:
            return 1  # Immediate

        if victim.severity >= 3 and victim.time_to_death_seconds < 1800:
            return 2  # Delayed

        return 3  # Minor

    # ── Private Helpers ──────────────────────────────────────────────────

    def _roll_severity(self, bias: float = 0.0) -> int:
        """
        Roll severity using weighted distribution.
        bias > 0 shifts toward higher severity.
        """
        weights = dict(VICTIM_SEVERITY_DISTRIBUTION)

        # Apply bias — shift weight toward higher severities
        if bias != 0.0:
            for sev in weights:
                if sev >= 4:
                    weights[sev] *= (1 + bias)
                elif sev <= 2:
                    weights[sev] *= max(0.1, 1 - bias * 0.5)

        # Normalize
        total = sum(weights.values())
        choices = list(weights.keys())
        probs = [weights[s] / total for s in choices]

        return random.choices(choices, weights=probs, k=1)[0]

    def get_status_summary(self) -> str:
        """Console-friendly status summary."""
        active = [v for v in self.state.victims if v.status in ("waiting", "en_route")]
        waiting = [v for v in active if v.status == "waiting"]
        en_route = [v for v in active if v.status == "en_route"]
        critical = [v for v in active if v.severity >= 4]

        return (
            f"Victims: {len(self.state.victims)} total | "
            f"{len(waiting)} waiting | {len(en_route)} en_route | "
            f"{self.state.metrics.victims_rescued} rescued | "
            f"{self.state.metrics.victims_deceased} deceased | "
            f"{len(critical)} critical"
        )
