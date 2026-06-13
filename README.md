<div align="center">

```
 ██████╗██████╗ ██╗███████╗██╗███████╗ ██████╗ ███████╗
██╔════╝██╔══██╗██║██╔════╝██║██╔════╝██╔═══██╗██╔════╝
██║     ██████╔╝██║███████╗██║███████╗██║   ██║███████╗
██║     ██╔══██╗██║╚════██║██║╚════██║██║   ██║╚════██║
╚██████╗██║  ██║██║███████║██║███████║╚██████╔╝███████║
 ╚═════╝╚═╝  ╚═╝╚═╝╚══════╝╚═╝╚══════╝ ╚═════╝ ╚══════╝
```

### *When disaster strikes, decisions determine who lives.*

**An autonomous multi-agent operating system for disaster response —  
where every AI decision is explainable, auditable, and measurable.**

<br/>

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Leaflet](https://img.shields.io/badge/Leaflet-OpenStreetMap-199900?style=for-the-badge&logo=leaflet&logoColor=white)](https://leafletjs.com)
[![Gemini](https://img.shields.io/badge/Gemini-1.5_Flash-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev)
[![License](https://img.shields.io/badge/License-MIT-00D4FF?style=for-the-badge)](LICENSE)

<br/>

[![Live Demo](https://img.shields.io/badge/🌐_LIVE_DEMO-View_CrisisOS-00D4FF?style=for-the-badge)](https://crisisos.netlify.app)
[![FAR AWAY](https://img.shields.io/badge/🏆_FAR_AWAY_2026-Agentic_&_Autonomous_Systems-FFB020?style=for-the-badge)](https://faraway.zuup.dev)

<br/>

![CrisisOS Demo](https://raw.githubusercontent.com/YOUR_USERNAME/crisisos/main/assets/demo.gif)

> *Replace the above with your actual demo GIF or screenshot*

</div>

---

## 🎯 What Is CrisisOS?

CrisisOS is **not a disaster simulator**. The simulation exists only to generate difficult decisions.

The actual product is a **multi-agent reasoning system** that demonstrates what happens when five specialized AI agents are given incomplete information, scarce resources, and life-or-death tradeoffs — and must coordinate to save the most lives possible.

> **"Emergency response doesn't fail because resources are missing.  
> It fails because every critical decision sacrifices something."**

CrisisOS makes those tradeoffs **visible**, **explainable**, and **measurable**.

---

## ⚡ The Problem

In the **2023 Turkey-Syria earthquake** (M7.8, 50,339 deaths):
- 90+ international rescue teams were deployed
- Teams had **no shared command system**
- Coordinators spread **paper maps on ambulance hoods** in the dark
- Some areas received **zero help for 4 days**

The failure wasn't capability. It was **coordination under uncertainty**.

After **72 hours**, earthquake survival rates drop to **5-10%**.  
Every hour of delayed coordination moves victims from *likely to survive* → *unlikely to survive*.

---

## 🧠 How CrisisOS Works

```
┌─────────────────────────────────────────────────────────────────┐
│                        LIVE CITY STATE                          │
│         (Real Delhi road network via OpenStreetMap)             │
└──────────────────────────┬──────────────────────────────────────┘
                           │ shared state, updated every tick
         ┌─────────────────┼──────────────────┐
         │                 │                  │
    ┌────▼────┐      ┌─────▼─────┐     ┌─────▼──────┐
    │  INTEL  │      │  MEDICAL  │     │  LOGISTICS │
    │  AGENT  │      │   AGENT   │     │   AGENT    │
    │         │      │           │     │            │
    │ Hotspot │      │  Triage   │     │  A* Route  │
    │ mapping │      │  scoring  │     │  planning  │
    └────┬────┘      └─────┬─────┘     └─────┬──────┘
         │                 │                  │
         └─────────────────┼──────────────────┘
                           │ proposals + conflicts
                    ┌──────▼───────┐
                    │  PREDICTION  │
                    │    AGENT     │
                    │              │
                    │  2-min ahead │
                    │  lookahead   │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  STRATEGIC   │
                    │  COMMANDER   │◄── Deterministic utility scoring
                    │              │    (Gemini explains the decision)
                    │  Arbitrates  │
                    │  conflicts   │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
       ┌──────▼──┐  ┌──────▼──┐  ┌────▼────────┐
       │DECISION │  │REASONING│  │AFTER-ACTION │
       │ LEDGER  │  │  PANEL  │  │   REPORT    │
       │(audit)  │  │(live UI)│  │(post-sim)   │
       └─────────┘  └─────────┘  └─────────────┘
```

---

## 🤖 The Five Agents

| Agent | Role | Decision Cycle |
|-------|------|----------------|
| 👑 **Strategic Commander** | Arbitrates conflicts between agents using utility scoring. Fully deterministic — never delegates to LLM. Gemini only explains the decision after it's made. | 8s |
| 🛰️ **Intelligence Agent** | Processes real-time city state, identifies victim hotspots, assesses route corridor passability, feeds all other agents. | 5s |
| 🚑 **Logistics Agent** | A* pathfinding on real Delhi road network via OpenStreetMap + openrouteservice. Auto-reroutes when roads collapse. Manages full rescue cycle: victim → hospital → return. | 8s |
| 🏥 **Medical Agent** | Applies START triage protocol. Manages hospital capacity. Makes the heartbreaking **expectant triage** decision for unreachable victims. | 10s |
| 🔮 **Prediction Agent** | 2-minute lookahead: projects fire spread direction using wind data (Open-Meteo), hospital overload timing, and route closures **before they happen**. | 15s |

---

## ⚔️ The Conflict Engine

The core innovation. CrisisOS deliberately generates scenarios with **no objectively correct answer**.

### Scenario: Road Sacrifice

```
SITUATION:
  • 1 critical victim (severity 5) needs Route 7
  • Route 7 is the ONLY corridor to 14 other victims in Sector C
  • Time to death: 8 minutes
  • Route closure (fire spread): 6 minutes

AGENT DEBATE:
  ┌─────────────┬────────────────────────────────────────┬────────┬──────┐
  │ Agent       │ Proposal                               │Utility │ Conf │
  ├─────────────┼────────────────────────────────────────┼────────┼──────┤
  │ MEDICAL   ✓ │ Send Ambulance 1 immediately           │  0.82  │  83% │
  │ LOGISTICS   │ Hold Route 7 — risk score too high     │  0.71  │  76% │
  │ COMMANDER   │ Preserve corridor, A2 via alt route    │  0.77  │  62% │
  └─────────────┴────────────────────────────────────────┴────────┴──────┘

COMMANDER REASONING (Gemini):
  "Although Victim 204 is immediately critical, committing Ambulance 1
   to Route 7 would seal the only remaining access to 15 victims in
   Sector C before fire spread closes the corridor. Expected survival
   value of preserving corridor access is 31% higher over 20 minutes."
```

Every decision is logged to the **Decision Ledger** with:
- Confidence score
- Alternative considered
- Reason alternative was rejected  
- Predicted outcome
- Actual outcome (filled post-simulation)

---

## 🗺️ Real Delhi Road Network

CrisisOS uses **real urban geography**, not a toy grid.

- Map tiles: **CartoDB Dark Matter** (dark command center aesthetic)
- Road routing: **OpenStreetMap** via `osmnx`
- Real-time directions: **openrouteservice API** (A* on actual Delhi streets)
- Pathfinding fallback: **NetworkX A*** (works offline, always available)
- Weather context: **Open-Meteo API** (wind speed affects fire spread direction)

```
Ambulance route colours:
  ── ── ──  CYAN   →  En route to victim
  ── ── ──  GREEN  →  Delivering patient to hospital
```

---

## 👤 Human Override Mode

CrisisOS doesn't replace emergency commanders. It makes them better.

```
Human command: "Send all units to Sector A"

CrisisOS response (before executing):
┌─────────────────────────────────────────────────────┐
│  ⚠  AI ADVISORY                                     │
│                                                     │
│  This command is predicted to increase              │
│  casualties by  +27                                 │
│                                                     │
│  Recommended alternative:                           │
│  Maintain 1 unit in Sector B and C, redirect        │
│  1 unit to Sector A.                                │
│                                                     │
│  [ EXECUTE ANYWAY ]    [ FOLLOW AI RECOMMENDATION ] │
└─────────────────────────────────────────────────────┘
```

The system tracks override outcomes in the After-Action Report —  
showing whether the human or the AI made the better call.

---

## 📋 Decision Ledger & After-Action Report

```
╔══════════════════════════════════════════════════════════╗
║          CrisisOS — CRISIS RESPONSE REPORT              ║
╚══════════════════════════════════════════════════════════╝

EVENT SUMMARY
Event:        Earthquake M7.1 — Connaught Place, New Delhi
Duration:     6 minutes simulated
Weather:      Wind 12km/h NE (Open-Meteo live data)

CASUALTY SUMMARY
Total victims:        84
Rescued:             28   (33% survival rate)
Conflicts resolved:  12
Total AI decisions:  115

CRITICAL DECISION — Tick 65
Prioritize Sector B over Sector A
Predicted casualty reduction: 18%
Actual casualty reduction:    21%  ✓ Model accurate

HUMAN OVERRIDE — Tick 89
Command: Evacuate Hospital H2
AI warning issued: +7 casualties projected
Human reversed decision: Yes
Outcome: 6 additional casualties avoided
══════════════════════════════════════════════════════════
```

---

## 🖥️ UI — Tactical Command Center

```
┌──────────────┬──────────────────────────────┬───────────────────┐
│ ACTIVE        │                              │ AGENT REASONING   │
│ INCIDENTS     │   Delhi Road Network         │                   │
│               │   (CartoDB Dark Matter)      │ CONFLICT ACTIVE ● │
│ ● M7.1 EQ     │                              │                   │
│ ⚡ Road Coll  │   🚑 ── ── ──►  🏥          │ MEDICAL ✓         │
│ 🔥 Structure  │      cyan route              │ Recall A2→V0057   │
│ 🏥 Patient S  │   🚑 ── ── ──►  🏥          │ Util:0.78 Cf:82%  │
│               │      green route             │                   │
│ RESOURCES     │                              │ LOGISTICS         │
│ A1 EN ROUTE   │   ● ● ●  victim clusters    │ No resources avail│
│ A2 TO HOSP    │   ○ ○    rescued (green)    │ Util:0.72 Cf:76%  │
│ A3 ON SCENE   │                              │                   │
│               │                              │ COMMANDER Tick 65 │
│ HOSPITALS     │                              │ Conf: 56% Δ=0.02  │
│ H1  68% ████  │                              │ Exp util 0.77>0.74│
│ H2  35% ██    │                              │                   │
│ H3 100% OVERLD│                              │ SYSTEM ACTIVITY   │
├──────────────┴──────────────────────────────┴───────────────────┤
│  VICTIMS 84  │  RESCUED 28  │  CRITICAL 5  │  DECISIONS 115     │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

### Backend
| Component | Technology |
|-----------|------------|
| API Framework | FastAPI + Uvicorn |
| Agent Architecture | Plain Python classes (5 agents) |
| Road Network | NetworkX + osmnx (OpenStreetMap) |
| Pathfinding | A* algorithm on OSM graph |
| Road Routing | openrouteservice API + A* fallback |
| LLM | Google Gemini 1.5 Flash (reasoning text only) |
| Real-time | WebSocket (FastAPI native) |
| Weather | Open-Meteo API |

### Frontend
| Component | Technology |
|-----------|------------|
| Framework | React 18 + Vite |
| Map | Leaflet.js + react-leaflet |
| Map Tiles | CartoDB Dark Matter (OpenStreetMap) |
| State | Zustand |
| Styling | Tailwind CSS |
| Charts | Recharts |
| Deployment | Netlify |

---

## 🚀 Quick Start

### Prerequisites
```bash
Python 3.11+
Node.js 18+
```

### 1. Clone
```bash
git clone https://github.com/YOUR_USERNAME/crisisos.git
cd crisisos
```

### 2. Backend
```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux  
source venv/bin/activate

pip install -r requirements.txt
```

Create `backend/.env`:
```env
GEMINI_API_KEY=your_gemini_api_key_here
ORS_API_KEY=your_openrouteservice_api_key_here
```

```bash
uvicorn main:app --reload --port 8000
```

### 3. Frontend
```bash
cd frontend
npm install
```

Create `frontend/.env`:
```env
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws
```

```bash
npm run dev
```

### 4. Open
```
http://localhost:5173
```

Click **START SIM** and watch the agents activate.

---

## 📁 Project Structure

```
crisisos/
├── backend/
│   ├── main.py                    # FastAPI app + WebSocket hub
│   ├── simulation/
│   │   ├── city.py                # SimulationState + city graph
│   │   ├── disaster.py            # Earthquake, fire, road collapse events
│   │   ├── victims.py             # Victim spawning + countdown timers
│   │   └── vehicles.py            # Ambulance movement + rescue cycle
│   ├── agents/
│   │   ├── base_agent.py          # BaseAgent + Decision Memory
│   │   ├── commander.py           # Deterministic arbitration + utility scoring
│   │   ├── intelligence.py        # Hotspot detection + route assessment
│   │   ├── logistics.py           # A* routing + ORS API + hospital delivery
│   │   ├── medical.py             # START triage + hospital capacity
│   │   └── prediction.py          # 2-min lookahead + weather integration
│   ├── engine/
│   │   ├── conflict_engine.py     # Conflict scenario generator
│   │   ├── decision_ledger.py     # Append-only audit trail
│   │   ├── utility_scorer.py      # Commander utility function
│   │   └── gemini_explainer.py    # Async LLM explanation layer
│   ├── reports/
│   │   └── after_action.py        # Post-simulation report generator
│   └── requirements.txt
│
└── frontend/
    ├── src/
    │   ├── config.js              # Environment variable config
    │   ├── store/
    │   │   └── useSimStore.js     # Zustand global state
    │   ├── components/
    │   │   ├── layout/            # Header, LeftPanel, RightPanel, BottomBar
    │   │   ├── map/               # CrisisMap, VehicleMarker, RouteOverlay
    │   │   ├── panels/            # AgentReasoning, ActivityLog, Predictions
    │   │   └── overlays/          # HumanOverride, JudgeReplay, AfterAction
    │   └── hooks/
    │       └── useWebSocket.js    # Auto-reconnecting WebSocket
    ├── netlify.toml               # Netlify deployment config
    └── public/_redirects          # SPA routing fallback
```

---

## 🔌 WebSocket Event Reference

| Event | Direction | Description |
|-------|-----------|-------------|
| `sim_started` | Server→Client | Simulation begins, city state snapshot |
| `disaster_triggered` | Server→Client | New disaster event with location + severity |
| `victim_spawned` | Server→Client | New victim with countdown timer |
| `agent_proposal` | Server→Client | Agent has proposed an action |
| `conflict_detected` | Server→Client | Two agents disagree on same resource |
| `decision_made` | Server→Client | Commander has arbitrated — full Decision object |
| `decision_explanation_ready` | Server→Client | Gemini explanation loaded (async) |
| `vehicle_assigned` | Server→Client | Vehicle dispatched with full route waypoints |
| `vehicle_rerouted` | Server→Client | Road blocked, vehicle on new route |
| `victim_rescued` | Server→Client | Rescue complete |
| `prediction_alert` | Server→Client | Proactive warning from Prediction Agent |
| `override_warning` | Server→Client | Human command would increase casualties |
| `report_ready` | Server→Client | After-action report generated |
| `human_command` | Client→Server | Human override command |
| `start_simulation` | Client→Server | Begin simulation |

---

## 🧪 Design Philosophy

### Why plain Python classes instead of LangGraph?

LangGraph adds framework overhead that slows development and debugging. Five plain Python classes with a message-passing protocol achieve the same multi-agent coordination with zero framework dependency.

### Why is the Commander deterministic?

If Gemini decides the action and the API goes down during a demo — the entire decision layer fails. Instead:

```
Agents propose → Commander scores via utility function → Decision made → Gemini explains
```

Gemini only enriches the reasoning panel. The simulation never waits for an LLM response.

### Why real road networks?

When a road collapses and the Logistics Agent reroutes around it — you need to **see** the route change on the actual Delhi map. On a toy grid, that moment is meaningless. On a real road network, it's undeniable.

---

## 🗺️ Roadmap

```
Phase 1 — TODAY (Hackathon MVP)
  ✅ 5-agent coordination on simulated city
  ✅ Real Delhi road network (OpenStreetMap)
  ✅ Conflict Engine + Decision Ledger
  ✅ Human Override with casualty projection
  ✅ After-Action Report + Judge Replay Mode
  ✅ Gemini-powered decision explanations

Phase 2 — DELHI ROUND
  ◻ Live NDRF/SDRF data integration
  ◻ Real hospital capacity APIs
  ◻ IoT sensor feeds (flood sensors, thermal cameras)
  ◻ Live Open-Meteo weather routing

Phase 3 — JAPAN FINALS (VISION)
  ◻ Google Earth Engine satellite damage assessment
  ◻ Multi-city coordination across state boundaries
  ◻ Government emergency management system integration
  ◻ National disaster response command platform
```

---

## 🏆 FAR AWAY 2026

Built for the **FAR AWAY International Hackathon 2026** by Zuup / Zylon Labs.

- **Theme:** Agentic & Autonomous Systems
- **Round 1:** Online MVP submission — June 14, 2026
- **Round 2:** 24-hour offline hackathon — New Delhi
- **Round 3:** Grand Finale — Tokyo, Japan (top 5 teams, fully sponsored)

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

**CrisisOS** — Built with the belief that better decisions save lives.

*"Somewhere, a decision was made. And because of it, she is breathing."*

<br/>

[![Live Demo](https://img.shields.io/badge/🌐_Try_CrisisOS-Live_Demo-00D4FF?style=for-the-badge)](https://crisisos.netlify.app)

</div>
