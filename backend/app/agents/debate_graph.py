"""
Person 2: LangGraph orchestration of the two-round debate.

Flow: PRO opening -> CON opening -> PRO rebuttal -> CON rebuttal
Main entry point: run_debate(claim, evidence)

Test (from the backend/ folder):
    python -m app.agents.debate_graph
"""

import json
import operator
from pathlib import Path
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.debate_agents import opening, rebuttal, split_evidence
from app.core.schemas import DebateTurn, EvidenceSnippet


class DebateState(TypedDict):
    claim: str
    pro_evidence: list[EvidenceSnippet]
    con_evidence: list[EvidenceSnippet]
    transcript: Annotated[list[DebateTurn], operator.add]
    citation_log: Annotated[list[dict], operator.add]


def _find_turn(state: DebateState, agent: str, rnd: int) -> DebateTurn:
    return next(t for t in state["transcript"] if t.agent == agent and t.round == rnd)


def _evidence_by_id(state: DebateState) -> dict[str, EvidenceSnippet]:
    return {s.id: s for s in state["pro_evidence"] + state["con_evidence"]}


def pro_opening(state: DebateState):
    turn, log = opening("PRO", state["claim"], state["pro_evidence"])
    return {"transcript": [turn], "citation_log": [log]}


def con_opening(state: DebateState):
    turn, log = opening("CON", state["claim"], state["con_evidence"])
    return {"transcript": [turn], "citation_log": [log]}


def pro_rebuttal(state: DebateState):
    turn, log = rebuttal("PRO", state["claim"], state["pro_evidence"],
                         _find_turn(state, "CON", 1), _evidence_by_id(state))
    return {"transcript": [turn], "citation_log": [log]}


def con_rebuttal(state: DebateState):
    turn, log = rebuttal("CON", state["claim"], state["con_evidence"],
                         _find_turn(state, "PRO", 1), _evidence_by_id(state))
    return {"transcript": [turn], "citation_log": [log]}


def build_graph():
    g = StateGraph(DebateState)
    g.add_node("pro_opening", pro_opening)
    g.add_node("con_opening", con_opening)
    g.add_node("pro_rebuttal", pro_rebuttal)
    g.add_node("con_rebuttal", con_rebuttal)
    g.add_edge(START, "pro_opening")
    g.add_edge("pro_opening", "con_opening")
    g.add_edge("con_opening", "pro_rebuttal")
    g.add_edge("pro_rebuttal", "con_rebuttal")
    g.add_edge("con_rebuttal", END)
    return g.compile()


_graph = build_graph()


def run_debate(claim: str, evidence: list[EvidenceSnippet]) -> dict:
    """Returns {"claim", "transcript": list[DebateTurn], "citation_log": list[dict]}."""
    pro, con = split_evidence(evidence)
    result = _graph.invoke({
        "claim": claim,
        "pro_evidence": pro,
        "con_evidence": con,
        "transcript": [],
        "citation_log": [],
    })
    return {
        "claim": claim,
        "transcript": result["transcript"],
        "citation_log": result["citation_log"],
    }


if __name__ == "__main__":
    tests_dir = Path(__file__).resolve().parents[2] / "tests"
    claim = "vitamin D supplements prevent respiratory infections"
    evidence = [EvidenceSnippet(**d) for d in
                json.loads((tests_dir / "fixture_vitd.json").read_text())]

    out = run_debate(claim, evidence)

    for t in out["transcript"]:
        print(f"\n=== {t.agent} | round {t.round} ===\n{t.argument}")
    print("\n=== Citation log ===")
    for log in out["citation_log"]:
        print(log)

    # Save for Person 3 (judge) to use as a real test input
    save_path = tests_dir / "fixture_vitd_debate.json"
    save_path.write_text(json.dumps({
        "claim": claim,
        "transcript": [t.model_dump() for t in out["transcript"]],
        "citation_log": out["citation_log"],
    }, indent=2))
    print(f"\nSaved debate to {save_path}")
