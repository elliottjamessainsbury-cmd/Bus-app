// app.js — Next Bus web app.
//
// A2: render the route's stops as a tube-map-style line.
// A3: tap a stop to see the next buses for this route at that stop, with a
//     live countdown. Data comes straight from TfL, anonymously (no key).
//
// Confirmed field shapes (TFL_API_NOTES.md):
//   /Line/{id}/Route/Sequence/{direction}
//     -> data.stopPointSequences[0].stopPoint  (list, travel order)
//        each stop: { id: <naptanId>, name, stopLetter, ... }
//   /StopPoint/{naptanId}/Arrivals
//     -> list of predictions, each: { lineId, lineName, destinationName,
//        timeToStation (seconds), vehicleId, ... }

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

// ---- data ---------------------------------------------------------------

async function fetchRouteStops(route, direction) {
  const url = `${TFL_BASE}/Line/${route}/Route/Sequence/${direction}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`TfL returned HTTP ${response.status}`);
  const data = await response.json();
  const sequences = data.stopPointSequences || [];
  const first = sequences[0] || {};
  return first.stopPoint || [];
}

// Live arrivals for this route at one stop, soonest first.
async function fetchStopArrivals(naptanId, route) {
  const url = `${TFL_BASE}/StopPoint/${naptanId}/Arrivals`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`TfL returned HTTP ${response.status}`);
  const all = await response.json();
  const forRoute = (Array.isArray(all) ? all : []).filter(
    (p) => p.lineId === route
  );
  forRoute.sort((a, b) => (a.timeToStation ?? 1e9) - (b.timeToStation ?? 1e9));
  return forRoute;
}

// ---- rendering ----------------------------------------------------------

function badgeText(stop) {
  if (stop.stopLetter) return stop.stopLetter;
  const words = (stop.name || "").split(/\s+/).filter(Boolean);
  if (words.length === 0) return "•";
  return words.slice(0, 2).map((w) => w[0].toUpperCase()).join("");
}

// Seconds-to-station -> friendly countdown.
function formatCountdown(seconds) {
  if (seconds == null) return "";
  if (seconds < 60) return "due";
  return `${Math.round(seconds / 60)} min`;
}

function renderStops(stops) {
  stopsEl.innerHTML = "";
  for (const stop of stops) {
    const li = document.createElement("li");
    li.className = "stop";
    li.dataset.naptan = stop.id || "";

    const row = document.createElement("div");
    row.className = "stop-row";

    const badge = document.createElement("span");
    badge.className = "badge";
    badge.textContent = badgeText(stop);

    const name = document.createElement("span");
    name.className = "stop-name";
    name.textContent = stop.name || "(unnamed stop)";

    row.appendChild(badge);
    row.appendChild(name);
    li.appendChild(row);

    // The inline arrivals panel, hidden until this stop is tapped.
    const panel = document.createElement("div");
    panel.className = "arrivals";
    li.appendChild(panel);

    row.addEventListener("click", () => onStopTap(stop, li, panel));
    stopsEl.appendChild(li);
  }
}

function renderArrivals(panel, arrivals) {
  panel.innerHTML = "";
  if (arrivals.length === 0) {
    const empty = document.createElement("p");
    empty.className = "arrivals-empty";
    empty.textContent = `No ${ROUTE} buses predicted here in the next ~30 min.`;
    panel.appendChild(empty);
    return;
  }
  // Show the soonest handful.
  for (const p of arrivals.slice(0, 5)) {
    const item = document.createElement("div");
    item.className = "arrival";

    const dest = document.createElement("span");
    dest.className = "arrival-dest";
    dest.textContent = `to ${p.destinationName || "?"}`;

    const when = document.createElement("span");
    when.className = "arrival-when";
    when.textContent = formatCountdown(p.timeToStation);

    item.appendChild(dest);
    item.appendChild(when);
    panel.appendChild(item);
  }
}

// ---- interaction --------------------------------------------------------

async function onStopTap(stop, li, panel) {
  const wasSelected = li.classList.contains("selected");

  // Collapse any other open stop.
  document.querySelectorAll(".stop.selected").forEach((el) => {
    el.classList.remove("selected");
    const p = el.querySelector(".arrivals");
    if (p) p.innerHTML = "";
  });

  if (wasSelected) return; // tapping the open stop closes it

  li.classList.add("selected");
  panel.innerHTML = '<p class="arrivals-loading">Loading…</p>';
  try {
    const arrivals = await fetchStopArrivals(stop.id, ROUTE);
    // Guard against a race if the user tapped elsewhere meanwhile.
    if (li.classList.contains("selected")) renderArrivals(panel, arrivals);
  } catch (err) {
    panel.innerHTML = `<p class="arrivals-empty">Couldn't load times: ${err.message}</p>`;
  }
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
