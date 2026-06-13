"""
CrisisOS — Medical Agent
Handles victim triage and hospital capacity management.
Uses modified START triage (Simple Triage and Rapid Treatment).
Decision cycle: every 10 seconds.
"""

from agents.base_agent import BaseAgent, Proposal
from simulation.city import LatLng, SimulationState, Victim, Vehicle


class MedicalAgent(BaseAgent):
    """
    The medical authority of CrisisOS.
    Responsible for:
    - Victim triage scoring (who to save first)
    - Hospital capacity management (where to send patients)
    - Expectant category decisions (when to stop trying)

    Triage levels:
    Priority 1 (Immediate):  severity >= 4, TTD < 600s
    Priority 2 (Delayed):    severity >= 3, TTD < 1800s
    Priority 3 (Minor):      severity <= 2
    Priority 0 (Expectant):  TTD < 60s AND no vehicle assigned
    """

    def __init__(self, state: SimulationState):
        super().__init__("MEDICAL", state)

    def perceive(self) -> dict:
        """Extract medical-relevant state."""
        return {
            "waiting_victims": [v.to_dict() for v in self.state.get_waiting_victims()],
            "critical_victims": [v.to_dict() for v in self.state.get_critical_victims()],
            "hospitals": [h.to_dict() for h in self.state.hospitals],
            "available_ambulances": [
                v.to_dict() for v in self.state.get_available_vehicles("ambulance")
            ],
        }

    def propose(self) -> list[Proposal]:
        """
        Generate triage-based proposals for victim rescue priority.
        Each proposal says: 'Send vehicle X to victim Y'.
        """
        proposals = []
        waiting = self.state.get_waiting_victims()

        if not waiting:
            return proposals

        # Score and rank all waiting victims
        scored_victims = []
        for victim in waiting:
            triage_score = self.calculate_triage_score(victim)
            triage_priority = self._get_triage_priority(victim)
            scored_victims.append((victim, triage_score, triage_priority))

        # Sort by triage score (highest first), excluding expectant
        scored_victims.sort(key=lambda x: x[1], reverse=True)

        # Get available ambulances
        available_ambulances = self.state.get_available_vehicles("ambulance")

        # Generate proposals for top victims that can be reached
        for victim, score, priority in scored_victims[:5]:  # Top 5 most urgent
            if priority == 0:
                # Expectant — propose but with very low score
                proposals.append(Proposal(
                    agent_name=self.name,
                    action=f"Triage classification: EXPECTANT for victim {victim.id}",
                    target=victim.id,
                    priority_score=0.05,
                    utility_score=0.05,
                    confidence=self.get_adjusted_confidence(0.9),
                    reasoning=(
                        f"Victim {victim.id} (severity {victim.severity}) near {victim.nearest_landmark} "
                        f"has {victim.time_to_death_seconds:.0f}s remaining. "
                        f"No vehicle can reach in time. Classified as Expectant."
                    ),
                    metadata={
                        "type": "triage",
                        "triage_priority": 0,
                        "victim_id": victim.id,
                        "victim_severity": victim.severity,
                        "victim_ttd": victim.time_to_death_seconds,
                    },
                ))
                continue

            # Find best hospital for this victim
            best_hospital = self.assess_hospital_routing(victim)

            # Propose rescue
            for ambulance in available_ambulances:
                eta = self._estimate_eta(ambulance, victim)

                # Skip if ambulance can't reach in time
                if eta > victim.time_to_death_seconds * 0.9:
                    continue

                proposals.append(Proposal(
                    agent_name=self.name,
                    action=f"Dispatch {ambulance.id} to victim {victim.id} near {victim.nearest_landmark}",
                    target=victim.id,
                    priority_score=score,
                    utility_score=score * self._hospital_capacity_factor(best_hospital),
                    confidence=self.get_adjusted_confidence(0.75 + priority * 0.05),
                    reasoning=(
                        f"Priority {priority} victim {victim.id} (severity {victim.severity}) "
                        f"near {victim.nearest_landmark}. "
                        f"TTD: {victim.time_to_death_seconds:.0f}s. "
                        f"ETA for {ambulance.id}: {eta:.0f}s. "
                        f"Route to {best_hospital.name if best_hospital else 'nearest'} hospital."
                    ),
                    metadata={
                        "type": "rescue",
                        "triage_priority": priority,
                        "victim_id": victim.id,
                        "vehicle_id": ambulance.id,
                        "hospital_id": best_hospital.id if best_hospital else None,
                        "eta_seconds": eta,
                        "victim_severity": victim.severity,
                        "victim_ttd": victim.time_to_death_seconds,
                        "victim_location": victim.location.to_dict(),
                    },
                ))
                break  # One ambulance per victim proposal

        return proposals

    def calculate_triage_score(self, victim: Victim) -> float:
        """
        Score = severity_weight * urgency_multiplier * survivability_factor

        survivability_factor:
        - If nearest available ambulance ETA > time_to_death: 0.1 (expectant)
        - Otherwise: 1.0

        This creates the heartbreaking tradeoff scenarios.
        """
        # Severity weight (normalized 0-1)
        severity_weight = victim.severity / 5.0

        # Urgency multiplier — higher when closer to death
        if victim.initial_ttd > 0:
            time_fraction = victim.time_to_death_seconds / victim.initial_ttd
            urgency_multiplier = max(0, 1.0 - time_fraction) + 0.5
        else:
            urgency_multiplier = 1.5

        # Survivability factor
        survivability = self._assess_survivability(victim)

        score = severity_weight * urgency_multiplier * survivability
        return min(1.0, score)

    def assess_hospital_routing(self, victim: Victim):
        """
        Return the best hospital for this victim.
        Factors: distance, current capacity, projected arrival time.
        If best hospital will be at 95%+ capacity by arrival: route to second best.
        """
        candidates = []
        for hospital in self.state.hospitals:
            distance = victim.location.distance_km(hospital.location)
            capacity_factor = self._hospital_capacity_factor(hospital)

            # Composite score: closer and less full = better
            score = capacity_factor / (1 + distance)
            candidates.append((hospital, score))

        candidates.sort(key=lambda x: x[1], reverse=True)

        if candidates:
            return candidates[0][0]
        return None

    # ── Private Helpers ──────────────────────────────────────────────────

    def _get_triage_priority(self, victim: Victim) -> int:
        """Modified START triage classification."""
        # Expectant — can't be saved
        if victim.time_to_death_seconds < 60 and victim.assigned_vehicle is None:
            nearest_ambulance = self._find_nearest_ambulance(victim)
            if nearest_ambulance is None:
                return 0
            eta = self._estimate_eta(nearest_ambulance, victim)
            if eta > victim.time_to_death_seconds:
                return 0

        # Immediate
        if victim.severity >= 4 and victim.time_to_death_seconds < 600:
            return 1

        # Delayed
        if victim.severity >= 3 and victim.time_to_death_seconds < 1800:
            return 2

        # Minor
        return 3

    def _assess_survivability(self, victim: Victim) -> float:
        """
        Probability of saving this victim given current resources.
        Key factor: can any available vehicle reach them in time?
        """
        nearest = self._find_nearest_ambulance(victim)
        if nearest is None:
            # No ambulances available at all
            if victim.time_to_death_seconds < 120:
                return 0.1  # Expectant
            return 0.3  # Might become available

        eta = self._estimate_eta(nearest, victim)
        if eta >= victim.time_to_death_seconds:
            return 0.1  # Can't reach in time

        # Survivable — score based on margin
        margin_ratio = (victim.time_to_death_seconds - eta) / victim.time_to_death_seconds
        return 0.5 + 0.5 * min(1.0, margin_ratio)

    def _find_nearest_ambulance(self, victim: Victim):
        """Find nearest available ambulance."""
        available = self.state.get_available_vehicles("ambulance")
        if not available:
            return None
        return min(available, key=lambda a: a.location.distance_km(victim.location))

    def _estimate_eta(self, vehicle: Vehicle, victim: Victim) -> float:
        """
        Estimate time in seconds for vehicle to reach victim.
        Uses simple distance/speed calculation.
        Real routing will come from LogisticsAgent.
        """
        distance_km = vehicle.location.distance_km(victim.location)
        # Average 45 km/h in city, adjusted for conditions
        speed_kmh = 45 * max(0.5, 1.0 - self.state.weather.get("precipitation", 0) * 0.02)
        return (distance_km / speed_kmh) * 3600 if speed_kmh > 0 else 9999

    def _hospital_capacity_factor(self, hospital) -> float:
        """Penalize sending to overloaded hospitals."""
        if hospital is None:
            return 0.5
        pct = hospital.capacity_percent
        if pct >= 95:
            return 0.2  # Severely penalized
        elif pct >= 85:
            return 0.5
        elif pct >= 70:
            return 0.8
        return 1.0
