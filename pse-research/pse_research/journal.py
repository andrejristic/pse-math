"""
Append-only journal (build spec 3.3).

Every event, forever, ordered, timestamped. The GUI's time-travel view and the
whole audit story depend on this being genuinely append-only, so append-only is
enforced at the DATABASE level with triggers, not merely by not exposing an
update method. Any UPDATE or DELETE against the events table raises.
"""
from __future__ import annotations

import json
import sqlite3
import time
from typing import Any, Iterator, Optional

# Event types (build spec 3.3), plus additions from the addendum.
EVENT_TYPES = {
    "BRANCH_OPENED", "BRANCH_CLOSED", "PHASE_CHANGE", "CANDIDATE_REGISTERED",
    "GATE_PASS", "GATE_REJECT", "GUARDIAN2_FINDING", "HUMAN_DECISION",
    "ABSORPTION", "DE_ABSORPTION", "FISSION", "UNIT_DEATH", "THETA_EVENT",
    "STRATEGY_OUTCOME", "ORPHAN_FLAGGED", "REFUTATION",
    # addendum:
    "GAP_HYPOTHESIS", "GAP_DROPPED", "INGEST_EXTERNAL",
}


class AppendOnlyJournal:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        # check_same_thread=False so the read-only daemon thread may use this
        # connection; access is serialized by the (non-threading) daemon server.
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA foreign_keys=ON;")
        self._init_schema()

    def _init_schema(self) -> None:
        c = self.conn
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                seq     INTEGER PRIMARY KEY AUTOINCREMENT,
                ts      REAL    NOT NULL,
                type    TEXT    NOT NULL,
                payload TEXT    NOT NULL
            );
            """
        )
        # Append-only enforcement: forbid UPDATE and DELETE at the DB level.
        c.execute(
            """
            CREATE TRIGGER IF NOT EXISTS events_no_update
            BEFORE UPDATE ON events BEGIN
                SELECT RAISE(ABORT, 'journal is append-only: UPDATE forbidden');
            END;
            """
        )
        c.execute(
            """
            CREATE TRIGGER IF NOT EXISTS events_no_delete
            BEFORE DELETE ON events BEGIN
                SELECT RAISE(ABORT, 'journal is append-only: DELETE forbidden');
            END;
            """
        )
        c.commit()

    def write(self, event_type: str, **payload: Any) -> int:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unknown event type: {event_type}")
        ts = time.time()
        cur = self.conn.execute(
            "INSERT INTO events (ts, type, payload) VALUES (?, ?, ?)",
            (ts, event_type, json.dumps(payload, sort_keys=True)),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def read_all(self, since_seq: int = 0) -> Iterator[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT seq, ts, type, payload FROM events WHERE seq > ? ORDER BY seq",
            (since_seq,),
        )
        for r in rows:
            yield {
                "seq": r["seq"],
                "ts": r["ts"],
                "type": r["type"],
                "payload": json.loads(r["payload"]),
            }

    def last_seq(self) -> int:
        row = self.conn.execute("SELECT COALESCE(MAX(seq), 0) AS m FROM events").fetchone()
        return int(row["m"])

    def close(self) -> None:
        self.conn.close()
