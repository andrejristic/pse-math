"""
Theta series statistics (build spec Sec 4 THETA, Sec 2 sigma invariant).

Theta = other-directed compute fraction, stored as a FRACTION in [0, 1].
("Other" = corpus, sibling output, counterexample search against own claims;
"self" = generating/pushing own line.) The build spec quotes theta bands on a
0-100 scale (e.g. [25,35]) and the sigma invariant on a 0-1 scale ([0.015,0.03]);
we store the fraction and convert bands by /100 so both match at once.

Pure Python, no numpy dependency, so the core runs anywhere.
"""
from __future__ import annotations

import math
from typing import Sequence


def mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def sigma(xs: Sequence[float]) -> float:
    """Population standard deviation."""
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    var = sum((x - m) ** 2 for x in xs) / len(xs)
    return math.sqrt(var)


def acf(xs: Sequence[float], lag: int = 1) -> float:
    """Autocorrelation at `lag`. Returns 0.0 for degenerate (flat/short) series."""
    n = len(xs)
    if n <= lag:
        return 0.0
    m = mean(xs)
    denom = sum((x - m) ** 2 for x in xs)
    if denom == 0:
        return 0.0
    num = sum((xs[i] - m) * (xs[i + lag] - m) for i in range(n - lag))
    return num / denom


def gradient_ratio(other: Sequence[float], own: Sequence[float]) -> float:
    """
    Grad_out / Grad_in proxy (Circle detection). `other` = other-directed effort
    increments, `own` = self-directed increments. Returns a large number when
    self-effort is ~0 (avoids div-by-zero), small when other-effort is ~0.
    """
    go = sum(other)
    gi = sum(own)
    if gi == 0:
        return math.inf if go > 0 else 0.0
    return go / gi


class ThetaSeries:
    """A rolling theta trace for one unit. Values are fractions in [0, 1]."""

    def __init__(self) -> None:
        self._xs: list[float] = []

    def record(self, value: float) -> None:
        if not (0.0 <= value <= 1.0):
            raise ValueError(f"theta must be a fraction in [0,1], got {value}")
        self._xs.append(value)

    def __len__(self) -> int:
        return len(self._xs)

    def values(self) -> list[float]:
        return list(self._xs)

    def window(self, n: int) -> list[float]:
        return self._xs[-n:] if n > 0 else list(self._xs)

    def mean(self, n: int = 0) -> float:
        return mean(self.window(n) if n else self._xs)

    def sigma(self, n: int = 0) -> float:
        return sigma(self.window(n) if n else self._xs)

    def acf(self, lag: int = 1, n: int = 0) -> float:
        return acf(self.window(n) if n else self._xs, lag)
