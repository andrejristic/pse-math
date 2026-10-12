"""
GAP_HYPOTHESIS lifecycle + producer filters + val(B) feedback (addendum A3).

  python3 tests/test_gap.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pse_research.gap import GapHypothesis, GapManager, GapState, Verdict  # noqa: E402
from pse_research.queue import HumanQueue  # noqa: E402


class _Journal:
    def __init__(self): self.events = []
    def write(self, t, **p): self.events.append((t, p))


def _gap(**over) -> GapHypothesis:
    base = dict(id="g1", informal_gap="no lemma covers k=2",
                evidence="B4 shows F cannot reach; F' not excluded",
                blast_radius=5.0, branch="B4", step=10)
    base.update(over)
    return GapHypothesis(**base)


def test_gap_requires_evidence_and_conjectural() -> None:
    for bad in (dict(evidence=""), dict(register="VERIFIED")):
        raised = False
        try:
            _gap(**bad)
        except ValueError:
            raised = True
        assert raised, bad


def test_survivor_is_queued_and_journalled() -> None:
    q = HumanQueue(); j = _Journal()
    gm = GapManager(q, j)
    st = gm.emit(_gap())
    assert st == GapState.QUEUED
    assert any(k == "GAP_HYPOTHESIS" for k, _ in j.events)
    assert len(q.today_view()) == 1


def test_dedup_drops_duplicate() -> None:
    q = HumanQueue(); j = _Journal()
    gm = GapManager(q, j)
    gm.emit(_gap(id="g1"))
    st = gm.emit(_gap(id="g2"))   # same informal_gap text -> duplicate
    assert st == GapState.DROPPED
    assert any(t == "GAP_DROPPED" and p["reason"] == "dedup" for t, p in j.events)


def test_corpus_cover_drops() -> None:
    q = HumanQueue(); j = _Journal()
    gm = GapManager(q, j, corpus_covers=lambda g: True)
    assert gm.emit(_gap()) == GapState.DROPPED


def test_skeptic_fills_drops() -> None:
    q = HumanQueue(); j = _Journal()
    gm = GapManager(q, j, skeptic_fills=lambda g: True)
    st = gm.emit(_gap())
    assert st == GapState.DROPPED
    assert any(p.get("reason") == "skeptic_filled" for _, p in j.events)


def test_confirm_spawns_and_resolves_queue() -> None:
    q = HumanQueue(); j = _Journal()
    gm = GapManager(q, j)
    gm.emit(_gap(id="g1"))
    st = gm.verdict("g1", Verdict.CONFIRMED)
    assert st == GapState.SPAWNED
    assert len(q) == 0                     # removed from queue on decision
    assert gm.confirmed_count == 1


def test_dismiss_feeds_valB() -> None:
    q = HumanQueue(); j = _Journal()
    gm = GapManager(q, j)
    gm.emit(_gap(id="g1"))
    gm.emit(_gap(id="g2", informal_gap="different gap here"))
    gm.verdict("g1", Verdict.CONFIRMED)
    gm.verdict("g2", Verdict.DISMISSED)
    assert abs(gm.upheld_rate() - 0.5) < 1e-9
    bm = gm.barrier_map()
    assert bm["confirmed"] == 1 and bm["dismissed"] == 1


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
