"""
Daemon/client over a Unix socket, with READ-ONLY enforced at the socket level.

  python3 tests/test_daemon.py
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pse_research.chat import ChatUnit  # noqa: E402
from pse_research.daemon import Client, ResearchDaemon  # noqa: E402
from pse_research.model import Candidate  # noqa: E402
from pse_research.shared_lib import ResearchSharedLib  # noqa: E402


def _cand(**over) -> Candidate:
    base = dict(id="L", name="lemma", informal_claim="claim",
                statement="theorem L : True := by trivial", proof_text="by trivial",
                structural_key="SK", hypotheses=[], used_hypotheses=[],
                dependencies=[])
    base.update(over)
    return Candidate.from_dict(base)


def _setup():
    d = tempfile.mkdtemp(prefix="psed_")
    dbp = os.path.join(d, "r.db")
    lib = ResearchSharedLib(dbp)
    lib.validate_contribution(_cand(id="v1", structural_key="K1"))
    chat = ChatUnit(lib.corpus, lib.journal)
    sock = os.path.join(d, "d.sock")
    daemon = ResearchDaemon(sock, chat)
    daemon.start()
    return lib, daemon, sock, d


def _teardown(lib, daemon, d):
    daemon.stop(); lib.close()
    import shutil
    shutil.rmtree(d, ignore_errors=True)


def test_ping_and_read() -> None:
    lib, daemon, sock, d = _setup()
    try:
        c = Client(sock)
        assert c.call("ping")["data"]["pong"] is True
        r = c.call("corpus_stats")
        assert r["ok"] and r["data"]["counts"].get("VERIFIED") == 1
        assert c.call("lemma", id="v1")["data"]["register"] == "VERIFIED"
    finally:
        _teardown(lib, daemon, d)


def test_write_ops_refused_at_socket() -> None:
    lib, daemon, sock, d = _setup()
    try:
        c = Client(sock)
        for op in ("refute", "validate_contribution", "store", "mark", "push"):
            r = c.call(op, id="v1")
            assert r["ok"] is False and "not allowed" in r["error"], (op, r)
        # corpus is unchanged after all those attempts
        assert c.call("corpus_stats")["data"]["counts"].get("VERIFIED") == 1
    finally:
        _teardown(lib, daemon, d)


def test_unknown_op_and_bad_args() -> None:
    lib, daemon, sock, d = _setup()
    try:
        c = Client(sock)
        assert c.call("frobnicate")["ok"] is False
        assert c.call("lemma")["ok"] is False   # missing 'id'
    finally:
        _teardown(lib, daemon, d)


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
