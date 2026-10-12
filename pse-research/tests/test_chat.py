"""
Chat unit: read-only query primitives, freshness stamp (R1), register separation
(R2), I-don't-know (R3), launch guidance (A5.1). Uses a real gate to populate.

  python3 tests/test_chat.py
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pse_research.chat import ChatUnit  # noqa: E402
from pse_research.model import Candidate  # noqa: E402
from pse_research.shared_lib import ResearchSharedLib  # noqa: E402


def _cand(**over) -> Candidate:
    base = dict(id="L", name="lemma", informal_claim="an informal claim",
                statement="theorem L : True := by trivial", proof_text="by trivial",
                structural_key="SK", hypotheses=[], used_hypotheses=[],
                dependencies=[], branch="B1", step=1)
    base.update(over)
    return Candidate.from_dict(base)


def _lib():
    fd, p = tempfile.mkstemp(suffix=".db"); os.close(fd); os.unlink(p)
    return ResearchSharedLib(p), p


def test_freshness_on_every_answer() -> None:
    lib, p = _lib()
    try:
        chat = ChatUnit(lib.corpus, lib.journal)
        for ans in (chat.corpus_stats(), chat.lemma("nope"), chat.orphans()):
            assert "freshness" in ans and "as_of_seq" in ans["freshness"]
    finally:
        lib.close(); os.unlink(p)


def test_register_separation() -> None:
    lib, p = _lib()
    try:
        lib.validate_contribution(_cand(id="v1", structural_key="K1"))
        chat = ChatUnit(lib.corpus, lib.journal)
        assert chat.lemma("v1")["register"] == "VERIFIED"
    finally:
        lib.close(); os.unlink(p)


def test_i_dont_know_reachable() -> None:
    lib, p = _lib()
    try:
        chat = ChatUnit(lib.corpus, lib.journal)
        assert chat.lemma("ghost")["answer"] == "i_dont_know"
        assert chat.launch_guide("fermat")["answer"] == "i_dont_know"
    finally:
        lib.close(); os.unlink(p)


def test_dependencies_and_dependents() -> None:
    lib, p = _lib()
    try:
        lib.validate_contribution(_cand(id="A", structural_key="KA"))
        lib.validate_contribution(_cand(id="B", structural_key="KB",
                                        dependencies=["A"]))
        chat = ChatUnit(lib.corpus, lib.journal)
        assert chat.dependencies("B")["dependencies"] == ["A"]
        assert chat.dependents("A")["dependents"] == ["B"]
    finally:
        lib.close(); os.unlink(p)


def test_orphans_view() -> None:
    lib, p = _lib()
    try:
        lib.validate_contribution(_cand(id="solo", structural_key="KS"))
        chat = ChatUnit(lib.corpus, lib.journal)
        assert "solo" in chat.orphans()["orphans"]
    finally:
        lib.close(); os.unlink(p)


def test_launch_guide_gives_steps_not_action() -> None:
    lib, p = _lib()
    try:
        chat = ChatUnit(lib.corpus, lib.journal)
        g = chat.launch_guide("collatz")
        assert g["steps"] and "CONFIRM" in " ".join(g["steps"])
        assert "never writes" in g["note"]
    finally:
        lib.close(); os.unlink(p)


def test_chat_is_read_only() -> None:
    # No public method mutates corpus/journal: the chat exposes only readers.
    lib, p = _lib()
    try:
        chat = ChatUnit(lib.corpus, lib.journal)
        writers = [m for m in dir(chat)
                   if m in ("store", "write", "validate_contribution", "refute",
                            "mark", "push")]
        assert writers == []
    finally:
        lib.close(); os.unlink(p)


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
