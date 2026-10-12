"""
Knowledge ingestion: curator dedup, reliability, three-consumer queries, and the
hard wall (external store has no corpus-write path). Offline (StubScraper).

  python3 tests/test_ingestion.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pse_research.ingestion import (  # noqa: E402
    Curator, ExternalStore, NetworkScraper, RawItem, StubScraper, TIER,
)


def _raw():
    return [
        RawItem("mathlib", "h1", "commutativity of addition",
                "theorem add_comm ...", kind="pair", url="mathlib://add_comm"),
        RawItem("mathoverflow", "h2", "a subtle error about k=2 case",
                None, kind="known_error"),
        RawItem("mathlib", "h1", "dup of add_comm", "dup", kind="pair"),  # dup hash
    ]


def test_curator_dedups_and_scores() -> None:
    store = ExternalStore()
    cur = Curator(store)
    scraper = StubScraper(_raw())
    inserted = cur.process(scraper.fetch())
    assert len(inserted) == 2            # third is a dup content_hash
    assert store.count() == 2
    # mathlib scored higher than mathoverflow
    pairs = store.pairs()
    assert pairs and pairs[0].reliability >= 0.9


def test_everything_is_cheap_signal() -> None:
    store = ExternalStore()
    Curator(store).process(StubScraper(_raw()).fetch())
    for e in store.pairs() + store.known_errors():
        assert e.tier == TIER


def test_hard_wall_no_corpus_write() -> None:
    store = ExternalStore()
    assert store.can_write_corpus() is False
    # the store has no corpus handle at all
    assert not hasattr(store, "store_lemma") and not hasattr(store, "corpus")


def test_recon_consumer_known_lookup() -> None:
    store = ExternalStore()
    Curator(store).process(StubScraper(_raw()).fetch())
    assert store.known("commutativity")       # RECON: already known
    assert not store.known("linear A decipherment")


def test_guardian2_consumer_pairs() -> None:
    store = ExternalStore()
    Curator(store).process(StubScraper(_raw()).fetch())
    pairs = store.pairs()
    assert all(p.formal is not None for p in pairs)
    assert len(store.known_errors()) == 1


def test_network_scraper_gated_by_profile() -> None:
    raised = False
    try:
        NetworkScraper(network_enabled=False)
    except RuntimeError:
        raised = True
    assert raised
    NetworkScraper(network_enabled=True)   # allowed when profile permits


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
