"""
Chat unit — read-only query primitives (build spec Sec 11, addendum A5).

The chat is a SUBORDINATE: it (1) GUIDES a launch and (2) REPORTS on demand, and
it observes everything. It is READ-ONLY over SHARED_LIB — it holds corpus/journal
handles but exposes no method that writes. Answers are STRUCTURED DATA; a
ModelBackend.phrase() renders prose from them and invents nothing (PSELGenerator).

Hard rules enforced here:
  R1 FRESHNESS STAMP on every answer.
  R2 REGISTER SEPARATION: every claim carries a register (VERIFIED / CONTESTED /
     CONJECTURAL) — conjectural is never stated like verified.
  R3 I DON'T KNOW is a valid, reachable answer.
  R5 CITATIONS ARE CHIPS: lemma ids are returned as first-class ids.
"""
from __future__ import annotations

from typing import Any, Optional

from .corpus import CorpusStore
from .model import Status

# Register labels (R2). A stored lemma's status maps to a register.
_REGISTER = {
    Status.VERIFIED.value: "VERIFIED",
    Status.VERIFIED_CONTESTED.value: "CONTESTED",
    Status.REFUTED.value: "REFUTED",
    Status.INVALIDATED.value: "INVALIDATED",
}

# Fixed launch scripts (A5.1): the chat tells you where to click; it never acts.
_LAUNCH_SCRIPTS = {
    "collatz": [
        "Open the Frontier tab.",
        "Right-click -> New branch.",
        "Set problem shape = 'collatz'; method = e.g. 'log-density weight search'.",
        "Enter the sub-goal in 'state', the method in 'action', the target in 'outcome'.",
        "Click CONFIRM. You (not the chat) start it; SHARED_LIB instantiates the unit.",
    ],
    "bounded_gaps": [
        "Open the Frontier tab.",
        "Right-click -> New branch.",
        "Set problem shape = 'bounded_gaps'; pick B1/B2/B3/B4 as the method.",
        "Fill state/action/outcome, then click CONFIRM.",
    ],
}


class ChatUnit:
    """Read-only. No method here mutates corpus or journal — by construction."""

    def __init__(self, corpus: CorpusStore, journal, queue=None,
                 units: Optional[dict] = None, model=None) -> None:
        self._corpus = corpus       # read-only use only
        self._journal = journal
        self._queue = queue
        self._units = units or {}
        self._model = model

    # ---- freshness (R1) ---------------------------------------------------
    def _freshness(self) -> dict[str, Any]:
        return {"as_of_seq": self._journal.last_seq()}

    def _wrap(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"freshness": self._freshness(), **payload}

    # ---- launch guidance (A5.1): guide, never execute ---------------------
    def launch_guide(self, problem: str) -> dict[str, Any]:
        key = problem.strip().lower().replace(" ", "_")
        steps = _LAUNCH_SCRIPTS.get(key)
        if steps is None:
            return self._wrap({"answer": "i_dont_know",
                               "note": f"no launch script for '{problem}'"})
        return self._wrap({
            "problem": key, "steps": steps,
            "note": "The chat only instructs; the LLM never writes the launch (A5.1).",
        })

    # ---- query primitives (build spec Sec 11) -----------------------------
    def lemma(self, lemma_id: str) -> dict[str, Any]:
        row = self._corpus.get(lemma_id)
        if row is None:
            return self._wrap({"answer": "i_dont_know", "lemma": lemma_id})
        return self._wrap({
            "id": row["id"],
            "statement": row["statement"],
            "informal_claim": row["informal_claim"],
            "status": row["status"],
            "register": _REGISTER.get(row["status"], "UNKNOWN"),  # R2
            "provenance": row["provenance"],
        })

    def dependencies(self, lemma_id: str) -> dict[str, Any]:
        if self._corpus.get(lemma_id) is None:
            return self._wrap({"answer": "i_dont_know"})
        return self._wrap({"id": lemma_id,
                           "dependencies": self._corpus.dependencies(lemma_id)})

    def dependents(self, lemma_id: str) -> dict[str, Any]:
        if self._corpus.get(lemma_id) is None:
            return self._wrap({"answer": "i_dont_know"})
        return self._wrap({"id": lemma_id,
                           "dependents": self._corpus.direct_dependents(lemma_id)})

    def corpus_stats(self) -> dict[str, Any]:
        return self._wrap({"counts": self._corpus.counts_by_status()})

    def orphans(self) -> dict[str, Any]:
        """Verified lemmas nothing depends on — the opening-spiral view."""
        out = []
        for lid in self._corpus.all_ids():
            row = self._corpus.get(lid)
            if row["status"] in (Status.VERIFIED.value,
                                 Status.VERIFIED_CONTESTED.value) \
                    and not self._corpus.direct_dependents(lid):
                out.append(lid)
        return self._wrap({"orphans": out})

    def pending_for_human(self) -> dict[str, Any]:
        if self._queue is None:
            return self._wrap({"answer": "i_dont_know", "note": "no queue attached"})
        items = [{"kind": it.kind, "node": it.node, "summary": it.summary,
                  "blast_radius": it.blast_radius}
                 for it in self._queue.today_view()]
        return self._wrap({"pending": items, "deferred": self._queue.deferred_count()})

    def unit_health(self, unit_id: str) -> dict[str, Any]:
        u = self._units.get(unit_id)
        if u is None:
            return self._wrap({"answer": "i_dont_know", "unit": unit_id})
        return self._wrap({"unit": unit_id, "health": u.theta_health(),
                           "phase": u.phase.value, "step": u.step})

    def diff_since(self, seq: int) -> dict[str, Any]:
        events = list(self._journal.read_all(since_seq=seq))
        return self._wrap({"since_seq": seq, "n_events": len(events),
                           "events": [{"seq": e["seq"], "type": e["type"]}
                                      for e in events]})

    # ---- phrasing (delegated; invents nothing) ----------------------------
    def phrase(self, structured: dict[str, Any]) -> str:
        if self._model is None:
            return str(structured)
        return self._model.phrase(structured)
