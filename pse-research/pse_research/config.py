"""
Profiles and constants — "fork as config" (build spec + addendum A4/A5).

There is ONE codebase. The Surface/Dell difference is a runtime PROFILE, not a
fork: a set of capability flags plus which pluggable backends are wired. The
Surface profile runs everything in small/local/replay mode; the Dell profile
flips the same code to full/remote/live. Nothing structural differs.

All numeric constants from the build spec live here, in one place, so the
"CHANGED / KEPT / ADDED" table (build spec Sec 2) is auditable at a glance.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# ============================================================================
# CONSTANTS (build spec Sec 2)
# ============================================================================
# --- KEPT UNCHANGED ---------------------------------------------------------
HEALTHY_SIGMA_THETA = (0.015, 0.03)     # sigma_theta healthy band, EVERY phase
SCHIZOID_SIGMA_THRESHOLD = 0.01         # flatline below this over the window
STABILITY_WINDOW = 10_000               # interactions
SINGLE_ORGANELLE_CAP = 0.20
TOTAL_ORGANELLE_BUDGET = 0.30
INHERITED_ORGANELLE_FACTOR = 0.70

# --- CHANGED: phase-dependent theta bands -----------------------------------
class Phase(str, Enum):
    RECON = "RECON"
    ASSAULT = "ASSAULT"
    CONSOLIDATION = "CONSOLIDATION"
    HUMAN_FACING = "HUMAN_FACING"

THETA_BANDS = {
    Phase.RECON: (40.00, 60.00),          # survey; high other-direction correct
    Phase.ASSAULT: (15.00, 25.00),        # deep push on own line; self-directed
    Phase.CONSOLIDATION: (25.00, 35.00),  # formalize, reconcile, hand off
    Phase.HUMAN_FACING: (25.00, 35.00),   # nominal 30.00, NEVER varies (A5/Sec11)
}
HUMAN_FACING_NOMINAL_THETA = 30.00

# --- ADDED ------------------------------------------------------------------
VERIFICATION_REQUIRED = True            # hard, non-overridable
ORPHAN_FLAG_AFTER = 500                 # steps with zero dependents
HUMAN_QUEUE_DAILY_CAP = 12              # A5 enforcement
DUPLICATE_SIMILARITY_T = 0.85          # candidate vs existing corpus lemma
SKEPTIC_BOUNTY_WINDOW = 2000           # steps a later refutation still penalizes
BRANCH_STALL_STEPS = 1500              # no new verified lemma -> stall review
MIN_CASES_FOR_STRATEGY_SHIFT = 20      # Seldon conservatism (master spec I-7)

# --- ABSORPTION CRITERION (build spec Sec 4, Def 5 adaptation) --------------
ABSORPTION_MIN_RESIDENCY = 1000        # invocations across distinct derivations
ABSORPTION_MIN_ALPHA = 0.10            # load-bearing fraction
ABSORPTION_ALPHA_STEPS = 100           # consecutive steps sustained
ABSORPTION_MIN_MI = 0.70              # contextual MI(candidate; mission)

# --- PATHOLOGY THRESHOLDS (build spec Sec 4) --------------------------------
CIRCLE_GRAD_RATIO = 0.1               # Grad_out/Grad_in below -> narcissistic
HELIX_SIGMA = 0.05                    # sigma above + ACF low -> borderline
HELIX_ACF = 0.5
CLOSING_SPIRAL_OVERLAP = 0.30         # pairwise basis Jaccard above -> codependent
OPENING_SPIRAL_ORPHAN_FRACTION = 0.5  # orphan fraction over window -> schizoid
OPENING_SPIRAL_WINDOW = 5000

# --- FAILURE / STOP CONDITIONS (build spec Sec 16) --------------------------
REFUTATION_RATE_HALT = 0.05           # F1: > 5% of stored lemmas -> halt intake


# ============================================================================
# PROFILE
# ============================================================================
class VerifierMode(str, Enum):
    SYMBOLIC = "symbolic"     # no Lean needed
    LEAN_BARE = "lean_bare"   # bare `lean`, core only, no mathlib (Surface)
    LEAN_LAKE = "lean_lake"   # `lake env lean` + mathlib (Dell)


class ModelMode(str, Enum):
    STUB = "stub"             # deterministic stand-in, no model (Surface/dev)
    LOCAL = "local"           # small local llama.cpp (Surface, light)
    REMOTE = "remote"         # remote API for heavy generation (Dell)


@dataclass
class Profile:
    """A capability profile. The whole Surface/Dell split lives in these flags."""
    name: str
    verifier_mode: VerifierMode
    model_mode: ModelMode
    lean_project_path: str | None = None     # for LEAN_* modes
    max_live_units: int = 2                   # swarm scale
    guardian1_enabled: bool = False           # network defence (Dell/exposed)
    ingestion_network_enabled: bool = False   # scraper may touch the network
    gui_live_socket: bool = False             # GUI may attach to a live daemon
    daily_human_cap: int = HUMAN_QUEUE_DAILY_CAP

    # ---- named profiles ---------------------------------------------------
    @staticmethod
    def surface(lean_project_path: str | None = None) -> "Profile":
        """Dev machine: small, local, replay-first. Everything runs, at toy scale."""
        return Profile(
            name="surface",
            verifier_mode=(VerifierMode.LEAN_BARE if lean_project_path
                           else VerifierMode.SYMBOLIC),
            model_mode=ModelMode.STUB,
            lean_project_path=lean_project_path,
            max_live_units=2,
            guardian1_enabled=False,
            ingestion_network_enabled=False,
            gui_live_socket=False,
        )

    @staticmethod
    def dell(lean_project_path: str) -> "Profile":
        """Deployment: full swarm, mathlib, remote generation, live GUI."""
        return Profile(
            name="dell",
            verifier_mode=VerifierMode.LEAN_LAKE,
            model_mode=ModelMode.REMOTE,
            lean_project_path=lean_project_path,
            max_live_units=16,
            guardian1_enabled=True,
            ingestion_network_enabled=True,
            gui_live_socket=True,
        )
