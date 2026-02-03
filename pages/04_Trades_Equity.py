from __future__ import annotations

import runpy
from pathlib import Path

from src.compat.shims import warn_legacy_import


def _repo_root() -> Path:
    """Best-effort repo root discovery (works from /pages and /src/*)."""
    p = Path(__file__).resolve()
    for parent in p.parents:
        if (parent / 'src').is_dir() and (parent / '.doc').is_dir():
            return parent
    return p.parents[1]


ROOT = _repo_root()
TARGET = ROOT / 'src' / 'phase2' / 'pages' / '04_Trades_Equity.py'

warn_legacy_import('pages/04_Trades_Equity.py', 'src/phase2/pages/04_Trades_Equity.py')
runpy.run_path(str(TARGET), run_name='__main__')
