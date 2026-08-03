# Spec 005 — PDF Passage Reports

**Status:** draft · **Phase:** 4 · **Depends on:** spec-002 (passage data + range endpoint), spec-003 (room scoping)

## Context

New feature: a user-friendly PDF report of passages for a room, filterable by date
interval — something a library coordinator can download and forward. Language: pt-BR.

## Design

### Endpoint

```
GET /api/v2/rooms/<room_id>/reports/passages.pdf?start=YYYY-MM-DD&end=YYYY-MM-DD
```

- Auth + room access enforced (spec-003). Interval validation: start ≤ end, max 400 days.
- Response: `application/pdf`, `Content-Disposition: attachment;
  filename="relatorio-<slug>-<start>-<end>.pdf"`.

### Rendering approach

**Backend-rendered: Jinja2 HTML template + WeasyPrint.** Charts embedded as SVG generated
server-side from the same aggregation service the JSON API uses (hand-built SVG bars or
matplotlib-to-SVG — no JS in PDF rendering).

Why not frontend (jsPDF/react-pdf/print CSS): backend PDF is testable in pytest, reusable
(e-mail/cron later), consistent typography, and keeps the ÷2 semantics in one place.
Trade-off: WeasyPrint needs system libs (pango/cairo) → Dockerfile grows; acceptable.

### Report contents (single template, 2–4 pages)

1. **Header:** room name, period, generated-at, "Contador de Pessoas — NCE/UFRJ" branding.
2. **KPI row:** total passages, estimated visits (÷2 rule, labeled honestly as estimate),
   daily average, busiest day, busiest hour overall.
3. **Chart: passages per day** across the interval (bar, zero-filled).
4. **Chart: average hourly profile** (bar, 24h, the "shape" of library traffic).
5. **Table:** per-day date / passages / visits (chunked across pages as needed).
6. **Footer:** data-quality note (sensor gaps in the period, from spec-002's counters) +
   page numbers.

### Frontend

"Exportar PDF" button on the room dashboard opening a small dialog: preset ranges (this
week / this month / last month / custom pickers) → triggers download via authenticated
axios request (blob), standard save. Loading + error states.

## Work breakdown

1. Aggregation service: range summary (reuses spec-002 services; adds busiest-day/hour).
2. Template + SVG chart helpers; golden-file test (render → assert text content with
   `pypdf`; pixel-diff optional).
3. Endpoint + auth tests + interval validation tests.
4. Dockerfile: WeasyPrint deps; verify image locally per spec-004 rule.
5. Frontend dialog + button + Playwright test (download completes, filename correct,
   PDF text contains the room name and totals).

## Acceptance criteria

- Report for any valid interval of the real backfilled data renders correctly (spot-check
  months with gaps/resets — footer numbers must match spec-002's quality report).
- pt-BR labels/dates (`DD/MM/YYYY`), América/São_Paulo boundaries — a passage at 23:50
  local lands on the correct report day (test).
- Unauthorized user → 404; no access → 404 (per spec-003 policy).

## Open questions

- Include the NCE/UFRJ logo (need the asset) or text-only branding?
- Also offer CSV of the per-day table (cheap add-on) now or later?
