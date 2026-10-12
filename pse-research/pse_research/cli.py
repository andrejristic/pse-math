"""
Phase 1 CLI: push a candidate to the gate by hand, dump the journal, show corpus.

Usage:
  python -m pse_research.cli --db research.db push examples/good.json
  python -m pse_research.cli --db research.db refute L_good "n=0 breaks it"
  python -m pse_research.cli --db research.db journal
  python -m pse_research.cli --db research.db corpus
"""
from __future__ import annotations

import argparse
import json
import sys

from .model import Candidate
from .shared_lib import ResearchSharedLib
from .verifier import LeanBackend


def _cmd_push(lib: ResearchSharedLib, args: argparse.Namespace) -> int:
    cand = Candidate.from_json_file(args.file)
    result = lib.validate_contribution(cand)
    if result.accepted:
        print(f"ACCEPT  {cand.id}  status={result.status.value}")
        return 0
    print(f"REJECT  {cand.id}  check={result.failed_check.value}")
    print(f"        {result.detail}")
    return 1


def _cmd_refute(lib: ResearchSharedLib, args: argparse.Namespace) -> int:
    out = lib.refute(args.lemma_id, args.counterexample, source=args.by)
    print(f"REFUTED {out['refuted']}; invalidated {len(out['invalidated'])}: "
          f"{out['invalidated']}")
    return 0


def _cmd_journal(lib: ResearchSharedLib, args: argparse.Namespace) -> int:
    for ev in lib.journal.read_all():
        print(f"[{ev['seq']:>4}] {ev['type']:<20} {json.dumps(ev['payload'])}")
    return 0


def _cmd_corpus(lib: ResearchSharedLib, args: argparse.Namespace) -> int:
    counts = lib.corpus.counts_by_status()
    print("corpus by status:", json.dumps(counts))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="pse_research.cli")
    p.add_argument("--db", default="research.db", help="path to the sqlite db")
    p.add_argument("--lean", metavar="PROJECT_DIR", default=None,
                   help="use real Lean elaboration for C1 via a project dir "
                        "(default: symbolic backend, no Lean needed)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("push", help="push a candidate json to the gate")
    sp.add_argument("file")
    sp.set_defaults(fn=_cmd_push)

    sp = sub.add_parser("refute", help="refute a stored lemma")
    sp.add_argument("lemma_id")
    sp.add_argument("counterexample")
    sp.add_argument("--by", default="cli")
    sp.set_defaults(fn=_cmd_refute)

    sp = sub.add_parser("journal", help="dump the append-only journal")
    sp.set_defaults(fn=_cmd_journal)

    sp = sub.add_parser("corpus", help="show corpus status counts")
    sp.set_defaults(fn=_cmd_corpus)

    args = p.parse_args(argv)
    backend = LeanBackend(args.lean) if args.lean else None
    lib = ResearchSharedLib(args.db, backend=backend)
    try:
        return args.fn(lib, args)
    finally:
        lib.close()


if __name__ == "__main__":
    sys.exit(main())
