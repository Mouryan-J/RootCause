# RCA Reasoning Evaluation

`retrieval_eval.jsonl` (see README) measures whether the hybrid BM25+Qdrant+Cohere
stack can find the right runbook for a query. It does not measure whether the
system reaches the correct *diagnosis* — and its queries largely reuse the
target runbook's own wording, so a 96% Recall@1 score mostly demonstrates
string/embedding matching, not reasoning.

This evaluation is a separate, harder benchmark: **18 incidents where the title
and logs never name the failure mode**, each with 2-3 plausible candidate root
causes (exactly one correct), including distractors chosen specifically because
a system that pattern-matches surface symptoms would be tempted to pick them.
It tests whether the system can discriminate between competing explanations
from ambiguous, noisy evidence — the actual claim being made by an "RCA copilot."

## Methodology

Each incident in `data/eval/rca_eval.jsonl` has:
- A symptom-only `title` and multi-line `logs` (timestamps, errors, metric
  readings as raw text — no separate clean `metrics` dict handed to the model)
- 2-3 `candidate_causes`, exactly one `is_correct: true`; wrong candidates
  carry a `why_plausible` note explaining what makes them a tempting
  superficial match
- `supporting_evidence_lines` / `distractor_evidence_lines` (log line indices)
- `expected_remediation`, `difficulty_tier` (1=direct, 2=competing causes,
  3=multi-hop across services), `required_reasoning_hops`, `category`

Tier distribution: 5 tier-1, 9 tier-2, 4 tier-3, across 9 categories (database,
deploy regression, messaging, resource exhaustion, cache, DNS/cert,
network/third-party, config, service mesh).

Two baselines ran against every incident:
- **Baseline A** — incident text straight to `claude-haiku-4-5`, no retrieval,
  no graph, no triage/remediation split.
- **Baseline E** — the actual production pipeline,
  `rootcause.agents.graph.run_analysis()` (triage → retrieval → RCA → remediation).

Since the RCA agent answers in free text, an LLM judge (`scripts/judge.py`,
prompt in `scripts/judge_prompt.md`, gpt-4o-mini — a different model than the
one being judged) matches each hypothesis to a `candidate_causes[].id` by
mechanism, not exact wording. **Top-1 Accuracy** = judged-correct top-ranked
hypothesis. **Top-3 Accuracy** = correct cause anywhere in the top 3.
**Hallucination Rate** = fraction of cited evidence strings that don't
fuzzy-match anything in the incident's logs (or retrieved doc excerpts, for E).

## Results

| | Top-1 Accuracy | Top-3 Accuracy | Avg Hallucination Rate |
|---|---|---|---|
| Baseline A (bare LLM) | 88.9% | 88.9% | 18.8% |
| Baseline E (full system) | 88.9% | 88.9% | 26.4% |

By difficulty tier (identical for both baselines on this run):

| Tier | n | Top-1 | Top-3 |
|---|---|---|---|
| 1 — direct | 5 | 100.0% | 100.0% |
| 2 — competing causes | 9 | 88.9% | 88.9% |
| 3 — multi-hop | 4 | 75.0% | 75.0% |

The headline numbers tie, but they're not telling the same story underneath —
see failure cases below. n=18, single run (no multi-run averaging for LLM
nondeterminism yet — see Limitations).

## Worked examples

**Correct, genuine discrimination under ambiguity (RCA-EVAL-002, tier 2).**
Symptoms: checkout latency up 4x, a Redis cache-miss spike (4%→38%), a cache
GET timeout, and Postgres connections at 180/200 — three independently
alarming-looking signals. The full system's top hypothesis (confidence 0.85)
correctly identified the new tax-lookup query in a same-window deploy as the
cause, explicitly ranking the Redis and Postgres explanations *lower*
(0.75, 0.7) as plausible-but-secondary rather than picking either as primary.
This is the target behavior the critique asked for: weighing competing
evidence instead of grabbing the first keyword match.

**Same pattern on a multi-hop incident (RCA-EVAL-008, tier 3).** A Stripe
outage cascading through billing-service's own retry storm into checkout
504s. Top hypothesis (0.92) correctly named the upstream Stripe degradation,
not the locally-visible thread-pool exhaustion that "looks like" the cause
from inside billing-service's own logs.

**Failure mode #1 — structured-output parsing fragility, not bad reasoning
(RCA-EVAL-017, RCA-EVAL-018; also several incidents mid-run).** Both baselines
hit real production bugs in `RCAOutput` parsing during this run: the model
occasionally appends trailing text after a JSON array (`Extra data` pydantic
error), or runs out of `max_tokens=1024` mid-generation and drops the
required `contributing_factors` field. Both trigger `rca.py`'s
`_fallback_rca()`, a generic restatement of the input with no real diagnosis.
**Every Top-1 miss in this entire eval traces back to this bug path, not to
the model picking a wrong-but-considered hypothesis.** This is a real
reliability finding, not an eval artifact — `rootcause/agents/rca.py`'s
`max_tokens` and the lenient-string-parsing validator are worth hardening
(tracked as backlog, not fixed in this pass — out of scope for eval tooling).

**Failure mode #2 — the fallback cascading into a wrong diagnosis
(RCA-EVAL-016, tier 3).** When the parsing bug above hit this incident, the
fallback text happened to repeat "shipping-rates-service ... carrier-api" —
and the judge matched that to the `carrier_api_flaky` *distractor*, the exact
wrong cause the incident was designed to tempt a shallow matcher into. The
production system would have gotten this right (Baseline A, unaffected by
the bug on this incident, correctly named the DNS TTL migration) — the miss
is a generation-reliability failure, not a reasoning failure.

**Failure mode #3 — judge over-leniency, found by manual spot-check
(RCA-EVAL-010, tier 3).** Also hit the fallback bug; the resulting hypothesis
was just "Multiple unrelated services timing out against
recommendations-service" — a restatement of the *symptom*, naming no
mechanism at all. The judge nonetheless scored this as matching the correct
cause (`upstream_gc_pause_amplified_by_mesh_retries`), reasoning that the
service names "aligned." **Manually reviewing this one decision found a false
positive**: the judge is too willing to match topical/keyword overlap rather
than requiring the hypothesis to actually state the causal mechanism. This
means Baseline E's true accuracy on genuinely-reasoned outputs is a little
lower than the 88.9% headline number suggests — at least one of its 16
"correct" scores didn't reason its way there.

## Limitations

- **n=18, single run per incident.** LLM outputs are stochastic at the
  temperatures used elsewhere in the pipeline; a single pass isn't enough to
  separate signal from noise, especially at the tier level (n=4 for tier 3).
- **Judge not independently audited at scale.** One manual spot-check (above)
  found a false positive. The spec calls for sampling 20% of judge decisions
  and reporting agreement rate — not done in this pass.
- **Only baselines A and E run.** B (RAG-only), C (hybrid retrieval only),
  and D (graph-RAG only) would isolate which architectural piece — retrieval,
  reranking, the dependency graph — actually contributes accuracy. Without
  them, "E ties A" cannot be separated into "the extra machinery adds nothing"
  vs. "the extra machinery's gains were masked by the parsing bug hitting both
  baselines independently." The worked examples above suggest the latter, but
  that's a hypothesis, not a measured result.
- **No Confidence Calibration, Cost, or Latency metrics yet.**
- **The parsing bug found here was not fixed in this pass** — fixing
  production agent code was explicitly out of scope for this eval-tooling
  change. It's the highest-leverage next fix: every single miss in this
  dataset traces back to it.

Full per-incident output, judge reasoning, and raw model responses:
`data/eval/rca_eval_results.json`. Phase 2 backlog (baselines B/C/D,
calibration, cost/latency, larger eval set, multi-run averaging,
the parsing-bug fix): `docs/rca-eval-progress.md`.
