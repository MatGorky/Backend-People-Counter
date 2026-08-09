# Spec 003 — Rooms, Devices and User Access

**Status:** ✅ implemented 2026-08-09 — room/device/user_room live in prod, seeded
(library room + its device + owner grant); room-scoped API v2 with 404-policy access
control and app_metadata admin role; frontend real-rooms flow. Grant-role granularity
and `passage_event.room_id NOT NULL` tightening remain future refinements. · **Phase:** 3
(after spec-002) · **Depends on:** spec-001/002/004 · **Fixes:** BUG-5/9, SEC-7 (authorization part)

## Context

Multi-room support was always intended (frontend routes are `/daily/:roomId`, a room list
UI is sketched in comments) but never formalized: rooms are mocked in `HomePage`, the
`roomId` never reaches the API, dead `Rooms`/`SinglePeopleCounter` models were never
migrated, and there is no authorization at all — any authenticated Supabase user sees
everything.

**Target rules (as stated):** a user has access to 0..N rooms; a room has 0..N passage
events. Users live in Supabase (auth only); everything else lives in our Postgres.

## Design

### Schema

```
room
  id          int identity PK
  name        text NOT NULL                 -- "Biblioteca NCE"
  slug        text NOT NULL UNIQUE          -- "biblioteca-nce"
  timezone    text NOT NULL DEFAULT 'America/Sao_Paulo'
  created_at  timestamptz NOT NULL DEFAULT now()

device
  id          text PK                       -- MQTT device_id (real ids unlisted)
  room_id     int NOT NULL FK→room.id
  description text NULL
  first_seen  timestamptz NULL
  last_seen   timestamptz NULL              -- updated by ingestion; doubles as health signal

user_room
  user_id     uuid NOT NULL                 -- Supabase auth.users.id (JWT `sub`)
  room_id     int  NOT NULL FK→room.id
  granted_at  timestamptz NOT NULL DEFAULT now()
  granted_by  uuid NULL
  PRIMARY KEY (user_id, room_id)
```

`passage_event.room_id` becomes NOT NULL after seed + backfill resolve it via `device`.
Unknown `device_id` at ingestion → auto-create device with `room_id NULL`? No —
**reject to raw-log-only + warning**; devices are registered explicitly (prevents public
-broker spoofing from creating rooms, SEC-3 mitigation).

### AuthN / AuthZ workflow

- **Authentication** (exists): Supabase JWT verified by `require_auth`. Harden per SEC-7:
  verify `iss`, keep `aud="authenticated"`, small leeway; check whether the Supabase
  project uses legacy HS256 shared secret or the newer asymmetric JWKS — support what the
  project actually has before touching it.
- **Authorization** (new): decorator `require_room_access` on every room-scoped endpoint —
  404 (not 403) when the user has no `user_room` row, so room existence isn't leaked.
- **Admin**: app-level admin flag read from the JWT's `app_metadata.role == "admin"`
  (set once per admin via Supabase dashboard — no user-management UI needed). Admins
  implicitly access all rooms and may call the grant/revoke endpoints.

### API

```
GET    /api/v2/me/rooms                          → rooms the caller can access (feeds HomePage)
POST   /api/v2/rooms                             → admin: create room
POST   /api/v2/rooms/<id>/devices                → admin: register/point a device at a room
GET    /api/v2/rooms/<id>/users                  → admin: list grants
PUT    /api/v2/rooms/<id>/users/<user_id>        → admin: grant access
DELETE /api/v2/rooms/<id>/users/<user_id>        → admin: revoke
```

All `rooms/<id>/passages/*` endpoints from spec-002 get `require_room_access`.

### Frontend

- `HomePage`: real `GET /me/rooms`; 0 rooms → "no access" screen; 1 room → auto-redirect
  (current behavior); N rooms → the room list already sketched in the commented code.
- Room name comes from the API (no more hard-coded "Biblioteca NCE" headings).
- Admin screens: **out of scope** (admin operations via API/Supabase dashboard for now).

### Seed / rollout

1. Migration creating the three tables.
2. Seed script: room "Biblioteca NCE" (`biblioteca-nce`), the library's device → that room,
   grants for the existing Supabase users (there are only a couple).
3. Backfill `passage_event.room_id` via device mapping; set NOT NULL.
4. Frontend cutover together with spec-002's.

## Work breakdown

1. Models + migration + seed script (rehearsed locally, then prod).
2. Auth hardening + `require_room_access` + admin check, with a full pytest matrix
   (no token / valid no-access / valid with-access / admin / expired).
3. `/me/rooms` + admin grant endpoints + tests.
4. Wire spec-002 endpoints to enforcement; ingestion updates `device.last_seen`.
5. Frontend: real rooms flow + tests; Playwright: two test users (one with access, one
   without) prove isolation end-to-end.

## Acceptance criteria

- A user with no grants sees an empty room list and gets 404 on direct URL access
  (Playwright-verified).
- A user with one room auto-redirects exactly as today; with two, sees the picker.
- Messages from an unregistered `device_id` never create passage events (test).
- All passage endpoints require both a valid JWT **and** a room grant (test matrix green).

## Open questions

- Grant roles per room (viewer/manager) now, or flat access until a real need appears?
  (Recommend flat now; the PK/table shape doesn't block adding a `role` column later.)
- Should `GET /me/rooms` include device health (`last_seen`) for a status badge (nice TCC
  touch)?
