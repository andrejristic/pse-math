"""
SHARED_LIB — the ONLY authority (build spec Sec 3).

There is exactly one gate in the system and it is here. Guardian 2 does not gate.
The chat unit does not gate. Every other component produces EVIDENCE; SHARED_LIB
alone accepts or rejects, and nothing is persisted that has not been accepted.

Order matters (build spec 3.1 note): verification first (cheap, objective,
rejects most bad candidates), unit-health second (expensive, statistical). No
point auditing a unit whose lemma does not typecheck.

Phase 1 scope:
  - The verification gate (C1-C7) is fully live.
  - The schizoid unit-health check is a STUB (no agents exist until Phase 2); it
    always passes and is clearly marked. The hook is real so Phase 2 drops in.
  - Guardian 2 semantic review is a STUB (Phase 5); returns no finding.
"""
from __future__ import annotations

import sqlite3
from typing import Optional

from .corpus import CorpusStore
from .journal import AppendOnlyJournal
from .model import Candidate, Check, Finding, GateResult, Status
from .verifier import Verifier, VerifierBackend


class ResearchSharedLib:
    def __init__(
        self,
        db_path: str,
        backend: Optional[VerifierBackend] = None,
        native_decide_whitelist: Optional[set[str]] = None,
    ) -> None:
        self.journal = AppendOnlyJournal(db_path)
        # Corpus shares the same connection/db as the journal metadata.
        self.corpus = CorpusStore(self.journal.conn)
        self.verifier = Verifier(
            self.corpus, backend=backend,
            native_decide_whitelist=native_decide_whitelist,
        )

    # ---- THE gate ---------------------------------------------------------
    def validate_contribution(self, candidate: Candidate) -> GateResult:
        self.journal.write("CANDIDATE_REGISTERED", candidate=candidate.id,
                           branch=candidate.branch, step=candidate.step)

        verdict = self.verifier.check(candidate)  # C1..C7, fail fast
        if not verdict.ok:
            assert verdict.failed_check is not None
            self.journal.write(
                "GATE_REJECT", candidate=candidate.id,
                failed=verdict.failed_check.value, detail=verdict.error_text,
            )
            return GateResult(accepted=False, failed_check=verdict.failed_check,
                              detail=verdict.error_text)

        # Inherited 4-condition schizoid check (Phase 2). Stub: no units yet.
        if not self._schizoid_check(candidate):
            self.journal.write("GATE_REJECT", candidate=candidate.id,
                               failed=Check.UNIT_HEALTH.value)
            return GateResult(accepted=False, failed_check=Check.UNIT_HEALTH,
                              detail="unit failed schizoid health check")

        # Semantic review is ADVISORY and does not block storage (Phase 5 stub).
        finding = self._guardian2_review(candidate)
        status = Status.VERIFIED_CONTESTED if finding.severe else Status.VERIFIED
        self.corpus.store(candidate, status=status)
        pass_payload = {"candidate": candidate.id, "status": status.value}
        # C5: an explicit non-vacuity waiver must be recorded in the journal
        # (build spec 3.1 C5). Without this the waiver leaves no audit trail.
        if candidate.hypotheses and candidate.human_waiver and not (
            candidate.witness and candidate.witness.strip()
        ):
            pass_payload["c5_human_waiver"] = True
        self.journal.write("GATE_PASS", **pass_payload)
        if finding.severe:
            self.journal.write("GUARDIAN2_FINDING", candidate=candidate.id,
                               kinds=finding.kinds, severe=True)
        return GateResult(accepted=True, status=status)

    def refute(self, lemma_id: str, counterexample: str, source: str) -> dict:
        """A verified lemma is later shown wrong; downstream invalidated (loud)."""
        if not self.corpus.exists(lemma_id):
            raise ValueError(f"cannot refute unknown lemma {lemma_id}")
        affected = self.corpus.transitive_dependents(lemma_id)
        self.corpus.mark(lemma_id, Status.REFUTED)
        for d in affected:
            self.corpus.mark(d, Status.INVALIDATED)
        self.journal.write("REFUTATION", lemma=lemma_id,
                           n_invalidated=len(affected), by=source,
                           counterexample=counterexample)
        return {"refuted": lemma_id, "invalidated": affected}

    # ---- stubs (become real in later phases) -----------------------------
    def _schizoid_check(self, candidate: Candidate) -> bool:
        # Phase 2: 4-condition schizoid check on the unit's theta trajectory.
        # No agents in Phase 1 -> always healthy.
        return True

    def _guardian2_review(self, candidate: Candidate) -> Finding:
        # Phase 5: G1-G6 judgement checks. No semantic review in Phase 1.
        return Finding.none()

    def close(self) -> None:
        self.journal.close()
