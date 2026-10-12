"""
Phase 2 acceptance: a research unit measures a coherent theta trajectory and the
absorption criterion / orphan flagging behave. Theta drives nothing here.

  python3 tests/test_phase2_unit.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pse_research import config  # noqa: E402
from pse_research.config import Phase  # noqa: E402
from pse_research.theta import acf, mean, sigma  # noqa: E402
from pse_research.unit import Mission, RegistryEntry, ResearchUnit  # noqa: E402


def _mk_unit(phase=Phase.ASSAULT) -> ResearchUnit:
    return ResearchUnit(
        unit_id="u1",
        mission=Mission(state="k_0=246", action="maynard-tao sieve",
                        outcome="narrow admissible tuple"),
        branch="B2", lifespan_max=10_000, phase=phase,
    )


# ---- theta statistics ------------------------------------------------------
def test_theta_stats_basic() -> None:
    assert abs(mean([0.2, 0.2, 0.2]) - 0.2) < 1e-9
    assert sigma([0.2, 0.2, 0.2]) < 1e-9        # ~0 up to float error
    assert sigma([0.1, 0.3]) > 0.0
    # perfectly alternating series has strongly negative lag-1 acf
    assert acf([0.0, 1.0, 0.0, 1.0, 0.0, 1.0], lag=1) < 0


# ---- unit records theta; drives nothing ------------------------------------
def test_unit_advances_and_measures() -> None:
    u = _mk_unit()
    # theta around 0.20, ASSAULT band [0.15,0.25], with sigma in the healthy
    # band [0.015,0.03] (a working unit, not a flatlined one).
    vals = [0.18, 0.22, 0.17, 0.23, 0.19, 0.21, 0.18, 0.22]
    for v in vals:
        u.advance(v)
    assert u.step == len(vals)
    h = u.theta_health(window=len(vals))
    assert h["in_band"], h
    assert not h["flatline"], h
    assert h["sigma_healthy"], h


def test_flatline_detected_in_health() -> None:
    u = _mk_unit()
    for _ in range(50):
        u.advance(0.20)  # perfectly flat -> sigma 0 -> flatline
    h = u.theta_health(window=50)
    assert h["flatline"] and h["sigma"] == 0.0, h


# ---- absorption criterion --------------------------------------------------
def _good_entry() -> RegistryEntry:
    e = RegistryEntry(lemma_id="L", verified=True,
                      residency=config.ABSORPTION_MIN_RESIDENCY,
                      mi=0.75, dependents=1, first_seen_step=0)
    for _ in range(config.ABSORPTION_ALPHA_STEPS):
        e.record_alpha(0.15)
    return e


def test_absorption_passes_when_all_hold() -> None:
    u = _mk_unit()
    e = _good_entry()
    u.boundary[e.lemma_id] = e
    ok, failed = u.try_absorb("L")
    assert ok, failed
    assert "L" in u.registry and "L" not in u.boundary


def test_absorption_blocked_by_orphan() -> None:
    # Condition (5): truth is not enough; it must be USED.
    u = _mk_unit()
    e = _good_entry()
    e.dependents = 0
    e.closes_subgoal = False
    u.boundary[e.lemma_id] = e
    ok, failed = u.try_absorb("L")
    assert not ok and "orphaned" in failed, failed


def test_absorption_blocked_by_low_residency_and_mi() -> None:
    u = _mk_unit()
    e = _good_entry()
    e.residency = 10
    e.mi = 0.10
    u.boundary[e.lemma_id] = e
    ok, failed = u.try_absorb("L")
    assert not ok
    assert any("residency" in f for f in failed) and any("MI" in f for f in failed)


def test_absorption_blocked_by_unsustained_alpha() -> None:
    u = _mk_unit()
    e = RegistryEntry(lemma_id="L", verified=True,
                      residency=config.ABSORPTION_MIN_RESIDENCY, mi=0.9,
                      dependents=1)
    e.record_alpha(0.15)  # only one step, not sustained
    u.boundary[e.lemma_id] = e
    ok, failed = u.try_absorb("L")
    assert not ok and any("sustained" in f for f in failed), failed


# ---- registry budget (0.30 total / 0.20 single) ----------------------------
def test_registry_single_cap_blocks_dominant_lemma() -> None:
    u = _mk_unit()
    e = _good_entry()
    for _ in range(config.ABSORPTION_ALPHA_STEPS):
        e.record_alpha(0.25)  # single-lemma share above the 0.20 cap
    u.boundary[e.lemma_id] = e
    ok, failed = u.try_absorb("L")
    assert not ok and "registry budget exceeded" in failed, failed


# ---- orphan flagging -------------------------------------------------------
def test_orphan_flagging() -> None:
    u = _mk_unit()
    e = RegistryEntry(lemma_id="orph", verified=True, dependents=0,
                      closes_subgoal=False, first_seen_step=0)
    u.boundary["orph"] = e
    u.step = config.ORPHAN_FLAG_AFTER + 1
    assert "orph" in u.orphans()
    # a used lemma is never an orphan
    e.dependents = 1
    assert "orph" not in u.orphans()


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
