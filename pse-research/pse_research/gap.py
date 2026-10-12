"""
GAP_HYPOTHESIS — an outward-facing finding (addendum A3).

A Guardian-2 finding turned OUTWARD: not "is this stored lemma sick?" but "is
there a hole at the frontier worth attacking?". Conjectural by construction; it
NEVER touches the corpus (nothing to typecheck) — it lives in the journal and the
queue only. This upgrades Honest Null (build spec F5) from passive to active.

Pipeline: born (B4/B3/CONSOLIDATION) -> dedup + prover-skeptic filter -> ranked
into the ONE queue -> human verdict -> feedback (val(B)) that calibrates the bar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

from .queue import HumanItem, HumanQueue


class GapState(str, Enum):
    PROPOSED = "PROPOSED"
    QUEUED = "QUEUED"
    CONFIRMED = "CONFIRMED"    # worth attacking -> a branch may be opened
    SPAWNED = "SPAWNED"        # a branch has been opened against it
    DISMISSED = "DISMISSED"    # "budalastina" — negative training signal
    DEFERRED = "DEFERRED"
    DROPPED = "DROPPED"        # dedup or skeptic filled it (silent)
    RESOLVED = "RESOLVED"      # later proven via the normal gate


class Verdict(str, Enum):
    CONFIRMED = "CONFIRMED"
    DISMISSED = "DISMISSED"
    DEFERRED = "DEFERRED"


@dataclass
class GapHypothesis:
    id: str
    informal_gap: str          # human terms (I-4: domain language, no strategy)
    evidence: str              # WHY it is a gap (pointer to B4 proof / DAG hole)
    blast_radius: float        # what attacking it would unlock
    default_action: str = "archive as un-investigated"
    register: str = "CONJECTURAL"   # never stated as fact (R2)
    branch: str = "B4"
    step: int = 0
    state: GapState = GapState.PROPOSED

    def __post_init__(self) -> None:
        if not self.evidence or not self.evidence.strip():
            raise ValueError("a GAP_HYPOTHESIS must carry concrete evidence")
        if self.register != "CONJECTURAL":
            raise ValueError("a GAP_HYPOTHESIS is always CONJECTURAL")
        if self.blast_radius is None:
            raise ValueError("a GAP_HYPOTHESIS must carry a blast radius")


class GapManager:
    """
    Owns open gaps and the producer-side filters. Journal is any object with
    .write(event_type, **payload); callbacks decouple it from the corpus/skeptic.
    """

    def __init__(self, queue: HumanQueue, journal,
                 corpus_covers: Optional[Callable[[GapHypothesis], bool]] = None,
                 skeptic_fills: Optional[Callable[[GapHypothesis], bool]] = None
                 ) -> None:
        self.queue = queue
        self.journal = journal
        self.corpus_covers = corpus_covers or (lambda g: False)
        self.skeptic_fills = skeptic_fills or (lambda g: False)
        self.open: dict[str, GapHypothesis] = {}
        # val(B) feedback: upheld/dismissed tallies calibrate the bar.
        self.confirmed_count = 0
        self.dismissed_count = 0

    def _duplicate(self, gap: GapHypothesis) -> bool:
        return any(g.informal_gap.strip().lower() == gap.informal_gap.strip().lower()
                   for g in self.open.values())

    def emit(self, gap: GapHypothesis) -> GapState:
        """Run the producer-side filters; queue only survivors."""
        # 1. outward dedup (C6 reused) — corpus or an already-open gap
        if self.corpus_covers(gap) or self._duplicate(gap):
            gap.state = GapState.DROPPED
            self.journal.write("GAP_DROPPED", gap=gap.id, reason="dedup")
            return gap.state
        # 2. prover-skeptic, outward — a skeptic paid to fill it
        if self.skeptic_fills(gap):
            gap.state = GapState.DROPPED
            self.journal.write("GAP_DROPPED", gap=gap.id, reason="skeptic_filled")
            return gap.state
        # survivor -> queue, ranked by blast radius, competing for A5 slots
        gap.state = GapState.QUEUED
        self.open[gap.id] = gap
        self.queue.push(HumanItem(
            kind="GAP_HYPOTHESIS", node=gap.id, summary=gap.informal_gap,
            affects=gap.evidence, blast_radius=gap.blast_radius,
            default_action=gap.default_action, created_step=gap.step,
            cost="opening a branch against it",
        ))
        self.journal.write("GAP_HYPOTHESIS", gap=gap.id,
                           blast=gap.blast_radius, evidence=gap.evidence)
        return gap.state

    def verdict(self, gap_id: str, verdict: Verdict) -> GapState:
        gap = self.open.get(gap_id)
        if gap is None:
            raise ValueError(f"unknown open gap {gap_id}")
        self.journal.write("HUMAN_DECISION", node=gap_id, kind="GAP_HYPOTHESIS",
                           verdict=verdict.value)
        self.queue.resolve(gap_id, kind="GAP_HYPOTHESIS")
        if verdict == Verdict.CONFIRMED:
            gap.state = GapState.SPAWNED         # a branch may be opened
            self.confirmed_count += 1
            del self.open[gap_id]
        elif verdict == Verdict.DISMISSED:
            gap.state = GapState.DISMISSED       # negative training signal
            self.dismissed_count += 1
            del self.open[gap_id]
        else:
            gap.state = GapState.DEFERRED
        return gap.state

    def upheld_rate(self) -> float:
        """val(B): fraction of decided gaps the human confirmed. Low = crying wolf."""
        total = self.confirmed_count + self.dismissed_count
        return self.confirmed_count / total if total else 0.0

    def barrier_map(self) -> dict:
        """The Honest-Null deliverable (c): what was flagged and what became of it."""
        return {
            "open": len(self.open),
            "confirmed": self.confirmed_count,
            "dismissed": self.dismissed_count,
            "upheld_rate": round(self.upheld_rate(), 3),
        }
