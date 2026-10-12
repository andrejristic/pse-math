"""
GUI in REPLAY MODE (build spec Sec 12, Phase 3).

PySide6. A PURE CLIENT: it reads a recorded journal + corpus and renders. It
never mutates corpus state. Replay mode is non-negotiable (build spec Sec 13):
the Surface cannot run the swarm, so the interface is developed against a
recorded journal, not a live daemon.

Layout (build spec Sec 12): 75/25 splitter (main | chat); QTabWidget with
Overview / Graph / Frontier / Queue / Lean; a persistent theta strip below the
tabs; a status bar above. The one visual invariant implemented here:
  STATUS IS CARRIED BY SHAPE, NOT ONLY COLOUR
  verified = solid box, conjectural = dashed, contested = double border,
  refuted = struck through, orphan = hollow.

Run:  python3 -m pse_research.gui --db research.db
"""
from __future__ import annotations

import sys
from typing import Any, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from .chat import ChatUnit
from .corpus import CorpusStore
from .journal import AppendOnlyJournal
from .model import Status


# ---------------------------------------------------------------------------
# Read-only replay source: corpus + journal from a recorded DB.
# ---------------------------------------------------------------------------
class ReplaySource:
    def __init__(self, db_path: str) -> None:
        self.journal = AppendOnlyJournal(db_path)
        self.corpus = CorpusStore(self.journal.conn)
        self.chat = ChatUnit(self.corpus, self.journal)

    def events(self) -> list[dict[str, Any]]:
        return list(self.journal.read_all())

    def theta_by_unit(self) -> dict[str, list[float]]:
        out: dict[str, list[float]] = {}
        for e in self.events():
            if e["type"] == "THETA_EVENT":
                p = e["payload"]
                out.setdefault(p.get("unit", "?"), []).append(float(p.get("theta", 0)))
        return out


# ---------------------------------------------------------------------------
# Theta strip: one sparkline per unit, always visible (build spec Sec 12).
# ---------------------------------------------------------------------------
class ThetaStrip(QtWidgets.QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._series: dict[str, list[float]] = {}
        self.setMinimumHeight(48)
        self.setToolTip("theta per live unit — a flatlined unit is visible here "
                        "regardless of the open tab")

    def set_series(self, series: dict[str, list[float]]) -> None:
        self._series = series
        self.update()

    def paintEvent(self, _ev: QtGui.QPaintEvent) -> None:
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), QtGui.QColor(20, 20, 24))
        if not self._series:
            p.setPen(QtGui.QColor(140, 140, 150))
            p.drawText(self.rect(), QtCore.Qt.AlignCenter,
                       "theta strip (no THETA_EVENTs in this journal)")
            return
        w = self.width() / max(1, len(self._series))
        for i, (uid, xs) in enumerate(self._series.items()):
            x0 = i * w
            p.setPen(QtGui.QColor(120, 200, 255))
            if len(xs) >= 2:
                mn, mx = min(xs), max(xs)
                rng = (mx - mn) or 1.0
                pts = []
                for j, v in enumerate(xs):
                    px = x0 + 40 + (w - 50) * j / (len(xs) - 1)
                    py = self.height() - 6 - (self.height() - 12) * (v - mn) / rng
                    pts.append(QtCore.QPointF(px, py))
                p.drawPolyline(QtGui.QPolygonF(pts))
            p.setPen(QtGui.QColor(200, 200, 210))
            p.drawText(int(x0) + 2, 14, uid)


# ---------------------------------------------------------------------------
# Graph: the lemma DAG, status carried by SHAPE (build spec Sec 12 [!]).
# ---------------------------------------------------------------------------
class DagView(QtWidgets.QGraphicsView):
    def __init__(self) -> None:
        self._scene = QtWidgets.QGraphicsScene()
        super().__init__(self._scene)
        self.setRenderHint(QtGui.QPainter.Antialiasing)

    def build_from_corpus(self, corpus: CorpusStore) -> None:
        self._scene.clear()
        ids = corpus.all_ids()
        # layer = longest dependency depth (simple layered layout, no graphviz)
        depth: dict[str, int] = {}

        def d(i: str, seen=None) -> int:
            seen = seen or set()
            if i in depth:
                return depth[i]
            if i in seen:
                return 0
            seen.add(i)
            deps = corpus.dependencies(i)
            depth[i] = 0 if not deps else 1 + max(d(x, seen) for x in deps)
            return depth[i]

        for i in ids:
            d(i)
        by_layer: dict[int, list[str]] = {}
        for i in ids:
            by_layer.setdefault(depth[i], []).append(i)

        pos: dict[str, QtCore.QPointF] = {}
        for layer, members in sorted(by_layer.items()):
            for k, i in enumerate(members):
                x, y = layer * 200.0, k * 90.0
                pos[i] = QtCore.QPointF(x + 60, y + 20)
                self._add_node(corpus, i, x, y)
        # edges
        pen = QtGui.QPen(QtGui.QColor(150, 150, 160))
        for i in ids:
            for dep in corpus.dependencies(i):
                if dep in pos:
                    self._scene.addLine(pos[dep].x(), pos[dep].y(),
                                        pos[i].x(), pos[i].y(), pen)

    def _add_node(self, corpus: CorpusStore, lid: str, x: float, y: float) -> None:
        row = corpus.get(lid)
        status = row["status"]
        orphan = (status in (Status.VERIFIED.value, Status.VERIFIED_CONTESTED.value)
                  and not corpus.direct_dependents(lid))
        rect = QtCore.QRectF(x, y, 120, 40)
        item = QtWidgets.QGraphicsRectItem(rect)

        pen = QtGui.QPen(QtGui.QColor(230, 230, 235))
        # SHAPE carries status (readable at 3am, colour is not):
        if status == Status.VERIFIED.value:
            pen.setStyle(QtCore.Qt.SolidLine)
        elif status == Status.VERIFIED_CONTESTED.value:
            pen.setStyle(QtCore.Qt.SolidLine); pen.setWidth(3)   # double/heavy border
        elif status in (Status.REFUTED.value, Status.INVALIDATED.value):
            pen.setStyle(QtCore.Qt.DashLine)
        # fill: hollow = orphan (nothing depends on it)
        item.setBrush(QtCore.Qt.NoBrush if orphan
                      else QtGui.QBrush(QtGui.QColor(40, 44, 52)))
        item.setPen(pen)
        item.setToolTip(f"{lid} [{status}]" + (" (orphan)" if orphan else ""))
        self._scene.addItem(item)

        label = self._scene.addText(lid)
        label.setDefaultTextColor(QtGui.QColor(230, 230, 235))
        label.setPos(x + 4, y + 8)
        # refuted = struck through
        if status in (Status.REFUTED.value, Status.INVALIDATED.value):
            f = label.font(); f.setStrikeOut(True); label.setFont(f)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, db_path: str) -> None:
        super().__init__()
        self.src = ReplaySource(db_path)
        self.setWindowTitle(f"PSE Research — REPLAY [{db_path}]")
        self.resize(1280, 800)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        splitter.addWidget(self._build_left())
        splitter.addWidget(self._build_chat())
        splitter.setSizes([960, 320])   # 75 / 25
        self.setCentralWidget(splitter)

        self._status = self.statusBar()
        self._refresh()

    # ---- left column ------------------------------------------------------
    def _build_left(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.addTab(self._tab_overview(), "Overview")
        self.tabs.addTab(self._tab_graph(), "Graph")
        self.tabs.addTab(self._tab_frontier(), "Frontier")
        self.tabs.addTab(self._tab_queue(), "Queue")
        self.tabs.addTab(self._tab_lean(), "Lean")
        lay.addWidget(self.tabs)
        self.theta_strip = ThetaStrip()
        lay.addWidget(self.theta_strip)
        return w

    def _tab_overview(self) -> QtWidgets.QWidget:
        self.overview = QtWidgets.QTextEdit(); self.overview.setReadOnly(True)
        return self.overview

    def _tab_graph(self) -> QtWidgets.QWidget:
        self.dag = DagView()
        return self.dag

    def _tab_frontier(self) -> QtWidgets.QWidget:
        self.frontier = QtWidgets.QTableWidget(0, 6)
        self.frontier.setHorizontalHeaderLabels(
            ["branch", "unit", "phase", "theta", "spent/budget", "last move"])
        return self.frontier

    def _tab_queue(self) -> QtWidgets.QWidget:
        self.queue_list = QtWidgets.QListWidget()
        return self.queue_list

    def _tab_lean(self) -> QtWidgets.QWidget:
        self.lean_view = QtWidgets.QPlainTextEdit()
        self.lean_view.setPlaceholderText("workspace-confined Lean view (Phase 5+)")
        return self.lean_view

    def _build_chat(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        self.freshness = QtWidgets.QLabel("as of: —")
        self.chat_out = QtWidgets.QTextEdit(); self.chat_out.setReadOnly(True)
        self.chat_in = QtWidgets.QLineEdit()
        self.chat_in.setPlaceholderText("ask (read-only): lemma <id> | orphans | stats")
        self.chat_in.returnPressed.connect(self._on_chat)
        lay.addWidget(self.freshness); lay.addWidget(self.chat_out)
        lay.addWidget(self.chat_in)
        return w

    # ---- data wiring ------------------------------------------------------
    def _refresh(self) -> None:
        events = self.src.events()
        verified = [e["payload"]["candidate"] for e in events
                    if e["type"] == "GATE_PASS"]
        refuted = [e["payload"].get("lemma") for e in events
                   if e["type"] == "REFUTATION"]
        rejects = [e["payload"]["candidate"] for e in events
                   if e["type"] == "GATE_REJECT"]
        gaps = [e["payload"].get("gap") for e in events
                if e["type"] == "GAP_HYPOTHESIS"]
        self.overview.setHtml(
            "<h3>Diff since last session</h3>"
            f"<b>Newly verified ({len(verified)}):</b> {', '.join(verified) or '—'}<br>"
            f"<b>Refuted ({len(refuted)}):</b> {', '.join(map(str, refuted)) or '—'}<br>"
            f"<b>Rejected candidates ({len(rejects)}):</b> {', '.join(rejects) or '—'}<br>"
            f"<b>Gap hypotheses ({len(gaps)}):</b> {', '.join(map(str, gaps)) or '—'}<br>"
        )
        self.dag.build_from_corpus(self.src.corpus)
        self.theta_strip.set_series(self.src.theta_by_unit())
        self.freshness.setText(f"as of: seq {self.src.journal.last_seq()}")
        self.statusBar().showMessage(
            f"REPLAY · corpus {self.src.corpus.counts_by_status()} · "
            f"events {len(events)}")

    def _on_chat(self) -> None:
        q = self.chat_in.text().strip()
        self.chat_in.clear()
        if q.startswith("lemma "):
            ans = self.src.chat.lemma(q.split(" ", 1)[1])
        elif q == "orphans":
            ans = self.src.chat.orphans()
        elif q == "stats":
            ans = self.src.chat.corpus_stats()
        else:
            ans = {"answer": "i_dont_know", "note": "try: lemma <id> | orphans | stats"}
        self.chat_out.append(f"> {q}\n{ans}\n")


def main(argv: Optional[list[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="pse_research.gui")
    ap.add_argument("--db", default="research.db")
    args = ap.parse_args(argv)
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow(args.db)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
