#!/usr/bin/env python3
"""
tfl_closure_check.py

A throwaway VALIDATION SPIKE - not production code.

Its one job: answer the question "Does TfL's open data actually KNOW when my
bus stops are closed or disrupted?" - so you can decide whether the closure
feature is worth building BEFORE you write any UI around it.

What it does, per stop:
  1. (optional) Helps you find the stop IDs for your stops by name or code.
  2. Prints the live bus arrivals  -> proves the live feed works for that stop.
  3. Prints any disruptions TfL is currently reporting -> the actual experiment.
  4. Flags stops that also appear in TfL's network-wide list of disrupted stops.

Then you do the part no script can do: walk to those stops in Zones 1-3 and
compare reality to what this printed. Where the gaps are is your real answer.

------------------------------------------------------------------------------
HOW TO RUN
  1. (Recommended) Get a free key at https://api-portal.tfl.gov.uk/
     Without a key you're limited to 50 requests/min; with one, 500/min.
       export TFL_APP_KEY="your_key_here"        # mac/linux
       setx TFL_APP_KEY "your_key_here"          # windows (then reopen terminal)
  2. Install the one dependency:
       pip install requests
  3. Find your stop IDs: set SEARCH_FOR (below) to a stop name or the 5-digit
     code printed on the physical bus-stop flag, run the script, copy the IDs.
  4. Paste those IDs into MY_STOPS, set SEARCH_FOR back to None, run again.
------------------------------------------------------------------------------
"""

import os
import time
import json
from urllib.parse import quote

import requests

BASE = "https://api.tfl.gov.uk"
APP_KEY = os.environ.get("TFL_APP_KEY")  # None is fine - you just get a lower rate limit


# ============================ CONFIGURE ME ===================================
# The stops you actually use. Use the Naptan IDs (look like "490008766S").
# Don't know them yet? Use SEARCH_FOR below to look them up first.
MY_STOPS = [
    # "490008766S",   # <- replace these with your real stop IDs
    # "490011611E",
]

# To look up a stop's ID, put its name OR its 5-digit flag code here, e.g.
#   SEARCH_FOR = "Angel Station"   or   SEARCH_FOR = "73916"
# Leave as None once you've filled in MY_STOPS.
SEARCH_FOR = None
# =============================================================================


def _get(path, params=None):
    """
    Make one GET request to the TfL API and return parsed JSON (or None on failure).
    Every other function goes through this one - so rate limiting, the API key,
    and error handling all live in a single place.
    """
    params = dict(params or {})
    if APP_KEY:
        params["app_key"] = APP_KEY
    url = f"{BASE}{path}"
    try:
        resp = requests.get(url, params=params, timeout=15)
    except requests.RequestException as e:
        print(f"  ! network error calling {path}: {e}")
        return None

    if resp.status_code == 429:
        print("  ! rate limited (HTTP 429). Slow down, or add a free TFL_APP_KEY.")
        return None
    if resp.status_code == 404:
        print(f"  ! not found (HTTP 404) for {path} - is that a valid stop id?")
        return None
    if resp.status_code != 200:
        print(f"  ! unexpected HTTP {resp.status_code} for {path}")
        return None

    try:
        return resp.json()
    except ValueError:
        print(f"  ! response wasn't JSON for {path}")
        return None


def search_stops(query):
    """Find candidate bus stops by name or 5-digit code. Prints id + name."""
    print(f"\nSearching bus stops matching: {query!r}")
    data = _get(f"/StopPoint/Search/{quote(query)}", {"modes": "bus"})
    if not data:
        return
    matches = data.get("matches", [])
    if not matches:
        print("  (no matches - try a different spelling or the 5-digit flag code)")
        return
    for m in matches:
        print(f"  {str(m.get('id')):<16} {m.get('name')}")


def get_arrivals(stop_id):
    """Live bus arrival predictions for one stop, soonest first."""
    data = _get(f"/StopPoint/{stop_id}/arrivals")
    if not isinstance(data, list):
        return []
    return sorted(data, key=lambda a: a.get("timeToStation", 10**9))


def get_stop_disruptions(stop_id):
    """Disruptions TfL is currently reporting for this specific stop (often empty = good)."""
    data = _get(f"/StopPoint/{stop_id}/disruption")
    return data if isinstance(data, list) else []


def get_disrupted_bus_stops():
    """Network-wide: the set of bus stop IDs TfL currently considers disrupted."""
    data = _get("/StopPoint/Mode/bus/Disruption", {"includeRouteBlockedStops": "true"})
    ids = set()
    if isinstance(data, list):
        for d in data:
            # The id-bearing field name isn't always the same, so grab whichever exists.
            for key in ("atcoCode", "stationAtcoCode", "id"):
                if d.get(key):
                    ids.add(d[key])
    return ids


def describe_disruption(d):
    """
    Pull the human-readable text out of a disruption, else dump the whole object.
    Dumping the raw JSON on purpose: it's how you discover the real field names.
    """
    return d.get("description") or json.dumps(d, indent=2)


def main():
    # --- ID lookup mode ------------------------------------------------------
    if SEARCH_FOR:
        search_stops(SEARCH_FOR)
        return

    if not MY_STOPS:
        print("No stops configured yet.")
        print("Set SEARCH_FOR to a stop name (or its 5-digit flag code) to find IDs,")
        print("then paste the IDs into MY_STOPS and run again.")
        return

    # --- The experiment ------------------------------------------------------
    print("Fetching TfL's network-wide list of disrupted bus stops...")
    disrupted_network = get_disrupted_bus_stops()
    print(f"  TfL currently reports {len(disrupted_network)} disrupted bus stops network-wide.\n")

    for stop_id in MY_STOPS:
        print("=" * 64)
        print(f"STOP: {stop_id}")

        # 1) Live arrivals - proves the feed works for this stop.
        arrivals = get_arrivals(stop_id)
        if arrivals:
            print("  Next buses:")
            for a in arrivals[:5]:
                mins = round(a.get("timeToStation", 0) / 60)
                line = a.get("lineName", "?")
                dest = a.get("destinationName", "?")
                print(f"    {line:<4} to {dest:<28} ~{mins} min")
        else:
            print("  No arrivals returned (could just be quiet - note it, don't assume closed).")

        # 2) Closure / disruption check - the actual question.
        in_network_list = stop_id in disrupted_network
        stop_disruptions = get_stop_disruptions(stop_id)

        if stop_disruptions or in_network_list:
            print("  [!] POSSIBLE CLOSURE / DISRUPTION REPORTED:")
            if in_network_list:
                print("      - appears in TfL's network-wide disrupted-stops list")
            for d in stop_disruptions:
                text = describe_disruption(d).replace("\n", "\n        ")
                print(f"      - {text}")
        else:
            print("  [ok] No disruption reported by TfL for this stop right now.")

        time.sleep(0.2)  # nowhere near the rate limit, but a polite habit to build

    print("=" * 64)
    print("\nNow the real test: walk to these stops and compare reality to the above.")
    print("  - Where TfL said 'disrupted' - was it actually?")
    print("  - Where TfL said nothing - was a stop in fact taped up and shut?")
    print("That gap is your answer on whether the closure feature is trustworthy enough to ship.")


if __name__ == "__main__":
    main()
