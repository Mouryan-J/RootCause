"""
RCA reasoning evaluation.

Distinct from run_eval.py (which measures retrieval-only Recall/MRR on
queries that echo their target runbook's own wording). This script measures
whether the system reaches the CORRECT root cause on incidents where the
input is symptom-only, ambiguous, and contains plausible-but-wrong distractor
causes -- i.e. whether the system reasons, not just retrieves.

Runs two baselines against every incident in data/eval/rca_eval.jsonl:
  Baseline A (bare LLM)   -- incident text straight to claude-haiku, no
                             retrieval, no graph, no triage/remediation split.
  Baseline E (full system)-- the real production pipeline,
                             rootcause.agents.graph.run_analysis().

For each, an LLM judge (scripts/judge.py) matches the top-ranked free-text
hypothesis against the incident's labeled candidate_causes, computing
Top-1/Top-3 RCA Accuracy. A simple fuzzy-match grounding check against the
incident's source text (logs, plus retrieved doc excerpts for Baseline E)
estimates a Hallucination Rate on cited evidence.

This makes real LLM calls (OpenAI + Anthropic, plus judge calls) -- costs
API credits. Confirm before running against all 18 incidents.

Usage:
    uv run python scripts/run_rca_eval.py
"""
from __future__ import annotations

import asyncio
import difflib
import json
import logging
import sys
import uuid
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from judge import judge_hypothesis

from rootcause.agents.graph import run_analysis
from rootcause.agents.rca import SYSTEM_PROMPT as RCA_SYSTEM_PROMPT
from rootcause.agents.rca import RCAOutput
from rootcause.core.config import get_settings

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger(__name__)

EVAL_PATH = Path("data/eval/rca_eval.jsonl")
RESULTS_PATH = Path("data/eval/rca_eval_results.json")
GROUNDING_MATCH_THRESHOLD = 0.4


def load_eval() -> list[dict]:
    with open(EVAL_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _correct_cause_id(incident: dict) -> str:
    return next(c["id"] for c in incident["candidate_causes"] if c["is_correct"])


# ── Baseline A: bare LLM, no retrieval/graph/triage/remediation ────────────


def run_baseline_a(incident: dict) -> dict:
    """Incident text straight to claude-haiku. Tests parametric reasoning alone."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        return {"root_causes": [], "error": "anthropic_api_key not set"}

    from langchain_anthropic import ChatAnthropic

    llm = ChatAnthropic(
        model=settings.model_rca,
        api_key=settings.anthropic_api_key,
        temperature=0,
        max_tokens=2048,
    ).with_structured_output(RCAOutput)

    incident_text = (
        f"## Incident\n"
        f"Title: {incident['title']}\n"
        f"Service: {incident['service']}\n"
        f"Severity: {incident['severity']}\n\n"
        f"## Retrieved Documents\nNo runbooks retrieved.\n\n"
        f"Logs:\n{incident['logs']}\n"
    )

    try:
        result: RCAOutput = llm.invoke([
            {"role": "user", "content": f"{RCA_SYSTEM_PROMPT}\n\n{incident_text}"},
        ])
        return {
            "root_causes": [rc.model_dump() for rc in result.root_causes],
            "contributing_factors": result.contributing_factors,
        }
    except Exception as exc:
        log.warning("Baseline A failed for %s: %s", incident["incident_id"], exc)
        return {"root_causes": [], "error": str(exc)}


# ── Baseline E: full production pipeline ────────────────────────────────────


async def run_baseline_e(incident: dict) -> dict:
    final = await run_analysis(
        incident_id=uuid.uuid4(),
        title=incident["title"],
        description=incident["title"],
        service=incident["service"],
        severity=incident["severity"],
        logs=incident["logs"],
    )
    return {
        "root_causes": final.get("root_causes") or [],
        "contributing_factors": final.get("contributing_factors") or [],
        "retrieved_docs": final.get("retrieved_docs") or [],
    }


# ── Grounding / hallucination check ─────────────────────────────────────────


def _evidence_grounded(evidence: str, source_lines: list[str]) -> bool:
    ev = evidence.lower().strip()
    if not ev:
        return True
    for line in source_lines:
        line_l = line.lower()
        if ev in line_l or line_l in ev:
            return True
        if difflib.SequenceMatcher(None, ev, line_l).ratio() >= GROUNDING_MATCH_THRESHOLD:
            return True
    return False


def hallucination_rate(top_hypothesis: dict, source_lines: list[str]) -> float | None:
    citations = top_hypothesis.get("evidence") or []
    if not citations:
        return None
    ungrounded = sum(1 for c in citations if not _evidence_grounded(c, source_lines))
    return round(ungrounded / len(citations), 3)


# ── Scoring ──────────────────────────────────────────────────────────────────


def score_run(incident: dict, run_result: dict, source_lines: list[str]) -> dict:
    root_causes = run_result.get("root_causes") or []
    correct_id = _correct_cause_id(incident)

    judged = []
    for rc in root_causes[:3]:
        verdict = judge_hypothesis(rc.get("description", ""), incident["candidate_causes"])
        judged.append({"description": rc.get("description", ""), "matched_id": verdict.matched_id, "reasoning": verdict.reasoning})

    top1_correct = bool(judged) and judged[0]["matched_id"] == correct_id
    top3_correct = any(j["matched_id"] == correct_id for j in judged)
    hrate = hallucination_rate(root_causes[0], source_lines) if root_causes else None

    return {
        "incident_id": incident["incident_id"],
        "difficulty_tier": incident["difficulty_tier"],
        "category": incident["category"],
        "judged_hypotheses": judged,
        "top1_correct": top1_correct,
        "top3_correct": top3_correct,
        "hallucination_rate": hrate,
        "error": run_result.get("error"),
    }


def _aggregate(scores: list[dict]) -> dict:
    n = len(scores)
    if n == 0:
        return {}
    top1 = sum(s["top1_correct"] for s in scores) / n
    top3 = sum(s["top3_correct"] for s in scores) / n
    hrates = [s["hallucination_rate"] for s in scores if s["hallucination_rate"] is not None]
    avg_hrate = sum(hrates) / len(hrates) if hrates else None

    by_tier: dict[int, dict] = {}
    for tier in sorted({s["difficulty_tier"] for s in scores}):
        tier_scores = [s for s in scores if s["difficulty_tier"] == tier]
        tn = len(tier_scores)
        by_tier[tier] = {
            "n": tn,
            "top1_accuracy": round(sum(s["top1_correct"] for s in tier_scores) / tn, 3),
            "top3_accuracy": round(sum(s["top3_correct"] for s in tier_scores) / tn, 3),
        }

    return {
        "n": n,
        "top1_accuracy": round(top1, 3),
        "top3_accuracy": round(top3, 3),
        "avg_hallucination_rate": round(avg_hrate, 3) if avg_hrate is not None else None,
        "by_difficulty_tier": by_tier,
    }


def print_summary(name: str, agg: dict) -> None:
    print(f"\n{'-' * 50}")
    print(f"  {name}  (n={agg.get('n')})")
    print(f"{'-' * 50}")
    print(f"  Top-1 RCA Accuracy   {agg.get('top1_accuracy', 0) * 100:5.1f}%")
    print(f"  Top-3 RCA Accuracy   {agg.get('top3_accuracy', 0) * 100:5.1f}%")
    hr = agg.get("avg_hallucination_rate")
    print(f"  Avg Hallucination Rate  {hr * 100:5.1f}%" if hr is not None else "  Avg Hallucination Rate  n/a")
    print("  By difficulty tier:")
    for tier, stats in agg.get("by_difficulty_tier", {}).items():
        print(f"    Tier {tier} (n={stats['n']}): Top-1 {stats['top1_accuracy'] * 100:5.1f}%  Top-3 {stats['top3_accuracy'] * 100:5.1f}%")


async def main() -> None:
    incidents = load_eval()
    print(f"\nRunning RCA reasoning eval on {len(incidents)} incidents...\n")

    a_scores, e_scores = [], []
    a_raw, e_raw = {}, {}

    for i, incident in enumerate(incidents):
        log_lines = incident["logs"].split("\n")
        print(f"[{i + 1}/{len(incidents)}] {incident['incident_id']}: {incident['title'][:60]}")

        a_result = run_baseline_a(incident)
        a_raw[incident["incident_id"]] = a_result
        a_scores.append(score_run(incident, a_result, log_lines))

        e_result = await run_baseline_e(incident)
        e_raw[incident["incident_id"]] = e_result
        e_source_lines = log_lines + [d["excerpt"] for d in e_result.get("retrieved_docs", [])]
        e_scores.append(score_run(incident, e_result, e_source_lines))

    a_agg = _aggregate(a_scores)
    e_agg = _aggregate(e_scores)

    # Write results to disk BEFORE any further printing -- a console
    # encoding issue or other formatting error here must not lose the
    # already-paid-for LLM call results.
    results = {
        "baseline_a": {"aggregate": a_agg, "per_incident": a_scores, "raw_outputs": a_raw},
        "baseline_e": {"aggregate": e_agg, "per_incident": e_scores, "raw_outputs": e_raw},
    }
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nFull results written to {RESULTS_PATH}")

    print_summary("Baseline A -- bare LLM (no retrieval/graph/triage)", a_agg)
    print_summary("Baseline E -- full RootCause system", e_agg)

    print(f"\n{'=' * 50}")
    print("  Improvement (E vs A)")
    print(f"{'=' * 50}")
    print(f"  Top-1 Accuracy  {(e_agg['top1_accuracy'] - a_agg['top1_accuracy']) * 100:+.1f}%")
    print(f"  Top-3 Accuracy  {(e_agg['top3_accuracy'] - a_agg['top3_accuracy']) * 100:+.1f}%")


if __name__ == "__main__":
    asyncio.run(main())
