import sys, os
sys.path.insert(0, os.path.dirname(__file__))
try:
    from simulation.city import SimulationState
    from simulation.victims import VictimManager
    from simulation.disaster import DisasterEngine
    from simulation.vehicles import VehicleManager
    from agents.base_agent import BaseAgent, Proposal, Decision
    from agents.commander import CommanderAgent
    from agents.intelligence import IntelligenceAgent
    from agents.logistics import LogisticsAgent
    from agents.medical import MedicalAgent
    from agents.prediction import PredictionAgent
    from engine.decision_ledger import DecisionLedger
    from engine.conflict_engine import ConflictEngine
    from engine.gemini_explainer import GeminiExplainer
    from engine.utility_scorer import score_proposal
    print("ALL IMPORTS OK")
    s = SimulationState()
    s.initialize()
    print(f"State initialized: {len(s.vehicles)} vehicles, {len(s.hospitals)} hospitals")
    print(f"Victim count: {len(s.victims)}")
    print("READY TO RUN")
except Exception as e:
    print(f"IMPORT ERROR: {e}")
    import traceback
    traceback.print_exc()
