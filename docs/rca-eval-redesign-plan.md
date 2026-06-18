# RootCause — RCA Evaluation Redesign Plan

**Purpose:** Fix the "inputs are too clean / answer-revealing" critique by building a real RCA benchmark, distinct from the existing retrieval benchmark, and using it to prove the system reasons rather than pattern-matches.

This document is written to be handed to Claude Code as an implementation spec. Each section ends with concrete file/script deliverables.

---

## 1. Current Weaknesses

**1.1 — Two different evaluations are being conflated.**
`retrieval_eval.jsonl` (50 queries → correct runbook) measures retrieval quality. It is a valid, well-designed benchmark *for what it tests*. The problem is that its result (96% Recall@1) gets read by an outside reviewer as evidence the whole system "works," when it only proves the embedding + BM25 + rerank stack finds the right document. There is currently **no benchmark that measures whether the RCA agent's final diagnosis is correct.**

**1.2 — The showcase incidents are answer-revealing.**
"Database connection pool exhausted," "Redis cache causing checkout latency," "Payment service returning 503s" — each of these is a *conclusion*, not a *symptom report*. A real on-call engineer doesn't open a ticket already knowing the cause; they see timeouts, latency graphs, and error codes and have to figure out the cause. When the input already contains the answer, the RCA agent's job degrades to "find the runbook whose title matches this sentence" — which is retrieval, not diagnosis, wearing a diagnosis costume.

**1.3 — No example currently has more than one plausible cause.**
Every demo incident maps to exactly one runbook with no competing explanation. This means the system has never been forced to *discriminate*. A reviewer's first question will be: "What happens when two runbooks are both plausible? Does it pick the right one, or just the one with the highest cosine similarity to the surface wording?" Right now there's no way to answer that with data.

**1.4 — No ground truth exists below the document level.**
The retrieval eval's ground truth is "which runbook is correct." There is no ground truth for "which specific root cause," "which evidence actually supports it," or "what the correct remediation is." Without that, you can't compute Top-1 RCA Accuracy, Evidence Quality, or Remediation Accuracy — the metrics that would actually demonstrate reasoning.

**Net effect:** the project currently has strong infrastructure (hybrid retrieval, graph context, multi-agent orchestration, observability) but no evidence that the infrastructure produces *better diagnoses*, only evidence that it produces *better document matches*. That gap is exactly what a Staff/Applied AI Engineer interviewer will probe first.

---

## 2. Recommended Dataset Design

### 2.1 New artifact, separate from the retrieval eval

Create `data/eval/rca_eval.jsonl` — an **incident-level RCA benchmark**, independent of `retrieval_eval.jsonl`. Do not modify or relabel the existing retrieval eval; it's doing its job correctly. This is a new, additional dataset that tests the next stage of the pipeline.

### 2.2 Incident schema

Each entry should contain:

```json
{
  "incident_id": "RCA-EVAL-014",
  "title": "Checkout latency increased 400% over the last 30 minutes",
  "service": "checkout-service",
  "severity": "high",
  "logs": "<multi-line, noisy, realistic log excerpt — see 2.3>",
  "deployment_history": [
    {"service": "payment-service", "version": "v2.14.3", "deployed_at": "13:55", "changelog": "refactored pricing calculation, added tax-lookup query"}
  ],
  "metrics_snapshot": {
    "checkout_p99_latency_ms": {"before": 220, "after": 1100},
    "payment_service_cache_miss_rate": {"before": 0.04, "after": 0.38},
    "postgres_connections_in_use": {"before": 60, "after": 180, "max": 200}
  },
  "candidate_causes": [
    {"id": "deploy_regression_tax_lookup", "label": "New tax-lookup query in v2.14.3 added extra DB round-trips per request", "is_correct": true},
    {"id": "redis_cache_exhaustion", "label": "Redis cache evicting keys, causing DB fallback", "is_correct": false, "why_plausible": "cache miss rate jumped from 4% to 38%, the most visually dramatic number in the logs"},
    {"id": "postgres_pool_exhaustion", "label": "Postgres connection pool nearing limit, independent cause", "is_correct": false, "why_plausible": "180/200 connections looks like the smoking gun, but it's downstream of the real cause"}
  ],
  "supporting_evidence_lines": [3, 4, 6],
  "distractor_evidence_lines": [5, 7],
  "expected_remediation": ["Roll back payment-service to v2.14.2", "Add index/cache key review for tax-lookup query before redeploying"],
  "difficulty_tier": 2,
  "required_reasoning_hops": 2,
  "category": "deploy_regression"
}
```

Field notes:
- `candidate_causes`: always include 2–3 entries, exactly one `is_correct: true`. The `why_plausible` field on wrong candidates documents *why a keyword/embedding matcher would be tempted to pick them* — this is what makes the dataset actually test discrimination.
- `supporting_evidence_lines` / `distractor_evidence_lines`: line-level grounding labels, used for the Evidence Quality and Hallucination Rate metrics (Section 3).
- `difficulty_tier`: 1 = mostly direct, mild noise. 2 = two competing plausible causes. 3 = multi-hop, requires the service dependency graph to connect symptom → upstream cause.
- `required_reasoning_hops`: 1 = the cause is stated in the same service's logs. 2+ = the cause lives in a different service than the one reporting symptoms (i.e., needs the Neo4j graph or causal inference across services).

### 2.3 Worked example of "noisy, realistic" logs (vs. the current clean style)

**Before (current style — answer-revealing):**
```
Title: Database connection pool exhausted
```

**After (target style — symptom-only, multi-source, with a red herring):**
```
14:02:11 WARN  checkout-service: upstream call to payment-service took 2300ms (expected <300ms)
14:02:14 WARN  checkout-service: upstream call to payment-service took 2800ms
14:03:02 ERROR payment-service: redis-cache GET timeout after 200ms
14:03:05 INFO  payment-service: cache miss rate 38% (baseline 4%)
14:03:40 WARN  postgres-primary: connections in use 180/200
14:04:01 INFO  api-gateway: deployed payment-service v2.14.3 at 13:55 (canary 10%->100%)
14:05:00 ERROR checkout-service: 12% of requests returning 504 Gateway Timeout
```
Title becomes: *"Checkout latency increased 400% over the last 30 minutes."* Nothing in the title names a cause. The cache-miss spike and the connection count are real, correlated signals — but they're downstream symptoms of the new deploy's query, not the root cause themselves. A system that just keyword/embedding-matches "redis" or "connections" against runbook titles will confidently pick the wrong distractor. A system that reasons about timing (deploy at 13:55, symptoms at 14:02) and causal direction (new query → more DB round-trips → both higher cache miss rate *and* higher connection hold time) gets it right.

### 2.4 Where the incidents come from (don't write 50 from scratch by hand)

You already have 227 real postmortems in `data/postmortems/`. Use them as raw material via a **"de-reveal" transform**:
1. For each postmortem, extract the "what happened" / "timeline" section (the symptom narrative as experienced in real time).
2. Strip or rewrite the explicit "root cause" sentence(s) — this is almost always a clearly identifiable paragraph ("The root cause was...", "This was caused by...").
3. Keep only what an on-call engineer would have seen in the first 10–15 minutes: alerts, log lines, metric deltas, recent deploys.
4. Hand-author 1–2 plausible *wrong* candidate causes per incident, grounded in something that actually appears in the symptom text (this is the part that can't be automated well — it requires understanding why a reasonable but wrong inference would be tempting).
5. Label ground truth from the postmortem's actual stated cause.

This gives you real-incident realism without needing 50 hand-written scenarios. Target: **30–50 incidents**, stratified roughly:
- 40% Tier 1 (sanity check — system should get these right)
- 40% Tier 2 (the actual test — competing plausible causes)
- 20% Tier 3 (multi-hop, requires the dependency graph)

Spread across categories: database, cache, deploy regression, third-party/network dependency, resource exhaustion (OOM/CPU), config/secrets, DNS/cert.

### Deliverables for this section
- `scripts/build_rca_eval.py` — semi-automated extraction tool from postmortems (does steps 1–3; you do step 4 by hand for each).
- `data/eval/rca_eval.jsonl` — final 30–50 labeled incidents.
- `data/eval/README.md` — documents the schema, the de-reveal methodology, and the tier/category breakdown (this file alone is a credibility asset for recruiters who skim repos).

---

## 3. Recommended Evaluation Design

### 3.1 Ground truth labels (recap, tied to metrics below)
Per incident: `candidate_causes` (with `is_correct` flags), `supporting_evidence_lines`, `distractor_evidence_lines`, `expected_remediation`, `difficulty_tier`, `required_reasoning_hops`.

### 3.2 Metrics and how to compute each

| Metric | Definition | Computation |
|---|---|---|
| **Top-1 RCA Accuracy** | % of incidents where the model's #1 ranked hypothesis matches `is_correct: true` | Exact match against `candidate_causes[].id`, or semantic-equivalence match via judge (see 3.3) if the model's free-text phrasing doesn't line up 1:1 with the label id |
| **Top-3 RCA Accuracy** | % where the correct cause appears anywhere in the model's top 3 hypotheses | Same matching logic, checked against all returned hypotheses, not just rank 1 |
| **Root Cause Ranking Quality** | How well the *ranking* reflects correctness, not just hit/miss | Mean Reciprocal Rank (`1/rank of correct cause`, 0 if absent) across the eval set |
| **Remediation Accuracy** | % where suggested remediation steps match the canonical fix for the true cause | Judge-scored: does the remediation list contain the key action(s) in `expected_remediation`? (e.g., "rollback," "scale connection pool," "clear cache key" — action-level match, not exact string) |
| **Evidence Quality** | Precision/recall of cited evidence against the line-level labels | `precision = correctly-cited supporting lines / all lines cited`; `recall = correctly-cited supporting lines / all supporting_evidence_lines`. Citing a `distractor_evidence_line` as if it supports the *correct* cause is a precision miss even if the final answer happens to be right |
| **Hallucination Rate** | % of cited evidence that cannot be found (verbatim or close paraphrase) in the actual input logs/retrieved docs | Automated grounding check: for each citation in the RCA output, string/fuzzy-match it against the source logs and retrieved runbook text. Anything unmatched is a hallucinated citation |
| **Confidence Calibration** | Does a stated 90% confidence mean it's right ~90% of the time? | Bucket the model's confidence scores (0–100) into bins (e.g., 0–20, 20–40, ...), compute empirical accuracy per bin, report as a reliability diagram + Expected Calibration Error (ECE) or Brier score |
| **Cost per Investigation** | Average $ spent per incident across triage + RCA + remediation LLM calls | Pull from existing Langfuse traces — sum token cost across the 3 LLM-calling agents per incident, average over the eval set |
| **Latency per Investigation** | End-to-end wall-clock time | p50 and p95 across the eval set, from pipeline start to completion timestamp (already logged in Postgres) |

### 3.3 Why you need a judge, and how to keep it defensible

Free-text RCA output won't always say "deploy_regression_tax_lookup" verbatim — it'll say something like "the new tax calculation query introduced in the latest deploy is causing extra database round trips." You need a semantic equivalence check, not exact string match.

Recommended approach: use a separate LLM call (e.g., GPT-4o-mini or Claude Haiku, *not* the same model doing the RCA) as a judge, given the model's hypothesis text + the candidate cause labels, asked to pick which `candidate_causes[].id` (if any) the hypothesis matches. To make this defensible rather than hand-wavy:
- Publish the judge prompt in the repo (`scripts/judge_prompt.md`).
- Manually review judge decisions on a 20% sample, report **judge–human agreement rate** (e.g., "judge agreed with manual labeling on 27/30 sampled cases, 90%"). This single number is what makes the eval credible — an unaudited LLM-judge is just as hand-wavy as no eval at all.

### Deliverables for this section
- `scripts/run_rca_eval.py` — runs the full pipeline against `rca_eval.jsonl`, computes all metrics above, writes results to `data/eval/rca_eval_results.json`.
- `scripts/judge.py` + `scripts/judge_prompt.md` — equivalence judge, with logging of every judge decision for auditability.
- `docs/evaluation.md` — human-readable writeup of methodology + results (see Section 5).

---

## 4. Baseline Comparisons

Run all baselines against the **same** `rca_eval.jsonl` set. Same incidents, same order, fixed model versions and temperature (e.g., temperature=0 or report mean over 3 runs to control for LLM nondeterminism — LLMs are not deterministic at temp>0, so single-run numbers are not credible on their own).

| Baseline | Components | What it tests | Expected strengths | Expected weaknesses | Metrics to measure |
|---|---|---|---|---|---|
| **A — GPT-only** | Incident text → LLM → RCA, no retrieval, no graph, no triage/remediation split | Parametric knowledge alone — can a general LLM diagnose this from raw text? | Fast, cheap, surprisingly decent on Tier 1 (common patterns it's seen in training) | No grounding in your specific runbooks; can't cite real evidence; likely worse on Tier 2/3 where domain-specific dependency knowledge matters | Top-1/Top-3 Accuracy, Hallucination Rate (likely highest here) |
| **B — RAG-only** | Incident → single-pass vector retrieval → LLM | Does naive retrieval-augmentation help at all? | Should beat A on Evidence Quality (something real to cite) | No reranking, no keyword precision, no graph — likely struggles on Tier 2 ambiguous cases where the *wrong* runbook is also semantically close | Top-1/Top-3 Accuracy, Evidence Quality |
| **C — Hybrid Retrieval** | Incident → BM25 + Vector + RRF + Cohere rerank → LLM | Does the hybrid stack (already proven on retrieval_eval.jsonl) translate into better diagnosis, not just better document-matching? | Should beat B on Evidence Quality and Top-1 Accuracy on Tier 1/2 | Still no graph — Tier 3 multi-hop cases should remain weak | Same as B + compare delta vs B isolates hybrid retrieval's marginal value |
| **D — Graph-RAG** | C + Neo4j service dependency graph in the RCA prompt | Does causal/topology context actually help on multi-hop incidents? | Should show the biggest jump specifically on Tier 3 (`required_reasoning_hops >= 2`) incidents — segment results by tier to show this | Should show little to no improvement on Tier 1 (nothing to add there) — that's expected and fine, report it honestly | Top-1/Top-3 Accuracy **segmented by tier**, Ranking Quality |
| **E — Full RootCause System** | D + multi-agent split (Triage → Retrieval → RCA → Remediation) | Does the full architecture (signal extraction via triage, separated remediation reasoning) add value over a single monolithic call doing everything? | Should show improvement on Remediation Accuracy specifically (dedicated agent vs. one model doing diagnosis+fix in one shot), and possibly better Evidence Quality (triage cleans noisy logs before retrieval) | Highest cost/latency — must be reported alongside accuracy gains, not hidden | All metrics, plus Cost and Latency per Investigation |

**Fair experiment design notes:**
- Fix the underlying LLM where possible (e.g., use claude-haiku for the RCA step in every baseline) so you're isolating *architecture*, not *model choice*. If you want to also test model choice, that's a separate, clearly labeled ablation.
- Run each baseline 3x and report mean ± std for Top-1 Accuracy — single runs of stochastic LLM outputs are not a credible number.
- Randomize incident presentation order per run to avoid any positional bias in batch processing.
- Report results **segmented by difficulty tier**, not just aggregated. An aggregate "92% accuracy" hides the fact that all the gains might be coming from easy Tier 1 cases — segmentation is what proves the system handles the hard cases the critique is about.

### Deliverable for this section
- `scripts/run_baselines.py` — runs A through E against `rca_eval.jsonl`, outputs a single comparison table (markdown + JSON) segmented by tier, ready to paste into `docs/evaluation.md`.

---

## 5. What to Say If Questioned (Defensibility)

Map each likely interviewer question directly to the specific evidence above:

| Question | Answer, backed by data |
|---|---|
| "Is it actually reasoning, or just keyword matching?" | "On the retrieval benchmark, hybrid retrieval gets 96% Recall@1 — that's keyword+embedding matching, and I'm explicit about that. On the separate RCA benchmark, where incidents have 2–3 competing plausible causes and the title never names the answer, Baseline E gets [X]% Top-1 accuracy vs Baseline A's [Y]% — the gap is the reasoning, not the retrieval." |
| "Does the dependency graph actually help, or is it decorative?" | "Segmented by difficulty tier: on Tier 3 incidents (root cause lives in a different service than the one showing symptoms), Baseline D beats Baseline C by [X] points on Top-1 accuracy. On Tier 1, the gap is ~0, which is expected — that's the control case proving the graph isn't just adding noise." |
| "Does hybrid retrieval add value beyond plain vector RAG?" | Cite the existing 84%→96% Recall@1 number for retrieval quality, *and* the Baseline B→C delta on the RCA benchmark for downstream diagnostic value — two different numbers, both reported, not conflated. |
| "Does the multi-agent split actually help, or is it architectural complexity for its own sake?" | "Baseline D vs E isolates exactly that. The improvement shows up specifically in Remediation Accuracy [X→Y] — a dedicated remediation agent, working from an already-completed diagnosis, produces more actionable fix steps than asking one model to diagnose and remediate in a single pass." Also be honest about the cost/latency tradeoff this introduces. |
| "How do you know the model isn't hallucinating evidence?" | "Hallucination Rate is computed automatically — every citation in the RCA output is checked against the actual input logs and retrieved docs. Current rate: [X]%. Failure cases are logged in `docs/evaluation.md` with examples." |
| "Isn't your eval set small?" | Be upfront: "30–50 incidents, stratified across 3 difficulty tiers and 6+ failure categories, derived from real postmortems. It's intentionally small and hand-curated rather than large and noisy, because each one has audited ground truth. I report this as a known limitation, not a hidden one." |

**What a credible evaluation section in the repo looks like:**
- `docs/evaluation.md` containing: methodology (how the dataset was built, the de-reveal process), the full baseline comparison table segmented by tier, 2–3 worked failure-case examples (including ones where the *full system* got it wrong — showing failure cases is a stronger credibility signal than only showing wins), the calibration reliability diagram, cost/latency table, and a clearly labeled "Limitations" subsection.
- Link this prominently from the README, right next to the existing retrieval evaluation table — framed explicitly as testing a different layer of the system ("Retrieval Evaluation tests document search; RCA Evaluation tests end-to-end diagnostic reasoning on ambiguous incidents").

---

## 6. Highest Priority Next Steps (fastest credibility improvement first)

Ordered by leverage, not by how "complete" each step feels:

1. **Build `rca_eval.jsonl` v0 — 15–20 incidents, hand-curated from postmortems.** This single artifact directly answers the critic's specific complaint. Even a small set with honest, imperfect results is far more credible than a polished demo with no ambiguity testing at all.
2. **Run Baseline A vs Baseline E only** (skip B/C/D for now) against that v0 set. This is the single highest-leverage comparison — it directly shows "does the whole system add value over a bare LLM call," which is the first thing any reviewer will ask.
3. **Add the Hallucination Rate / evidence grounding check.** Cheap to build (string/fuzzy match citations against source text), and it's the second thing technical reviewers probe after "is this just keyword matching."
4. **Write `docs/evaluation.md`** documenting the above three, transparently, including at least one failure case. Link it from the README next to the existing retrieval table.
5. **(Stretch, after the above lands)** Fill out the full A–E baseline matrix, add Confidence Calibration and Cost/Latency, expand the eval set to 30–50 incidents with full tier stratification.

Steps 1–4 are achievable in a single focused session and directly neutralize the specific critique you received. Step 5 turns "neutralized critique" into "this person clearly knows how to evaluate AI systems rigorously" — which is the stronger hiring signal, but it's the polish layer, not the fix.
