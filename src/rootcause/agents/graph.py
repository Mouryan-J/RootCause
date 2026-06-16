"""
LangGraph multi-agent graph — star topology.

Coordinator routes to workers; workers never communicate directly.

Flow:
  START → coordinator → triage → coordinator
                      → retrieval → coordinator
                      → rca → coordinator
                      → remediation → coordinator → END
"""
from __future__ import annotations

import uuid
from typing import Any

from langgraph.graph import END, StateGraph  # type: ignore[import]

from rootcause.agents.rca import rca_node
from rootcause.agents.remediation import remediation_node
from rootcause.agents.retrieval import retrieval_node
from rootcause.agents.state import IncidentState
from rootcause.agents.triage import triage_node
from rootcause.core.logging import get_logger
from rootcause.core.telemetry import get_langfuse_callback

log = get_logger(__name__)

_PIPELINE = ["triage", "retrieval", "rca", "remediation"]


def coordinator_node(state: IncidentState) -> dict:
    """Decide which worker to invoke next, or signal completion."""
    completed = set(state.get("completed_steps") or [])
    for step in _PIPELINE:
        if step not in completed:
            return {"next_worker": step}
    return {"next_worker": "done"}


def _route(state: IncidentState) -> str:
    return state.get("next_worker", "done")


def _build_graph() -> Any:
    g = StateGraph(IncidentState)

    g.add_node("coordinator", coordinator_node)
    g.add_node("triage", triage_node)
    g.add_node("retrieval", retrieval_node)
    g.add_node("rca", rca_node)
    g.add_node("remediation", remediation_node)

    g.set_entry_point("coordinator")
    g.add_conditional_edges(
        "coordinator",
        _route,
        {
            "triage": "triage",
            "retrieval": "retrieval",
            "rca": "rca",
            "remediation": "remediation",
            "done": END,
        },
    )
    for worker in _PIPELINE:
        g.add_edge(worker, "coordinator")

    return g.compile()


_graph = _build_graph()


async def run_analysis(
    incident_id: uuid.UUID,
    title: str,
    description: str,
    service: str,
    severity: str,
    logs: str | None = None,
    metrics: dict | None = None,
) -> IncidentState:
    """Run the full analysis pipeline and return the final state."""
    initial: IncidentState = {
        "incident_id": str(incident_id),
        "title": title,
        "description": description,
        "service": service,
        "severity": severity,
        "logs": logs,
        "metrics": metrics,
        "next_worker": "",
        "completed_steps": [],
        "incident_category": "",
        "key_signals": [],
        "search_query": "",
        "retrieved_docs": [],
        "root_causes": [],
        "contributing_factors": [],
        "remediation_steps": [],
        "summary": "",
        "runbooks_referenced": [],
        "model_used": "",
        "error": None,
    }

    callbacks = []
    cb = get_langfuse_callback(session_id=str(incident_id))
    if cb:
        callbacks.append(cb)

    log.info("analysis_started", incident_id=str(incident_id), service=service)
    invoke_config = {"callbacks": callbacks} if callbacks else {}
    final: IncidentState = await _graph.ainvoke(initial, config=invoke_config)
    log.info(
        "analysis_complete",
        incident_id=str(incident_id),
        root_causes=len(final.get("root_causes") or []),
        steps=len(final.get("remediation_steps") or []),
    )
    return final
