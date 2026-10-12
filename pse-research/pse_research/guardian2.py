"""
Guardian 2 — the proof skeptic (build spec Sec 7). Framework + checks.

DESIGN PRINCIPLE: Lean proves the theorem you WROTE, not the one you MEANT.
Guardian 2 owns that gap and nothing else. Everything mechanically decidable is
already in the SHARED_LIB gate (C1-C7) and must not be duplicated here.

[!] Guardian 2 has NO gate authority. It produces findings; SHARED_LIB stores,
    contests, or rejects. Severe findings (G1/G2/G6) reach the human via the queue.

Which checks run WITHOUT a model (structural, live on the Surface):
  G3 hypothesis inflation (diachronic, over the dependency path)
  G4 scope creep in naming
  G5 trivial generalization (alpha-rename padding)
  G2 definitional smuggling (heuristic: new def + near-trivial lemma)
Which need a model (hook; wired via ModelBackend on the Dell, injectable in tests):
  G1 statement drift  (the highest-value, hardest check)
  G6 constant regression (needs domain baseline; partly structural here)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .model import Candidate

SEVERE_KINDS = {"G1", "G2", "G6"}
_GENERALITY_WORDS = ("general", "arbitrary", "forall", "any", "universal", "all")


@dataclass
class G2Finding:
    kind: str          # "G1".."G6"
    detail: str

    @property
    def severe(self) -> bool:
        return self.kind in SEVERE_KINDS


def normalize_statement(stmt: str) -> str:
    """
    Alpha-rename normalization for G5: collapse standalone single-letter
    identifiers to '_' so "a + b = b + a" and "x + y = y + x" match. A heuristic
    stand-in for Lean's real structural normal form (wired with LeanBackend).
    """
    return re.sub(r"\b[a-zA-Z]\b", "_", stmt)


class Guardian2:
    def __init__(self,
                 drift_check: Optional[Callable[[str, str], Optional[str]]] = None
                 ) -> None:
        # drift_check(informal_claim, statement) -> detail if drift, else None.
        # None => no model wired => G1 does not fire (honest on the Surface).
        self.drift_check = drift_check
        self.findings_raised = 0
        self.findings_upheld = 0

    def review(self, candidate: Candidate,
               context: Optional[dict[str, Any]] = None) -> list[G2Finding]:
        ctx = context or {}
        out: list[G2Finding] = []
        for fn in (self._g1, self._g2, self._g3, self._g4, self._g5, self._g6):
            f = fn(candidate, ctx)
            if f:
                out.append(f)
        self.findings_raised += len(out)
        return out

    @staticmethod
    def is_severe(findings: list[G2Finding]) -> bool:
        return any(f.severe for f in findings)

    # ---- G1 statement drift (model-backed) --------------------------------
    def _g1(self, c: Candidate, ctx) -> Optional[G2Finding]:
        if self.drift_check is None:
            return None
        detail = self.drift_check(c.informal_claim, c.statement)
        return G2Finding("G1", detail) if detail else None

    # ---- G2 definitional smuggling (heuristic) ----------------------------
    def _g2(self, c: Candidate, ctx) -> Optional[G2Finding]:
        introduces_def = bool(re.search(r"\bdef\b", c.statement))
        trivial_proof = (len(c.proof_text.strip()) <= 12
                         or re.search(r"\b(rfl|trivial|simp)\b", c.proof_text) is not None)
        if introduces_def and trivial_proof:
            return G2Finding("G2", "a definition is introduced alongside a "
                                   "near-trivial lemma that needs it (the hard "
                                   "part may be smuggled into the definition)")
        return None

    # ---- G3 hypothesis inflation (diachronic, structural) -----------------
    def _g3(self, c: Candidate, ctx) -> Optional[G2Finding]:
        counts = ctx.get("dep_hyp_counts")   # hypothesis counts along the chain
        if not counts:
            return None
        chain = list(counts) + [len(c.hypotheses)]
        strictly_growing = all(b > a for a, b in zip(chain, chain[1:]))
        if strictly_growing and chain[-1] >= ctx.get("g3_threshold", 4):
            return G2Finding("G3", f"hypotheses accumulate along the dependency "
                                   f"path {chain}; the final statement may apply "
                                   f"to nothing of interest")
        return None

    # ---- G4 scope creep in naming -----------------------------------------
    def _g4(self, c: Candidate, ctx) -> Optional[G2Finding]:
        name_l = c.name.lower()
        suggests_general = any(w in name_l for w in _GENERALITY_WORDS)
        actually_restricted = len(c.hypotheses) > 0
        if suggests_general and actually_restricted:
            return G2Finding("G4", f"name '{c.name}' reads as more general than "
                                   f"the statement, which carries {len(c.hypotheses)}"
                                   f" hypotheses")
        return None

    # ---- G5 trivial generalization (alpha-rename padding) -----------------
    def _g5(self, c: Candidate, ctx) -> Optional[G2Finding]:
        corpus_norm = ctx.get("corpus_norm")   # {lemma_id: normalized_statement}
        if not corpus_norm:
            return None
        norm = normalize_statement(c.statement)
        for lid, other in corpus_norm.items():
            if norm == other:
                return G2Finding("G5", f"structurally identical to {lid} up to "
                                       f"variable renaming (padding, not new)")
        return None

    # ---- G6 constant regression (structural-ish) --------------------------
    def _g6(self, c: Candidate, ctx) -> Optional[G2Finding]:
        claimed = ctx.get("claimed_constant")
        baseline = ctx.get("baseline_constant")
        if claimed is None or baseline is None:
            return None
        # a claimed improvement must actually be smaller AND unconditional
        if claimed >= baseline:
            return G2Finding("G6", f"claimed constant {claimed} is not an "
                                   f"improvement over baseline {baseline}")
        if c.hypotheses:
            return G2Finding("G6", f"claimed improvement {claimed} holds only "
                                   f"under assumptions not carried in the statement")
        return None

    # ---- self-check (build spec Sec 7 self_check) -------------------------
    def record_upheld(self, upheld: bool) -> None:
        if upheld:
            self.findings_upheld += 1

    def upheld_rate(self) -> float:
        return (self.findings_upheld / self.findings_raised
                if self.findings_raised else 0.0)

    def crying_wolf(self, threshold: float = 0.15) -> bool:
        """Narcissistic G2: manufactures objections. Low upheld rate = wolf."""
        return self.findings_raised > 0 and self.upheld_rate() < threshold
