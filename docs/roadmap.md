# Roadmap

> How we get from [current-state.md](current-state.md) to a system with tests, a real
> data model, multi-room support, reports, and a decent UI — without a dev environment
> (everything is verified locally before any deploy) and without breaking 22 months of
> continuously collected data.

## Documents

| Doc | Covers |
|---|---|
| [current-state.md](current-state.md) | Verified system snapshot (2026-08-03) |
| [issues.md](issues.md) | All known problems with stable IDs (SEC-x / BUG-x / DEBT-x / COST-x) |
| [specs/spec-001-testing-and-quality.md](specs/spec-001-testing-and-quality.md) | Tests (unit, e2e), Storybook, architecture & SQLAlchemy 2.0 refactor |
| [specs/spec-002-passage-events.md](specs/spec-002-passage-events.md) | Proper `passage_event` table replacing raw `data_tracker` as the source of truth |
| [specs/spec-003-rooms-and-access.md](specs/spec-003-rooms-and-access.md) | Rooms, devices, user↔room access, real auth workflow |
| [specs/spec-004-local-dev-env.md](specs/spec-004-local-dev-env.md) | Local Postgres + MQTT broker + sensor simulator; test-before-deploy workflow |
| [specs/spec-005-pdf-reports.md](specs/spec-005-pdf-reports.md) | User-friendly PDF report with date-interval filters |
| [specs/spec-006-annual-visualization.md](specs/spec-006-annual-visualization.md) | Annual view (per-month + heatmap) |
| [specs/spec-007-design-improvements.md](specs/spec-007-design-improvements.md) | App shell, states, theming, pt-BR consistency |

## Constraints

1. **No cloud dev environment** (cost) — everything is verified locally before deploy
   (spec-004).
2. **No vendor lock-in** — the stated end-state is running on university (NCE) infra.
   Application code uses platform-neutral primitives only: env-var config (plain env
   vars, deliberately **not** GCP Secret Manager), vanilla Postgres, MQTT, Docker.
   GCP-specific bits live only in deploy commands/scripts, never in the app.

## Phases

Order matters: each phase makes the next one safe(r). Specs can still be read/refined in
any order.

### Phase 0 — Security & hygiene hotfix (do first, small, independent)
Fixes: SEC-1 (mitigated), SEC-2, SEC-4, SEC-5, SEC-6, DEBT-8.
1. ✅ Credential hygiene: secrets removed from image and repo; lifecycle decisions are
   tracked privately, outside this public repo ([secrets.md](secrets.md)).
2. ✅ Secrets out of `Dockerfile`; deploys use `--env-vars-file deploy/prod.env.yaml`
   (gitignored) — scheme documented in [secrets.md](secrets.md).
3. Redeploy once with the clean Dockerfile, then run the artifact-purge checklist in
   [secrets.md](secrets.md) (old source tarballs, build logs, images still contain the secrets).
4. Lock down / delete unauthenticated endpoints (`/test-data/*` POST included, `/data-tracker/tracker*`).
5. Commit `app/config.py` (topics only — it holds no secrets) and the cleaned `Dockerfile`; push so the GitHub repo actually builds.
6. Tidy stray folders (delete empty `projeto-biblioteca-nce-front`, archive legacy `biblioteca-nce-frontend`).

*Gate: one careful redeploy of the backend (config-level change, verified with a local container run first).*

### Phase 1 — Local development environment (spec-004)
Prerequisite for every other phase: docker-compose Postgres + Mosquitto, a sensor
simulator replaying real payloads, seed scripts, `.env`-driven config. From here on,
**nothing is deployed that wasn't run locally first.**

### Phase 2 — Quality baseline (spec-001)
App factory refactor, SQLAlchemy 2.0 models, pinned deps, pytest suite, Vitest, Playwright
e2e against the local stack, Storybook, ruff/eslint, GitHub Actions CI. Ends with the
existing behavior covered by tests — the safety net for Phase 3.

### Phase 2.5 — Subscriber to free-tier VM (spec-008) — ✅ **done 2026-08-08**
MQTT worker runs on an Always-Free `e2-micro` in us-central1; Cloud Run scales to zero
(kills COST-1, ~US$40–45/mo). Verified end-to-end incl. reboot recovery and
single-delivery while the web service was scaled to zero. SEC-2 network tightening
deferred to a follow-up (needs the Cloud Run↔DB connector decision, see spec-008).

### Phase 3 — Real data model (spec-002, then spec-003)
`passage_event` table + parser + dedupe + backfill of the 25,970 historical events;
rooms/devices/user-access schema and authorization; new room-scoped API; frontend
switches over; `data_tracker` demoted to raw ingest log.

### Phase 4 — Features (spec-005, spec-006) — ✅ **done 2026-08-10**
PDF reports with date-interval filters (reportlab; deviation noted in spec-005) and the
annual visualization (monthly bars + calendar heatmap + year-over-year delta). Bonus
fix: deep links no longer bounce through /login during session restore.

### Phase 5 — Design (spec-007)
App shell, navigation, states, theming — developed against Storybook, verified with
Playwright.

## Decision points (need your call, none block Phase 0/1)

1. **Visits = passages ÷ 2** — confirm this stays the official rule (firmware already
   computes `people_count` the same way). Spec-002 moves it to the backend.
2. ~~**Cost** (COST-1)~~ — **decided 2026-08-03: appendix option B** (subscriber → free
   `e2-micro` VM, Cloud Run scales to zero) → [spec-008](specs/spec-008-subscriber-vm.md),
   Phase 2.5. COST-2 (Cloud SQL right-sizing / option D) remains open for later.
3. **Admin model** (spec-003): who grants room access — a Supabase `app_metadata` role
   checked by the API (recommended, no extra UI) or an in-app admin panel?
4. **Raw log retention** (spec-002): keep writing raw `data_tracker` forever (recommended:
   yes, it's the audit trail; optionally prune >N months later) or stop after cutover?
5. **PDF contents** (spec-005): confirm KPIs/branding (NCE logo? pt-BR only?).
6. **Frontend package manager**: settle on pnpm and delete `yarn.lock`? (DEBT-4)

## Appendix — cost options for the always-on backend (COST-1)

The web API itself could scale to zero; only the MQTT subscription needs 24/7 presence.

| Option | Change | Effect |
|---|---|---|
| A. Status quo | none | ~1 vCPU always allocated + Cloud SQL, ~US$40–60/mo ballpark — check billing |
| **B. Split subscriber — CHOSEN → [spec-008](specs/spec-008-subscriber-vm.md)** | Move the MQTT subscriber to a free-tier `e2-micro` VM writing to the same DB; Cloud Run API scales to zero | Removes the always-on Cloud Run cost; adds a VM to manage; VM's static IP also lets us close SEC-2 |
| C. Device → HTTPS | Firmware posts JSON directly to the API (or Pub/Sub push) instead of public MQTT | Kills the always-on requirement **and** SEC-3; needs Arduino changes |
| D. Supabase Postgres | Move data into the existing Supabase project's Postgres, drop Cloud SQL | Removes Cloud SQL cost; DB and auth in one place; migration effort |
| E. University infra (stated end-state) | Run the whole stack via the spec-004 compose file on NCE servers | Kills all GCP cost; needs uni ops buy-in, HTTPS ingress, and an auth decision (cloud Supabase works from anywhere; swapping it is isolated behind `require_auth`) |

These are independent of the roadmap phases (the code changes in specs 001–007 are
compatible with any of them); B/C/D/E would each get their own mini-spec if chosen. The
portability constraint above exists precisely so that E stays cheap to execute.
