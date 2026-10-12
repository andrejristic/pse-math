"""
The human queue — the A5 mechanism (build spec Sec 10, addendum A3/A5).

One list. One entry point. Hard daily cap. The constraint binds the SWARM, not
the human: when the cap is hit, items are NOT dropped — they are DEFERRED, and a
persistent overflow is itself a system pathology surfaced as a single item.

Every item carries: what happened, what it affects, what a decision costs, and a
default action if deferred past a horizon. Never present a decision without its
blast radius.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from . import config

# Item kinds in default priority order (build spec Sec 10) + GAP_HYPOTHESIS
# (addendum A3), ranked among the rest by blast radius.
PRIORITY = {
    "REFUTATION": 0,          # a stored lemma broke; dependents invalidated
    "GUARDIAN2_SEVERE": 1,    # G1/G2/G6 finding on a new candidate
    "GAP_HYPOTHESIS": 2,      # addendum A3: frontier hole, ranked by blast
    "CORPUS_CONTEST": 3,      # sweep finding on a stored lemma, by blast
    "ABSORPTION_CONFIRM": 4,  # candidate meets the absorption criterion
    "BRANCH_STALL": 5,        # budget decision needed
    "CONFLICT": 6,            # two units' claims inconsistent
    "TIER2": 7,               # Guardian 1 quarantine authorization
    "ATTENTION_OVERFLOW": -1, # A5 meta-item: the queue exceeded the cap
}


@dataclass
class HumanItem:
    kind: str
    node: str                       # lemma id / branch id / candidate id
    summary: str                    # what happened
    affects: Any = None             # what it affects (ids / count)
    cost: str = ""                  # what a decision costs
    default_action: str = ""        # if deferred past a horizon
    blast_radius: float = 0.0       # for ranking within a priority
    created_step: int = 0

    @property
    def priority(self) -> int:
        return PRIORITY.get(self.kind, 99)

    def sort_key(self) -> tuple:
        # lower priority first; higher blast first; earlier first
        return (self.priority, -self.blast_radius, self.created_step)


class HumanQueue:
    def __init__(self, daily_cap: int = config.HUMAN_QUEUE_DAILY_CAP) -> None:
        self.daily_cap = daily_cap
        self._items: list[HumanItem] = []

    def push(self, item: HumanItem) -> None:
        self._items.append(item)

    def pending(self) -> list[HumanItem]:
        """All items, best-first (never dropped)."""
        return sorted(self._items, key=lambda it: it.sort_key())

    def today_view(self) -> list[HumanItem]:
        """The at-most-cap items presented to the human today."""
        # the overflow meta-item, if present, always shows
        real = [it for it in self.pending() if it.kind != "ATTENTION_OVERFLOW"]
        return real[: self.daily_cap]

    def deferred_count(self) -> int:
        real = [it for it in self._items if it.kind != "ATTENTION_OVERFLOW"]
        return max(0, len(real) - self.daily_cap)

    def is_overflowing(self) -> bool:
        """A5: more uncertainty generated than resolved -> a pathology."""
        return self.deferred_count() > 0

    def overflow_item(self, step: int = 0) -> Optional[HumanItem]:
        """Surface persistent overflow as ONE queue item (build spec Sec 10)."""
        n = self.deferred_count()
        if n == 0:
            return None
        return HumanItem(
            kind="ATTENTION_OVERFLOW", node="queue",
            summary=f"queue exceeded the daily attention cap by {n} item(s)",
            affects=n,
            cost="the swarm is generating more uncertainty than it resolves (A5)",
            default_action="reduce live branches / raise Guardian 2 severity / "
                           "widen absorption windows (build spec F3)",
            created_step=step,
        )

    def resolve(self, node: str, kind: Optional[str] = None) -> bool:
        """Remove an item once the human has decided it."""
        for i, it in enumerate(self._items):
            if it.node == node and (kind is None or it.kind == kind):
                del self._items[i]
                return True
        return False

    def __len__(self) -> int:
        return len(self._items)
