"""
CrisisOS — Vehicle Movement Simulation
Handles ambulance and fire truck movement along routes.
Vehicles interpolate position along assigned route waypoints each tick.
"""

import math
import random
from typing import Optional

from simulation.city import LatLng, SimulationState, Vehicle
from config import (
    VEHICLE_SPEED_KMH,
    VEHICLE_FUEL_CONSUMPTION,
    TICK_INTERVAL_SECONDS,
    WS_EVENTS,
)

ARRIVAL_THRESHOLD_DEGREES = 0.003
VEHICLE_SPEED_DEGREES_PER_TICK = 0.005
RESCUE_ONSCENE_TICKS = 3
HOSPITAL_DROPOFF_TICKS = 5

def check_arrival(vehicle, victim):
    dlat = abs(vehicle.location.lat - victim.location.lat)
    dlng = abs(vehicle.location.lng - victim.location.lng)
    distance = (dlat**2 + dlng**2) ** 0.5
    return distance < ARRIVAL_THRESHOLD_DEGREES

def move_vehicle_toward_target(vehicle, target_location):
    dlat = target_location.lat - vehicle.location.lat
    dlng = target_location.lng - vehicle.location.lng
    distance = (dlat**2 + dlng**2) ** 0.5
    
    if distance < ARRIVAL_THRESHOLD_DEGREES:
        return True  # ARRIVED
    
    # Move toward target
    move_fraction = min(1.0, VEHICLE_SPEED_DEGREES_PER_TICK / distance) if distance > 0 else 1.0
    vehicle.location.lat += dlat * move_fraction
    vehicle.location.lng += dlng * move_fraction
    return False  # still moving

class VehicleManager:
    """
    Manages vehicle movement, routing, and status transitions.
    Each tick, vehicles move along their assigned routes toward targets.
    """

    def __init__(self, state: SimulationState):
        self.state = state
        self._on_scene_counters: dict[str, int] = {}  # vehicle_id → ticks remaining on scene

    async def tick(self):
        """Process all vehicle movement for one tick."""
        for vehicle in self.state.vehicles:
            await self._tick_vehicle(vehicle)
            
    async def _tick_vehicle(self, vehicle: Vehicle):
        if vehicle.status == 'en_route':
            victim = self.state.get_victim(vehicle.assigned_victim)
            if not victim or not victim.location:
                return
            arrived = move_vehicle_toward_target(vehicle, victim.location)
            
            # Emit movement event
            await self.state.emit_event(
                WS_EVENTS["VEHICLE_MOVED"],
                {
                    "vehicle_id": vehicle.id,
                    "location": vehicle.location.to_dict(),
                    "heading": self._calculate_heading(vehicle),
                    "eta_seconds": 0,
                    "status": vehicle.status,
                },
            )
            
            if arrived or check_arrival(vehicle, victim):
                vehicle.status = 'on_scene'
                vehicle.onscene_ticks_remaining = RESCUE_ONSCENE_TICKS
                await self.state.emit_event(WS_EVENTS["VEHICLE_MOVED"], {
                    "vehicle_id": vehicle.id, "location": vehicle.location.to_dict(),
                    "heading": 0, "eta_seconds": 0, "status": 'on_scene'
                })
        
        elif vehicle.status == 'on_scene':
            vehicle.onscene_ticks_remaining -= 1
            if vehicle.onscene_ticks_remaining <= 0:
                # Rescue complete — now drive to hospital
                victim = self.state.get_victim(vehicle.assigned_victim)
                if victim:
                    victim.status = 'rescued'
                    self.state.metrics.victims_rescued += 1
                
                # Find nearest available hospital
                hospital = self._find_nearest_hospital(vehicle.location)
                if not hospital:
                    hospital = self.state.hospitals[0]  # fallback
                    
                vehicle.target_hospital = hospital.id
                vehicle.status = 'to_hospital'
                route = self.generate_simple_route(vehicle.location, hospital.location)
                vehicle.assigned_route = route
                vehicle.route_index = 0
                dist = vehicle.location.distance_km(hospital.location)
                eta_sec = (dist / 60.0) * 3600

                await self.state.emit_event(WS_EVENTS["VEHICLE_ASSIGNED"], {
                    "vehicle_id": vehicle.id,
                    "target_victim_id": f"hospital_{hospital.id}",
                    "route": route,
                    "estimated_seconds": eta_sec,
                    "tick": self.state.tick
                })
                
                if victim:
                    await self.state.emit_event(WS_EVENTS["VICTIM_RESCUED"], {'victim_id': victim.id, 'rescued_at': vehicle.location.to_dict(), 'hospital': hospital.id, 'tick': self.state.tick})
                
                await self.state.emit_event(WS_EVENTS["METRICS_UPDATE"], {"metrics": self.state.metrics.to_dict()})
                print(f"[RESCUE COMPLETE] Vehicle {vehicle.id} rescued {victim.id} at tick {self.state.tick}, heading to {hospital.id}")
                
        elif vehicle.status == 'to_hospital':
            hospital = self.state.get_hospital(vehicle.target_hospital)
            if not hospital:
                return
                
            arrived = move_vehicle_toward_target(vehicle, hospital.location)
            
            await self.state.emit_event(
                WS_EVENTS["VEHICLE_MOVED"],
                {
                    "vehicle_id": vehicle.id,
                    "location": vehicle.location.to_dict(),
                    "heading": self._calculate_heading(vehicle),
                    "eta_seconds": 0,
                    "status": vehicle.status,
                },
            )
            
            # Simple distance check to be robust
            if arrived or vehicle.location.distance_km(hospital.location) < 0.5:
                vehicle.status = 'at_hospital'
                vehicle.hospital_ticks_remaining = HOSPITAL_DROPOFF_TICKS
                
                # Increase hospital capacity
                hospital.capacity_used += 1
                
                await self.state.emit_event(WS_EVENTS["HOSPITAL_STATUS_CHANGE"], {
                    "hospital_id": hospital.id,
                    "capacity_percent": hospital.capacity_percent,
                    "status": hospital.status,
                    "name": hospital.name
                })
                print(f"[AT HOSPITAL] {vehicle.id} dropping off at {hospital.id}")
                
        elif vehicle.status == 'at_hospital':
            vehicle.hospital_ticks_remaining -= 1
            if vehicle.hospital_ticks_remaining <= 0:
                # Done at hospital — now available for next assignment
                vehicle.status = 'available'
                vehicle.assigned_victim = None
                vehicle.target_hospital = None
                
                await self.state.emit_event(WS_EVENTS["VEHICLE_MOVED"], {
                    "vehicle_id": vehicle.id, "location": vehicle.location.to_dict(),
                    "heading": 0, "eta_seconds": 0, "status": 'available'
                })
                
                # Immediately try to reassign
                print(f"[AVAILABLE] {vehicle.id} ready for next mission at tick {self.state.tick}")
                await self.try_reassign_vehicle(vehicle, self.state)
                
        elif vehicle.status == 'returning':
            await self._move_vehicle_home(vehicle)

    async def try_reassign_vehicle(self, vehicle, state):
        """Called immediately after a rescue completes"""
        
        # Find unassigned victims sorted by severity then time urgency
        unassigned = [
            v for v in state.victims 
            if v.status == 'waiting' and v.assigned_vehicle is None
        ]
        
        if not unassigned:
            vehicle.status = 'available'
            return
        
        # Sort: severity descending, then time_to_death ascending
        unassigned.sort(key=lambda v: (-v.severity, v.time_to_death_seconds))
        next_victim = unassigned[0]
        
        # Assign
        vehicle.status = 'en_route'
        vehicle.assigned_victim = next_victim.id
        next_victim.assigned_vehicle = vehicle.id
        next_victim.status = 'en_route'
        
        route = self.generate_simple_route(vehicle.location, next_victim.location)
        dist = vehicle.location.distance_km(next_victim.location)
        eta_sec = (dist / 60.0) * 3600  # assuming 60 km/h
        
        await state.emit_event(
            WS_EVENTS["VEHICLE_ASSIGNED"],
            {
                "vehicle_id": vehicle.id,
                "target_victim_id": next_victim.id,
                "route": route,
                "estimated_seconds": eta_sec,
                "tick": state.tick
            }
        )
        
        print(f"[REASSIGNED] Vehicle {vehicle.id} → next victim {next_victim.id}")

    async def _move_vehicle_home(self, vehicle: Vehicle):
        """Move vehicle back to its home location."""
        home = vehicle.home_location
        dist = vehicle.location.distance_km(home)

        if dist < 0.05:
            # Arrived home
            vehicle.location = LatLng(home.lat, home.lng)
            vehicle.status = "available"
            vehicle.assigned_route = []
            vehicle.route_index = 0
            vehicle.fuel = min(1.0, vehicle.fuel + 0.1)  # Refuel at base
            self.state.update_metrics()
            print(f"  🏠 {vehicle.id} returned to base — now available")
            return

        # Move toward home
        rain_factor = 1.0 - (self.state.weather.get("precipitation", 0) * 0.02)
        speed_kmh = VEHICLE_SPEED_KMH * max(0.5, rain_factor)
        distance_km = (speed_kmh / 3600) * TICK_INTERVAL_SECONDS

        fraction = min(1.0, distance_km / dist) if dist > 0 else 1.0
        vehicle.location = LatLng(
            lat=round(vehicle.location.lat + (home.lat - vehicle.location.lat) * fraction, 6),
            lng=round(vehicle.location.lng + (home.lng - vehicle.location.lng) * fraction, 6),
        )

        vehicle.fuel = max(0.0, vehicle.fuel - VEHICLE_FUEL_CONSUMPTION)

        await self.state.emit_event(
            WS_EVENTS["VEHICLE_MOVED"],
            {
                "vehicle_id": vehicle.id,
                "location": vehicle.location.to_dict(),
                "heading": self._calculate_heading(vehicle),
                "eta_seconds": 0,
                "status": vehicle.status,
            },
        )

    def assign_route(self, vehicle_id: str, route: list, victim_id: str = None):
        """
        Assign a route to a vehicle. Route is a list of LatLng dicts.
        Called by LogisticsAgent after route calculation.
        """
        vehicle = self.state.get_vehicle(vehicle_id)
        if not vehicle:
            return False

        vehicle.assigned_route = route
        vehicle.route_index = 0
        vehicle.status = "en_route"
        if victim_id:
            vehicle.assigned_victim = victim_id

        # Calculate initial ETA
        total_dist = 0.0
        prev = vehicle.location
        for wp in route:
            if isinstance(wp, dict):
                wp_loc = LatLng(wp["lat"], wp["lng"])
            elif isinstance(wp, LatLng):
                wp_loc = wp
            else:
                wp_loc = LatLng(wp[0], wp[1])
            total_dist += prev.distance_km(wp_loc)
            prev = wp_loc

        speed_kmh = VEHICLE_SPEED_KMH
        vehicle.eta_seconds = (total_dist / speed_kmh) * 3600 if speed_kmh > 0 else 0

        self.state.update_metrics()
        return True

    def _find_nearest_hospital(self, location: LatLng):
        """Find nearest hospital that isn't overloaded."""
        candidates = [h for h in self.state.hospitals if h.status != "overloaded"]
        if not candidates:
            candidates = self.state.hospitals  # Fallback to all

        if not candidates:
            return None

        return min(candidates, key=lambda h: location.distance_km(h.location))

    def _calculate_heading(self, vehicle: Vehicle) -> float:
        """Calculate heading in degrees based on route direction."""
        if not vehicle.assigned_route or vehicle.route_index >= len(vehicle.assigned_route):
            return 0.0

        target = vehicle.assigned_route[vehicle.route_index]
        if isinstance(target, dict):
            target_loc = LatLng(target["lat"], target["lng"])
        elif isinstance(target, LatLng):
            target_loc = target
        else:
            target_loc = LatLng(target[0], target[1])

        dlat = target_loc.lat - vehicle.location.lat
        dlng = target_loc.lng - vehicle.location.lng

        heading = math.degrees(math.atan2(dlng, dlat))
        return heading % 360

    def generate_simple_route(self, start: LatLng, end: LatLng, num_waypoints: int = 5) -> list[dict]:
        """
        Generate a simple interpolated route between two points.
        Used as fallback when ORS/NetworkX routing unavailable.
        Adds slight randomization for realistic-looking routes.
        """
        waypoints = []
        for i in range(num_waypoints + 1):
            t = i / num_waypoints
            # Add slight jitter for non-straight route
            jitter_lat = random.uniform(-0.002, 0.002) if 0 < i < num_waypoints else 0
            jitter_lng = random.uniform(-0.002, 0.002) if 0 < i < num_waypoints else 0

            lat = start.lat + (end.lat - start.lat) * t + jitter_lat
            lng = start.lng + (end.lng - start.lng) * t + jitter_lng
            waypoints.append([round(lat, 6), round(lng, 6)])

        return waypoints

    def get_status_summary(self) -> str:
        available = sum(1 for v in self.state.vehicles if v.status == "available")
        en_route = sum(1 for v in self.state.vehicles if v.status == "en_route")
        on_scene = sum(1 for v in self.state.vehicles if v.status == "on_scene")
        returning = sum(1 for v in self.state.vehicles if v.status == "returning")

        # Log per-vehicle detail for debugging
        details = []
        for v in self.state.vehicles:
            if v.type == "ambulance":
                victim_info = f"→{v.assigned_victim}" if v.assigned_victim else ""
                details.append(f"{v.id}:{v.status}{victim_info}")

        return (
            f"Vehicles: {available} avail | {en_route} enroute | "
            f"{on_scene} scene | {returning} ret [{' '.join(details)}]"
        )
