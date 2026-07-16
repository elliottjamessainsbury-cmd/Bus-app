#!/usr/bin/env python3
"""
run_watcher.py — the Watcher's continuous run loop (PRD FR4–FR8).

This is the entry point that actually *runs* the instrument. Every poll cycle it:
  1. fetches live arrivals for each watched route and extracts per-bus state,
  2. diffs against the previous cycle (stateful),
  3. runs the curtailment detector,
  4. stores any suspected-curtailment events, and
  5. sleeps, then repeats.

It ties together every module we built:
    config -> tfl_client -> watcher -> detector -> route_geometry -> store

Resilience (FR8): a single bad route or a bad cycle is logged and skipped — it
never kills the process. The instrument is meant to run unattended for weeks.

RUN IT (on your Mac):
    cd ~/Bus-app
    python3 run_watcher.py 38          # watch just route 38
    python3 run_watcher.py             # watch every route in config.ROUTES
Stop it any time with Ctrl-C.
"""

import sys
import time
from datetime import datetime, timezone

import config
import tfl_client
import watcher
import detector
import route_geometry
import store


def run_cycle(routes, tracker, det, db_path=None,
              fetch_states=None, logger=print):
    """Do exactly one poll cycle across `routes`.

    Isolated from the loop and the clock so it can be tested with an injected
    `fetch_states` and no real network. Returns (states, diff, events).

    A route that fails to fetch is logged and skipped this cycle — its buses
    simply look absent, which the detector tolerates as a one-cycle blip.
    """
    fetch_states = fetch_states or watcher.fetch_vehicle_states

    all_states = {}
    for route in routes:
        try:
            all_states.update(fetch_states(route))
        except tfl_client.TflError as exc:
            logger(f"  ! route {route} skipped this cycle: {exc}")

    diff = tracker.update(all_states)
    events = det.process(diff, set(all_states))
    for event in events:
        store.insert_event(event, db_path)
    return all_states, diff, events


def _now_hms():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def run(routes=None, db_path=None, poll_interval=None, max_cycles=None,
        fetch_states=None, is_normal_termination=None,
        sleep_fn=time.sleep, logger=print):
    """Start the Watcher.

    routes         : list of line ids to watch (default config.ROUTES).
    max_cycles     : stop after this many cycles (default None = run forever).
                     Used by tests to run a bounded number of cycles.
    fetch_states / is_normal_termination / sleep_fn : injectable seams for tests.
    """
    routes = routes or config.ROUTES
    poll_interval = config.POLL_INTERVAL_SECONDS if poll_interval is None else poll_interval
    is_normal_termination = is_normal_termination or route_geometry.is_normal_termination

    # --- startup -------------------------------------------------------
    store.init_db(db_path)
    loaded = route_geometry.preload(routes)

    logger("=" * 60)
    logger("Bus Curtailment Watcher starting")
    logger(f"  routes         : {', '.join(routes)}")
    logger(f"  poll interval  : {poll_interval}s")
    logger(f"  persistence K  : {config.PERSISTENCE_K}")
    logger(f"  TfL key present: {tfl_client.has_key()}")
    logger(f"  geometry loaded: {len(loaded)}/{len(routes) * 2} route-directions")
    logger(f"  event store    : {db_path or config.DB_PATH}")
    logger("=" * 60)

    tracker = watcher.CycleTracker()
    det = detector.Detector(
        k=config.PERSISTENCE_K,
        is_normal_termination=is_normal_termination,
    )

    # --- the loop ------------------------------------------------------
    cycle = 0
    while max_cycles is None or cycle < max_cycles:
        cycle += 1
        try:
            states, diff, events = run_cycle(
                routes, tracker, det, db_path, fetch_states, logger
            )
            summary = (
                f"[{_now_hms()}] cycle {cycle}: {len(states)} buses, "
                f"{len(diff.changed)} changed, {len(events)} event(s) recorded"
            )
            if events:
                summary += " <-- CURTAILMENT SUSPECTED"
            logger(summary)
            for event in events:
                logger(
                    f"    route {event['route']} bus {event['vehicle_id']}: "
                    f"{event['expected_terminus']} -> {event['apparent_terminus']} "
                    f"({event['confidence']}; {event['notes']})"
                )
        except Exception as exc:  # noqa: BLE001 - deliberately broad (FR8)
            # Any unexpected error in a cycle must not kill the process.
            logger(f"  ! cycle {cycle} error (skipped, not fatal): {exc}")

        # Sleep between cycles, but not after the final one.
        if max_cycles is None or cycle < max_cycles:
            sleep_fn(poll_interval)

    return cycle


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    routes = argv or config.ROUTES
    try:
        run(routes=routes)
    except KeyboardInterrupt:
        print("\nStopped by user. The event store is saved.")


if __name__ == "__main__":
    main()
