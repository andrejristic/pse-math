"""
Seldon Engine — research configuration (build spec Sec 9).

Unchanged mechanism; what changes is what fills the population record. Replicator
dynamic over (method, problem-shape) pairs, with the master-spec conservatism: no
weight shift beyond 5% before MIN_CASES_FOR_STRATEGY_SHIFT (20) observations.

[!] REJECTIONS AND REFUTATIONS ARE FITNESS DATA, weighted differently:
    reject = -1  (aggressive conjecturing is fine if survivors are strong)
    refutation = -(1 + blast_radius)  (post-acceptance error costs invalidation)

In this domain 20 branches is a LOT of wall-clock, so Seldon contributes nothing
useful for months. That is expected: build the engine now (on the Surface, with
synthetic records), do not tune anything on 3 data points.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from . import config


@dataclass
class BranchRecord:
    """One closed branch (build spec Sec 9 population record entry)."""
    problem_shape: str
    method: str
    verified_lemmas: int = 0
    orphan_rate: float = 0.0
    rejects: int = 0
    refutations: int = 0
    refutation_blast: float = 0.0     # summed blast radius of refutations
    outcome: str = "closed"

    def fitness(self) -> float:
        """Positive for verified lemmas produced; penalties per the [!] rule."""
        f = float(self.verified_lemmas)
        f += -1.0 * self.rejects
        f += -(1.0 * self.refutations + self.refutation_blast)
        return f


class SeldonEngine:
    def __init__(self, max_shift: float = 0.05) -> None:
        self.records: list[BranchRecord] = []
        self.max_shift = max_shift
        # replicator weights per (problem_shape, method)
        self.weights: dict[tuple[str, str], float] = {}

    def record(self, br: BranchRecord) -> None:
        self.records.append(br)

    def observations(self, problem_shape: str) -> int:
        return sum(1 for r in self.records if r.problem_shape == problem_shape)

    def _pairs(self, problem_shape: str) -> dict[str, list[BranchRecord]]:
        by_method: dict[str, list[BranchRecord]] = defaultdict(list)
        for r in self.records:
            if r.problem_shape == problem_shape:
                by_method[r.method].append(r)
        return by_method

    def update_weights(self, problem_shape: str) -> dict[str, float]:
        """
        Replicator step over methods for a problem shape. CONSERVATISM: if there
        are fewer than MIN_CASES_FOR_STRATEGY_SHIFT observations, weights are NOT
        moved beyond max_shift (5%). Returns current weights for the shape.
        """
        by_method = self._pairs(problem_shape)
        if not by_method:
            return {}

        # mean fitness per method
        fit = {m: sum(r.fitness() for r in rs) / len(rs)
               for m, rs in by_method.items()}
        methods = list(fit)
        # softmax-like non-negative shares from fitness
        lo = min(fit.values())
        shifted = {m: (fit[m] - lo + 1e-6) for m in methods}
        total = sum(shifted.values())
        target = {m: shifted[m] / total for m in methods}

        n_obs = self.observations(problem_shape)
        cur = {m: self.weights.get((problem_shape, m), 1.0 / len(methods))
               for m in methods}

        if n_obs < config.MIN_CASES_FOR_STRATEGY_SHIFT:
            # clamp each move to max_shift — do not act on thin data
            new = {}
            for m in methods:
                delta = target[m] - cur[m]
                delta = max(-self.max_shift, min(self.max_shift, delta))
                new[m] = cur[m] + delta
        else:
            new = target

        s = sum(new.values())
        new = {m: v / s for m, v in new.items()}
        for m in methods:
            self.weights[(problem_shape, m)] = new[m]
        return new

    def top_method(self, problem_shape: str) -> Optional[str]:
        w = self.update_weights(problem_shape)
        return max(w, key=w.get) if w else None

    def is_confident(self, problem_shape: str) -> bool:
        """Whether enough branches have closed to trust the recommendation."""
        return self.observations(problem_shape) >= config.MIN_CASES_FOR_STRATEGY_SHIFT
