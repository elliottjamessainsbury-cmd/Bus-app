# PRD: Bus Curtailment Validation Instrument

**Status:** Draft for review
**Author:** Elliott
**Type:** Internal validation / research instrument (NOT the consumer product)
**Build target:** Claude Code

---

## 1. Overview

A small, single-operator tool that watches many London bus routes at once, automatically flags buses that *look* like they terminated early ("curtailment"), checks whether a known road or route closure could explain each one, and lets me log what I *actually* saw in the real world. The point is to gather enough evidence to answer one question before we build any user-facing feature:

> **When a bus terminates early, can TfL's open data reliably tell us – or at least explain why?**

This is a measuring instrument, not a product. It has no consumer UI and sends no alerts to anyone. Its only output is data and a summary report that tells me whether the curtailment feature is worth building, worth shipping with a disclaimer, or worth cutting.

---

## 2. Background & problem

The wider project is a London bus app that surfaces things Google Maps and Citymapper bury: per-route, per-stop arrivals for the stops you actually use, bus-stop closure status, and – the hardest one – early termination ("curtailment").

Curtailment is hard because **TfL publishes no clean "this bus turned back early" signal.** It can only be *inferred* (worked out indirectly) by watching a bus's live arrival predictions disappear from the stops further down its route. That inference is noisy, so before building it we need to know how often the inference is right, and how often a road closure explains the event.

Two facts make a dedicated instrument necessary:

- **Curtailment is rare per route** (roughly every few weeks on any single route), so watching only 3 routes would take months to learn anything. We widen the net to many routes purely to gather events faster.
- **Only a human on the bus knows the truth.** The automated detector produces *guesses*; road data produces *possible causes*; neither knows what really happened. So we must also capture real-world observations to check the guesses against.

---

## 3. Goal & the question we're answering

Collect, over several weeks, a dataset of suspected curtailment events across many central London routes, enriched with possible road/route-closure causes, plus a smaller set of human-verified observations. Use it to measure:

1. How often a suspected curtailment coincides with a mapped road closure or a published route diversion (the **corroboration rate**).
2. For events I personally witnessed, how often the detector was right (**false-positive rate**) and how often it missed a real one (**false-negative rate**).

---

## 4. Scope

**In scope (what this IS):**
- A persistent background "watcher" polling many routes.
- Automatic detection of curtailment-shaped events.
- Enrichment of each event with possible road/route-closure causes.
- A dead-simple way for me to log real-world observations.
- A shared store so automated guesses and my observations sit in the same format.
- A summary report answering the question in section 3.

**Out of scope (what this is NOT) – see also Non-Goals, section 13:**
- The consumer app, its UI, saved-routes/saved-stops features, or any user-facing alerts.
- National or non-London coverage.
- Perfect accuracy. This tool measures accuracy; it doesn't need to be the final algorithm.

---

## 5. Glossary

Plain-language definitions so the requirements below read cleanly:

- **Polyline** – a line made of connected points (dot-to-dot). A bus route's path on a map is a polyline.
- **Polygon** – a closed loop fencing off an area. A road closure's affected zone is a polygon.
- **Intersection** – the spot where two shapes overlap (e.g. does the route polyline cross the closure polygon?).
- **Buffer** – fattening a line by a set margin so we also catch closures *beside* the route, not only ones it crosses exactly.
- **Stateful / watcher** – a program that keeps running and *remembers* the previous moment, so it can notice change over time (needed because curtailment = "predictions that were there have vanished").
- **Inference** – working something out indirectly from clues, because it isn't stated directly.
- **Ground truth** – the verified real-world fact of what actually happened, as opposed to a guess.
- **False positive** – the detector cried "curtailment" but there wasn't one.
- **False negative** – a real curtailment happened but the detector missed it.
- **Naptan / ATCO ID** – TfL's unique id for a stop (looks like `490008766S`).
- **Spike** – a quick throwaway experiment to test one risky assumption. (Our earlier `tfl_closure_check.py` was a spike. This instrument is a step up from that.)

---

## 6. How it works (architecture in plain terms)

Three parts writing into one shared store:

1. **The Watcher (automated, stateful).** Every ~30 seconds it asks TfL for the live bus predictions on each configured route, remembers what it saw last time, and compares the two. When a bus's predictions for stops further down its route disappear (or its stated destination shortens), it records a *suspected curtailment* event.

2. **The Enricher (corroboration).** For each suspected event, it checks TfL's published route disruptions (plain-text diversions) and road-closure polygons near where the bus was last seen, and records whether a closure plausibly coincides, plus the description. This is the "your bus may be diverted due to [X]" logic – used to *explain and corroborate*, never as the primary detector.

3. **The Manual Log (ground truth).** A no-friction way for me to record what I actually observed ("on the 38, diverted at Essex Rd, no next-stop info, terminated at Islington"). Writes one row, tagged as a human observation.

All three write into a **single shared store** using one schema (section 7), distinguished by a `source` field. Because guesses and truth share a format, comparing them later is a simple query, not a data-wrangling project.

---

## 7. Shared data schema

One table, `events`. Every row is one observation, whether automated or human.

| Field | Type | Meaning |
|---|---|---|
| `event_id` | text | Unique id for the row |
| `source` | text | `auto` (the Watcher) or `manual` (me) |
| `detected_at` | text (ISO 8601) | When the event was detected/observed |
| `route` | text | Line id, e.g. `38` |
| `direction` | text | `inbound` / `outbound` / `unknown` |
| `vehicle_id` | text | Bus id (auto only; blank for manual) |
| `last_seen_stop` | text | Furthest stop still predicted / where I last knew it was heading |
| `expected_terminus` | text | Where the bus *should* have ended |
| `apparent_terminus` | text | Where it *seemed* to stop short |
| `event_type` | text | `curtailment_suspected`, `diversion_observed`, `normal`, etc. |
| `near_closure` | boolean / null | Enricher: did a closure plausibly coincide? |
| `closure_desc` | text | Enricher: the disruption/closure text, if any |
| `confidence` | text / number | Auto only: how strong the signal was |
| `notes` | text | Free text (my description, or detector debug info) |

Recommended store: **SQLite** (a single self-contained database file – simple, queryable, no server). CSV is an acceptable lower-friction fallback if SQLite proves fiddly early on.

---

## 8. Functional requirements

**Configuration**
- **FR1.** The set of routes to watch is configurable in one place (start with ~40–50 central London routes for validation; the eventual product watches far fewer).
- **FR2.** Poll interval, buffer distance, and detection-sensitivity thresholds are all configurable, not hard-coded.
- **FR3.** The TfL API key is read from an environment variable, never hard-coded.

**The Watcher**
- **FR4.** Every poll cycle, fetch live arrival predictions for each configured route.
- **FR5.** For each bus (vehicle) seen, record the set of stops it is currently predicting for, its stated destination, and the furthest-along stop it still predicts to.
- **FR6.** Maintain the previous cycle's state in memory so consecutive cycles can be compared.
- **FR7.** Detect suspected curtailment per the heuristic in section 9 and write an `auto` event row.
- **FR8.** Run continuously and survive transient API errors (a failed cycle is logged and skipped, not fatal).

**The Enricher**
- **FR9.** For each suspected event, fetch the route's published disruption/diversion text and record it.
- **FR10.** For each suspected event, fetch road-closure polygons near the last-seen location and test them against the route polyline using a configurable buffer; record whether any coincides and its description.
- **FR11.** Enrichment may run at detection time or as a batch pass over stored events (implementer's choice; batch is fine).

**The Manual Log**
- **FR12.** Manual observations are captured via an external **Google Form** (build-vs-buy: nothing to build or host), with fields mirroring the relevant `events` columns. The form itself is set up once in Google Forms, not written in code.
- **FR13.** Provide an **import step** that loads the form's responses (from its linked Google Sheet, exported as CSV) into the `events` table, setting `source = manual` and mapping the form's submission timestamp to `detected_at`.

**Reporting**
- **FR14.** Provide a summary command that reports: total events, corroboration rate (share of suspected curtailments with a coinciding closure), and – for events with a matching manual observation – false-positive and false-negative counts.
- **FR15.** Provide a way to list events filtered by route and date for manual inspection.

---

## 9. Curtailment detection heuristic

Plain version: a bus is a *suspected curtailment* when it clearly stops heading toward the end of its route while still being active earlier on the route – and we only believe it if the signal persists, to filter out momentary data glitches.

Precise rules, comparing one cycle to the next for the same `vehicle_id`:

- **Trigger A (destination shortens):** the bus's stated destination changes to a stop that is *earlier* along the route than its previous destination.
- **Trigger B (predictions retreat):** the bus stops predicting for downstream stops it was previously predicting for, while still predicting for stops upstream – i.e. its "reach" shrinks back up the line.

**Noise filters (to cut false positives):**
- **Normal terminus exclusion:** if predictions simply end at the route's scheduled terminus, that's a normal completed journey, not curtailment.
- **Persistence:** require the signal to hold for `K` consecutive cycles (configurable, default 2–3) before recording, so a single missed cycle or GPS blip doesn't trigger it.
- **Single-cycle disappearance:** a vehicle vanishing for one cycle then returning is treated as a data blip, not curtailment.

The detector should record its `confidence` based on which triggers fired and how long the signal persisted, so weak and strong signals can be told apart in analysis.

---

## 10. Enrichment / corroboration logic

- Pull route geometry (the route's ordered stops and path) once per route and cache it.
- For a suspected event, take the last-seen location, fetch nearby road-closure polygons, and test for intersection with the route polyline after applying the buffer (default 75m, configurable).
- Separately, pull the route's published disruption text (TfL often states diversions directly – this is the cheapest, highest-quality corroboration and should be checked first).
- Record `near_closure` and `closure_desc`. Be conservative: only mark `near_closure = true` when the match is genuine. A silent "no" is better than a wrong "yes".

---

## 11. Reporting & decision criteria

The summary report (FR14) exists to make a build decision. Suggested decision logic once enough events are collected:

- **High corroboration + low false-positive rate** → build the curtailment feature, surfacing cause where known.
- **Decent detection but weak corroboration** → ship as "may be curtailed" with the disclaimer, no cause attribution.
- **High false-positive or false-negative rate** → cut or rethink; the inference isn't trustworthy enough.

---

## 12. Technical considerations

- **Language/stack:** Python. Keep dependencies minimal: `requests` (HTTP), a geometry library such as `shapely` (polyline/polygon intersection), and the standard-library `sqlite3`.
- **Data source:** TfL Unified API (`https://api.tfl.gov.uk`), free registered key (500 requests/min; ample for dozens of routes at a 30s interval). Endpoints expected to be used: live arrivals per route, route stop-sequence/geometry, per-route disruption and status, and road disruption (polygons). **Exact JSON field names must be confirmed against live responses** – the earlier spike already prints raw responses for this; don't assume field names from this doc.
- **Statefulness:** the Watcher must persist between cycles. In-memory state is fine while running; the event store (SQLite) is the durable record.
- **Resilience:** wrap all network calls; one bad cycle must not kill the process.
- **Politeness:** small delay between calls; stay well under the rate limit.
- **Privacy/cost:** single operator, no user data, no cloud services required – runs locally.

---

## 13. Non-goals

- No consumer-facing UI, map rendering, or styling.
- No alerts/notifications to any user.
- No saved-routes/saved-stops product features.
- No coverage outside London; no commercial roadworks platforms (TfL's own road data suffices).
- Not the production curtailment algorithm – this measures whether one is viable.

---

## 14. Signals considered and rejected

Signals we evaluated as inputs to curtailment detection and deliberately set aside. Recorded here so they aren't re-litigated in three weeks.

- **Google Maps crowdedness ("how busy is this bus").** *Considered as:* a curtailment input. *Decision:* rejected. The data is real but consumer-app only – it is **not exposed through the Google Maps Platform API at any price** (the Routes/Directions API returns stops, times, line and fare details, but no occupancy field), so it isn't accessible to us. Even if it were, it's a weak, lagging signal: crowding answers "how full," not "did it turn back," and relates to curtailment only via a noisy second-order effect (a curtailed bus crowds the *next* one). *Possible future feature, not a curtailment input:* a "will I get a seat?" feature would source occupancy from the transit agency's GTFS-Realtime feed (`OccupancyStatus` field), not Google – and we'd first need to confirm TfL populates occupancy for buses.

- **Causeway / one.network roadworks platform.** *Considered as:* a road-closure data source. *Decision:* rejected as a source; kept the underlying idea. It's a commercial B2B platform with no open developer API. TfL's own `/Road/{id}/disruption` endpoint covers London, includes closure polygons, and is already in our stack – so we use that instead. (Causeway's consumer output already flows into Google/Waze/Apple Maps anyway.)

- **Road closures as a *primary* curtailment detector.** *Considered as:* the main detection signal. *Decision:* rejected as a detector; retained as corroboration. A road closure far more often produces a *diversion* than a curtailment; many curtailments have non-roadworks causes (service regulation, driver/vehicle shortages, incidents); and roadworks permits are temporally coarse (planned date-windows, not "this trip, now"). Road and line disruption data is therefore used only as a corroborating, explanatory layer on top of the live-prediction inference (sections 9–10) – never as the trigger.

---

## 15. Success metrics

- **Coverage:** at least N suspected events collected across the validation window (set N once we see the event rate – widening routes is the lever).
- **Corroboration rate:** computed and reported.
- **Accuracy (on witnessed events):** false-positive and false-negative counts computed from `manual` vs `auto` rows.
- **Decision reached:** at the end of the window, the report supports a clear build / ship-with-disclaimer / cut decision.

---

## 16. Open questions / decisions to confirm before/while building

1. **Route set:** which ~40–50 routes? (Suggest central + the 38/55/243 you care about.)
2. **Store:** SQLite (recommended) or CSV to start?
3. **Buffer distance:** start at 75m? Tune later against real matches.
4. **Persistence `K`:** 2 or 3 cycles before recording a suspected curtailment?
5. **Enrichment timing:** live at detection, or nightly batch over the day's events?
6. **Manual log surface:** ✅ **Decided — Google Form**, fields mirroring the `events` schema, imported into the table with `source = manual`. Chosen on a build-vs-buy basis: no app to build, no server to host, and it works perfectly from a phone at the stop. Reconsider only if a single unified system later proves worth the effort.

---

## 17. Next step (workflow handoff)

Once this PRD is agreed, generate an **atomic task list** from it – small, individually testable tasks, built one at a time with a commit after each – then implement task by task. Suggested first slice: the shared store + schema (section 7), then the Watcher (FR4–FR8) against a *single* route, then widen, then add the Enricher, then the Manual Log, then Reporting. Get one route working end to end before scaling out.
