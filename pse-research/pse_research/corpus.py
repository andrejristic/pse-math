"""
Corpus store (build spec 3.2).

Verified lemmas, their proof terms, dependency edges, provenance, and the
INFORMAL CLAIM field. The DAG is DERIVED from the store (the lemma_deps table),
never stored separately — one source of truth.

Only SHARED_LIB writes here (via store / mark). Nothing else has a write path.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Optional

from .model import Candidate, Status


class CorpusStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        c = self.conn
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS lemmas (
                id             TEXT PRIMARY KEY,
                name           TEXT NOT NULL,
                informal_claim TEXT NOT NULL,
                statement      TEXT NOT NULL,
                proof_text     TEXT NOT NULL,
                structural_key TEXT NOT NULL,
                status         TEXT NOT NULL,
                branch         TEXT NOT NULL,
                step           INTEGER NOT NULL,
                provenance     TEXT NOT NULL
            );
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS lemma_deps (
                lemma_id TEXT NOT NULL,
                dep_id   TEXT NOT NULL,
                PRIMARY KEY (lemma_id, dep_id),
                FOREIGN KEY (lemma_id) REFERENCES lemmas(id)
            );
            """
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_deps_dep ON lemma_deps(dep_id);"
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_lemmas_skey ON lemmas(structural_key);"
        )
        c.commit()

    # ---- reads ------------------------------------------------------------
    def get(self, lemma_id: str) -> Optional[dict[str, Any]]:
        r = self.conn.execute("SELECT * FROM lemmas WHERE id = ?", (lemma_id,)).fetchone()
        return dict(r) if r else None

    def exists(self, lemma_id: str) -> bool:
        return self.get(lemma_id) is not None

    def status_of(self, lemma_id: str) -> Optional[Status]:
        r = self.get(lemma_id)
        return Status(r["status"]) if r else None

    def find_by_structural_key(self, structural_key: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM lemmas WHERE structural_key = ?", (structural_key,)
        ).fetchall()
        return [dict(r) for r in rows]

    def direct_dependents(self, lemma_id: str) -> list[str]:
        rows = self.conn.execute(
            "SELECT lemma_id FROM lemma_deps WHERE dep_id = ?", (lemma_id,)
        ).fetchall()
        return [r["lemma_id"] for r in rows]

    def dependencies(self, lemma_id: str) -> list[str]:
        rows = self.conn.execute(
            "SELECT dep_id FROM lemma_deps WHERE lemma_id = ?", (lemma_id,)
        ).fetchall()
        return [r["dep_id"] for r in rows]

    def all_ids(self) -> list[str]:
        rows = self.conn.execute("SELECT id FROM lemmas ORDER BY id").fetchall()
        return [r["id"] for r in rows]

    def transitive_dependents(self, lemma_id: str) -> list[str]:
        """Everything downstream of lemma_id (used by refute + blast radius)."""
        seen: set[str] = set()
        stack = [lemma_id]
        while stack:
            cur = stack.pop()
            for dep in self.direct_dependents(cur):
                if dep not in seen:
                    seen.add(dep)
                    stack.append(dep)
        return sorted(seen)

    def would_create_cycle(self, candidate: Candidate) -> Optional[list[str]]:
        """
        C3 helper: if we add candidate.id depending on candidate.dependencies,
        does any dependency (transitively) already depend back on candidate.id?
        Returns a witnessing path if a cycle would form, else None.
        """
        cid = candidate.id
        for dep in candidate.dependencies:
            # walk UP from dep through what dep depends on; if we reach cid, cycle.
            stack = [(dep, [cid, dep])]
            seen = {dep}
            while stack:
                node, path = stack.pop()
                if node == cid:
                    return path
                nxt = self.conn.execute(
                    "SELECT dep_id FROM lemma_deps WHERE lemma_id = ?", (node,)
                ).fetchall()
                for r in nxt:
                    d = r["dep_id"]
                    if d == cid:
                        return path + [cid]
                    if d not in seen:
                        seen.add(d)
                        stack.append((d, path + [d]))
        return None

    # ---- writes (SHARED_LIB only) ----------------------------------------
    def store(self, candidate: Candidate, status: Status) -> None:
        self.conn.execute(
            """
            INSERT INTO lemmas
              (id, name, informal_claim, statement, proof_text, structural_key,
               status, branch, step, provenance)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate.id, candidate.name, candidate.informal_claim,
                candidate.statement, candidate.proof_text, candidate.structural_key,
                status.value, candidate.branch, candidate.step,
                json.dumps(candidate.provenance(), sort_keys=True),
            ),
        )
        for dep in candidate.dependencies:
            self.conn.execute(
                "INSERT OR IGNORE INTO lemma_deps (lemma_id, dep_id) VALUES (?, ?)",
                (candidate.id, dep),
            )
        self.conn.commit()

    def mark(self, lemma_id: str, status: Status) -> None:
        self.conn.execute(
            "UPDATE lemmas SET status = ? WHERE id = ?", (status.value, lemma_id)
        )
        self.conn.commit()

    def counts_by_status(self) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT status, COUNT(*) AS n FROM lemmas GROUP BY status"
        ).fetchall()
        return {r["status"]: r["n"] for r in rows}
