"""SENTINEL-ALPHA one-command runner.

Self-contained helper:
- Safe imports when invoked from scripts/ by adding project root to sys.path.
- Provides a small CLI: migrate, test, run, certify, status, verify.

Design contract:
- scripts/ = thin entrypoints
- src/     = core engine + db + canonical tools

Operational contract (Wave 5C):
- Generates (or preserves) a stable SENTINEL_RUN_ID for run/certify.
- Writes a transcript for each run/certify execution under reports/.
- Remains offline-by-default for certify; online must be explicit.

This file intentionally remains self-contained for operational stability.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def ensure_sys_path() -> Path:
    """Ensure project root is on sys.path even when invoked from scripts/."""
    root = Path(__file__).resolve().parents[1]
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root


def normalize_db_path(root: Path, db_path: str) -> str:
    p = Path(db_path)
    if not p.is_absolute():
        p = root / p
    return str(p.resolve())


def _load_local_env(root: Path) -> None:
    """Load config/sentinel.local.env if present (shell-agnostic).

    Format:
      KEY=value
      # comments allowed

    Only sets vars not already present in the environment.
    """
    env_path = root / "config" / "sentinel.local.env"
    if not env_path.exists():
        return

    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and (k not in os.environ):
                os.environ[k] = v
    except Exception:
        # Never fail the runner because of a local env file.
        return


def _ensure_run_id(command: str) -> str | None:
    """Ensure SENTINEL_RUN_ID exists for operational commands.

    We only force a run id for commands that produce/verify run artifacts.
    """
    if command not in {"run", "certify", "verify"}:
        return None

    rid = (os.environ.get("SENTINEL_RUN_ID") or "").strip()
    if not rid:
        rid = uuid4().hex
        os.environ["SENTINEL_RUN_ID"] = rid
    return rid


def _transcript_path(root: Path, command: str, run_id: str | None) -> str | None:
    if command not in {"run", "certify"}:
        return None
    if not run_id:
        return None
    os.makedirs(root / "reports", exist_ok=True)
    kind = "CERTIFY" if command == "certify" else "RUN"
    return str((root / "reports" / f"{kind}_TRANSCRIPT_{run_id}.txt").resolve())


def _append_transcript(transcript_path: str, text: str) -> None:
    try:
        with open(transcript_path, "a", encoding="utf-8") as f:
            f.write(text)
            if not text.endswith("\n"):
                f.write("\n")
    except Exception:
        # Transcripts are best-effort; never block the run.
        return


def run_cmd(cmd: list[str], *, cwd: Path | None = None, transcript_path: str | None = None) -> None:
    """Run a subprocess command, fail hard on non-zero exit code.

    If transcript_path is provided, capture stdout+stderr and append it to the transcript.
    """
    printable = " ".join(cmd)
    print("[cmd]", printable)

    t0 = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd is not None else None,
        capture_output=bool(transcript_path),
        text=True,
        check=False,
    )
    dt_ms = int((time.perf_counter() - t0) * 1000)

    if transcript_path:
        ts = datetime.now(timezone.utc).isoformat()
        header = f"\n===== {ts}Z | {dt_ms} ms | {printable} =====\n"
        _append_transcript(transcript_path, header)
        _append_transcript(transcript_path, (proc.stdout or "") + (proc.stderr or ""))

        # Echo back to console so interactive runs behave as before.
        if proc.stdout:
            sys.stdout.write(proc.stdout)
        if proc.stderr:
            sys.stderr.write(proc.stderr)

    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="sentinel", description="SENTINEL-ALPHA runner")
    parser.add_argument(
        "command",
        choices=["certify", "status", "verify", "migrate", "test", "run", "forecast"],
        help="Action to perform",
    )
    parser.add_argument(
        "--db",
        "--db-path",
        dest="db_path",
        default=os.environ.get("SENTINEL_ALPHA_DB_PATH", "data/sentinel_alpha.db"),
        help="Path to DuckDB database (default: data/sentinel_alpha.db)",
    )
    parser.add_argument("--skip-tests", action="store_true", help="Skip test suite (not recommended for certify)")

    net = parser.add_mutually_exclusive_group()
    net.add_argument(
        "--offline",
        action="store_true",
        help="Force offline mode (no network backfill).",
    )
    net.add_argument(
        "--online",
        action="store_true",
        help="Force online mode (network backfill allowed).",
    )

    parser.add_argument(
        "--no-backfill",
        action="store_true",
        help="Disable online backfill (deprecated; use --offline)",
    )
    parser.add_argument(
        "--provider-order",
        default=os.environ.get("SENTINEL_PRICE_PROVIDER_ORDER", "stooq"),
        help="Comma-separated provider order, e.g. stooq,yfinance,alphavantage",
    )
    parser.add_argument("--enable-yfinance", action="store_true", help="Enable yfinance provider")
    parser.add_argument(
        "--alphavantage-key",
        default=os.environ.get("ALPHAVANTAGE_API_KEY", ""),
        help="AlphaVantage API key (optional)",
    )
    parser.add_argument(
        "--run-id",
        default=os.environ.get("SENTINEL_RUN_ID", ""),
        help="Run identifier to verify (default: latest SUCCESS run)",
    )
    parser.add_argument(
        "--universe-id",
        default=os.environ.get("SENTINEL_UNIVERSE_ID", "ALL"),
        help="Universe id (default: ALL). Note: run/certify currently operate on ALL.",
    )
    return parser.parse_args(argv)


def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None or str(v).strip() == "":
        return bool(default)
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}


def apply_env(args: argparse.Namespace) -> None:
    """Apply runtime env configuration for downstream modules."""
    os.environ["SENTINEL_ALPHA_DB_PATH"] = args.db_path
    os.environ["SENTINEL_PRICE_PROVIDER_ORDER"] = args.provider_order

    # A7.0: disclosure defaults for retail-realism roadmap.
    # NOTE: these are *not* yet economic/ledger-altering switches. They are
    # recorded and surfaced in the audit report as explicit contracts.
    os.environ.setdefault("SENTINEL_DIVIDEND_POLICY", "B")
    os.environ.setdefault("SENTINEL_TIMING_MODE", "T_PLUS_1")

    # Default: disable yfinance unless explicitly enabled
    if args.enable_yfinance:
        os.environ["SENTINEL_DISABLE_YFINANCE"] = "0"
    else:
        os.environ.setdefault("SENTINEL_DISABLE_YFINANCE", "1")

    # A5.2: offline-by-default for certify; online must be explicit.
    # Precedence:
    #   1) --online
    #   2) --offline or --no-backfill
    #   3) certify defaults to offline
    if getattr(args, "online", False):
        os.environ["SENTINEL_ALLOW_ONLINE_BACKFILL"] = "1"
        os.environ["SENTINEL_OFFLINE"] = "0"
    else:
        offline = bool(getattr(args, "offline", False) or getattr(args, "no_backfill", False) or args.command == "certify")
        if offline:
            os.environ["SENTINEL_ALLOW_ONLINE_BACKFILL"] = "0"
            os.environ["SENTINEL_OFFLINE"] = "1"
        else:
            os.environ.setdefault("SENTINEL_ALLOW_ONLINE_BACKFILL", "1")
            os.environ.setdefault("SENTINEL_OFFLINE", "0")

    if args.alphavantage_key:
        os.environ["ALPHAVANTAGE_API_KEY"] = args.alphavantage_key


def cmd_status(db_path: str) -> None:
    """Deprecated local implementation.

    Use: <PY> -m src.tools.db_status --db <DB>
    """
    raise RuntimeError("cmd_status is deprecated; use src.tools.db_status")


def cmd_verify(db_path: str, run_id: str | None = None) -> None:
    """Deprecated local implementation.

    Use: <PY> -m src.tools.verify_run --db <DB> [--run-id <RID>]
    """
    raise RuntimeError("cmd_verify is deprecated; use src.tools.verify_run")


def main(argv: list[str] | None = None) -> None:
    root = ensure_sys_path()
    _load_local_env(root)

    args = parse_args(list(argv) if argv is not None else sys.argv[1:])
    args.db_path = normalize_db_path(root, args.db_path)
    apply_env(args)

    # Stable run id + transcript for operational clarity.
    run_id = _ensure_run_id(args.command)
    transcript_path = _transcript_path(root, args.command, run_id)
    if transcript_path:
        os.environ["SENTINEL_TRANSCRIPT_PATH"] = transcript_path
        os.makedirs(Path(transcript_path).parent, exist_ok=True)
        banner = (
            "SENTINEL-ALPHA TRANSCRIPT\n"
            f"command={args.command}\n"
            f"run_id={run_id}\n"
            f"db_path={args.db_path}\n"
            f"offline={os.environ.get('SENTINEL_OFFLINE','')} allow_online_backfill={os.environ.get('SENTINEL_ALLOW_ONLINE_BACKFILL','')}\n"
            f"started_utc={datetime.now(timezone.utc).isoformat()}\n"
        )
        _append_transcript(transcript_path, banner)

    py = sys.executable

    if args.command == "migrate":
        run_cmd([py, "-m", "src.db.migrate", "--db", args.db_path], cwd=root, transcript_path=transcript_path)
        return

    if args.command == "test":
        run_cmd([py, "main_test.py"], cwd=root, transcript_path=transcript_path)
        return

    if args.command == "run":
        # Preflight: validate ticker mappings and input coverage before starting the audit.
        run_cmd([py, "-m", "src.tools.verify_ticker_mappings", "--db", args.db_path], cwd=root, transcript_path=transcript_path)
        run_cmd([py, "-m", "src.tools.verify_inputs", "--db", args.db_path, "--universe-id", "ALL"], cwd=root, transcript_path=transcript_path)
        # Strict provenance gate (no test data): fail-fast before running the audit.
        run_cmd([py, "-m", "src.tools.verify_provenance", "--db", args.db_path, "--universe-id", "ALL"], cwd=root, transcript_path=transcript_path)
        # Wave 6 closure: optional pre-trade forecasts/ranking (default ON).
        if _env_bool("SENTINEL_ENABLE_FORECASTS", True):
            fr_cmd = [py, "-m", "src.tools.forecast_rankings", "--db", args.db_path, "--universe-id", "ALL"]
            if run_id:
                fr_cmd += ["--run-id", run_id]
            run_cmd(fr_cmd, cwd=root, transcript_path=transcript_path)
        run_cmd([py, "main.py"], cwd=root, transcript_path=transcript_path)
        return

    if args.command == "certify":
        run_cmd([py, "-m", "src.db.migrate", "--db", args.db_path], cwd=root, transcript_path=transcript_path)
        if not args.skip_tests:
            run_cmd([py, "main_test.py"], cwd=root, transcript_path=transcript_path)
        # Preflight: validate ticker mappings and input coverage before starting the audit.
        run_cmd([py, "-m", "src.tools.verify_ticker_mappings", "--db", args.db_path], cwd=root, transcript_path=transcript_path)
        run_cmd([py, "-m", "src.tools.verify_inputs", "--db", args.db_path, "--universe-id", "ALL"], cwd=root, transcript_path=transcript_path)
        # Strict provenance gate (no test data): fail-fast before running the audit.
        run_cmd([py, "-m", "src.tools.verify_provenance", "--db", args.db_path, "--universe-id", "ALL"], cwd=root, transcript_path=transcript_path)
        # Wave 6 closure: optional pre-trade forecasts/ranking (default ON).
        if _env_bool("SENTINEL_ENABLE_FORECASTS", True):
            fr_cmd = [py, "-m", "src.tools.forecast_rankings", "--db", args.db_path, "--universe-id", "ALL"]
            if run_id:
                fr_cmd += ["--run-id", run_id]
            run_cmd(fr_cmd, cwd=root, transcript_path=transcript_path)
        run_cmd([py, "main.py"], cwd=root, transcript_path=transcript_path)
        return

    if args.command == "forecast":
        # Standalone forecast generation (no schema changes, no network).
        uid = (args.universe_id or "ALL").strip() or "ALL"
        run_cmd([py, "-m", "src.tools.verify_ticker_mappings", "--db", args.db_path], cwd=root, transcript_path=transcript_path)
        run_cmd([py, "-m", "src.tools.verify_inputs", "--db", args.db_path, "--universe-id", uid], cwd=root, transcript_path=transcript_path)
        fr_cmd = [py, "-m", "src.tools.forecast_rankings", "--db", args.db_path, "--universe-id", uid]
        # If user provided --run-id, use it for artifact naming; otherwise default to asof_date naming.
        if (args.run_id or "").strip():
            fr_cmd += ["--run-id", args.run_id.strip()]
        run_cmd(fr_cmd, cwd=root, transcript_path=transcript_path)
        return

    if args.command == "verify":
        cmd = [py, "-m", "src.tools.verify_run", "--db", args.db_path]
        if (args.run_id or "").strip():
            cmd += ["--run-id", args.run_id]
        run_cmd(cmd, cwd=root, transcript_path=transcript_path)
        return

    if args.command == "status":
        run_cmd([py, "-m", "src.tools.db_status", "--db", args.db_path], cwd=root, transcript_path=transcript_path)
        return

    raise SystemExit(2)


if __name__ == "__main__":
    main()
