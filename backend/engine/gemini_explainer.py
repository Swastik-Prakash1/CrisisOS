"""
CrisisOS — Gemini Explainer
Async, non-blocking explanations for decisions and after-action reports.
If Gemini is slow or unavailable, the system keeps running perfectly.
Explanations degrade gracefully to template strings.
"""

import asyncio
from typing import Optional

from agents.base_agent import Decision
from config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_MAX_TOKENS, GEMINI_TIMEOUT_SECONDS, WS_EVENTS


class GeminiExplainer:
    """
    ONLY touches two things:
    1. Reasoning panel explanations (async, non-blocking)
    2. After-action report narrative generation

    If Gemini is slow or unavailable, the system keeps running perfectly.
    """

    def __init__(self, state=None):
        self._model = None
        self._available = False
        self._state = state
        self._init_gemini()

    def _init_gemini(self):
        """Initialize Gemini client. Fails silently if unavailable."""
        if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
            print("  ⚠ Gemini API key not configured — using template explanations")
            return

        try:
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            self._model = genai.GenerativeModel(GEMINI_MODEL)
            self._available = True
            print("  ✅ Gemini explainer initialized")
        except Exception as e:
            print(f"  ⚠ Gemini initialization failed: {e}")

    async def explain_decision(self, decision: Decision, state_snapshot: dict) -> str:
        """
        Generate a 2-3 sentence plain English explanation for the reasoning panel.
        ASYNC and NON-BLOCKING — simulation continues regardless.
        """
        if not self._available or not self._model:
            return self._get_fallback_explanation(decision)

        prompt = (
            "You are CrisisOS, an emergency response AI. Explain this decision "
            "in 2 sentences as if briefing an emergency commander. Be specific "
            "about the tradeoff. Use the numbers from the context.\n\n"
            f"Decision: {decision.action}\n"
            f"Alternative rejected: {decision.alternative_considered}\n"
            f"Rejected because: {decision.alternative_rejected_because}\n"
            f"Confidence: {decision.confidence:.0%}\n"
            f"Scenario type: {decision.scenario_type}\n"
            f"Key context: {state_snapshot}\n\n"
            "Response format: 2 sentences maximum. No preamble. Direct. "
            "Use specific numbers and victim IDs when available."
        )

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self._model.generate_content,
                    prompt,
                    generation_config={"max_output_tokens": GEMINI_MAX_TOKENS},
                ),
                timeout=GEMINI_TIMEOUT_SECONDS,
            )
            explanation = response.text.strip()

            # Broadcast the explanation
            if self._state:
                await self._state.emit_event(
                    WS_EVENTS["DECISION_EXPLANATION_READY"],
                    {
                        "decision_id": decision.id,
                        "explanation": explanation,
                    },
                )

            return explanation

        except asyncio.TimeoutError:
            print(f"  ⚠ Gemini timeout for decision {decision.id}")
            return self._get_fallback_explanation(decision)
        except Exception as e:
            print(f"  ⚠ Gemini error: {e}")
            return self._get_fallback_explanation(decision)

    async def generate_after_action_report(self, ledger_export: dict, final_metrics: dict) -> str:
        """
        Generate a comprehensive after-action report narrative.
        This is the one place Gemini can be creative and verbose.
        """
        if not self._available or not self._model:
            return self._get_fallback_report(ledger_export, final_metrics)

        # Keep the prompt compact
        critical = ledger_export.get("critical_decisions", [])[:5]
        stats = ledger_export.get("statistics", {})

        prompt = (
            "You are CrisisOS generating an After-Action Report for a disaster response simulation. "
            "Write a professional crisis management report with these sections:\n\n"
            "1. EXECUTIVE SUMMARY (2-3 sentences)\n"
            "2. KEY DECISIONS ANALYSIS (analyze the critical decisions)\n"
            "3. SYSTEM PERFORMANCE (evaluate AI vs baseline)\n"
            "4. RECOMMENDATIONS (3-4 actionable items)\n\n"
            f"Simulation metrics:\n{final_metrics}\n\n"
            f"Decision statistics:\n{stats}\n\n"
            f"Critical decisions (up to 5):\n"
        )

        for d in critical:
            prompt += (
                f"\n- Tick {d.get('tick')}: {d.get('action')} "
                f"(rejected: {d.get('alternative_considered')}, "
                f"reason: {d.get('alternative_rejected_because')})"
            )

        prompt += (
            "\n\nWrite professionally. Use specific numbers. "
            "Acknowledge both successes and failures honestly. "
            "Format with clear section headers."
        )

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self._model.generate_content,
                    prompt,
                    generation_config={"max_output_tokens": 1000},
                ),
                timeout=15,
            )
            return response.text.strip()
        except Exception as e:
            print(f"  ⚠ Gemini report generation failed: {e}")
            return self._get_fallback_report(ledger_export, final_metrics)

    def _get_fallback_explanation(self, decision: Decision) -> str:
        """Template-based fallback if Gemini is unavailable."""
        if decision.scenario_type == "road_sacrifice":
            return (
                f"{decision.agent_winner} prioritized corridor preservation over immediate rescue "
                f"(confidence: {decision.confidence:.0%}). "
                f"Alternative '{decision.alternative_considered}' rejected: "
                f"{decision.alternative_rejected_because}"
            )
        elif decision.scenario_type == "resource_exhaustion":
            return (
                f"Resource exhaustion forced {decision.agent_winner} to select {decision.target} "
                f"(confidence: {decision.confidence:.0%}). "
                f"Insufficient resources to cover all sectors simultaneously — "
                f"{decision.alternative_rejected_because}"
            )
        else:
            return (
                f"{decision.agent_winner} prioritized {decision.target} "
                f"(confidence: {decision.confidence:.0%}). "
                f"Alternative '{decision.alternative_considered}' rejected: "
                f"{decision.alternative_rejected_because}"
            )

    def _get_fallback_report(self, ledger_export: dict, final_metrics: dict) -> str:
        """Template-based fallback report."""
        stats = ledger_export.get("statistics", {})
        metrics = final_metrics

        report = (
            "═══ CRISISOS AFTER-ACTION REPORT ═══\n\n"
            "EXECUTIVE SUMMARY\n"
            f"CrisisOS processed {stats.get('total', 0)} decisions across "
            f"{stats.get('critical', 0)} critical conflict scenarios. "
            f"AI-assisted response rescued {metrics.get('victims_rescued', 0)} victims "
            f"with {metrics.get('victims_deceased', 0)} casualties.\n\n"
            "KEY DECISIONS\n"
        )

        best = ledger_export.get("best_decision")
        worst = ledger_export.get("worst_decision")

        if best:
            report += (
                f"Most impactful: Tick {best.get('tick', '?')} — {best.get('action', '?')} "
                f"(Confidence: {best.get('confidence', 0):.0%})\n"
            )
        if worst:
            report += (
                f"Most difficult: Tick {worst.get('tick', '?')} — {worst.get('action', '?')} "
                f"(Confidence: {worst.get('confidence', 0):.0%})\n"
            )

        report += (
            f"\nSYSTEM PERFORMANCE\n"
            f"Average decision confidence: {stats.get('avg_confidence', 0):.0%}\n"
            f"Conflict resolution rate: {stats.get('critical', 0)} scenarios resolved\n"
            f"Decision accuracy: {stats.get('outcome_accuracy', 0):.0%}\n\n"
            "RECOMMENDATIONS\n"
            "1. Increase ambulance fleet to cover resource exhaustion scenarios\n"
            "2. Pre-position vehicles near predicted hotspots\n"
            "3. Implement automatic hospital diversion protocols\n"
            "4. Expand prediction horizon beyond 2-minute window\n"
        )

        return report

    @property
    def is_available(self) -> bool:
        return self._available
