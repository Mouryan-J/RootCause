"""LangGraph state shared across all agent nodes."""
from __future__ import annotations

from typing import Any

from typing_extensions import TypedDict


class IncidentState(TypedDict, total=False):
    # ── Input ────────────────────────────────────────────────────────────────
    incident_id: str
    title: str
    description: str
    service: str
    severity: str
    logs: str | None
    metrics: dict[str, Any] | None

    # ── Coordinator routing ───────────────────────────────────────────────────
    next_worker: str        # "triage" | "retrieval" | "rca" | "remediation" | "done"
    completed_steps: list[str]

    # ── Triage output ─────────────────────────────────────────────────────────
    incident_category: str
    key_signals: list[str]
    search_query: str

    # ── Retrieval output ──────────────────────────────────────────────────────
    retrieved_docs: list[dict]

    # ── RCA output ────────────────────────────────────────────────────────────
    root_causes: list[dict]         # [{description, confidence, evidence: []}]
    contributing_factors: list[str]

    # ── Remediation output ────────────────────────────────────────────────────
    remediation_steps: list[str]
    summary: str
    runbooks_referenced: list[str]

    # ── Metadata ──────────────────────────────────────────────────────────────
    model_used: str
    error: str | None
