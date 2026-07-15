"""
detector.py — the curtailment heuristic (PRD §9).

Reads the neutral cycle diffs produced by watcher.py and decides which buses
look *curtailment-shaped*, applying the §9 triggers and noise filters. When a
signal has persisted long enough it produces a ready-to-store `auto` event row
(PRD §7 schema).

Task split:
  * T2.4a (this file now): Trigger A/B, persistence K, single-cycle-vanish
    grace, confidence, and event construction — all testable offline.
  * T2.4b (next): wire in the real "normal terminus" exclusion once we have the
    route's ordered stops. Until then the terminus check is a placeholder that
    assumes a dropped stop is NOT the terminus, so on live data this will
    over-flag buses finishing normally. That's expected and fixed in T2.4b.

The triggers (comparing a bus's previous snapshot to its current one):
  * Trigger A — stated destination shortens (changes to a different terminus).
  * Trigger B — the reach retreats: the previously-furthest stop has dropped
    off while nearer stops remain. (A bus travelling normally sheds its NEAREST
    stops and keeps its furthest, so a lost FURTHEST stop is the curtailment
    shape.)
"""

import uuid
from datetime import datetime, timezone


def _utc_now_iso():
    """Current UTC time as an ISO 8601 string, matching how the store holds
    timestamps (see store.py)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Detector:
    """Turns a stream of cycle diffs into suspected-curtailment event rows.

    Parameters
    ----------
    k : int
        Persistence — how many consecutive cycles a trigger must hold before an
        event is recorded (config.PERSISTENCE_K).
    is_normal_termination : callable(route, direction, naptan_id) -> bool
        Returns True if a bus dropping its furthest stop `naptan_id` is simply
        finishing normally at the route's scheduled terminus (so NOT a
        curtailment). Placeholder in T2.4a always returns False; T2.4b supplies
        the real, geometry-backed check.
    now_iso : callable() -> str
        Injectable clock, so tests get deterministic timestamps.
    """

    def __init__(self, k=2, is_normal_termination=None, now_iso=None):
        self.k = k
        self.is_normal_termination = is_normal_termination or (lambda r, d, n: False)
        self.now_iso = now_iso or _utc_now_iso
        # Per-bus running signal: vehicleId -> {count, triggers, recorded, missing}
        self.streaks = {}

    # ---- trigger detection ---------------------------------------------
    def _triggers(self, vd):
        """Which §9 triggers fired for one bus's diff this cycle. Returns a set
        drawn from {"A", "B"} (empty if none)."""
        fired = set()

        # Trigger A: destination shortened (changed to a different, real terminus).
        if vd.destination_changed and vd.new.destination:
            fired.add("A")

        # Trigger B: the previously-furthest stop dropped off, the bus is still
        # active (still predicts some stops), and that dropped stop isn't just
        # the route's normal terminus being reached.
        old_furthest = vd.old.furthest_stop
        if (
            old_furthest is not None
            and old_furthest in vd.stops_dropped
            and vd.new.predicted_stops
            and not self.is_normal_termination(vd.new.route, vd.new.direction, old_furthest)
        ):
            fired.add("B")

        return fired

    # ---- confidence -----------------------------------------------------
    def _confidence(self, triggers, count):
        """A coarse label so weak and strong signals can be told apart in
        analysis (PRD §9). Stronger when both triggers fire and/or the signal
        has persisted beyond the minimum K cycles."""
        both = len(triggers) >= 2
        persisted = count > self.k
        if both and persisted:
            return "high"
        if both or persisted:
            return "medium"
        return "low"

    # ---- event construction --------------------------------------------
    def _make_event(self, vehicle_id, streak, vd):
        """Build one `auto` event row (dict keyed by store.py columns)."""
        triggers = streak["triggers"]
        # expected terminus = where it was heading before; apparent = where it
        # now seems to end (its shortened destination, or its shrunken reach).
        expected = vd.old.destination
        if "A" in triggers and vd.new.destination:
            apparent = vd.new.destination
        else:
            apparent = vd.new.furthest_stop_name()

        trigger_names = "+".join(sorted(triggers))
        return {
            "event_id": str(uuid.uuid4()),
            "source": "auto",
            "detected_at": self.now_iso(),
            "route": vd.new.route,
            "direction": vd.new.direction,
            "vehicle_id": vehicle_id,
            "last_seen_stop": vd.new.furthest_stop_name(),
            "expected_terminus": expected,
            "apparent_terminus": apparent,
            "event_type": "curtailment_suspected",
            "near_closure": None,       # Enricher fills this later
            "closure_desc": None,       # Enricher fills this later
            "confidence": self._confidence(triggers, streak["count"]),
            "notes": (
                f"triggers={trigger_names}; persisted={streak['count']} cycles; "
                f"dropped {len(vd.stops_dropped)} stops"
            ),
        }

    # ---- main entry point ----------------------------------------------
    def process(self, cycle_diff, current_vehicle_ids):
        """Advance the detector by one cycle.

        `cycle_diff` is a watcher.CycleDiff; `current_vehicle_ids` is the set of
        vehicleIds seen in THIS cycle (used to tell a broken signal from a bus
        that merely vanished for a cycle). Returns a list of new event rows
        recorded this cycle (usually empty).
        """
        events = []

        # 1) Which buses fired a trigger this cycle?
        fired_this_cycle = {}
        for vid, vd in cycle_diff.changed.items():
            triggers = self._triggers(vd)
            if triggers:
                fired_this_cycle[vid] = (triggers, vd)

        # 2) Extend each firing bus's streak; record once it reaches K.
        for vid, (triggers, vd) in fired_this_cycle.items():
            st = self.streaks.setdefault(
                vid, {"count": 0, "triggers": set(), "recorded": False, "missing": 0}
            )
            st["count"] += 1
            st["triggers"] |= triggers
            st["missing"] = 0
            if st["count"] >= self.k and not st["recorded"]:
                events.append(self._make_event(vid, st, vd))
                st["recorded"] = True

        # 3) Age every other tracked bus.
        for vid in list(self.streaks):
            if vid in fired_this_cycle:
                continue
            if vid in current_vehicle_ids:
                # Present but no trigger this cycle -> the signal broke. Reset.
                del self.streaks[vid]
            else:
                # Absent -> tolerate a single-cycle disappearance (blip), then drop.
                self.streaks[vid]["missing"] += 1
                if self.streaks[vid]["missing"] >= 2:
                    del self.streaks[vid]

        return events
