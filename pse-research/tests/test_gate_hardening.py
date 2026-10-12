"""
Phase 1 hardening suite — adversarial pressure on the gate beyond the basic
C1-C7 acceptance. The gate is the foundation; a leak here (a false ACCEPT) is the
expensive kind. These tests hunt for leaks, verify nothing is stored on reject,
verify persistence across reopen, and pin down deliberate policy decisions.

  python3 tests/test_gate_hardening.py
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pse_research.model import Candidate, Check, Status  # noqa: E402
from pse_research.shared_lib import ResearchSharedLib  # noqa: E402


def _new_path() -> str:
    fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd); os.unlink(path)
    return path


def _lib(**kw) -> tuple[ResearchSharedLib, str]:
    p = _new_path()
    return ResearchSharedLib(p, **kw), p


def _cand(**over) -> Candidate:
    base = dict(
        id="L", name="lemma", informal_claim="claim",
        statement="theorem L : True := by trivial", proof_text="by trivial",
        structural_key="SK", hypotheses=[], used_hypotheses=[], dependencies=[],
        branch="B1", step=1,
    )
    base.update(over)
    return Candidate.from_dict(base)


# ---- LEAK HUNT: term-level sorry (sorryAx) must not slip through ------------
def test_leak_sorryax_caught() -> None:
    lib, path = _lib()
    try:
        c = _cand(id="L_ax", proof_text="Lean.sorryAx _ true")
        r = lib.validate_contribution(c)
        assert not r.accepted and r.failed_check == Check.C2_ESCAPE_HATCHES, r
        assert lib.corpus.counts_by_status() == {}, "nothing may be stored"
    finally:
        lib.close(); os.unlink(path)


def test_admit_caught() -> None:
    lib, path = _lib()
    try:
        r = lib.validate_contribution(_cand(id="L_admit", proof_text="by admit"))
        assert not r.accepted and r.failed_check == Check.C2_ESCAPE_HATCHES, r
    finally:
        lib.close(); os.unlink(path)


def test_new_axiom_declaration_caught() -> None:
    lib, path = _lib()
    try:
        c = _cand(id="L_axm", statement="axiom cheat : HardThing")
        r = lib.validate_contribution(c)
        assert not r.accepted and r.failed_check == Check.C2_ESCAPE_HATCHES, r
    finally:
        lib.close(); os.unlink(path)


# ---- C2 must NOT false-positive on innocent identifiers --------------------
def test_c2_no_false_positive_on_identifier() -> None:
    # "sorryish" / "admittedly" contain the substrings but are not the hatches.
    lib, path = _lib()
    try:
        c = _cand(id="L_ok", proof_text="by exact admittedly_sorryish_lemma")
        r = lib.validate_contribution(c)
        assert r.accepted, f"innocent identifier wrongly rejected: {r}"
    finally:
        lib.close(); os.unlink(path)


# ---- nothing is stored on ANY rejection ------------------------------------
def test_nothing_stored_on_reject() -> None:
    lib, path = _lib()
    try:
        for c in (
            _cand(id="a", parses=False),                       # C1
            _cand(id="b", proof_text="by sorry"),              # C2
            _cand(id="c", dependencies=["c"]),                 # C3
            _cand(id="d", hypotheses=["h"], used_hypotheses=[], witness="w"),  # C4
            _cand(id="e", hypotheses=["h"], used_hypotheses=["h"]),            # C5
            _cand(id="f", dependencies=["missing"]),           # C7
        ):
            assert not lib.validate_contribution(c).accepted
        assert lib.corpus.counts_by_status() == {}, "reject must store nothing"
    finally:
        lib.close(); os.unlink(path)


# ---- fail-fast reports the CHEAPEST failing check --------------------------
def test_failfast_reports_cheapest() -> None:
    # This candidate fails C2 (sorry) AND C4 (unused hyp) AND C5. Must report C2.
    lib, path = _lib()
    try:
        c = _cand(id="multi", proof_text="by sorry",
                  hypotheses=["h"], used_hypotheses=[])
        r = lib.validate_contribution(c)
        assert r.failed_check == Check.C2_ESCAPE_HATCHES, r
    finally:
        lib.close(); os.unlink(path)


# ---- re-pushing an existing id is blocked ----------------------------------
def test_duplicate_id_blocked() -> None:
    lib, path = _lib()
    try:
        assert lib.validate_contribution(_cand(id="X", structural_key="SKX")).accepted
        r = lib.validate_contribution(_cand(id="X", structural_key="SKX2"))
        assert not r.accepted and r.failed_check == Check.C3_CYCLES, r
    finally:
        lib.close(); os.unlink(path)


# ---- C6: different structural keys are NOT duplicates -----------------------
def test_c6_no_false_positive_different_key() -> None:
    lib, path = _lib()
    try:
        assert lib.validate_contribution(_cand(id="p", structural_key="K1")).accepted
        assert lib.validate_contribution(_cand(id="q", structural_key="K2")).accepted
    finally:
        lib.close(); os.unlink(path)


# ---- C6: a REFUTED lemma's structural key may be reused ---------------------
def test_c6_refuted_key_reusable() -> None:
    lib, path = _lib()
    try:
        assert lib.validate_contribution(_cand(id="old", structural_key="KR")).accepted
        lib.refute("old", "wrong", source="t")
        # same structural key is now free because the holder is dead
        r = lib.validate_contribution(_cand(id="new", structural_key="KR"))
        assert r.accepted, f"refuted key should be reusable: {r}"
    finally:
        lib.close(); os.unlink(path)


# ---- C7 policy: depending on VERIFIED_CONTESTED is allowed (documented) -----
def test_c7_contested_dependency_allowed() -> None:
    # A contested lemma still typechecks; the refute cascade tracks the risk.
    lib, path = _lib()
    try:
        assert lib.validate_contribution(_cand(id="base", structural_key="KB")).accepted
        lib.corpus.mark("base", Status.VERIFIED_CONTESTED)
        r = lib.validate_contribution(
            _cand(id="dep", structural_key="KD", dependencies=["base"]))
        assert r.accepted, f"contested dependency should be allowed: {r}"
    finally:
        lib.close(); os.unlink(path)


# ---- C5: human waiver path works AND is recorded in the journal -------------
def test_c5_human_waiver_recorded() -> None:
    lib, path = _lib()
    try:
        c = _cand(id="w", hypotheses=["h"], used_hypotheses=["h"],
                  witness=None, human_waiver=True)
        assert lib.validate_contribution(c).accepted
        passes = [e for e in lib.journal.read_all() if e["type"] == "GATE_PASS"]
        assert passes and passes[-1]["payload"].get("c5_human_waiver") is True, \
            "human waiver must be journalled"
    finally:
        lib.close(); os.unlink(path)


# ---- persistence: corpus + journal survive close/reopen --------------------
def test_persistence_across_reopen() -> None:
    path = _new_path()
    lib = ResearchSharedLib(path)
    lib.validate_contribution(_cand(id="persist", structural_key="KP"))
    seq_before = lib.journal.last_seq()
    lib.close()
    try:
        lib2 = ResearchSharedLib(path)
        assert lib2.corpus.status_of("persist") == Status.VERIFIED
        assert lib2.journal.last_seq() == seq_before
        # a re-push of the same id is still blocked after reopen
        assert not lib2.validate_contribution(
            _cand(id="persist", structural_key="KP2")).accepted
        lib2.close()
    finally:
        for ext in ("", "-wal", "-shm"):
            if os.path.exists(path + ext):
                os.unlink(path + ext)


# ---- transitive dependents on a diamond DAG --------------------------------
def test_diamond_transitive_dependents() -> None:
    #     A          refute A  ->  B, C, D all invalidated
    #    / \
    #   B   C
    #    \ /
    #     D
    lib, path = _lib()
    try:
        lib.validate_contribution(_cand(id="A", structural_key="dA"))
        lib.validate_contribution(_cand(id="B", structural_key="dB", dependencies=["A"]))
        lib.validate_contribution(_cand(id="C", structural_key="dC", dependencies=["A"]))
        lib.validate_contribution(_cand(id="D", structural_key="dD",
                                        dependencies=["B", "C"]))
        assert set(lib.corpus.transitive_dependents("A")) == {"B", "C", "D"}
        out = lib.refute("A", "root false", source="t")
        assert set(out["invalidated"]) == {"B", "C", "D"}, out
    finally:
        lib.close(); os.unlink(path)


# ---- model validation: bad candidates rejected at construction -------------
def test_model_rejects_empty_informal_claim() -> None:
    for bad in ("", "   "):
        raised = False
        try:
            _cand(id="z", informal_claim=bad)
        except ValueError:
            raised = True
        assert raised, "empty informal_claim must be rejected at construction"


def test_model_rejects_unknown_field() -> None:
    raised = False
    try:
        Candidate.from_dict({"id": "z", "name": "n", "informal_claim": "c",
                             "statement": "s", "proof_text": "p",
                             "structural_key": "k", "bogus_field": 1})
    except ValueError:
        raised = True
    assert raised, "unknown candidate field must be rejected"


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
