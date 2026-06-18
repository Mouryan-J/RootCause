# RCA Evaluation Redesign — Progress Tracker

Tracks implementation of the RCA reasoning benchmark (response to the "inputs are too clean / answer-revealing" eval critique). Scope and rationale: see `rca-eval-redesign-plan.md` (full spec) — this session implements that spec's Section 6, steps 1–4 only.

## Phase 1 — COMPLETE

- [x] `data/eval/rca_eval.jsonl` — 18 hand-authored incidents, symptom-only, 2–3 candidate causes each with exactly one correct. 5 tier-1, 9 tier-2, 4 tier-3; 9 categories (database, deploy_regression, messaging, resource_exhaustion, cache, dns_cert, network_third_party, config, service_mesh). Deliberately omits a separate `metrics_snapshot`/`deployment_history` field — all signals live inside unstructured `logs` text only.
- [x] `scripts/build_rca_eval.py` — generates the JSONL (mirrors `scripts/build_eval.py` pattern), asserts exactly one correct cause + valid evidence-line indices per incident at write time
- [x] `scripts/judge_prompt.md` — equivalence-judge prompt, checked in for auditability
- [x] `scripts/judge.py` — LLM judge (gpt-4o-mini, different model than the RCA agent) matching free-text RCA hypothesis → `candidate_causes[].id`
- [x] `scripts/run_rca_eval.py` — Baseline A (bare claude-haiku call, no retrieval/graph/triage) vs Baseline E (full `run_analysis()` pipeline), Top-1/Top-3 accuracy + simple fuzzy-match hallucination rate, segmented by difficulty tier. Writes `data/eval/rca_eval_results.json`.
- [x] Ran `build_rca_eval.py` — 18/18 incidents validated cleanly
- [x] `uv run pytest tests/unit/ -v` — all 17 existing tests still pass, no regressions (no production agent code was touched)
- [x] **Ran `run_rca_eval.py` against real APIs.** Cost was small (estimated $0.20-1, user approved). First attempt crashed at the very end on a Windows console Unicode encoding bug *after* all LLM calls completed but *before* results were saved to disk — lost that run's data. Fixed (`sys.stdout.reconfigure(utf-8)`, write results to disk before any print formatting, ASCII-only separators) and re-ran cleanly.
- [x] `data/eval/rca_eval_results.json` — real results: **88.9% Top-1/Top-3 accuracy for both Baseline A (bare LLM) and Baseline E (full pipeline)**. Headline numbers tie, but investigation found every single miss in both baselines traces back to one root cause: a pre-existing `RCAOutput` parsing bug in `rootcause/agents/rca.py` (trailing-data JSON errors and `max_tokens=1024` truncation) that triggers a near-content-free fallback. Genuine reasoning (when parsing succeeds) got every incident right, including ambiguous tier-2/3 cases with distractors. Also found, via manual spot-check, one judge false-positive (over-matched a content-free fallback to the correct cause on keyword overlap alone).
- [x] `docs/evaluation.md` — methodology, results by tier, 2 positive worked examples of genuine discrimination under ambiguity, 3 failure-case writeups (parsing bug, fallback-cascades-to-wrong-distractor, judge over-leniency), honest Limitations section
- [x] README.md — added "RCA Reasoning Evaluation" section next to "Retrieval Evaluation", updated project structure block

## Key finding worth acting on next

The `RCAOutput` parsing bug in `rootcause/agents/rca.py` (raises on trailing JSON data, and on `contributing_factors` missing when generation hits `max_tokens=1024`) is the single highest-leverage fix discovered by this eval — it caused 100% of the misses in this 18-incident set. Not fixed in this pass (out of scope: this work was eval-tooling only, no production agent code touched). Worth a follow-up session: raise `max_tokens` for the RCA call and harden the lenient JSON-string parsing in `RCAOutput.parse_string_fields`.

## Phase 2 — backlog, not started (deferred per spec doc §6 step 5)

- [ ] Fix the `RCAOutput` parsing bug found above (arguably higher leverage than anything below)
- [ ] Tighten the judge prompt to require explicit mechanism-statement, not just topical/keyword overlap (found one false positive on manual spot-check)
- [ ] Baseline B (RAG-only, no rerank/graph)
- [ ] Baseline C (Hybrid retrieval, no graph)
- [ ] Baseline D (Graph-RAG, no multi-agent split)
- [ ] Evidence Quality precision/recall metric (line-level grounding)
- [ ] Confidence Calibration (reliability diagram + ECE/Brier score)
- [ ] Cost per investigation (pull from Langfuse traces)
- [ ] Latency p50/p95 per investigation
- [ ] 3x reruns per incident to control for LLM nondeterminism (report mean ± std)
- [ ] Expand eval set from 18 → 30–50 incidents with full tier stratification
- [ ] Sample 20% of judge decisions for manual review, report judge-human agreement rate (only 1 decision spot-checked so far)

## How to resume

Phase 1 is complete and committed-ready. To pick this up again, start with the "Key finding worth acting on next" above — fixing the RCA parsing bug and re-running `scripts/run_rca_eval.py` would likely raise both baselines' real accuracy and produce a more meaningful A-vs-E comparison than this run could, since both baselines hit the same bug independently. After that, work down the Phase 2 backlog in roughly the listed order (judge tightening is cheap and high-value; baselines B-D and the larger eval set are the expensive long-tail items).
