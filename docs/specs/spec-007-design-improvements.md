# Spec 007 — Design Improvements

**Status:** ✅ implemented 2026-08-10 (core) — app shell (nav, room switcher, user menu
with logout), DataState loading/error+retry/empty on every view, theme-driven shared
chart component, dark-mode detection fixed, pt-BR MUI + pickers, 401 → sign-out,
central copy module, Storybook stories for states/chart. Remaining nice-to-haves:
formal Lighthouse a11y audit, dark-mode toggle decision, NCE logo asset, full string
migration to the copy module. · **Phase:** 5 · **Depends on:** spec-001 (Storybook), spec-003 (rooms in shell) · **Fixes:** DEBT-9

## Context

The current UI is three bare pages with default MUI styling, no navigation, no logout, no
feedback states, mixed pt-BR/English, and hard-coded chart colors. Functional for a demo,
not for a TCC defense. Storybook (spec-001) is the workbench for this spec.

## Design

### App shell

- Top AppBar: product name, room switcher (when >1 room), nav — **Diário · Mensal ·
  Anual · Relatórios** — user menu with e-mail + **Sair** (logout finally exists).
- Layout route wrapping all authenticated pages; login page stays bare.

### Theme & tokens

- Single MUI theme: palette (primary derived from NCE/UFRJ identity if the asset exists,
  otherwise a chosen accessible blue), consistent typography scale, spacing.
- Chart colors come from the theme (no more `#ff5722` literals); highlight color for
  max-bucket defined once.
- Localization: `ptBR` locale for MUI + Date Pickers everywhere (partially done), all
  copy pt-BR, dates `DD/MM/YYYY`.

### States & feedback

Every data view gets the four states, as reusable components with stories:
- **Loading:** skeleton matching the chart/table silhouette.
- **Empty:** "Sem registros no período" + hint.
- **Error:** message + "Tentar novamente" (retry) — errors stop being console-only.
- **Data:** the chart.

Plus: session-expired handling (axios 401 interceptor → redirect to login with a toast).

### Components refactor

- Extract the duplicated Daily/Monthly page bodies into `PassageChartPage`
  (picker + KPI card + chart) parameterized by granularity — kills DEBT-5 on the front.
- Chart wrapper component (responsive container, tooltip formatting, highlight logic) —
  one Storybook story per granularity.
- A11y pass: labels on pickers/buttons, chart `aria-label` summaries, focus states,
  color contrast ≥ AA.

## Work breakdown

1. Theme + shell + logout + 401 handling (small PRs, each verified in Storybook + local).
2. State components + integration into pages.
3. `PassageChartPage` consolidation.
4. Copy pass (pt-BR everywhere) + a11y pass.
5. Playwright: nav flows, logout, error-state rendering (API mocked/killed), visual
   sanity screenshots per page for the TCC appendix.

## Acceptance criteria

- No hard-coded colors/strings in page components (theme + i18n-ready copy module).
- All four states demonstrable in Storybook for every data view.
- Logout works and expired sessions land on /login with feedback.
- Lighthouse a11y ≥ 90 on the three main pages.

## Open questions

- Dark mode: cheap with MUI theme — in scope or not?
- Is there an official NCE/UFRJ visual identity/logo we may use?
