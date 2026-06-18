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

Return the id of the candidate cause that the hypothesis is describing, even
if the wording differs substantially -- match on underlying mechanism, not
surface phrasing. For example, "the new deploy added a query that bypasses
the cache" and "deploy_tax_lookup_regression: new tax-lookup query has cache
keys that miss the warm set" describe the same mechanism and should match.

If the hypothesis does not clearly describe the mechanism of any candidate
(e.g. it's vague, names a different service entirely, or is unrelated),
return "none". Do not guess generously -- a vague or partially-overlapping
hypothesis that doesn't commit to the specific mechanism should be "none",
not a forced match."""


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
