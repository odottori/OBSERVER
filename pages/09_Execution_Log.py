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
TARGET = ROOT / 'src' / 'phase2' / 'pages' / '09_Execution_Log.py'

warn_legacy_import('pages/09_Execution_Log.py', 'src/phase2/pages/09_Execution_Log.py')
runpy.run_path(str(TARGET), run_name='__main__')
