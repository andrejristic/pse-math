"""
Knowledge ingestion — scraper + curator, one external store (addendum A1).

TWO agents, one seam:
  SCRAPER  (Extract)  : acquisition; touches the network; sandboxed; provenance.
                        Output lands in QUARANTINE (raw, untrusted).
  CURATOR  (Transform+Load): works only over quarantine (no network); extracts
                        (informal<->formal) pairs, tags known-error cases,
                        normalizes, scores reliability, de-duplicates.

THE ONE RULE (addendum Sec 0): everything here is a CHEAP SIGNAL. It NEVER enters
the corpus as verified. The ExternalStore has ZERO corpus-write path — it does
not even hold a corpus handle. To USE a result, a unit must re-prove it via the
gate. Three consumers read the store: RECON/dedup, Guardian 2, Seldon prior.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

TIER = "EXTERNAL_CHEAP_SIGNAL"   # the only tier anything here can have

# Source reliability priors (curator scoring). mathlib is aligned formal+informal.
SOURCE_RELIABILITY = {
    "mathlib": 0.95, "nlab": 0.7, "mathoverflow": 0.5,
    "arxiv": 0.6, "blog": 0.3, "unknown": 0.2,
}


@dataclass
class RawItem:
    """What the scraper drops into quarantine. Untrusted."""
    source: str
    content_hash: str
    informal: str
    formal: Optional[str] = None
    kind: str = "pair"        # "pair" | "known_error" | "history"
    url: str = ""
    fetched_ts: float = 0.0


@dataclass
class ExternalEntry:
    content_hash: str
    source: str
    informal: str
    formal: Optional[str]
    kind: str
    reliability: float
    url: str = ""
    fetched_ts: float = 0.0
    tier: str = TIER          # immutable: cheap signal, never corpus


class ExternalStore:
    """Separate store; deliberately has NO corpus handle (the hard wall)."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS external_knowledge (
                content_hash TEXT PRIMARY KEY,
                source TEXT, informal TEXT, formal TEXT, kind TEXT,
                reliability REAL, url TEXT, fetched_ts REAL, tier TEXT
            );
            """
        )
        self.conn.commit()

    def can_write_corpus(self) -> bool:
        return False   # structural guarantee, asserted by callers

    def put(self, e: ExternalEntry) -> bool:
        """Insert if new (dedup on content_hash). Returns True if inserted."""
        assert e.tier == TIER, "external knowledge is always a cheap signal"
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO external_knowledge VALUES (?,?,?,?,?,?,?,?,?)",
            (e.content_hash, e.source, e.informal, e.formal, e.kind,
             e.reliability, e.url, e.fetched_ts, e.tier),
        )
        self.conn.commit()
        return cur.rowcount > 0

    # ---- consumer queries -------------------------------------------------
    def known(self, text: str) -> bool:
        """RECON/dedup consumer: is this already known/tried?"""
        t = f"%{text.strip().lower()}%"
        row = self.conn.execute(
            "SELECT 1 FROM external_knowledge WHERE lower(informal) LIKE ? LIMIT 1",
            (t,),
        ).fetchone()
        return row is not None

    def pairs(self) -> list[ExternalEntry]:
        """Guardian 2 consumer: aligned (informal<->formal) pairs for G1."""
        rows = self.conn.execute(
            "SELECT * FROM external_knowledge WHERE formal IS NOT NULL "
            "AND kind='pair'"
        ).fetchall()
        return [self._row(r) for r in rows]

    def known_errors(self) -> list[ExternalEntry]:
        rows = self.conn.execute(
            "SELECT * FROM external_knowledge WHERE kind='known_error'"
        ).fetchall()
        return [self._row(r) for r in rows]

    def count(self) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) AS n FROM external_knowledge").fetchone()["n"]

    def _row(self, r: sqlite3.Row) -> ExternalEntry:
        return ExternalEntry(
            content_hash=r["content_hash"], source=r["source"],
            informal=r["informal"], formal=r["formal"], kind=r["kind"],
            reliability=r["reliability"], url=r["url"],
            fetched_ts=r["fetched_ts"], tier=r["tier"],
        )


class Curator:
    """Transform+Load. No network handle. Turns raw quarantine into entries."""

    def __init__(self, store: ExternalStore) -> None:
        self.store = store

    def process(self, raw: Iterable[RawItem]) -> list[ExternalEntry]:
        inserted: list[ExternalEntry] = []
        for item in raw:
            rel = SOURCE_RELIABILITY.get(item.source, SOURCE_RELIABILITY["unknown"])
            e = ExternalEntry(
                content_hash=item.content_hash, source=item.source,
                informal=item.informal, formal=item.formal, kind=item.kind,
                reliability=rel, url=item.url, fetched_ts=item.fetched_ts,
            )
            if self.store.put(e):       # dedup happens in the store
                inserted.append(e)
        return inserted


class StubScraper:
    """Offline scraper for building/testing: yields provided raw items."""

    name = "stub"

    def __init__(self, items: Iterable[RawItem]) -> None:
        self._items = list(items)

    def fetch(self) -> list[RawItem]:
        return list(self._items)


class NetworkScraper:
    """Real network acquisition (Dell/exposed). Gated by profile; placeholder."""

    name = "network"

    def __init__(self, network_enabled: bool) -> None:
        if not network_enabled:
            raise RuntimeError(
                "NetworkScraper disabled by profile (ingestion_network_enabled=False)."
                " It is a network-exposed surface and pulls Guardian 1 forward; "
                "enable only on the Dell/exposed profile."
            )
