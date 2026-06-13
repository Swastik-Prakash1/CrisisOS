"""
CrisisOS — Intelligence Agent
Processes raw simulation state into prioritized intelligence.
Feeds other agents with structured summaries.
Runs every 5 seconds (fastest cycle of all agents).
"""

from agents.base_agent import BaseAgent, Proposal
from simulation.city import LatLng, SimulationState
from config import SECTORS


class IntelligenceAgent(BaseAgent):
    """
    The eyes and ears of CrisisOS.
    Doesn't make resource allocation decisions — instead processes
    raw state into actionable intelligence for other agents.

    Outputs:
    - hotspot_map: sectors ranked by urgency
    - route_status: current passability of key corridors
    - resource_gaps: where vehicles are needed vs where they are
    - hospital_pressure: which hospitals are approaching limits
    """

    def __init__(self, state: SimulationState):
        super().__init__("INTELLIGENCE", state)
        self.hotspots: list[dict] = []
        self.route_status: dict[str, float] = {}
        self.resource_gaps: dict[str, dict] = {}
        self.hospital_pressure: list[dict] = []

    def perceive(self) -> dict:
        """Extract full situational awareness."""
        return {
            "active_victims": [v.to_dict() for v in self.state.get_active_victims()],
            "disasters": [d.to_dict() for d in self.state.disasters if d.active],
            "vehicles": [v.to_dict() for v in self.state.vehicles],
            "hospitals": [h.to_dict() for h in self.state.hospitals],
            "roads": {k: v.to_dict() for k, v in self.state.roads.items()},
        }

    def propose(self) -> list[Proposal]:
        """
        Intelligence Agent doesn't propose resource actions directly.
        Instead, it generates intelligence reports that inform other agents.
        Returns proposals for priority sector focus changes.
        """
        self._update_hotspots()
        self._update_route_status()
        self._update_resource_gaps()
        self._update_hospital_pressure()

        proposals = []

        # Propose sector priority changes
        for hotspot in self.hotspots[:3]:
            if hotspot["urgency_score"] > 0.7:
                proposals.append(Proposal(
                    agent_name=self.name,
                    action=f"Prioritize Sector {hotspot['sector']} — {hotspot['name']}",
                    target=f"sector_{hotspot['sector']}",
                    priority_score=hotspot["urgency_score"],
                    utility_score=hotspot["urgency_score"] * 0.8,
                    confidence=self.get_adjusted_confidence(0.85),
                    reasoning=(
                        f"Sector {hotspot['sector']} has {hotspot['victim_count']} active victims "
                        f"(avg severity {hotspot['avg_severity']:.1f}). "
                        f"Urgency score: {hotspot['urgency_score']:.2f}."
                    ),
                    metadata={
                        "type": "intelligence_priority",
                        "hotspot": hotspot,
                    },
                ))

        # Propose route warnings
        for edge_id, passability in self.route_status.items():
            if passability < 0.5:
                road = self.state.roads.get(edge_id)
                road_name = road.name if road else edge_id
                proposals.append(Proposal(
                    agent_name=self.name,
                    action=f"Route degradation warning — {road_name}",
                    target=edge_id,
                    priority_score=1.0 - passability,
                    utility_score=0.6,
                    confidence=self.get_adjusted_confidence(0.9),
                    reasoning=f"{road_name} passability at {passability:.0%}. Recommend rerouting.",
                    metadata={"type": "route_warning", "passability": passability},
                ))

        return proposals

    def identify_hotspots(self) -> list[dict]:
        """
        Hotspot = cluster of victims in a geographic sector.
        Score = sum(victim_severity * time_pressure) for all victims in sector.
        """
        self._update_hotspots()
        return self.hotspots

    def assess_route_corridors(self) -> dict[str, float]:
        """
        For each road segment, returns passability score 0.0-1.0.
        0.0 = blocked, 1.0 = clear, intermediate = degraded.
        """
        self._update_route_status()
        return self.route_status

    def get_sector_intelligence(self, sector_id: str) -> dict:
        """Get detailed intelligence for a specific sector."""
        sector_info = SECTORS.get(sector_id, {})
        center = LatLng(sector_info["center"][0], sector_info["center"][1])

        victims = [
            v for v in self.state.get_active_victims()
            if v.sector == sector_id
        ]

        vehicles_in_sector = [
            v for v in self.state.vehicles
            if v.location.distance_km(center) < sector_info.get("radius_km", 2.0)
        ]

        return {
            "sector": sector_id,
            "name": sector_info.get("name", sector_id),
            "victim_count": len(victims),
            "critical_count": sum(1 for v in victims if v.severity >= 4),
            "vehicle_count": len(vehicles_in_sector),
            "available_vehicles": sum(1 for v in vehicles_in_sector if v.status == "available"),
            "avg_severity": sum(v.severity for v in victims) / len(victims) if victims else 0,
            "min_ttd": min((v.time_to_death_seconds for v in victims), default=9999),
        }

    # ── Private Update Methods ───────────────────────────────────────────

    def _update_hotspots(self):
        """Recalculate sector hotspot rankings."""
        self.hotspots = []

        for sector_id, sector_info in SECTORS.items():
            center = LatLng(sector_info["center"][0], sector_info["center"][1])
            victims = [v for v in self.state.get_active_victims() if v.sector == sector_id]

            if not victims:
                continue

            # Urgency score = sum of (severity * time_pressure) for each victim
            urgency_score = 0.0
            for v in victims:
                time_pressure = max(0, 1.0 - (v.time_to_death_seconds / v.initial_ttd)) if v.initial_ttd > 0 else 1.0
                urgency_score += (v.severity / 5.0) * (0.5 + 0.5 * time_pressure)

            # Normalize by max possible (5 critical victims at max urgency)
            urgency_score = min(1.0, urgency_score / 5.0)

            self.hotspots.append({
                "sector": sector_id,
                "name": sector_info["name"],
                "center": center.to_dict(),
                "victim_count": len(victims),
                "critical_count": sum(1 for v in victims if v.severity >= 4),
                "avg_severity": sum(v.severity for v in victims) / len(victims),
                "urgency_score": round(urgency_score, 3),
                "min_ttd_seconds": min(v.time_to_death_seconds for v in victims),
            })

        # Sort by urgency (highest first)
        self.hotspots.sort(key=lambda h: h["urgency_score"], reverse=True)

    def _update_route_status(self):
        """Update passability scores for all known roads."""
        self.route_status = {}
        for edge_id, road in self.state.roads.items():
            if road.blocked:
                self.route_status[edge_id] = 0.0
            else:
                self.route_status[edge_id] = road.degraded

    def _update_resource_gaps(self):
        """Identify sectors that need more resources."""
        self.resource_gaps = {}
        for sector_id, sector_info in SECTORS.items():
            intel = self.get_sector_intelligence(sector_id)
            gap = intel["victim_count"] - intel["available_vehicles"]
            self.resource_gaps[sector_id] = {
                "gap": max(0, gap),
                "victims": intel["victim_count"],
                "vehicles_available": intel["available_vehicles"],
                "critical": intel["critical_count"],
            }

    def _update_hospital_pressure(self):
        """Assess hospital pressure levels."""
        self.hospital_pressure = []
        for hospital in self.state.hospitals:
            pressure = {
                "hospital_id": hospital.id,
                "name": hospital.name,
                "capacity_percent": hospital.capacity_percent,
                "status": hospital.status,
                "remaining_beds": hospital.capacity_total - hospital.capacity_used,
            }
            self.hospital_pressure.append(pressure)

        # Sort by pressure (highest first)
        self.hospital_pressure.sort(key=lambda h: h["capacity_percent"], reverse=True)
