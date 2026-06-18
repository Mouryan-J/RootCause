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

## Key finding, fixed

The `RCAOutput` parsing bug in `rootcause/agents/rca.py` (raised on trailing JSON data, and on `contributing_factors` missing when generation hit `max_tokens=1024`) caused 100% of the misses in the 18-incident eval run above. **Fixed**: `max_tokens` raised 1024 → 2048 in both `rca.py` and `scripts/run_rca_eval.py`'s Baseline A (which independently hit the same bug); `RCAOutput.parse_string_fields` now uses `json.JSONDecoder().raw_decode()` instead of `json.loads()`, which parses the first valid JSON value and ignores trailing data instead of raising. Added a regression test (`test_rca_output_tolerates_trailing_data_after_json`) reproducing the exact failure mode found by the eval. All 18 unit tests pass; this was a pure code fix, no API calls made.

**Not yet re-verified against real APIs** — the fix is unit-tested but `scripts/run_rca_eval.py` hasn't been re-run since. Re-running (full or spot-check on the previously-failed incidents: RCA-EVAL-006, 010, 016, 017, 018) would confirm the fix actually resolves the eval misses and update `docs/evaluation.md` / the README's reported numbers, which currently describe the pre-fix run.

## Phase 2 — backlog, not started (deferred per spec doc §6 step 5)

- [ ] **Re-run `scripts/run_rca_eval.py`** (spot-check previously-failed incidents first, then full re-run) to verify the parsing fix actually improves accuracy, and update `docs/evaluation.md` + README with post-fix numbers
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

## Status as of last checkpoint

- Commit `e5b2586` — eval tooling + dataset + docs (Phase 1)
- Commit `6ead44f` — the parsing-bug fix
- Commit `9f5b772` — checkpoint notes
- All pushed to `origin/main`. Live backend (`https://rootcause-api.onrender.com/health`) confirmed healthy/responding post-deploy.
- **Spot-checked the fix against real APIs** on the 5 previously-failed incidents (`RCA-EVAL-006, 010, 016, 017, 018`) using `scripts/run_rca_eval.py <incident-ids>` (new: accepts incident IDs as CLI args, writes to `data/eval/rca_eval_results_spotcheck.json` instead of clobbering the full results file). Findings:
  - **Baseline E (production pipeline) went from 60% → 100%** on this subset on the first re-run. Real, substantial improvement.
  - **Not fully eliminated**: re-running 2 of those same incidents again, `RCA-EVAL-010` hit the identical `contributing_factors` truncation bug again — same code, same `max_tokens=2048`, different outcome. The model's output length varies call-to-call even at temperature=0; this tier-3 multi-hop incident sits right at the edge of the token budget. The fix reduces the failure rate, it does not guarantee zero failures.
  - **Confirmed the judge over-leniency issue is reproducible, not a one-off**: when RCA-EVAL-010 fell back again, the judge matched the same content-free fallback text to the correct cause on keyword overlap alone — identical to the first time this was spot-checked manually.
  - Bumped Baseline A's (bare-LLM comparison script only, not production) `max_tokens` 2048 → 3072 for a bit more headroom; still saw one truncation there too. Comparison-script robustness, not a production concern.
- `docs/evaluation.md` and the README's reported eval numbers (88.9%/88.9%, full 18-incident run) **still describe the pre-fix run** — not yet updated to a post-fix full re-run. The spot-check above is real evidence the fix helps, but isn't a full re-run with updated headline numbers.
- **Live app (literal production URL) not end-to-end tested by Claude.** `POST /incidents/analyze` requires a Bearer token (`API_SECRET_KEY`), which is set in Render's dashboard, not in the local `.env` — Claude doesn't have it. User opted to test the live demo themselves in a browser rather than share the key or test locally.

## How to resume

1. **If the production max_tokens truncation needs fully closing**: the residual risk is real but small (1 reproducible failure across ~7 incident-runs in spot-checks). Options: raise `max_tokens` further (try 3072 in `rca.py` itself, matching what was tried for the comparison baseline), or add a retry-on-truncation before falling back to the generic placeholder, or prompt the model to be more concise. Not done yet.
2. **Tighten the judge prompt** (`scripts/judge_prompt.md` + `scripts/judge.py`) to stop matching content-free/generic hypotheses on keyword overlap alone — now confirmed reproducible across 2 separate spot-checks on the same incident.
3. **Full 18-incident re-run** once 1-2 are addressed, to get real post-fix headline numbers for `docs/evaluation.md` and the README (currently describe the pre-fix run).
4. Then the rest of the Phase 2 backlog above (judge sampling/audit, baselines B-D, larger eval set, calibration/cost/latency).
