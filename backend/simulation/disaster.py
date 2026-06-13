"""
CrisisOS — Disaster Event Engine
Schedules and triggers disaster events at configured simulation ticks.
Manages earthquake, fire spread, road collapses, and hospital overload.
"""

import math
import random
import uuid
from typing import Optional

from simulation.city import Disaster, LatLng, RoadStatus, SimulationState
from config import (
    DISASTER_TICK_EARTHQUAKE,
    DISASTER_TICK_ROAD_COLLAPSE,
    DISASTER_TICK_FIRE,
    DISASTER_TICK_HOSPITAL_OVERLOAD,
    DELHI_LANDMARKS,
    TICK_INTERVAL_SECONDS,
    WS_EVENTS,
)


class DisasterEngine:
    """
    Manages the disaster timeline for a simulation.
    Events are pre-scheduled at specific ticks for reliable demo flow.
    Secondary events (fire spread, aftershocks) keep spawning to maintain pressure.
    """

    def __init__(self, state: SimulationState, victim_manager=None):
        self.state = state
        self.victim_manager = victim_manager
        self._disaster_counter = 0
        self._fire_spread_tick = 0

        # Pre-scheduled events (tick → event config)
        self.scheduled_events: dict[int, list[dict]] = {}
        self._schedule_default_timeline()

    def _schedule_default_timeline(self):
        """
        Set up the default disaster timeline.
        Tuned for a 4-minute demo with escalating pressure.
        """
        # T+30s (tick 15): Earthquake strikes — primary event
        self.scheduled_events[DISASTER_TICK_EARTHQUAKE] = [
            {
                "type": "earthquake",
                "location": (28.6139, 77.2090),  # Connaught Place area
                "severity": 0.85,
                "name": "M7.1 Earthquake — Connaught Place Epicenter",
                "victim_count": 15,
                "spread_radius": 2.5,
            }
        ]

        # T+50s (tick 25): Road collapse — blocks key corridors
        self.scheduled_events[DISASTER_TICK_ROAD_COLLAPSE] = [
            {
                "type": "road_collapse",
                "location": (28.6100, 77.2350),  # Near Ring Road
                "severity": 0.9,
                "name": "Road Collapse — Ring Road near Lajpat Nagar",
                "victim_count": 4,
                "spread_radius": 0.3,
                "roads_to_block": [
                    {"edge_id": "ring_road_east", "location": (28.6100, 77.2350), "name": "Ring Road (East Section)"},
                    {"edge_id": "lajpat_nagar_connector", "location": (28.5720, 77.2350), "name": "Lajpat Nagar Connector"},
                ],
            }
        ]

        # T+70s (tick 35): Fire outbreak — spreads over time
        self.scheduled_events[DISASTER_TICK_FIRE] = [
            {
                "type": "fire",
                "location": (28.6200, 77.2000),  # Karol Bagh area
                "severity": 0.7,
                "name": "Structure Fire — Karol Bagh Market",
                "victim_count": 8,
                "spread_radius": 0.5,
            }
        ]

        # T+100s (tick 50): Hospital overload from incoming patients
        self.scheduled_events[DISASTER_TICK_HOSPITAL_OVERLOAD] = [
            {
                "type": "hospital_overload",
                "location": (28.5950, 77.2280),  # South Emergency Hospital
                "severity": 0.8,
                "name": "Patient Surge — South Emergency Hospital",
                "victim_count": 6,
                "spread_radius": 0.8,
                "hospital_id": "H3",
            }
        ]

        # Secondary waves — keep pressure mounting
        self.scheduled_events[45] = [
            {
                "type": "fire",
                "location": (28.6250, 77.2100),
                "severity": 0.6,
                "name": "Secondary Fire — ITO Junction",
                "victim_count": 5,
                "spread_radius": 0.4,
            }
        ]

        self.scheduled_events[75] = [
            {
                "type": "road_collapse",
                "location": (28.6285, 77.2410),
                "severity": 0.75,
                "name": "Overpass Collapse — Mathura Road",
                "victim_count": 3,
                "spread_radius": 0.2,
                "roads_to_block": [
                    {"edge_id": "mathura_road_south", "location": (28.6285, 77.2410), "name": "Mathura Road (South)"},
                ],
            }
        ]

        # Late-stage victim surge — resource exhaustion pressure
        self.scheduled_events[85] = [
            {
                "type": "earthquake",
                "location": (28.6350, 77.2300),
                "severity": 0.5,
                "name": "Aftershock — Chandni Chowk Sector",
                "victim_count": 10,
                "spread_radius": 1.0,
            }
        ]

    async def tick(self):
        """
        Called every simulation tick. Check for scheduled events and process fire spread.
        """
        current_tick = self.state.tick

        # Check for scheduled events
        if current_tick in self.scheduled_events:
            for event_config in self.scheduled_events[current_tick]:
                await self._trigger_event(event_config)

        # Process fire spread every 5 ticks (10 seconds)
        if current_tick > 0 and current_tick % 5 == 0:
            await self._process_fire_spread()

        # Update phase based on what's happening
        self._update_phase()

    async def _trigger_event(self, config: dict):
        """Trigger a disaster event and spawn associated victims."""
        self._disaster_counter += 1
        location = LatLng(config["location"][0], config["location"][1])

        disaster = Disaster(
            id=f"D{self._disaster_counter:03d}",
            type=config["type"],
            location=location,
            severity=config["severity"],
            active=True,
            spread_radius=config["spread_radius"],
            tick_started=self.state.tick,
            name=config["name"],
        )

        self.state.disasters.append(disaster)

        # Block roads if specified
        if "roads_to_block" in config:
            for road_info in config["roads_to_block"]:
                road = RoadStatus(
                    edge_id=road_info["edge_id"],
                    blocked=True,
                    degraded=0.0,
                    blocked_at_tick=self.state.tick,
                    location=LatLng(road_info["location"][0], road_info["location"][1]) if "location" in road_info else None,
                    name=road_info.get("name", road_info["edge_id"]),
                )
                self.state.roads[road_info["edge_id"]] = road
                disaster.affected_roads.append(road_info["edge_id"])

                await self.state.emit_event(
                    WS_EVENTS["ROAD_BLOCKED"],
                    {
                        "edge_id": road_info["edge_id"],
                        "location": road.location.to_dict() if road.location else None,
                        "name": road.name,
                    },
                )

        # Hospital overload — spike capacity
        if config["type"] == "hospital_overload" and "hospital_id" in config:
            hospital = self.state.get_hospital(config["hospital_id"])
            if hospital:
                # Surge: add 15 patients immediately
                hospital.capacity_used = min(
                    hospital.capacity_used + 15,
                    hospital.capacity_total,
                )
                await self.state.emit_event(
                    WS_EVENTS["HOSPITAL_STATUS_CHANGE"],
                    {
                        "hospital_id": hospital.id,
                        "capacity_percent": hospital.capacity_percent,
                        "status": hospital.status,
                        "name": hospital.name,
                    },
                )

        # Spawn victims
        if self.victim_manager and config.get("victim_count", 0) > 0:
            severity_bias = 0.3 if config["type"] == "earthquake" else 0.0
            victims = self.victim_manager.spawn_victim_cluster(
                epicenter=location,
                count=config["victim_count"],
                severity_bias=severity_bias,
            )

            # Emit victim spawn events
            for victim in victims:
                await self.state.emit_event(
                    WS_EVENTS["VICTIM_SPAWNED"],
                    victim.to_dict(),
                )

        # Emit disaster event
        await self.state.emit_event(
            WS_EVENTS["DISASTER_TRIGGERED"],
            {"disaster": disaster.to_dict()},
        )

        # Update phase
        if config["type"] == "earthquake":
            self.state.phase = "earthquake"

        # Console logging
        severity_label = "CRITICAL" if config["severity"] >= 0.8 else "MAJOR" if config["severity"] >= 0.6 else "MODERATE"
        print(f"  🔴 [{severity_label}] {config['name']}")
        if config.get("victim_count", 0) > 0:
            print(f"     └─ {config['victim_count']} victims spawned near {self.state.get_nearest_landmark(location)}")

    async def _process_fire_spread(self):
        """
        Simulate fire spreading to adjacent areas.
        Fire spreads faster in wind direction and at higher wind speeds.
        """
        active_fires = [d for d in self.state.disasters if d.type == "fire" and d.active]

        for fire in active_fires:
            # Expand spread radius
            wind_factor = 1 + (self.state.weather.get("wind_speed", 15) / 50)
            fire.spread_radius += 0.05 * wind_factor * fire.severity

            # Cap spread
            if fire.spread_radius > 3.0:
                fire.severity *= 0.95  # Fire starts dying down
                if fire.severity < 0.2:
                    fire.active = False
                    continue

            # Occasionally spawn new victims in spread zone
            if random.random() < 0.3 * fire.severity:
                if self.victim_manager:
                    # Spawn 1-3 victims at fire edge
                    wind_dir_rad = math.radians(self.state.weather.get("wind_direction", 315))
                    edge_lat = fire.location.lat + (fire.spread_radius / 111) * math.cos(wind_dir_rad)
                    edge_lng = fire.location.lng + (fire.spread_radius / (111 * math.cos(math.radians(fire.location.lat)))) * math.sin(wind_dir_rad)

                    new_victims = self.victim_manager.spawn_victim_cluster(
                        epicenter=LatLng(edge_lat, edge_lng),
                        count=random.randint(1, 2),
                        severity_bias=0.2,
                    )

                    for v in new_victims:
                        await self.state.emit_event(
                            WS_EVENTS["VICTIM_SPAWNED"],
                            v.to_dict(),
                        )

            # Check if fire threatens roads
            for edge_id, road in self.state.roads.items():
                if road.location and not road.blocked:
                    dist = fire.location.distance_km(road.location)
                    if dist < fire.spread_radius * 0.8:
                        road.degraded = max(0.0, road.degraded - 0.15)
                        if road.degraded <= 0.2:
                            road.blocked = True
                            road.blocked_at_tick = self.state.tick

            await self.state.emit_event(
                WS_EVENTS["FIRE_SPREADING"],
                {
                    "disaster_id": fire.id,
                    "new_radius": round(fire.spread_radius, 3),
                    "severity": round(fire.severity, 3),
                    "location": fire.location.to_dict(),
                },
            )

    def _update_phase(self):
        """Update simulation phase based on disaster state."""
        active_disasters = [d for d in self.state.disasters if d.active]
        if not active_disasters:
            if self.state.disasters:
                self.state.phase = "stabilizing"
            return

        has_earthquake = any(d.type == "earthquake" for d in active_disasters)
        has_secondary = any(d.type in ("fire", "road_collapse") for d in active_disasters)

        if has_earthquake and has_secondary:
            self.state.phase = "secondary"
        elif has_earthquake:
            self.state.phase = "earthquake"
        elif has_secondary:
            self.state.phase = "secondary"

    def add_custom_event(self, tick: int, config: dict):
        """Add a custom disaster event at a specific tick. Used by ConflictEngine."""
        if tick not in self.scheduled_events:
            self.scheduled_events[tick] = []
        self.scheduled_events[tick].append(config)

    def get_active_disasters(self) -> list[Disaster]:
        return [d for d in self.state.disasters if d.active]

    def get_fires(self) -> list[Disaster]:
        return [d for d in self.state.disasters if d.type == "fire" and d.active]

    def get_blocked_road_count(self) -> int:
        return sum(1 for r in self.state.roads.values() if r.blocked)

    def get_status_summary(self) -> str:
        active = self.get_active_disasters()
        return (
            f"Disasters: {len(active)} active | "
            f"Roads blocked: {self.get_blocked_road_count()} | "
            f"Phase: {self.state.phase}"
        )
