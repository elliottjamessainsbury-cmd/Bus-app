# CLAUDE.md — Bus Curtailment Validation Instrument

Standing context for this project. `PRD-bus-curtailment-validation.md` is the
full specification and the source of truth; this file is the short list of
guardrails that should hold in every session.

## What this project is

A single-operator **validation instrument** that watches many London bus routes,
flags buses that appear to terminate early ("curtailment"), checks whether a road
or route closure could explain each one, and lets the operator log real-world
observations. Its only purpose is to gather evidence to decide whether a
curtailment feature is worth building. It is a precursor to a London bus app —
not the app itself.

## Golden rules (do not violate without checking first)

- **This is a measuring instrument, not the product.** Do NOT build consumer UI,
  user-facing alerts or notifications, saved-routes / saved-stops features, map
  rendering, or styling. If a task starts heading that way, stop and confirm.
  (See PRD §4 and §13.)
- **TfL Unified API is the only live-data source.** Do not add Google Maps
  Platform or commercial roadworks platforms (e.g. Causeway / one.network) as
  data sources. (See PRD §14.)
- **Do not trust API field names from the PRD or from memory.** Confirm exact
  JSON shapes against live API responses before relying on them. The repo's
  spike script prints raw responses for exactly this purpose.
- **Road and line disruption data is corroboration only** — used to explain or
  confirm a suspected curtailment, never as the primary detector. The detector
  is the live-prediction inference. (See PRD §9–§10 and §14.)
- **Never hardcode the API key.** Read it from the `TFL_APP_KEY` environment
  variable.

## How we work

- Workflow is PRD-first → atomic task list → one task at a time, with a commit
  after each task.
- Before writing code, generate an atomic, individually-testable task list from
  the PRD and confirm it. Don't start implementing until the list is agreed.
- **Build one route end to end before scaling to many.** Order: shared store +
  schema → Watcher (single route) → widen → Enricher → Manual Log → Reporting.
  (See PRD §17.)
- Keep changes small and reviewable. Explain non-obvious choices in plain
  language with brief bracket-explainers for jargon — the operator is learning
  to build and wants to understand, not just receive, the code.

## Stack

- Python, with minimal dependencies: `requests`, `shapely` (geometry), and the
  standard-library `sqlite3`.
- Data store: SQLite, a single `events` table with a `source` field
  (`auto` / `manual`) — the shared schema in PRD §7.
- Runs locally. No cloud services, no user data.

## Scope reminders

- **Validation scope ≠ product scope.** Watching dozens of routes here is
  intentional (it surfaces the rare curtailment events faster) and sits well
  within TfL's rate limits. The eventual product watches only a few routes.
- **Signals already considered and rejected** are recorded in PRD §14 (Google
  crowdedness, Causeway, road-as-primary-detector). Don't reintroduce them
  without revisiting that section first.
