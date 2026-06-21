# RCA Reasoning Evaluation

`retrieval_eval.jsonl` (see README) measures whether the hybrid BM25+Qdrant+Cohere
stack can find the right runbook for a query. It does not measure whether the
system reaches the correct *diagnosis* — and its queries largely reuse the
target runbook's own wording, so a 96% Recall@1 score mostly demonstrates
string/embedding matching, not reasoning.

This evaluation is a separate, harder benchmark: incidents where the title
and logs never name the failure mode, each with 2-3 plausible candidate root
causes (exactly one correct), including distractors chosen specifically because
a system that pattern-matches surface symptoms would be tempted to pick them.
It tests whether the system can discriminate between competing explanations
from ambiguous, noisy evidence — the actual claim being made by an "RCA copilot."

## Eval Validity Notes

This benchmark went through several rounds of self-interrogation before the
numbers below were trustworthy. Disclosing the iteration rather than hiding
it, per the project's own standard: a number that survived a fix is more
credible than a clean number nobody tried to break.

- **Judge over-leniency, confirmed 3x, fixed.** The original LLM judge
  (`scripts/judge.py`) scored a content-free fallback response as a correct
  match purely on keyword/topic overlap with the right answer — found on
  manual spot-check, then reproduced twice more. Fixed by requiring the judge
  to identify a stated causal mechanism before matching, with 4 few-shot
  examples (including the actual fallback text that fooled it) showing a
  symptom-restatement must score "none" even when it shares service names
  with the correct candidate.
- **Parsing/truncation bug, found by the v1 run, partially fixed.** Every
  Top-1 miss in the original 18-incident run traced to one bug:
  `RCAOutput`'s JSON parser raised on trailing text after the array, and
  `max_tokens=1024` sometimes truncated generation before a required field
  was written — both falling back to a generic, content-free response.
  Fixed the parser (`raw_decode()` instead of `json.loads()`) and raised
  `max_tokens` to 2048, then added a retry-with-a-concise-instruction step
  before falling back. The retry measurably helps (60%→100% on a 5-incident
  spot-check) but doesn't eliminate the failure mode — it's still
  probabilistic at the token budget's edge. `_fallback_rca()` now sets an
  explicit `fallback: True` marker so eval scoring can exclude it
  deterministically instead of letting the judge guess at fuzzy-matched text.
- **Neo4j was never initialized in this eval script.** `get_service_dependencies()`
  only works after `init_neo4j()` sets its module-level connection, which is
  normally called by the FastAPI app's startup lifecycle — `run_rca_eval.py`
  never started that app, so every eval run (the entire v1 18-incident run,
  and the early v2 spot-checks) silently got an empty dependency graph
  regardless of what's actually seeded in Neo4j. Fixed by having the script
  call `init_neo4j()`/`close_neo4j()` itself; confirmed via logs that real
  graph edges now return (e.g. `depends_on=4` for payment-service).
- **Baseline A had no retry-before-fallback, unlike production `rca.py`.**
  This meant a chunk of Baseline A's "failures" across this project were an
  unrelated comparison-script gap, not reasoning misses — fixed by giving
  `run_baseline_a()` the same retry logic, and marking its hard failures
  with the same `fallback` flag so they're excluded from accuracy instead of
  counted as wrong.

## Methodology

Two dataset versions exist, run by the same harness (`scripts/run_rca_eval.py`,
which transparently adapts both schemas):

**v1 — `data/eval/rca_eval.jsonl` (18 incidents, historical).** Each incident
has a symptom-only `title` and a single `logs` text block, 2-3
`candidate_causes` (exactly one correct), and a `difficulty_tier` (1=direct,
2=competing causes, 3=multi-hop). A retrospective critique found this set's
distractors were often trivially nominal (e.g. "cache hit rate: healthy
95%") and its dependency-graph component was never actually exercised (see
Eval Validity Notes) — its numbers are kept below for transparency but are
**superseded** by v2.

**v2 — `data/eval/rca_eval_v2.jsonl` (8 incidents, current).** Structured
schema: a `timeline` of events (including deliberate red-herring deploys),
`logs_excerpt` with the causal chain deliberately *not* narrated in clean
reading order, a numeric `metrics_snapshot` the model must use to rule
distractors in/out, and `candidate_causes` where every wrong answer shares
literal evidence overlap with the true cause (a `why_tempting` field
documents exactly which token/metric makes it tempting) rather than being
obviously nominal. Covers 7 distinct failure classes — cascading
third-party latency (x2, one single-hop, one two-hop), multi-tenant
resource contention, a feature-flag-gated N+1 pattern, a producer/consumer
schema mismatch, a two-hop dependency-library version skew, a deliberately
*inverted* case where the true cause is local despite an upstream
red-herring metric, and a cache-invalidation race condition (a
data-correctness failure, not a latency/error one). All incidents use real
seeded Neo4j service names so the dependency graph is genuinely exercised,
not just present in the prompt as text.

Two baselines ran against every incident in both versions:
- **Baseline A** — incident text straight to `claude-haiku-4-5`, no retrieval,
  no graph, no triage/remediation split.
- **Baseline E** — the actual production pipeline,
  `rootcause.agents.graph.run_analysis()` (triage → retrieval → RCA → remediation).

Since the RCA agent answers in free text, an LLM judge (`scripts/judge.py`,
prompt in `scripts/judge_prompt.md`, gpt-4o-mini — a different model than the
one being judged) matches each hypothesis to a `candidate_causes[].id` by
mechanism, not exact wording — hardened per the Eval Validity Notes above to
require a stated mechanism, not topic overlap. **Top-1 Accuracy** =
judged-correct top-ranked hypothesis. **Top-3 Accuracy** = correct cause
anywhere in the top 3. **Hallucination Rate** = fraction of cited evidence
strings that don't fuzzy-match anything in the incident's logs (or retrieved
doc excerpts, for E). **Fallback Rate** = fraction of incidents where the
pipeline hit its content-free fallback path; these are excluded from the
accuracy numerator/denominator rather than scored as either right or wrong.

## v2 Results (current)

| | Top-1 Accuracy | Top-3 Accuracy | Hallucination Rate | Fallback Rate |
|---|---|---|---|---|
| Baseline A (bare LLM) | 100.0% (n=7) | 100.0% (n=7) | 7.1%* | 12.5% (1/8) |
| Baseline E (full system) | 100.0% (n=8) | 100.0% (n=8) | 0.0% | 0.0% (0/8) |

By difficulty tier (Baseline E):

| Tier | n | Top-1 | Top-3 |
|---|---|---|---|
| 2 — competing causes | 5 | 100.0% | 100.0% |
| 3 — multi-hop / data-correctness | 3 | 100.0% | 100.0% |

\* Both of Baseline A's flagged citations were real evidence the model
correctly synthesized from multiple source facts into one paraphrased
sentence (e.g. combining a deploy event, a pool-usage number, and a timing
correlation) — the fuzzy-match detector only checks similarity against a
*single* source line, so a faithful multi-fact paraphrase doesn't score as
grounded even though every component is traceable to real input. Manually
verified both against the source `logs_excerpt`/`metrics_snapshot`: neither
is a fabrication. This is a known limitation of the detection heuristic
itself, not a finding about the model.

**End-to-end pipeline latency** (Baseline E, wall-clock from `analysis_started`
to `analysis_complete`, extracted from run logs at no extra API cost): 11–20
seconds per incident, median ~15s across 8 incidents. The two incidents that
triggered the retry-before-fallback step took ~20s, a measurable and
explainable cost of that safety net.

**Honest takeaway: accuracy does not separate the two baselines.** Across
every run of both the v1 and v2 datasets, a bare LLM call ties the full
multi-agent pipeline on Top-1/Top-3 accuracy. `claude-haiku-4-5` is a strong
single-pass reasoner over well-presented evidence, even across 7 genuinely
distinct failure classes with hardened, evidence-sharing distractors. This
isn't a flaw in the harness — the judge, the grounding filter, the
dependency-graph wiring, and the fallback-retry logic were all independently
verified working (see Eval Validity Notes and worked examples below). It
means this benchmark's actual demonstrated value is different from "the
architecture improves accuracy": it's (1) the grounding/hallucination-control
behavior (Baseline E never fell back to a content-free response across this
run; the grounding filter strips fabricated evidence before it reaches the
output), and (2) the two real production bugs the evaluation process itself
found and fixed along the way. Isolating *which* architectural piece (if any)
contributes accuracy would require Baselines B/C/D — not run yet, see
Limitations.

## v2 Worked examples

**Genuine discrimination against a literally-overlapping distractor
(RCA-EVAL-V2-001, tier 2).** Symptoms: payment-service latency above SLO,
worker pool at 89% utilization. One distractor is a deploy to
payment-service itself that explicitly retunes "connection pool sizing" —
sharing the literal "pool" vocabulary with the real symptom, not a generic
recency trap. The system correctly distinguished it by noticing payment-service's
outbound connection pool is segmented by endpoint class: the pool serving
auth-service calls was at 100% utilization while the pool serving every
other endpoint sat at 12% — an asymmetry a pool-wide misconfiguration
wouldn't produce. The real cause (a new synchronous fraud-score lookup added
to auth-service's token validation) was correctly ranked first.

**Recognizing a downstream effect instead of a cause
(RCA-EVAL-V2-008, tier 3).** A cache-invalidation race (moved from
synchronous to async in a recent deploy) caused stale reads immediately
after writes. Redis's own eviction rate had genuinely quadrupled (3%→12%) —
a real, measurable anomaly directly involving the "stale" cache layer named
in the symptom. The system correctly identified this as a downstream
consequence of the same architecture change (the async invalidation task
backlog causing invalidation+repopulation bursts) rather than the trigger,
and ranked the actual race condition first.

**Testing for over-generalization, not just discrimination
(RCA-EVAL-V2-007, tier 2, deliberately inverted).** Every other incident in
this set has its true cause one or more hops upstream of the symptomatic
service — a system could learn "always blame upstream" as a shortcut and
still score well. This incident's true cause (a connection leak introduced
by api-gateway's *own* deploy) is local, with auth-service showing a real
but secondary latency uptick (95ms→110ms) designed to tempt exactly that
shortcut. The system correctly ruled out auth-service by magnitude (15ms is
far too small to explain api-gateway's SLO-violating creep) and direction
(more plausibly a downstream effect of the leak holding more connections
open, not a cause), correctly naming the local leak.

## v1 Results (historical, superseded — see Eval Validity Notes)

The numbers below are from the original 18-incident run, before the
parsing-bug fix, the judge hardening, and the Neo4j fix described above.
Kept for transparency, not as a current claim.

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

n=18, single run (no multi-run averaging for LLM nondeterminism — see
Limitations).

**Worked examples (v1).**

*Correct, genuine discrimination under ambiguity (RCA-EVAL-002, tier 2).*
Symptoms: checkout latency up 4x, a Redis cache-miss spike (4%→38%), a cache
GET timeout, and Postgres connections at 180/200 — three independently
alarming-looking signals. The full system's top hypothesis (confidence 0.85)
correctly identified the new tax-lookup query in a same-window deploy as the
cause, explicitly ranking the Redis and Postgres explanations *lower*
(0.75, 0.7) as plausible-but-secondary rather than picking either as primary.

*Same pattern on a multi-hop incident (RCA-EVAL-008, tier 3).* A Stripe
outage cascading through billing-service's own retry storm into checkout
504s. Top hypothesis (0.92) correctly named the upstream Stripe degradation,
not the locally-visible thread-pool exhaustion that "looks like" the cause
from inside billing-service's own logs.

*Failure mode — structured-output parsing fragility, not bad reasoning
(RCA-EVAL-017, RCA-EVAL-018, and others).* Both baselines hit the parsing
bug described in Eval Validity Notes. **Every Top-1 miss in this entire run
traces back to this bug path, not to the model picking a wrong-but-considered
hypothesis** — a real reliability finding, since fixed.

*Failure mode — the fallback cascading into a wrong diagnosis
(RCA-EVAL-016, tier 3).* When the parsing bug hit this incident, the
fallback text happened to repeat "shipping-rates-service ... carrier-api" —
and the judge matched that to the `carrier_api_flaky` distractor, the exact
wrong cause the incident was designed to tempt a shallow matcher into.

*Failure mode — judge over-leniency, found by manual spot-check
(RCA-EVAL-010, tier 3).* The judge scored a content-free symptom restatement
as matching the correct cause on service-name overlap alone — the bug fixed
in the Eval Validity Notes above.

## Limitations

- **n=8 for v2, single run.** LLM outputs are stochastic; a single pass
  isn't enough to separate signal from noise, especially given the
  fallback's known probabilistic recurrence. Multi-run averaging (3x per
  incident, mean ± std) is in the backlog, not done in this pass.
- **Accuracy doesn't separate Baseline A from Baseline E** (see Honest
  takeaway above) — only Baselines A and E have been run. B (RAG-only), C
  (hybrid retrieval only), and D (graph-RAG only) would isolate which
  architectural piece, if any, contributes accuracy beyond what the base
  model already does on its own. Not run yet.
- **Judge not independently audited at scale.** The few-shot hardening
  fixed three specific reproduced false positives; the spec's call for
  sampling 20% of judge decisions and reporting human-agreement rate has not
  been done.
- **`required_evidence_ids` exist in the v2 schema but aren't scored yet.**
  Evidence-quality precision/recall against exact evidence IDs (rather than
  fuzzy-matching free text) is designed into the dataset but not yet wired
  into `score_run()`.
- **No Confidence Calibration metric yet.** The RCA agent emits a confidence
  score per root cause; whether it's well-calibrated (a reliability diagram
  or Brier score) hasn't been measured.
- **v1's 18 incidents are kept for transparency but no longer represent
  current numbers** — see Eval Validity Notes for why they were superseded.

Full per-incident output, judge reasoning, and raw model responses:
`data/eval/rca_eval_results.json` (v1) and `data/eval/rca_eval_results_spotcheck.json`
(latest v2 run). Backlog (baselines B/C/D, evidence-ID scoring, calibration,
multi-run averaging, expanding the v2 set): `docs/rca-eval-progress.md`.
