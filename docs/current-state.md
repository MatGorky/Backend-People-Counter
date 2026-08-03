# Current State — People Counter (Biblioteca NCE)

> Snapshot taken 2026-08-03. This document describes the system **as it was**, before the
> improvement work planned in [roadmap.md](roadmap.md). Facts here were verified against
> the production GCP project, the production database (read-only), and both repositories.
>
> **Update (same day, post-Phase-0):** the security hotfix already landed after this
> snapshot — `/test-data/*` endpoints deleted, auth fixed on all `/data-tracker` routes,
> CORS restricted, secrets and MQTT topic names moved out of the image/repo into
> gitignored env files ([secrets.md](secrets.md)). §2/§5/§8 describe the pre-Phase-0
> state. Identifying details (addresses, topic names) are deliberately not listed in
> this public document.

## 1. What the system is

A people counter for the NCE library (TCC project). A retro-reflective IR sensor at the
library entrance (ESP-based, Arduino IDE firmware — not in these repos) publishes an MQTT
message on a public broker every time the beam is interrupted. A Flask backend subscribed
to those topics stores every message in Postgres. A React frontend, authenticated via
Supabase, shows daily and monthly passage charts.

```
IR sensor (library network)
   │  MQTT publish (JSON topic — name unlisted, QoS 0, no auth/TLS)
   ▼
broker.hivemq.com (PUBLIC broker)
   │  subscribe
   ▼
Cloud Run: biblioteca-nce-back  ──────────► Cloud SQL: biblioteca-nce (Postgres 16)
   Flask + Flask-RESTX + paho-mqtt               table data_tracker (raw payloads)
   gunicorn 1 worker / 8 threads
   min=1, max=1, CPU always on  ◄────────── REST (JWT Bearer)
                                                 │
Cloud Run: biblioteca-nce-front (nginx + Vite build, scale-to-zero)
   React 19 + MUI 6 + Recharts
   Supabase JS (auth only) ──► Supabase project vwbhomickkuhdheiqqoy (auth + JWT)
```

## 2. Repositories and folders

| What | Path | Remote | State |
|---|---|---|---|
| Backend (this repo) | `C:\Users\gorku\Backend-People-Counter` | github.com/MatGorky/Backend-People-Counter | `Dockerfile` and `app/config.py` are **untracked** — the GitHub copy cannot run as-is |
| Frontend (active) | `C:\Users\gorku\front-projects\biblioteca-nce-front` | github.com/MatGorky/Frontend-People-Counter | Uncommitted WIP: rooms routing, monthly page, lockfile churn |
| Frontend (legacy) | `C:\Users\gorku\front-projects\biblioteca-nce-frontend` | — | First iteration, Nov 2024. Superseded; candidate for deletion |
| Empty repo | `C:\Users\gorku\projeto-biblioteca-nce-front` | — | `git init`-ed, zero commits, zero files. Candidate for deletion |

Also: `C:\Users\gorku\front-projects\.git` is an unrelated admin-owned repo wrapping the
folder, which triggers git "dubious ownership" errors inside it.

## 3. Production infrastructure (GCP project `matgorky`, us-central1)

| Resource | Name | Key config |
|---|---|---|
| Cloud Run (API + MQTT) | `biblioteca-nce-back` | minScale=1, maxScale=1, **CPU always allocated**, 1 vCPU / 512Mi, concurrency=1 |
| Cloud Run (static front) | `biblioteca-nce-front` | scale-to-zero, maxScale=40 |
| Cloud SQL | `biblioteca-nce` | Postgres 16 Enterprise, public IP (address unlisted here), console flags it "under-provisioned" |
| Supabase | `vwbhomickkuhdheiqqoy` | Auth only (email+password); backend verifies the JWT with the shared HS256 secret |

Notes:

- The backend must be always-on **only** because the MQTT subscriber lives inside the web
  process. This is the main cost driver (~1 vCPU allocated 24/7).
- The Cloud SQL Admin API is disabled in the project (instance runs fine; `gcloud sql`
  commands don't work).
- Deploys are done manually with `gcloud run deploy` from local source (no CI/CD).
- Database access is password-based over a public IP; tightening the network allowlist
  and moving to a dedicated app role is tracked as SEC-2 (lands with spec-008). Secrets
  handling: [secrets.md](secrets.md).

## 4. Usage assessment (as of 2026-08-03)

**Question: is anyone using this?**

Measurement limits first (verified empirically): request **logs** are kept 30 days
(`_Default` bucket; the 400-day locked bucket is `_Required` = admin audit only), and
Cloud Run **metrics** in this project are queryable back to ~2026-06-03 only (~2 months —
established by finding the oldest surviving `billable_instance_time` point of the
always-on backend, which by definition has existed every day). Both pipelines were
validated by generating a probe request and observing it appear in metrics and logs.
**Nothing can be proven about traffic before ~June 2026.**

- **Dashboard/API: dormant within the provable window.** Zero requests to either service
  from 2026-06-03 through 2026-08-01 (metrics), zero in the 30-day logs — until the owner
  opened the dashboard during this assessment (2026-08-03, login + daily views, all 200s).
  The owner reports accessing it a handful of times earlier in 2026 (e.g. around the
  Feb/Mar deploys); that predates retention and is neither confirmed nor contradicted by
  the data.
- **Data collection: yes, continuously.** The sensor is alive and publishing (last
  message 2026-07-31, the most recent day checked; 763 messages in July 2026). The
  subscriber has been recording nearly uninterrupted since 2024-09-23.

**Conclusion:** a working system with a live data feed and an owner who checks in
occasionally, but no regular readers — at least two recent months with zero dashboard
opens. The always-on Cloud Run vCPU + Cloud SQL Enterprise instance mostly serve the
collector, not readers. See roadmap Phase 0 and the cost appendix.

## 5. Backend anatomy

```
app/
  __init__.py        # creates Flask app, CORS, Api, SQLAlchemy at import time,
                     # then imports namespaces and STARTS the MQTT subscriber (import side effect)
  config.py          # UNTRACKED. DevelopmentConfig (always used, incl. prod) + MQTT_TOPICS list
  apis/
    testdata.py      # /test-data/* endpoints over table test_data (obsolete discovery data)
    data_tracker.py  # /data-tracker/* endpoints over table data_tracker (what the front uses)
  models/
    testdata.py           # TestData        -> table test_data      (exists in DB)
    data_tracker.py       # DataTracker     -> table data_tracker   (exists in DB)
    rooms.py              # Rooms           -> never migrated, not imported (dead)
    devices.py            # DUPLICATE copy of Rooms class (copy-paste), dead
    single_people_counter.py # SinglePeopleCounter -> never migrated, dead
  mqtt/subscriber.py # paho-mqtt client; topic->handler map
  utils/auth.py      # require_auth decorator verifying Supabase HS256 JWT
migrations/          # alembic; env.py imports `app` (side effects on migrate)
Dockerfile           # UNTRACKED. python:3.12-slim + gunicorn; secrets hard-coded
requirements.txt     # unpinned: Flask, Flask-RESTX, Flask-SQLAlchemy, SQLAlchemy,
                     # psycopg2-binary, alembic, paho-mqtt, gunicorn, PyJWT, flask-cors
```

### REST endpoints

| Route | Auth | Purpose / notes |
|---|---|---|
| `GET /test-data/test` | none | all `test_data` rows (8 rows from Sept 2024) |
| `GET /test-data/test/<start>/<end>` | none | daily counts with `generate_series` zero-fill |
| `GET /test-data/test/<date>` | none | hourly counts for a day |
| `POST /test-data/test/<date>` | **none** | inserts a fake row — open write endpoint in prod |
| `GET /data-tracker/tracker` | broken (`@require_auth` w/o parens) | dump of all raw rows |
| `GET /data-tracker/daily/<YYYY-MM-DD>` | yes | counts per hour (São Paulo tz), **used by front** |
| `GET /data-tracker/monthly/<YYYY-MM>` | yes | counts per day, **used by front** |
| `GET /data-tracker/tracker/<topic>` | **none** | 500s (`.filter_by` called on a `Result`) |

The daily/monthly endpoints count **all rows of `data_tracker`** for the period,
regardless of topic — i.e., the frontend visualization is fed by the raw discovery table
(this is exactly the workaround planned to be replaced by a proper passage-event table).

### MQTT subscriber

- Broker `broker.hivemq.com:1883`, no TLS/auth; subscribes to 10 topics (names
  unlisted — env-driven since Phase 0, see [secrets.md](secrets.md)).
- The legacy test topic → `test_data` table; **every other topic** → raw insert into
  `data_tracker(topic, payload, register_time=now())`.
- Runs on a background thread (`loop_start`) inside the single gunicorn worker.
- Reliability: QoS 0, no persistent session; DB writes fail roughly weekly with
  `SSL SYSCALL error: EOF detected` (stale connection, no `pool_pre_ping`) and the
  message is dropped.

## 6. The data (verified in prod, read-only)

Tables actually in the DB: `alembic_version`, `data_tracker`, `test_data`.

| Table | Rows | Range |
|---|---|---|
| `data_tracker` | 26,019 | 2024-09-23 → 2026-07-31 (ongoing) |
| `test_data` | 8 | Sept 2024 only (dead) |

Topic distribution in `data_tracker`: **the JSON topic 25,970 rows (99.8%)**;
a query topic 45; two config topics 4.

### The JSON topic's payload (the real passage event)

```json
{
  "device_id": "<device-id>",
  "time_system":  "2026-07-31T16:44:10Z",
  "time_poweron": "2026-07-29T19:53:27Z",
  "time_detected":"2026-07-31T16:44:10Z",
  "access_count": 14007,
  "people_count": 7003,
  "status_sensor": "free",
  "ip_address": "10.10.x.x",
  "RSSI": "-76",
  "pulse_ton": 101,        // absent in 2024 payloads — optional
  "pulse_toff": 302        // absent in 2024 payloads — optional
}
```

Verified semantics (from 25,970 consecutive-row deltas of `access_count`):

- **One message = one beam interruption (passage).** 25,300 transitions are exactly +1.
- `access_count` = device's cumulative passage counter; `people_count` = floor(access/2)
  computed by the firmware (entry + exit = one visit). The frontend re-applies the same
  ÷2 rule to row counts.
- **362 duplicate deliveries** (same count repeated) → ingestion must dedupe.
- **301 gaps** (counter jumps > +1) → messages lost while the service was down/disconnected;
  the counter allows quantifying loss.
- **6 counter resets** (e.g. 6278→1) — device reboot/reflash; counters are per-"era".
- `status_sensor` is `"free"` in 25,969 of 25,970 rows (a single `"blocked"`), so
  messages fire on beam release, not per state change.

### Timezone quirk (important)

`time_detected` carries a `Z` suffix but is actually **America/São_Paulo local time**
(device clock): e.g. device `16:44:10Z` was received by the server at `19:44:10` UTC.
`register_time` is naive server-now (UTC). The backend compensates with the double
conversion `func.timezone('America/Sao_Paulo', func.timezone('UTC', register_time))` and
the frontend converts again for display. Any new schema must store true UTC and make this
explicit.

## 7. Frontend anatomy

Stack: Vite + React 19 + TypeScript, MUI 6, MUI X Date Pickers, Recharts, axios,
react-router 7, supabase-js. Package manager nominally pnpm (but `yarn.lock` also
present and `package-lock.json` was just deleted — needs settling).

```
src/
  App.tsx                     # session-gated routes: /login, /, /daily/:roomId, /monthly/:roomId
  pages/HomePage.tsx          # rooms are MOCKED ([{id:"1", name:"Biblioteca NCE"}]);
                              # auto-redirects to /daily/1; multi-room list UI commented out
  pages/DailyCounterPage.tsx  # bar chart per hour; pads display to 07–19h; highlights max;
                              # "Total de Visitas" = ceil(sum/2)  ← domain rule in the UI
  pages/MonthlyCounterPage.tsx# bar chart per day of month (mostly a copy of Daily)
  components/molecules/LoginForm/  # Supabase signInWithPassword
  services/axios.tsx          # axios instance + Bearer token interceptor (Supabase session)
  services/counter.ts         # GET data-tracker/daily/<d>, data-tracker/monthly/<m>
  utils/datetime.ts           # hour extraction in America/Sao_Paulo
  utils/supabase.ts, theme.tsx, types/counter.ts
```

Known limitations: `roomId` from the URL is **never sent to the API** (all rooms would
show the same data); no logout control; no loading/empty/error UI (errors go to
`console.error`); no tests; no Storybook; strings mix pt-BR and English.

## 8. Deployment process (today)

1. Backend: `gcloud run deploy biblioteca-nce-back --source .` from the local folder
   (secrets baked into the image via Dockerfile ENV).
2. Frontend: multi-stage Docker build (node:22-alpine + pnpm → nginx:1.25-alpine),
   `gcloud run deploy biblioteca-nce-front --source .`.
3. Migrations: run manually via alembic against prod (env.py reads the Flask config, and
   importing it starts the MQTT subscriber as a side effect).
4. No dev/staging environment, no CI, no automated tests of any kind.
