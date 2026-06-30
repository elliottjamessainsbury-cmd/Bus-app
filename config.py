"""
config.py — all tunable settings for the Bus Curtailment Validation Instrument.

This file is intentionally *just data*: read-only constants, no logic. Every
knob the PRD says must be configurable (FR1, FR2, FR3) lives here in one place
so nothing is hard-coded deeper in the code. Change a value here and the whole
instrument picks it up.

Nothing here is a secret. The TfL API key is NOT stored in this file — it is
read from the TFL_APP_KEY environment variable (see CLAUDE.md golden rules and
PRD FR3).
"""

# --- Routes to watch (FR1) ----------------------------------------------
# We start small to get one route working end to end before scaling out
# (PRD §17). These are the routes of interest; the validation set widens to
# ~40–50 central London routes later by simply adding ids to this list.
#
# Values are TfL "line ids" — the public route number as a string, e.g. "38".
ROUTES = [
    "21",
    "38",
    "55",
    "243",
]

# --- Polling (FR2) ------------------------------------------------------
# How often the Watcher asks TfL for fresh predictions, in seconds. The PRD
# targets ~30s; at this interval dozens of routes stay well under TfL's
# 500 requests/min limit (PRD §12).
POLL_INTERVAL_SECONDS = 30

# A small courtesy pause between individual API calls within a cycle, so we
# spread requests out rather than firing them all at once (PRD §12 politeness).
INTER_CALL_DELAY_SECONDS = 0.2

# --- Detection sensitivity (FR2, PRD §9) --------------------------------
# Persistence K: how many *consecutive* poll cycles the curtailment signal
# must hold before we record an event. Higher = fewer false positives but
# slower to catch short events. Default 2 catches events faster during
# validation, which is what this instrument is for.
PERSISTENCE_K = 2

# --- Enrichment / corroboration (FR2, PRD §10) --------------------------
# Buffer distance in metres: how far *beside* the route we still count a road
# closure as plausibly coinciding, when testing closure polygons against the
# route polyline. PRD default is 75m; tune later against real matches.
BUFFER_METRES = 75

# When the Enricher runs. "batch" = a nightly pass over the day's stored
# events (keeps the Watcher loop lean); "live" = enrich each event the moment
# it is detected. PRD §11/§16 leaves this to the implementer; we use batch.
ENRICHMENT_MODE = "batch"

# --- Storage ------------------------------------------------------------
# Path to the SQLite event store (the durable record; PRD §7). This file is
# git-ignored — it is local research data, not source.
DB_PATH = "events.db"
