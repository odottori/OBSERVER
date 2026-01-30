#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# pack_session.py
# - deterministic session folders (no symlinks)
# - auto-run-id: DB-first (DuckDB audit_runs), fs fallback
# - session_key: stable across actions (run/certify/forecast) by excluding "cmd" from hash basis
# Debug: set env PACK_SESSION_DEBUG=1


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def utc_now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def canonical_json(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha1_12(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


def norm_db_path(db_path: str) -> str:
    rr = repo_root()
    p = Path(db_path)
    if not p.is_absolute():
        p = (rr / p).resolve()
    try:
        rel = p.relative_to(rr.resolve())
        return rel.as_posix()
    except Exception:
        return p.as_posix()


def debug_enabled() -> bool:
    v = os.environ.get("PACK_SESSION_DEBUG", "").strip().lower()
    return v in ("1", "true", "yes", "y", "on")


def dbg(msg: str) -> None:
    if debug_enabled():
        print(f"[pack_session][debug] {msg}")


@dataclass(frozen=True)
class SessionParams:
    cmd: str  # run | certify | forecast
    db_path: str
    universe_id: str
    mode: str  # offline | online
    provider_order: str
    enable_yfinance: bool
    alphavantage_key_set: bool
    extra: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cmd": self.cmd,
            "db_path": self.db_path,
            "universe_id": self.universe_id,
            "mode": self.mode,
            "provider_order": self.provider_order,
            "enable_yfinance": self.enable_yfinance,
            "alphavantage_key_set": self.alphavantage_key_set,
            "extra": self.extra,
        }


def compute_session_key(sp: SessionParams) -> Tuple[str, str]:
    # stable across actions: exclude cmd
    basis = sp.to_dict().copy()
    basis.pop("cmd", None)
    payload = canonical_json(basis)
    return sha1_12(payload), payload


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def copy_if_exists(src: Path, dst: Path, actions: List[str]) -> None:
    if not src.exists():
        actions.append(f"SKIP missing: {src.as_posix()}")
        return
    ensure_dir(dst.parent)
    dst.write_bytes(src.read_bytes())
    actions.append(f"COPIED: {src.as_posix()} -> {dst.as_posix()}")


def load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_json(path: Path, obj: Dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def rotate_history(history_dir: Path, keep_last: int) -> None:
    if keep_last <= 0 or not history_dir.exists():
        return
    entries = sorted([p for p in history_dir.iterdir() if p.is_dir()], key=lambda p: p.name)
    excess = len(entries) - keep_last
    for i in range(excess):
        for child in entries[i].rglob("*"):
            if child.is_file():
                try:
                    child.unlink()
                except Exception:
                    pass
        for child in sorted(entries[i].rglob("*"), reverse=True):
            if child.is_dir():
                try:
                    child.rmdir()
                except Exception:
                    pass
        try:
            entries[i].rmdir()
        except Exception:
            pass


# -----------------------------
# DuckDB run-id resolution
# -----------------------------

def _duckdb_connect(db_path: Path):
    try:
        import duckdb  # type: ignore
    except Exception as e:
        dbg(f"duckdb import failed: {e}")
        return None
    try:
        return duckdb.connect(str(db_path))
    except Exception as e:
        dbg(f"duckdb connect failed: {e}")
        return None


def _duckdb_columns(conn, table: str) -> set[str]:
    try:
        rows = conn.execute(
            "select column_name from information_schema.columns where lower(table_name)=lower(?)",
            [table],
        ).fetchall()
        return {str(r[0]) for r in rows}
    except Exception as e:
        dbg(f"information_schema.columns failed: {e}")
        return set()


def _duckdb_table_exists(conn, table: str) -> bool:
    try:
        row = conn.execute(
            "select 1 from information_schema.tables where lower(table_name)=lower(?) limit 1",
            [table],
        ).fetchone()
        return row is not None
    except Exception:
        try:
            conn.execute(f"select 1 from {table} limit 1").fetchone()
            return True
        except Exception:
            return False


def _try_duckdb_latest_run_id(db_path: Path) -> Tuple[Optional[str], str]:
    conn = _duckdb_connect(db_path)
    if conn is None:
        return None, "duckdb connect/import failed"

    try:
        if not _duckdb_table_exists(conn, "audit_runs"):
            return None, "audit_runs table missing"

        cols = _duckdb_columns(conn, "audit_runs")
        dbg(f"audit_runs columns={sorted(cols)}")

        if "run_id" not in cols:
            return None, "audit_runs.run_id missing"

        time_order: Optional[str] = None
        if {"finished_at", "started_at"}.issubset(cols):
            time_order = "finished_at desc nulls last, started_at desc nulls last"
        elif {"ts_end", "ts_start"}.issubset(cols):
            time_order = "ts_end desc nulls last, ts_start desc nulls last"
        elif "finished_at" in cols:
            time_order = "finished_at desc nulls last"
        elif "started_at" in cols:
            time_order = "started_at desc nulls last"
        elif "created_at" in cols:
            time_order = "created_at desc nulls last"
        elif "ts" in cols:
            time_order = "ts desc nulls last"

        if time_order is None:
            return None, "no usable time columns in audit_runs"

        status_prefix = ""
        if "status" in cols:
            status_prefix = (
                "case when upper(cast(status as varchar)) in ('SUCCESS','PASS') then 0 else 1 end asc, "
            )

        q = (
            "select cast(run_id as varchar) as run_id "
            "from audit_runs "
            "where run_id is not null and length(cast(run_id as varchar)) > 0 "
            f"order by {status_prefix}{time_order} "
            "limit 1"
        )
        dbg(f"duckdb query={q}")

        row = conn.execute(q).fetchone()
        if row and row[0]:
            return str(row[0]), ""

        return None, "audit_runs has no non-empty run_id rows"
    except Exception as e:
        return None, f"duckdb query failed: {type(e).__name__}: {e}"
    finally:
        try:
            conn.close()
        except Exception:
            pass


# -----------------------------
# FS fallback run-id resolution
# -----------------------------

def _try_reports_latest_run_id(reports_dir: Path) -> Optional[str]:
    candidates: List[Tuple[float, str, Path]] = []

    patterns = [
        ("CERTIFY_TRANSCRIPT_*.txt", r"^CERTIFY_TRANSCRIPT_(?P<id>[0-9a-fA-F\-]{16,})\.txt$"),
        ("RUN_TRANSCRIPT_*.txt", r"^RUN_TRANSCRIPT_(?P<id>[0-9a-fA-F\-]{16,})\.txt$"),
        ("AUDIT_COMPLETE_*.md", r"^AUDIT_COMPLETE_(?P<id>[0-9a-fA-F\-]{16,})\.md$"),
        ("FORECAST_RANKING_*.json", r"^FORECAST_RANKING_(?P<id>[0-9a-fA-F\-]{16,})\.json$"),
    ]

    for glob_pat, rx in patterns:
        for p in reports_dir.glob(glob_pat):
            m = re.match(rx, p.name)
            if not m:
                continue
            rid = m.group("id")
            try:
                mtime = p.stat().st_mtime
            except Exception:
                continue
            candidates.append((mtime, rid, p))

    if not candidates:
        return None

    candidates.sort(key=lambda t: t[0], reverse=True)
    return candidates[0][1]


def resolve_run_id_auto(db_path: Path, reports_dir: Path) -> Tuple[Optional[str], str]:
    rid, detail = _try_duckdb_latest_run_id(db_path)
    if rid:
        return rid, "duckdb:audit_runs"
    if detail:
        print(f"[pack_session] NOTE: DB auto-run-id unavailable: {detail}")

    rid2 = _try_reports_latest_run_id(reports_dir)
    if rid2:
        return rid2, "fs:reports"
    return None, "none"


# -----------------------------
# Packing
# -----------------------------

def pack_session(
    sp: SessionParams,
    run_id: Optional[str],
    asof_date: Optional[str],
    snapshot: bool,
    keep_last: int,
    dry_run: bool,
) -> int:
    rr = repo_root()
    reports = rr / "reports"
    db_abs = (rr / sp.db_path).resolve() if not Path(sp.db_path).is_absolute() else Path(sp.db_path)

    auto_requested = (run_id is None) or (run_id.strip().lower() in ("", "auto", "latest"))
    if auto_requested:
        rid, src = resolve_run_id_auto(db_abs, reports)
        if rid:
            run_id = rid
            print(f"[pack_session] Auto-selected run_id={run_id} via {src}")
        else:
            print("[pack_session] ERROR: could not auto-resolve run_id (DB and reports/ both empty).")

    session_key, payload = compute_session_key(sp)
    base = rr / "reports" / "sessions" / session_key
    latest = base / "LATEST"
    hist = base / "history"

    actions: List[str] = []

    session_json = base / "session.json"
    meta = load_json(session_json) or {}
    meta.setdefault("session_key", session_key)
    meta.setdefault("created_at_utc", datetime.now(timezone.utc).isoformat())
    meta["params"] = sp.to_dict()
    meta["params_canonical_json"] = payload

    meta.setdefault("runs", [])
    if run_id:
        meta["runs"].append({"run_id": run_id, "packed_at_utc": datetime.now(timezone.utc).isoformat()})
        seen = set()
        dedup = []
        for r in meta["runs"]:
            rid2 = r.get("run_id")
            if not rid2 or rid2 in seen:
                continue
            seen.add(rid2)
            dedup.append(r)
        meta["runs"] = dedup

    if snapshot:
        snap_dir = hist / utc_now_compact()
        if dry_run:
            actions.append(f"DRY-RUN snapshot to: {snap_dir.as_posix()}")
        else:
            ensure_dir(snap_dir)
            if latest.exists():
                for f in latest.rglob("*"):
                    if f.is_file():
                        rel = f.relative_to(latest)
                        dst = snap_dir / rel
                        ensure_dir(dst.parent)
                        dst.write_bytes(f.read_bytes())
            rotate_history(hist, keep_last)

    if dry_run:
        actions.append(f"DRY-RUN ensure LATEST: {latest.as_posix()}")
    else:
        ensure_dir(latest)

    # Audit
    if run_id:
        copy_if_exists(reports / f"AUDIT_COMPLETE_{run_id}.md", latest / "audit" / "AUDIT_COMPLETE.md", actions)
    copy_if_exists(reports / "AUDIT_COMPLETE.md", latest / "audit" / "AUDIT_COMPLETE_LATEST.md", actions)

    # Transcripts
    if run_id:
        copy_if_exists(reports / f"RUN_TRANSCRIPT_{run_id}.txt", latest / "transcripts" / "RUN_TRANSCRIPT.txt", actions)
        copy_if_exists(reports / f"CERTIFY_TRANSCRIPT_{run_id}.txt", latest / "transcripts" / "CERTIFY_TRANSCRIPT.txt", actions)

    # Forecast
    if run_id:
        copy_if_exists(reports / f"FORECAST_RANKING_{run_id}.json", latest / "forecast" / "FORECAST_RANKING.json", actions)
        copy_if_exists(reports / f"FORECAST_RANKING_{run_id}.md", latest / "forecast" / "FORECAST_RANKING.md", actions)
    if asof_date:
        copy_if_exists(reports / f"FORECAST_RANKING_{asof_date}.json", latest / "forecast" / "FORECAST_RANKING_ASOF.json", actions)
        copy_if_exists(reports / f"FORECAST_RANKING_{asof_date}.md", latest / "forecast" / "FORECAST_RANKING_ASOF.md", actions)
    copy_if_exists(reports / "FORECAST_RANKING_LATEST.json", latest / "forecast" / "FORECAST_RANKING_LATEST.json", actions)

    if not dry_run:
        save_json(session_json, meta)

    actions_md = base / f"pack_log_{utc_now_compact()}.md"
    text: List[str] = []
    text.append("# PACK SESSION")
    text.append(f"- session_key: `{session_key}`")
    text.append(f"- cmd: `{sp.cmd}`")
    text.append(f"- db: `{sp.db_path}`")
    text.append(f"- universe_id: `{sp.universe_id}`")
    text.append(f"- mode: `{sp.mode}`")
    if run_id:
        text.append(f"- run_id: `{run_id}`")
    if asof_date:
        text.append(f"- asof_date: `{asof_date}`")
    text.append("")
    text.append("## Actions")
    text.extend([f"- {a}" for a in actions])

    if dry_run:
        print("\n".join(text))
    else:
        actions_md.write_text("\n".join(text), encoding="utf-8")
        print("\n".join(text))
        print(f"\nWrote: {actions_md.as_posix()}")
        print(f"Session dir: {base.as_posix()}")

    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Pack reports into deterministic session folders (no symlinks).")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("pack", help="Pack artifacts into reports/sessions/<session_key>/LATEST")
    sp.add_argument("--action", default="run", choices=["run", "certify", "forecast"])
    sp.add_argument("--db", required=True)
    sp.add_argument("--universe-id", default="ALL")
    mode = sp.add_mutually_exclusive_group(required=True)
    mode.add_argument("--offline", action="store_true")
    mode.add_argument("--online", action="store_true")
    sp.add_argument("--provider-order", default="")
    sp.add_argument("--enable-yfinance", action="store_true")
    sp.add_argument("--alphavantage-key", default="")
    sp.add_argument("--extra", default="")

    sp.add_argument("--run-id", default="auto", help="Default: auto (resolve latest from DB/reports).")
    sp.add_argument("--asof-date", default="")
    sp.add_argument("--snapshot", action="store_true")
    sp.add_argument("--keep-last", type=int, default=0)
    sp.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    sp = SessionParams(
        cmd=args.action,
        db_path=norm_db_path(args.db),
        universe_id=args.universe_id,
        mode="offline" if args.offline else "online",
        provider_order=args.provider_order.strip(),
        enable_yfinance=bool(args.enable_yfinance),
        alphavantage_key_set=bool(args.alphavantage_key.strip()),
        extra=args.extra.strip(),
    )

    rid = args.run_id.strip()
    run_id: Optional[str] = rid if rid.lower() not in ("", "auto", "latest") else None

    return pack_session(
        sp=sp,
        run_id=run_id,
        asof_date=args.asof_date.strip() or None,
        snapshot=bool(args.snapshot),
        keep_last=int(args.keep_last),
        dry_run=bool(args.dry_run),
    )


if __name__ == "__main__":
    raise SystemExit(main())
