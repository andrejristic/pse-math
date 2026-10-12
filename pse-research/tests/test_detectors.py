"""
Attractor detectors on synthetic theta series (build spec Sec 4). Proves each
pathology fires on a planted signal and stays quiet on a healthy one — the
Phase-4 acceptance criterion depends on catching failures you PLANTED.

  python3 tests/test_detectors.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pse_research import detectors as D  # noqa: E402
from pse_research.detectors import Pathology  # noqa: E402


def _healthy_series(n: int = 200) -> list[float]:
    # mean ~0.20, sigma ~0.02 (healthy band), decent autocorrelation
    return [0.20 + 0.02 * ((i % 4) - 1.5) / 1.5 for i in range(n)]


# ---- Helix (borderline: thrashing) -----------------------------------------
def test_helix_fires_on_thrashing() -> None:
    # big alternating swings: high sigma, negative acf
    series = [0.1 if i % 2 == 0 else 0.9 for i in range(50)]
    assert D.detect_helix(series)


def test_helix_quiet_on_healthy() -> None:
    assert not D.detect_helix(_healthy_series())


# ---- Circle (narcissistic: re-derives own consequences) --------------------
def test_circle_fires() -> None:
    # mu high (~0.5), sigma ~0 (flat), and effort flows inward (grad_out<<grad_in)
    series = [0.50] * 100
    grad_out = [0.01] * 100   # almost no other-directed work
    grad_in = [1.0] * 100     # heavy self-directed
    assert D.detect_circle(series, grad_out, grad_in)


def test_circle_quiet_when_outward() -> None:
    series = [0.50] * 100
    grad_out = [1.0] * 100    # plenty of outward work -> not narcissistic
    grad_in = [1.0] * 100
    assert not D.detect_circle(series, grad_out, grad_in)


# ---- Closing Spiral (codependent: premature convergence) -------------------
def test_closing_spiral_on_high_overlap() -> None:
    a = {"L1", "L2", "L3", "L4"}
    b = {"L1", "L2", "L3", "L5"}   # Jaccard = 3/5 = 0.6 > 0.30
    assert D.detect_closing_spiral(a, b)
    assert abs(D.basis_overlap(a, b) - 0.6) < 1e-9


def test_closing_spiral_quiet_on_divergent() -> None:
    a = {"L1", "L2", "L3"}
    b = {"L4", "L5", "L6"}         # disjoint -> 0 overlap
    assert not D.detect_closing_spiral(a, b)


# ---- Opening Spiral (schizoid: verified machinery, never used) --------------
def test_opening_spiral_fires() -> None:
    flat = [0.30] * 10             # flat sigma (< 0.01)
    assert D.detect_opening_spiral(flat, orphan_fraction=0.7, steps=6000)


def test_opening_spiral_needs_time_and_orphans() -> None:
    flat = [0.30] * 10
    # too early
    assert not D.detect_opening_spiral(flat, orphan_fraction=0.7, steps=100)
    # not enough orphans
    assert not D.detect_opening_spiral(flat, orphan_fraction=0.2, steps=6000)


# ---- classifier ordering ---------------------------------------------------
def test_classify_healthy_is_none() -> None:
    s = _healthy_series()
    assert D.classify_unit(s, [0.5] * len(s), [0.5] * len(s),
                           orphan_fraction=0.0, steps=6000) == Pathology.NONE


def test_classify_prefers_helix_first() -> None:
    thrash = [0.1 if i % 2 == 0 else 0.9 for i in range(50)]
    assert D.classify_unit(thrash, [0.01] * 50, [1.0] * 50,
                           orphan_fraction=0.9, steps=6000) == Pathology.HELIX


def _run_all() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t(); print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1; print(f"FAIL  {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1; print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run_all())
