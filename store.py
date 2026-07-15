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


# Running this file directly sets up the store — handy for a first-time setup
# and for the T1.1 test ("run it, then inspect the schema").
if __name__ == "__main__":
    path = init_db()
    print(f"Initialised event store at: {path}")
    print(f"Table 'events' has {len(EVENT_COLUMNS)} columns:")
    for name, coltype in EVENT_COLUMNS:
        print(f"  {name:<18} {coltype}")
