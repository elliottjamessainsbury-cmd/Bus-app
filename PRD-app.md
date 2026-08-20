# PRD: NONSTOP — London bus web app

**Name:** NONSTOP
**Status:** Draft, actively building
**Author:** Elliott
**Type:** Personal web app (PWA) — the consumer product track (see CLAUDE.md)
**Live:** https://elliottjamessainsbury-cmd.github.io/Bus-app/ (GitHub Pages)
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

---

## 7. v2 direction — NONSTOP landing page + multi-route (2026-08)

Operator decision (2026-08): give the app a real front door and a name.

### 7.1 Branding
- App name **NONSTOP**, shown **top-left** of the landing page.

### 7.2 Landing page structure (top to bottom)
1. **NONSTOP** wordmark, top-left.
2. **Header copy** (verbatim):
   > Taking buses in London is painful.
   > Stopping early. Diverting without warning. Stops randomly closed. Citymapper,
   > Google Maps and TfL show you information that isn't always right.
   > The speaker on the bus is muffled and nobody can hear what's going in.
   > Wasted time, being late, not sure what's going on and frustration.
   > NONSTOP shows you the information that no one else does. Find your stop, get up
   > to date, and understand how to navigate the city like a pro.
3. **Prompt copy** (verbatim), directly above the route buttons:
   > Choose your local stop or bus route to see live, accurate updates.
4. **Route buttons: 55 and 38.** Selecting one reveals **the exact stop-line UI we
   already have** (A2/A3), for that route, underneath. No redesign of that view.

### 7.3 Closed bus stops (new feature — pending data verification)
- Real London closed stops are usually the yellow "BUS STOP CLOSED" sign.
- In the UI, a **closed stop's badge turns yellow** (replace the red tile with a
  yellow tile, keep the stop letter) instead of red.
- **Data source is unconfirmed:** likely TfL StopPoint/Line disruption endpoints.
  A live inspection spike must confirm whether TfL exposes stop closures and the
  exact field shapes BEFORE we build this (golden rule). This is the first use of
  TfL *disruption* data in the app, and it is a TfL *fact* (safe to show), not our
  inference — consistent with the "surface facts, gate inference" principle.

### 7.4 Copy note
Header says "NONSTOP Shows" — corrected to "NONSTOP shows" (sentence case) unless
the operator wants the emphatic capital.

## 8. v2 task list (atomic, one commit each)

- **A7.** Landing page shell: NONSTOP wordmark, header + prompt copy, 55/38 route
  buttons. Static, no data yet.
- **A8.** Multi-route: selecting a route button loads the existing stop-line UI
  (A2/A3) for that route (parametrise the current hard-coded route 38). Adds 55.
- **A9 (spike).** Confirm live whether/how TfL exposes **closed bus stops**
  (StopPoint/Line disruption shapes). Record in `TFL_API_NOTES.md`.
- **A10.** If A9 confirms: colour closed stops' badges **yellow** in the stop line.
- Existing **A4/A5/A6** (direction toggle, auto-refresh/polish, PWA install) still
  apply and fold in around the above.
