# PRD: Simple "Next Bus" Web App

**Status:** Draft, actively building
**Author:** Elliott
**Type:** Personal web app (PWA) — the consumer product track (see CLAUDE.md)
**Relationship to the instrument:** independent for now; shares only the TfL data
source. The curtailment engine is NOT wired in yet.

---

## 1. Why

Google Maps and Citymapper both reshape TfL's bus arrival data, and they
disagree with each other. This app shows the arrivals **straight from TfL** —
stripped down to the one question that matters day to day: *"when's my next
bus?"* It's also a learning project.

## 2. What it is (v1 scope)

A small, phone-friendly web page that:
1. Lets you **pick a route** (start with the ones we already watch: 21, 38, 55, 243).
2. Shows that route's **stops as a vertical line** — tube-map style, in travel
   order, with a direction toggle.
3. Lets you **tap a stop** to see the **next buses** for that route at that stop,
   with a live countdown, refreshed automatically.

That's it. No accounts, no saved stops (yet), no map tiles, no curtailment
surfacing. Deliberately minimal.

## 3. What it is NOT (v1)

- Not native iOS (a PWA "Add to Home Screen" gives an app-like feel for now).
- No curtailment/diversion display yet — that waits on the instrument's findings.
- No multi-modal (tube/rail) — buses only.
- No routing/journey planning — this is a "what's coming at this stop" tool.

## 4. Technical shape

- **Pure client-side** static site in `webapp/`: HTML + CSS + vanilla JS. No build
  step, no framework, no server to host.
- **Data:** TfL Unified API, called **directly from the browser, anonymously**
  (no key embedded). The 50 req/min anonymous limit is ample for personal use.
  Endpoints (shapes confirmed in `TFL_API_NOTES.md`):
  - route stops in order: `/Line/{id}/Route/Sequence/{direction}`
  - live arrivals at a stop: `/StopPoint/{naptanId}/Arrivals` (filtered to the route)
- **Runs** by opening the folder with any static server (e.g.
  `python3 -m http.server`) and viewing in the phone/desktop browser; later a PWA
  manifest makes it installable to the home screen.
- **Risk to verify first:** browser CORS — that TfL permits direct calls from a
  web page. Task A1 checks this live.

## 5. Task list (atomic, one commit each)

- **A1.** Scaffold `webapp/` and prove live data: fetch route 38's ordered stops
  and list them on the page. (Confirms CORS + data flow.)
- **A2.** Render the stops as a vertical tube-map-style line with stop badges.
- **A3.** Tap a stop → fetch and show next buses (countdown) for that stop+route.
- **A4.** Route picker (21/38/55/243) + inbound/outbound direction toggle.
- **A5.** Auto-refresh arrivals; loading and error states; tidy styling.
- **A6.** PWA manifest + icon so "Add to Home Screen" opens it full-screen.

## 6. Later (not now)

Saved stops, more routes, surfacing the curtailment/diversion signal once the
instrument proves it's worth showing, and possibly a native iOS build.
