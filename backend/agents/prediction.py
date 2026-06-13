"""
CrisisOS — Prediction Agent
Looks 2 minutes (120 seconds) into the future.
Uses spread models and projection algorithms — NOT LLM.
Decision cycle: every 15 seconds.
"""

import math
import random
from dataclasses import dataclass, field
from typing import Optional

import httpx

from agents.base_agent import BaseAgent, Proposal
from simulation.city import LatLng, SimulationState
from config import DEFAULT_WEATHER, TICK_INTERVAL_SECONDS


@dataclass
class Alert:
    """Proactive alert from the Prediction Agent."""
    id: str = ""
    urgency: str = "moderate"  # low | moderate | high | critical
    message: str = ""
    category: str = ""  # fire_spread | hospital_overload | route_closure | victim_cluster
    target: str = ""
    time_horizon_seconds: int = 120
    confidence: float = 0.7
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "urgency": self.urgency,
            "message": self.message,
            "category": self.category,
            "target": self.target,
            "time_horizon_seconds": self.time_horizon_seconds,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


class PredictionAgent(BaseAgent):
    """
    The foresight engine of CrisisOS.
    Separates CrisisOS from reactive systems by looking ahead.

    Capabilities:
    - Fire spread projection (cellular model)
    - Hospital overload prediction (fill rate extrapolation)
    - Route closure forecasting (fire proximity + spread)
    - Victim cluster critical window prediction

    Does NOT use LLM — pure algorithmic projection.
    """

    def __init__(self, state: SimulationState):
        super().__init__("PREDICTION", state)
        self.active_alerts: list[Alert] = []
        self._alert_counter = 0
        self.weather_loaded = False

    def perceive(self) -> dict:
        """Extract prediction-relevant state."""
        return {
            "fires": [
                d.to_dict() for d in self.state.disasters
                if d.type == "fire" and d.active
            ],
            "hospitals": [h.to_dict() for h in self.state.hospitals],
            "roads": {k: v.to_dict() for k, v in self.state.roads.items()},
            "active_victims": len(self.state.get_active_victims()),
            "critical_victims": len(self.state.get_critical_victims()),
            "weather": self.state.weather,
        }

    def propose(self) -> list[Proposal]:
        """
        Generate proactive predictions as proposals.
        These inform the Commander about future threats.
        """
        proposals = []

        # Generate all alert types
        self.active_alerts = self.generate_proactive_alerts()

        for alert in self.active_alerts:
            priority = {"critical": 0.95, "high": 0.8, "moderate": 0.6, "low": 0.3}.get(alert.urgency, 0.5)

            proposals.append(Proposal(
                agent_name=self.name,
                action=alert.message,
                target=alert.target,
                priority_score=priority,
                utility_score=priority * alert.confidence,
                confidence=self.get_adjusted_confidence(alert.confidence),
                reasoning=f"Prediction ({alert.category}): {alert.message}",
                metadata={
                    "type": "prediction",
                    "alert": alert.to_dict(),
                    "category": alert.category,
                },
            ))

        return proposals

    def project_fire_spread(self, fire_id: str = None, horizon_seconds: int = 120) -> list[dict]:
        """
        Simple cellular spread model:
        - Fire spreads to adjacent areas at rate proportional to severity
        - Wind speed and direction affect spread rate and direction
        - Returns list of areas that will be affected within horizon

        Returns:
            list of {location, time_to_reach, probability}
        """
        projections = []
        fires = [d for d in self.state.disasters if d.type == "fire" and d.active]
        if fire_id:
            fires = [d for d in fires if d.id == fire_id]

        for fire in fires:
            wind_speed = self.state.weather.get("wind_speed", 15)
            wind_dir = self.state.weather.get("wind_direction", 315)
            wind_dir_rad = math.radians(wind_dir)

            # Spread rate: base + wind contribution
            base_spread_rate = 0.1 * fire.severity  # km per 120 seconds
            wind_spread_rate = base_spread_rate * (1 + wind_speed / 30)

            # Project spread in multiple directions, biased by wind
            for angle_offset in range(-60, 61, 30):
                spread_dir = wind_dir_rad + math.radians(angle_offset)
                # Wind alignment factor: maximum spread in wind direction
                alignment = max(0.3, math.cos(math.radians(angle_offset)))
                spread_distance = wind_spread_rate * alignment

                # Project point
                proj_lat = fire.location.lat + (spread_distance / 111) * math.cos(spread_dir)
                proj_lng = fire.location.lng + (spread_distance / (111 * math.cos(math.radians(fire.location.lat)))) * math.sin(spread_dir)

                time_to_reach = horizon_seconds * (1 - alignment * 0.5)

                projections.append({
                    "location": {"lat": round(proj_lat, 6), "lng": round(proj_lng, 6)},
                    "source_fire": fire.id,
                    "time_to_reach_seconds": round(time_to_reach),
                    "probability": round(alignment * fire.severity, 2),
                })

        return projections

    def project_hospital_overload(self, hospital_id: str = None, horizon_seconds: int = 120) -> list[dict]:
        """
        Current fill rate + incoming patient ETA = projected capacity at T+horizon.
        """
        projections = []

        for hospital in self.state.hospitals:
            if hospital_id and hospital.id != hospital_id:
                continue

            # Count incoming patients (victims en_route)
            incoming = sum(
                1 for v in self.state.victims
                if v.status == "en_route" and v.assigned_vehicle
            )

            # Estimate fill rate (patients per minute from recent history)
            current_pct = hospital.capacity_percent
            # Assume steady state: incoming / total_hospitals patients per 2 min
            projected_incoming = incoming / max(1, len(self.state.hospitals))
            projected_pct = current_pct + (projected_incoming / hospital.capacity_total) * 100

            # Time to critical (95%)
            if current_pct < 95 and projected_pct > current_pct:
                rate_per_second = (projected_pct - current_pct) / horizon_seconds
                if rate_per_second > 0:
                    time_to_critical = (95 - current_pct) / rate_per_second
                else:
                    time_to_critical = 9999
            else:
                time_to_critical = 0 if current_pct >= 95 else 9999

            projections.append({
                "hospital_id": hospital.id,
                "hospital_name": hospital.name,
                "current_percent": current_pct,
                "projected_percent": min(100, round(projected_pct, 1)),
                "time_to_critical_seconds": round(time_to_critical),
                "incoming_patients": incoming,
                "recommendation": self._hospital_recommendation(hospital, projected_pct),
            })

        return projections

    def generate_proactive_alerts(self) -> list[Alert]:
        """
        Creates alerts for the UI BEFORE problems occur.
        This is what makes CrisisOS proactive, not reactive.
        """
        alerts = []

        # 1. Fire spread alerts
        fire_projections = self.project_fire_spread()
        for proj in fire_projections:
            if proj["probability"] > 0.5:
                # Check if projected area threatens roads
                proj_loc = LatLng(proj["location"]["lat"], proj["location"]["lng"])
                threatened_roads = []
                for edge_id, road in self.state.roads.items():
                    if road.location and not road.blocked:
                        if proj_loc.distance_km(road.location) < 0.5:
                            threatened_roads.append(road.name or edge_id)

                if threatened_roads:
                    self._alert_counter += 1
                    alerts.append(Alert(
                        id=f"PA{self._alert_counter:04d}",
                        urgency="high",
                        message=f"🔥 Fire projected to reach {', '.join(threatened_roads[:2])} in ~{proj['time_to_reach_seconds']//60} min",
                        category="fire_spread",
                        target=proj["source_fire"],
                        time_horizon_seconds=proj["time_to_reach_seconds"],
                        confidence=proj["probability"],
                        metadata={"projected_location": proj["location"], "threatened_roads": threatened_roads},
                    ))

        # 2. Hospital overload alerts
        hospital_projections = self.project_hospital_overload()
        for proj in hospital_projections:
            if proj["projected_percent"] > 85 and proj["time_to_critical_seconds"] < 600:
                self._alert_counter += 1
                urgency = "critical" if proj["time_to_critical_seconds"] < 300 else "high"
                alerts.append(Alert(
                    id=f"PA{self._alert_counter:04d}",
                    urgency=urgency,
                    message=f"⚠ {proj['hospital_name']} projected to reach {proj['projected_percent']:.0f}% capacity in ~{proj['time_to_critical_seconds']//60} min",
                    category="hospital_overload",
                    target=proj["hospital_id"],
                    time_horizon_seconds=proj["time_to_critical_seconds"],
                    confidence=0.8,
                    metadata={"hospital_projection": proj},
                ))

        # 3. Victim cluster critical window
        critical_victims = self.state.get_critical_victims()
        sectors_with_critical = {}
        for v in critical_victims:
            if v.sector not in sectors_with_critical:
                sectors_with_critical[v.sector] = []
            sectors_with_critical[v.sector].append(v)

        for sector, victims in sectors_with_critical.items():
            min_ttd = min(v.time_to_death_seconds for v in victims)
            if min_ttd < 300 and len(victims) >= 2:
                self._alert_counter += 1
                alerts.append(Alert(
                    id=f"PA{self._alert_counter:04d}",
                    urgency="critical" if min_ttd < 120 else "high",
                    message=f"⏰ Sector {sector}: {len(victims)} critical victims entering danger window in {min_ttd:.0f}s",
                    category="victim_cluster",
                    target=f"sector_{sector}",
                    time_horizon_seconds=int(min_ttd),
                    confidence=0.9,
                    metadata={"sector": sector, "victim_count": len(victims), "min_ttd": min_ttd},
                ))

        # Sort by urgency
        urgency_order = {"critical": 0, "high": 1, "moderate": 2, "low": 3}
        alerts.sort(key=lambda a: urgency_order.get(a.urgency, 4))

        return alerts

    async def load_weather_context(self):
        """
        Call Open-Meteo API ONCE at simulation start.
        Store: wind_speed, wind_direction, precipitation.
        Fire spreads faster in wind direction, vehicles slower in rain.
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={
                        "latitude": 28.6139,
                        "longitude": 77.2090,
                        "current_weather": True,
                        "hourly": "precipitation,windspeed_10m,winddirection_10m",
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    current = data.get("current_weather", {})

                    self.state.weather = {
                        "wind_speed": current.get("windspeed", DEFAULT_WEATHER["wind_speed"]),
                        "wind_direction": current.get("winddirection", DEFAULT_WEATHER["wind_direction"]),
                        "precipitation": data.get("hourly", {}).get("precipitation", [0])[0],
                        "temperature": current.get("temperature", DEFAULT_WEATHER["temperature"]),
                    }
                    self.weather_loaded = True
                    print(f"  🌤 Weather loaded: wind {self.state.weather['wind_speed']}km/h, "
                          f"direction {self.state.weather['wind_direction']}°, "
                          f"rain {self.state.weather['precipitation']}mm, "
                          f"temp {self.state.weather['temperature']}°C")
                    return

        except Exception as e:
            print(f"  ⚠ Open-Meteo API unavailable: {e}")

        # Fallback to defaults
        self.state.weather = dict(DEFAULT_WEATHER)
        self.weather_loaded = True
        print(f"  🌤 Using default weather: wind {DEFAULT_WEATHER['wind_speed']}km/h NW")

    def _hospital_recommendation(self, hospital, projected_pct: float) -> str:
        """Generate recommendation for hospital capacity management."""
        if projected_pct >= 95:
            return f"Immediately divert incoming patients from {hospital.name}. Route to alternative facilities."
        elif projected_pct >= 85:
            return f"Begin preemptive diversion planning for {hospital.name}. Notify alternate facilities."
        elif projected_pct >= 70:
            return f"Monitor {hospital.name} capacity. Prepare contingency routing."
        return f"{hospital.name} within normal parameters."
