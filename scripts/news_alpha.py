"""NEWS-ALPHA operator runner.

This is a thin, self-contained entrypoint intended for day-to-day operation.

Design goals:
- Offline-by-default.
- Deterministic and audit-friendly (no implicit network).
- No schema ownership; schema lives in src/db/migrate.py.

Commands:
- collect : generate JSONL fixtures from Google News RSS (offline-parse by default; online is guarded)
- run     : consume fixtures and write NEWS-ALPHA rows into DuckDB (recs + sentiment_cache)
- status  : show a small operational summary from the DB and latest artifacts

Online posture:
- Online actions require BOTH:
  - passing --online
  - setting NEWS_ALPHA_ALLOW_ONLINE=1 (or passing --allow-online in this runner)

This runner intentionally does not modify scripts/sentinel.py; it is a parallel lane.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

import zipfile

from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def ensure_sys_path() -> Path:
    """Ensure project root is on sys.path even when invoked from scripts/."""

    root = Path(__file__).resolve().parents[1]
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root


def _load_local_env(root: Path) -> None:
    """Load config/sentinel.local.env if present (shell-agnostic)."""

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
        return


def normalize_db_path(root: Path, db_path: str) -> str:
    p = Path(db_path)
    if not p.is_absolute():
        p = root / p
    return str(p.resolve())


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="news_alpha", description="NEWS-ALPHA operator runner")

    sub = p.add_subparsers(dest="command", required=True)

    # Common
    def _add_common(x: argparse.ArgumentParser) -> None:
        x.add_argument(
            "--db",
            default=os.environ.get("SENTINEL_ALPHA_DB_PATH", "data/sentinel_alpha.db"),
            help="Path to DuckDB database (default: data/sentinel_alpha.db)",
        )
        x.add_argument(
            "--universe-id",
            default=os.environ.get("SENTINEL_UNIVERSE_ID", "ALL"),
            help="Universe id (default: ALL)",
        )
        x.add_argument(
            "--allow-online",
            action="store_true",
            help="Set NEWS_ALPHA_ALLOW_ONLINE=1 for this invocation (still requires --online)",
        )

    # collect
    c = sub.add_parser("collect", help="Collect Google News RSS into JSONL fixtures")
    _add_common(c)
    c.add_argument("--date-from", required=True, help="YYYY-MM-DD (inclusive)")
    c.add_argument("--date-to", required=True, help="YYYY-MM-DD (inclusive)")
    c.add_argument("--when-days", type=int, default=14, help="Google News query window in days")
    c.add_argument("--domains", action="append", default=[], help="Allowed source domains (repeatable)")
    c.add_argument(
        "--raw-dir",
        default="reports/news_alpha/raw/rss",
        help="Directory for raw RSS XML files (default: reports/news_alpha/raw/rss)",
    )
    c.add_argument(
        "--out-fixtures",
        default="",
        help="Output JSONL fixtures path (default: reports/news_alpha/collector/collector_<ts>.jsonl)",
    )
    c.add_argument(
        "--stats-file",
        default="",
        help="Output stats JSON path (default: reports/news_alpha/collector/collector_<ts>_stats.json)",
    )
    c.add_argument("--offline-parse", action="store_true", help="Parse existing raw XML files")
    c.add_argument("--online", action="store_true", help="Fetch RSS from the network (guarded)")
    c.add_argument(
        "--strict-dq",
        action="store_true",
        help="Fail (rc=2) if the collector produces zero kept items (data-quality gate)",
    )

    # run
    r = sub.add_parser("run", help="Consume fixtures and write recs/sentiment_cache")
    _add_common(r)
    r.add_argument("--date-from", required=True, help="YYYY-MM-DD (inclusive)")
    r.add_argument("--date-to", required=True, help="YYYY-MM-DD (inclusive)")
    r.add_argument("--fixtures", required=True, help="Path to JSONL fixtures")
    r.add_argument("--dry-run", action="store_true", help="Do not write to DB")
    r.add_argument("--overwrite", action="store_true", help="Overwrite existing firm rows in date range")
    r.add_argument("--online", action="store_true", help="Enable online mode (guarded; v0.1 fixtures only)")
    r.add_argument(
        "--rejects-file",
        default="",
        help="Optional rejects JSONL path (default: reports/news_alpha/rejects_<ts>.jsonl)",
    )
    r.add_argument(
        "--log-file",
        default="",
        help="Optional log file path (default: reports/news_alpha/news_alpha_<ts>.log)",
    )
    r.add_argument("--log-json", action="store_true", help="Emit JSONL logs")
    r.add_argument("--log-level", default="INFO", help="DEBUG|INFO|WARNING|ERROR")

    # status
    s = sub.add_parser("status", help="Show operational summary")
    _add_common(s)
    s.add_argument("--limit", type=int, default=25, help="Max rows to show")

    # history (GDELT)
    h = sub.add_parser("history", help="GDELT history lane utilities (download/profile/fixtures)")
    _add_common(h)
    hsub = h.add_subparsers(dest="history_cmd", required=True)

    # history download
    hd = hsub.add_parser("download", help="Download GDELT daily bulk raw zips (idempotent)")
    hd.add_argument("--stream", required=True, choices=["events", "gkg", "both"], help="events|gkg|both")
    hd.add_argument("--date-from", required=True, help="YYYY-MM-DD (inclusive)")
    hd.add_argument("--date-to", required=True, help="YYYY-MM-DD (inclusive)")
    hd.add_argument(
        "--raw-dir",
        default="data/news_alpha/history/gdelt1",
        help="History root (default: data/news_alpha/history/gdelt1)",
    )
    hd.add_argument("--max-retries", type=int, default=2, help="Max retries per file")
    hd.add_argument("--timeout", type=int, default=60, help="HTTP timeout seconds")
    hd.add_argument(
        "--with-gkgcounts",
        action="store_true",
        help="Also download daily gkgcounts files (if available)",
    )
    hd.add_argument("--online", action="store_true", help="Fetch from the network (guarded)")

    # history profile
    hp = hsub.add_parser("profile", help="Profile raw history (census) to guide FilterSpec")
    hp.add_argument("--stream", required=True, choices=["events", "gkg", "both"], help="events|gkg|both")
    hp.add_argument("--date-from", required=True, help="YYYY-MM-DD (inclusive)")
    hp.add_argument("--date-to", required=True, help="YYYY-MM-DD (inclusive)")
    hp.add_argument(
        "--raw-dir",
        default="data/news_alpha/history/gdelt1",
        help="History root (default: data/news_alpha/history/gdelt1)",
    )
    hp.add_argument(
        "--out",
        default="reports/news_alpha/profile",
        help="Output root (default: reports/news_alpha/profile)",
    )
    hp.add_argument("--top-n", type=int, default=50, help="Top-N items in the census tables")

    # history fixtures
    hf = hsub.add_parser("fixtures", help="Build fixtures JSONL applying FilterSpec + entity map")
    hf.add_argument("--stream", required=True, choices=["events", "gkg", "both"], help="events|gkg|both")
    hf.add_argument("--date-from", required=True, help="YYYY-MM-DD (inclusive)")
    hf.add_argument("--date-to", required=True, help="YYYY-MM-DD (inclusive)")
    hf.add_argument(
        "--raw-dir",
        default="data/news_alpha/history/gdelt1",
        help="History root (default: data/news_alpha/history/gdelt1)",
    )
    hf.add_argument(
        "--filter-spec",
        default="config/news_alpha/gdelt_filter_spec.json",
        help="Filter spec JSON (default: config/news_alpha/gdelt_filter_spec.json)",
    )
    hf.add_argument(
        "--entity-map",
        default="config/news_alpha/entity_ticker_map.csv",
        help="Entity→ticker map CSV (default: config/news_alpha/entity_ticker_map.csv)",
    )
    hf.add_argument(
        "--out",
        default="data/news_alpha/history/gdelt1/fixtures",
        help="Output fixtures root (default: data/news_alpha/history/gdelt1/fixtures)",
    )
    hf.add_argument("--limit-per-day", type=int, default=0, help="Optional cap on emitted rows per day (0=unlimited)")
    hf.add_argument(
        "--keep-unmapped",
        action="store_true",
        help="Keep records with no matched tickers (default: drop)",
    )
    hf.add_argument(
        "--merge",
        action="store_true",
        help="Also write merged fixtures under fixtures/merged when stream=both",
    )

    return p


def _maybe_enable_online(args: argparse.Namespace) -> None:
    if getattr(args, "allow_online", False):
        os.environ["NEWS_ALPHA_ALLOW_ONLINE"] = "1"


def cmd_collect(root: Path, args: argparse.Namespace) -> int:
    from src.news_alpha.collect_google_news_rss import main as collector_main

    ts = _utc_stamp()
    out_fixtures = args.out_fixtures.strip() or f"reports/news_alpha/collector/collector_{ts}.jsonl"
    stats_file = args.stats_file.strip() or f"reports/news_alpha/collector/collector_{ts}_stats.json"

    argv = [
        "--db",
        args.db,
        "--universe-id",
        args.universe_id,
        "--date-from",
        args.date_from,
        "--date-to",
        args.date_to,
        "--when-days",
        str(int(args.when_days)),
        "--raw-dir",
        args.raw_dir,
        "--out-fixtures",
        out_fixtures,
        "--stats-file",
        stats_file,
    ]

    for d in (args.domains or []):
        if (d or "").strip():
            argv += ["--domains", d.strip()]

    if args.offline_parse:
        argv += ["--offline-parse"]
    if args.online:
        argv += ["--online"]

    rc = int(collector_main(argv) or 0)

    print(f"[news_alpha] collect rc={rc}")
    print(f"[news_alpha] fixtures={Path(out_fixtures).resolve()}")
    print(f"[news_alpha] stats={Path(stats_file).resolve()}")

    # Data-quality summary (offline-first, so empty output can be legitimate).
    try:
        import json as _json

        st = _json.loads(Path(stats_file).read_text(encoding="utf-8"))
        kept = int(st.get("items_kept", 0))
        raw = int(st.get("items_raw", 0))
        tick_req = int(st.get("tickers_requested", 0))
        tick_raw = int(st.get("tickers_with_raw", 0))
        missing = int(st.get("raw_files_missing", 0))

        if kept == 0 and tick_req > 0:
            reason = "no items in range/filters"
            if tick_raw == 0 and raw == 0:
                reason = "no raw XML found for requested tickers"
            elif raw > 0 and kept == 0:
                reason = "all items filtered (date/domains)"
            print(f"[news_alpha][DQ] WARNING: items_kept=0 (raw={raw}, tickers_with_raw={tick_raw}, missing_raw={missing}) -> {reason}")
            if getattr(args, "strict_dq", False):
                return 2
    except Exception:
        # Never block operation due to stats parsing.
        if getattr(args, "strict_dq", False):
            return 2

    return rc


def cmd_run(root: Path, args: argparse.Namespace) -> int:
    from src.news_alpha.run import main as run_main

    ts = _utc_stamp()
    rejects_file = args.rejects_file.strip() or f"reports/news_alpha/rejects_{ts}.jsonl"
    log_file = args.log_file.strip() or f"reports/news_alpha/news_alpha_{ts}.log"

    argv = [
        "--db",
        args.db,
        "--universe-id",
        args.universe_id,
        "--date-from",
        args.date_from,
        "--date-to",
        args.date_to,
        "--provider",
        "fixtures",
        "--fixtures",
        args.fixtures,
        "--log-level",
        args.log_level,
        "--log-file",
        log_file,
        "--rejects-file",
        rejects_file,
    ]

    if args.log_json:
        argv += ["--log-json"]
    if args.dry_run:
        argv += ["--dry-run"]
    if args.overwrite:
        argv += ["--overwrite"]
    if args.online:
        argv += ["--online"]

    rc = int(run_main(argv) or 0)

    print(f"[news_alpha] run rc={rc}")
    print(f"[news_alpha] log_file={Path(log_file).resolve()}")
    print(f"[news_alpha] rejects_file={Path(rejects_file).resolve()}")
    return rc


def cmd_status(root: Path, args: argparse.Namespace) -> int:
    import duckdb

    db_path = args.db
    limit = int(args.limit)
    firm = "NEWS-ALPHA"

    def _latest(glob_pat: str) -> Path | None:
        rep = root / "reports" / "news_alpha"
        if not rep.exists():
            return None
        files = list(rep.glob(glob_pat))
        if not files:
            return None
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return files[0]

    latest_fixture = _latest("collector/*.jsonl")
    latest_stats = _latest("collector/*_stats.json")
    latest_log = _latest("news_alpha_*.log*")
    latest_rejects = _latest("rejects_*.jsonl")

    print("SENTINEL-ALPHA | NEWS-ALPHA status")
    print(f"db={Path(db_path).resolve()}")
    print(f"universe_id={args.universe_id}")
    print(f"latest_fixture={str(latest_fixture) if latest_fixture else '(none)'}")
    print(f"latest_stats={str(latest_stats) if latest_stats else '(none)'}")
    print(f"latest_log={str(latest_log) if latest_log else '(none)'}")
    print(f"latest_rejects={str(latest_rejects) if latest_rejects else '(none)'}")

    con = duckdb.connect(db_path, read_only=False)
    try:
        # Counters
        recs_cnt = int(con.execute("SELECT COUNT(*) FROM recs WHERE firm = ?", [firm]).fetchone()[0])
        cache_cnt = int(con.execute("SELECT COUNT(*) FROM sentiment_cache WHERE model = 'lexicon-v1'").fetchone()[0])
        print(f"recs_rows_firm={recs_cnt}")
        print(f"sentiment_cache_rows_model=lexicon-v1 count={cache_cnt}")

        rows = con.execute(
            """
            SELECT date, ticker, rating, sentiment_score, headline
            FROM recs
            WHERE firm = ?
            ORDER BY date DESC, ticker ASC
            LIMIT ?
            """,
            [firm, limit],
        ).fetchall()
        if rows:
            print("\nLatest recs:")
            for d, t, rating, sc, hl in rows:
                hl_s = (hl or "").replace("\n", " ")
                if len(hl_s) > 120:
                    hl_s = hl_s[:117] + "..."
                print(f"- {d} | {t} | {rating} | score={float(sc):+.3f} | {hl_s}")
        else:
            print("\n(no NEWS-ALPHA rows in recs)")
    finally:
        try:
            con.close()
        except Exception:
            pass

    return 0


# -------------------------------
# History lane (GDELT daily bulk)
# -------------------------------


def _parse_ymd(s: str) -> date:
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d").date()
    except Exception as e:
        raise ValueError(f"Invalid date '{s}'. Expected YYYY-MM-DD") from e


def _iter_days(d0: date, d1: date) -> Iterator[date]:
    if d1 < d0:
        raise ValueError("date-to must be >= date-from")
    cur = d0
    while cur <= d1:
        yield cur
        cur = cur + timedelta(days=1)


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_json(path: Path, obj: Any) -> None:
    _ensure_dir(path.parent)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _iso_day(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")



def _gdelt_base() -> str:
    # Default to HTTP because some environments/proxies break HTTPS to data.gdeltproject.org.
    # Override with NEWS_ALPHA_GDELT_BASE (e.g., https://data.gdeltproject.org) if needed.
    return os.environ.get('NEWS_ALPHA_GDELT_BASE', 'http://data.gdeltproject.org').rstrip('/')


def _gdelt_events_url(yyyymmdd: str) -> str:
    # Daily GDELT event bulk files: https://data.gdeltproject.org/events/index.html
    return f"{_gdelt_base()}/events/{yyyymmdd}.export.CSV.zip"


def _gdelt_gkg_url(yyyymmdd: str) -> str:
    # Daily GKG bulk files: https://data.gdeltproject.org/gkg/index.html
    return f"{_gdelt_base()}/gkg/{yyyymmdd}.gkg.csv.zip"


def _gdelt_gkgcounts_url(yyyymmdd: str) -> str:
    return f"{_gdelt_base()}/gkg/{yyyymmdd}.gkgcounts.csv.zip"



def _candidate_urls(url: str) -> List[str]:
    # Try the given URL first; if it is http/https, add the alternate scheme as fallback.
    # This helps in environments where HTTPS interception breaks certificate validation,
    # or where HTTPS returns transient 502/503 while HTTP succeeds.
    if url.startswith('https://'):
        alt = 'http://' + url[len('https://'):]
        return [url, alt]
    if url.startswith('http://'):
        alt = 'https://' + url[len('http://'):]
        return [url, alt]
    return [url]


def _download_binary(url: str, timeout_s: int) -> bytes:
    req = Request(url, headers={"User-Agent": "NEWS-ALPHA/0.2 (history lane)"})
    with urlopen(req, timeout=timeout_s) as resp:
        return resp.read()


def _download_to_file(url: str, dest: Path, max_retries: int, timeout_s: int) -> Tuple[str, Optional[int], Optional[str], str]:
    """Download URL to dest atomically.

    Returns (status, http_status, error_message)
      - status in {downloaded, missing, error}

    Notes:
      - We try the provided URL first, then (if applicable) retry once with the alternate scheme
        (http<->https). This is pragmatic for corporate proxies / TLS interception scenarios.
    """

    _ensure_dir(dest.parent)
    tmp = dest.with_suffix(dest.suffix + ".part")
    if tmp.exists():
        try:
            tmp.unlink()
        except Exception:
            pass

    last_err: Optional[str] = None

    for cand_url in _candidate_urls(url):
        # For each candidate URL, retry with backoff.
        for attempt in range(1, max_retries + 1):
            try:
                blob = _download_binary(cand_url, timeout_s=timeout_s)
                tmp.write_bytes(blob)
                tmp.replace(dest)
                return ("downloaded", 200, None, cand_url)
            except HTTPError as e:
                code = int(getattr(e, "code", 0) or 0)
                if code == 404:
                    return ("missing", 404, "not_found", cand_url)
                last_err = f"HTTPError {getattr(e, 'code', '?')}: {e}"
                # If it is a transient gateway error, try the alternate scheme (if any)
                if code in (502, 503, 504):
                    break
            except URLError as e:
                last_err = f"URLError: {e}"
                # Commonly happens with TLS interception or DNS issues; try alternate scheme.
                break
            except Exception as e:
                last_err = f"{type(e).__name__}: {e}"

            # Backoff
            if attempt < max_retries:
                time.sleep(min(2 ** attempt, 8))

    return ("error", None, last_err or "unknown_error", url)


def _history_root(raw_dir: str) -> Path:
    return Path(raw_dir)


def _manifest_path(hist_root: Path, stream: str, d0: date, d1: date) -> Path:
    return hist_root / "manifests" / f"manifest_{stream}_{d0.strftime('%Y%m%d')}_{d1.strftime('%Y%m%d')}.json"


def _events_dest(hist_root: Path, yyyymmdd: str) -> Path:
    yyyy = yyyymmdd[:4]
    return hist_root / "events" / "raw" / yyyy / f"{yyyymmdd}.export.CSV.zip"


def _gkg_dest(hist_root: Path, yyyymmdd: str) -> Path:
    yyyy = yyyymmdd[:4]
    return hist_root / "gkg" / "raw" / yyyy / f"{yyyymmdd}.gkg.csv.zip"


def _gkgcounts_dest(hist_root: Path, yyyymmdd: str) -> Path:
    yyyy = yyyymmdd[:4]
    return hist_root / "gkg" / "raw" / yyyy / f"{yyyymmdd}.gkgcounts.csv.zip"


def _guard_online(online_flag: bool) -> None:
    if not online_flag:
        raise RuntimeError("This command requires --online")
    if os.environ.get("NEWS_ALPHA_ALLOW_ONLINE", "0") != "1":
        raise RuntimeError("Online actions require NEWS_ALPHA_ALLOW_ONLINE=1 (or pass --allow-online)")


def cmd_history(root: Path, args: argparse.Namespace) -> int:
    cmd = getattr(args, "history_cmd", "")
    if cmd == "download":
        return cmd_history_download(args)
    if cmd == "profile":
        return cmd_history_profile(args)
    if cmd == "fixtures":
        return cmd_history_fixtures(args)
    print("Unknown history subcommand")
    return 2


def cmd_history_download(args: argparse.Namespace) -> int:
    _guard_online(bool(args.online))

    hist_root = _history_root(str(args.raw_dir))
    d0 = _parse_ymd(args.date_from)
    d1 = _parse_ymd(args.date_to)

    streams: List[str]
    if args.stream == "both":
        streams = ["events", "gkg"]
    else:
        streams = [args.stream]

    results: Dict[str, Any] = {
        "manifest_version": "v1",
        "provider": "gdelt1",
        "generated_at_utc": _utc_iso_now(),
        "date_from": _iso_day(d0),
        "date_to": _iso_day(d1),
        "streams": streams,
        "entries": [],
    }

    for d in _iter_days(d0, d1):
        yyyymmdd = d.strftime("%Y%m%d")
        for stream in streams:
            if stream == "events":
                url = _gdelt_events_url(yyyymmdd)
                dest = _events_dest(hist_root, yyyymmdd)
                kind = "events"
                to_fetch = [(kind, url, dest)]
            else:
                # gkg
                to_fetch = [("gkg", _gdelt_gkg_url(yyyymmdd), _gkg_dest(hist_root, yyyymmdd))]
                if bool(getattr(args, "with_gkgcounts", False)):
                    to_fetch.append(("gkgcounts", _gdelt_gkgcounts_url(yyyymmdd), _gkgcounts_dest(hist_root, yyyymmdd)))

            for kind, url, dest in to_fetch:
                entry: Dict[str, Any] = {
                    "date": _iso_day(d),
                    "yyyymmdd": yyyymmdd,
                    "stream": stream,
                    "kind": kind,
                    "url": url,
                    "dest": str(dest.as_posix()),
                }

                if dest.exists() and dest.stat().st_size > 0:
                    entry["status"] = "exists"
                    entry["bytes"] = int(dest.stat().st_size)
                    entry["sha256"] = _sha256_file(dest)
                    results["entries"].append(entry)
                    continue

                status, http_status, err, effective_url = _download_to_file(
                    url=url,
                    dest=dest,
                    max_retries=int(args.max_retries),
                    timeout_s=int(args.timeout),
                )
                entry["status"] = status
                if effective_url and effective_url != url:
                    entry["url_effective"] = effective_url
                if http_status is not None:
                    entry["http_status"] = int(http_status)
                if err:
                    entry["error"] = err

                if status == "downloaded" and dest.exists() and dest.stat().st_size > 0:
                    entry["bytes"] = int(dest.stat().st_size)
                    entry["sha256"] = _sha256_file(dest)
                results["entries"].append(entry)

    # Write one manifest per stream requested (events/gkg) for convenience.
    # (gkgcounts are included under stream=gkg)
    for stream in streams:
        manifest = dict(results)
        manifest["stream"] = stream
        manifest["entries"] = [e for e in results["entries"] if e.get("stream") == stream]
        mp = _manifest_path(hist_root, stream, d0, d1)
        _write_json(mp, manifest)
        print(f"Wrote manifest: {mp}")

    # Console summary
    cnts: Dict[str, int] = {"downloaded": 0, "exists": 0, "missing": 0, "error": 0}
    for e in results["entries"]:
        st = str(e.get("status") or "")
        if st in cnts:
            cnts[st] += 1
    print(f"Summary: downloaded={cnts['downloaded']} exists={cnts['exists']} missing={cnts['missing']} error={cnts['error']}")

    if cnts['error'] > 0:
        # Print up to first 5 errors to aid debugging without overwhelming logs.
        shown = 0
        print('First errors:')
        for e in results['entries']:
            if str(e.get('status')) != 'error':
                continue
            msg = e.get('error') or ''
            url = e.get('url') or ''
            kind = e.get('kind') or e.get('stream')
            day = e.get('date') or e.get('yyyymmdd')
            print(f"  - {day} {kind}: {msg} ({url})")
            shown += 1
            if shown >= 5:
                break
    return 0 if cnts["error"] == 0 else 2


def _iter_zip_tsv_rows(zip_path: Path) -> Iterator[List[str]]:
    with zipfile.ZipFile(zip_path, "r") as z:
        # Usually a single file; pick the first non-directory member.
        members = [m for m in z.namelist() if not m.endswith("/")]
        if not members:
            return
        name = members[0]
        with z.open(name, "r") as f:
            wrapper = io.TextIOWrapper(f, encoding="utf-8", errors="replace")
            reader = csv.reader(wrapper, delimiter="\t")
            for row in reader:
                if not row:
                    continue
                yield row


def _norm_text(s: str, strip_punct: bool = True, lowercase: bool = True) -> str:
    t = (s or "").strip()
    if lowercase:
        t = t.lower()
    if strip_punct:
        t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t, flags=re.UNICODE).strip()
    return t


def _safe_domain(url: str) -> str:
    try:
        u = urlparse(url)
        return (u.netloc or "").lower()
    except Exception:
        return ""


def _parse_float(s: str) -> float:
    try:
        return float(str(s).strip())
    except Exception:
        return 0.0


def _parse_gkg_tone(field: str) -> float:
    # GKG tone often encodes multiple comma-delimited stats. We keep the first (avg tone).
    if not isinstance(field, str):
        return 0.0
    parts = [p.strip() for p in field.split(",") if p.strip()]
    if not parts:
        return 0.0
    return _parse_float(parts[0])


def _split_gkg_list(field: str) -> List[str]:
    if not isinstance(field, str) or not field.strip():
        return []
    out: List[str] = []
    for token in field.split(";"):
        t = token.strip()
        if not t:
            continue
        # Common patterns: NAME,1 or 1#Name#CC#...
        if "#" in t:
            parts = [p.strip() for p in t.split("#") if p.strip()]
            if len(parts) >= 2:
                out.append(parts[1])
                continue
        if "," in t:
            out.append(t.split(",", 1)[0].strip())
        else:
            out.append(t)
    return [x for x in out if x.strip()]


class _EntityRule:
    __slots__ = ("entity_raw", "entity_norm", "ticker", "match_type", "priority", "start_date", "end_date")

    def __init__(
        self,
        entity_raw: str,
        entity_norm: str,
        ticker: str,
        match_type: str,
        priority: int,
        start_date: Optional[date],
        end_date: Optional[date],
    ) -> None:
        self.entity_raw = entity_raw
        self.entity_norm = entity_norm
        self.ticker = ticker
        self.match_type = match_type
        self.priority = priority
        self.start_date = start_date
        self.end_date = end_date


def _parse_optional_date(s: str) -> Optional[date]:
    t = (s or "").strip()
    if not t:
        return None
    return _parse_ymd(t)


def _load_entity_map(path: str) -> List[_EntityRule]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))
    rules: List[_EntityRule] = []
    with p.open("r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            if str(row[0]).strip().startswith("#"):
                continue
            # Skip header (common in CSV templates)
            if (str(row[0]).strip().lower() == "entity_raw") and (len(row) > 2 and str(row[2]).strip().lower() == "ticker"):
                continue
            # entity_raw,entity_norm,ticker,match_type,priority,start_date,end_date,notes
            entity_raw = (row[0] if len(row) > 0 else "").strip().strip('"')
            entity_norm = (row[1] if len(row) > 1 else "").strip().strip('"')
            ticker = (row[2] if len(row) > 2 else "").strip()
            match_type = (row[3] if len(row) > 3 else "EXACT").strip().upper() or "EXACT"
            prio = int((row[4] if len(row) > 4 else "0") or 0)
            start_d = _parse_optional_date(row[5] if len(row) > 5 else "")
            end_d = _parse_optional_date(row[6] if len(row) > 6 else "")

            if not ticker or not entity_raw:
                continue
            if not entity_norm:
                entity_norm = _norm_text(entity_raw)
            rules.append(_EntityRule(entity_raw, entity_norm, ticker, match_type, prio, start_d, end_d))

    # Highest priority first.
    rules.sort(key=lambda r: (-int(r.priority), r.entity_norm, r.ticker))
    return rules


def _rule_active(rule: _EntityRule, d: date) -> bool:
    if rule.start_date and d < rule.start_date:
        return False
    if rule.end_date and d > rule.end_date:
        return False
    return True


def _match_tickers(
    candidates: Iterable[str],
    rules: List[_EntityRule],
    d: date,
    strip_punct: bool = True,
    lowercase: bool = True,
) -> List[str]:
    ticks: List[str] = []
    seen: set[str] = set()
    cand_norms = [(c, _norm_text(c, strip_punct=strip_punct, lowercase=lowercase)) for c in candidates if str(c).strip()]

    for raw, norm in cand_norms:
        for rule in rules:
            if not _rule_active(rule, d):
                continue
            if rule.match_type == "EXACT":
                if norm == rule.entity_norm:
                    if rule.ticker not in seen:
                        ticks.append(rule.ticker)
                        seen.add(rule.ticker)
            elif rule.match_type == "CONTAINS":
                if rule.entity_norm and rule.entity_norm in norm:
                    if rule.ticker not in seen:
                        ticks.append(rule.ticker)
                        seen.add(rule.ticker)
            elif rule.match_type == "REGEX":
                try:
                    if re.search(rule.entity_raw, raw, flags=re.IGNORECASE):
                        if rule.ticker not in seen:
                            ticks.append(rule.ticker)
                            seen.add(rule.ticker)
                except re.error:
                    continue

    ticks.sort()
    return ticks


def _load_filter_spec(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))
    obj = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("Filter spec must be a JSON object")
    return obj


def _events_pass_filter(row: List[str], spec: Dict[str, Any], domain: str, avg_tone: float) -> bool:
    ev = spec.get("events") if isinstance(spec.get("events"), dict) else {}
    codes_inc = set(str(x).strip() for x in (ev.get("include_event_codes") or []) if str(x).strip())
    root_inc = set(str(x).strip() for x in (ev.get("include_root_event_codes") or []) if str(x).strip())
    codes_exc = set(str(x).strip() for x in (ev.get("exclude_event_codes") or []) if str(x).strip())
    actor_inc = [str(x).strip() for x in (ev.get("include_actor_names") or []) if str(x).strip()]
    actor_exc = [str(x).strip() for x in (ev.get("exclude_actor_names") or []) if str(x).strip()]
    dom_inc = set(str(x).strip().lower() for x in (ev.get("include_domains") or []) if str(x).strip())
    dom_exc = set(str(x).strip().lower() for x in (ev.get("exclude_domains") or []) if str(x).strip())

    # Heuristic indices for GDELT 1.0 Event daily export.
    ev_code = row[26].strip() if len(row) > 26 else ""
    root_code = row[28].strip() if len(row) > 28 else ""
    actor1 = row[6].strip() if len(row) > 6 else ""
    actor2 = row[16].strip() if len(row) > 16 else ""

    if ev_code and ev_code in codes_exc:
        return False
    if codes_inc and ev_code not in codes_inc:
        return False
    if root_inc and root_code not in root_inc:
        return False

    if dom_exc and domain and domain in dom_exc:
        return False
    if dom_inc and (not domain or domain not in dom_inc):
        return False

    if actor_inc:
        hay = f"{actor1} {actor2}".lower()
        if not any(a.lower() in hay for a in actor_inc):
            return False
    if actor_exc:
        hay = f"{actor1} {actor2}".lower()
        if any(a.lower() in hay for a in actor_exc):
            return False

    tone_spec = ev.get("tone") if isinstance(ev.get("tone"), dict) else {}
    min_abs = float(tone_spec.get("min_abs_tone") or 0.0)
    if min_abs > 0.0 and abs(float(avg_tone)) < min_abs:
        return False

    return True


def _any_match(hay: List[str], needles: List[str]) -> bool:
    if not needles:
        return True
    if not hay:
        return False
    hay_l = [h.lower() for h in hay if str(h).strip()]
    needles_l = [n.lower() for n in needles if str(n).strip()]
    for n in needles_l:
        if any(n in h for h in hay_l):
            return True
    return False


def _any_forbidden(hay: List[str], forb: List[str]) -> bool:
    if not forb or not hay:
        return False
    hay_l = [h.lower() for h in hay if str(h).strip()]
    forb_l = [f.lower() for f in forb if str(f).strip()]
    for f in forb_l:
        if any(f in h for h in hay_l):
            return True
    return False


def _gkg_pass_filter(themes: List[str], persons: List[str], orgs: List[str], locs: List[str], spec: Dict[str, Any]) -> bool:
    g = spec.get("gkg") if isinstance(spec.get("gkg"), dict) else {}

    inc_themes = [str(x).strip() for x in (g.get("include_themes") or []) if str(x).strip()]
    exc_themes = [str(x).strip() for x in (g.get("exclude_themes") or []) if str(x).strip()]
    if _any_forbidden(themes, exc_themes):
        return False
    if inc_themes and not _any_match(themes, inc_themes):
        return False

    inc_p = [str(x).strip() for x in (g.get("include_persons") or []) if str(x).strip()]
    exc_p = [str(x).strip() for x in (g.get("exclude_persons") or []) if str(x).strip()]
    if _any_forbidden(persons, exc_p):
        return False
    if inc_p and not _any_match(persons, inc_p):
        return False

    inc_o = [str(x).strip() for x in (g.get("include_organizations") or []) if str(x).strip()]
    exc_o = [str(x).strip() for x in (g.get("exclude_organizations") or []) if str(x).strip()]
    if _any_forbidden(orgs, exc_o):
        return False
    if inc_o and not _any_match(orgs, inc_o):
        return False

    inc_l = [str(x).strip() for x in (g.get("include_locations") or []) if str(x).strip()]
    exc_l = [str(x).strip() for x in (g.get("exclude_locations") or []) if str(x).strip()]
    if _any_forbidden(locs, exc_l):
        return False
    if inc_l and not _any_match(locs, inc_l):
        return False

    return True


def cmd_history_fixtures(args: argparse.Namespace) -> int:
    hist_root = _history_root(str(args.raw_dir))
    d0 = _parse_ymd(args.date_from)
    d1 = _parse_ymd(args.date_to)
    spec = _load_filter_spec(str(args.filter_spec))
    rules = _load_entity_map(str(args.entity_map))
    out_root = Path(str(args.out))

    norm_cfg = spec.get("normalization") if isinstance(spec.get("normalization"), dict) else {}
    lowercase = bool(norm_cfg.get("lowercase", True))
    strip_punct = bool(norm_cfg.get("strip_punctuation", True))

    streams = [args.stream] if args.stream != "both" else ["events", "gkg"]
    if args.stream == "both" and bool(getattr(args, "merge", False)):
        _ensure_dir(out_root / "merged")

    emitted_total = 0
    kept_total = 0
    dropped_unmapped = 0
    missing_raw = 0

    for d in _iter_days(d0, d1):
        yyyymmdd = d.strftime("%Y%m%d")
        day_items_by_stream: Dict[str, List[Dict[str, Any]]] = {}

        for stream in streams:
            items: List[Dict[str, Any]] = []
            if stream == "events":
                zp = _events_dest(hist_root, yyyymmdd)
                if not zp.exists():
                    missing_raw += 1
                    day_items_by_stream[stream] = []
                    continue
                for row in _iter_zip_tsv_rows(zp):
                    # SQLDATE (YYYYMMDD) at idx 1
                    sql = row[1].strip() if len(row) > 1 else yyyymmdd
                    url = row[-1].strip() if row else ""
                    domain = _safe_domain(url)
                    avg_tone = _parse_float(row[34]) if len(row) > 34 else 0.0
                    if not _events_pass_filter(row, spec, domain=domain, avg_tone=avg_tone):
                        continue

                    actor1 = row[6].strip() if len(row) > 6 else ""
                    actor2 = row[16].strip() if len(row) > 16 else ""
                    ev_code = row[26].strip() if len(row) > 26 else ""
                    root_code = row[28].strip() if len(row) > 28 else ""

                    ticks = _match_tickers(
                        candidates=[actor1, actor2],
                        rules=rules,
                        d=d,
                        strip_punct=strip_punct,
                        lowercase=lowercase,
                    )

                    emitted_total += 1
                    if not ticks and not bool(getattr(args, "keep_unmapped", False)):
                        dropped_unmapped += 1
                        continue

                    headline = f"[GDELT-EVENT] {actor1 or 'UNKNOWN'} {ev_code or ''} {actor2 or ''}".strip()
                    body = f"actor1={actor1}; actor2={actor2}; event_code={ev_code}; root_code={root_code}; avg_tone={avg_tone:+.3f}; domain={domain}"
                    published_at = f"{sql[:4]}-{sql[4:6]}-{sql[6:8]}T00:00:00Z" if re.match(r"^\d{8}$", sql) else f"{_iso_day(d)}T00:00:00Z"
                    items.append(
                        {
                            "provider": "gdelt1",
                            "stream": "events",
                            "published_at": published_at,
                            "source": domain or "GDELT",
                            "url": url or None,
                            "headline": headline,
                            "body": body,
                            "tickers": ticks,
                            "gdelt": {
                                "event_code": ev_code,
                                "event_root_code": root_code,
                                "avg_tone": avg_tone,
                                "actor1": actor1,
                                "actor2": actor2,
                            },
                        }
                    )
                    kept_total += 1
                    if int(getattr(args, "limit_per_day", 0) or 0) > 0 and len(items) >= int(args.limit_per_day):
                        break

            else:
                zp = _gkg_dest(hist_root, yyyymmdd)
                if not zp.exists():
                    missing_raw += 1
                    day_items_by_stream[stream] = []
                    continue

                for row in _iter_zip_tsv_rows(zp):
                    # We support two common layouts:
                    # - Daily GKG (v1-style): DATE,NUMARTS,COUNTS,THEMES,LOCATIONS,PERSONS,ORGS,TONE,...,SOURCES,SOURCEURLS
                    # - Per-record GKG (v2+): includes a DocumentIdentifier URL field.

                    url_candidates = [c for c in row if isinstance(c, str) and c.startswith("http")]
                    urls: List[str] = []
                    themes: List[str] = []
                    persons: List[str] = []
                    orgs: List[str] = []
                    tone = 0.0

                    if len(row) >= 11 and re.match(r"^\d{8}$", row[0].strip()):
                        # v1-style daily
                        themes = _split_gkg_list(row[3]) if len(row) > 3 else []
                        persons = _split_gkg_list(row[5]) if len(row) > 5 else []
                        orgs = _split_gkg_list(row[6]) if len(row) > 6 else []
                        tone = _parse_gkg_tone(row[7]) if len(row) > 7 else 0.0
                        # SOURCEURLS field typically last
                        srcurls_field = row[10] if len(row) > 10 else ""
                        for u in str(srcurls_field).split(";"):
                            uu = u.strip()
                            if uu.startswith("http"):
                                urls.append(uu)
                    else:
                        # v2-ish per-record: pick first URL, and treat remaining list-like fields as metadata.
                        if url_candidates:
                            urls = [url_candidates[0]]
                        # Heuristic: themes/persons/orgs are semicolon-delimited fields.
                        for c in row:
                            if not isinstance(c, str):
                                continue
                            if ";" in c and "http" not in c:
                                # Split and keep as candidates.
                                # NOTE: v2 uses different vocabularies; we treat these as untyped candidates.
                                persons += _split_gkg_list(c)
                        tone = 0.0

                    locs: List[str] = []
                    if len(row) >= 11 and re.match(r"^\d{8}$", row[0].strip()):
                        locs = _split_gkg_list(row[4]) if len(row) > 4 else []
                    if not _gkg_pass_filter(themes, persons, orgs, locs, spec):
                        continue

                    entity_candidates = list(dict.fromkeys(persons + orgs))
                    ticks = _match_tickers(
                        candidates=entity_candidates,
                        rules=rules,
                        d=d,
                        strip_punct=strip_punct,
                        lowercase=lowercase,
                    )

                    top_theme = themes[0] if themes else ""
                    top_ent = (orgs[0] if orgs else (persons[0] if persons else ""))

                    for url in urls:
                        domain = _safe_domain(url)
                        emitted_total += 1
                        if not ticks and not bool(getattr(args, "keep_unmapped", False)):
                            dropped_unmapped += 1
                            continue

                        headline_parts = ["[GDELT-GKG]"]
                        if domain:
                            headline_parts.append(domain)
                        if top_theme:
                            headline_parts.append(top_theme)
                        if top_ent:
                            headline_parts.append(top_ent)
                        headline = " - ".join([p for p in headline_parts if p]).strip()
                        body = f"themes={top_theme}; entity={top_ent}; tone={tone:+.3f}; domain={domain}"

                        items.append(
                            {
                                "provider": "gdelt1",
                                "stream": "gkg",
                                "published_at": f"{_iso_day(d)}T00:00:00Z",
                                "source": domain or "GDELT",
                                "url": url,
                                "headline": headline,
                                "body": body,
                                "tickers": ticks,
                                "gdelt": {
                                    "themes": themes,
                                    "persons": persons,
                                    "organizations": orgs,
                                    "tone": tone,
                                },
                            }
                        )
                        kept_total += 1

                        if int(getattr(args, "limit_per_day", 0) or 0) > 0 and len(items) >= int(args.limit_per_day):
                            break
                    if int(getattr(args, "limit_per_day", 0) or 0) > 0 and len(items) >= int(args.limit_per_day):
                        break

            # Deduplicate by URL (within the stream/day) to keep fixtures stable.
            seen_url: set[str] = set()
            deduped: List[Dict[str, Any]] = []
            for it in items:
                u = str(it.get("url") or "")
                if u and u in seen_url:
                    continue
                if u:
                    seen_url.add(u)
                deduped.append(it)
            day_items_by_stream[stream] = deduped

            # Write stream/day file
            out_path = out_root / stream / f"{_iso_day(d)}.jsonl"
            _ensure_dir(out_path.parent)
            with out_path.open("w", encoding="utf-8") as f:
                for it in deduped:
                    f.write(json.dumps(it, ensure_ascii=False, sort_keys=True) + "\n")

        # Optional merged output when stream=both
        if args.stream == "both" and bool(getattr(args, "merge", False)):
            merged: List[Dict[str, Any]] = []
            for st in ("events", "gkg"):
                merged += day_items_by_stream.get(st, [])
            # Dedup by URL across streams
            seen: set[str] = set()
            out: List[Dict[str, Any]] = []
            for it in merged:
                u = str(it.get("url") or "")
                if u and u in seen:
                    continue
                if u:
                    seen.add(u)
                out.append(it)
            out_path = out_root / "merged" / f"{_iso_day(d)}.jsonl"
            _ensure_dir(out_path.parent)
            with out_path.open("w", encoding="utf-8") as f:
                for it in out:
                    f.write(json.dumps(it, ensure_ascii=False, sort_keys=True) + "\n")

    print(
        "History fixtures done: "
        + f"kept={kept_total} emitted={emitted_total} dropped_unmapped={dropped_unmapped} missing_raw_days={missing_raw}"
    )
    return 0


def cmd_history_profile(args: argparse.Namespace) -> int:
    hist_root = _history_root(str(args.raw_dir))
    d0 = _parse_ymd(args.date_from)
    d1 = _parse_ymd(args.date_to)
    top_n = int(args.top_n)
    out_root = Path(str(args.out)) / "gdelt1"

    streams = [args.stream] if args.stream != "both" else ["events", "gkg"]
    report_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    for stream in streams:
        stats: Dict[str, Any] = {
            "provider": "gdelt1",
            "stream": stream,
            "date_from": _iso_day(d0),
            "date_to": _iso_day(d1),
            "generated_at_utc": _utc_iso_now(),
            "days": 0,
            "missing_raw_days": 0,
            "rows_total": 0,
            "rows_with_url": 0,
            "top_domains": [],
            "top_event_codes": [],
            "top_actor_names": [],
            "top_themes": [],
            "top_entities": [],
        }

        dom_cnt: Dict[str, int] = {}
        ev_cnt: Dict[str, int] = {}
        act_cnt: Dict[str, int] = {}
        theme_cnt: Dict[str, int] = {}
        ent_cnt: Dict[str, int] = {}

        for d in _iter_days(d0, d1):
            stats["days"] += 1
            yyyymmdd = d.strftime("%Y%m%d")
            zp = _events_dest(hist_root, yyyymmdd) if stream == "events" else _gkg_dest(hist_root, yyyymmdd)
            if not zp.exists():
                stats["missing_raw_days"] += 1
                continue

            for row in _iter_zip_tsv_rows(zp):
                stats["rows_total"] += 1

                if stream == "events":
                    url = row[-1].strip() if row else ""
                    if url.startswith("http"):
                        stats["rows_with_url"] += 1
                        dom = _safe_domain(url)
                        if dom:
                            dom_cnt[dom] = dom_cnt.get(dom, 0) + 1
                    ev = row[26].strip() if len(row) > 26 else ""
                    if ev:
                        ev_cnt[ev] = ev_cnt.get(ev, 0) + 1
                    a1 = row[6].strip() if len(row) > 6 else ""
                    a2 = row[16].strip() if len(row) > 16 else ""
                    for a in (a1, a2):
                        if a:
                            act_cnt[a] = act_cnt.get(a, 0) + 1
                else:
                    # GKG: accumulate themes/entities and domains from URLs
                    if len(row) >= 11 and re.match(r"^\d{8}$", row[0].strip()):
                        themes = _split_gkg_list(row[3]) if len(row) > 3 else []
                        persons = _split_gkg_list(row[5]) if len(row) > 5 else []
                        orgs = _split_gkg_list(row[6]) if len(row) > 6 else []
                        for t in themes:
                            theme_cnt[t] = theme_cnt.get(t, 0) + 1
                        for e in persons + orgs:
                            ent_cnt[e] = ent_cnt.get(e, 0) + 1
                        srcurls_field = row[10] if len(row) > 10 else ""
                        for u in str(srcurls_field).split(";"):
                            uu = u.strip()
                            if uu.startswith("http"):
                                stats["rows_with_url"] += 1
                                dom = _safe_domain(uu)
                                if dom:
                                    dom_cnt[dom] = dom_cnt.get(dom, 0) + 1
                    else:
                        url_candidates = [c for c in row if isinstance(c, str) and c.startswith("http")]
                        if url_candidates:
                            stats["rows_with_url"] += 1
                            dom = _safe_domain(url_candidates[0])
                            if dom:
                                dom_cnt[dom] = dom_cnt.get(dom, 0) + 1

        def _top(d: Dict[str, int]) -> List[Dict[str, Any]]:
            items = sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))[:top_n]
            return [{"key": k, "count": int(v)} for k, v in items]

        stats["top_domains"] = _top(dom_cnt)
        if stream == "events":
            stats["top_event_codes"] = _top(ev_cnt)
            stats["top_actor_names"] = _top(act_cnt)
        else:
            stats["top_themes"] = _top(theme_cnt)
            stats["top_entities"] = _top(ent_cnt)

        out_path = out_root / stream / f"profile_{d0.strftime('%Y%m%d')}_{d1.strftime('%Y%m%d')}_{report_ts}.json"
        _write_json(out_path, stats)
        print(f"Wrote profile: {out_path}")
        print(
            f"Profile summary [{stream}]: days={stats['days']} missing_days={stats['missing_raw_days']} rows={stats['rows_total']} urls={stats['rows_with_url']}"
        )

    return 0


def main(argv: list[str] | None = None) -> None:
    root = ensure_sys_path()
    _load_local_env(root)

    args = build_parser().parse_args(list(argv) if argv is not None else sys.argv[1:])
    _maybe_enable_online(args)

    # Normalize db path to avoid surprises.
    args.db = normalize_db_path(root, args.db)

    if args.command == "collect":
        raise SystemExit(cmd_collect(root, args))
    if args.command == "run":
        raise SystemExit(cmd_run(root, args))
    if args.command == "status":
        raise SystemExit(cmd_status(root, args))
    if args.command == "history":
        raise SystemExit(cmd_history(root, args))

    raise SystemExit(2)


if __name__ == "__main__":
    main()
