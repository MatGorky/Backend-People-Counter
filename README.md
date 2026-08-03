# People Counter — Backend (Biblioteca NCE)

Flask service for the NCE library people counter (TCC project): subscribes to the IR
sensor's MQTT messages, stores passage data in Postgres, and serves a REST API consumed
by the [React frontend](https://github.com/MatGorky/Frontend-People-Counter). Auth is
Supabase JWT (auth only — everything else is vendor-neutral by design).

**Start here:** [docs/current-state.md](docs/current-state.md) ·
[docs/issues.md](docs/issues.md) · [docs/roadmap.md](docs/roadmap.md) · specs in
[docs/specs/](docs/specs/). Development is spec-driven; secrets policy in
[docs/secrets.md](docs/secrets.md).

## Local development (spec-004)

Requirements: Python 3.12, Docker Desktop.

```bash
# 1. One-time setup
pip install -r requirements.txt
cp .env.example .env    # placeholder topics work for a self-contained demo;
                        # real topic names are unlisted (docs/secrets.md)

# 2. Start Postgres + Mosquitto
docker compose up -d

# 3. Create the schema
python -m alembic upgrade head

# 4. Seed ~60 days of plausible data
python scripts/seed_local.py

# 5. Run the API  →  http://localhost:8080 (Swagger UI at /)
python scripts/run_api.py
```

Try it:

```bash
# authenticated request with a locally minted token
curl -H "Authorization: Bearer $(python scripts/dev_token.py)" \
  http://localhost:8080/data-tracker/daily/$(date +%F)

# publish simulated sensor passages (watch them land in the DB / API)
python scripts/simulate_sensor.py --count 20 --interval 0.3

# anomaly injection for ingestion testing (spec-002)
python scripts/simulate_sensor.py --duplicate-every 7 --gap-every 11 --reset-at 30
```

Frontend: in the frontend repo, create `.env.local` with
`VITE_API_URL=http://localhost:8080` and run `pnpm dev`.

## Rules

- **Nothing deploys before it ran locally.** There is no cloud dev environment.
- Secrets: env vars only, never in code/Dockerfile/commits — [docs/secrets.md](docs/secrets.md).
- Prod deploy: `gcloud run deploy biblioteca-nce-back --source . --region us-central1
  --env-vars-file deploy/prod.env.yaml`
