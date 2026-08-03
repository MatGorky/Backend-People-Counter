# People Counter — Backend (Biblioteca NCE)

TCC project (B.S. Computer Science): IR sensor at the NCE library entrance → MQTT →
this Flask service on Cloud Run → Cloud SQL Postgres → React dashboard. Supabase is used
for **auth only**.

## Read first

- `docs/current-state.md` — verified system snapshot (architecture, data semantics, usage)
- `docs/issues.md` — known problems with stable IDs (SEC-x/BUG-x/DEBT-x/COST-x)
- `docs/roadmap.md` — phased plan + decision points; specs live in `docs/specs/`

Development is **spec-driven**: changes should map to a spec in `docs/specs/` and
reference issue IDs.

## Repos & environments

- Backend: this repo → Cloud Run `biblioteca-nce-back` (GCP project `matgorky`, us-central1)
- Frontend: `C:\Users\gorku\front-projects\biblioteca-nce-front` → Cloud Run `biblioteca-nce-front`
  (ignore `biblioteca-nce-frontend` and `projeto-biblioteca-nce-front` — legacy/empty)
- DB: Cloud SQL `biblioteca-nce` (Postgres 16). MQTT: public HiveMQ broker (to be replaced).
- **There is no dev environment (cost).** Rule: nothing deploys before it ran locally
  (see `docs/specs/spec-004-local-dev-env.md`). Deploys are manual `gcloud run deploy`.

## Hard rules

- Never put secrets in code, Dockerfiles, or commits. Env vars only — plain env vars,
  **not** GCP Secret Manager. Scheme + deploy command: `docs/secrets.md`; real values
  live only in gitignored `deploy/prod.env.yaml` and local `.env`.
- **This repo is PUBLIC.** MQTT topic names, the DB address/IP, device identifiers, and
  the security posture's live status stay OUT of committed files — gitignored env files
  only. Before any commit or push, sweep the diff for such details.
- Portability: the system should be able to move onto university (NCE) infra later.
  Platform-neutral primitives only in app code (env config, vanilla Postgres, MQTT,
  Docker); GCP specifics stay in deploy scripts.
- Prod DB access for analysis: read-only queries only; never write outside a migration.
- Migrations via alembic, rehearsed locally against the compose stack before prod.
- The device's `time_detected` is São Paulo local time **mislabeled as UTC (`Z`)** —
  see current-state.md §6 before touching anything time-related.
- One MQTT message = one passage; visits = passages ÷ 2 (device and product rule).
