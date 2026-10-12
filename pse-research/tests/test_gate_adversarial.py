"""
Phase 1 acceptance suite (build spec Sec 14, Phase 1).

ACCEPT WHEN: all of C1-C7 demonstrably fire on hand-built adversarial examples,
each rejection correctly journalled with its check ID. Plus: a clean candidate is
accepted, the journal is genuinely append-only, and a refutation cascades.

Runs with plain python (no pytest needed):  python tests/test_gate_adversarial.py
Also pytest-compatible (test_* functions).
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pse_research.model import Candidate, Check, Status  # noqa: E402
from pse_research.shared_lib import ResearchSharedLib  # noqa: E402


def _fresh_lib() -> tuple[ResearchSharedLib, str]:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)  # let sqlite create it fresh
    return ResearchSharedLib(path), path


def _clean_candidate(**over) -> Candidate:
    """A candidate that passes every check unless a field is overridden."""
    base = dict(
        id="L_clean", name="clean_lemma",
        informal_claim="for all n, P(n) holds",
        statement="theorem L_clean : True := by trivial",
        proof_text="by trivial",
        structural_key="SK_clean",
        hypotheses=[], used_hypotheses=[], dependencies=[],
        branch="B1", step=1,
    )
    base.update(over)
    return Candidate.from_dict(base)


def _last_reject(lib: ResearchSharedLib) -> dict:
    rejects = [e for e in lib.journal.read_all() if e["type"] == "GATE_REJECT"]
    assert rejects, "expected a GATE_REJECT event in the journal"
    return rejects[-1]


# ---- the clean baseline ----------------------------------------------------
def test_clean_candidate_accepted() -> None:
    lib, path = _fresh_lib()
    try:
        r = lib.validate_contribution(_clean_candidate())
        assert r.accepted and r.status == Status.VERIFIED, r
        passes = [e for e in lib.journal.read_all() if e["type"] == "GATE_PASS"]
        assert len(passes) == 1
    finally:
        lib.close(); os.unlink(path)


# ---- C1: does not elaborate ------------------------------------------------
def test_c1_parse_failure() -> None:
    lib, path = _fresh_lib()
    try:
        c = _clean_candidate(id="L_c1", parses=False,
                             parse_error="unexpected token")
        r = lib.validate_contribution(c)
        assert not r.accepted and r.failed_check == Check.C1_PARSE, r
        assert _last_reject(lib)["payload"]["failed"] == "C1_PARSE"
    finally:
        lib.close(); os.unlink(path)


# ---- C2: escape hatch (sorry) ----------------------------------------------
def test_c2_sorry_rejected() -> None:
    lib, path = _fresh_lib()
    try:
        c = _clean_candidate(id="L_c2", proof_text="by sorry")
        r = lib.validate_contribution(c)
        assert not r.accepted and r.failed_check == Check.C2_ESCAPE_HATCHES, r
        assert _last_reject(lib)["payload"]["failed"] == "C2_ESCAPE_HATCHES"
    finally:
        lib.close(); os.unlink(path)


def test_c2_native_decide_whitelist() -> None:
    # native_decide rejected off-whitelist, accepted on-whitelist.
    fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd); os.unlink(path)
    lib = ResearchSharedLib(path, native_decide_whitelist={"B_ok"})
    try:
        c_bad = _clean_candidate(id="L_nd1", branch="B_no",
                                 proof_text="by native_decide")
        assert lib.validate_contribution(c_bad).failed_check == Check.C2_ESCAPE_HATCHES
        c_ok = _clean_candidate(id="L_nd2", branch="B_ok",
                                proof_text="by native_decide", structural_key="SK_nd2")
        assert lib.validate_contribution(c_ok).accepted
    finally:
        lib.close(); os.unlink(path)


# ---- C3: cycle (self-dependency) -------------------------------------------
def test_c3_cycle_rejected() -> None:
    # In an append-only DAG a genuine multi-node cycle cannot form (you may only
    # depend on already-stored nodes); the representative violation is a lemma
    # that depends on itself, which C3 must catch.
    lib, path = _fresh_lib()
    try:
        c = _clean_candidate(id="L_cyc", dependencies=["L_cyc"])
        r = lib.validate_contribution(c)
        assert not r.accepted and r.failed_check == Check.C3_CYCLES, r
        assert _last_reject(lib)["payload"]["failed"] == "C3_CYCLES"
    finally:
        lib.close(); os.unlink(path)


# ---- C4: unused hypothesis -------------------------------------------------
def test_c4_unused_hypothesis_rejected() -> None:
    lib, path = _fresh_lib()
    try:
        c = _clean_candidate(id="L_c4", hypotheses=["h1", "h2"],
                             used_hypotheses=["h1"], witness="n=0")
        r = lib.validate_contribution(c)
        assert not r.accepted and r.failed_check == Check.C4_HYP_UTILIZATION, r
        assert _last_reject(lib)["payload"]["failed"] == "C4_HYP_UTILIZATION"
    finally:
        lib.close(); os.unlink(path)


# ---- C5: vacuous hypotheses ------------------------------------------------
def test_c5_vacuity_rejected() -> None:
    lib, path = _fresh_lib()
    try:
        c = _clean_candidate(id="L_c5", hypotheses=["h1"],
                             used_hypotheses=["h1"], witness=None,
                             human_waiver=False)
        r = lib.validate_contribution(c)
        assert not r.accepted and r.failed_check == Check.C5_NON_VACUITY, r
        assert _last_reject(lib)["payload"]["failed"] == "C5_NON_VACUITY"
    finally:
        lib.close(); os.unlink(path)


# ---- C6: duplication -------------------------------------------------------
def test_c6_duplicate_rejected() -> None:
    lib, path = _fresh_lib()
    try:
        assert lib.validate_contribution(
            _clean_candidate(id="L_orig", structural_key="SK_dup")).accepted
        c = _clean_candidate(id="L_dup", structural_key="SK_dup")
        r = lib.validate_contribution(c)
        assert not r.accepted and r.failed_check == Check.C6_NON_DUPLICATION, r
        assert _last_reject(lib)["payload"]["failed"] == "C6_NON_DUPLICATION"
    finally:
        lib.close(); os.unlink(path)


# ---- C7: depends on unverified lemma ---------------------------------------
def test_c7_unverified_dependency_rejected() -> None:
    lib, path = _fresh_lib()
    try:
        c = _clean_candidate(id="L_c7", dependencies=["L_missing"])
        r = lib.validate_contribution(c)
        assert not r.accepted and r.failed_check == Check.C7_DEP_CLOSURE, r
        assert _last_reject(lib)["payload"]["failed"] == "C7_DEP_CLOSURE"
    finally:
        lib.close(); os.unlink(path)


def test_c7_refuted_dependency_rejected() -> None:
    lib, path = _fresh_lib()
    try:
        assert lib.validate_contribution(
            _clean_candidate(id="L_base", structural_key="SK_base")).accepted
        lib.refute("L_base", "counterexample at n=0", source="test")
        c = _clean_candidate(id="L_on_refuted", structural_key="SK_ref",
                             dependencies=["L_base"])
        r = lib.validate_contribution(c)
        assert not r.accepted and r.failed_check == Check.C7_DEP_CLOSURE, r
    finally:
        lib.close(); os.unlink(path)


# ---- journal is genuinely append-only --------------------------------------
def test_journal_append_only_enforced() -> None:
    lib, path = _fresh_lib()
    try:
        lib.journal.write("THETA_EVENT", unit="u1", theta=30.0)
        for stmt in ("UPDATE events SET type='HACKED' WHERE seq=1",
                     "DELETE FROM events WHERE seq=1"):
            raised = False
            try:
                lib.journal.conn.execute(stmt); lib.journal.conn.commit()
            except sqlite3.IntegrityError:
                raised = True
            except sqlite3.OperationalError:
                raised = True
            assert raised, f"append-only not enforced for: {stmt}"
    finally:
        lib.close(); os.unlink(path)


# ---- refutation cascades transitively --------------------------------------
def test_refutation_cascade() -> None:
    lib, path = _fresh_lib()
    try:
        lib.validate_contribution(_clean_candidate(id="A", structural_key="SKA"))
        lib.validate_contribution(_clean_candidate(id="B", structural_key="SKB",
                                                   dependencies=["A"]))
        lib.validate_contribution(_clean_candidate(id="C", structural_key="SKC",
                                                   dependencies=["B"]))
        out = lib.refute("A", "root is false", source="test")
        assert set(out["invalidated"]) == {"B", "C"}, out
        assert lib.corpus.status_of("A") == Status.REFUTED
        assert lib.corpus.status_of("B") == Status.INVALIDATED
        assert lib.corpus.status_of("C") == Status.INVALIDATED
    finally:
        lib.close(); os.unlink(path)


def _run_all() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run_all())
