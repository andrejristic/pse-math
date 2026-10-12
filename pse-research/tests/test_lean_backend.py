"""
Real-Lean integration for the gate: C1 runs actual elaboration via LeanBackend
instead of the symbolic stand-in. Proves the pluggable backend works end to end
on the installed toolchain (no mathlib needed — these are core-Lean proofs).

Skips cleanly if `lean` is not on PATH.

  python3 tests/test_lean_backend.py
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pse_research.model import Candidate, Check, Status  # noqa: E402
from pse_research.shared_lib import ResearchSharedLib  # noqa: E402
from pse_research.verifier import LeanBackend  # noqa: E402


def _cand(**over) -> Candidate:
    base = dict(
        id="L", name="lemma", informal_claim="claim",
        statement="theorem L : 1 + 1 = 2 := by rfl", proof_text="by rfl",
        structural_key="SK", hypotheses=[], used_hypotheses=[], dependencies=[],
        branch="B1", step=1,
    )
    base.update(over)
    return Candidate.from_dict(base)


def _make_lib(project_dir: str) -> tuple[ResearchSharedLib, str]:
    fd, dbp = tempfile.mkstemp(suffix=".db"); os.close(fd); os.unlink(dbp)
    lib = ResearchSharedLib(dbp, backend=LeanBackend(project_dir))
    return lib, dbp


def test_real_lean_good_accepted() -> None:
    proj = tempfile.mkdtemp(prefix="lean_proj_")
    lib, dbp = _make_lib(proj)
    try:
        r = lib.validate_contribution(
            _cand(id="good", statement="theorem good : 1 + 1 = 2 := by rfl"))
        assert r.accepted and r.status == Status.VERIFIED, r
    finally:
        lib.close(); os.unlink(dbp); shutil.rmtree(proj, ignore_errors=True)


def test_real_lean_type_error_rejected_at_c1() -> None:
    proj = tempfile.mkdtemp(prefix="lean_proj_")
    lib, dbp = _make_lib(proj)
    try:
        # 1 + 1 = 3 by rfl is a genuine elaboration error -> C1 must fire.
        r = lib.validate_contribution(
            _cand(id="wrong", statement="theorem wrong : 1 + 1 = 3 := by rfl"))
        assert not r.accepted and r.failed_check == Check.C1_PARSE, r
        assert "error" in r.detail.lower()
    finally:
        lib.close(); os.unlink(dbp); shutil.rmtree(proj, ignore_errors=True)


def test_real_lean_sorry_passes_c1_caught_by_c2() -> None:
    # KEY LESSON: `sorry` is only a WARNING in Lean (C1/elaboration returns ok).
    # The gate still rejects it — at C2, the escape-hatch text scan. This is why
    # C1 alone is not a soundness guarantee.
    proj = tempfile.mkdtemp(prefix="lean_proj_")
    lib, dbp = _make_lib(proj)
    try:
        r = lib.validate_contribution(_cand(
            id="hole",
            statement="theorem hole : 1 + 1 = 2 := by sorry",
            proof_text="by sorry"))
        assert not r.accepted and r.failed_check == Check.C2_ESCAPE_HATCHES, r
    finally:
        lib.close(); os.unlink(dbp); shutil.rmtree(proj, ignore_errors=True)


def test_real_lean_nontrivial_proof_accepted() -> None:
    # A slightly less trivial core-Lean proof to show real elaboration.
    proj = tempfile.mkdtemp(prefix="lean_proj_")
    lib, dbp = _make_lib(proj)
    try:
        stmt = ("theorem add_comm_two (a b : Nat) : a + b = b + a := by "
                "exact Nat.add_comm a b")
        r = lib.validate_contribution(
            _cand(id="addcomm", statement=stmt, proof_text="by exact Nat.add_comm a b"))
        assert r.accepted, r
    finally:
        lib.close(); os.unlink(dbp); shutil.rmtree(proj, ignore_errors=True)


def _run_all() -> int:
    if shutil.which("lean") is None:
        print("SKIP  lean not on PATH — real-Lean tests skipped")
        return 0
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
