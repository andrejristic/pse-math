"""
Human queue (A5 cap + overflow-as-pathology) and A2 decision report files.

  python3 tests/test_queue_reports.py
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pse_research.queue import HumanItem, HumanQueue  # noqa: E402
from pse_research.reports import render_decision_md, write_report_file  # noqa: E402


def test_priority_ordering() -> None:
    q = HumanQueue(daily_cap=12)
    q.push(HumanItem("BRANCH_STALL", "B2", "stall"))
    q.push(HumanItem("REFUTATION", "L1", "broke", affects=["L2"]))
    q.push(HumanItem("GUARDIAN2_SEVERE", "cand9", "drift"))
    order = [it.kind for it in q.pending()]
    assert order[0] == "REFUTATION" and order[1] == "GUARDIAN2_SEVERE"


def test_gap_hypotheses_ranked_by_blast() -> None:
    q = HumanQueue(daily_cap=12)
    q.push(HumanItem("GAP_HYPOTHESIS", "g_small", "gap", blast_radius=1.0))
    q.push(HumanItem("GAP_HYPOTHESIS", "g_big", "gap", blast_radius=9.0))
    gaps = [it.node for it in q.pending() if it.kind == "GAP_HYPOTHESIS"]
    assert gaps == ["g_big", "g_small"]   # higher blast first


def test_daily_cap_defers_not_drops() -> None:
    q = HumanQueue(daily_cap=3)
    for i in range(10):
        q.push(HumanItem("CORPUS_CONTEST", f"L{i}", "contest", blast_radius=i))
    assert len(q.today_view()) == 3
    assert len(q.pending()) == 10          # nothing dropped
    assert q.deferred_count() == 7
    assert q.is_overflowing()


def test_overflow_surfaced_as_single_item() -> None:
    q = HumanQueue(daily_cap=2)
    for i in range(5):
        q.push(HumanItem("BRANCH_STALL", f"B{i}", "stall"))
    ov = q.overflow_item(step=42)
    assert ov is not None and ov.kind == "ATTENTION_OVERFLOW"
    assert ov.affects == 3


def test_resolve_removes_item() -> None:
    q = HumanQueue()
    q.push(HumanItem("REFUTATION", "L1", "broke"))
    assert q.resolve("L1")
    assert len(q) == 0


# ---- A2 report files -------------------------------------------------------
def test_report_render_contains_key_fields() -> None:
    md = render_decision_md({
        "kind": "GAP_HYPOTHESIS", "node": "g_big", "verdict": "CONFIRMED",
        "statement": "theorem foo : True := by trivial",
        "informal_claim": "there is a gap at k=2",
        "blast_radius": 9.0, "commit": "abc123", "step": 100,
        "evidence": "B4 shows family F cannot reach; F' not excluded",
        "rationale": "worth a branch",
    })
    for needle in ("CONFIRMED", "g_big", "k=2", "abc123", "family F"):
        assert needle in md, needle


def test_report_file_written_and_derived() -> None:
    d = tempfile.mkdtemp(prefix="reports_")
    try:
        path = write_report_file(d, {
            "kind": "REFUTATION", "node": "L1", "verdict": "ACK",
            "statement": "x", "informal_claim": "y", "step": 7,
        })
        assert os.path.exists(path)
        with open(path, encoding="utf-8") as fh:
            assert "L1" in fh.read()
    finally:
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
