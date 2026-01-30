from __future__ import annotations

import os
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

from src.db.migrate import cli_migrate


st.title("Data Gaps & Backfill")
st.caption(
    "Questa pagina rende osservabile il meccanismo data_gaps/backfill: quando il runner incontra buchi di prezzo, "
    "registra un evento in data_gaps con reason_code e rows_upserted."
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = os.environ.get("SENTINEL_ALPHA_DB_PATH", str(ROOT / "data" / "sentinel_alpha.db"))

with st.sidebar:
    st.header("Scope")
    db_path = st.text_input("DB path", value=DEFAULT_DB)
    cli_migrate(db_path)
    con = duckdb.connect(db_path, read_only=False)
    try:
        run_ids = (
            con.execute(
                "SELECT DISTINCT run_id FROM data_gaps ORDER BY run_id DESC LIMIT 500"
            )
            .fetchdf()["run_id"]
            .astype(str)
            .tolist()
        )
        if not run_ids:
            # Fallback: from audit_runs
            run_ids = (
                con.execute(
                    "SELECT run_id FROM audit_runs ORDER BY COALESCE(finished_at, started_at) DESC LIMIT 500"
                )
                .fetchdf()["run_id"]
                .astype(str)
                .tolist()
            )
    finally:
        try:
            con.close()
        except Exception:
            pass

    if not run_ids:
        st.warning("No runs in DB.")
        st.stop()

    run_id = st.selectbox("run_id", options=run_ids, index=0)
    kind = st.selectbox("kind", options=["(any)", "prices", "news"], index=0)
    show_only_fail = st.checkbox("Only failures", value=False)
    limit = st.number_input("Max rows", min_value=50, max_value=20000, value=2000, step=50)


cli_migrate(db_path)
con = duckdb.connect(db_path, read_only=False)
try:
    wh = "WHERE run_id = ?"
    params: list = [run_id]
    if kind and kind != "(any)":
        wh += " AND kind = ?"
        params.append(kind)
    if show_only_fail:
        wh += " AND UPPER(status) <> 'SUCCESS'"

    df = con.execute(
        f"SELECT * FROM data_gaps {wh} ORDER BY requested_at DESC LIMIT {int(limit)}",
        params,
    ).df()
finally:
    try:
        con.close()
    except Exception:
        pass


st.subheader("Summary")
if df is None or df.empty:
    st.info("No data_gaps rows for this selection.")
    st.stop()

sum_cols = [c for c in ["provider", "status", "reason_code", "kind"] if c in df.columns]
if sum_cols:
    grp = df.groupby(sum_cols, dropna=False).size().reset_index(name="n")
    grp = grp.sort_values("n", ascending=False)
    st.dataframe(grp, use_container_width=True)

st.divider()

st.subheader("Rows")
keep = [
    "requested_at",
    "kind",
    "ticker",
    "requested_start_date",
    "requested_end_date",
    "obtained_start_date",
    "obtained_end_date",
    "status",
    "provider",
    "reason_code",
    "rows_inserted",
    "rows_upserted",
    "duration_ms",
    "message",
    "error",
]
keep = [c for c in keep if c in df.columns]
st.dataframe(df[keep], use_container_width=True)

with st.expander("Raw table view"):
    st.dataframe(df, use_container_width=True)
