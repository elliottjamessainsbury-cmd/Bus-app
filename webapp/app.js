// app.js — Next Bus web app.
//
// A2 scope: render route 38's stops in travel order as a tube-map-style line,
// each with its stop-letter badge, and make each stop tappable (arrivals wired
// up in A3). Data comes straight from TfL, anonymously (no key needed).
//
// Confirmed field shapes (TFL_API_NOTES.md):
//   /Line/{id}/Route/Sequence/{direction}
//     -> data.stopPointSequences[0].stopPoint  (list, travel order)
//        each stop: { id: <naptanId>, name, stopLetter, ... }

"use strict";

const TFL_BASE = "https://api.tfl.gov.uk";
const ROUTE = "38";
const DIRECTION = "outbound";

const statusEl = document.getElementById("status");
const stopsEl = document.getElementById("stops");
const headerTitleEl = document.getElementById("header-title");
const headerSubEl = document.getElementById("header-sub");

function setStatus(message, isError) {
  statusEl.textContent = message || "";
  statusEl.classList.toggle("error", Boolean(isError));
  statusEl.style.display = message ? "" : "none";
}

// Fetch this route's ordered stops for the chosen direction.
async function fetchRouteStops(route, direction) {
  const url = `${TFL_BASE}/Line/${route}/Route/Sequence/${direction}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`TfL returned HTTP ${response.status}`);
  const data = await response.json();
  const sequences = data.stopPointSequences || [];
  const first = sequences[0] || {};
  return first.stopPoint || [];
}

// Turn a stop into its short badge text: the stop letter if present, else the
// stop name's initials as a fallback.
function badgeText(stop) {
  if (stop.stopLetter) return stop.stopLetter;
  const words = (stop.name || "").split(/\s+/).filter(Boolean);
  if (words.length === 0) return "•";
  return words.slice(0, 2).map((w) => w[0].toUpperCase()).join("");
}

// Build the tube-map line. Each stop becomes a tappable row.
function renderStops(stops) {
  stopsEl.innerHTML = "";
  for (const stop of stops) {
    const li = document.createElement("li");
    li.className = "stop";
    li.dataset.naptan = stop.id || "";

    const badge = document.createElement("span");
    badge.className = "badge";
    badge.textContent = badgeText(stop);

    const name = document.createElement("span");
    name.className = "stop-name";
    name.textContent = stop.name || "(unnamed stop)";

    li.appendChild(badge);
    li.appendChild(name);

    // Selection is visual for now; A3 hangs live arrivals off this tap.
    li.addEventListener("click", () => onStopTap(stop, li));

    stopsEl.appendChild(li);
  }
}

// A2 placeholder: just toggle the selected highlight. A3 replaces this with a
// live arrivals fetch.
function onStopTap(stop, li) {
  const wasSelected = li.classList.contains("selected");
  document.querySelectorAll(".stop.selected").forEach((el) =>
    el.classList.remove("selected")
  );
  if (!wasSelected) li.classList.add("selected");
}

async function init() {
  try {
    const stops = await fetchRouteStops(ROUTE, DIRECTION);
    if (stops.length === 0) {
      setStatus("No stops returned for this route/direction.", true);
      return;
    }
    renderStops(stops);
    const terminus = stops[stops.length - 1];
    headerTitleEl.textContent = `Route ${ROUTE}`;
    headerSubEl.textContent = `towards ${terminus.name || DIRECTION}`;
    setStatus("");
  } catch (err) {
    setStatus(
      `Could not load stops: ${err.message}. ` +
        `If this looks like a CORS/network error, tell Claude.`,
      true
    );
  }
}

init();
