# VoiceScope — Deferred Work

Written by the CEO review (2026-08-19). Each item is a real gap, not a vague intention.

## P1 — Product gaps

- [ ] **Real-time / live call monitoring.** VoiceScope is post-call only today. Competitors (VoiceObs) offer live latency breakdown and streaming word monitoring. Large lift (streaming audio + partial-transcript harness). Deferred from the CEO review as a follow-on bet, not part of the current scope.
- [ ] **Doc drift on layer count.** `README.md` says "8 deterministic checks", `BACKEND.md` says "7-layer harness", and `core/harness.py` docstring says "7-layer". The weights dict actually has 8 keys (`schema`, `citations`, `cross_check`, `facts`, `sentiment_consistency`, `outcome_evidence`, `escalation`, `duplicate`). Reconcile all three to one number.
- [ ] **Weak fact layer.** The harness benchmark shows `avg_fact_accuracy` at ~41% and `outcome_evidence` as the weakest layer. `core/facts.py` uses deterministic extraction; consider adding a labeled fact-contradiction eval set and tightening the extractor.

## P2 — Demo limitations (also documented in README)

- [ ] **In-memory rate limiting.** Per-process state, lost on restart. Move to Redis/Postgres for multi-instance deploys.
- [ ] **In-memory batch storage.** Batch state is a Python dict. Persist to a database.
- [ ] **Extraction heuristics.** `core/extractions.py` uses keyword/regex, not LLM. Replace with LLM calls for nuanced fields.
- [ ] **Settings provider UI is display-only.** Keys are configured in `.env`, the Settings "Providers" tab is informational.

## P3 — Nice-to-have

- [ ] **Alert rule dedup.** `check_alerts` inserts an incident row every evaluation; repeated triggers on an already-active rule can spam `alert_incidents`.
- [ ] **Benchmark artifact promotion.** Surface `scripts/run_benchmark.py` output as a committed `benchmark_result.json` on CI so the README badge can be dynamic rather than hand-edited.
