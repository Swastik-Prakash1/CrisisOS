"""
CrisisOS — City State & Simulation State
The single source of truth for the entire simulation.
All agents read from and write to this state object.
"""

import asyncio
import math
import random
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

import networkx as nx

from config import (
    CITY_CENTER,
    CITY_BOUNDS,
    HOSPITALS,
    INITIAL_VEHICLES,
    SECTORS,
    DELHI_LANDMARKS,
)


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class LatLng:
    lat: float
    lng: float

    def to_dict(self) -> dict:
        return {"lat": self.lat, "lng": self.lng}

    @classmethod
    def from_dict(cls, d: dict) -> "LatLng":
        return cls(lat=d["lat"], lng=d["lng"])

    def distance_km(self, other: "LatLng") -> float:
        """Haversine distance in kilometers."""
        R = 6371.0
        lat1, lat2 = math.radians(self.lat), math.radians(other.lat)
        dlat = math.radians(other.lat - self.lat)
        dlng = math.radians(other.lng - self.lng)
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@dataclass
class Disaster:
    id: str
    type: str  # "earthquake" | "fire" | "road_collapse" | "hospital_overload"
    location: LatLng
    severity: float  # 0.0-1.0
    active: bool
    spread_radius: float  # km
    tick_started: int
    name: str = ""  # Human-readable name using real locations
    affected_roads: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "location": self.location.to_dict(),
            "severity": self.severity,
            "active": self.active,
            "spread_radius": self.spread_radius,
            "tick_started": self.tick_started,
            "name": self.name,
            "affected_roads": self.affected_roads,
        }


@dataclass
class Victim:
    id: str
    location: LatLng
    severity: int  # 1-5
    time_to_death_seconds: float
    initial_ttd: float  # Original TTD for tracking
    status: str  # "waiting" | "en_route" | "rescued" | "deceased"
    assigned_vehicle: Optional[str]
    sector: str
    spawned_at_tick: int
    nearest_landmark: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "location": self.location.to_dict(),
            "severity": self.severity,
            "time_to_death_seconds": round(self.time_to_death_seconds, 1),
            "initial_ttd": round(self.initial_ttd, 1),
            "status": self.status,
            "assigned_vehicle": self.assigned_vehicle,
            "sector": self.sector,
            "spawned_at_tick": self.spawned_at_tick,
            "nearest_landmark": self.nearest_landmark,
        }


@dataclass
class Vehicle:
    id: str
    type: str  # "ambulance" | "fire_truck"
    status: str  # "available" | "en_route" | "on_scene" | "returning"
    location: LatLng
    assigned_victim: Optional[str]
    assigned_route: list  # list of LatLng waypoints
    route_index: int  # Current position along route
    eta_seconds: float
    fuel: float
    home_location: LatLng  # Where to return
    target_hospital: Optional[str] = None
    onscene_ticks_remaining: int = 0
    hospital_ticks_remaining: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "status": self.status,
            "location": self.location.to_dict(),
            "assigned_victim": self.assigned_victim,
            "target_hospital": self.target_hospital,
            "assigned_route": [p.to_dict() if isinstance(p, LatLng) else p for p in self.assigned_route],
            "eta_seconds": round(self.eta_seconds, 1),
            "fuel": round(self.fuel, 3),
        }


@dataclass
class Hospital:
    id: str
    name: str
    location: LatLng
    capacity_total: int
    capacity_used: int

    @property
    def capacity_percent(self) -> float:
        if self.capacity_total == 0:
            return 100.0
        return round((self.capacity_used / self.capacity_total) * 100, 1)

    @property
    def status(self) -> str:
        pct = self.capacity_percent
        if pct >= 95:
            return "overloaded"
        elif pct >= 85:
            return "critical"
        elif pct >= 70:
            return "warning"
        return "ok"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "location": self.location.to_dict(),
            "capacity_total": self.capacity_total,
            "capacity_used": self.capacity_used,
            "capacity_percent": self.capacity_percent,
            "status": self.status,
        }


@dataclass
class RoadStatus:
    edge_id: str
    blocked: bool
    degraded: float  # 0.0 = fully blocked, 1.0 = clear
    blocked_at_tick: Optional[int]
    location: Optional[LatLng] = None
    name: str = ""

    def to_dict(self) -> dict:
        return {
            "edge_id": self.edge_id,
            "blocked": self.blocked,
            "degraded": self.degraded,
            "blocked_at_tick": self.blocked_at_tick,
            "location": self.location.to_dict() if self.location else None,
            "name": self.name,
        }


@dataclass
class Metrics:
    victims_total: int = 0
    victims_rescued: int = 0
    victims_deceased: int = 0
    victims_critical_active: int = 0
    casualties_avoided: int = 0
    baseline_casualties: int = 0
    ambulances_deployed: int = 0
    decisions_made: int = 0
    conflicts_resolved: int = 0
    human_overrides: int = 0
    human_override_warnings_accepted: int = 0

    def to_dict(self) -> dict:
        return {
            "victims_total": self.victims_total,
            "victims_rescued": self.victims_rescued,
            "victims_deceased": self.victims_deceased,
            "victims_critical_active": self.victims_critical_active,
            "casualties_avoided": self.casualties_avoided,
            "baseline_casualties": self.baseline_casualties,
            "ambulances_deployed": self.ambulances_deployed,
            "decisions_made": self.decisions_made,
            "conflicts_resolved": self.conflicts_resolved,
            "human_overrides": self.human_overrides,
            "human_override_warnings_accepted": self.human_override_warnings_accepted,
        }


# ── Simulation State ─────────────────────────────────────────────────────────

class SimulationState:
    """
    The single source of truth for the entire CrisisOS simulation.
    Thread-safe via asyncio lock for concurrent agent access.
    """

    def __init__(self):
        self.lock = asyncio.Lock()

        # Simulation lifecycle
        self.running: bool = False
        self.paused: bool = False
        self.tick: int = 0
        self.elapsed_seconds: int = 0
        self.phase: str = "standby"  # standby | earthquake | secondary | stabilizing
        self.start_time: float = 0.0

        # Entities
        self.disasters: list[Disaster] = []
        self.roads: dict[str, RoadStatus] = {}
        self.victims: list[Victim] = []
        self.vehicles: list[Vehicle] = []
        self.hospitals: list[Hospital] = []

        # Metrics
        self.metrics: Metrics = Metrics()

        # Road network (NetworkX graph)
        self.road_graph: Optional[nx.Graph] = None

        # Event queue for WebSocket broadcasting
        self._event_queue: asyncio.Queue = asyncio.Queue()

        # Weather context (loaded from Open-Meteo)
        self.weather: dict = {
            "wind_speed": 15.0,
            "wind_direction": 315,
            "precipitation": 0.0,
            "temperature": 38.0,
        }

    def initialize(self):
        """Set up initial city state — hospitals, vehicles, empty victim list."""
        # Initialize hospitals
        self.hospitals = [
            Hospital(
                id=h["id"],
                name=h["name"],
                location=LatLng(h["location"]["lat"], h["location"]["lng"]),
                capacity_total=h["capacity_total"],
                capacity_used=h["capacity_used"],
            )
            for h in HOSPITALS
        ]

        # Initialize vehicles
        self.vehicles = [
            Vehicle(
                id=v["id"],
                type=v["type"],
                status="available",
                location=LatLng(v["location"]["lat"], v["location"]["lng"]),
                assigned_victim=None,
                assigned_route=[],
                route_index=0,
                eta_seconds=0.0,
                fuel=1.0,
                home_location=LatLng(v["location"]["lat"], v["location"]["lng"]),
            )
            for v in INITIAL_VEHICLES
        ]

        # Clear state
        self.disasters = []
        self.roads = {}
        self.victims = []
        self.metrics = Metrics()
        self.tick = 0
        self.elapsed_seconds = 0
        self.phase = "standby"

    def start(self):
        """Begin simulation."""
        self.running = True
        self.paused = False
        self.start_time = time.time()
        self.phase = "standby"

    def pause(self):
        """Pause simulation."""
        self.paused = True

    def resume(self):
        """Resume simulation."""
        self.paused = False

    def stop(self):
        """End simulation."""
        self.running = False
        self.phase = "ended"

    def advance_tick(self):
        """Increment simulation tick and elapsed time."""
        self.tick += 1
        self.elapsed_seconds = self.tick * 2  # 2 seconds per tick

    # ── Entity Helpers ───────────────────────────────────────────────────

    def get_victim(self, victim_id: str) -> Optional[Victim]:
        for v in self.victims:
            if v.id == victim_id:
                return v
        return None

    def get_vehicle(self, vehicle_id: str) -> Optional[Vehicle]:
        for v in self.vehicles:
            if v.id == vehicle_id:
                return v
        return None

    def get_hospital(self, hospital_id: str) -> Optional[Hospital]:
        for h in self.hospitals:
            if h.id == hospital_id:
                return h
        return None

    def get_available_vehicles(self, vehicle_type: str = None) -> list[Vehicle]:
        return [
            v for v in self.vehicles
            if v.status == "available"
            and (vehicle_type is None or v.type == vehicle_type)
        ]

    def get_active_victims(self) -> list[Victim]:
        return [v for v in self.victims if v.status in ("waiting", "en_route")]

    def get_waiting_victims(self) -> list[Victim]:
        return [v for v in self.victims if v.status == "waiting"]

    def get_critical_victims(self) -> list[Victim]:
        return [
            v for v in self.victims
            if v.status in ("waiting", "en_route") and v.severity >= 4
        ]

    def get_sector_for_location(self, loc: LatLng) -> str:
        """Determine which sector a location belongs to."""
        min_dist = float("inf")
        best_sector = "A"
        for sector_id, info in SECTORS.items():
            center = LatLng(info["center"][0], info["center"][1])
            dist = loc.distance_km(center)
            if dist < min_dist:
                min_dist = dist
                best_sector = sector_id
        return best_sector

    def get_nearest_landmark(self, loc: LatLng) -> str:
        """Find nearest Delhi landmark for realistic naming."""
        min_dist = float("inf")
        best_name = "Central Delhi"
        for name, (lat, lng) in DELHI_LANDMARKS.items():
            dist = loc.distance_km(LatLng(lat, lng))
            if dist < min_dist:
                min_dist = dist
                best_name = name
        return best_name

    # ── Metrics Update ───────────────────────────────────────────────────

    def update_metrics(self):
        """Recompute all metrics from current state."""
        self.metrics.victims_total = len(self.victims)
        self.metrics.victims_rescued = sum(1 for v in self.victims if v.status == "rescued")
        self.metrics.victims_deceased = sum(1 for v in self.victims if v.status == "deceased")
        self.metrics.victims_critical_active = sum(
            1 for v in self.victims
            if v.status in ("waiting", "en_route") and v.severity >= 4
        )
        self.metrics.ambulances_deployed = sum(
            1 for v in self.vehicles
            if v.type == "ambulance" and v.status in ("en_route", "on_scene")
        )

    # ── Event Queue ──────────────────────────────────────────────────────

    async def emit_event(self, event_type: str, data: dict):
        """Push event to broadcast queue."""
        await self._event_queue.put({
            "type": event_type,
            "data": data,
            "tick": self.tick,
            "timestamp": time.time(),
        })

    async def get_event(self) -> dict:
        """Pop next event from queue (blocks until available)."""
        return await self._event_queue.get()

    def has_events(self) -> bool:
        return not self._event_queue.empty()

    # ── Serialization ────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Full state snapshot for API responses."""
        return {
            "simulation": {
                "running": self.running,
                "paused": self.paused,
                "tick": self.tick,
                "elapsed_seconds": self.elapsed_seconds,
                "phase": self.phase,
            },
            "disasters": [d.to_dict() for d in self.disasters],
            "roads": {k: v.to_dict() for k, v in self.roads.items()},
            "victims": [v.to_dict() for v in self.victims],
            "vehicles": [v.to_dict() for v in self.vehicles],
            "hospitals": [h.to_dict() for h in self.hospitals],
            "metrics": self.metrics.to_dict(),
            "weather": self.weather,
        }

    def compact_snapshot(self) -> dict:
        """Minimal state snapshot for Gemini context (keep token count low)."""
        return {
            "tick": self.tick,
            "phase": self.phase,
            "active_disasters": len([d for d in self.disasters if d.active]),
            "waiting_victims": len(self.get_waiting_victims()),
            "critical_victims": len(self.get_critical_victims()),
            "available_vehicles": len(self.get_available_vehicles()),
            "hospitals": [
                {"id": h.id, "capacity_pct": h.capacity_percent, "status": h.status}
                for h in self.hospitals
            ],
            "metrics": {
                "rescued": self.metrics.victims_rescued,
                "deceased": self.metrics.victims_deceased,
                "total": self.metrics.victims_total,
            },
        }
