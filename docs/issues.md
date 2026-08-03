# Issues Inventory

> Everything known to be wrong or fragile, with stable IDs so specs and commits can
> reference them (e.g. "fixes SEC-4"). Severity: 🔴 critical · 🟠 high · 🟡 medium · ⚪ low.
> File references point at the current code.

## Security

| ID | Sev | Issue |
|---|---|---|
| SEC-1 | 🔴→🟡 | **Secrets were hard-coded in `Dockerfile`** (DB credentials, JWT secret) until 2026-08. *Status:* image cleaned, secrets live only in gitignored env files + Cloud Run env vars ([secrets.md](secrets.md)); GCP build-artifact purge pending first clean deploy. Credential lifecycle details are managed privately, outside this repo. |
| SEC-2 | 🔴 | **Cloud SQL hardening needed**: public-IP + password auth with an over-privileged role and a permissive network allowlist. → Restrict authorized networks (a static worker IP arrives with spec-008), move the app to a dedicated non-superuser role and database, or adopt connector/IAM auth. |
| SEC-3 | 🟠 | **Public MQTT broker without auth or TLS** (`broker.hivemq.com`). Anyone who guesses the topic names can inject fake passages or watch live occupancy + device internals (local IP, RSSI). Mitigations: private broker or authenticated TLS broker, payload signing, or device→HTTPS ingestion (see roadmap appendix). |
| SEC-4 | 🟠 | **Unauthenticated endpoints in prod**: all `/test-data/*` including `POST /test-data/test/<date>` (writes rows), and `GET /data-tracker/tracker/<topic>`. → Require auth everywhere or delete the obsolete endpoints ([app/apis/testdata.py](../app/apis/testdata.py), [app/apis/data_tracker.py:122](../app/apis/data_tracker.py)). |
| SEC-5 | 🟠 | **`@require_auth` used without parentheses** on `GET /data-tracker/tracker` ([app/apis/data_tracker.py:37](../app/apis/data_tracker.py)) — the function becomes the `roles` argument, so the endpoint doesn't verify tokens (and returns garbage). The decorator's dual usage is a foot-gun; make it work both ways or enforce one form. |
| SEC-6 | 🟡 | `CORS(app)` allows every origin on every route. Restrict to the frontend origins. |
| SEC-7 | 🟡 | JWT verification gaps: no issuer check, `role` claim is Supabase's DB role (`authenticated`) so the decorator's `roles` param can't express app permissions; no room-level authorization exists at all (spec-003). Supabase is also migrating projects to asymmetric JWKS signing — verify which mode the project uses before touching auth. |

## Bugs

| ID | Sev | Issue |
|---|---|---|
| BUG-1 | 🟠 | `GET /data-tracker/tracker/<topic>` always 500s: `.filter_by()` is called on the executed `Result`, not the `Select` ([app/apis/data_tracker.py:124-131](../app/apis/data_tracker.py)). |
| BUG-2 | 🟠 | Weekly silent data loss: MQTT handler DB writes fail with `psycopg2.OperationalError: SSL SYSCALL error: EOF detected` (stale pooled connections; no `pool_pre_ping`/retry) and the passage is dropped. Part of the 301 observed counter gaps. |
| BUG-3 | 🟡 | `handle_default` swallows every exception with a `print`; no retry, no dead-letter, naive `replace("\n","")` sanitization ([app/mqtt/subscriber.py:28-33](../app/mqtt/subscriber.py)). |
| BUG-4 | 🟡 | `on_disconnect` has a wrong signature (missing `self`) and is never registered on the client, so disconnects are invisible ([app/mqtt/subscriber.py:44](../app/mqtt/subscriber.py)). |
| BUG-5 | 🟡 | [app/models/devices.py](../app/models/devices.py) is a copy-paste duplicate of the `Rooms` class (importing both would crash with a duplicate-table error). `Rooms` and `SinglePeopleCounter` were never migrated — models drifted from the real schema. |
| BUG-6 | 🟡 | Daily/monthly aggregates count **all** `data_tracker` topics, so config/query messages inflate passage counts (minor today: ~49 non-JSON rows lifetime). |
| BUG-7 | 🟡 | `app/apis/testdata.py` defines three classes all named `TestDataResource` (silent shadowing) and `data_by_hour` marshals a datetime with `fields.Date`. |
| BUG-8 | 🟡 | MQTT subscriber starts at import time: `alembic` migrations connect to the broker ([migrations/env.py:7](../migrations/env.py)), and >1 gunicorn workers would create duplicate subscribers (double-inserting every message). |
| BUG-9 | 🟡 | Frontend: `roomId` route param is never sent to the API; every room shows the library's data. Rooms on `HomePage` are mocked. |
| BUG-10 | ⚪ | Daily endpoint omits hours with zero passages; the frontend pads 07–19h client-side — inconsistent with the monthly endpoint (which zero-fills only in the obsolete testdata version). |
| BUG-11 | ⚪ | The device's `time_detected` is São Paulo local time mislabeled with `Z`; compensated by a double `func.timezone()` per query. Fragile — normalize at ingestion instead (spec-002). |

## Technical debt

| ID | Sev | Issue |
|---|---|---|
| DEBT-1 | 🟠 | Zero tests (backend, frontend, e2e) and no CI. Nothing can be changed safely. (spec-001) |
| DEBT-2 | 🟡 | Legacy SQLAlchemy `db.Column` declarative style; move to SQLAlchemy 2.0 typed `Mapped[]`/`mapped_column()` with `DeclarativeBase`, and current Flask-SQLAlchemy 3 patterns. (spec-001) |
| DEBT-3 | 🟡 | No app factory: Flask app, DB, CORS, API and the MQTT thread are all created at import of `app/__init__.py`; config is hard-wired to `DevelopmentConfig` even in prod; logging is `print()`. (spec-001) |
| DEBT-4 | 🟡 | Unpinned `requirements.txt`; frontend has pnpm as declared manager but `yarn.lock` committed and `package-lock.json` freshly deleted. Pick one (pnpm) and pin. |
| DEBT-5 | 🟡 | Heavy duplication: `testdata.py` vs `data_tracker.py` namespaces, `DailyCounterPage` vs `MonthlyCounterPage` (~90% identical). |
| DEBT-6 | 🟡 | Obsolete surface: `test_data` table (8 rows, Sept 2024), its endpoints, and the legacy test topic — remove after spec-002 lands. |
| DEBT-7 | ⚪ | Alembic revisions have empty messages; `env.py` imports the full app (side effects). |
| DEBT-8 | 🟠 | Repo hygiene: `Dockerfile` and `app/config.py` are untracked, so the GitHub backend repo can't build; frontend WIP uncommitted; stray folders (`projeto-biblioteca-nce-front` empty repo, `biblioteca-nce-frontend` legacy copy, admin-owned `front-projects/.git` causing dubious-ownership errors). |
| DEBT-9 | 🟡 | UX gaps: no logout button, no loading/empty/error states, mixed pt-BR/English copy, hard-coded chart colors. (spec-007) |

## Cost

| ID | Sev | Issue |
|---|---|---|
| COST-1 | 🟠 | `biblioteca-nce-back` runs min=1/max=1 with CPU always allocated purely to keep the MQTT thread alive — an always-on vCPU serving zero HTTP traffic. *Decision 2026-08-03:* fix via [spec-008](specs/spec-008-subscriber-vm.md) (subscriber → free-tier VM, Cloud Run scales to zero). |
| COST-2 | 🟡 | Cloud SQL Enterprise instance for a 26k-row dataset; console flags it "under-provisioned" (fleet advice). Right-size it, or consider consolidating storage into Supabase's Postgres (already in the stack) and dropping Cloud SQL entirely. |
