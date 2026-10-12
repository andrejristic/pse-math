"""
Prover-Skeptic ledger + Seldon engine on synthetic data (build spec Sec 5, 9).

  python3 tests/test_pvp_seldon.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pse_research import config  # noqa: E402
from pse_research.prover_skeptic import Outcome, ProverSkepticLedger  # noqa: E402
from pse_research.seldon import BranchRecord, SeldonEngine  # noqa: E402


# ---- Prover-Skeptic --------------------------------------------------------
def test_skeptic_cannot_review_own() -> None:
    led = ProverSkepticLedger()
    raised = False
    try:
        led.open("c1", prover="u1", skeptic="u1", step=0)
    except ValueError:
        raised = True
    assert raised


def test_survivor_rewards_prover() -> None:
    led = ProverSkepticLedger(bounty_window=100)
    led.open("c1", prover="u1", skeptic="u2", step=0)
    led.on_gate_pass("c1", step=10)
    # before the window elapses: nothing settled
    assert led.settle_survivors(now_step=50) == []
    settled = led.settle_survivors(now_step=200)
    assert len(settled) == 1 and settled[0].outcome == Outcome.SURVIVED
    assert settled[0].prover_payoff == 1.0


def test_late_refutation_penalizes_both() -> None:
    led = ProverSkepticLedger(bounty_window=2000)
    led.open("c1", prover="u1", skeptic="u2", step=0)
    led.on_gate_pass("c1", step=10)
    ch = led.on_refutation("c1", step=500)   # within window
    assert ch is not None and ch.outcome == Outcome.REFUTED
    assert ch.prover_payoff == -1.0 and ch.skeptic_payoff == -1.0


def test_refutation_outside_window_no_penalty() -> None:
    led = ProverSkepticLedger(bounty_window=100)
    led.open("c1", prover="u1", skeptic="u2", step=0)
    led.on_gate_pass("c1", step=10)
    ch = led.on_refutation("c1", step=10_000)   # far outside window
    assert ch is not None and ch.outcome != Outcome.REFUTED
    assert ch.prover_payoff == 0.0 and ch.skeptic_payoff == 0.0


# ---- Seldon ----------------------------------------------------------------
def test_fitness_penalizes_refutations_more_than_rejects() -> None:
    a = BranchRecord("gaps", "sieve", verified_lemmas=5, rejects=3)
    b = BranchRecord("gaps", "sieve", verified_lemmas=5, refutations=3,
                     refutation_blast=6.0)
    assert a.fitness() > b.fitness()   # refutations cost far more


def test_seldon_conservative_on_thin_data() -> None:
    eng = SeldonEngine(max_shift=0.05)
    # only a few records -> weights must not move far from uniform (0.5 each)
    for _ in range(3):
        eng.record(BranchRecord("gaps", "sieve", verified_lemmas=100))
        eng.record(BranchRecord("gaps", "barrier", verified_lemmas=0, rejects=50))
    w = eng.update_weights("gaps")
    assert not eng.is_confident("gaps")
    # despite sieve looking much better, the move is clamped to <= 5%
    assert abs(w["sieve"] - 0.5) <= 0.05 + 1e-9, w


def test_seldon_acts_once_enough_data() -> None:
    eng = SeldonEngine(max_shift=0.05)
    for _ in range(config.MIN_CASES_FOR_STRATEGY_SHIFT):
        eng.record(BranchRecord("gaps", "sieve", verified_lemmas=100))
        eng.record(BranchRecord("gaps", "barrier", verified_lemmas=1, rejects=50))
    assert eng.is_confident("gaps")
    assert eng.top_method("gaps") == "sieve"


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
