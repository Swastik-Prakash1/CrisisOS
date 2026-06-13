import React from 'react';
import { MapContainer, TileLayer, CircleMarker, Polyline, Circle, Marker, Tooltip, useMap } from 'react-leaflet';
import L from 'leaflet';
import useSimStore from '../../store/useSimStore';
import 'leaflet/dist/leaflet.css';

// Position interpolation along route
function getPositionAlongRoute(route, elapsedTicks, totalTicks) {
  if (!route || route.length < 2) return null;
  const progress = totalTicks > 0 ? Math.min(1.0, elapsedTicks / totalTicks) : 1.0;
  
  let totalDist = 0;
  const dists = [0];
  for (let i = 1; i < route.length; i++) {
    const p1 = Array.isArray(route[i-1]) ? route[i-1] : [route[i-1].lat, route[i-1].lng];
    const p2 = Array.isArray(route[i]) ? route[i] : [route[i].lat, route[i].lng];
    const d = Math.sqrt(
      Math.pow(p2[0] - p1[0], 2) + 
      Math.pow(p2[1] - p1[1], 2)
    );
    totalDist += d;
    dists.push(totalDist);
  }
  
  if (totalDist === 0) return Array.isArray(route[0]) ? route[0] : [route[0].lat, route[0].lng];

  const target = progress * totalDist;
  for (let i = 1; i < route.length; i++) {
    if (dists[i] >= target) {
      const t = (target - dists[i-1]) / (dists[i] - dists[i-1]);
      const p1 = Array.isArray(route[i-1]) ? route[i-1] : [route[i-1].lat, route[i-1].lng];
      const p2 = Array.isArray(route[i]) ? route[i] : [route[i].lat, route[i].lng];
      return [
        p1[0] + (p2[0] - p1[0]) * t,
        p1[1] + (p2[1] - p1[1]) * t
      ];
    }
  }
  
  const last = route[route.length - 1];
  return Array.isArray(last) ? last : [last.lat, last.lng];
}

const TILE_URL = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';
const TILE_ATTRIBUTION = '&copy; OpenStreetMap contributors &copy; CARTO';
const DELHI_CENTER = [28.6139, 77.2090];
const INITIAL_ZOOM = 13;

// Severity to color mapping for victims
const VICTIM_COLORS = {
  5: '#FF4444',
  4: '#FF6644',
  3: '#FFB020',
  2: '#FFD700',
  1: '#00FF88',
};

const STATUS_COLORS = {
  waiting: null, // use severity
  en_route: '#00D4FF',
  rescued: '#00D4FF',
  deceased: '#3D4F6E',
};

// Vehicle icons
function createVehicleIcon(type, status) {
  const emoji = type === 'ambulance' ? '🚑' : '🚒';
  const glow = status === 'en_route' ? 'filter: drop-shadow(0 0 6px rgba(0, 212, 255, 0.8));' :
               status === 'on_scene' ? 'filter: drop-shadow(0 0 6px rgba(255, 176, 32, 0.8));' : '';

  return L.divIcon({
    html: `<div style="font-size: 20px; ${glow}">${emoji}</div>`,
    className: 'vehicle-marker',
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });
}

// Hospital icon
function createHospitalIcon(status) {
  const borderColor = status === 'overloaded' || status === 'critical' ? '#FF4444' :
                       status === 'warning' ? '#FFB020' : '#00FF88';
  return L.divIcon({
    html: `<div class="hospital-marker" style="border-color: ${borderColor}; color: ${borderColor}">+</div>`,
    className: '',
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });
}

function VictimMarkers() {
  const { victims } = useSimStore();
  const active = victims.filter(v => v.status !== 'rescued');

  return (
    <>
      {active.map(v => {
        const color = STATUS_COLORS[v.status] || VICTIM_COLORS[v.severity] || '#FFD700';
        const opacity = v.status === 'deceased' ? 0.3 : v.status === 'rescued' ? 0.4 : 0.9;
        const radius = v.severity >= 4 ? 6 : v.severity >= 3 ? 5 : 4;

        return (
          <CircleMarker
            key={v.id}
            center={[v.location.lat, v.location.lng]}
            radius={radius}
            pathOptions={{
              color: color,
              fillColor: color,
              fillOpacity: opacity * 0.7,
              opacity: opacity,
              weight: 1.5,
            }}
          >
            <Tooltip>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11 }}>
                <strong>{v.id}</strong> | Severity: {v.severity} | {v.status.toUpperCase()}<br />
                TTD: {v.time_to_death_seconds?.toFixed(0) || '?'}s | {v.nearest_landmark || v.sector}
              </div>
            </Tooltip>
          </CircleMarker>
        );
      })}
    </>
  );
}

function DisasterOverlays() {
  const { disasters } = useSimStore();

  return (
    <>
      {disasters.filter(d => d.active !== false).map(d => {
        if (d.type === 'earthquake') {
          return (
            <Circle
              key={d.id}
              center={[d.location.lat, d.location.lng]}
              radius={(d.spread_radius || 1) * 800}
              pathOptions={{
                color: '#FF4444',
                fillColor: '#FF4444',
                fillOpacity: 0.08,
                weight: 2,
                dashArray: '8 4',
              }}
            >
              <Tooltip permanent>
                <span style={{ color: '#FF4444', fontFamily: "'JetBrains Mono', monospace", fontSize: 10 }}>
                  {d.name}
                </span>
              </Tooltip>
            </Circle>
          );
        }

        if (d.type === 'fire') {
          return (
            <Circle
              key={d.id}
              center={[d.location.lat, d.location.lng]}
              radius={(d.spread_radius || 0.5) * 600}
              pathOptions={{
                color: '#FF9632',
                fillColor: '#FF6600',
                fillOpacity: 0.15,
                weight: 2,
              }}
            >
              <Tooltip>
                <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10 }}>
                  🔥 {d.name} (radius: {(d.spread_radius || 0).toFixed(2)}km)
                </span>
              </Tooltip>
            </Circle>
          );
        }

        return null;
      })}
    </>
  );
}

function BlockedRoadMarkers() {
  const { blockedRoads } = useSimStore();

  return (
    <>
      {blockedRoads.filter(r => r.location).map(r => (
        <CircleMarker
          key={r.edge_id}
          center={[r.location.lat, r.location.lng]}
          radius={8}
          pathOptions={{
            color: '#FF4444',
            fillColor: '#FF4444',
            fillOpacity: 0.5,
            weight: 2,
          }}
        >
          <Tooltip>
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10 }}>
              🚧 BLOCKED: {r.name || r.edge_id}
            </span>
          </Tooltip>
        </CircleMarker>
      ))}
    </>
  );
}

function VehicleMarkers() {
  const { vehicles, tick } = useSimStore();

  return (
    <>
      {vehicles.map(v => {
        if (!v.location) return null;
        
        let displayPos = [v.location.lat, v.location.lng];
        if (v.assignedRoute && v.assignedRoute.length > 1 && v.routeStartTick !== undefined && v.estimatedTicks > 0) {
            const elapsedTicks = tick - v.routeStartTick;
            const interpPos = getPositionAlongRoute(v.assignedRoute, elapsedTicks, v.estimatedTicks);
            if (interpPos && (v.status === 'en_route' || v.status === 'to_hospital')) {
                displayPos = interpPos;
            }
        }
        
        return (
          <Marker
            key={v.id}
            position={displayPos}
            icon={createVehicleIcon(v.type, v.status)}
          >
            <Tooltip>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10 }}>
                <strong>{v.id}</strong> ({v.type}) | {v.status.toUpperCase()}
                {v.assigned_victim && <><br />Target: {v.assigned_victim}</>}
                {v.eta_seconds > 0 && <><br />ETA: {v.eta_seconds.toFixed(0)}s</>}
              </div>
            </Tooltip>
          </Marker>
        );
      })}
    </>
  );
}

function HospitalMarkers() {
  const { hospitals } = useSimStore();

  return (
    <>
      {hospitals.map(h => {
        if (!h.location) return null;
        return (
          <Marker
            key={h.id}
            position={[h.location.lat, h.location.lng]}
            icon={createHospitalIcon(h.status)}
          >
            <Tooltip>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10 }}>
                <strong>{h.name}</strong><br />
                Capacity: {h.capacity_percent?.toFixed(0) || 0}% [{(h.status || 'ok').toUpperCase()}]
              </div>
            </Tooltip>
          </Marker>
        );
      })}
    </>
  );
}

function ActiveRoutes() {
  const { vehicles } = useSimStore();

  return (
    <>
      {vehicles
        .filter(v => v.assignedRoute && v.assignedRoute.length > 2 
                  && (v.status === 'en_route' || v.status === 'to_hospital'))
        .map(v => {
          const positions = v.assignedRoute.map(p =>
            Array.isArray(p) ? p : [p.lat, p.lng]
          );
          
          return (
            <Polyline
              key={`route-${v.id}`}
              positions={positions}
              pathOptions={{
                color: v.status === 'to_hospital' ? '#00FF88' : '#00D4FF',
                weight: 2,
                opacity: 0.65,
                dashArray: '6, 4'
              }}
            />
          );
      })}
    </>
  );
}

export default function CrisisMap() {
  return (
    <div className="center-map">
      <MapContainer
        center={DELHI_CENTER}
        zoom={INITIAL_ZOOM}
        style={{ width: '100%', height: '100%' }}
        zoomControl={true}
      >
        <TileLayer url={TILE_URL} attribution={TILE_ATTRIBUTION} />
        <DisasterOverlays />
        <BlockedRoadMarkers />
        <VictimMarkers />
        <VehicleMarkers />
        <HospitalMarkers />
        <ActiveRoutes />
      </MapContainer>
    </div>
  );
}
