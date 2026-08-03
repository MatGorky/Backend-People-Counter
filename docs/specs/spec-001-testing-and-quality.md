# Spec 001 — Testing & Code Quality Baseline

**Status:** draft · **Phase:** 2 · **Depends on:** spec-004 (local env) · **Fixes:** DEBT-1/2/3/4/5/7, BUG-1/5/7, SEC-5

## Context

There are zero tests in either repo, no CI, and the backend has import-time side effects
(app, DB, CORS and the MQTT thread are built when `app/__init__.py` is imported) that make
it untestable as-is. Models use pre-2.0 SQLAlchemy `db.Column` style. The user's explicit
priority: unit tests, Playwright e2e, Storybook, good architecture, up-to-date SQLAlchemy.

## Goals

1. Backend restructured so every piece is testable in isolation (app factory, no import
   side effects, env-driven config).
2. SQLAlchemy 2.0 typed models (`DeclarativeBase`, `Mapped[]`, `mapped_column()`).
3. pytest suite covering models, services, API endpoints, auth, and MQTT handlers.
4. Frontend: Vitest + React Testing Library for units, Playwright for e2e, Storybook for
   components.
5. Lint/format + pinned dependencies + GitHub Actions CI on both repos.

## Non-goals

New features or schema changes (spec-002/003). This phase must preserve current behavior —
the tests written here are the safety net for the later refactors.

## Design

### Backend restructure

```
app/
  __init__.py          # create_app(config) factory ONLY; nothing at import time
  config.py            # BaseConfig / LocalConfig / ProductionConfig, all values from env
  extensions.py        # db = SQLAlchemy(metadata=naming_convention), cors, api
  models/              # SQLAlchemy 2.0 typed models; delete dead devices.py duplicate,
                       # rooms.py / single_people_counter.py (recreated properly in spec-003)
  apis/                # thin Flask-RESTX resources; marshaling only
  services/            # query/aggregation logic extracted from resources (pure, testable)
  mqtt/subscriber.py   # constructed and started explicitly by the entrypoint, never at import
  utils/auth.py        # require_auth fixed to support both @require_auth and @require_auth()
wsgi.py                # prod entrypoint: create_app() + start subscriber (gunicorn target)
```

- `migrations/env.py` stops importing the app: build metadata from `app.extensions` +
  models module without triggering the factory/subscriber (fixes BUG-8's alembic side).
- Engine options: `pool_pre_ping=True`, `pool_recycle` — fixes the weekly stale-connection
  drops (BUG-2) at the infrastructure level; handler-level retry stays in spec-002.
- Logging: `logging` module instead of `print`, structured enough for Cloud Logging.
- Dependencies: `requirements.txt` pinned (or `pyproject.toml` + pip-tools); Python 3.12.
- Lint/format: `ruff` (lint + format) with pre-commit hooks.

### Backend tests (pytest)

- **Fixtures:** `create_app(TestConfig)` + a real Postgres from the local compose stack
  (spec-004) — the queries use Postgres-only SQL (`generate_series`, `date_part`,
  `timezone`), so SQLite is not an option. Each test runs in a rolled-back transaction.
- **Unit:** services (aggregations with known seeded rows, timezone edges — the
  23:00/00:00 São Paulo boundary!), auth decorator (valid/expired/garbage tokens signed
  with a test secret, both decorator forms), MQTT handlers called directly with recorded
  real payloads (no broker needed), including the 2024 payload variant without
  `pulse_ton/pulse_toff`, duplicates, and malformed JSON.
- **API:** Flask test client against seeded DB: status codes, marshaled shapes, auth
  required on every endpoint (regression for SEC-4/5).
- **Characterization first:** before refactoring, pin current daily/monthly endpoint
  outputs for a seeded dataset, then refactor until green.

### Frontend tests

- **Vitest + React Testing Library:** `utils/datetime`, services (axios mocked),
  `LoginForm` (error/loading states), chart pages with mocked service layer (hour padding
  logic, ÷2 totals — until spec-002 moves it to the API).
- **Storybook 8+ (vite builder):** stories for LoginForm, chart cards, page states
  (loading/empty/error/data) — becomes the workbench for spec-007.
- **Playwright e2e:** runs against the full local stack (spec-004: local DB seeded, local
  API, Vite dev server; Supabase cloud with a dedicated test user, credentials in
  `.env.test`). Flows: login → redirect; wrong password → error; daily chart renders
  seeded data; date navigation; monthly view; logout (once it exists). CI-friendly
  (headless, trace on failure).

### CI (GitHub Actions, both repos)

- Backend: ruff + pytest (services Postgres container).
- Frontend: eslint + vitest + build + Storybook build; Playwright job spins the compose
  stack (or is a manually-triggered workflow if runtime is a concern).

## Work breakdown

1. Pin deps, add ruff, commit untracked `Dockerfile`/`config.py` cleanup (with Phase 0 done).
2. Characterization tests for the two endpoints the frontend uses.
3. App factory + extensions split + wsgi entrypoint; fix `require_auth` both-forms; fix BUG-1.
4. SQLAlchemy 2.0 model rewrite (`TestData`, `DataTracker`); delete dead models.
5. Services extraction; pytest suite to target coverage (aim: services/apis ≥ 90%).
6. Frontend: settle pnpm (DEBT-4), Vitest + RTL suite, Storybook setup + first stories.
7. Playwright + `.env.test` + docs; GitHub Actions on both repos.

## Acceptance criteria

- `pytest` green locally and in CI; endpoint behavior identical to pre-refactor
  (characterization tests prove it).
- `alembic upgrade` no longer opens an MQTT connection.
- 2 gunicorn workers would NOT double-subscribe (subscriber lives in one explicit place).
- `pnpm test`, `pnpm build`, `pnpm storybook` and `pnpm exec playwright test` all green.
- CI badge on both READMEs.

## Open questions

- Coverage gate in CI (fail under X%) — pick a number or skip the gate?
- Playwright in CI on every PR vs manual trigger (compose spin-up time)?
