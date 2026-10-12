"""
Attractor detection — the four search pathologies (build spec Sec 4).

Detection is on the unit's theta series and registry growth — no new machinery
beyond theta.py. Same ordering as the master spec: B (Helix), C (Closing Spiral),
then S (Opening Spiral) LAST, because the schizoid pattern passes every surface
metric and is caught only temporally.

The numeric signals below are the spec's; the thresholds live in config.py. Where
the spec states a qualitative signal ("mu high") we use a documented proxy and
say so — these are detectors to be calibrated, not oracles.
"""
from __future__ import annotations

from enum import Enum
from typing import Sequence

from . import config
from .theta import acf, gradient_ratio, mean, sigma


class Pathology(str, Enum):
    NONE = "NONE"
    CIRCLE = "CIRCLE"                 # narcissistic: re-derives own consequences
    HELIX = "HELIX"                   # borderline: thrashing
    CLOSING_SPIRAL = "CLOSING_SPIRAL" # codependent: premature convergence
    OPENING_SPIRAL = "OPENING_SPIRAL" # schizoid: verified machinery, never used


# Recommended response per pathology (build spec Sec 4). Advisory strings; the
# swarm layer (Phase 4) acts on them.
RESPONSE = {
    Pathology.CIRCLE: "forced RECON phase; if it recurs, terminate and harvest",
    Pathology.HELIX: "budget floor per approach — cannot switch before N steps",
    Pathology.CLOSING_SPIRAL: "forced divergence: re-mission one unit or fission",
    Pathology.OPENING_SPIRAL: "REPLACEMENT not remediation: harvest, retire, "
                              "re-instantiate with a different method",
}


# ---- single-unit detectors -------------------------------------------------
def detect_helix(series: Sequence[float]) -> bool:
    """BORDERLINE: sigma > 0.05 and ACF < 0.5 — abandons approaches before they
    mature. High variance with low autocorrelation = thrashing."""
    return sigma(series) > config.HELIX_SIGMA and acf(series, 1) < config.HELIX_ACF


def detect_circle(series: Sequence[float], grad_out: Sequence[float],
                  grad_in: Sequence[float]) -> bool:
    """NARCISSISTIC: mu high + sigma low + Grad_out/Grad_in < 0.1. Re-derives its
    own consequences; output high, corpus contribution ~0.
    Proxy for 'mu high': theta mean above the CONSOLIDATION upper band (0.35)."""
    mu = mean(series)
    s = sigma(series)
    ratio = gradient_ratio(grad_out, grad_in)
    return (mu > 0.35 and s < config.HEALTHY_SIGMA_THETA[0]
            and ratio < config.CIRCLE_GRAD_RATIO)


def detect_opening_spiral(series: Sequence[float], orphan_fraction: float,
                          steps: int) -> bool:
    """SCHIZOID (most dangerous): ever-growing machinery, nothing used. Caught
    temporally by ORPHAN RATE + registry stagnation: orphan fraction > 0.5 over
    >= 5000 steps with flat sigma_theta."""
    return (orphan_fraction > config.OPENING_SPIRAL_ORPHAN_FRACTION
            and steps >= config.OPENING_SPIRAL_WINDOW
            and sigma(series) < config.SCHIZOID_SIGMA_THRESHOLD)


# ---- pairwise detector (needs two units) -----------------------------------
def basis_overlap(reg_a: set[str], reg_b: set[str]) -> float:
    """Jaccard over two units' registries (earned bases)."""
    if not reg_a and not reg_b:
        return 0.0
    return len(reg_a & reg_b) / len(reg_a | reg_b)


def detect_closing_spiral(reg_a: set[str], reg_b: set[str]) -> bool:
    """CODEPENDENT: two units collapse onto the same approach and stop being
    independent probes. Looks like consensus, which is why it is missed. Pairwise
    basis overlap above 0.30 sustained."""
    return basis_overlap(reg_a, reg_b) > config.CLOSING_SPIRAL_OVERLAP


# ---- classifier ------------------------------------------------------------
def classify_unit(series: Sequence[float], grad_out: Sequence[float],
                  grad_in: Sequence[float], orphan_fraction: float,
                  steps: int) -> Pathology:
    """
    Single-unit classification in the master-spec order: B (Helix), then Circle,
    then S (Opening Spiral) LAST. Returns the first match. Closing Spiral is
    pairwise and handled separately by detect_closing_spiral.
    """
    if detect_helix(series):
        return Pathology.HELIX
    if detect_circle(series, grad_out, grad_in):
        return Pathology.CIRCLE
    if detect_opening_spiral(series, orphan_fraction, steps):
        return Pathology.OPENING_SPIRAL
    return Pathology.NONE
