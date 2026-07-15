"""
tfl_client.py — one small, shared doorway to the TfL Unified API.

Every part of the instrument (Watcher, Enricher, lookups) talks to TfL through
this module. Keeping all HTTP in one place means the API key, error handling,
timeouts and the base URL are defined exactly once — change them here and
everything downstream follows.

This reuses the proven pattern from the tfl_closure_check.py spike, promoted
from throwaway script to shared code.

Key handling (PRD FR3, CLAUDE.md golden rule): the API key is read from the
TFL_APP_KEY environment variable. It is never hard-coded and never committed.
Without a key the API still works at the lower 50-requests/min anonymous limit;
with one you get 500/min.
"""

import os

import requests

# The single base URL for every request. All paths below are appended to this.
BASE = "https://api.tfl.gov.uk"

# Read the key once, at import time, from the environment. None is acceptable —
# it just means we call anonymously at the lower rate limit.
# Normalise as we read it: an unset variable, an empty string, or whitespace
# all collapse to None (= call anonymously). Doing this once, at the source,
# keeps get() and has_key() from ever disagreeing about whether we have a key.
APP_KEY = (os.environ.get("TFL_APP_KEY") or "").strip() or None

# How long (seconds) we wait for TfL before giving up on a single request.
DEFAULT_TIMEOUT = 15


class TflError(Exception):
    """Raised when a request cannot be completed or returns a non-200 status.

    Callers that want the instrument to keep running through a bad cycle
    (PRD FR8 resilience) can catch this and log-and-skip.
    """


def get(path, params=None):
    """Make one GET request to the TfL API and return the parsed JSON.

    `path`   — the endpoint path, e.g. "/Line/38/Arrivals". A leading slash is
               optional; "Line/38/Arrivals" works too.
    `params` — optional dict of query-string parameters.

    Returns the decoded JSON (a list or dict, depending on the endpoint).
    Raises TflError on network failure, a non-200 status, or non-JSON body,
    so every caller handles failure the same way.
    """
    # Normalise the path so callers may pass "Line/38/Route" or "/Line/38/Route"
    # interchangeably — we guarantee exactly one leading slash before BASE.
    if not isinstance(path, str) or not path.strip():
        raise TflError("path must be a non-empty string")
    path = "/" + path.strip().lstrip("/")

    # Copy so we never mutate the caller's dict, then attach the key if we have
    # one. TfL accepts the subscription key as the `app_key` query parameter.
    query = dict(params or {})
    if APP_KEY:
        query["app_key"] = APP_KEY

    url = f"{BASE}{path}"
    try:
        resp = requests.get(url, params=query, timeout=DEFAULT_TIMEOUT)
    except requests.RequestException as exc:
        # Network-level problem (DNS, connection, timeout) — no HTTP response.
        raise TflError(f"network error calling {path}: {exc}") from exc

    if resp.status_code != 200:
        # Surface the common cases with a readable message; 429 = rate limited,
        # 404 = bad path/id. The status code is included for anything else.
        raise TflError(f"HTTP {resp.status_code} for {path}")

    try:
        return resp.json()
    except ValueError as exc:
        raise TflError(f"response was not JSON for {path}") from exc


def has_key():
    """True if a TFL_APP_KEY was found in the environment. Handy for a startup
    message so the operator knows whether they are on the 50 or 500/min limit."""
    return APP_KEY is not None
