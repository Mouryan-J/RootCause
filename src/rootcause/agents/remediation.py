"""
Remediation worker node.

Uses gpt-4o-mini to generate prioritised remediation steps and a plain-English
incident summary, grounded in the root causes and retrieved runbooks.
Falls back to extracting steps directly from runbook excerpts when LLM unavailable.
"""
from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from rootcause.agents.state import IncidentState
from rootcause.core.config import get_settings

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an on-call engineer responding to a production incident.

Given the root cause analysis and relevant runbooks, produce:
- remediation_steps: ordered list of concrete actions (immediate first, \
then short-term, then long-term). Each step should be a single actionable sentence.
- summary: 2-3 sentence plain-English summary of what happened, why, and how to fix it.

Ground your steps in the runbook excerpts provided. Be specific — include \
exact commands or config changes where the runbooks supply them."""


class RemediationOutput(BaseModel):
    remediation_steps: list[str]
    summary: str


def _extract_steps_from_runbooks(docs: list[dict]) -> list[str]:
    steps: list[str] = []
    for doc in docs[:3]:
        if doc.get("source") != "runbook":
            continue
        for line in doc.get("excerpt", "").splitlines():
            line = line.strip()
            m = re.match(r"^\d+\.\s+(.+)", line)
            if m:
                steps.append(m.group(1))
    return steps[:10] if steps else ["Refer to the retrieved runbooks for remediation guidance."]


def _fallback(state: IncidentState) -> dict:
    docs = state.get("retrieved_docs") or []
    root_causes = state.get("root_causes") or []
    summary = (
        f"Incident in {state.get('service', 'unknown service')} "
        f"({state.get('severity', '')} severity). "
        + (f"Likely cause: {root_causes[0]['description']}" if root_causes else "")
    )
    completed = list(state.get("completed_steps") or []) + ["remediation"]
    return {
        "remediation_steps": _extract_steps_from_runbooks(docs),
        "summary": summary,
        "completed_steps": completed,
    }


def remediation_node(state: IncidentState) -> dict:
    settings = get_settings()
    if not settings.openai_api_key:
        log.warning("openai_api_key not set, using fallback remediation")
        return _fallback(state)

    try:
        from langchain_openai import ChatOpenAI  # type: ignore[import]

        llm = ChatOpenAI(
            model=settings.model_agents,
            api_key=settings.openai_api_key,
            temperature=0,
        ).with_structured_output(RemediationOutput)

        root_causes = state.get("root_causes") or []
        docs = state.get("retrieved_docs") or []

        rca_text = "\n".join(
            f"- {rc['description']} (confidence: {rc['confidence']:.0%})"
            for rc in root_causes
        ) or "Root cause undetermined."

        factors_text = "\n".join(
            f"- {f}" for f in (state.get("contributing_factors") or [])
        )

        docs_text = "\n\n".join(
            f"**{d['doc_id']}** — {d['title']}\n{d['excerpt'][:600]}"
            for d in docs[:4]
        ) or "No runbooks retrieved."

        prompt = (
            f"## Incident\n"
            f"Service: {state.get('service')}, Severity: {state.get('severity')}\n"
            f"Title: {state.get('title')}\n\n"
            f"## Root Causes\n{rca_text}\n\n"
            f"## Contributing Factors\n{factors_text or 'None identified.'}\n\n"
            f"## Relevant Runbooks\n{docs_text}"
        )

        result: RemediationOutput = llm.invoke([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ])

        completed = list(state.get("completed_steps") or []) + ["remediation"]
        log.info("Remediation complete: %d steps", len(result.remediation_steps))
        return {
            "remediation_steps": result.remediation_steps,
            "summary": result.summary,
            "completed_steps": completed,
        }

    except Exception as exc:
        log.warning("Remediation LLM failed, using fallback: %s", exc)
        result = _fallback(state)
        result["error"] = str(exc)
        return result
