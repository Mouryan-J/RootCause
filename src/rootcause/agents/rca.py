"""
RCA worker node.

Uses claude-haiku-4-5-20251001 to synthesize 1-3 root causes from the
incident details and retrieved runbooks/postmortems.
Falls back to a heuristic summary when the API key is absent.
"""
from __future__ import annotations

import json
import logging

from pydantic import BaseModel, Field, model_validator

from rootcause.agents.state import IncidentState
from rootcause.core.config import get_settings

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an expert site reliability engineer performing root cause analysis.

You will be given:
1. An incident description with symptoms, logs, and metrics
2. A set of retrieved runbooks and postmortems that may be relevant

Your task:
- Identify 1-3 most likely root causes, ordered by confidence
- For each root cause provide: a clear description, a confidence score (0.0-1.0), \
and 2-4 pieces of evidence drawn from the incident details or retrieved documents
- List up to 5 contributing factors (conditions that made the incident worse but \
were not the primary cause)

Be specific and cite exact error messages, metrics, or runbook IDs as evidence."""


class RootCauseItem(BaseModel):
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str]


class RCAOutput(BaseModel):
    root_causes: list[RootCauseItem]
    contributing_factors: list[str]

    @model_validator(mode="before")
    @classmethod
    def parse_string_fields(cls, values: dict) -> dict:
        for field in ("root_causes", "contributing_factors"):
            if isinstance(values.get(field), str):
                values[field] = json.loads(values[field])
        return values


def _format_docs(docs: list[dict]) -> str:
    if not docs:
        return "No runbooks retrieved."
    lines = []
    for i, d in enumerate(docs, 1):
        lines.append(f"[{i}] {d['doc_id']} — {d['title']} (source: {d['source']})")
        lines.append(d["excerpt"][:800])
        lines.append("")
    return "\n".join(lines)


def _fallback_rca(state: IncidentState) -> dict:
    docs = state.get("retrieved_docs") or []
    runbooks = [d["doc_id"] for d in docs if d.get("source") == "runbook"]
    completed = list(state.get("completed_steps") or []) + ["rca"]
    return {
        "root_causes": [
            {
                "description": f"Potential issue in {state.get('service', 'unknown service')}: {state.get('description', '')[:200]}",
                "confidence": 0.5,
                "evidence": state.get("key_signals") or [],
            }
        ],
        "contributing_factors": [],
        "runbooks_referenced": runbooks,
        "model_used": "fallback",
        "completed_steps": completed,
    }


def rca_node(state: IncidentState) -> dict:
    settings = get_settings()
    if not settings.anthropic_api_key:
        log.warning("anthropic_api_key not set, using fallback RCA")
        return _fallback_rca(state)

    try:
        from langchain_anthropic import ChatAnthropic  # type: ignore[import]

        llm = ChatAnthropic(
            model=settings.model_rca,
            api_key=settings.anthropic_api_key,
            temperature=0,
            max_tokens=1024,
        ).with_structured_output(RCAOutput)

        docs = state.get("retrieved_docs") or []
        incident_text = (
            f"## Incident\n"
            f"Title: {state.get('title')}\n"
            f"Service: {state.get('service')}\n"
            f"Severity: {state.get('severity')}\n"
            f"Category: {state.get('incident_category', 'unknown')}\n"
            f"Description: {state.get('description')}\n"
        )
        if state.get("key_signals"):
            incident_text += f"Key signals: {', '.join(state['key_signals'])}\n"
        if state.get("logs"):
            incident_text += f"\nLogs:\n{state['logs'][:2000]}\n"
        if state.get("metrics"):
            incident_text += f"\nMetrics: {state['metrics']}\n"

        incident_text += f"\n## Retrieved Documents\n{_format_docs(docs)}"

        result: RCAOutput = llm.invoke([
            {"role": "user", "content": f"{SYSTEM_PROMPT}\n\n{incident_text}"},
        ])

        runbooks_referenced = [
            d["doc_id"] for d in docs if d.get("source") == "runbook"
        ]
        completed = list(state.get("completed_steps") or []) + ["rca"]
        log.info("RCA complete: %d root causes identified", len(result.root_causes))

        return {
            "root_causes": [rc.model_dump() for rc in result.root_causes],
            "contributing_factors": result.contributing_factors,
            "runbooks_referenced": runbooks_referenced,
            "model_used": settings.model_rca,
            "completed_steps": completed,
        }

    except Exception as exc:
        log.warning("RCA LLM failed, using fallback: %s", exc)
        result = _fallback_rca(state)
        result["error"] = str(exc)
        return result
