# Spec 004 — Local Development Environment

**Status:** draft · **Phase:** 1 (prerequisite for everything) · **Fixes:** enables the "test locally before any deploy" rule (no dev env in the cloud for cost reasons)

## Context

Today the only environment is production: no way to run the system locally, so every
change has been YOLO-deployed. There is no dev cloud environment on purpose (cost), so
local must be a faithful stand-in: Postgres, an MQTT broker, the backend, the frontend,
and a way to simulate the sensor.

## Design

```
docker-compose.yml (backend repo root)
  db:        postgres:16          port 5432, volume, POSTGRES_DB=people_counter
  mqtt:      eclipse-mosquitto:2  port 1883 (anonymous allowed locally)
  # backend and frontend run on the host (fast reload), containers optional later
```

- **Config via env only** (pairs with Phase 0): `.env.example` committed; real `.env`
  gitignored. Backend reads `SQLALCHEMY_DATABASE_URI`, `SUPABASE_JWT_SECRET`,
  `MQTT_BROKER_HOST/PORT`, `MQTT_TOPICS`. The broker host being configurable is what
  makes local Mosquitto possible (it's hard-coded to HiveMQ today).
- **Auth in local dev:** keep using the cloud Supabase project (free, zero setup) with
  dedicated test users; tests that need to mint tokens sign their own with the local
  test secret. Optional later: `supabase start` for full offline.
- **Schema:** `alembic upgrade head` against local DB (after spec-001 removes env.py side
  effects; until then a documented workaround).
- **Seed:** script generating realistic passage data (library-shaped: weekday peaks,
  07–19h) + a small committed sample of real anonymized payloads for parser tests.
- **Sensor simulator:** `scripts/simulate_sensor.py` — publishes JSON-topic payloads
  (topic from `MQTT_TOPIC_JSON`) to the local broker with realistic timing,
  `access_count` progression, and flags to inject duplicates / gaps / resets / garbage.
  This is the e2e workhorse.
- **Runner:** `Makefile` (works in Git Bash) or `justfile` with: `up`, `down`, `db-reset`,
  `seed`, `api`, `front`, `simulate`, `test`, `e2e`.
- **Portability:** this compose file is also the deployment blueprint for the planned
  future move onto university (NCE) infrastructure (roadmap Constraints / option E) —
  keep it free of GCP-specific pieces.
- **Windows note:** document Docker Desktop requirement; everything else is
  shell-agnostic.

### Workflow rule (goes in both READMEs + CLAUDE.md)

> Nothing is deployed unless it ran locally: unit tests green, stack up, simulator
> replayed, and the change verified in the local frontend. Prod deploys remain manual
> `gcloud run deploy` until CI exists (spec-001).

## Work breakdown

1. compose file + mosquitto config + `.env.example` both repos.
2. Make broker/host/topics configurable in backend config (small, safe change — can even
   precede Phase 2 refactor).
3. Seed + simulator scripts (+ committed sample payload fixtures).
4. Frontend `.env.local` pointing at `http://localhost:5000`; verify full loop:
   simulator → mosquitto → subscriber → Postgres → API → Vite frontend chart.
5. README quickstart (5 commands max) + runner targets.

## Acceptance criteria

- Fresh machine with Docker: `make up && make seed && make api` + `pnpm dev` shows the
  dashboard with local data in < 10 minutes.
- `make simulate` produces visible new passages in the local dashboard within seconds.
- No secret values required beyond the personal `.env` (and none of them prod secrets —
  local DB creds are local-only; Supabase test-user creds only for e2e).

## Open questions

- Containerize backend/frontend in compose too (parity) or keep host-run (speed)?
  Recommend host-run now, containers when CI needs them.
