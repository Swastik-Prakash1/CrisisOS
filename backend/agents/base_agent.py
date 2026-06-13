"""
CrisisOS — Base Agent Class
Abstract base for all 5 autonomous agents.
Defines the perceive → propose → update_memory lifecycle.
"""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Proposal:
    """A proposed action from an agent to the Commander for arbitration."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent_name: str = ""
    action: str = ""              # Human-readable action description
    target: str = ""              # What/who this action targets
    priority_score: float = 0.0   # 0.0-1.0, higher = more urgent
    utility_score: float = 0.0    # Expected value calculation
    confidence: float = 0.5       # 0.0-1.0
    reasoning: str = ""           # 1-2 sentence justification
    conflicts_with: list = field(default_factory=list)  # IDs of conflicting proposals
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "agent_name": self.agent_name,
            "action": self.action,
            "target": self.target,
            "priority_score": round(self.priority_score, 3),
            "utility_score": round(self.utility_score, 3),
            "confidence": round(self.confidence, 3),
            "reasoning": self.reasoning,
            "conflicts_with": self.conflicts_with,
            "metadata": self.metadata,
        }


@dataclass
class Decision:
    """A finalized decision by the Commander, logged to the Decision Ledger."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    timestamp: str = ""
    tick: int = 0
    agent_winner: str = ""
    action: str = ""
    target: str = ""
    confidence: float = 0.5
    utility_score: float = 0.0

    alternative_considered: str = ""
    alternative_agent: str = ""
    alternative_rejected_because: str = ""

    gemini_explanation: str = ""  # Filled async by Gemini — can be "" initially

    predicted_outcome: str = ""
    actual_outcome: Optional[str] = None

    was_human_override: bool = False
    human_override_warning: Optional[str] = None

    scenario_type: str = "routine"  # road_sacrifice | resource_exhaustion | cascade_prevention | human_bad_command | routine

    # Keep the original proposals for Judge Replay
    proposals: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "tick": self.tick,
            "agent_winner": self.agent_winner,
            "action": self.action,
            "target": self.target,
            "confidence": round(self.confidence, 3),
            "utility_score": round(self.utility_score, 3),
            "alternative_considered": self.alternative_considered,
            "alternative_agent": self.alternative_agent,
            "alternative_rejected_because": self.alternative_rejected_because,
            "gemini_explanation": self.gemini_explanation,
            "predicted_outcome": self.predicted_outcome,
            "actual_outcome": self.actual_outcome,
            "was_human_override": self.was_human_override,
            "human_override_warning": self.human_override_warning,
            "scenario_type": self.scenario_type,
            "proposals": [p.to_dict() if hasattr(p, 'to_dict') else p for p in self.proposals],
        }


@dataclass
class Conflict:
    """Detected conflict between two or more agent proposals."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: str = ""       # "resource_contention" | "priority_disagreement" | "route_conflict"
    agents_involved: list = field(default_factory=list)
    proposals: list = field(default_factory=list)  # The conflicting proposals
    resource: str = ""   # What resource is contested
    description: str = ""
    scenario_type: str = "routine"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "agents_involved": self.agents_involved,
            "proposals": [p.to_dict() if hasattr(p, 'to_dict') else p for p in self.proposals],
            "resource": self.resource,
            "description": self.description,
            "scenario_type": self.scenario_type,
        }


class BaseAgent(ABC):
    """
    Abstract base class for all CrisisOS agents.

    Lifecycle per decision cycle:
    1. perceive() — extract relevant state slice
    2. propose() — generate proposed actions with scores
    3. update_memory() — learn from decision outcomes

    Each agent has a confidence_modifier that adjusts based on past accuracy.
    """

    def __init__(self, name: str, state):
        self.name = name
        self.state = state
        self.decision_history: list[dict] = []
        self.confidence_modifier: float = 1.0  # Range: 0.7 - 1.3

    @abstractmethod
    def perceive(self) -> dict:
        """
        Extract the relevant slice of simulation state for this agent.
        Each agent only looks at what it cares about.
        """
        raise NotImplementedError

    @abstractmethod
    def propose(self) -> list[Proposal]:
        """
        Generate a list of proposed actions with priority and utility scores.
        These go to the Commander for arbitration.
        """
        raise NotImplementedError

    def update_memory(self, decision: Decision, outcome: str):
        """
        Update confidence modifier based on past decision outcomes.
        If previous similar decision was correct: confidence_modifier *= 1.05
        If previous similar decision was wrong: confidence_modifier *= 0.92
        This is the 'learning' behavior visible to judges.
        """
        was_positive = "positive" in outcome.lower() or "correct" in outcome.lower() or "saved" in outcome.lower()

        if was_positive:
            self.confidence_modifier = min(1.3, self.confidence_modifier * 1.05)
        else:
            self.confidence_modifier = max(0.7, self.confidence_modifier * 0.92)

        self.decision_history.append({
            "decision_id": decision.id,
            "outcome": outcome,
            "tick": self.state.tick,
            "confidence_modifier": round(self.confidence_modifier, 4),
        })

        # Keep history bounded
        if len(self.decision_history) > 50:
            self.decision_history = self.decision_history[-50:]

    def get_adjusted_confidence(self, base_confidence: float) -> float:
        """Apply confidence modifier to a base confidence score."""
        return min(1.0, max(0.0, base_confidence * self.confidence_modifier))

    def get_memory_summary(self) -> dict:
        """Summary of agent's learning state for UI display."""
        return {
            "agent": self.name,
            "confidence_modifier": round(self.confidence_modifier, 4),
            "decisions_participated": len(self.decision_history),
            "recent_trend": self._get_trend(),
        }

    def _get_trend(self) -> str:
        """Calculate recent performance trend."""
        if len(self.decision_history) < 3:
            return "insufficient_data"
        recent = self.decision_history[-5:]
        positive = sum(1 for d in recent if "positive" in d.get("outcome", "").lower())
        if positive >= 4:
            return "improving"
        elif positive <= 1:
            return "declining"
        return "stable"
