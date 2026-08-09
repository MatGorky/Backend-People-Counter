# Historical Backfill — Data Quality Report

Produced by `scripts/backfill_passages.py` against production on **2026-08-09**, migrating
the raw ingest log (Sept 2024 → Aug 2026) into `passage_event` (spec-002).

| Metric | Value | Meaning |
|---|---|---|
| Raw JSON-topic rows processed | 26,246 | every sensor message since 2024-09-23 |
| Passage events created | 25,876 | the clean, deduplicated passage history |
| Duplicate deliveries dropped | 370 | same device counter delivered twice (QoS/retained redeliveries) |
| Parse failures | **0** | both firmware payload eras parse cleanly |
| Unknown-device rows | 0 | single registered sensor for the whole period |
| Counter resets | 6 | device reboots/reflashes (counter "eras") |
| Gap incidents | 302 | windows where the server missed messages |
| **Estimated missed passages** | **3,924 (~13%)** | device-counter jumps across gaps — losses of the old always-on-subscriber design (service restarts, weekly stale-connection drops), quantified via the device's own cumulative counter |
| Clock-skew fallbacks | 328 | events where the device clock diverged >30 min from server receipt; server time used |

Notes:

- Every event links to its raw message via `passage_event.raw_id` (UNIQUE) — the table
  can be dropped and rebuilt from the audit log at any time.
- The ~13% historical loss is not recoverable (the timestamps never reached the server)
  but is now measurable per era, which the TCC can report honestly. The new pipeline
  (dedicated worker + `pool_pre_ping` + retry) removes the loss mechanisms.
- The 370 duplicates and 302 gaps confirm, at full scale, the sampling analysis in
  [current-state.md](current-state.md) §6 that motivated the dedupe design.
