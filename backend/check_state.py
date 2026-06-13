"""Quick state checker for CrisisOS simulation."""
import json
import urllib.request

def check_state():
    url = "http://localhost:8000/state"
    try:
        resp = urllib.request.urlopen(url, timeout=5)
        data = json.loads(resp.read().decode())
    except Exception as e:
        print(f"ERROR: {e}")
        return

    sim = data.get("simulation", {})
    metrics = data.get("metrics", {})
    victims = data.get("victims", [])
    vehicles = data.get("vehicles", [])

    print(f"\n=== CrisisOS State Check ===")
    print(f"Tick: {sim.get('tick', '?')} | Running: {sim.get('running')} | Phase: {sim.get('phase')}")
    print(f"\n--- Metrics ---")
    print(f"  Victims total:    {metrics.get('victims_total', 0)}")
    print(f"  Rescued:          {metrics.get('victims_rescued', 0)}")
    print(f"  Deceased:         {metrics.get('victims_deceased', 0)}")
    print(f"  Critical active:  {metrics.get('victims_critical_active', 0)}")
    print(f"  Decisions made:   {metrics.get('decisions_made', 0)}")
    print(f"  Conflicts resolved: {metrics.get('conflicts_resolved', 0)}")
    
    # Victim status breakdown
    statuses = {}
    for v in victims:
        s = v.get("status", "unknown")
        statuses[s] = statuses.get(s, 0) + 1
    print(f"\n--- Victim Status Breakdown ---")
    for s, count in sorted(statuses.items()):
        print(f"  {s}: {count}")
    
    # Vehicle status
    print(f"\n--- Vehicle Status ---")
    for v in vehicles:
        victim = v.get("assigned_victim", "")
        route_len = len(v.get("assigned_route", []))
        print(f"  {v['id']} ({v['type']}): {v['status']}"
              f"{f' -> {victim}' if victim else ''}"
              f"{f' [{route_len} wp]' if route_len else ''}"
              f" ETA:{v.get('eta_seconds', 0):.0f}s")

    # Decisions
    try:
        resp2 = urllib.request.urlopen("http://localhost:8000/decisions", timeout=5)
        ddata = json.loads(resp2.read().decode())
        decisions = ddata.get("decisions", [])
        stats = ddata.get("statistics", {})
        print(f"\n--- Decision Stats ---")
        print(f"  Total decisions: {stats.get('total', 0)}")
        print(f"  Avg confidence: {stats.get('avg_confidence', 0):.2%}")
        print(f"  Scenario counts: {stats.get('scenario_counts', {})}")
        
        # Show confidence values
        confidences = [d.get("confidence", 0) for d in decisions]
        if confidences:
            print(f"  Confidence range: {min(confidences):.2%} - {max(confidences):.2%}")
            print(f"  Last 5 confidences: {[f'{c:.2%}' for c in confidences[-5:]]}")
    except:
        pass

if __name__ == "__main__":
    check_state()
