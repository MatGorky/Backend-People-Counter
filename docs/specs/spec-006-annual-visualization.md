# Spec 006 — Annual Visualization

**Status:** draft · **Phase:** 4 · **Depends on:** spec-002 (yearly endpoint), spec-003 (room scoping)

## Context

New feature: a year-level view of library traffic. With 2024-09 → today backfilled
(spec-002) there are 2+ years of real data — this is the TCC's money shot: seasonality of
an academic library (semester peaks, exam weeks, vacations).

## Design

### API (from spec-002)

`GET /api/v2/rooms/<id>/passages/yearly?year=YYYY` →
`{"data": [12 zero-filled monthly buckets], "totals": {...}}`, computed in the room's
timezone. Optional `?resolution=daily` returns 365 per-day buckets for the heatmap.

### Frontend — new page `/yearly/:roomId`

1. Year picker (only years with data enabled; from a small `years-available` field on
   `/me/rooms` or a cheap extra call).
2. **Monthly bar chart** (12 bars, consistent with existing daily/monthly styling,
   max-month highlighted).
3. **Calendar heatmap** (GitHub-contributions style, 53×7, color scale by daily
   passages) — the semester rhythm becomes visible at a glance. Recharts has no native
   heatmap; build a small SVG grid component (good Storybook candidate, ~trivial with
   the daily-resolution endpoint).
4. KPI cards: total visits in year, busiest month, busiest single day, comparison with
   previous year (Δ%) when data exists.
5. Navigation ties into the app shell (spec-007): Diário / Mensal / Anual / Relatórios.

## Work breakdown

1. Yearly aggregation service + endpoint (+ daily resolution) + tests (timezone/DST-free
   in Brazil since 2019, but keep the boundary tests anyway).
2. Heatmap component in Storybook (empty/sparse/dense states) + monthly bar page.
3. Wire page, routes, year picker; Playwright: seeded year renders, totals match, year
   switch works.

## Acceptance criteria

- 2025 (only full historical year) renders correctly from backfilled data; months with
  known sensor gaps display honestly (no fake zeros presented as "closed library" — the
  data-quality footnote from spec-002 shows on the page).
- Heatmap tooltip: date + passages + visits, pt-BR formatted.
- Page holds up on mobile width (heatmap scrolls horizontally).

## Open questions

- Compare-two-years overlay (2025 vs 2026 lines) — worth it for the TCC defense, or keep
  scope minimal?
