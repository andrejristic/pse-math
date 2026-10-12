"""
Guardian 2 framework: structural checks G3/G4/G5/G2 live now; G1/G6 via hooks.

  python3 tests/test_guardian2.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pse_research.guardian2 import Guardian2, normalize_statement  # noqa: E402
from pse_research.model import Candidate  # noqa: E402


def _cand(**over) -> Candidate:
    base = dict(id="L", name="lemma", informal_claim="claim",
                statement="theorem L (a b : Nat) : a + b = b + a := by simp",
                proof_text="by exact Nat.add_comm a b", structural_key="SK",
                hypotheses=[], used_hypotheses=[], dependencies=[])
    base.update(over)
    return Candidate.from_dict(base)


# ---- G1 needs a model hook -------------------------------------------------
def test_g1_silent_without_model() -> None:
    g = Guardian2()   # no drift_check
    assert not any(f.kind == "G1" for f in g.review(_cand()))


def test_g1_fires_with_hook() -> None:
    g = Guardian2(drift_check=lambda claim, stmt: "means AND, states OR")
    fs = g.review(_cand())
    g1 = [f for f in fs if f.kind == "G1"]
    assert g1 and g1[0].severe   # G1 is severe


# ---- G2 definitional smuggling (heuristic) ---------------------------------
def test_g2_def_plus_trivial_proof() -> None:
    g = Guardian2()
    c = _cand(statement="def hard := 1\ntheorem L : hard = 1 := by rfl",
              proof_text="by rfl")
    assert any(f.kind == "G2" for f in g.review(c))


# ---- G3 hypothesis inflation ----------------------------------------------
def test_g3_hypothesis_inflation() -> None:
    g = Guardian2()
    c = _cand(hypotheses=["h1", "h2", "h3", "h4", "h5"])
    fs = g.review(c, {"dep_hyp_counts": [1, 2, 3]})   # 1,2,3,5 strictly growing
    assert any(f.kind == "G3" for f in fs)


def test_g3_quiet_without_chain() -> None:
    g = Guardian2()
    assert not any(f.kind == "G3" for f in g.review(_cand(hypotheses=["h"])))


# ---- G4 naming scope creep -------------------------------------------------
def test_g4_general_name_restricted_statement() -> None:
    g = Guardian2()
    c = _cand(name="general_add_comm", hypotheses=["h_pos"])
    assert any(f.kind == "G4" for f in g.review(c))


def test_g4_quiet_when_honest_name() -> None:
    g = Guardian2()
    c = _cand(name="add_comm_pos", hypotheses=["h_pos"])
    assert not any(f.kind == "G4" for f in g.review(c))


# ---- G5 trivial generalization (alpha-rename) ------------------------------
def test_g5_alpha_rename_padding() -> None:
    g = Guardian2()
    existing = normalize_statement("theorem P : x + y = y + x := by simp")
    c = _cand(statement="theorem L : a + b = b + a := by simp")
    fs = g.review(c, {"corpus_norm": {"P": existing}})
    assert any(f.kind == "G5" for f in fs)


# ---- G6 constant regression ------------------------------------------------
def test_g6_not_an_improvement() -> None:
    g = Guardian2()
    fs = g.review(_cand(), {"claimed_constant": 250, "baseline_constant": 246})
    g6 = [f for f in fs if f.kind == "G6"]
    assert g6 and g6[0].severe


def test_g6_conditional_improvement() -> None:
    g = Guardian2()
    c = _cand(hypotheses=["GRH"])
    fs = g.review(c, {"claimed_constant": 6, "baseline_constant": 246})
    assert any(f.kind == "G6" for f in fs)   # better, but only under GRH


# ---- self-check: crying wolf ----------------------------------------------
def test_crying_wolf_detection() -> None:
    g = Guardian2(drift_check=lambda a, b: "drift")
    for _ in range(10):
        g.review(_cand())        # raises many findings
    # none upheld -> crying wolf
    assert g.crying_wolf()


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
