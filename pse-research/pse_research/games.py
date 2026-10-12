"""
Game forms and the Bayesian posterior (build spec Sec 5).

Posterior machinery is inherited unchanged: uniform prior, update per
interaction, confidence C = 1 - H(P)/log2(N), suppress output below 0.3, partial
reset on structural discontinuity. Only the LIBRARY of forms changes for this
domain.

The [!] epistemic-hygiene rule lives here: a CHEAP signal (numerical/heuristic
evidence, verified to 2^68, density argument) must NOT update the posterior like
a COSTLY signal (a verified lemma). We temper the likelihood by a weight; cheap
evidence gets a small weight no matter how many orders of magnitude it covers.
"""
from __future__ import annotations

import math
from enum import Enum
from typing import Sequence


class GameForm(str, Enum):
    # RETAINED (4)
    STAG_HUNT = "STAG_HUNT"
    WAR_OF_ATTRITION = "WAR_OF_ATTRITION"
    SIGNALLING = "SIGNALLING"
    GLOBAL_GAMES = "GLOBAL_GAMES"
    # ADDED (1)
    PROVER_SKEPTIC = "PROVER_SKEPTIC"


# The enabled library for this deployment. The 7 dropped mixed-motive forms
# (Nash Substrate, Iterated PD, Chicken, Bargaining, All-Pay, Correlated Eq,
# unit-level ESS) are intentionally absent: research units share one objective,
# so fitting them would make the posterior fit noise. ESS survives at swarm level
# in Seldon, not here.
ENABLED_FORMS = [
    GameForm.STAG_HUNT, GameForm.WAR_OF_ATTRITION, GameForm.SIGNALLING,
    GameForm.GLOBAL_GAMES, GameForm.PROVER_SKEPTIC,
]

CONFIDENCE_SUPPRESS_BELOW = 0.3

# Signal weights (Signalling form, the epistemic hygiene [!]).
CHEAP_SIGNAL_WEIGHT = 0.2     # numerical/heuristic — never dominant
COSTLY_SIGNAL_WEIGHT = 1.0    # a verified lemma


class Posterior:
    """A categorical posterior over the enabled game forms."""

    def __init__(self, labels: Sequence[GameForm] | None = None) -> None:
        self.labels = list(labels) if labels else list(ENABLED_FORMS)
        n = len(self.labels)
        self.p = [1.0 / n] * n     # uniform prior

    # ---- update -----------------------------------------------------------
    def update(self, likelihoods: dict[GameForm, float], weight: float = 1.0) -> None:
        """
        Bayesian update tempered by `weight` (the cheap/costly distinction).
        likelihoods: P(evidence | form) for each form (missing -> 1.0, neutral).
        weight in (0,1]: cheap evidence uses a small weight so it cannot swing
        the posterior like a costly one.
        """
        new = []
        for lab, prior in zip(self.labels, self.p):
            like = max(likelihoods.get(lab, 1.0), 1e-12) ** weight
            new.append(prior * like)
        s = sum(new)
        if s <= 0:
            return
        self.p = [x / s for x in new]

    def update_cheap(self, likelihoods: dict[GameForm, float]) -> None:
        self.update(likelihoods, weight=CHEAP_SIGNAL_WEIGHT)

    def update_costly(self, likelihoods: dict[GameForm, float]) -> None:
        self.update(likelihoods, weight=COSTLY_SIGNAL_WEIGHT)

    # ---- confidence -------------------------------------------------------
    def entropy_bits(self) -> float:
        return -sum(x * math.log2(x) for x in self.p if x > 0)

    def confidence(self) -> float:
        """C = 1 - H(P)/log2(N). 0 at uniform, 1 at certainty."""
        n = len(self.labels)
        if n <= 1:
            return 1.0
        return 1.0 - self.entropy_bits() / math.log2(n)

    def suppressed(self) -> bool:
        """Below 0.3 confidence, output is suppressed (build spec Sec 5)."""
        return self.confidence() < CONFIDENCE_SUPPRESS_BELOW

    def most_likely(self) -> GameForm:
        i = max(range(len(self.p)), key=lambda k: self.p[k])
        return self.labels[i]

    def as_dict(self) -> dict[str, float]:
        return {lab.value: round(pr, 6) for lab, pr in zip(self.labels, self.p)}

    # ---- structural discontinuity ----------------------------------------
    def partial_reset(self, toward_uniform: float = 0.5) -> None:
        """
        On a structural discontinuity, blend the posterior back toward uniform by
        `toward_uniform` in [0,1] (1.0 = full reset). Keeps some memory.
        """
        n = len(self.labels)
        u = 1.0 / n
        self.p = [(1 - toward_uniform) * x + toward_uniform * u for x in self.p]
        s = sum(self.p)
        self.p = [x / s for x in self.p]
