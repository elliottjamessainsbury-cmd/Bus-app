"""
watcher.py — the Watcher (PRD §6.1, FR4–FR8).

Task T2.2 covers the first two jobs:
  * fetch the live arrivals for a route, and
  * boil that flat list of predictions down into one tidy snapshot per bus.

Later tasks add remembering the previous cycle (T2.3), the curtailment
heuristic (T2.4), and the continuous resilient loop (T2.5).

Why "per bus"? TfL's arrivals feed is a flat list where ONE bus (`vehicleId`)
appears in many rows — one row per upcoming stop it is predicted to reach (see
TFL_API_NOTES.md). To reason about a bus we first regroup those rows by
`vehicleId`, giving each bus the full set of stops it currently "reaches".
"""

from dataclasses import dataclass, field
from collections import Counter

import tfl_client


@dataclass
class VehicleState:
    """One bus's snapshot for a single poll cycle.

    predicted_stops maps a stop's naptanId -> details we care about:
        {"name": <stationName>, "time_to_station": <seconds>,
         "expected_arrival": <iso8601>}
    Keeping the whole set is what lets the detector later notice the set
    shrinking back up the line (Trigger B).
    """
    vehicle_id: str
    route: str            # lineId, e.g. "38"
    direction: str        # "inbound" / "outbound" / "" if unknown
    destination: str      # destinationName, e.g. "Piccadilly Circus"
    predicted_stops: dict = field(default_factory=dict)

    @property
    def furthest_stop(self):
        """The naptanId of the stop this bus reaches *latest* — i.e. the one
        with the largest time_to_station. That is its current "reach" up the
        line. Returns None if it somehow has no timed stops.

        [Within a single bus, a bigger time_to_station means further along its
        remaining journey, so the max marks how far ahead it still predicts.]
        """
        timed = {
            naptan: info["time_to_station"]
            for naptan, info in self.predicted_stops.items()
            if info.get("time_to_station") is not None
        }
        if not timed:
            return None
        return max(timed, key=timed.get)

    def furthest_stop_name(self):
        """Human-readable name of the furthest stop, for logs. '' if none."""
        naptan = self.furthest_stop
        if naptan is None:
            return ""
        return self.predicted_stops[naptan].get("name", "")


def extract_vehicle_states(predictions):
    """Turn TfL's flat arrivals list into {vehicleId: VehicleState}.

    `predictions` is the list returned by /Line/{id}/Arrivals. This function is
    deliberately pure (no network, no clock) so it is easy to test against saved
    responses.

    Rows without a `vehicleId` are skipped — we can't track a bus we can't name.
    If the same bus predicts the same stop more than once in a cycle (rare), we
    keep the *soonest* (smallest time_to_station), since that is the live one.
    """
    # Gather each bus's rows first, so we can resolve per-bus fields (like
    # destination and direction) across all of them rather than trusting one row.
    rows_by_vehicle = {}
    for p in predictions:
        if not isinstance(p, dict):
            continue
        vehicle_id = p.get("vehicleId")
        if not vehicle_id:
            continue
        rows_by_vehicle.setdefault(vehicle_id, []).append(p)

    states = {}
    for vehicle_id, rows in rows_by_vehicle.items():
        predicted_stops = {}
        for r in rows:
            naptan = r.get("naptanId")
            if not naptan:
                continue
            time_to_station = r.get("timeToStation")
            existing = predicted_stops.get(naptan)
            # Keep the soonest prediction if a stop appears twice.
            if existing is not None and existing.get("time_to_station") is not None \
                    and time_to_station is not None \
                    and existing["time_to_station"] <= time_to_station:
                continue
            predicted_stops[naptan] = {
                "name": r.get("stationName", ""),
                "time_to_station": time_to_station,
                "expected_arrival": r.get("expectedArrival", ""),
            }

        states[vehicle_id] = VehicleState(
            vehicle_id=vehicle_id,
            route=_most_common(rows, "lineId"),
            direction=_most_common(rows, "direction"),
            destination=_most_common(rows, "destinationName"),
            predicted_stops=predicted_stops,
        )
    return states


def _most_common(rows, key):
    """The most frequent non-empty value of `key` across a bus's rows.

    Destination/direction/line should be identical on every row for one bus, but
    taking the majority value is robust to the odd stale or blank row.
    """
    values = [r.get(key) for r in rows if r.get(key)]
    if not values:
        return ""
    return Counter(values).most_common(1)[0][0]


def fetch_vehicle_states(route):
    """Live path: fetch this route's arrivals from TfL and extract per-bus state.

    Thin wrapper around the API so the pure extraction above stays testable.
    Raises tfl_client.TflError on any API failure (the loop in T2.5 will catch
    it and skip the cycle — PRD FR8).
    """
    predictions = tfl_client.get(f"/Line/{route}/Arrivals")
    if not isinstance(predictions, list):
        raise tfl_client.TflError(
            f"expected a list of predictions for route {route}, "
            f"got {type(predictions).__name__}"
        )
    return extract_vehicle_states(predictions)


@dataclass
class VehicleDiff:
    """What changed for one bus that was present in BOTH cycles.

    All fields are plain facts about the change — no judgement about whether it
    is a curtailment. That interpretation happens in T2.4, which reads these.
    `stops_dropped` / `stops_added` are sets of naptanIds.
    """
    vehicle_id: str
    old: VehicleState
    new: VehicleState
    destination_changed: bool
    stops_dropped: set = field(default_factory=set)
    stops_added: set = field(default_factory=set)
    furthest_changed: bool = False

    @property
    def has_change(self):
        """True if anything at all moved — used to decide whether this bus is
        worth reporting in the cycle diff."""
        return (
            self.destination_changed
            or self.furthest_changed
            or bool(self.stops_dropped)
            or bool(self.stops_added)
        )

    def describe(self):
        """One-line human summary, for eyeballing during development."""
        parts = []
        if self.destination_changed:
            parts.append(f"destination {self.old.destination!r} -> {self.new.destination!r}")
        if self.furthest_changed:
            parts.append(
                f"reach {self.old.furthest_stop_name()!r} -> {self.new.furthest_stop_name()!r}"
            )
        if self.stops_dropped:
            parts.append(f"-{len(self.stops_dropped)} stops")
        if self.stops_added:
            parts.append(f"+{len(self.stops_added)} stops")
        return f"bus {self.vehicle_id} ({self.new.route}): " + "; ".join(parts)


@dataclass
class CycleDiff:
    """Everything that changed between the previous cycle and this one."""
    appeared: dict = field(default_factory=dict)   # vehicleId -> VehicleState (new only)
    vanished: dict = field(default_factory=dict)   # vehicleId -> VehicleState (gone)
    changed: dict = field(default_factory=dict)    # vehicleId -> VehicleDiff (moved)

    def summarise(self):
        lines = [
            f"cycle diff: {len(self.appeared)} appeared, "
            f"{len(self.vanished)} vanished, {len(self.changed)} changed"
        ]
        for vd in self.changed.values():
            lines.append("  " + vd.describe())
        return "\n".join(lines)


def _diff_vehicle(old, new):
    """Compare one bus's old vs new snapshot and return a VehicleDiff."""
    old_stops = set(old.predicted_stops)
    new_stops = set(new.predicted_stops)
    return VehicleDiff(
        vehicle_id=new.vehicle_id,
        old=old,
        new=new,
        destination_changed=(old.destination != new.destination),
        stops_dropped=old_stops - new_stops,
        stops_added=new_stops - old_stops,
        furthest_changed=(old.furthest_stop != new.furthest_stop),
    )


def diff_cycles(old_states, new_states):
    """Diff two cycles of {vehicleId: VehicleState}.

    Returns a CycleDiff splitting buses into appeared (new this cycle), vanished
    (gone this cycle), and changed (in both, with something different). Buses in
    both cycles with no change are simply omitted.
    """
    old_ids = set(old_states)
    new_ids = set(new_states)

    appeared = {vid: new_states[vid] for vid in new_ids - old_ids}
    vanished = {vid: old_states[vid] for vid in old_ids - new_ids}

    changed = {}
    for vid in old_ids & new_ids:
        vd = _diff_vehicle(old_states[vid], new_states[vid])
        if vd.has_change:
            changed[vid] = vd

    return CycleDiff(appeared=appeared, vanished=vanished, changed=changed)


class CycleTracker:
    """Holds the previous cycle's states in memory and diffs each new cycle
    against it (PRD FR6 — "maintain the previous cycle's state so consecutive
    cycles can be compared").

    Usage each poll:
        diff = tracker.update(new_states)
    The very first update has no previous cycle, so every bus shows up as
    'appeared' and nothing is 'changed'.
    """

    def __init__(self):
        self.previous = {}  # vehicleId -> VehicleState

    def update(self, new_states):
        diff = diff_cycles(self.previous, new_states)
        self.previous = new_states  # remember for next time
        return diff


def summarise_states(states, limit=10):
    """Return a short human-readable summary of a cycle's states, for eyeballing
    during development (the T2.2 test / a quick manual run)."""
    lines = [f"{len(states)} buses currently active"]
    for vs in list(states.values())[:limit]:
        lines.append(
            f"  bus {vs.vehicle_id} ({vs.route} {vs.direction}) "
            f"-> {vs.destination} | {len(vs.predicted_stops)} stops predicted, "
            f"reach = {vs.furthest_stop_name()!r}"
        )
    if len(states) > limit:
        lines.append(f"  ... and {len(states) - limit} more")
    return "\n".join(lines)
