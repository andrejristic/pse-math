"""
Daemon / client skeleton (build spec Sec 13, Sec 11 R-rules).

  DAEMON  holds the swarm, runs the verifier, owns the journal. Serves queries
          over a local Unix domain socket. (Here: the read-only query surface;
          the swarm loop is Phase 4.)
  CLIENT  a pure client. It may REQUEST, never mutate corpus state directly.

[!] READ-ONLY is enforced at the SOCKET level, not by convention (build spec
    Phase 6 acceptance): only ops in READ_OPS are dispatched. A write op is
    refused by the daemon regardless of what the client sends.

Protocol: newline-delimited JSON. Request {"op": str, "args": {...}}.
Response {"ok": bool, "data": ...} or {"ok": false, "error": str}.
"""
from __future__ import annotations

import json
import socket
import socketserver
import threading
from typing import Any, Optional

from .chat import ChatUnit

# The ENTIRE allowed op surface. Writes (validate_contribution, refute, store,
# mark, push) are deliberately absent -> the socket cannot mutate state.
READ_OPS = {
    "ping": lambda chat, a: {"pong": True},
    "lemma": lambda chat, a: chat.lemma(a["id"]),
    "dependencies": lambda chat, a: chat.dependencies(a["id"]),
    "dependents": lambda chat, a: chat.dependents(a["id"]),
    "corpus_stats": lambda chat, a: chat.corpus_stats(),
    "orphans": lambda chat, a: chat.orphans(),
    "diff_since": lambda chat, a: chat.diff_since(a.get("seq", 0)),
    "pending_for_human": lambda chat, a: chat.pending_for_human(),
    "unit_health": lambda chat, a: chat.unit_health(a["unit_id"]),
    "launch_guide": lambda chat, a: chat.launch_guide(a["problem"]),
}


class _Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        chat: ChatUnit = self.server.chat  # type: ignore[attr-defined]
        for raw in self.rfile:
            try:
                req = json.loads(raw.decode("utf-8"))
                op = req.get("op")
                args = req.get("args", {}) or {}
            except Exception as e:  # noqa: BLE001
                self._send({"ok": False, "error": f"bad request: {e}"})
                continue
            fn = READ_OPS.get(op)
            if fn is None:
                self._send({"ok": False,
                            "error": f"read-only client: op '{op}' not allowed"})
                continue
            try:
                self._send({"ok": True, "data": fn(chat, args)})
            except KeyError as e:
                self._send({"ok": False, "error": f"missing arg: {e}"})
            except Exception as e:  # noqa: BLE001
                self._send({"ok": False, "error": str(e)})

    def _send(self, obj: dict[str, Any]) -> None:
        self.wfile.write((json.dumps(obj) + "\n").encode("utf-8"))
        self.wfile.flush()


class _Server(socketserver.UnixStreamServer):
    # Non-threading: requests are serialized so the single shared SQLite
    # connection is never used concurrently. The Phase-4 daemon will move to a
    # per-thread connection / serialized DB layer for real concurrency.
    allow_reuse_address = True


class ResearchDaemon:
    """pse-researchd (read-only query surface). Runs in a background thread."""

    def __init__(self, socket_path: str, chat: ChatUnit) -> None:
        self.socket_path = socket_path
        self._server = _Server(socket_path, _Handler)
        self._server.chat = chat  # type: ignore[attr-defined]
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._server.serve_forever,
                                        daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()


class Client:
    """Pure read-only client over the Unix socket."""

    def __init__(self, socket_path: str) -> None:
        self.socket_path = socket_path

    def call(self, op: str, **args: Any) -> dict[str, Any]:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(self.socket_path)
            s.sendall((json.dumps({"op": op, "args": args}) + "\n").encode("utf-8"))
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = s.recv(4096)
                if not chunk:
                    break
                buf += chunk
        return json.loads(buf.decode("utf-8"))
