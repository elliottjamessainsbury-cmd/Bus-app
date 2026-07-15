#!/usr/bin/env python3
"""
inspect_arrivals.py — a small inspection spike for task T2.1.

Its ONE job: print a real, live arrivals response from TfL so we can read off
the *actual* field names before building the Watcher on top of them. This is
the CLAUDE.md golden rule in action — "do not trust API field names from the
PRD or from memory; confirm them against live responses." (We just got bitten
by exactly this: the route endpoint calls it `name`, not `lineName`.)

This is throwaway/reference code, not part of the instrument. It reads nothing
and writes nothing — it only prints.

RUN IT (on your Mac, where TfL is reachable and your key is set):
    cd ~/Bus-app
    python3 inspect_arrivals.py

Then copy everything it prints back into the chat, and we'll write down the
confirmed field names and build the detector against them.
"""

import json
from collections import Counter

import tfl_client

# The route to inspect. 38 is one of ours and usually busy, so there should be
# several live predictions to look at. Change if you want to sample another.
ROUTE = "38"

# How many full prediction objects to dump in detail. Two is enough to see the
# shape without drowning in output.
FULL_DUMPS = 2


def main():
    print(f"Key detected in environment: {tfl_client.has_key()}")
    print(f"Fetching live arrivals for route {ROUTE} ...\n")

    try:
        predictions = tfl_client.get(f"/Line/{ROUTE}/Arrivals")
    except tfl_client.TflError as exc:
        print(f"Could not fetch arrivals: {exc}")
        print("If this is HTTP 429, wait a minute and try again.")
        return

    if not isinstance(predictions, list):
        print(f"Unexpected response type: {type(predictions).__name__} (expected a list)")
        print(json.dumps(predictions, indent=2)[:1000])
        return

    print(f"TfL returned {len(predictions)} live predictions for route {ROUTE}.\n")
    if not predictions:
        print("Empty list — the route may be quiet right now. Try again shortly,")
        print("or change ROUTE at the top of this file to a busier route.")
        return

    # 1) The full menu of field names present, and how often each appears. This
    #    is the bit we care about most — the real column names.
    key_counts = Counter()
    for p in predictions:
        if isinstance(p, dict):
            key_counts.update(p.keys())
    print("=" * 68)
    print("FIELD NAMES present across all predictions (name: how many rows had it)")
    print("=" * 68)
    for key, count in sorted(key_counts.items()):
        print(f"  {key:<24} {count}/{len(predictions)}")

    # 2) A couple of complete objects, pretty-printed, so we can see the values
    #    and nesting, not just the names.
    print("\n" + "=" * 68)
    print(f"FIRST {FULL_DUMPS} PREDICTIONS IN FULL (raw JSON)")
    print("=" * 68)
    for i, p in enumerate(predictions[:FULL_DUMPS]):
        print(f"\n--- prediction #{i + 1} ---")
        print(json.dumps(p, indent=2))

    # 3) A focused look at the handful of fields the Watcher will likely lean on,
    #    IF they exist — printed defensively so a missing name can't crash this.
    print("\n" + "=" * 68)
    print("FIELDS THE WATCHER WILL PROBABLY NEED (best-guess names — confirm above)")
    print("=" * 68)
    likely = [
        "vehicleId", "destinationName", "towards", "direction",
        "stationName", "naptanId", "lineName", "expectedArrival", "timeToStation",
    ]
    sample = predictions[0]
    for name in likely:
        present = name in sample
        marker = "ok " if present else "?? "
        value = sample.get(name, "(absent)")
        print(f"  [{marker}] {name:<18} = {value}")


if __name__ == "__main__":
    main()
