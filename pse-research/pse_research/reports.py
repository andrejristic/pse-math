"""
Human-decision report files — addendum A2.

Every HUMAN_DECISION lands in the append-only journal (the source of truth). This
renders, in ADDITION, a human-readable markdown file per decision, so the
mathematics/decision trail survives outside the system and is git-diffable. Bound
to the GATE_PASS commit hash when available.

[!] The report file is DERIVED from the journal, never a second source of truth.
    If the two diverge, the journal wins and the file is regenerated.
"""
from __future__ import annotations

import os
from typing import Any, Optional


def render_decision_md(decision: dict[str, Any]) -> str:
    """Render one decision (a dict; typically a journal HUMAN_DECISION payload)."""
    d = decision
    lines = [
        f"# Decision: {d.get('verdict', '(none)')} — {d.get('node', '?')}",
        "",
        f"- **kind**: {d.get('kind', '?')}",
        f"- **node**: {d.get('node', '?')}",
        f"- **commit**: {d.get('commit', '(none)')}",
        f"- **step**: {d.get('step', '?')}",
        "",
        "## What was decided",
        d.get("summary", "(no summary)"),
        "",
        "## Statement",
        "```lean",
        d.get("statement", "(n/a)"),
        "```",
        "",
        "## Informal claim (the theorem you MEANT)",
        d.get("informal_claim", "(n/a)"),
        "",
        "## Blast radius",
        f"{d.get('blast_radius', '(unknown)')}",
        "",
        "## Evidence / findings seen",
        d.get("evidence", "(none recorded)"),
        "",
        "## Verdict",
        f"**{d.get('verdict', '(none)')}**"
        + (f" — {d['rationale']}" if d.get("rationale") else ""),
        "",
    ]
    return "\n".join(lines)


def _safe_name(node: str, step: Any) -> str:
    stem = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(node))
    return f"decision_{stem}_{step}.md"


def write_report_file(reports_dir: str, decision: dict[str, Any]) -> str:
    """Write the rendered decision to reports_dir; returns the file path."""
    os.makedirs(reports_dir, exist_ok=True)
    path = os.path.join(reports_dir, _safe_name(decision.get("node", "x"),
                                                decision.get("step", 0)))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(render_decision_md(decision))
    return path
