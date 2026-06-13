"""
CrisisOS — Utility Scorer
Pure utility function scoring for Commander arbitration.
This is separated for testability and clarity.
"""

from simulation.city import SimulationState
from config import VICTIM_SEVERITY_WEIGHTS


def score_proposal(proposal_meta: dict, state: SimulationState) -> float:
    """
    Composite utility function.

    Score = (severity_weight * time_urgency * reachability_factor *
             cascade_prevention_bonus * hospital_capacity_factor)

    All components are in [0, 1] range (except cascade bonus is additive).
    """
    # Extract metadata
    victim_severity = proposal_meta.get("victim_severity", 3)
    victim_ttd = proposal_meta.get("victim_ttd", 600)
    route_risk = proposal_meta.get("route_risk", 0.0)
    hospital_id = proposal_meta.get("hospital_id")
    accessible_victims = proposal_meta.get("accessible_victims", 0)
    proposal_type = proposal_meta.get("type", "dispatch")
    eta_seconds = proposal_meta.get("eta_seconds", 0)

    # 1. Severity weight
    severity_weight = VICTIM_SEVERITY_WEIGHTS.get(victim_severity, 0.5)

    # 2. Time urgency: higher when closer to death
    if victim_ttd > 0:
        time_urgency = max(0.1, min(1.0, 1.0 - (victim_ttd / 1200)))
    else:
        time_urgency = 1.0

    # 3. Reachability factor
    reachability = max(0.0, 1.0 - route_risk)

    # 4. Cascade prevention bonus
    cascade_bonus = 0.0
    if proposal_type == "route_hold" and accessible_victims > 5:
        cascade_bonus = 0.3
    elif accessible_victims > 10:
        cascade_bonus = 0.2

    # 5. Hospital capacity factor
    hospital_factor = 1.0
    if hospital_id:
        hospital = state.get_hospital(hospital_id)
        if hospital:
            pct = hospital.capacity_percent
            if pct >= 95:
                hospital_factor = 0.3
            elif pct >= 85:
                hospital_factor = 0.6
            elif pct >= 70:
                hospital_factor = 0.85

    # 6. ETA feasibility factor
    eta_factor = 1.0
    if eta_seconds > 0 and victim_ttd > 0:
        margin = victim_ttd - eta_seconds
        if margin < 0:
            eta_factor = 0.1  # Can't reach in time
        elif margin < 60:
            eta_factor = 0.5  # Very tight
        elif margin < 120:
            eta_factor = 0.8  # Tight but feasible

    # Composite score
    score = (
        severity_weight * 0.25 +
        time_urgency * 0.25 +
        reachability * 0.15 +
        eta_factor * 0.15 +
        hospital_factor * 0.1 +
        cascade_bonus +
        0.1  # Base score
    )

    return min(1.0, max(0.0, score))


def score_20_minute_window(
    option_a_victims: int,
    option_a_avg_severity: float,
    option_b_victims: int,
    option_b_avg_severity: float,
) -> tuple[float, float, float]:
    """
    Compare two options over a 20-minute expected value window.
    Used for Road Sacrifice scenario resolution.

    Returns:
        (option_a_score, option_b_score, ratio)
    """
    # Expected lives saved = victims * probability_of_save * severity_weight
    a_score = option_a_victims * (option_a_avg_severity / 5.0) * 0.7
    b_score = option_b_victims * (option_b_avg_severity / 5.0) * 0.6

    ratio = b_score / a_score if a_score > 0 else float('inf')

    return round(a_score, 2), round(b_score, 2), round(ratio, 2)
