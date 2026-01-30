#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import json
from pathlib import Path
from typing import List, Optional, Tuple


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def run_cmd(cmd: List[str], env: dict, dry_run: bool) -> int:
    printable = " ".join(cmd)
    print(f"[ops_run_session] $ {printable}")
    if dry_run:
        return 0
    p = subprocess.run(cmd, env=env)
    return int(p.returncode)


def _norm_db_path(rr: Path, db_path: str) -> str:
    p = Path(db_path)
    if not p.is_absolute():
        p = (rr / p).resolve()
    try:
        rel = p.relative_to(rr.resolve())
        return rel.as_posix()
    except Exception:
        return p.as_posix()


def _read_json(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _match_params(params: dict, want: dict) -> bool:
    # Compare only keys we care about; ignore extra keys.
    for k, v in want.items():
        if params.get(k) != v:
            return False
    return True


def find_session_dir(rr: Path, want_params: dict) -> Tuple[Optional[Path], Optional[str]]:
    sessions_root = rr / "reports" / "sessions"
    if not sessions_root.exists():
        return None, None

    best: Optional[Tuple[float, Path, str]] = None
    for session_dir in sessions_root.iterdir():
        if not session_dir.is_dir():
            continue
        sj = session_dir / "session.json"
        if not sj.exists():
            continue
        obj = _read_json(sj)
        if not obj:
            continue
        params = obj.get("params") or {}
        if not isinstance(params, dict):
            continue
        if not _match_params(params, want_params):
            continue
        try:
            mtime = sj.stat().st_mtime
        except Exception:
            mtime = 0.0
        key = str(obj.get("session_key") or session_dir.name)
        cand = (mtime, session_dir, key)
        if best is None or cand[0] > best[0]:
            best = cand

    if best is None:
        return None, None
    return best[1], best[2]


def main() -> int:
    rr = repo_root()
    sentinel = rr / "scripts" / "sentinel.py"
    packer = rr / "scripts" / "pack_session.py"

    if not sentinel.exists():
        print(f"[ops_run_session] ERROR: missing {sentinel}")
        return 2
    if not packer.exists():
        print(f"[ops_run_session] ERROR: missing {packer}")
        return 2

    ap = argparse.ArgumentParser(description="Run -> pack -> certify -> pack (DB-first auto-run-id).")
    ap.add_argument("--db", required=True, help="Path to DuckDB (e.g. .\\data\\sentinel_alpha.db)")
    ap.add_argument("--universe-id", default="ALL")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--offline", action="store_true", help="Force offline mode (recommended).")
    mode.add_argument("--online", action="store_true", help="Allow online mode.")
    ap.add_argument("--skip-run", action="store_true", help="Skip sentinel run step.")
    ap.add_argument("--skip-certify", action="store_true", help="Skip sentinel certify step.")
    ap.add_argument("--skip-pack", action="store_true", help="Skip packing steps.")
    ap.add_argument("--pack-debug", action="store_true", help="Enable PACK_SESSION_DEBUG=1 for packer.")
    ap.add_argument("--dry-run", action="store_true", help="Print commands only.")
    args = ap.parse_args()

    # Default: offline if user did not specify
    offline = True
    if args.online:
        offline = False
    if args.offline:
        offline = True

    pyexe = sys.executable
    env = os.environ.copy()
    if args.pack_debug:
        env["PACK_SESSION_DEBUG"] = "1"

    db = args.db
    universe = args.universe_id

    if not args.skip_run:
        cmd = [pyexe, str(sentinel), "run", "--db", db, "--universe-id", universe]
        cmd += ["--offline"] if offline else ["--online"]
        rc = run_cmd(cmd, env, args.dry_run)
        if rc != 0:
            print(f"[ops_run_session] ERROR: sentinel run failed rc={rc}")
            return rc

    if not args.skip_pack and not args.skip_run:
        cmd = [pyexe, str(packer), "pack", "--action", "run", "--db", db, "--universe-id", universe]
        cmd += ["--offline"] if offline else ["--online"]
        rc = run_cmd(cmd, env, args.dry_run)
        if rc != 0:
            print(f"[ops_run_session] ERROR: pack (run) failed rc={rc}")
            return rc

    if not args.skip_certify:
        cmd = [pyexe, str(sentinel), "certify", "--db", db, "--universe-id", universe]
        rc = run_cmd(cmd, env, args.dry_run)
        if rc != 0:
            print(f"[ops_run_session] ERROR: sentinel certify failed rc={rc}")
            return rc

    if not args.skip_pack and not args.skip_certify:
        cmd = [pyexe, str(packer), "pack", "--action", "certify", "--db", db, "--universe-id", universe]
        cmd += ["--offline"] if offline else ["--online"]
        rc = run_cmd(cmd, env, args.dry_run)
        if rc != 0:
            print(f"[ops_run_session] ERROR: pack (certify) failed rc={rc}")
            return rc

    want = {
        "db_path": _norm_db_path(rr, db),
        "universe_id": universe,
        "mode": "offline" if offline else "online",
    }
    sdir, skey = find_session_dir(rr, want)

    print("[ops_run_session] DONE")
    if sdir and skey:
        latest = sdir / "LATEST"
        print(f"[ops_run_session] SESSION={skey}")
        print(f"[ops_run_session] Session dir: {sdir.as_posix()}")
        print(f"[ops_run_session] LATEST: {latest.as_posix()}")
    else:
        print("[ops_run_session] NOTE: could not locate session dir (session.json not found or params mismatch).")
        print("[ops_run_session] Expected under: .\\reports\\sessions\\<session_key>\\LATEST\\")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
