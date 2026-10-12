# pse-research — Phase 1

Foundation for the PSE Mathematical Research System.
Companion to `../PSE_MATH_RESEARCH_BUILD.txt` and `../PSE_MATH_RESEARCH_ADDENDUM.txt`.

Phase 1 (build spec Sec 14) = **JOURNAL + SHARED_LIB SKELETON + VERIFICATION
GATE**. No agents. A CLI pushes a candidate by hand; the gate accepts or rejects.
This is the foundation: *if the gate leaks, everything above it is sand.*

## What is implemented

| Piece | File | Status |
|---|---|---|
| Append-only journal (SQLite WAL, UPDATE/DELETE forbidden by triggers) | `pse_research/journal.py` | live |
| Corpus store + derived dependency DAG + transitive dependents | `pse_research/corpus.py` | live |
| Verification gate C1–C7 (fail-fast, cheapest first) | `pse_research/verifier.py` | live |
| SHARED_LIB — the one gate; `validate_contribution`, `refute` | `pse_research/shared_lib.py` | live |
| CLI (push / refute / journal / corpus) | `pse_research/cli.py` | live |
| Schizoid unit-health check | `shared_lib._schizoid_check` | **stub → Phase 2** |
| Guardian 2 semantic review | `shared_lib._guardian2_review` | **stub → Phase 5** |

### The seven mechanical checks (C1–C7)

Cheapest first, fail fast. Mechanical only — never routed through an LLM.

- **C1 PARSE/TYPECHECK** — the proof term elaborates. Delegated to a pluggable
  backend (see below).
- **C2 NO ESCAPE HATCHES** — no `sorry`, `admit`, new `axiom`; `native_decide`
  only on a per-branch whitelist (it trusts the compiler = real soundness risk).
- **C3 NO CYCLES** — adding the lemma keeps the dependency DAG acyclic. In an
  append-only DAG you may only depend on already-stored nodes, so the
  representative violation is self-dependency, which C3 catches.
- **C4 HYPOTHESIS UTILIZATION** — every declared hypothesis is referenced
  (unused hypothesis = vacuity smell).
- **C5 NON-VACUITY** — the hypothesis set is satisfiable: a witness is required,
  or an explicit human waiver recorded.
- **C6 NON-DUPLICATION** — not structurally subsumed by an existing corpus lemma
  (structural key, not embedding similarity).
- **C7 DEPENDENCY CLOSURE** — every dependency is itself VERIFIED.

Fail any → REJECT, nothing stored, rejection journalled with the failing check ID
and full error text. Rejections are data.

## The Lean backend (why C1 is pluggable)

C1 is the only check that genuinely needs a proof assistant. It is delegated to a
`VerifierBackend`:

- **`SymbolicBackend`** (default) — works with **no Lean installed**. Uses the
  candidate's declared representation. Sufficient to exercise the whole gate on
  adversarial examples, which is exactly the Phase 1 acceptance criterion.
- **`LeanBackend`** — shells out to `lake env lean` on a real Lean 4 project.
  Raises loudly if `lake` is not on PATH, so its absence is never silent.

**Lean 4.32.1 is installed here (toolchain only, no mathlib)**, so the gate has
been run against REAL elaboration — see `tests/test_lean_backend.py`. Wiring:

- In code: `ResearchSharedLib(db, backend=LeanBackend("/path/to/project"))`.
- From the CLI: add `--lean PROJECT_DIR` to any command.
- `LeanBackend` uses `lake env lean` when the project has a lakefile (needed once
  mathlib is a dependency), else falls back to bare `lean` (enough for core-Lean
  proofs — what the Surface runs before mathlib). `candidate.statement` must be a
  COMPLETE declaration including its proof.

Nothing in the gate logic changes — only C1's backend. Mathlib (add on the Dell
later, ~5-6 GB) is only needed once branches formalize real number theory.

```sh
python3 -m pse_research.cli --db research.db --lean ./lean_proj push cand.json
```

## Run it

```sh
# Phase 1 acceptance suite (the six adversarial rejections + accept + extras)
python3 tests/test_gate_adversarial.py
# Phase 1 hardening suite (leak hunt, persistence, policy pins)
python3 tests/test_gate_hardening.py

# push a candidate by hand
python3 -m pse_research.cli --db research.db push examples/good.json
python3 -m pse_research.cli --db research.db push examples/bad_sorry.json

# inspect
python3 -m pse_research.cli --db research.db corpus
python3 -m pse_research.cli --db research.db journal
```

## Phase 1 acceptance — met

`tests/test_gate_adversarial.py` demonstrates all of C1–C7 firing on hand-built
adversarial examples, each rejection journalled with its check ID, plus:
a clean candidate accepted, the journal proven append-only at the DB level, and a
refutation cascading transitively (root → REFUTED, dependents → INVALIDATED).

`tests/test_gate_hardening.py` adds adversarial pressure: a real leak hunt
(term-level `sorryAx` caught, `admit` caught, new `axiom` caught, no false
positive on innocent identifiers), nothing-stored-on-any-reject, fail-fast
reports the cheapest failing check, duplicate-id blocked, refuted structural key
reusable, contested-dependency policy pinned, human-waiver journalled,
persistence across close/reopen, and transitive dependents over a diamond DAG.

`tests/test_lean_backend.py` runs C1 against the installed Lean toolchain: a real
proof accepted, a genuine type error (`1 + 1 = 3 := by rfl`) rejected at C1 with
the actual Lean error captured in the journal, and `sorry` passing C1 (only a
warning) but caught at C2 — the concrete proof that C1 alone is not soundness.

```
acceptance:   12/12 passed
hardening:    15/15 passed
real-Lean:     4/4  passed   (Lean 4.32.1, no mathlib)
```

A leak was found and fixed during hardening: C2 scanned for `sorry` but not the
term-level `sorryAx`, which tokenizes differently and would have slipped through.
Now listed explicitly; the real defence remains LeanBackend + `#print axioms`.

## Candidate format

A candidate is JSON (see `examples/`). Backend-independent fields; under
`LeanBackend` the derivable ones (`used_hypotheses`, `parses`, `structural_key`)
come from real elaboration instead of being declared.

| field | meaning |
|---|---|
| `id`, `name` | identity |
| `informal_claim` | **required, immutable** — the theorem you MEANT (Guardian-2 / G1 basis) |
| `statement` | the formal statement — the theorem you WROTE |
| `proof_text` | the Lean proof term / tactic block |
| `structural_key` | normalized form for structural dedup (C6) |
| `hypotheses`, `used_hypotheses` | for C4 |
| `witness`, `human_waiver` | for C5 |
| `dependencies` | lemma ids relied on (C3, C7) |
| `branch`, `step` | provenance |

## What is deliberately NOT here yet

Per the build order, later phases add: research units + theta (Phase 2), the GUI
in replay mode (Phase 3), the swarm + pathology detection (Phase 4), Guardian 2
(Phase 5), the chat unit (Phase 6), Seldon (Phase 7), Guardian 1 (Phase 8), and
the addendum pieces (knowledge ingestion, decision report files, GAP_HYPOTHESIS).
The stubs above are the real hooks those phases drop into.
