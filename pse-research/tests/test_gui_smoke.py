"""
Headless smoke test for the replay-mode GUI. Cannot verify pixels without a
display, but it proves the app BUILDS against a real recorded journal, wires the
data, and renders the shape-carrying DAG. Runs under the offscreen QPA platform.

  QT_QPA_PLATFORM=offscreen python3 tests/test_gui_smoke.py
(the test sets the platform itself if not already set)
"""
from __future__ import annotations

import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pse_research.model import Candidate  # noqa: E402
from pse_research.shared_lib import ResearchSharedLib  # noqa: E402


def _cand(**over) -> Candidate:
    base = dict(id="L", name="lemma", informal_claim="claim",
                statement="theorem L : True := by trivial", proof_text="by trivial",
                structural_key="SK", hypotheses=[], used_hypotheses=[],
                dependencies=[])
    base.update(over)
    return Candidate.from_dict(base)


def _populate(db_path: str) -> None:
    lib = ResearchSharedLib(db_path)
    lib.validate_contribution(_cand(id="A", structural_key="KA"))
    lib.validate_contribution(_cand(id="B", structural_key="KB", dependencies=["A"]))
    lib.validate_contribution(_cand(id="C", structural_key="KC", dependencies=["B"]))
    lib.validate_contribution(_cand(id="solo", structural_key="KS"))  # orphan
    lib.refute("C", "counterexample", source="test")                 # struck-through
    lib.journal.write("THETA_EVENT", unit="u1", theta=0.30)
    lib.journal.write("THETA_EVENT", unit="u1", theta=0.32)
    lib.journal.write("GAP_HYPOTHESIS", gap="g1", blast=5.0, evidence="B4")
    lib.close()


def test_gui_builds_and_wires() -> None:
    d = tempfile.mkdtemp(prefix="psegui_")
    dbp = os.path.join(d, "r.db")
    _populate(dbp)
    try:
        from PySide6 import QtWidgets
        from pse_research.gui import MainWindow

        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        win = MainWindow(dbp)

        # five tabs (Overview/Graph/Frontier/Queue/Lean)
        assert win.tabs.count() == 5, win.tabs.count()
        # DAG scene rendered nodes+edges (4 lemmas -> at least 4 rect items)
        rects = [it for it in win.dag._scene.items()
                 if it.__class__.__name__ == "QGraphicsRectItem"]
        assert len(rects) == 4, len(rects)
        # overview mentions verified and gap
        html = win.overview.toHtml()
        assert "Newly verified" in html and "g1" in html
        # theta strip received the series
        assert "u1" in win.src.theta_by_unit()
        # chat panel is read-only-driven: a query returns structured data
        win.chat_in.setText("stats"); win._on_chat()
        assert "VERIFIED" in win.chat_out.toPlainText()
        win.close()
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)


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
