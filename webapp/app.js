// app.js — Next Bus web app.
//
// A1 scope: fetch route 38's stops in travel order, straight from TfL, and list
// them. This also proves the browser can call the TfL API directly (CORS) with
// no API key (anonymous access is fine for personal use).
//
// Field shapes are the ones we confirmed live in TFL_API_NOTES.md:
//   /Line/{id}/Route/Sequence/{direction}
//     -> data.stopPointSequences[0].stopPoint  (a list, in travel order)
//        each stop: { id: <naptanId>, name: <stop name>, ... }

"use strict";

// One place for the API base and the config this screen uses. Later tasks make
// route/direction user-selectable (A4); for now they are fixed.
const TFL_BASE = "https://api.tfl.gov.uk";
const ROUTE = "38";
const DIRECTION = "outbound";

// Grab the page elements we write into.
const statusEl = document.getElementById("status");
const stopsEl = document.getElementById("stops");

// Small helper: show a message in the status line, optionally as an error.
function setStatus(message, isError) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", Boolean(isError));
}

// Fetch this route's ordered stops for the chosen direction.
async function fetchRouteStops(route, direction) {
  const url = `${TFL_BASE}/Line/${route}/Route/Sequence/${direction}`;
  const response = await fetch(url);
  if (!response.ok) {
    // e.g. 429 (rate limited) or 404 (bad route/direction).
    throw new Error(`TfL returned HTTP ${response.status}`);
  }
  const data = await response.json();

  // Dig out the ordered stop list, defensively.
  const sequences = data.stopPointSequences || [];
  const first = sequences[0] || {};
  const stops = first.stopPoint || [];
  return stops;
}

// Render the stops as list items.
function renderStops(stops) {
  stopsEl.innerHTML = "";
  for (const stop of stops) {
    const li = document.createElement("li");
    li.textContent = stop.name || "(unnamed stop)";
    stopsEl.appendChild(li);
  }
}

// Kick things off when the page loads.
async function init() {
  try {
    const stops = await fetchRouteStops(ROUTE, DIRECTION);
    if (stops.length === 0) {
      setStatus("No stops returned for this route/direction.", true);
      return;
    }
    renderStops(stops);
    setStatus(`Route ${ROUTE} — ${stops.length} stops (${DIRECTION}).`);
  } catch (err) {
    // The most likely first-run failure is a CORS block; surface it plainly.
    setStatus(
      `Could not load stops: ${err.message}. ` +
        `If this looks like a CORS/network error, tell Claude — we'll add a tiny proxy.`,
      true
    );
  }
}

init();
