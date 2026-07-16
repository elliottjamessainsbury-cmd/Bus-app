"""
route_geometry.py — a route's ordered stops and terminus (PRD §10 caching).

The detector needs to know a route's *scheduled terminus* so it can tell "the
bus finished its journey normally at the last stop" apart from "the bus turned
back early". That is the normal-terminus exclusion the detector left as a
placeholder in T2.4a; this module provides the real answer.

Data source: GET /Line/{id}/Route/Sequence/{direction} (shape confirmed in
TFL_API_NOTES.md). We fetch each route+direction once and cache it — route
geometry barely changes, and PRD §10 says to cache it per route.
"""

import tfl_client

# Cache: (route, direction) -> {"ordered": [naptanId, ...], "termini": {naptanId}}
# Populated lazily on first use and kept for the process lifetime.
_cache = {}


def _fetch(route, direction):
    """Fetch and parse one route+direction's ordered stops.

    Returns {"ordered": [...naptanIds in travel order...],
             "termini": {naptanId of the last stop of each sequence}}.
    Raises tfl_client.TflError on API failure (callers decide what to do).
    """
    data = tfl_client.get(f"/Line/{route}/Route/Sequence/{direction}")
    if not isinstance(data, dict):
        raise tfl_client.TflError(
            f"route sequence for {route}/{direction} was not a JSON object"
        )

    sequences = data.get("stopPointSequences") or []
    ordered = []
    termini = set()
    for seq in sequences:
        stops = seq.get("stopPoint") or []
        ids = [s.get("id") for s in stops if isinstance(s, dict) and s.get("id")]
        if not ids:
            continue
        # The last stop of each sequence is a terminus (handles branched routes).
        termini.add(ids[-1])
        # Keep the longest sequence as the representative ordered list.
        if len(ids) > len(ordered):
            ordered = ids
    return {"ordered": ordered, "termini": termini}


def get_geometry(route, direction):
    """Ordered stops + termini for a route+direction, using the cache."""
    key = (route, direction)
    if key not in _cache:
        _cache[key] = _fetch(route, direction)
    return _cache[key]


def is_normal_termination(route, direction, naptan_id):
    """True if `naptan_id` is a scheduled terminus of this route+direction — i.e.
    a bus dropping this as its furthest stop is finishing normally, not being
    curtailed. This is the callable the Detector expects.

    On an API failure we return False (do NOT suppress): for a measuring
    instrument it is safer to over-report and see the noise than to silently
    swallow a real event because geometry couldn't be loaded.
    """
    try:
        geo = get_geometry(route, direction)
    except tfl_client.TflError:
        return False
    return naptan_id in geo["termini"]


def preload(routes, directions=("outbound", "inbound")):
    """Warm the cache for a set of routes up front (e.g. at Watcher startup), so
    the first detection cycle isn't slowed by geometry fetches. Failures are
    swallowed here — is_normal_termination will simply retry/decline later.
    Returns the list of (route, direction) pairs successfully loaded."""
    loaded = []
    for route in routes:
        for direction in directions:
            try:
                get_geometry(route, direction)
                loaded.append((route, direction))
            except tfl_client.TflError:
                pass
    return loaded


def clear_cache():
    """Empty the cache (mainly for tests)."""
    _cache.clear()
