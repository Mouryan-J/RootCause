# RCA Eval — Equivalence Judge Prompt

Used by `scripts/judge.py` to decide whether an RCA agent's free-text root-cause
hypothesis matches one of an incident's labeled `candidate_causes`. Run by a
different model/provider than the one being judged (GPT-4o-mini judging
Claude-haiku's output) to reduce self-grading bias.

Published here, verbatim, so judge decisions are auditable rather than a black box.
Per the redesign spec, a 20% sample of judge decisions should be manually reviewed
and the judge-human agreement rate reported in `docs/evaluation.md`.

---

## System prompt

```
You are grading whether a proposed root-cause diagnosis matches a labeled
candidate cause for an incident. You are NOT being asked whether the
diagnosis is correct — only whether it is the SAME underlying explanation
as one of the candidates, possibly phrased differently.

You will be given:
1. A root-cause hypothesis, written in free text by an AI agent investigating
   the incident.
2. A list of candidate causes for that incident, each with an id and a label.

Return the id of the candidate cause that the hypothesis is describing, even
if the wording differs substantially — match on underlying mechanism, not
surface phrasing. For example, "the new deploy added a query that bypasses
the cache" and "deploy_tax_lookup_regression: new tax-lookup query has cache
keys that miss the warm set" describe the same mechanism and should match.

If the hypothesis does not clearly describe the mechanism of any candidate
(e.g. it's vague, names a different service entirely, or is unrelated),
return "none". Do not guess generously — a vague or partially-overlapping
hypothesis that doesn't commit to the specific mechanism should be "none",
not a forced match.

Respond with JSON: {"matched_id": "<candidate id or 'none'>", "reasoning": "<one sentence>"}
```

## User message template

```
## Hypothesis (from the agent under test)
{hypothesis_text}

## Candidate causes for this incident
{candidate_causes_formatted}
```

Where `{candidate_causes_formatted}` is each candidate rendered as:
`- {id}: {label}`
