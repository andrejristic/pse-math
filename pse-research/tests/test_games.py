"""
Bayesian posterior + confidence + the cheap!=costly rule (build spec Sec 5).

  python3 tests/test_games.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pse_research.games import ENABLED_FORMS, GameForm, Posterior  # noqa: E402


def test_uniform_prior_zero_confidence_suppressed() -> None:
    p = Posterior()
    assert abs(p.confidence()) < 1e-9
    assert p.suppressed()


def test_costly_evidence_raises_confidence() -> None:
    p = Posterior()
    for _ in range(3):
        p.update_costly({GameForm.WAR_OF_ATTRITION: 4.0})
    assert p.most_likely() == GameForm.WAR_OF_ATTRITION
    assert p.confidence() > 0.3 and not p.suppressed()


def test_cheap_signal_moves_less_than_costly() -> None:
    like = {GameForm.SIGNALLING: 4.0}
    pc = Posterior(); pc.update_cheap(like)
    px = Posterior(); px.update_costly(like)
    # the costly update must concentrate probability more than the cheap one
    assert px.confidence() > pc.confidence()
    # and a cheap signal, no matter how strong, stays modest after one hit
    assert pc.p[pc.labels.index(GameForm.SIGNALLING)] < \
        px.p[px.labels.index(GameForm.SIGNALLING)]


def test_partial_reset_moves_toward_uniform() -> None:
    p = Posterior()
    for _ in range(5):
        p.update_costly({GameForm.STAG_HUNT: 5.0})
    c_before = p.confidence()
    p.partial_reset(0.5)
    assert p.confidence() < c_before
    # full reset returns to ~uniform
    p.partial_reset(1.0)
    assert abs(p.confidence()) < 1e-6


def test_probabilities_normalized() -> None:
    p = Posterior()
    p.update_costly({GameForm.GLOBAL_GAMES: 2.0, GameForm.STAG_HUNT: 0.5})
    assert abs(sum(p.p) - 1.0) < 1e-9


def test_library_has_no_dropped_forms() -> None:
    # exactly the 5 enabled forms; the 7 mixed-motive forms are absent
    assert len(ENABLED_FORMS) == 5
    assert GameForm.PROVER_SKEPTIC in ENABLED_FORMS


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
