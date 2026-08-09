# Spec 002 — Passage Events: a real table for the real data

**Status:** ✅ implemented 2026-08-09 — schema + ingestion + backfill live in prod;
26,246 raw rows → 25,876 events, 0 parse failures (see
[data-quality-report.md](../data-quality-report.md)). v1 endpoints still serving until
retirement; `data_tracker` remains the raw audit log. · **Phase:** 3 · **Depends on:**
spec-001 (tests), spec-004 (local env) · **Fixes:** BUG-6/10/11, DEBT-6 · **Enables:** spec-003/005/006

## Context

During discovery the backend subscribed to ~10 topics and dumped every payload into
`data_tracker(topic, payload)` — and that raw table became the production data source for
the frontend. Verified reality (see current-state.md §6): 99.8% of rows are messages on
the device's JSON topic (name unlisted; env `MQTT_TOPIC_JSON`) where **one message = one
beam interruption**, with a
device-side cumulative `access_count`, duplicate deliveries (362 observed), gaps (301) and
counter resets (6). The device's `time_detected` is São Paulo local time mislabeled `Z`.

## Goals

1. A first-class `passage_event` table as the single source of truth for all
   visualizations and reports.
2. Ingestion that parses the JSON topic, normalizes time to true UTC, dedupes
   deliveries, and never silently drops a message.
3. Backfill of all 25,970 historical events (idempotent, with a data-quality report).
4. API v2 serving aggregates from `passage_event`, with the ÷2 "visits" rule owned by the
   backend, zero-filled buckets, and room scoping (interface defined here, enforcement in
   spec-003).
5. `data_tracker` demoted to raw ingest log (kept for audit/debug).

## Non-goals

Auth/authorization changes (spec-003); removing raw logging; firmware changes.

## Design

### Schema (alembic migration, SQLAlchemy 2.0 models)

```
passage_event
  id            bigint identity PK
  device_id     text NOT NULL                  -- the sensor's device_id (unlisted)
  room_id       int  NULL FK→room.id           -- resolved via device table (spec-003); nullable until then
  occurred_at   timestamptz NOT NULL           -- true UTC (see time normalization)
  received_at   timestamptz NOT NULL           -- server receipt time
  access_count  bigint NULL                    -- device cumulative counter (gap/dup detection)
  people_count  bigint NULL                    -- device-computed floor(access/2)
  status_sensor text NULL
  rssi          int  NULL
  ip_address    inet NULL
  pulse_ton     int  NULL                      -- absent in 2024-era payloads
  pulse_toff    int  NULL
  raw_id        bigint NULL FK→data_tracker.id -- provenance link
  created_at    timestamptz NOT NULL DEFAULT now()

  INDEX (room_id, occurred_at)
  INDEX (device_id, occurred_at)
```

All timestamps `timestamptz`, stored UTC. Aggregation queries convert with a single
`AT TIME ZONE` using the room's timezone (spec-003 adds `room.timezone`, default
`America/Sao_Paulo`) — the double-`func.timezone` hack dies.

### Time normalization (BUG-11)

`occurred_at` = `time_detected` parsed as **America/São_Paulo local** (strip the fake
`Z`), converted to UTC. Fallback when absent/unparseable: `received_at`. Sanity guard: if
|occurred_at − received_at| > 30 min, trust `received_at` and flag the row (protects
against device clock drift/resets; today's observed skew is seconds).

### Ingestion (subscriber)

- The JSON topic (`MQTT_TOPIC_JSON`) → parse → insert raw `data_tracker` row (unchanged, audit) →
  insert `passage_event` with `raw_id`.
- **Dedupe rule:** drop (as passage) a message whose `(device_id, access_count)` equals
  the previous accepted event for that device unless the counter obviously reset
  (`access_count` < previous). Matches the 362 observed duplicate deliveries.
- Parse failure → raw row still written + WARNING log; never an unhandled exception.
- DB retry: one reconnect-and-retry on `OperationalError` (with spec-001's
  `pool_pre_ping` this closes BUG-2's message loss).
- Other topics: raw log only, as today.

### Backfill (one-off script, run locally against prod after local rehearsal)

- Iterate the JSON topic's `data_tracker` rows in id order, apply the same
  parser/dedupe, `raw_id` link makes it idempotent (skip already-migrated).
- Output report: rows in, events out, duplicates dropped, parse failures, counter eras
  detected, estimated missed passages (sum of gap deltas per era) — numbers for the TCC.

### API v2 (new namespace, old endpoints kept until frontend cutover)

```
GET /api/v2/rooms/<room_id>/passages/daily?date=YYYY-MM-DD    → 24 zero-filled hourly buckets + totals
GET /api/v2/rooms/<room_id>/passages/monthly?month=YYYY-MM    → per-day buckets + totals
GET /api/v2/rooms/<room_id>/passages/range?start&end          → per-day buckets (feeds spec-005 reports)
GET /api/v2/rooms/<room_id>/passages/yearly?year=YYYY         → per-month buckets (spec-006)
```

Every response: `{"data": [...], "totals": {"passages": N, "visits": ceil(N/2)}}` —
the ÷2 rule moves out of the frontend (frontend then displays, never computes).

### Frontend cutover

`services/counter.ts` switches to v2 (with `roomId` finally in the path); remove client
÷2 and hour-padding; delete obsolete `test-data` usage. Old v1 endpoints + `test_data`
table/endpoints/topic removed one release later (DEBT-6).

## Work breakdown

1. Model + migration (locally rehearsed → prod).
2. Parser module + unit tests from recorded real payloads (both schema eras, dup, gap,
   reset, garbage cases).
3. Subscriber wiring + retry; local e2e with simulator (spec-004).
4. Backfill script + rehearsal on local copy → run on prod → commit report to docs/.
5. API v2 + service layer + tests.
6. Frontend switch + Playwright update.
7. Deploy sequence: backend (dual-write) → verify → backfill → frontend → retire v1.

## Acceptance criteria

- Every new JSON-topic message produces exactly one `passage_event` (duplicates
  excluded), with `occurred_at` in true UTC, verified by an integration test replaying a
  recorded real-world sequence (incl. a duplicate and a reset).
- Backfilled totals per historical day match v1 daily counts minus known non-JSON topics
  (BUG-6 delta documented in the backfill report).
- Frontend daily/monthly views show identical numbers before/after cutover (± the BUG-6
  correction) — Playwright asserts against the seeded local stack.
- `raw_id` lets any event be traced to its original payload.

## Open questions

- Retention for raw `data_tracker` (keep forever vs prune > 12–24 months)?
- Also expose passage-level listing (`GET .../passages?start&end` raw events) for the
  report appendix, or aggregates only?
