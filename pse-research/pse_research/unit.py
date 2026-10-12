"""
The research unit (build spec Sec 4). Phase 2.

One unit = one branch = one line of attack. Standard PSE Unit (Core, Boundary,
Registry, Theta) with domain content:
  CORE      mission {state, action, outcome}; written at instantiation, never
            self-modified; lifespan = compute budget in steps.
  BOUNDARY  registers CANDIDATE LEMMAS (own + siblings') held provisionally.
  REGISTRY  the EARNED BASIS: verified, load-bearing lemmas invoked without
            re-derivation. Budgets 0.30 total / 0.20 single now mean something.
  THETA     other-directed compute fraction (theta.py).

Phase 2 rule: theta is MEASURED and journalled but DRIVES NOTHING. Phase
transitions are SHARED_LIB-controlled (like fission); a unit cannot declare its
own phase, so `set_phase` is intended to be called by SHARED_LIB only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from . import config
from .config import Phase
from .theta import ThetaSeries


@dataclass
class Mission:
    state: str      # current best known bound / open sub-goal
    action: str     # the method being applied
    outcome: str    # the improvement targeted


@dataclass
class RegistryEntry:
    """A lemma the unit is developing toward / holds in its earned basis."""
    lemma_id: str
    verified: bool = False
    residency: int = 0                  # invocations across DISTINCT derivations
    mi: float = 0.0                     # contextual MI(candidate; mission)
    dependents: int = 0                 # other lemmas that depend on it
    closes_subgoal: bool = False        # directly closes a mission sub-goal
    first_seen_step: int = 0
    _alpha_run: int = 0                 # consecutive steps with alpha >= threshold
    alpha: float = 0.0                  # current load-bearing fraction

    def record_alpha(self, alpha: float) -> None:
        self.alpha = alpha
        if alpha >= config.ABSORPTION_MIN_ALPHA:
            self._alpha_run += 1
        else:
            self._alpha_run = 0

    def invoke(self, distinct: bool = True) -> None:
        if distinct:
            self.residency += 1

    @property
    def orphaned(self) -> bool:
        # NOT orphaned iff something depends on it OR it closes a sub-goal.
        return self.dependents == 0 and not self.closes_subgoal


class ResearchUnit:
    def __init__(self, unit_id: str, mission: Mission, branch: str,
                 lifespan_max: int, phase: Phase = Phase.RECON) -> None:
        self.unit_id = unit_id
        self.mission = mission           # Core self; never self-modified
        self.branch = branch
        self.lifespan_max = lifespan_max
        self.phase = phase
        self.step = 0
        self.theta = ThetaSeries()
        self.boundary: dict[str, RegistryEntry] = {}   # provisional candidates
        self.registry: dict[str, RegistryEntry] = {}   # earned basis
        self.dead = False
        self.death_reason: Optional[str] = None

    # ---- lifecycle --------------------------------------------------------
    def advance(self, theta_value: float) -> None:
        """One interaction: record theta, tick the step. Theta drives nothing."""
        self.theta.record(theta_value)
        self.step += 1

    def set_phase(self, phase: Phase) -> None:
        """SHARED_LIB-controlled. A unit cannot declare its own phase."""
        self.phase = phase

    def die(self, reason: str) -> None:
        self.dead = True
        self.death_reason = reason

    @property
    def budget_consumed(self) -> float:
        return self.step / self.lifespan_max if self.lifespan_max else 1.0

    # ---- boundary ---------------------------------------------------------
    def register_candidate(self, lemma_id: str, mi: float = 0.0) -> RegistryEntry:
        e = self.boundary.get(lemma_id)
        if e is None:
            e = RegistryEntry(lemma_id=lemma_id, mi=mi, first_seen_step=self.step)
            self.boundary[lemma_id] = e
        return e

    # ---- theta health (measured; informative only in Phase 2) -------------
    def theta_health(self, window: int = config.STABILITY_WINDOW) -> dict:
        s = self.theta.sigma(window)
        m = self.theta.mean(window)
        lo, hi = config.THETA_BANDS[self.phase]
        return {
            "sigma": s,
            "mean_fraction": m,
            "mean_scaled": m * 100.0,
            "sigma_healthy": config.HEALTHY_SIGMA_THETA[0] <= s
            <= config.HEALTHY_SIGMA_THETA[1],
            "flatline": s < config.SCHIZOID_SIGMA_THRESHOLD,
            "in_band": (lo / 100.0) <= m <= (hi / 100.0),
            "phase": self.phase.value,
        }

    # ---- absorption criterion (build spec Sec 4, Def 5) -------------------
    def absorption_ok(self, entry: RegistryEntry) -> tuple[bool, list[str]]:
        """
        ALL must hold. Returns (ok, list of failed condition labels). Condition
        (5) NOT ORPHANED is the whole defence against the Opening Spiral: nothing
        enters a basis for being TRUE, only for being USED.
        """
        failed: list[str] = []
        if not entry.verified:
            failed.append("status!=VERIFIED")
        if entry.residency < config.ABSORPTION_MIN_RESIDENCY:
            failed.append(f"residency<{config.ABSORPTION_MIN_RESIDENCY}")
        if entry._alpha_run < config.ABSORPTION_ALPHA_STEPS:
            failed.append(f"alpha>= {config.ABSORPTION_MIN_ALPHA} not sustained "
                          f"{config.ABSORPTION_ALPHA_STEPS} steps")
        if entry.mi < config.ABSORPTION_MIN_MI:
            failed.append(f"MI<{config.ABSORPTION_MIN_MI}")
        if entry.orphaned:
            failed.append("orphaned")
        return (not failed, failed)

    def try_absorb(self, lemma_id: str) -> tuple[bool, list[str]]:
        """Promote a boundary candidate to the earned basis if criterion holds."""
        entry = self.boundary.get(lemma_id)
        if entry is None:
            return (False, ["not at boundary"])
        ok, failed = self.absorption_ok(entry)
        if ok and self._registry_budget_ok(entry):
            self.registry[lemma_id] = entry
            del self.boundary[lemma_id]
        elif ok:
            failed.append("registry budget exceeded")
            ok = False
        return (ok, failed)

    # ---- registry budgets (0.30 total / 0.20 single) ----------------------
    def _registry_budget_ok(self, incoming: RegistryEntry) -> bool:
        """
        A unit whose basis is dominated by one imported lemma is decorating
        someone else's method, not developing one. alpha stands in for a lemma's
        share of the basis here.
        """
        shares = [e.alpha for e in self.registry.values()] + [incoming.alpha]
        total = sum(shares)
        if total > config.TOTAL_ORGANELLE_BUDGET:
            return False
        if any(s > config.SINGLE_ORGANELLE_CAP for s in shares):
            return False
        return True

    # ---- orphan flagging --------------------------------------------------
    def orphans(self) -> list[str]:
        """
        Verified boundary/registry entries with zero dependents past
        ORPHAN_FLAG_AFTER steps. The opening-spiral early view.
        """
        out = []
        for e in list(self.boundary.values()) + list(self.registry.values()):
            age = self.step - e.first_seen_step
            if e.verified and e.orphaned and age >= config.ORPHAN_FLAG_AFTER:
                out.append(e.lemma_id)
        return out
