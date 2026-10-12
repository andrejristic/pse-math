"""
Prover-Skeptic (Merlin-Arthur) bookkeeping — build spec Sec 5 ADDED form.

The structural core of research and the only asymmetric, near-zero-sum form: one
unit generates a candidate; a designated skeptic is paid to break it. Generation
is expensive, checking is cheap.

Roles are PER-CANDIDATE, not per-unit; a unit is never skeptic for its own output.

Payoffs (fed to Seldon as strategy fitness):
  prover  +  on a candidate that passes the gate AND survives the bounty window
  skeptic +  on a refutation, or a gap that forces a revision
  BOTH    -  on a candidate accepted and LATER refuted within the bounty window
[!] The SHARED penalty is the whole design: without it, the cheapest skeptic
    strategy is to approve everything. With it, every approval carries exposure.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from . import config


class Outcome(str, Enum):
    OPEN = "OPEN"
    PASSED = "PASSED"            # passed gate, bounty window still open
    SURVIVED = "SURVIVED"       # passed gate AND survived the bounty window
    REFUTED = "REFUTED"         # accepted then refuted within the window


@dataclass
class Challenge:
    candidate_id: str
    prover: str
    skeptic: str
    opened_step: int
    accepted_step: Optional[int] = None
    outcome: Outcome = Outcome.OPEN
    prover_payoff: float = 0.0
    skeptic_payoff: float = 0.0

    def __post_init__(self) -> None:
        if self.prover == self.skeptic:
            raise ValueError("a unit is never skeptic for its own candidate")


class ProverSkepticLedger:
    """Tracks challenges and settles payoffs when the bounty window closes."""

    def __init__(self, bounty_window: int = config.SKEPTIC_BOUNTY_WINDOW) -> None:
        self.bounty_window = bounty_window
        self.challenges: dict[str, Challenge] = {}

    def open(self, candidate_id: str, prover: str, skeptic: str,
             step: int) -> Challenge:
        ch = Challenge(candidate_id, prover, skeptic, opened_step=step)
        self.challenges[candidate_id] = ch
        return ch

    def on_gate_pass(self, candidate_id: str, step: int) -> None:
        ch = self.challenges.get(candidate_id)
        if ch:
            ch.accepted_step = step
            ch.outcome = Outcome.PASSED

    def on_refutation(self, candidate_id: str, step: int) -> Optional[Challenge]:
        """
        A refutation inside the bounty window penalizes BOTH prover and skeptic.
        Returns the settled challenge, or None if outside the window / unknown.
        """
        ch = self.challenges.get(candidate_id)
        if ch is None or ch.accepted_step is None:
            return None
        within = (step - ch.accepted_step) <= self.bounty_window
        if within:
            ch.outcome = Outcome.REFUTED
            ch.prover_payoff -= 1.0
            ch.skeptic_payoff -= 1.0   # the shared penalty
        return ch

    def on_skeptic_refutes(self, candidate_id: str) -> None:
        """Skeptic breaks a candidate BEFORE it is stored: skeptic +1."""
        ch = self.challenges.get(candidate_id)
        if ch:
            ch.skeptic_payoff += 1.0

    def settle_survivors(self, now_step: int) -> list[Challenge]:
        """
        Close out challenges whose bounty window has elapsed without refutation:
        prover +1 (candidate survived). Returns the newly-settled challenges.
        """
        settled = []
        for ch in self.challenges.values():
            if (ch.outcome == Outcome.PASSED and ch.accepted_step is not None
                    and (now_step - ch.accepted_step) > self.bounty_window):
                ch.outcome = Outcome.SURVIVED
                ch.prover_payoff += 1.0
                settled.append(ch)
        return settled
