#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/guardian.py

GUARDIAN front-door CLI.

This repo uses *direct mode*:
- Source of truth: ./docs/
- Operational control room: ./.doc/

Implementation notes
--------------------
- The operational commands (init/sync/lint/derive/status/programme) live in
  `scripts/guardian_ops.py`.
- The JIT prompt generator lives in `scripts/guardian_next.py`.

This wrapper keeps a stable user interface:
  py scripts/guardian.py <command> [args]
"""

from __future__ import annotations

import sys
from typing import List, Optional


USAGE = """\
Usage:
  py scripts/guardian.py <command> [args]

Commands:
  init                 Initialize .doc/ scaffolding (non-destructive).
  sync [--clean]       Validate docs/ and update .doc/CANONICAL_LIBRARY.md (direct mode).
  lint                 Validate structure and required docs; warn on anomalies.
  derive               Generate .doc/canonical/derived/{PROJ,TECH,DDT}.md.
  status               Print current GUARDIAN operational status.
  programme            Write a short operational plan into CURRENT_STATE.md.
  next                 Generate/update p0 in .doc/CURRENT_STATE.md from .doc/TODO.md.
  gate                 Run the WI gate suite (writes reports/*_<WI>[_CLOSE].log) + collector.
  collect              Check expected logs for a WI in reports/ (collector B).
  docs-check           Validate docset markdown links (docs/ + .doc/).
  help                 Show this message.
"""


OPS_COMMANDS = {"init", "sync", "lint", "derive", "status", "programme"}


def _print_usage() -> None:
    sys.stdout.write(USAGE + "\n")


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if not argv or argv[0] in {"-h", "--help", "help"}:
        _print_usage()
        return 0

    cmd, *rest = argv

    if cmd in OPS_COMMANDS:
        import guardian_ops
        # guardian_ops expects argv like: ["sync", "--clean"]
        return int(guardian_ops.main([cmd] + rest))

    if cmd == "next":
        if rest:
            sys.stderr.write("ERROR: 'guardian next' does not accept extra arguments.\n")
            return 2

        import guardian_next

        # guardian_next uses argparse and expects sys.argv[1:] == ["next"]
        old_argv = sys.argv
        try:
            sys.argv = ["guardian_next", "next"]
            return int(guardian_next.main())
        finally:
            sys.argv = old_argv

    if cmd == "collect":
        import wi_log_collector

        # wi_log_collector expects argv like: ["--wi", "WI-0160", "--mode", "normal"]
        return int(wi_log_collector.main(rest))

    if cmd == "gate":
        import wi_gate_runner

        # wi_gate_runner expects argv like: ["--wi", "WI-0240", "--mode", "normal"]
        return int(wi_gate_runner.main(rest))

    if cmd == "docs-check":
        import doc_integrity_check

        # doc_integrity_check expects argv like: ["--mode", "hard"]  (default: hard)
        return int(doc_integrity_check.main(rest))

    sys.stderr.write(f"ERROR: Unknown command '{cmd}'.\n\n")
    _print_usage()
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
