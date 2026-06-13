# ADR 004 — Dataset Strategy

## Decision
Hybrid corpus: hand-written synthetic runbooks + real postmortems 
scraped from danluu/post-mortems.

## Why
No single public dataset provides runbooks + root causes + 
ground-truth labels together. Synthetic runbooks give us:
- Perfect quality control
- Ground-truth labels for evaluation (we wrote them)
- Coverage of the exact failure types we target

Real postmortems (danluu/post-mortems, 11k+ stars on GitHub) add 
authentic language and real company incident patterns.
