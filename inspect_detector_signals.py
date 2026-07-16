#!/usr/bin/env python3
"""
inspect_detector_signals.py — live spike for the detector redesign (task R0).

Before rebuilding the detector to be state-based and route-position-aware, we
need three facts confirmed against live data (CLAUDE.md golden rule: never
assume field shapes/behaviour). For a sample of real buses on each watched
route this script prints what we need to answer:

  Q1. HORIZON — do a bus's predicted stops reach all the way to its
      destination / the route terminus, or only a rolling window? (Decides
      whether "reach falls short of terminus" is a valid curtailment signal.)

  Q2. NAPTAN MATCH — do the arrivals `naptanId`s actually line up with the
      route-sequence stop ids, so we can place a prediction at a route position?

  Q3. DESTINATION -> POSITION — does `destinationName` match a stop *name* in
      the route sequence (so we can tell a shortened destination from a longer
      one by route order)?

Also prints `tripId` per bus so we can see it's per-journey (the key we want to
use to separate a bus's successive journeys).

Throwaway/reference code: reads nothing, writes nothing, only prints.

RUN IT (on your Mac):
    cd ~/Bus-app
    python3 inspect_detector_signals.py

Then paste the output back into the chat.
"""

from collections import Counter

import config
import tfl_client

DIRECTIONS = ["outbound", "inbound"]
SAMPLE_BUSES_PER_ROUTE = 4   # keep the output readable


def build_sequence_map(route, direction):
    """Return position/name lookups for a route+direction's ordered stops.

    {"pos_by_naptan": {naptanId: index},
     "pos_by_name":   {stop name: index},
     "ordered":       [naptanId, ...],
     "terminus_naptan": naptanId or None,
     "terminus_name":   str or None}
    """
    data = tfl_client.get(f"/Line/{route}/Route/Sequence/{direction}")
    sequences = data.get("stopPointSequences") or []
    pos_by_naptan = {}
    pos_by_name = {}
    ordered = []
    for seq in sequences:
        for stop in seq.get("stopPoint") or []:
            nid = stop.get("id")
            name = stop.get("name")
            if nid and nid not in pos_by_naptan:
                pos_by_naptan[nid] = len(ordered)
                ordered.append((nid, name))
                if name and name not in pos_by_name:
                    pos_by_name[name] = pos_by_naptan[nid]
    terminus_naptan = ordered[-1][0] if ordered else None
    terminus_name = ordered[-1][1] if ordered else None
    return {
        "pos_by_naptan": pos_by_naptan,
        "pos_by_name": pos_by_name,
        "ordered": ordered,
        "terminus_naptan": terminus_naptan,
        "terminus_name": terminus_name,
    }


def _most_common(values):
    values = [v for v in values if v]
    return Counter(values).most_common(1)[0][0] if values else ""


def inspect_route(route):
    print("#" * 70)
    print(f"# ROUTE {route}")
    print("#" * 70)

    # Route sequence maps per direction (the ordered stops + terminus).
    maps = {}
    for direction in DIRECTIONS:
        try:
            maps[direction] = build_sequence_map(route, direction)
            m = maps[direction]
            print(f"  {direction}: {len(m['ordered'])} stops, "
                  f"terminus = {m['terminus_name']!r} ({m['terminus_naptan']})")
        except tfl_client.TflError as exc:
            print(f"  {direction}: could not fetch sequence: {exc}")

    # Live arrivals for the whole route (both directions in one list).
    try:
        arrivals = tfl_client.get(f"/Line/{route}/Arrivals")
    except tfl_client.TflError as exc:
        print(f"  could not fetch arrivals: {exc}")
        return
    if not isinstance(arrivals, list) or not arrivals:
        print("  no live arrivals right now (route quiet?) — try again shortly.")
        return

    # Group predictions by bus.
    by_vehicle = {}
    for p in arrivals:
        vid = p.get("vehicleId")
        if vid:
            by_vehicle.setdefault(vid, []).append(p)

    print(f"\n  {len(by_vehicle)} buses live. Sampling up to "
          f"{SAMPLE_BUSES_PER_ROUTE}:\n")

    for vid, rows in list(by_vehicle.items())[:SAMPLE_BUSES_PER_ROUTE]:
        direction = _most_common([r.get("direction") for r in rows])
        destination = _most_common([r.get("destinationName") for r in rows])
        trip = _most_common([str(r.get("tripId")) for r in rows])
        smap = maps.get(direction)

        print(f"  bus {vid}  trip={trip}  dir={direction}  dest={destination!r}")

        if not smap:
            print("      (no sequence map for this direction — skipping positions)\n")
            continue

        # Place each predicted stop at its route position.
        pos_by_naptan = smap["pos_by_naptan"]
        rows_sorted = sorted(rows, key=lambda r: r.get("timeToStation", 10**9))
        positions = []
        matched = 0
        for r in rows_sorted:
            pos = pos_by_naptan.get(r.get("naptanId"))
            if pos is not None:
                matched += 1
                positions.append(pos)

        terminus_pos = len(smap["ordered"]) - 1
        furthest_pos = max(positions) if positions else None
        nearest_pos = min(positions) if positions else None

        # Q2: naptan match rate.
        print(f"      stops predicted: {len(rows_sorted)}, "
              f"matched to route position: {matched}/{len(rows_sorted)}")
        # Q1: horizon — furthest predicted position vs terminus position.
        if furthest_pos is not None:
            print(f"      route positions predicted: {nearest_pos}..{furthest_pos} "
                  f"of 0..{terminus_pos} (terminus)")
            reaches = "YES" if furthest_pos >= terminus_pos else "no"
            print(f"      reaches terminus position? {reaches} "
                  f"(gap to terminus = {terminus_pos - furthest_pos})")
        # Q3: destination name -> position.
        dest_pos = smap["pos_by_name"].get(destination)
        if dest_pos is not None:
            print(f"      destination matches a route stop name at position {dest_pos}")
        else:
            print(f"      destination {destination!r} NOT found among route stop names")
        print()


def main():
    print(f"Key detected: {tfl_client.has_key()}")
    print(f"Routes: {', '.join(config.ROUTES)}\n")
    for route in config.ROUTES:
        inspect_route(route)


if __name__ == "__main__":
    main()
