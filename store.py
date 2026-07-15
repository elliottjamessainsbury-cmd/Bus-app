"""
store.py — the single shared event store (PRD §6, §7).

Everything the instrument learns — the Watcher's automated guesses AND the
operator's real-world observations — lands in one SQLite table called `events`,
in one shared format, told apart only by the `source` column. Keeping guesses
and ground truth in the same shape is what makes the later comparison a simple
query instead of a data-wrangling project (PRD §6).

[SQLite = a whole database kept in a single ordinary file on disk. No server to
run, no account — the standard-library `sqlite3` module talks to it directly.]

This module (task T1.1) is responsible for *creating* the table. Reading and
writing rows come next (T1.2).
"""

import sqlite3

import config

# One place naming the columns, in PRD §7 order. Each entry is
# (column_name, column_type). We keep it as data so the CREATE statement and
# any future checks read from the same source of truth.
#
# A note on types — SQLite only really has TEXT / INTEGER / REAL / BLOB. It has
# no dedicated boolean or date type, so:
#   * dates/times are TEXT in ISO 8601 form, e.g. "2026-07-15T14:03:00Z"
#   * near_closure is INTEGER used as a boolean: 1 = yes, 0 = no, NULL = unknown
#     (the Enricher hasn't decided yet). PRD §7 explicitly allows null here.
#   * confidence is TEXT so it can hold either a word ("high") or a number as
#     text — PRD §7 lists it as "text / number".
EVENT_COLUMNS = [
    ("event_id", "TEXT PRIMARY KEY"),   # unique id for the row
    ("source", "TEXT NOT NULL"),        # 'auto' (Watcher) or 'manual' (operator)
    ("detected_at", "TEXT NOT NULL"),   # ISO 8601 timestamp of detection/observation
    ("route", "TEXT"),                  # line id, e.g. '38'
    ("direction", "TEXT"),              # 'inbound' / 'outbound' / 'unknown'
    ("vehicle_id", "TEXT"),             # bus id (auto only; blank for manual)
    ("last_seen_stop", "TEXT"),         # furthest stop still predicted / last known heading
    ("expected_terminus", "TEXT"),      # where the bus *should* have ended
    ("apparent_terminus", "TEXT"),      # where it *seemed* to stop short
    ("event_type", "TEXT"),             # 'curtailment_suspected', 'diversion_observed', ...
    ("near_closure", "INTEGER"),        # boolean-ish: 1 / 0 / NULL (Enricher)
    ("closure_desc", "TEXT"),           # the disruption/closure text, if any (Enricher)
    ("confidence", "TEXT"),             # auto only: how strong the signal was
    ("notes", "TEXT"),                  # free text (operator's words, or detector debug)
]


def connect(db_path=None):
    """Open (and, if needed, create) the SQLite database file, returning a
    connection. Defaults to the path in config.DB_PATH so the whole instrument
    shares one store; callers can pass their own path for tests.

    [A "connection" is just an open handle to the database file that you run
    queries through and then close.]
    """
    return sqlite3.connect(db_path or config.DB_PATH)


def init_db(db_path=None):
    """Create the `events` table if it does not already exist.

    Safe to call every time the program starts: `IF NOT EXISTS` means an
    existing store with its data is left untouched, so this never wipes
    anything. Returns the path it initialised, for convenience.
    """
    columns_sql = ",\n    ".join(f"{name} {coltype}" for name, coltype in EVENT_COLUMNS)
    create_sql = f"CREATE TABLE IF NOT EXISTS events (\n    {columns_sql}\n)"

    conn = connect(db_path)
    try:
        conn.execute(create_sql)
        conn.commit()
    finally:
        # Always close, even if the statement raised, so the file isn't left
        # locked open.
        conn.close()
    return db_path or config.DB_PATH


# The bare column names, in order, derived from the single definition above so
# the writers/readers below can never drift out of sync with the table.
COLUMN_NAMES = [name for name, _ in EVENT_COLUMNS]


def insert_event(event, db_path=None):
    """Write one row into the `events` table.

    `event` is a dict mapping column name -> value. You only need to supply the
    columns you know; any column you leave out is stored as NULL (e.g. a manual
    observation has no `vehicle_id`, the Enricher fills `near_closure` in later).

    Returns the `event_id` written, so callers can log/reference it.

    We build the statement from COLUMN_NAMES and pass the values *separately* as
    parameters (the `?` placeholders) rather than pasting them into the SQL
    string. That is "parameterised" querying — it keeps values as data, so a
    stray quote or odd character in a stop name can never corrupt the query
    [this is also the standard defence against SQL injection].
    """
    unknown = set(event) - set(COLUMN_NAMES)
    if unknown:
        # Fail loudly on a typo'd column rather than silently dropping data.
        raise ValueError(f"unknown event column(s): {sorted(unknown)}")
    if not event.get("event_id"):
        raise ValueError("event_id is required")
    if not event.get("source"):
        raise ValueError("source is required ('auto' or 'manual')")

    placeholders = ", ".join("?" for _ in COLUMN_NAMES)
    columns_sql = ", ".join(COLUMN_NAMES)
    values = [event.get(name) for name in COLUMN_NAMES]

    conn = connect(db_path)
    try:
        conn.execute(
            f"INSERT INTO events ({columns_sql}) VALUES ({placeholders})",
            values,
        )
        conn.commit()
    finally:
        conn.close()
    return event["event_id"]


def list_events(route=None, date=None, db_path=None):
    """Read rows back from the store, newest first, as a list of dicts.

    Optional filters (either, both, or neither):
      `route` — only rows for this line id, e.g. "38".
      `date`  — only rows detected on this calendar day, as "YYYY-MM-DD".
                We match the start of `detected_at`, whose ISO 8601 timestamps
                begin with the date (e.g. "2026-07-15T14:03:00Z").

    Each row comes back as a plain dict keyed by column name, so callers read
    `row["route"]` rather than juggling positions.
    """
    clauses = []
    params = []
    if route is not None:
        clauses.append("route = ?")
        params.append(route)
    if date is not None:
        clauses.append("detected_at LIKE ?")
        params.append(f"{date}%")  # match the date prefix of the timestamp

    where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"SELECT {', '.join(COLUMN_NAMES)} FROM events{where_sql} ORDER BY detected_at DESC"

    conn = connect(db_path)
    try:
        # row_factory makes each row behave like a dict keyed by column name.
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


# Running this file directly sets up the store — handy for a first-time setup
# and for the T1.1 test ("run it, then inspect the schema").
if __name__ == "__main__":
    path = init_db()
    print(f"Initialised event store at: {path}")
    print(f"Table 'events' has {len(EVENT_COLUMNS)} columns:")
    for name, coltype in EVENT_COLUMNS:
        print(f"  {name:<18} {coltype}")
