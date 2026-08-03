# Spec 008 — Move the MQTT Subscriber to a Free-Tier VM

**Status:** chosen 2026-08-03 (cost appendix option B) · **Phase:** 2.5 · **Depends on:** spec-001 (worker entrypoint) · **Fixes:** COST-1; enables closing SEC-2

## Context

The backend Cloud Run service runs `minScale=1, maxScale=1, CPU always allocated` solely
because the MQTT subscriber is a background thread inside the web process — an always-on
vCPU (~US$45/mo ballpark) serving near-zero HTTP traffic. GCP's Always Free tier includes
one non-preemptible `e2-micro` VM (2 shared vCPU burst / 1 GB RAM) in `us-central1` —
same region as Cloud SQL — plus 30 GB standard disk and 1 GB/mo North-America egress.
The subscriber is a tiny process (paho-mqtt + SQLAlchemy inserts); it fits with huge
headroom.

## Target architecture

```
IR sensor → HiveMQ (public) ──MQTT──► e2-micro VM (us-central1, free tier)
                                        docker: mqtt-worker container → Cloud SQL
User → Cloud Run biblioteca-nce-back (API only, min=0, CPU throttled)  → Cloud SQL
```

- **VM:** Debian 12 + Docker (or Container-Optimized OS). One container: the worker from
  spec-001's refactor (`python -m app.mqtt_worker` entrypoint — subscriber + models, no
  web server), `restart: always`, env vars from an `env_file` (per docs/secrets.md).
  This VM setup is deliberately identical to what a university box would run later.
- **Cloud Run:** same image, but `--min-instances=0 --no-cpu-boost --cpu-throttling`
  restored; API-only entrypoint (gunicorn) no longer starts the subscriber. Cold starts
  of a few seconds are acceptable for an occasionally-opened dashboard.
- **Networking:** VM needs **outbound only** (MQTT 1883, Postgres 5432). No inbound
  firewall rules except IAP SSH for admin. Reserve a **static external IPv4** so the DB
  can pin it (note: in-use external IPv4 costs ~US$3.7/mo unless the free tier exempts
  it — verify on the first bill; alternative: drop the external IP and use Cloud NAT,
  ~US$1/mo at one VM).
- **SEC-2 closure (the security bonus):** with the worker on a fixed IP, restrict Cloud
  SQL authorized networks to that IP (+ your home IP for analysis). Cloud Run API access
  to the DB then needs either your home-IP-style openness removed and… → simplest robust
  combo: Cloud SQL keeps public IP but authorized networks = {VM static IP, your current
  home IP}; the Cloud Run API connects via the Cloud SQL connector (enable the sqladmin
  API — free) **or**, to stay maximally vendor-neutral, the API also egresses via a
  static IP (VPC connector — costs money, avoid) → pragmatic choice: **Cloud SQL Python
  connector for the Cloud Run side only**, vanilla `psycopg2` on the VM. GCP-specific
  glue stays in config/deploy layer, app code unchanged. Decide at implementation time;
  both paths documented here so the trade-off is explicit.

## Reliability

- Same delivery semantics as today (public broker, QoS 0); spec-002's dedupe/gap
  accounting applies unchanged.
- `restart: always` + paho automatic reconnect (fixed in spec-001: register
  `on_disconnect`, log reconnects).
- Watchdog: `device.last_seen` (spec-003) already doubles as a health signal; optional
  log-based alert if no message stored for N hours during library opening hours.
- VM maintenance: live-migrates transparently; reboots are covered by docker restart
  policy + `--restart-policy=always` on the container.

## Rollout (after spec-001's entrypoint split, locally rehearsed per spec-004)

1. Create VM (free-tier config: `e2-micro`, `us-central1-*`, 30 GB standard PD, Debian
   12), install Docker, deploy the worker container with its env file; verify messages
   flow into `data_tracker` (watch for double inserts while both subscribers run — the
   overlap window is fine: spec-002 dedupe, or do a brief planned gap instead).
2. Redeploy Cloud Run with worker disabled + `min-instances=0` + CPU throttling on.
3. Verify: dashboard still works (cold start acceptable), messages keep arriving via VM.
4. Restrict Cloud SQL authorized networks (SEC-2) per the networking decision above.
5. Watch the next billing cycle; expected drop ≈ US$40–45/mo (verify — pricing
   assumptions, not guarantees).

## Acceptance criteria

- A sensor message published while Cloud Run is scaled to zero is stored within seconds
  (proves the collector no longer depends on the web service).
- Cloud Run back shows `min-instances: 0` and near-zero billable instance time over a
  normal week.
- VM survives a reboot with no manual action (container auto-starts, resubscribes).
- Cloud SQL authorized networks no longer contain 0.0.0.0/0 (or equivalent).

## Open questions

- ~~Outbound path for the VM~~ — **decided 2026-08-03: (a) static external IPv4 on the
  VM** (~$0–3.7/mo accepted by owner; verify possible free-tier exemption on first bill).
  Alternatives kept for reference: (b) Cloud NAT (~$1/mo, NAT IP may be billed);
  (c) Cloud SQL private IP for the DB leg (strongest SEC-2 posture) — (c) can still be
  layered on later without changing the VM. The public HiveMQ broker remains the only
  hard internet dependency; appendix option C (device → HTTPS/own broker) would remove
  it later.
- Brief planned message gap during cutover vs overlap-and-dedupe?
