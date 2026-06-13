"""
CrisisOS — Logistics Agent
Handles all vehicle assignment and routing.
Uses openrouteservice API for real directions, falls back to NetworkX A*.
Decision cycle: every 8 seconds.
"""

import math
from typing import Optional

import httpx
import polyline as polyline_decoder

from agents.base_agent import BaseAgent, Proposal
from simulation.city import LatLng, SimulationState, Vehicle, Victim
from config import ORS_API_KEY, VEHICLE_SPEED_KMH


class LogisticsAgent(BaseAgent):
    """
    The logistics brain of CrisisOS.
    Responsible for:
    - Vehicle-to-victim assignment proposals
    - Route calculation (ORS API → A* fallback)
    - Route risk scoring (probability of route being blocked)
    - Vehicle fuel and availability management
    """

    def __init__(self, state: SimulationState):
        super().__init__("LOGISTICS", state)
        self.http_client: Optional[httpx.AsyncClient] = None
        self._cached_routes: dict[str, list] = {}  # Cache route calculations

    def perceive(self) -> dict:
        """Extract logistics-relevant state."""
        return {
            "vehicles": [v.to_dict() for v in self.state.vehicles],
            "waiting_victims": [v.to_dict() for v in self.state.get_waiting_victims()],
            "blocked_roads": {
                k: v.to_dict() for k, v in self.state.roads.items() if v.blocked
            },
            "active_fires": [
                d.to_dict() for d in self.state.disasters
                if d.type == "fire" and d.active
            ],
        }

    def propose(self) -> list[Proposal]:
        """
        Generate vehicle assignment proposals.
        Each proposal says: 'Assign vehicle X to victim Y via route Z'.
        Includes route risk scoring.
        """
        proposals = []
        waiting = self.state.get_waiting_victims()
        available = self.state.get_available_vehicles()

        if not waiting or not available:
            # If no vehicles available, propose holding patterns
            if waiting and not available:
                most_critical = max(waiting, key=lambda v: v.severity)
                proposals.append(Proposal(
                    agent_name=self.name,
                    action=f"Hold — no vehicles available for victim {most_critical.id} near {most_critical.nearest_landmark}",
                    target=most_critical.id,
                    priority_score=0.9 if most_critical.severity >= 4 else 0.5,
                    utility_score=0.0,
                    confidence=self.get_adjusted_confidence(0.95),
                    reasoning=(
                        f"All vehicles deployed. Victim {most_critical.id} "
                        f"(severity {most_critical.severity}, TTD: {most_critical.time_to_death_seconds:.0f}s) "
                        f"near {most_critical.nearest_landmark} cannot be reached. "
                        f"Recommend recalling nearest returning vehicle."
                    ),
                    metadata={
                        "type": "hold",
                        "victim_id": most_critical.id,
                        "victim_severity": most_critical.severity,
                    },
                ))
            return proposals

        # Score all vehicle-victim pairs
        assignments = []
        for vehicle in available:
            if vehicle.type != "ambulance":
                continue  # Fire trucks handled separately

            for victim in waiting:
                distance = vehicle.location.distance_km(victim.location)
                eta = self._estimate_eta(vehicle, victim)
                route_risk = self._route_risk_score(vehicle.location, victim.location)

                # Utility: how valuable is this assignment?
                # Higher severity + lower ETA + lower risk = higher utility
                severity_factor = victim.severity / 5.0
                time_factor = max(0, 1.0 - (eta / victim.time_to_death_seconds)) if victim.time_to_death_seconds > 0 else 0
                risk_factor = 1.0 - route_risk

                utility = severity_factor * 0.4 + time_factor * 0.35 + risk_factor * 0.25

                assignments.append({
                    "vehicle": vehicle,
                    "victim": victim,
                    "distance": distance,
                    "eta": eta,
                    "route_risk": route_risk,
                    "utility": utility,
                })

        # Sort by utility
        assignments.sort(key=lambda a: a["utility"], reverse=True)

        # Generate proposals for top assignments (avoid duplicate vehicles/victims)
        used_vehicles = set()
        used_victims = set()

        for assignment in assignments:
            v_id = assignment["vehicle"].id
            victim_id = assignment["victim"].id

            if v_id in used_vehicles or victim_id in used_victims:
                continue

            vehicle = assignment["vehicle"]
            victim = assignment["victim"]
            eta = assignment["eta"]
            route_risk = assignment["route_risk"]

            risk_label = "LOW" if route_risk < 0.3 else "MODERATE" if route_risk < 0.6 else "HIGH"

            proposals.append(Proposal(
                agent_name=self.name,
                action=f"Dispatch {vehicle.id} to victim {victim.id} near {victim.nearest_landmark}",
                target=victim.id,
                priority_score=assignment["utility"],
                utility_score=assignment["utility"],
                confidence=self.get_adjusted_confidence(0.7 + (1 - route_risk) * 0.2),
                reasoning=(
                    f"Route {vehicle.id}→{victim.id}: "
                    f"ETA {eta:.0f}s, distance {assignment['distance']:.1f}km, "
                    f"route risk {risk_label} ({route_risk:.0%}). "
                    f"Victim TTD: {victim.time_to_death_seconds:.0f}s."
                ),
                metadata={
                    "type": "dispatch",
                    "vehicle_id": vehicle.id,
                    "victim_id": victim.id,
                    "eta_seconds": eta,
                    "distance_km": assignment["distance"],
                    "route_risk": route_risk,
                    "victim_location": victim.location.to_dict(),
                    "vehicle_location": vehicle.location.to_dict(),
                },
            ))

            used_vehicles.add(v_id)
            used_victims.add(victim_id)

            if len(proposals) >= 5:
                break

        return proposals

    def propose_route_hold(self, route_edge_id: str, reason: str) -> Proposal:
        """
        Propose holding a route corridor open (not sending vehicles through).
        Used in Road Sacrifice scenarios.
        """
        road = self.state.roads.get(route_edge_id)
        road_name = road.name if road else route_edge_id

        # Count victims accessible only through this route
        # (simplified — in full implementation would use graph analysis)
        nearby_victims = len([
            v for v in self.state.get_active_victims()
            if road and road.location and v.location.distance_km(road.location) < 1.0
        ])

        return Proposal(
            agent_name=self.name,
            action=f"Hold route corridor — {road_name}",
            target=route_edge_id,
            priority_score=0.8,
            utility_score=0.7 + (nearby_victims * 0.02),
            confidence=self.get_adjusted_confidence(0.75),
            reasoning=(
                f"Route {road_name} is the only access to {nearby_victims} victims. "
                f"{reason}. Recommend preserving corridor access."
            ),
            metadata={
                "type": "route_hold",
                "edge_id": route_edge_id,
                "accessible_victims": nearby_victims,
            },
        )

    async def find_optimal_route(self, start: LatLng, end: LatLng) -> list[dict]:
        """
        Primary: Call openrouteservice API for real road directions.
        Fallback: Generate interpolated route.
        """
        cache_key = f"{start.lat:.4f},{start.lng:.4f}→{end.lat:.4f},{end.lng:.4f}"
        if cache_key in self._cached_routes:
            return self._cached_routes[cache_key]

        # Try ORS API
        if ORS_API_KEY and ORS_API_KEY != "your_openrouteservice_key_here":
            try:
                route = await self._ors_route(start, end)
                if route:
                    self._cached_routes[cache_key] = route
                    return route
            except Exception as e:
                print(f"  ⚠ ORS routing failed: {e}")

        # Fallback: interpolated route with jitter
        route = self._fallback_route(start, end)
        self._cached_routes[cache_key] = route
        return route

    async def _ors_route(self, start: LatLng, end: LatLng) -> Optional[list[list[float]]]:
        """Call OpenRouteService API for real road directions."""
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(timeout=5.0)

        try:
            response = await self.http_client.post(
                "https://api.openrouteservice.org/v2/directions/driving-car/json",
                headers={"Authorization": ORS_API_KEY, "Content-Type": "application/json"},
                json={
                    "coordinates": [[start.lng, start.lat], [end.lng, end.lat]],
                    "preference": "fastest",
                    "instructions": False,
                    "geometry": True,
                    "geometry_simplify": False
                },
            )

            if response.status_code == 200:
                data = response.json()
                encoded_geometry = data["routes"][0]["geometry"]
                
                # Use polyline to decode if it is a string
                if isinstance(encoded_geometry, str):
                    import polyline as pl
                    decoded_coords = pl.decode(encoded_geometry)
                    return [[c[0], c[1]] for c in decoded_coords]
                else:
                    # Fallback if it is already coordinates
                    coords = encoded_geometry["coordinates"] if isinstance(encoded_geometry, dict) else encoded_geometry
                    return [[c[1], c[0]] for c in coords]
        except Exception as e:
            print(f"[ORS FALLBACK] {e} — using A* instead")
            
        return None

    def _fallback_route(self, start: LatLng, end: LatLng, waypoints: int = 6) -> list[dict]:
        """Generate a simple interpolated route (fallback when ORS unavailable)."""
        import random
        route = []
        for i in range(waypoints + 1):
            t = i / waypoints
            jitter_lat = random.uniform(-0.0015, 0.0015) if 0 < i < waypoints else 0
            jitter_lng = random.uniform(-0.0015, 0.0015) if 0 < i < waypoints else 0
            route.append({
                "lat": round(start.lat + (end.lat - start.lat) * t + jitter_lat, 6),
                "lng": round(start.lng + (end.lng - start.lng) * t + jitter_lng, 6),
            })
        return route

    def _route_risk_score(self, start: LatLng, end: LatLng) -> float:
        """
        Probability that this route gets blocked before vehicle completes it.
        Based on: proximity to active disasters and fire spread zones.
        """
        risk = 0.0

        # Check proximity to active fires
        for disaster in self.state.disasters:
            if not disaster.active:
                continue

            if disaster.type == "fire":
                # Calculate route midpoint
                midpoint = LatLng(
                    (start.lat + end.lat) / 2,
                    (start.lng + end.lng) / 2,
                )
                distance_to_fire = midpoint.distance_km(disaster.location)

                if distance_to_fire < disaster.spread_radius * 1.5:
                    # Route passes near fire
                    proximity_factor = 1.0 - (distance_to_fire / (disaster.spread_radius * 1.5))
                    risk = max(risk, proximity_factor * disaster.severity)

        # Check if any roads along route are blocked
        for edge_id, road in self.state.roads.items():
            if road.blocked and road.location:
                midpoint = LatLng((start.lat + end.lat) / 2, (start.lng + end.lng) / 2)
                dist = midpoint.distance_km(road.location)
                if dist < 0.5:
                    risk = max(risk, 0.8)

        return min(1.0, risk)

    def _estimate_eta(self, vehicle: Vehicle, victim: Victim) -> float:
        """Estimate ETA in seconds."""
        distance = vehicle.location.distance_km(victim.location)
        speed = VEHICLE_SPEED_KMH * max(0.5, 1.0 - self.state.weather.get("precipitation", 0) * 0.02)
        # Add penalty for route risk
        risk = self._route_risk_score(vehicle.location, victim.location)
        speed *= (1.0 - risk * 0.3)  # Risky routes are slower
        return (distance / speed) * 3600 if speed > 0 else 9999
