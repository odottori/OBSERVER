from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st


def _repo_root() -> Path:
    """Best-effort repo root discovery (works from /pages and /src/*)."""
    p = Path(__file__).resolve()
    for parent in p.parents:
        if (parent / 'src').is_dir() and (parent / '.doc').is_dir():
            return parent
    # Fallback: historical assumption (file lives under repo/pages/)
    return p.parents[1]

ROOT = _repo_root()
DEFAULT_DB = os.environ.get("SENTINEL_ALPHA_DB_PATH", str(ROOT / "data" / "sentinel_alpha.db"))
FIRM = "NEWS-ALPHA"


def _run(cmd: list[str], env_overrides: dict[str, str]) -> tuple[int, str]:
    env = os.environ.copy()
    env.update(env_overrides)
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, env=env)
    out = (proc.stdout or "") + (proc.stderr or "")
    return int(proc.returncode), out


def _latest_in(dir_path: Path, pattern: str) -> Path | None:
    if not dir_path.exists():
        return None
    files = list(dir_path.glob(pattern))
    if not files:
        return None
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0]


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


st.title("NEWS-ALPHA")
st.caption(
    "Lane operativa per la raccolta e trasformazione di news (offline-by-default). "
    "Workflow tipico: collect → fixtures.jsonl → run → scrittura in recs (firm=NEWS-ALPHA) e sentiment_cache."
)


with st.sidebar:
    st.header("Runtime")
    db_path = st.text_input("DB path", value=DEFAULT_DB)
    universe_id = st.text_input("Universe", value="ALL")

    st.divider()
    st.header("Collector")
    date_from = st.date_input("date_from", value=date.today())
    date_to = st.date_input("date_to", value=date.today())
    when_days = st.number_input("when_days", min_value=1, max_value=60, value=14, step=1)
    domains_raw = st.text_area("allowed domains (one per line)", value="")
    raw_dir = st.text_input("raw_dir", value="reports/news_alpha/raw/rss")

    offline_parse = st.checkbox("offline_parse", value=True)
    online = st.checkbox("online (guarded)", value=False)
    allow_online = st.checkbox("allow_online for this run", value=False)

    st.divider()
    st.header("Runner")
    overwrite = st.checkbox("overwrite (firm rows in range)", value=False)
    dry_run = st.checkbox("dry_run", value=False)
    log_json = st.checkbox("log_json", value=True)

    st.divider()
    confirm = st.checkbox("Confermo: esegui comandi", value=False)


env_overrides = {
    "SENTINEL_ALPHA_DB_PATH": db_path,
}
if allow_online:
    env_overrides["NEWS_ALPHA_ALLOW_ONLINE"] = "1"

py = sys.executable

rep = ROOT / "reports" / "news_alpha"
latest_fixture = _latest_in(rep / "collector", "*.jsonl")
latest_stats = _latest_in(rep / "collector", "*_stats.json")

st.subheader("Artifacts")
c1, c2 = st.columns(2)
with c1:
    st.write(f"**Latest fixtures:** `{str(latest_fixture) if latest_fixture else '(none)'}`")
with c2:
    st.write(f"**Latest collector stats:** `{str(latest_stats) if latest_stats else '(none)'}`")
if latest_stats and latest_stats.exists():
    st.json(_read_json(latest_stats))

st.divider()


st.subheader("Commands")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("collect fixtures", disabled=not confirm, use_container_width=True):
        cmd = [
            py,
            "scripts/news_alpha.py",
            "collect",
            "--db",
            db_path,
            "--universe-id",
            universe_id,
            "--date-from",
            date_from.isoformat(),
            "--date-to",
            date_to.isoformat(),
            "--when-days",
            str(int(when_days)),
            "--raw-dir",
            raw_dir,
        ]
        domains = [d.strip() for d in (domains_raw or "").splitlines() if d.strip()]
        for d in domains:
            cmd += ["--domains", d]

        if offline_parse:
            cmd += ["--offline-parse"]
        if online:
            cmd += ["--online"]
        if allow_online:
            cmd += ["--allow-online"]

        rc, out = _run(cmd, env_overrides)
        st.session_state["news_last_cmd"] = "collect"
        st.session_state["news_last_rc"] = rc
        st.session_state["news_last_out"] = out

with col2:
    fixtures_default = str(latest_fixture) if latest_fixture else ""
    fixtures_path = st.text_input("fixtures_jsonl", value=fixtures_default)

with col3:
    if st.button("run NEWS-ALPHA", disabled=not (confirm and bool(fixtures_default or True)), use_container_width=True):
        if not fixtures_path.strip():
            st.error("fixtures_jsonl is required (run collect first, or paste a path).")
        else:
            cmd = [
                py,
                "scripts/news_alpha.py",
                "run",
                "--db",
                db_path,
                "--universe-id",
                universe_id,
                "--date-from",
                date_from.isoformat(),
                "--date-to",
                date_to.isoformat(),
                "--fixtures",
                fixtures_path.strip(),
            ]
            if overwrite:
                cmd += ["--overwrite"]
            if dry_run:
                cmd += ["--dry-run"]
            if log_json:
                cmd += ["--log-json"]
            if online:
                cmd += ["--online"]
            if allow_online:
                cmd += ["--allow-online"]

            rc, out = _run(cmd, env_overrides)
            st.session_state["news_last_cmd"] = "run"
            st.session_state["news_last_rc"] = rc
            st.session_state["news_last_out"] = out


last_cmd = st.session_state.get("news_last_cmd")
last_rc = st.session_state.get("news_last_rc")
last_out = st.session_state.get("news_last_out")
if last_cmd:
    st.subheader("Last execution")
    st.write(f"**command:** {last_cmd}")
    st.write(f"**exit code:** {last_rc}")
    st.code(last_out or "(no output)")

st.divider()


st.subheader("DB preview (firm=NEWS-ALPHA)")
try:
    con = duckdb.connect(db_path, read_only=False)
    # Summary metrics
    total_recs = int(con.execute("SELECT COUNT(*) FROM recs WHERE firm = ?", [FIRM]).fetchone()[0])
    total_cache = int(con.execute("SELECT COUNT(*) FROM sentiment_cache WHERE model='lexicon-v1'").fetchone()[0])
    m1, m2 = st.columns(2)
    m1.metric("recs rows (NEWS-ALPHA)", total_recs)
    m2.metric("sentiment_cache rows (lexicon-v1)", total_cache)

    df = con.execute(
        """
        SELECT
          date,
          ticker,
          rating,
          sentiment_score,
          headline,
          source_url,
          published_at
        FROM recs
        WHERE firm = ?
          AND date BETWEEN ? AND ?
        ORDER BY date DESC, ticker ASC
        LIMIT 200
        """,
        [FIRM, date_from, date_to],
    ).df()

    st.dataframe(df, use_container_width=True, hide_index=True)
finally:
    try:
        con.close()
    except Exception:
        pass
