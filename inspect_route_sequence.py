#!/usr/bin/env python3
"""
inspect_route_sequence.py — inspection spike for task T2.4b.

Its ONE job: print the shape of TfL's route-sequence response so we can read off
the REAL field names for a route's *ordered* list of stops (and therefore its
terminus). We need this to tell "the bus finished normally at its last stop"
apart from "the bus turned back early" — the normal-terminus exclusion the
detector currently fakes with a placeholder.

Same golden rule as before (CLAUDE.md): confirm field names against a live
response, don't trust them from memory or the PRD.

Throwaway/reference code — reads nothing, writes nothing, only prints.

RUN IT (on your Mac):
    cd ~/Bus-app
    python3 inspect_route_sequence.py

Then paste everything it prints back into the chat.
"""

import json

import tfl_client

ROUTE = "38"
# TfL serves a separate ordered sequence per direction. We look at both because
# a route's terminus differs by direction (outbound ends one place, inbound the
# other).
DIRECTIONS = ["outbound", "inbound"]


def inspect_direction(direction):
    print("=" * 68)
    print(f"ROUTE {ROUTE} — direction: {direction}")
    print("=" * 68)

    try:
        data = tfl_client.get(f"/Line/{ROUTE}/Route/Sequence/{direction}")
    except tfl_client.TflError as exc:
        print(f"  could not fetch: {exc}")
        return

    if not isinstance(data, dict):
        print(f"  unexpected top-level type: {type(data).__name__}")
        print(json.dumps(data, indent=2)[:800])
        return

    # 1) Top-level field names — the menu we choose from.
    print("\nTOP-LEVEL KEYS:")
    for key in sorted(data.keys()):
        val = data[key]
        kind = type(val).__name__
        size = f" (len {len(val)})" if isinstance(val, (list, dict, str)) else ""
        print(f"  {key:<22} {kind}{size}")

    # 2) The ordered stops. TfL usually nests these under 'stopPointSequences';
    #    we look there but fall back gracefully if the name differs.
    sequences = data.get("stopPointSequences")
    if not isinstance(sequences, list) or not sequences:
        print("\n  No 'stopPointSequences' list found — dumping a trimmed raw copy")
        print("  so we can see where the ordered stops actually live:")
        print(json.dumps(data, indent=2)[:1500])
        return

    print(f"\n'stopPointSequences' holds {len(sequences)} sequence(s).")
    first = sequences[0]
    print("KEYS on a sequence:", sorted(first.keys()) if isinstance(first, dict) else type(first).__name__)

    stops = first.get("stopPoint") if isinstance(first, dict) else None
    if not isinstance(stops, list) or not stops:
        print("  Could not find a 'stopPoint' list on the first sequence; raw copy:")
        print(json.dumps(first, indent=2)[:1500])
        return

    # 3) One full stop entry, so we see the exact field names per stop.
    print(f"\nFirst sequence has {len(stops)} stops. One full stop entry (raw):")
    print(json.dumps(stops[0], indent=2))

    # 4) The ordered list itself, first few + last few — the terminus is the
    #    last entry. We print id + name using best-guess names, defensively.
    def stop_id(s):
        return s.get("id") or s.get("stationId") or s.get("naptanId") or "?"

    def stop_name(s):
        return s.get("name") or s.get("stationName") or "?"

    print("\nORDERED STOPS (first 3):")
    for s in stops[:3]:
        print(f"  {stop_id(s):<16} {stop_name(s)}")
    print("  ...")
    print("ORDERED STOPS (last 3 — the terminus is the final one):")
    for s in stops[-3:]:
        print(f"  {stop_id(s):<16} {stop_name(s)}")


def main():
    print(f"Key detected: {tfl_client.has_key()}\n")
    for direction in DIRECTIONS:
        inspect_direction(direction)
        print()


if __name__ == "__main__":
    main()
