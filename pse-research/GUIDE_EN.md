# PSE Research — Guide (EN)
### Components ordered MOST → LEAST important

This is what was built on the Surface (one codebase, `Profile`-selected; **no
fork**). Everything here is pure Python + SQLite (+ optional Lean for C1, +
PySide6 for the GUI). Run the whole suite: `./run_tests.sh` → **105/105**.

Read top-to-bottom: the higher an item, the more the whole system depends on it
being correct.

---

### 1. THE GATE — `shared_lib.py` + `verifier.py` · ⭐ most important
The one authority. Only `SHARED_LIB.validate_contribution` stores a lemma, and
only after C1–C7 pass. *If the gate leaks, everything above it is sand.*
C1 parse/typecheck · C2 no escape hatches (`sorry`/`sorryAx`/`admit`/`axiom`,
`native_decide` whitelisted) · C3 no cycles · C4 hypothesis utilization · C5
non-vacuity · C6 non-duplication · C7 dependency closure.
Test: `tests/test_gate_adversarial.py`, `tests/test_gate_hardening.py`.

### 2. APPEND-ONLY JOURNAL — `journal.py`
The single source of truth. Every event, forever; UPDATE/DELETE forbidden by DB
triggers. The GUI, reports, and the whole audit story derive from it.
Test: `test_gate_adversarial.py::test_journal_append_only_enforced`.

### 3. PROFILES — `config.py` + backends (`verifier.py`, `model_backend.py`)
The Surface/Dell split as CONFIG, not a fork. `Profile.surface()` = symbolic/bare-
Lean, stub model, 2 units, replay GUI. `Profile.dell()` = lake+mathlib, remote
model, full swarm, live socket. All spec constants live here in one auditable place.

### 4. RESEARCH UNIT — `unit.py` + `theta.py` (Phase 2)
One unit = one branch. Core (immutable mission), Boundary (provisional
candidates), Registry (earned basis), Theta (measured, drives nothing in P2).
**Absorption = USE, not truth**: a lemma enters a basis only if VERIFIED,
resident, load-bearing, mission-relevant, and NOT orphaned. Test:
`tests/test_phase2_unit.py`.

### 5. PATHOLOGY DETECTORS — `detectors.py`
Circle (re-derives itself), Helix (thrashing), Closing Spiral (premature
convergence, by basis overlap), Opening Spiral (schizoid: verified machinery
never used — the most dangerous, caught only by orphan rate + flat sigma).
Test: `tests/test_detectors.py`.

### 6. GUARDIAN 2 — `guardian2.py`
The proof skeptic: the gap between the theorem you WROTE and the one you MEANT.
No gate authority; produces findings. Structural checks live now (G3 inflation,
G4 naming, G5 alpha-rename padding, G2 smuggling); G1 statement-drift and G6
regression are model-backed hooks. Self-check catches "crying wolf".
Test: `tests/test_guardian2.py`.

### 7. GAP_HYPOTHESIS — `gap.py` (addendum A3)
Guardian 2 turned OUTWARD: "is there a hole worth attacking?". Conjectural, never
in the corpus. Dedup + prover-skeptic filter before it costs your attention;
ranked into the queue; your verdict feeds val(B). Turns Honest Null (F5) into a
barrier map. Test: `tests/test_gap.py`.

### 8. HUMAN QUEUE + REPORT FILES — `queue.py` + `reports.py` (A5/A2)
One capped inbox (12/day); items deferred not dropped; persistent overflow is
itself a pathology. Every decision also writes a git-diffable markdown report
(derived from the journal, never a second source of truth).
Test: `tests/test_queue_reports.py`.

### 9. PROVER-SKEPTIC + SELDON — `prover_skeptic.py` + `seldon.py`
The adversarial form (shared penalty on late refutation) and the strategy engine
(replicator over method×problem-shape; refutations cost more than rejects;
conservative below 20 observations). Built + tested on synthetic data now.
Test: `tests/test_pvp_seldon.py`.

### 10. KNOWLEDGE INGESTION — `ingestion.py` (addendum A1)
Scraper (network, Dell) + Curator (offline, local). External store = **cheap
signal, hard wall, never corpus**. Three consumers: RECON/dedup, Guardian 2
pairs, Seldon prior. Test: `tests/test_ingestion.py`.

### 11. CHAT — `chat.py` (Sec 11 / A5)
Read-only query primitives with a freshness stamp (R1), register separation
(R2), reachable "I don't know" (R3). Guides a launch (tells you where to click),
never writes it. Test: `tests/test_chat.py`.

### 12. DAEMON / CLIENT — `daemon.py` (Sec 13)
Unix-socket query surface; **read-only enforced at the socket**, not by
convention (write ops are simply not in the op table). Test: `tests/test_daemon.py`.

### 13. GUI (REPLAY MODE) — `gui.py` (Phase 3) · least critical to correctness
PySide6, pure client, reads a recorded journal. Overview / Graph / Frontier /
Queue / Lean + theta strip + chat. **Status carried by SHAPE not colour**
(verified solid, contested heavy, refuted struck-through, orphan hollow).
Run: `QT_QPA_PLATFORM=offscreen python3 -m pse_research.gui --db research.db`
(drop the env var on a real desktop). Test: `tests/test_gui_smoke.py`.

---

## What is NOT here (Dell-class)
mathlib-scale formalization; long live swarms with real generation; full
Guardian 1. The CODE for all of it runs on the Surface at toy scale — the Dell
only runs it bigger, by switching the profile.

## Quick start
```sh
./run_tests.sh                                   # 105/105
python3 -m pse_research.cli --db r.db push examples/good.json
python3 -m pse_research.cli --db r.db --lean ./proj push cand.json   # real Lean
QT_QPA_PLATFORM=offscreen python3 -m pse_research.gui --db r.db
```
