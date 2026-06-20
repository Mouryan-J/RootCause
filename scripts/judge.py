"""
Equivalence judge for the RCA reasoning eval.

The RCA agent under test produces free-text root-cause descriptions, which
won't usually match a candidate_causes[].id verbatim (e.g. it might say "the
new deploy's query bypasses the warm cache" instead of repeating the label
"deploy_tax_lookup_regression" word for word). This module uses a separate
LLM call to decide which labeled candidate cause (if any) a hypothesis
actually describes.

Uses gpt-4o-mini regardless of which model produced the hypothesis, so the
judge is never grading its own output. Prompt is published in
scripts/judge_prompt.md for auditability -- keep the two in sync.
"""
from __future__ import annotations

import logging

from pydantic import BaseModel

from rootcause.core.config import get_settings

log = logging.getLogger(__name__)

JUDGE_SYSTEM_PROMPT = """\
You are grading whether a proposed root-cause diagnosis matches a labeled
candidate cause for an incident. You are NOT being asked whether the
diagnosis is correct -- only whether it is the SAME underlying explanation
as one of the candidates, possibly phrased differently.

You will be given:
1. A root-cause hypothesis, written in free text by an AI agent investigating
   the incident.
2. A list of candidate causes for that incident, each with an id and a label.

Before deciding, first identify the specific causal MECHANISM the hypothesis
states: the chain of "X happened, which caused Y, which produced the observed
symptom." A hypothesis that only restates the alert/symptom in different words
(e.g. naming the affected service and repeating the same error or metric that
was already given as input) without explaining WHY it happened states no
mechanism, and must be scored "none" -- even if it shares service names or
keywords with a candidate. Shared vocabulary is not shared mechanism.

Return the id of the candidate cause whose mechanism matches the hypothesis's
stated mechanism, even if the wording differs substantially. Do not guess
generously -- a vague, partially-overlapping, or symptom-only hypothesis that
doesn't commit to a specific mechanism should be "none", not a forced match.

## Examples

Hypothesis: "Potential issue in billing-service: Checkout failing with 504s,
billing-service reporting thread pool exhaustion"
Candidates: - upstream_provider_outage_amplified_by_retries: Stripe API
degradation triggered a retry storm that exhausted billing-service's thread pool
Correct verdict: none
Why: This just restates the alert -- the same service name and the same
exhaustion symptom already given as input. It never says WHY the pool
exhausted (no mention of Stripe, retries, or any upstream cause). Matching on
"thread pool exhaustion" keyword overlap alone would be wrong.

Hypothesis: "Potential issue in recommendations-service: Multiple unrelated
services timing out against recommendations-service"
Candidates: - upstream_gc_pause_amplified_by_mesh_retries: a new caching layer
in user-profile-service caused long GC pauses, and downstream retries amplified
the resulting latency into widespread timeouts
Correct verdict: none
Why: "Multiple services timing out" restates the symptom already reported. It
never identifies user-profile-service, GC pauses, or a caching layer -- there
is no mechanism here to match against.

Hypothesis: "There may be an issue with the database affecting checkout"
Candidates: - db_connection_pool_exhaustion: a connection leak in the new
payments client exhausted the pool
Correct verdict: none
Why: "An issue with the database" is a guess at the affected component, not a
stated mechanism. No leak, no pool, no specific failure is named.

Hypothesis: "The new deploy added a query that bypasses the cache, hitting the
database directly on every request"
Candidates: - deploy_tax_lookup_regression: new tax-lookup query has cache keys
that miss the warm set, forcing extra DB round-trips on every checkout
Correct verdict: deploy_tax_lookup_regression
Why: Different wording, same mechanism -- a new query path skipping the cache
and hitting the DB directly. This matches despite sharing no literal keywords
with the candidate's label.

In your reasoning, state the mechanism the hypothesis actually gives (or note
that it gives none) before concluding whether that matches a candidate."""


class JudgeVerdict(BaseModel):
    matched_id: str
    reasoning: str


def _format_candidates(candidate_causes: list[dict]) -> str:
    return "\n".join(f"- {c['id']}: {c['label']}" for c in candidate_causes)


def judge_hypothesis(
    hypothesis_text: str,
    candidate_causes: list[dict],
    judge_model: str | None = None,
) -> JudgeVerdict:
    """Decide which candidate_causes[].id (if any) a free-text hypothesis matches."""
    settings = get_settings()
    if not settings.openai_api_key:
        log.warning("openai_api_key not set, judge cannot run -- returning 'none'")
        return JudgeVerdict(matched_id="none", reasoning="judge unavailable: no API key")

    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        model=judge_model or settings.model_agents,
        api_key=settings.openai_api_key,
        temperature=0,
    ).with_structured_output(JudgeVerdict)

    user_message = (
        f"## Hypothesis (from the agent under test)\n{hypothesis_text}\n\n"
        f"## Candidate causes for this incident\n{_format_candidates(candidate_causes)}"
    )

    try:
        result: JudgeVerdict = llm.invoke([
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ])
        return result
    except Exception as exc:
        log.warning("Judge call failed: %s", exc)
        return JudgeVerdict(matched_id="none", reasoning=f"judge error: {exc}")
