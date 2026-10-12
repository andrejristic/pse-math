"""
PSE Mathematical Research System — Phase 1 data model.

Everything the gate reasons about is declared here. The Candidate is a
BACKEND-INDEPENDENT representation: the mechanical checks C1-C7 operate on these
fields. When a real Lean toolchain is wired in (LeanBackend, see verifier.py),
the same fields are DERIVED from actual elaboration instead of declared by hand.

Design invariants enforced by the types here:
  - informal_claim is required and immutable (the basis for Guardian 2 / G1).
  - status transitions go only through SHARED_LIB; nothing else constructs a
    stored status.
"""
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class Status(str, Enum):
    """Lifecycle status of a lemma in the corpus."""
    VERIFIED = "VERIFIED"
    VERIFIED_CONTESTED = "VERIFIED_CONTESTED"  # verified, open Guardian-2 finding
    REFUTED = "REFUTED"                        # later shown wrong
    INVALIDATED = "INVALIDATED"                # transitively downstream of a refute


class Check(str, Enum):
    """The seven mechanical checks, in fail-fast order (cheapest first)."""
    C1_PARSE = "C1_PARSE"                      # proof term elaborates
    C2_ESCAPE_HATCHES = "C2_ESCAPE_HATCHES"    # no sorry/admit/axiom/native_decide
    C3_CYCLES = "C3_CYCLES"                    # DAG stays acyclic
    C4_HYP_UTILIZATION = "C4_HYP_UTILIZATION"  # every hypothesis is referenced
    C5_NON_VACUITY = "C5_NON_VACUITY"          # hypotheses satisfiable
    C6_NON_DUPLICATION = "C6_NON_DUPLICATION"  # not subsumed by existing lemma
    C7_DEP_CLOSURE = "C7_DEP_CLOSURE"          # every dependency is VERIFIED
    UNIT_HEALTH = "UNIT_HEALTH"                # phase-2 schizoid check (stub now)


@dataclass
class Candidate:
    """A candidate lemma presented to the gate. Nothing is stored until accepted."""
    id: str
    name: str
    informal_claim: str          # REQUIRED, immutable — the theorem you MEANT
    statement: str               # the formal statement text (the theorem you WROTE)
    proof_text: str              # Lean proof term / tactic block, as text
    structural_key: str          # normalized form for structural dedup (C6)
    hypotheses: list[str] = field(default_factory=list)
    used_hypotheses: list[str] = field(default_factory=list)  # referenced in proof
    dependencies: list[str] = field(default_factory=list)     # lemma ids relied on
    witness: Optional[str] = None      # satisfiability witness for C5
    human_waiver: bool = False         # explicit human non-vacuity waiver (C5)
    # Backend hint: in SYMBOLIC mode, whether the term is declared to elaborate.
    # A LeanBackend ignores this and elaborates for real.
    parses: bool = True
    parse_error: str = ""
    branch: str = "B0"
    step: int = 0

    def __post_init__(self) -> None:
        if not self.informal_claim or not self.informal_claim.strip():
            raise ValueError(
                f"candidate {self.id}: informal_claim is required and non-empty "
                "(it is the immutable basis for Guardian 2 / statement-drift)."
            )

    def provenance(self) -> dict[str, Any]:
        return {"branch": self.branch, "step": self.step, "name": self.name}

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Candidate":
        known = {f.name for f in dataclasses.fields(Candidate)}
        unknown = set(d) - known
        if unknown:
            raise ValueError(f"unknown candidate fields: {sorted(unknown)}")
        return Candidate(**d)

    @staticmethod
    def from_json_file(path: str) -> "Candidate":
        with open(path, "r", encoding="utf-8") as fh:
            return Candidate.from_dict(json.load(fh))


@dataclass
class Verdict:
    """Result of running C1-C7 over a candidate."""
    ok: bool
    failed_check: Optional[Check] = None
    error_text: str = ""

    @staticmethod
    def passed() -> "Verdict":
        return Verdict(ok=True)

    @staticmethod
    def fail(check: Check, error_text: str) -> "Verdict":
        return Verdict(ok=False, failed_check=check, error_text=error_text)


@dataclass
class Finding:
    """A Guardian-2 (semantic) finding. Advisory only — never gates. Stub in P1."""
    kinds: list[str] = field(default_factory=list)
    severe: bool = False
    detail: str = ""

    @staticmethod
    def none() -> "Finding":
        return Finding()


@dataclass
class GateResult:
    """What SHARED_LIB.validate_contribution returns."""
    accepted: bool
    status: Optional[Status] = None       # set when accepted
    failed_check: Optional[Check] = None  # set when rejected
    detail: str = ""
