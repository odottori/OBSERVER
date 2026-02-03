from __future__ import annotations

import json
import os
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

from src.phase0.db.migrate import cli_migrate


st.title("Audit Runs")
st.caption(
    "Browse e diagnostica dei run persistiti (audit_runs, report archiviati, transcript). "
    "I report sono salvati sia come reports/AUDIT_COMPLETE.md (latest) sia come reports/AUDIT_COMPLETE_<run_id>.md."
)

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

with st.sidebar:
    st.header("Filter")
    db_path = st.text_input("DB path", value=DEFAULT_DB)
    status = st.selectbox("Status", options=["(any)", "SUCCESS", "FAILED", "RUNNING"], index=0)
    limit = st.number_input("Max rows", min_value=10, max_value=5000, value=200, step=10)
    refresh = st.button("Refresh", use_container_width=True)


@st.cache_data(show_spinner=False)
def _load_runs(_db_path: str, _status: str, _limit: int) -> pd.DataFrame:
    cli_migrate(_db_path)
    con = duckdb.connect(_db_path, read_only=False)
    try:
        wh = ""
        params: list = []
        if _status and _status != "(any)":
            wh = "WHERE status = ?"
            params.append(_status)
        q = f"""
        SELECT run_id, started_at, finished_at, status, universe_id, holding_period_sessions, code_fingerprint, error
        FROM audit_runs
        {wh}
        ORDER BY COALESCE(finished_at, started_at) DESC
        LIMIT {int(_limit)}
        """
        df = con.execute(q, params).df()
        return df
    finally:
        try:
            con.close()
        except Exception:
            pass


if refresh:
    _load_runs.clear()

runs = _load_runs(db_path, status, int(limit))

if runs is None or runs.empty:
    st.info("No runs found.")
    st.stop()

st.dataframe(runs, use_container_width=True)

run_ids = runs["run_id"].astype(str).tolist()
selected = st.selectbox("Select run_id", options=run_ids, index=0)


def _find_report_for_run(rid: str) -> Path | None:
    rep = ROOT / "reports"
    p1 = rep / f"AUDIT_COMPLETE_{rid}.md"
    if p1.exists():
        return p1
    p0 = rep / "AUDIT_COMPLETE.md"
    return p0 if p0.exists() else None


def _find_transcripts_for_run(rid: str) -> list[Path]:
    rep = ROOT / "reports"
    if not rep.exists():
        return []
    files = list(rep.glob(f"*_TRANSCRIPT_{rid}.txt"))
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files


st.subheader("Run detail")

cli_migrate(db_path)
con = duckdb.connect(db_path, read_only=False)
try:
    row = con.execute(
        """
        SELECT run_id, started_at, finished_at, status, universe_id, holding_period_sessions, config_json, notes, error
        FROM audit_runs
        WHERE run_id = ?
        """,
        [selected],
    ).fetchone()
finally:
    try:
        con.close()
    except Exception:
        pass

if not row:
    st.error("run_id not found in DB.")
    st.stop()

rid, started_at, finished_at, stt, uid, hps, cfg_raw, notes, err = row

c1, c2, c3, c4 = st.columns(4)
c1.metric("run_id", rid)
c2.metric("status", stt)
c3.metric("universe", uid)
c4.metric("holding_period", int(hps or 0))

st.write(f"**started_at:** `{started_at}`")
st.write(f"**finished_at:** `{finished_at}`")
if notes:
    st.write(f"**notes:** {notes}")
if err:
    st.error(err)

with st.expander("config_json"):
    if cfg_raw:
        try:
            st.json(json.loads(cfg_raw))
        except Exception:
            st.code(str(cfg_raw), language="text")
    else:
        st.caption("(empty)")


st.divider()

st.subheader("Artifacts")

rp = _find_report_for_run(rid)
if rp is not None and rp.exists():
    st.write(f"Report file: `{rp}`")
    with st.expander("Open report"):
        st.markdown(rp.read_text(encoding="utf-8", errors="replace"))
else:
    st.info("No report found under reports/.")

trs = _find_transcripts_for_run(rid)
if trs:
    st.write("Transcript files:")
    for p in trs:
        with st.expander(f"Open transcript: {p.name}"):
            st.code(p.read_text(encoding="utf-8", errors="replace"), language="text")
else:
    st.caption("No transcript for this run_id.")
