from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

from src.phase0.db.migrate import cli_migrate


st.set_page_config(page_title="SENTINEL-ALPHA | Institutional Terminal", layout="wide")

ROOT = Path(__file__).resolve().parent
DB_PATH = os.environ.get("SENTINEL_ALPHA_DB_PATH", str(ROOT / "data" / "sentinel_alpha.db"))

# Ensure schema on app start.
cli_migrate(DB_PATH)


def _latest_file(glob_pat: str) -> Path | None:
    rep = ROOT / "reports"
    if not rep.exists():
        return None
    files = list(rep.glob(glob_pat))
    if not files:
        return None
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0]


def _read_text(p: Path, max_chars: int = 200_000) -> str:
    try:
        txt = p.read_text(encoding="utf-8", errors="replace")
        return txt if len(txt) <= max_chars else (txt[:max_chars] + "\n... (truncated)\n")
    except Exception as e:
        return f"(unable to read {p}: {e})"


st.title("SENTINEL-ALPHA: Institutional Terminal")
st.caption(
    "Questa UI è un cruscotto operativo multi-pagina. La pagina 'Pipeline Control' esegue davvero i comandi "
    "(migrate/tests/gates/run/certify) e cattura transcript in reports/."
)


left, right = st.columns([2, 1])
with left:
    st.subheader("Runtime")
    st.write(f"**DB:** `{DB_PATH}`")
    st.write(f"**Project root:** `{ROOT}`")
    st.write(f"**Now (local):** `{datetime.now().isoformat(timespec='seconds')}`")

with right:
    st.subheader("Artifacts")
    rpt = _latest_file("AUDIT_COMPLETE.md")
    trn = _latest_file("*_TRANSCRIPT_*.txt")
    st.write(f"**Latest report:** `{str(rpt) if rpt else '(none)'}`")
    st.write(f"**Latest transcript:** `{str(trn) if trn else '(none)'}`")


st.divider()


st.subheader("Last run status")
try:
    con = duckdb.connect(DB_PATH, read_only=False)
    row = con.execute(
        """
        SELECT run_id, started_at, finished_at, status, universe_id, holding_period_sessions, error
        FROM audit_runs
        ORDER BY COALESCE(finished_at, started_at) DESC
        LIMIT 1
        """
    ).fetchone()
    if row:
        run_id, started_at, finished_at, status, universe_id, hps, error = row
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("run_id", run_id)
        c2.metric("status", status)
        c3.metric("universe", universe_id)
        c4.metric("holding_period", int(hps or 0))

        st.write(f"**started_at:** `{started_at}`")
        st.write(f"**finished_at:** `{finished_at}`")

        if status and str(status).upper() != "SUCCESS" and error:
            st.error(error)

        # Quick counters
        try:
            tcnt = int(con.execute("SELECT COUNT(*) FROM audit_trades WHERE run_id = ?", [run_id]).fetchone()[0])
            ecnt = int(con.execute("SELECT COUNT(*) FROM audit_equity WHERE run_id = ?", [run_id]).fetchone()[0])
            st.write(f"Trades rows: **{tcnt}**, Equity rows: **{ecnt}**")
        except Exception:
            pass
    else:
        st.info("Nessun audit run trovato. Vai su 'Pipeline Control' e lancia RUN o CERTIFY.")
finally:
    try:
        con.close()
    except Exception:
        pass


st.divider()


st.subheader("Quick view")
tab1, tab2 = st.tabs(["AUDIT_COMPLETE.md", "Latest transcript"])

with tab1:
    if rpt and rpt.exists():
        st.markdown(_read_text(rpt))
    else:
        st.info("Nessun report trovato in reports/. Esegui RUN o CERTIFY.")

with tab2:
    if trn and trn.exists():
        st.code(_read_text(trn), language="text")
    else:
        st.info("Nessun transcript trovato in reports/. Esegui RUN o CERTIFY.")
