"""
CrisisOS — Configuration & Constants
All simulation parameters, API keys, and system constants.
"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


# ── API Keys ─────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
ORS_API_KEY = os.getenv("ORS_API_KEY", "")

# ── City Configuration ───────────────────────────────────────────────────────
CITY_NAME = os.getenv("SIMULATION_CITY", "Delhi")
CITY_CENTER = (28.6139, 77.2090)  # Delhi center
CITY_BOUNDS = {
    "lat_min": 28.58,
    "lat_max": 28.65,
    "lng_min": 77.18,
    "lng_max": 77.25,
}
MAP_INITIAL_ZOOM = 13

# ── Simulation Timing ────────────────────────────────────────────────────────
TICK_INTERVAL_SECONDS = 2          # Real-time seconds per tick
SIMULATION_DURATION_TICKS = 180    # 6 minutes total (180 ticks × 2s)

# ── Disaster Tick Scheduling ─────────────────────────────────────────────────
DISASTER_TICK_EARTHQUAKE = int(os.getenv("DISASTER_TICK_EARTHQUAKE", "15"))
DISASTER_TICK_ROAD_COLLAPSE = int(os.getenv("DISASTER_TICK_ROAD_COLLAPSE", "25"))
DISASTER_TICK_FIRE = int(os.getenv("DISASTER_TICK_FIRE", "35"))
DISASTER_TICK_HOSPITAL_OVERLOAD = int(os.getenv("DISASTER_TICK_HOSPITAL_OVERLOAD", "50"))

# ── Conflict Scenario Scheduling ─────────────────────────────────────────────
CONFLICT_TICK_ROAD_SACRIFICE = int(os.getenv("CONFLICT_TICK_ROAD_SACRIFICE", "36"))
CONFLICT_TICK_RESOURCE_EXHAUSTION = int(os.getenv("CONFLICT_TICK_RESOURCE_EXHAUSTION", "65"))

# ── Agent Decision Cycle Intervals (in ticks) ────────────────────────────────
AGENT_CYCLE_INTELLIGENCE = 3      # Every 6 seconds (3 ticks × 2s)
AGENT_CYCLE_LOGISTICS = 4         # Every 8 seconds
AGENT_CYCLE_MEDICAL = 5           # Every 10 seconds
AGENT_CYCLE_PREDICTION = 8        # Every 16 seconds (≈15s)
AGENT_CYCLE_COMMANDER = 4         # Every 8 seconds — arbitrates after proposals

# ── Victim Parameters ────────────────────────────────────────────────────────
VICTIM_SEVERITY_WEIGHTS = {
    5: 1.0,    # Immediate — life threatening
    4: 0.8,    # Critical
    3: 0.5,    # Serious
    2: 0.3,    # Moderate
    1: 0.1,    # Minor
}

# Time-to-death ranges by severity (in seconds)
VICTIM_TTD_RANGES = {
    5: (180, 300),
    4: (360, 480),
    3: (600, 900),
    2: (1200, 1800),
    1: (2400, 3600),
}

# Severity distribution weights for spawning
VICTIM_SEVERITY_DISTRIBUTION = {
    1: 0.15,   # 15% minor
    2: 0.30,   # 30% moderate
    3: 0.30,   # 30% serious
    4: 0.18,   # 18% critical
    5: 0.07,   # 7% immediate
}

VICTIM_SPAWN_BURST_SIZE = 12      # Victims per disaster event
VICTIM_SPAWN_RADIUS_KM = 1.5     # Spread radius around epicenter

# ── Vehicle Parameters ────────────────────────────────────────────────────────
VEHICLE_SPEED_KMH = 80             # Emergency vehicle speed with sirens
VEHICLE_ON_SCENE_TICKS = 3        # Time spent on scene (6 seconds)
VEHICLE_FUEL_CONSUMPTION = 0.002  # Per tick while moving

# ── Hospital Configuration ────────────────────────────────────────────────────
HOSPITALS = [
    {
        "id": "H1",
        "name": "City General Hospital",
        "location": {"lat": 28.6280, "lng": 77.2195},
        "capacity_total": 120,
        "capacity_used": 72,   # Start at 60%
    },
    {
        "id": "H2",
        "name": "North District Medical Center",
        "location": {"lat": 28.6420, "lng": 77.1985},
        "capacity_total": 80,
        "capacity_used": 28,   # Start at 35%
    },
    {
        "id": "H3",
        "name": "South Emergency Hospital",
        "location": {"lat": 28.5950, "lng": 77.2280},
        "capacity_total": 60,
        "capacity_used": 45,   # Start at 75% — will go critical
    },
]

# ── Initial Vehicle Fleet ─────────────────────────────────────────────────────
INITIAL_VEHICLES = [
    {
        "id": "A1",
        "type": "ambulance",
        "location": {"lat": 28.6280, "lng": 77.2195},  # At City General
    },
    {
        "id": "A2",
        "type": "ambulance",
        "location": {"lat": 28.6420, "lng": 77.1985},  # At North District
    },
    {
        "id": "A3",
        "type": "ambulance",
        "location": {"lat": 28.5950, "lng": 77.2280},  # At South Emergency
    },
    {
        "id": "FT1",
        "type": "fire_truck",
        "location": {"lat": 28.6180, "lng": 77.2050},  # Fire station 1
    },
    {
        "id": "FT2",
        "type": "fire_truck",
        "location": {"lat": 28.6350, "lng": 77.2300},  # Fire station 2
    },
]

# ── Road Network ──────────────────────────────────────────────────────────────
ROAD_GRAPH_PATH = os.path.join(os.path.dirname(__file__), "data", "city_graph.gpickle")
ENABLE_OSMNX_DOWNLOAD = os.getenv("ENABLE_OSMNX_DOWNLOAD", "false").lower() == "true"

# ── Baseline Simulation ──────────────────────────────────────────────────────
ENABLE_BASELINE = os.getenv("ENABLE_BASELINE", "true").lower() == "true"

# ── Server ────────────────────────────────────────────────────────────────────
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
CORS_ORIGINS = ["http://localhost:5173", "http://localhost:3000", "*"]

# ── Delhi Landmark Locations (for realistic incident naming) ──────────────────
DELHI_LANDMARKS = {
    "Connaught Place": (28.6315, 77.2167),
    "Lajpat Nagar": (28.5700, 77.2400),
    "Karol Bagh": (28.6519, 77.1907),
    "Chandni Chowk": (28.6506, 77.2301),
    "Saket": (28.5244, 77.2167),
    "Hauz Khas": (28.5494, 77.2001),
    "Rajouri Garden": (28.6492, 77.1219),
    "Dwarka": (28.5921, 77.0460),
    "Rohini": (28.7324, 77.1104),
    "Nehru Place": (28.5491, 77.2533),
    "India Gate": (28.6129, 77.2295),
    "ITO Junction": (28.6285, 77.2410),
    "Moolchand": (28.5689, 77.2388),
    "AIIMS": (28.5672, 77.2100),
    "Ring Road (Lajpat Nagar)": (28.5720, 77.2350),
    "Mathura Road": (28.5850, 77.2450),
    "Outer Ring Road (Nehru Nagar)": (28.6100, 77.2500),
}

# ── Sectors (for agent spatial reasoning) ─────────────────────────────────────
SECTORS = {
    "A": {"center": (28.635, 77.215), "radius_km": 1.5, "name": "North Central"},
    "B": {"center": (28.615, 77.195), "radius_km": 1.5, "name": "West Central"},
    "C": {"center": (28.595, 77.230), "radius_km": 1.5, "name": "South East"},
    "D": {"center": (28.625, 77.240), "radius_km": 1.5, "name": "East"},
}

# ── Agent Display Names ──────────────────────────────────────────────────────
AGENT_COLORS = {
    "COMMANDER":    "#00D4FF",
    "MEDICAL":      "#00FF88",
    "LOGISTICS":    "#FFB020",
    "PREDICTION":   "#8B5CF6",
    "INTELLIGENCE": "#3B82F6",
}

# ── Weather Defaults (fallback if Open-Meteo unavailable) ─────────────────────
DEFAULT_WEATHER = {
    "wind_speed": 15.0,       # km/h
    "wind_direction": 315,    # NW
    "precipitation": 0.0,     # mm
    "temperature": 38.0,      # °C (Delhi summer)
}

# ── Gemini Configuration ─────────────────────────────────────────────────────
GEMINI_MODEL = "gemini-1.5-flash"
GEMINI_MAX_TOKENS = 300
GEMINI_TIMEOUT_SECONDS = 5

# ── WebSocket Event Types ─────────────────────────────────────────────────────
WS_EVENTS = {
    # Simulation lifecycle
    "SIM_STARTED": "sim_started",
    "SIM_PAUSED": "sim_paused",
    "SIM_ENDED": "sim_ended",
    "SIM_TICK": "sim_tick",

    # Disasters
    "DISASTER_TRIGGERED": "disaster_triggered",
    "ROAD_BLOCKED": "road_blocked",
    "FIRE_SPREADING": "fire_spreading",
    "HOSPITAL_STATUS_CHANGE": "hospital_status_change",

    # Agents
    "AGENT_PROPOSAL": "agent_proposal",
    "CONFLICT_DETECTED": "conflict_detected",
    "DECISION_MADE": "decision_made",
    "DECISION_EXPLANATION_READY": "decision_explanation_ready",

    # Victims
    "VICTIM_SPAWNED": "victim_spawned",
    "VICTIM_STATUS_CHANGED": "victim_status_changed",
    "VICTIM_RESCUED": "victim_rescued",
    "VICTIM_DECEASED": "victim_deceased",

    # Vehicles
    "VEHICLE_MOVED": "vehicle_moved",
    "VEHICLE_ASSIGNED": "vehicle_assigned",
    "VEHICLE_REROUTED": "vehicle_rerouted",

    # Prediction
    "PREDICTION_ALERT": "prediction_alert",

    # Metrics
    "METRICS_UPDATE": "metrics_update",

    # Human Override
    "OVERRIDE_WARNING": "override_warning",

    # Reports
    "REPORT_READY": "report_ready",
}
