# Secrets Handling

> This file documents the **scheme**. Operational specifics — actual values, addresses,
> topic names, and credential-lifecycle decisions — are deliberately kept out of this
> public repository (gitignored files + private notes).
> Constraint from roadmap.md: plain env vars only — no GCP Secret Manager (portability
> to university infra).

## What counts as a secret here

| Value | Secret? | Notes |
|---|---|---|
| `SQLALCHEMY_DATABASE_URI` (contains Cloud SQL password) | **yes** | superuser on an internet-reachable instance |
| `SUPABASE_JWT_SECRET` (legacy HS256 signing secret) | **yes** | whoever has it can mint valid API tokens |
| Supabase test-user password (e2e, later) | yes | limited blast radius, still gitignored |
| Frontend `VITE_SUPABASE_ANON_KEY` | no | public by design (client-side key, protected by Supabase RLS/auth rules) |
| Frontend `VITE_API_URL`, `VITE_SUPABASE_URL` | no | public endpoints |
| MQTT topic names | **treat as secret** | unauthenticated public broker (SEC-3): the names are the only gate until the broker is replaced. Never commit them — gitignored env files only (`MQTT_TOPICS`, `MQTT_TOPIC_JSON`, `MQTT_TEST_TOPIC`). |
| DB address / instance details | unlisted | kept out of committed docs; connection string lives in env files only |

## Where secrets live (the only two homes)

1. **Local:** gitignored files —
   - backend `.env` (KEY=VALUE, consumed by compose/dotenv; local-stack values only),
   - `deploy/prod.env.yaml` (YAML, consumed by gcloud at deploy; the real prod values).
   Committed templates: `.env.example`, `deploy/prod.env.yaml.example`.
2. **Cloud Run service env vars:** set at deploy time from the local file:

   ```bash
   gcloud run deploy biblioteca-nce-back --source . --region us-central1 \
     --env-vars-file deploy/prod.env.yaml
   ```

   `--env-vars-file` replaces the revision's full env-var set — deterministic, no secrets
   in shell history, none in the image.

Nowhere else. Specifically **never in**: Dockerfiles, source code, commits, docs,
screenshots, chat sessions, CI logs. The university-infra future maps 1:1: the same
values go into an `env_file` for compose/systemd on NCE servers.

**Worker VM (spec-008):** the VM's `~/Backend-People-Counter/.env` (chmod 600) is
provisioned over `gcloud compute scp` from a locally generated minimal file — DB URI +
MQTT settings only; the JWT secret never goes to the VM (the worker doesn't verify
tokens). Re-provision the same way after any credential change.

## Rules

- The Dockerfile carries zero configuration; the app reads everything from env at runtime.
- `.gitignore` covers `.env`, `.env.*`, `deploy/*.env.yaml` (templates excepted). Verify
  after cloning: `git check-ignore deploy/prod.env.yaml` must match.
- Before any commit touching config: `git status` — no env file may appear.
- spec-001 adds a `gitleaks` pre-commit hook as a net for exactly this class of accident.
- Prod DB analysis queries: read-only, and never paste the URI into scripts — load it
  from the env file.

## Cleanup of pre-existing copies (pending — do after the first clean deploy)

The old Dockerfile baked both secrets into build artifacts. They persist inside the GCP
project (owner-only access) until purged:

- [x] Deploy once with the clean Dockerfile + `--env-vars-file` — done 2026-08-08
      (revision `biblioteca-nce-back-00034-pd2`).
- [x] Purge old source uploads — done 2026-08-08: both `run-sources-*` (14 zips) and the
      legacy `*_cloudbuild/source/` bucket (all tarballs, 2024-09 → 2025-05) emptied;
      only the clean deploy's zip remains.
- [x] Old build logs: bucket copies removed with the folder above; Cloud Logging copies
      expired long ago (30-day retention).
- [x] Delete container images predating the clean deploy — done 2026-08-08: all 35 old
      versions (2024-09 → 2026-02) deleted, exactly one image (the clean build) remains;
      rollback to pre-cleanup revisions is intentionally broken.
- [ ] Local: check editor/backup copies of the old Dockerfile if any
      (`Dockerfile.bak`, OneDrive version history of the repo folder, etc.).
