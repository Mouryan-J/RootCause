"""
Triage worker node.

Uses gpt-4o-mini to classify the incident, extract key diagnostic signals,
and generate an optimized search query for the retrieval step.
Falls back to description-based defaults when the API key is absent.
"""
from __future__ import annotations

import logging

from pydantic import BaseModel

from rootcause.agents.state import IncidentState
from rootcause.core.config import get_settings

log = logging.getLogger(__name__)

CATEGORIES = (
    "database", "api", "kubernetes", "networking",
    "messaging", "deployment", "application", "cache", "security",
)

SYSTEM_PROMPT = f"""\
You are an incident triage specialist. Analyze the incident and return JSON with:
- incident_category: one of {CATEGORIES}
- key_signals: list of 3-5 most important diagnostic signals (exact error messages, \
affected services, anomalous metric values)
- search_query: 20-40 word query optimised for retrieving relevant runbooks and postmortems"""


class TriageOutput(BaseModel):
    incident_category: str
    key_signals: list[str]
    search_query: str


def _fallback(state: IncidentState, err: str) -> dict:
    completed = list(state.get("completed_steps") or []) + ["triage"]
    return {
        "incident_category": "uncategorized",
        "key_signals": [state.get("description", "")[:300]],
        "search_query": f"{state.get('title', '')} {state.get('description', '')} {state.get('service', '')}".strip()[:400],
        "completed_steps": completed,
        "error": err,
    }


def triage_node(state: IncidentState) -> dict:
    settings = get_settings()
    if not settings.openai_api_key:
        return _fallback(state, "openai_api_key not configured")

    try:
        from langchain_openai import ChatOpenAI  # type: ignore[import]

        llm = ChatOpenAI(
            model=settings.model_agents,
            api_key=settings.openai_api_key,
            temperature=0,
        ).with_structured_output(TriageOutput)

        incident_text = (
            f"Title: {state.get('title')}\n"
            f"Service: {state.get('service')}\n"
            f"Severity: {state.get('severity')}\n"
            f"Description: {state.get('description')}"
        )
        if state.get("logs"):
            incident_text += f"\n\nLogs (truncated):\n{state['logs'][:2000]}"
        if state.get("metrics"):
            incident_text += f"\n\nMetrics: {state['metrics']}"

        result: TriageOutput = llm.invoke([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": incident_text},
        ])

        completed = list(state.get("completed_steps") or []) + ["triage"]
        log.info("Triage complete: category=%s", result.incident_category)
        return {
            "incident_category": result.incident_category,
            "key_signals": result.key_signals,
            "search_query": result.search_query,
            "completed_steps": completed,
        }

    except Exception as exc:
        log.warning("Triage LLM failed, using fallback: %s", exc)
        return _fallback(state, str(exc))
