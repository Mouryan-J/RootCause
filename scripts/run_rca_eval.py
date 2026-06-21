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
from rootcause.agents.rca import RETRY_NOTE
from rootcause.agents.rca import SYSTEM_PROMPT as RCA_SYSTEM_PROMPT
from rootcause.agents.rca import RCAOutput
from rootcause.core.config import get_settings
from rootcause.db.neo4j_client import close_neo4j, init_neo4j

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger(__name__)

EVAL_PATH = Path("data/eval/rca_eval.jsonl")
EVAL_V2_PATH = Path("data/eval/rca_eval_v2.jsonl")
# Separate file, kept apart from the main v1/v2 set: these incidents are
# deliberately constructed so Baseline A structurally cannot name the
# correct dependency (no service names in logs/metrics, only a type
# signature) -- a graph-necessity probe, not a general reasoning benchmark.
# Always loaded (so `category` filtering at report time is the same code
# path either way), but must be reported separately by category --
# blending it into one combined accuracy number would conflate two
# different research questions (general reasoning vs. graph necessity).
EVAL_GRAPH_TEST_PATH = Path("data/eval/rca_eval_graph_test.jsonl")
RESULTS_PATH = Path("data/eval/rca_eval_results.json")
GROUNDING_MATCH_THRESHOLD = 0.4


def load_eval() -> list[dict]:
    incidents = []
    for path in (EVAL_PATH, EVAL_V2_PATH, EVAL_GRAPH_TEST_PATH):
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            incidents.extend(json.loads(line) for line in f if line.strip())
    return incidents


def _correct_cause_id(incident: dict) -> str:
    return next(c["id"] for c in incident["candidate_causes"] if c["is_correct"])


def _incident_title(incident: dict) -> str:
    """v1 incidents use `title`; v2 incidents use `alert_title`."""
    return incident.get("alert_title") or incident.get("title", "")


def _incident_tier(incident: dict) -> int:
    """v1 incidents use `difficulty_tier`; v2 incidents use `tier`."""
    return incident.get("difficulty_tier", incident.get("tier"))


def _incident_logs_text(incident: dict) -> str:
    """v1 incidents carry a single `logs` string. v2 incidents carry a
    structured `timeline` + `logs_excerpt` instead -- combined here into one
    chronological text block so both schemas flow through the same
    prompt-building code in both baselines."""
    if "logs" in incident:
        return incident["logs"]
    lines = [f"[{e['t']}] {e['event']}" for e in incident.get("timeline", [])]
    lines.extend(incident.get("logs_excerpt", []))
    return "\n".join(lines)


def _incident_metrics(incident: dict) -> dict | None:
    """v2-only: a structured numeric metrics_snapshot the model must use to
    rule distractors in/out. v1 incidents have no equivalent (their metrics
    live inline as text inside `logs`), so this is None for them."""
    return incident.get("metrics_snapshot")


# ── Baseline A: bare LLM, no retrieval/graph/triage/remediation ────────────


def run_baseline_a(incident: dict) -> dict:
    """Incident text straight to claude-haiku. Tests parametric reasoning alone."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        return {"root_causes": [], "error": "anthropic_api_key not set", "fallback": True}

    from langchain_anthropic import ChatAnthropic

    llm = ChatAnthropic(
        model=settings.model_rca,
        api_key=settings.anthropic_api_key,
        temperature=0,
        max_tokens=3072,
    ).with_structured_output(RCAOutput)

    metrics = _incident_metrics(incident)
    incident_text = (
        f"## Incident\n"
        f"Title: {_incident_title(incident)}\n"
        f"Service: {incident['service']}\n"
        f"Severity: {incident['severity']}\n\n"
        f"## Retrieved Documents\nNo runbooks retrieved.\n\n"
        f"Logs:\n{_incident_logs_text(incident)}\n"
    )
    if metrics:
        incident_text += f"\nMetrics: {metrics}\n"

    base_content = f"{RCA_SYSTEM_PROMPT}\n\n{incident_text}"
    try:
        result: RCAOutput = llm.invoke([{"role": "user", "content": base_content}])
    except Exception as first_exc:
        log.warning(
            "Baseline A generation failed for %s, retrying once with a concise instruction: %s",
            incident["incident_id"],
            first_exc,
        )
        try:
            result = llm.invoke([{"role": "user", "content": base_content + RETRY_NOTE}])
        except Exception as exc:
            log.warning("Baseline A failed for %s after retry: %s", incident["incident_id"], exc)
            return {"root_causes": [], "error": str(exc), "fallback": True}

    return {
        "root_causes": [rc.model_dump() for rc in result.root_causes],
        "contributing_factors": result.contributing_factors,
        "fallback": False,
    }


# ── Baseline E: full production pipeline ────────────────────────────────────


async def run_baseline_e(incident: dict) -> dict:
    final = await run_analysis(
        incident_id=uuid.uuid4(),
        title=_incident_title(incident),
        description=_incident_title(incident),
        service=incident["service"],
        severity=incident["severity"],
        logs=_incident_logs_text(incident),
        metrics=_incident_metrics(incident),
    )
    return {
        "root_causes": final.get("root_causes") or [],
        "contributing_factors": final.get("contributing_factors") or [],
        "retrieved_docs": final.get("retrieved_docs") or [],
        "service_graph": final.get("service_graph") or {},
        "fallback": bool(final.get("fallback", False)),
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
    is_fallback = bool(run_result.get("fallback", False))

    judged = []
    for rc in root_causes[:3]:
        verdict = judge_hypothesis(rc.get("description", ""), incident["candidate_causes"])
        judged.append({"description": rc.get("description", ""), "matched_id": verdict.matched_id, "reasoning": verdict.reasoning})

    top1_correct = bool(judged) and judged[0]["matched_id"] == correct_id
    top3_correct = any(j["matched_id"] == correct_id for j in judged)
    hrate = hallucination_rate(root_causes[0], source_lines) if root_causes else None

    return {
        "incident_id": incident["incident_id"],
        "difficulty_tier": _incident_tier(incident),
        "category": incident["category"],
        "judged_hypotheses": judged,
        "top1_correct": top1_correct,
        "top3_correct": top3_correct,
        "hallucination_rate": hrate,
        # Pipeline hit its content-free fallback path -- exclude from accuracy
        # numerator/denominator instead of letting the judge score a generic
        # placeholder as either right or wrong; track it as its own rate.
        "fallback": is_fallback,
        "error": run_result.get("error"),
    }


def _accuracy_stats(scores: list[dict]) -> dict:
    scored = [s for s in scores if not s["fallback"]]
    n = len(scored)
    if n == 0:
        return {"n": 0, "top1_accuracy": None, "top3_accuracy": None}
    return {
        "n": n,
        "top1_accuracy": round(sum(s["top1_correct"] for s in scored) / n, 3),
        "top3_accuracy": round(sum(s["top3_correct"] for s in scored) / n, 3),
    }


def _aggregate(scores: list[dict]) -> dict:
    total_n = len(scores)
    if total_n == 0:
        return {}
    fallback_count = sum(s["fallback"] for s in scores)
    scored = [s for s in scores if not s["fallback"]]

    hrates = [s["hallucination_rate"] for s in scored if s["hallucination_rate"] is not None]
    avg_hrate = sum(hrates) / len(hrates) if hrates else None

    by_tier: dict[int, dict] = {}
    for tier in sorted({s["difficulty_tier"] for s in scores}):
        by_tier[tier] = _accuracy_stats([s for s in scores if s["difficulty_tier"] == tier])

    stats = _accuracy_stats(scores)
    return {
        "total_n": total_n,
        "fallback_count": fallback_count,
        "fallback_rate": round(fallback_count / total_n, 3),
        **stats,
        "avg_hallucination_rate": round(avg_hrate, 3) if avg_hrate is not None else None,
        "by_difficulty_tier": by_tier,
    }


def print_summary(name: str, agg: dict) -> None:
    print(f"\n{'-' * 50}")
    print(f"  {name}  (total n={agg.get('total_n')}, fallback excluded={agg.get('fallback_count')})")
    print(f"{'-' * 50}")
    print(f"  Fallback Rate   {agg.get('fallback_rate', 0) * 100:5.1f}%")
    top1 = agg.get("top1_accuracy")
    top3 = agg.get("top3_accuracy")
    print(f"  Top-1 RCA Accuracy   {top1 * 100:5.1f}%  (n={agg.get('n')})" if top1 is not None else "  Top-1 RCA Accuracy   n/a (all fallback)")
    print(f"  Top-3 RCA Accuracy   {top3 * 100:5.1f}%  (n={agg.get('n')})" if top3 is not None else "  Top-3 RCA Accuracy   n/a (all fallback)")
    hr = agg.get("avg_hallucination_rate")
    print(f"  Avg Hallucination Rate  {hr * 100:5.1f}%" if hr is not None else "  Avg Hallucination Rate  n/a")
    print("  By difficulty tier:")
    for tier, stats in agg.get("by_difficulty_tier", {}).items():
        t1 = f"{stats['top1_accuracy'] * 100:5.1f}%" if stats["top1_accuracy"] is not None else "n/a"
        t3 = f"{stats['top3_accuracy'] * 100:5.1f}%" if stats["top3_accuracy"] is not None else "n/a"
        print(f"    Tier {tier} (n={stats['n']}): Top-1 {t1}  Top-3 {t3}")


async def main() -> None:
    incidents = load_eval()
    results_path = RESULTS_PATH

    requested_ids = sys.argv[1:]
    if requested_ids:
        incidents = [i for i in incidents if i["incident_id"] in requested_ids]
        missing = set(requested_ids) - {i["incident_id"] for i in incidents}
        if missing:
            print(f"Warning: unknown incident ids ignored: {sorted(missing)}")
        # Spot-checks write to a separate file so they never clobber a full
        # 18-incident results.json with partial data.
        results_path = RESULTS_PATH.with_name("rca_eval_results_spotcheck.json")

    # Baseline E's retrieval_node calls get_service_dependencies(), which
    # reads a connection only init_neo4j() sets up -- normally done by the
    # FastAPI app's startup lifecycle, which this standalone script never
    # runs. Without this, every eval run silently gets an empty dependency
    # graph regardless of what's actually seeded in Neo4j.
    try:
        await init_neo4j()
    except Exception as exc:
        log.warning("Neo4j unavailable for this run -- dependency graph will be empty: %s", exc)

    print(f"\nRunning RCA reasoning eval on {len(incidents)} incidents...\n")

    a_scores, e_scores = [], []
    a_raw, e_raw = {}, {}

    try:
        for i, incident in enumerate(incidents):
            log_lines = _incident_logs_text(incident).split("\n")
            print(f"[{i + 1}/{len(incidents)}] {incident['incident_id']}: {_incident_title(incident)[:60]}")

            a_result = run_baseline_a(incident)
            a_raw[incident["incident_id"]] = a_result
            a_scores.append(score_run(incident, a_result, log_lines))

            e_result = await run_baseline_e(incident)
            e_raw[incident["incident_id"]] = e_result
            e_source_lines = log_lines + [d["excerpt"] for d in e_result.get("retrieved_docs", [])]
            e_scores.append(score_run(incident, e_result, e_source_lines))
    finally:
        await close_neo4j()

    a_agg = _aggregate(a_scores)
    e_agg = _aggregate(e_scores)

    # Write results to disk BEFORE any further printing -- a console
    # encoding issue or other formatting error here must not lose the
    # already-paid-for LLM call results.
    results = {
        "baseline_a": {"aggregate": a_agg, "per_incident": a_scores, "raw_outputs": a_raw},
        "baseline_e": {"aggregate": e_agg, "per_incident": e_scores, "raw_outputs": e_raw},
    }
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nResults written to {results_path}")

    print_summary("Baseline A -- bare LLM (no retrieval/graph/triage)", a_agg)
    print_summary("Baseline E -- full RootCause system", e_agg)

    print(f"\n{'=' * 50}")
    print("  Improvement (E vs A)")
    print(f"{'=' * 50}")
    if a_agg["top1_accuracy"] is not None and e_agg["top1_accuracy"] is not None:
        print(f"  Top-1 Accuracy  {(e_agg['top1_accuracy'] - a_agg['top1_accuracy']) * 100:+.1f}%")
        print(f"  Top-3 Accuracy  {(e_agg['top3_accuracy'] - a_agg['top3_accuracy']) * 100:+.1f}%")
    else:
        print("  n/a -- one or both baselines had no non-fallback incidents to compare")


if __name__ == "__main__":
    asyncio.run(main())
