"""
CrisisOS — Decision Ledger
Append-only log of all decisions.
The audit trail, source of After-Action Reports, and Judge Replay data.
"""

import time
from typing import Optional

from agents.base_agent import Decision
from config import WS_EVENTS


class DecisionLedger:
    """
    Immutable audit log of every decision made by the Commander.
    Supports:
    - Appending decisions (with immediate WebSocket broadcast)
    - Updating outcomes when observed
    - Filtering for critical decisions (for Judge Replay)
    - Exporting for After-Action Report generation
    """

    def __init__(self):
        self.decisions: list[Decision] = []
        self._state = None  # Reference to SimulationState for event emission

    def set_state(self, state):
        """Set reference to SimulationState for event emission."""
        self._state = state

    async def log(self, decision: Decision):
        """
        Append decision to the ledger.
        Broadcasts to WebSocket immediately.
        """
        self.decisions.append(decision)

        # Broadcast decision event
        if self._state:
            await self._state.emit_event(
                WS_EVENTS["DECISION_MADE"],
                {"decision": decision.to_dict()},
            )

        # Console log for critical decisions
        if decision.scenario_type != "routine":
            print(f"\n  ⚖ DECISION [{decision.scenario_type.upper()}] Tick {decision.tick}")
            print(f"    Winner: [{decision.agent_winner}] {decision.action}")
            if decision.alternative_considered and decision.alternative_agent:
                print(f"    Rejected: [{decision.alternative_agent}] {decision.alternative_considered}")
                print(f"    Reason: {decision.alternative_rejected_because}")
            print(f"    Confidence: {decision.confidence:.0%} | Utility: {decision.utility_score:.3f}")
            print(f"    Predicted: {decision.predicted_outcome}")

    async def update_outcome(
        self,
        decision_id: str,
        outcome: str,
        actual_casualties_delta: int = 0,
    ):
        """
        Called when we can measure what actually happened.
        Fills decision.actual_outcome field.
        Returns the decision for feedback to agent confidence modifiers.
        """
        for decision in self.decisions:
            if decision.id == decision_id:
                decision.actual_outcome = outcome

                # Determine if outcome was positive
                if actual_casualties_delta <= 0:
                    outcome_quality = "positive"
                else:
                    outcome_quality = "negative"

                return decision, outcome_quality

        return None, None

    def get_critical_decisions(self) -> list[Decision]:
        """Returns decisions where scenario_type != 'routine'."""
        return [d for d in self.decisions if d.scenario_type != "routine"]

    def get_worst_decision(self) -> Optional[Decision]:
        """Decision where actual_outcome was worse than predicted_outcome."""
        candidates = [
            d for d in self.decisions
            if d.actual_outcome and "negative" in (d.actual_outcome or "").lower()
        ]
        if not candidates:
            # Fallback: lowest confidence critical decision
            critical = self.get_critical_decisions()
            if critical:
                return min(critical, key=lambda d: d.confidence)
            return None
        return candidates[0]

    def get_best_decision(self) -> Optional[Decision]:
        """Decision with highest utility that had a positive outcome."""
        candidates = [
            d for d in self.decisions
            if d.scenario_type != "routine"
        ]
        if candidates:
            return max(candidates, key=lambda d: d.utility_score)
        return None

    def get_decisions_by_agent(self, agent_name: str) -> list[Decision]:
        """Get all decisions won by a specific agent."""
        return [d for d in self.decisions if d.agent_winner == agent_name]

    def get_decisions_by_scenario(self, scenario_type: str) -> list[Decision]:
        """Get all decisions of a specific scenario type."""
        return [d for d in self.decisions if d.scenario_type == scenario_type]

    def get_statistics(self) -> dict:
        """Compute ledger statistics for reports."""
        total = len(self.decisions)
        if total == 0:
            return {"total": 0}

        critical = self.get_critical_decisions()
        by_agent = {}
        for d in self.decisions:
            if d.agent_winner not in by_agent:
                by_agent[d.agent_winner] = 0
            by_agent[d.agent_winner] += 1

        confidences = [d.confidence for d in self.decisions]
        utilities = [d.utility_score for d in self.decisions]

        outcomes_known = [d for d in self.decisions if d.actual_outcome]
        positive = sum(1 for d in outcomes_known if "positive" in (d.actual_outcome or "").lower())
        accuracy = positive / len(outcomes_known) if outcomes_known else 0

        return {
            "total": total,
            "critical": len(critical),
            "by_agent": by_agent,
            "avg_confidence": sum(confidences) / total,
            "avg_utility": sum(utilities) / total,
            "max_confidence": max(confidences),
            "min_confidence": min(confidences),
            "outcomes_known": len(outcomes_known),
            "outcome_accuracy": accuracy,
            "scenario_counts": {
                "road_sacrifice": len(self.get_decisions_by_scenario("road_sacrifice")),
                "resource_exhaustion": len(self.get_decisions_by_scenario("resource_exhaustion")),
                "cascade_prevention": len(self.get_decisions_by_scenario("cascade_prevention")),
                "human_bad_command": len(self.get_decisions_by_scenario("human_bad_command")),
                "routine": len(self.get_decisions_by_scenario("routine")),
            },
        }

    def export_for_report(self) -> dict:
        """Full ledger as structured dict for Gemini to summarize."""
        return {
            "decisions": [d.to_dict() for d in self.decisions],
            "statistics": self.get_statistics(),
            "critical_decisions": [d.to_dict() for d in self.get_critical_decisions()],
            "best_decision": self.get_best_decision().to_dict() if self.get_best_decision() else None,
            "worst_decision": self.get_worst_decision().to_dict() if self.get_worst_decision() else None,
        }

    def to_dict(self) -> list[dict]:
        """Serialize full ledger."""
        return [d.to_dict() for d in self.decisions]
