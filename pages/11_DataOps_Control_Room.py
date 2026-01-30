from __future__ import annotations

import os
from datetime import date, datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st
import yaml

from src.db.migrate import cli_migrate
from src.dataops.closures_seed import seed_market_halts_from_csv
from src.dataops.halts_sync import sync_halts_yaml
from src.dataops.prices_ingest import ingest_prices_incremental
from src.dataops.dq_prices import run_price_data_quality


st.title("DataOps Control Room (PHASE1)")
st.caption(
    "Editor + comandi operativi per closures/halts/prices ingest e Data Quality..."
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = os.environ.get("SENTINEL_ALPHA_DB_PATH", str(ROOT / "data" / "sentinel_alpha.db"))
HALTS_YAML = ROOT / "config" / "dataops" / "halts.yml"


def _now_run_id(prefix: str) -> str:
    return f"{prefix}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"


with st.sidebar:
    st.header("Scope")
    db_path = st.text_input("DB path", value=DEFAULT_DB)
    asof = st.date_input("asof_date", value=date.today())
    universe_id = st.text_input("universe_id (optional)", value="ALL")
    lookback_days = st.number_input("lookback_days", min_value=5, max_value=365, value=45, step=5)
    window_days = st.number_input("dq window_days", min_value=30, max_value=2000, value=365, step=30)
    allow_online = st.checkbox("Allow online ingest", value=False)

cli_migrate(db_path)

st.subheader("halts.yml editor")
if not HALTS_YAML.exists():
    st.warning(f"Missing: {HALTS_YAML}")
else:
    raw = HALTS_YAML.read_text(encoding="utf-8", errors="replace")
    edited = st.text_area("config/dataops/halts.yml", value=raw, height=320)
    col_a, col_b = st.columns([1, 3])
    with col_a:
        if st.button("Validate", use_container_width=True):
            try:
                obj = yaml.safe_load(edited)
                if not isinstance(obj, dict):
                    st.error("YAML root must be a mapping/dict")
                else:
                    st.success("YAML OK")
                    st.json(obj)
            except Exception as e:
                st.error(f"YAML error: {e}")
    with col_b:
        if st.button("Save halts.yml", use_container_width=True):
            try:
                obj = yaml.safe_load(edited)
                if not isinstance(obj, dict):
                    st.error("YAML root must be a mapping/dict")
                else:
                    HALTS_YAML.write_text(edited.strip() + "\n", encoding="utf-8")
                    st.success("Saved")
            except Exception as e:
                st.error(f"Save failed: {e}")

st.divider()

st.subheader("Commands")
cmd_cols = st.columns(5)

result_msgs: list[str] = []

def _with_con():
    con = duckdb.connect(db_path, read_only=False)
    return con

with cmd_cols[0]:
    if st.button("Import closures", use_container_width=True):
        run_id = _now_run_id("DATAOPS_CLOSURES")
        con = _with_con()
        try:
            res = seed_market_halts_from_csv(con, run_id=run_id)
            result_msgs.append(res.message)
        finally:
            con.close()

with cmd_cols[1]:
    if st.button("Sync halts.yml", use_container_width=True):
        run_id = _now_run_id("DATAOPS_HALTS")
        con = _with_con()
        try:
            res = sync_halts_yaml(con, run_id=run_id)
            result_msgs.append(res.message)
        finally:
            con.close()

with cmd_cols[2]:
    if st.button("Prices ingest", use_container_width=True):
        run_id = _now_run_id("DATAOPS_INGEST")
        con = _with_con()
        try:
            res = ingest_prices_incremental(
                con,
                run_id=run_id,
                asof_date=asof,
                universe_id=universe_id or "ALL",
                lookback_days=int(lookback_days),
                start_date=None,
                max_window_days=180,
                online=bool(allow_online),
            )
            result_msgs.append(res.message)
        finally:
            con.close()

with cmd_cols[3]:
    if st.button("DQ prices", use_container_width=True):
        run_id = _now_run_id("DATAOPS_DQ")
        con = _with_con()
        try:
            res = run_price_data_quality(
                con,
                run_id=run_id,
                asof_date=asof,
                window_days=int(window_days),
            )
            result_msgs.append(res.message)
        finally:
            con.close()

with cmd_cols[4]:
    if st.button("Refresh views", use_container_width=True):
        result_msgs.append("refreshed")

if result_msgs:
    for m in result_msgs[-5:]:
        st.info(m)

st.divider()

st.subheader("DB views")
con = duckdb.connect(db_path, read_only=False)
try:
    tabs = st.tabs(["dq_runs", "dq_metrics_daily", "dq_findings", "data_gaps", "halts"])

    with tabs[0]:
        try:
            df = con.execute("SELECT * FROM dq_runs ORDER BY finished_at DESC LIMIT 200").df()
            st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.warning(f"dq_runs not available: {e}")

    with tabs[1]:
        try:
            df = con.execute(
                "SELECT * FROM dq_metrics_daily ORDER BY asof_date DESC, market, metric LIMIT 5000"
            ).df()
            st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.warning(f"dq_metrics_daily not available: {e}")

    with tabs[2]:
        try:
            df = con.execute("SELECT * FROM dq_findings ORDER BY created_at DESC LIMIT 2000").df()
            st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.warning(f"dq_findings not available: {e}")

    with tabs[3]:
        try:
            df = con.execute(
                "SELECT * FROM data_gaps ORDER BY requested_at DESC LIMIT 2000"
            ).df()
            st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.warning(f"data_gaps not available: {e}")

    with tabs[4]:
        c1, c2 = st.columns(2)
        with c1:
            try:
                df = con.execute("SELECT * FROM market_halts ORDER BY start_date DESC LIMIT 2000").df()
                st.dataframe(df, use_container_width=True)
            except Exception as e:
                st.warning(f"market_halts not available: {e}")
        with c2:
            try:
                df = con.execute("SELECT * FROM ticker_halts ORDER BY start_date DESC LIMIT 2000").df()
                st.dataframe(df, use_container_width=True)
            except Exception as e:
                st.warning(f"ticker_halts not available: {e}")
finally:
    con.close()
