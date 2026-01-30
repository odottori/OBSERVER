"""Operational reset utility (NEWS-ALPHA / SENTINEL-ALPHA).

Goals
-----
- Provide a repeatable clean-room operator workflow.
- Default to safe behavior (dry-run unless --yes).
- Never modify schema beyond running existing idempotent migrations.

Typical usage
-------------
<PY> scripts/ops_reset.py doctor
<PY> scripts/ops_reset.py reset --yes

Multi-OS:
- Windows/PowerShell: <PY> := `py -3.14` (or `py`)
- Linux/macOS:        <PY> := `python`

Notes
-----
- By default, DB is cleaned (audit tables + NEWS-ALPHA rows) but not deleted.
- Use --db-reset to replace the DuckDB file (it will be backed up first).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


def ensure_sys_path() -> Path:
    """Ensure project root is on sys.path even when invoked from scripts/."""

    root = Path(__file__).resolve().parents[1]
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def normalize_db_path(root: Path, db_path: str) -> Path:
    p = Path(db_path)
    if not p.is_absolute():
        p = root / p
    return p.resolve()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _safe_rm_file(p: Path, *, root: Path, dry_run: bool) -> bool:
    if not p.exists():
        return False
    if not _is_within(p, root):
        raise RuntimeError(f"Refusing to delete outside repo root: {p}")
    if dry_run:
        print(f"[DRY] rm {p}")
        return True
    try:
        p.unlink()
        return True
    except IsADirectoryError:
        return False


def _safe_rm_tree(p: Path, *, root: Path, dry_run: bool) -> bool:
    if not p.exists():
        return False
    if not _is_within(p, root):
        raise RuntimeError(f"Refusing to delete outside repo root: {p}")
    if dry_run:
        print(f"[DRY] rmtree {p}")
        return True
    shutil.rmtree(p)
    return True


def _safe_rm_dir_contents(p: Path, *, root: Path, dry_run: bool, keep_files: Sequence[str] = ()) -> int:
    if not p.exists() or not p.is_dir():
        return 0
    if not _is_within(p, root):
        raise RuntimeError(f"Refusing to delete outside repo root: {p}")

    keep = {k for k in keep_files}
    n = 0
    for child in p.iterdir():
        if child.name in keep:
            continue
        if child.is_dir():
            n += 1 if _safe_rm_tree(child, root=root, dry_run=dry_run) else 0
        else:
            n += 1 if _safe_rm_file(child, root=root, dry_run=dry_run) else 0
    return n


def _run_migrate(root: Path, db_path: Path) -> None:
    # Use the current interpreter so that "py -3.14" works on Windows.
    cmd = [sys.executable, "-m", "src.db.migrate", "--db", str(db_path)]
    print("[cmd]", " ".join(cmd))
    p = subprocess.run(cmd, cwd=str(root), check=False)
    if p.returncode != 0:
        raise SystemExit(p.returncode)


def _duckdb_connect(db_path: Path):
    import duckdb  # type: ignore

    return duckdb.connect(str(db_path))


def _table_exists(con, table: str) -> bool:
    q = """
    SELECT 1
    FROM information_schema.tables
    WHERE table_schema='main' AND table_name = ?
    LIMIT 1
    """
    return con.execute(q, [table]).fetchone() is not None


def _exec_delete(con, sql: str, params: Sequence[object] = ()) -> int:
    # DuckDB returns rowcount unreliably for DELETE; compute via COUNT(*) before/after when needed.
    con.execute(sql, list(params))
    return 0


def _count(con, table: str, where_sql: str = "", params: Sequence[object] = ()) -> int:
    if not _table_exists(con, table):
        return 0
    q = f"SELECT COUNT(*) FROM {table}"
    if where_sql.strip():
        q += f" WHERE {where_sql}"
    r = con.execute(q, list(params)).fetchone()
    return int(r[0]) if r and r[0] is not None else 0


@dataclass
class DBPurgeReport:
    actions: List[str]


def purge_db(
    *,
    db_path: Path,
    firm: str,
    model: str,
    wipe_audit: bool,
    wipe_news_alpha: bool,
    wipe_sentiment_cache: bool,
    wipe_prices: bool,
    wipe_universe: bool,
    dry_run: bool,
) -> DBPurgeReport:
    actions: List[str] = []

    if not db_path.exists():
        actions.append(f"DB missing: {db_path} (will be created by migrations)")
        return DBPurgeReport(actions=actions)

    if dry_run:
        actions.append(f"[DRY] Would open DuckDB: {db_path}")
        return DBPurgeReport(actions=actions)

    con = _duckdb_connect(db_path)
    try:
        # NEWS-ALPHA rows
        if wipe_news_alpha and _table_exists(con, "recs"):
            before = _count(con, "recs", "firm = ?", [firm])
            _exec_delete(con, "DELETE FROM recs WHERE firm = ?", [firm])
            after = _count(con, "recs", "firm = ?", [firm])
            actions.append(f"DB: recs firm={firm}: {before} -> {after}")

        if wipe_sentiment_cache and _table_exists(con, "sentiment_cache"):
            before = _count(con, "sentiment_cache", "model = ?", [model])
            _exec_delete(con, "DELETE FROM sentiment_cache WHERE model = ?", [model])
            after = _count(con, "sentiment_cache", "model = ?", [model])
            actions.append(f"DB: sentiment_cache model={model}: {before} -> {after}")

        # Session/audit tables
        if wipe_audit:
            for t in ["audit_signal_decisions", "audit_trades", "audit_equity", "audit_runs"]:
                if not _table_exists(con, t):
                    continue
                before = _count(con, t)
                _exec_delete(con, f"DELETE FROM {t}")
                after = _count(con, t)
                actions.append(f"DB: {t}: {before} -> {after}")

        # Market data (optional)
        if wipe_prices:
            for t in ["data_gaps", "dividends", "prices", "ticker_halts", "market_halts"]:
                if not _table_exists(con, t):
                    continue
                before = _count(con, t)
                _exec_delete(con, f"DELETE FROM {t}")
                after = _count(con, t)
                actions.append(f"DB: {t}: {before} -> {after}")

        # Universe/ticker mappings (optional)
        if wipe_universe:
            for t in ["universe_membership", "universes", "ticker_mappings"]:
                if not _table_exists(con, t):
                    continue
                before = _count(con, t)
                _exec_delete(con, f"DELETE FROM {t}")
                after = _count(con, t)
                actions.append(f"DB: {t}: {before} -> {after}")

        # Compact (best-effort)
        try:
            con.execute("VACUUM")
        except Exception:
            pass

    finally:
        try:
            con.close()
        except Exception:
            pass

    return DBPurgeReport(actions=actions)


@dataclass
class FSPlan:
    files_deleted: int
    dirs_deleted: int
    notes: List[str]


def purge_filesystem(
    *,
    root: Path,
    scope: str,
    purge_history_raw: bool,
    dry_run: bool,
) -> FSPlan:
    files_deleted = 0
    dirs_deleted = 0
    notes: List[str] = []

    # runs/
    runs_dir = root / "runs"
    if runs_dir.exists():
        # remove everything under runs/
        n = _safe_rm_dir_contents(runs_dir, root=root, dry_run=dry_run)
        notes.append(f"runs/: removed {n} item(s)")
        files_deleted += n

    # reports/
    reports_dir = root / "reports"
    if reports_dir.exists():
        if scope == "full":
            # Keep reports/__init__.py (present in this repo)
            n = _safe_rm_dir_contents(reports_dir, root=root, dry_run=dry_run, keep_files=("__init__.py", "news_alpha"))
            notes.append(f"reports/: removed {n} item(s) (kept __init__.py, news_alpha/)")
            files_deleted += n

        # Always purge news_alpha artifacts (but keep folder skeleton)
        na = reports_dir / "news_alpha"
        if na.exists():
            # Purge everything under reports/news_alpha/**
            # Keep the directory itself.
            n = _safe_rm_dir_contents(na, root=root, dry_run=dry_run)
            notes.append(f"reports/news_alpha/: removed {n} item(s)")
            files_deleted += n

    # data/news_alpha/history
    hist_root = root / "data" / "news_alpha" / "history" / "gdelt1"
    if hist_root.exists():
        # Always clear manifests + fixtures
        for rel in ["manifests", "fixtures"]:
            p = hist_root / rel
            if p.exists():
                n = _safe_rm_dir_contents(p, root=root, dry_run=dry_run)
                notes.append(f"{p.relative_to(root)}: removed {n} item(s)")
                files_deleted += n

        if purge_history_raw:
            for rel in ["events/raw", "gkg/raw"]:
                p = hist_root / rel
                if p.exists():
                    n = _safe_rm_dir_contents(p, root=root, dry_run=dry_run)
                    notes.append(f"{p.relative_to(root)}: removed {n} item(s)")
                    files_deleted += n
        else:
            notes.append("history raw: preserved (use --purge-history-raw to delete)")

    return FSPlan(files_deleted=files_deleted, dirs_deleted=dirs_deleted, notes=notes)


def write_transcript(root: Path, *, title: str, lines: List[str]) -> Path:
    out_dir = root / "reports" / "news_alpha" / "ops"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"ops_reset_{utc_stamp()}.md"

    content: List[str] = []
    content.append(f"# {title}")
    content.append("")
    content.extend(lines)
    content.append("")
    path.write_text("\n".join(content), encoding="utf-8")
    return path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ops_reset", description="Operational reset utility")
    sub = p.add_subparsers(dest="command", required=True)

    def _add_common(x: argparse.ArgumentParser) -> None:
        x.add_argument(
            "--db",
            default=os.environ.get("SENTINEL_ALPHA_DB_PATH", "data/sentinel_alpha.db"),
            help="DuckDB path (default: data/sentinel_alpha.db)",
        )
        x.add_argument(
            "--scope",
            choices=["news-alpha", "full"],
            default="full",
            help="news-alpha: only NEWS-ALPHA artifacts; full: also purge SENTINEL artifacts under reports/ (default: full)",
        )
        x.add_argument(
            "--purge-history-raw",
            action="store_true",
            help="Also delete history raw zips under data/news_alpha/history/gdelt1/*/raw",
        )
        x.add_argument(
            "--firm",
            default="NEWS-ALPHA",
            help="Firm name stored in recs (default: NEWS-ALPHA)",
        )
        x.add_argument(
            "--model",
            default="lexicon-v1",
            help="Sentiment model stored in sentiment_cache (default: lexicon-v1)",
        )
        x.add_argument("--wipe-audit", action="store_true", help="Delete audit_* tables (sessions)")
        x.add_argument("--wipe-news-alpha", action="store_true", help="Delete recs rows for NEWS-ALPHA firm")
        x.add_argument(
            "--wipe-sentiment-cache",
            action="store_true",
            help="Delete sentiment_cache rows for the given model",
        )
        x.add_argument(
            "--wipe-prices",
            action="store_true",
            help="Delete market data tables (prices/dividends/data_gaps/halts)",
        )
        x.add_argument(
            "--wipe-universe",
            action="store_true",
            help="Delete universes/universe_membership/ticker_mappings",
        )
        x.add_argument(
            "--db-reset",
            action="store_true",
            help="Replace the DB file (it will be backed up first) and re-run migrations",
        )
        x.add_argument(
            "--yes",
            action="store_true",
            help="Actually perform destructive actions (otherwise dry-run)",
        )

    d = sub.add_parser("doctor", help="Show what would be deleted (dry-run)")
    _add_common(d)

    r = sub.add_parser("reset", help="Perform reset (requires --yes)")
    _add_common(r)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    root = ensure_sys_path()
    args = build_parser().parse_args(argv if argv is not None else sys.argv[1:])

    db_path = normalize_db_path(root, args.db)

    dry_run = True
    if args.command == "reset" and args.yes:
        dry_run = False

    # Default purge choices (conservative): clean audit + news-alpha rows + sentiment cache.
    wipe_audit = bool(args.wipe_audit) or True
    wipe_news_alpha = bool(args.wipe_news_alpha) or True
    wipe_sentiment_cache = bool(args.wipe_sentiment_cache) or True

    # The optional wipes remain opt-in.
    wipe_prices = bool(args.wipe_prices)
    wipe_universe = bool(args.wipe_universe)

    lines: List[str] = []
    lines.append(f"- command: {args.command}")
    lines.append(f"- scope: {args.scope}")
    lines.append(f"- dry_run: {dry_run}")
    lines.append(f"- db: {db_path}")
    lines.append(f"- db_reset: {bool(args.db_reset)}")
    lines.append(f"- purge_history_raw: {bool(args.purge_history_raw)}")
    lines.append(f"- db_wipes: audit={wipe_audit}, news_alpha={wipe_news_alpha}, sentiment_cache={wipe_sentiment_cache}, prices={wipe_prices}, universe={wipe_universe}")

    # 1) Filesystem purge
    fs = purge_filesystem(
        root=root,
        scope=args.scope,
        purge_history_raw=bool(args.purge_history_raw),
        dry_run=dry_run,
    )

    lines.append("")
    lines.append("## Filesystem purge")
    lines.append(f"- items_deleted: {fs.files_deleted} (approx; includes files and subtrees)")
    for n in fs.notes:
        lines.append(f"- {n}")

    # 2) DB init/reset
    lines.append("")
    lines.append("## Database")

    if args.db_reset:
        if dry_run:
            lines.append(f"- [DRY] Would backup and delete DB file: {db_path}")
        else:
            if db_path.exists():
                bak = db_path.with_suffix(db_path.suffix + f".bak_{utc_stamp()}")
                shutil.copy2(db_path, bak)
                lines.append(f"- backed up DB -> {bak}")
                db_path.unlink()
                lines.append("- deleted DB file")
            else:
                lines.append("- DB did not exist; will be created")

    # Always run migrations (idempotent). In dry-run we just report.
    if dry_run:
        lines.append(f"- [DRY] Would run migrations: <PY> -m src.db.migrate --db {db_path}")
    else:
        _run_migrate(root, db_path)
        lines.append("- migrations applied")

    # 3) DB purge (tables)
    db_report = purge_db(
        db_path=db_path,
        firm=str(args.firm),
        model=str(args.model),
        wipe_audit=wipe_audit,
        wipe_news_alpha=wipe_news_alpha,
        wipe_sentiment_cache=wipe_sentiment_cache,
        wipe_prices=wipe_prices,
        wipe_universe=wipe_universe,
        dry_run=dry_run,
    )

    if db_report.actions:
        for a in db_report.actions:
            lines.append(f"- {a}")
    else:
        lines.append("- no DB actions")

    # Transcript
    title = "OPS Reset Transcript"
    transcript_path = write_transcript(root, title=title, lines=lines)

    print("\n[ops_reset] Done")
    print(f"[ops_reset] transcript: {transcript_path.resolve()}")

    if args.command == "reset" and not args.yes:
        print("\n[ops_reset] NOTE: reset requires --yes to perform deletions; ran in dry-run mode.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
