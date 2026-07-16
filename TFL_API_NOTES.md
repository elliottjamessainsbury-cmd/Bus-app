# TfL API field notes — confirmed against live responses

Per the CLAUDE.md golden rule ("do not trust API field names from the PRD or
from memory; confirm against live responses"), this file records field names we
have **seen in real responses**, with the date and endpoint. Update it whenever
we confirm a new endpoint.

---

## `GET /Line/{id}/Arrivals`

Confirmed live for route `38` on 2026-07-15 (370 predictions). Returns a **flat
JSON list** of prediction objects. Every field below was present in 370/370
rows.

**Crucial shape fact:** one bus (`vehicleId`) appears in **many** rows — one row
per upcoming stop it is currently predicted to reach. So to get a single bus's
state, you **group the list by `vehicleId`** and collect its stops.

### Fields the Watcher uses

| Field | Example | Watcher role |
|---|---|---|
| `vehicleId` | `"LTZ1522"` | Identify one physical bus across poll cycles. → `events.vehicle_id` |
| `lineId` | `"38"` | The route. → `events.route` |
| `direction` | `"outbound"` / `"inbound"` | → `events.direction` |
| `naptanId` | `"490006008W"` | The stop **this prediction is for**. The set of these per vehicle = the stops it's predicting to. |
| `stationName` | `"Dean Street / Chinatown"` | Human name of that stop (for readable logs / `last_seen_stop`). |
| `timeToStation` | `1665` | Seconds until the bus reaches that stop. The **largest** value for a vehicle marks its furthest-ahead ("reach") stop. |
| `destinationName` | `"Piccadilly Circus"` | The bus's stated destination. A change to an earlier stop = **Trigger A**. → `expected`/`apparent_terminus` |
| `expectedArrival` | `"2026-07-15T13:14:53Z"` | ISO 8601 predicted arrival time at that stop. |
| `timestamp` | `"2026-07-15T12:47:08Z"` | When TfL generated this snapshot. |

### Other fields present (not needed yet, noted for completeness)
`$type`, `id` (prediction id), `operationType`, `platformName`, `bearing`,
`tripId`, `baseVersion`, `modeName`, `timeToLive`, `towards`, `currentLocation`,
`lineName`, `timing` (a nested object of server clock adjustments).

### Gotchas confirmed
- **`destinationNaptanId` is empty (`""`)** in the live data — do **not** rely on
  it. Use `destinationName` for the destination.
- `lineName` exists **here** (arrivals) but the `/Line/{id}/Route` endpoint uses
  `name` instead — endpoints differ, which is exactly why we confirm each one.

---

## Per-vehicle state the Watcher derives (from the above)

Grouping the arrivals list by `vehicleId`, each bus becomes:

- **predicted_stops** — the set of `naptanId` it currently predicts for.
- **furthest_stop / reach** — the `naptanId` with the largest `timeToStation`
  (how far ahead it still expects to run).
- **destination** — `destinationName` (consistent across its rows).
- **direction** — `direction`.

Comparing one cycle to the next for the same `vehicleId` gives the §9 triggers:

- **Trigger A (destination shortens):** `destinationName` changes to a stop
  earlier along the route than before.
- **Trigger B (predictions retreat):** downstream `naptanId`s it predicted for
  disappear while upstream ones remain — its reach shrinks back up the line.

## `GET /Line/{id}/Route/Sequence/{direction}`

Confirmed live for route `38`, both directions, on 2026-07-15. `{direction}` is
`outbound` or `inbound` (same words the arrivals feed uses). Returns a **dict**.

The ordered stops live at:

    stopPointSequences[0].stopPoint   # a list, in travel order

Each entry in that `stopPoint` list is a stop with (fields we use):

| Field | Example | Use |
|---|---|---|
| `id` | `"490009035E"` | The stop's **naptanId** — same id style as the arrivals `naptanId`, so they match directly. |
| `name` | `"Clapton Pond"` | Readable stop name. |

The **terminus is the last entry** of the `stopPoint` list. Confirmed:
- outbound (44 stops): first = Clapton Pond, **last = Victoria Bus Station
  (`490014050D`)**.
- inbound (45 stops): first = Victoria Bus Station, **last = Lea Bridge
  Roundabout (`490009035L`)**.

### Gotchas / notes
- Naptan ids are **direction- and side-specific** (opposite-side stops have
  different ids), so match arrivals→sequence by the exact `id`, per direction.
- Each stop also carries a `lines` list (every route serving it), `stationId` /
  `parentId` / `topMostParentId` (hub-level ids — do NOT use these for matching;
  use `id`), plus `lat`/`lon`.
- `stopPointSequences` can in principle hold more than one sequence (branching
  routes); route 38 has exactly 1 per direction. Our geometry helper treats the
  last stop of *each* sequence as a terminus, to be safe on branched routes.

## Still to confirm (future inspection spikes)
- **Route disruption text** and **road disruption polygons** — for the Enricher
  (Slice 4).
