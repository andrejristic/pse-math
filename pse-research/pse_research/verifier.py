"""
Verification subsystem (build spec 3.1) — the mechanical, binary, cheap gate.

Runs C1-C7 in order, cheapest first, FAIL FAST. This is NOT a judgement call and
must NEVER be routed through an LLM. Anything requiring interpretation belongs to
Guardian 2, not here — the two lists must never blur.

Backend abstraction:
  C1 (parse/typecheck) is the only check that genuinely needs a proof assistant.
  It is delegated to a VerifierBackend so the real Lean toolchain drops in
  without touching the gate logic.
    - SymbolicBackend: works TODAY with no Lean installed. Uses the candidate's
      declared `parses` flag and a light syntactic sanity pass. Sufficient to
      exercise the whole gate on adversarial examples (Phase 1 acceptance).
    - LeanBackend: shells out to `lake env lean` on a real proof file. Raises if
      no toolchain is present, so its absence is loud, never silent.

C2-C7 are pure structural/graph logic and are REAL now regardless of backend.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from typing import Optional, Protocol

from .corpus import CorpusStore
from .model import Candidate, Check, Status, Verdict

# Escape hatches forbidden by C2. `native_decide` is conditionally allowed via a
# per-branch whitelist because it trusts the compiler (a real soundness risk).
#   - `sorry`/`admit`: tactic-level holes.
#   - `sorryAx`: the TERM-LEVEL sorry (Lean.sorryAx). Tokenizes distinctly from
#     `sorry`, so it must be listed explicitly or it slips through — a real leak.
# NOTE: this text scan is a best-effort symbolic check. Real soundness comes from
# LeanBackend elaboration plus an axiom-footprint audit (`#print axioms`), which
# catches any hole that reaches the trusted kernel regardless of spelling.
FORBIDDEN_TOKENS = ("sorry", "sorryAx", "admit")
FORBIDDEN_DECLS = ("axiom",)
CONDITIONAL_TOKENS = ("native_decide",)


class VerifierBackend(Protocol):
    def typecheck(self, candidate: Candidate) -> tuple[bool, str]:
        """Return (ok, error_text). ok=True means the term elaborates."""
        ...


class SymbolicBackend:
    """No-Lean backend. Honest about what it can and cannot check."""

    name = "symbolic"

    def typecheck(self, candidate: Candidate) -> tuple[bool, str]:
        # A declared non-parse (adversarial example) fails immediately.
        if not candidate.parses:
            return False, candidate.parse_error or "declared elaboration failure"
        # Light syntactic sanity: statement and proof must be non-empty and the
        # proof must not be an obvious placeholder. This is NOT a real elaboration
        # check; the LeanBackend replaces it.
        if not candidate.statement.strip():
            return False, "empty statement"
        if not candidate.proof_text.strip():
            return False, "empty proof term"
        return True, ""


class LeanBackend:
    """
    Real elaboration via Lean 4. Drop-in for SymbolicBackend.

    `candidate.statement` is expected to be a COMPLETE declaration including its
    proof (e.g. "theorem L : 1 + 1 = 2 := by rfl"); that is what gets elaborated.
    `proof_text` is used only by C2's text scan, never concatenated here.

    If `lean_project_path` contains a lakefile, elaboration runs via
    `lake env lean` (needed once mathlib is a dependency). Otherwise it falls back
    to a bare `lean` invocation, which is enough for core-only proofs (no mathlib)
    and is what the Surface uses before mathlib is installed.

    Requires `lean` on PATH; raises RuntimeError if absent so the gap is loud.
    """

    name = "lean"

    def __init__(self, lean_project_path: str, timeout: int = 120) -> None:
        if shutil.which("lean") is None:
            raise RuntimeError(
                "LeanBackend requested but `lean` is not on PATH. Install the Lean "
                "toolchain (elan) or use SymbolicBackend."
            )
        self.project = lean_project_path
        self.timeout = timeout
        self._has_lake = shutil.which("lake") is not None and (
            os.path.exists(os.path.join(lean_project_path, "lakefile.toml"))
            or os.path.exists(os.path.join(lean_project_path, "lakefile.lean"))
        )

    def typecheck(self, candidate: Candidate) -> tuple[bool, str]:
        os.makedirs(self.project, exist_ok=True)
        fd, path = tempfile.mkstemp(suffix=".lean", dir=self.project)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(candidate.statement + "\n")
            cmd = (["lake", "env", "lean", path] if self._has_lake
                   else ["lean", path])
            proc = subprocess.run(
                cmd, cwd=self.project, capture_output=True, text=True,
                timeout=self.timeout,
            )
            out = (proc.stderr or "") + (proc.stdout or "")
            # Lean reports type errors on stderr AND returns non-zero. A `sorry`
            # is only a WARNING (return 0) — C2 catches that, not C1.
            ok = proc.returncode == 0 and "error:" not in out.lower()
            return ok, "" if ok else out.strip()
        except subprocess.TimeoutExpired:
            return False, "elaboration timed out (resource bound, build spec 3.1)"
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass


class Verifier:
    """Runs C1-C7 against a candidate given the current corpus."""

    def __init__(
        self,
        corpus: CorpusStore,
        backend: Optional[VerifierBackend] = None,
        native_decide_whitelist: Optional[set[str]] = None,
    ) -> None:
        self.corpus = corpus
        self.backend: VerifierBackend = backend or SymbolicBackend()
        self.native_decide_whitelist = native_decide_whitelist or set()

    def check(self, candidate: Candidate) -> Verdict:
        for fn in (
            self._c1_parse,
            self._c2_escape_hatches,
            self._c3_cycles,
            self._c4_hyp_utilization,
            self._c5_non_vacuity,
            self._c6_non_duplication,
            self._c7_dep_closure,
        ):
            verdict = fn(candidate)
            if not verdict.ok:
                return verdict
        return Verdict.passed()

    # ---- C1: parse / typecheck (backend) ---------------------------------
    def _c1_parse(self, c: Candidate) -> Verdict:
        ok, err = self.backend.typecheck(c)
        if not ok:
            return Verdict.fail(Check.C1_PARSE, f"elaboration failed: {err}")
        return Verdict.passed()

    # ---- C2: no escape hatches -------------------------------------------
    def _c2_escape_hatches(self, c: Candidate) -> Verdict:
        # Tokenize on word boundaries so we do not false-match inside identifiers.
        tokens = set(re.findall(r"[A-Za-z_][A-Za-z0-9_']*", c.proof_text))
        for bad in FORBIDDEN_TOKENS:
            if bad in tokens:
                return Verdict.fail(Check.C2_ESCAPE_HATCHES,
                                    f"forbidden escape hatch `{bad}` in proof term")
        for decl in FORBIDDEN_DECLS:
            if re.search(rf"\b{decl}\b", c.statement) or re.search(rf"\b{decl}\b", c.proof_text):
                return Verdict.fail(Check.C2_ESCAPE_HATCHES,
                                    f"new `{decl}` declaration is not allowed")
        for tok in CONDITIONAL_TOKENS:
            if tok in tokens and c.branch not in self.native_decide_whitelist:
                return Verdict.fail(
                    Check.C2_ESCAPE_HATCHES,
                    f"`{tok}` used but branch {c.branch} is not whitelisted for it",
                )
        return Verdict.passed()

    # ---- C3: no cycles ----------------------------------------------------
    def _c3_cycles(self, c: Candidate) -> Verdict:
        if self.corpus.exists(c.id):
            return Verdict.fail(Check.C3_CYCLES,
                                f"lemma id {c.id} already exists in corpus")
        path = self.corpus.would_create_cycle(c)
        if path is not None:
            return Verdict.fail(Check.C3_CYCLES,
                                "adding this lemma would create a cycle: "
                                + " -> ".join(path))
        return Verdict.passed()

    # ---- C4: hypothesis utilization --------------------------------------
    def _c4_hyp_utilization(self, c: Candidate) -> Verdict:
        used = set(c.used_hypotheses)
        unused = [h for h in c.hypotheses if h not in used]
        if unused:
            return Verdict.fail(
                Check.C4_HYP_UTILIZATION,
                f"declared hypotheses never referenced in proof (vacuity smell): "
                f"{unused}",
            )
        return Verdict.passed()

    # ---- C5: non-vacuity --------------------------------------------------
    def _c5_non_vacuity(self, c: Candidate) -> Verdict:
        if not c.hypotheses:
            return Verdict.passed()  # nothing to satisfy
        if c.witness is not None and c.witness.strip():
            return Verdict.passed()
        if c.human_waiver:
            return Verdict.passed()  # explicit waiver; recorded by the gate
        return Verdict.fail(
            Check.C5_NON_VACUITY,
            "hypothesis set has no satisfiability witness and no human waiver "
            "(hypotheses may be unsatisfiable -> lemma vacuously true)",
        )

    # ---- C6: non-duplication ---------------------------------------------
    def _c6_non_duplication(self, c: Candidate) -> Verdict:
        matches = self.corpus.find_by_structural_key(c.structural_key)
        live = [m for m in matches
                if m["status"] in (Status.VERIFIED.value, Status.VERIFIED_CONTESTED.value)]
        if live:
            return Verdict.fail(
                Check.C6_NON_DUPLICATION,
                f"structurally subsumed by existing lemma(s): "
                f"{[m['id'] for m in live]}",
            )
        return Verdict.passed()

    # ---- C7: dependency closure ------------------------------------------
    def _c7_dep_closure(self, c: Candidate) -> Verdict:
        for dep in c.dependencies:
            st = self.corpus.status_of(dep)
            if st is None:
                return Verdict.fail(Check.C7_DEP_CLOSURE,
                                    f"dependency {dep} is not in the corpus")
            if st not in (Status.VERIFIED, Status.VERIFIED_CONTESTED):
                return Verdict.fail(
                    Check.C7_DEP_CLOSURE,
                    f"dependency {dep} is not verified (status={st.value})",
                )
        return Verdict.passed()
