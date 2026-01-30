from __future__ import annotations

import os
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

from src.db.migrate import cli_migrate


st.title("Trades & Equity")
st.caption(
    "Analisi operativa per un run: ledger trade (audit_trades) e curva equity (audit_equity). "
    "Questa pagina non lancia l'audit; legge i dati già persistiti."
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
    st.divider()
    show_raw_cols = st.checkbox("Show wide columns", value=False)
    ticker_filter = st.text_input("Filter ticker (contains)", value="")
    firm_filter = st.text_input("Filter firm (contains)", value="")
    rating_filter = st.text_input("Filter rating (exact)", value="")
    limit = st.number_input("Max trade rows", min_value=50, max_value=20000, value=2000, step=50)


cli_migrate(db_path)
con = duckdb.connect(db_path, read_only=False)
try:
    trades = con.execute("SELECT * FROM audit_trades WHERE run_id = ?", [run_id]).df()
    equity = con.execute("SELECT * FROM audit_equity WHERE run_id = ? ORDER BY date", [run_id]).df()
finally:
    try:
        con.close()
    except Exception:
        pass


st.subheader("Equity curve")
if equity is not None and not equity.empty:
    eq = equity.copy()
    eq["date"] = pd.to_datetime(eq["date"], errors="coerce")
    eq = eq.dropna(subset=["date"]).sort_values("date")

    start = float(eq["equity"].iloc[0])
    end = float(eq["equity"].iloc[-1])
    roi = ((end / start) - 1.0) * 100.0 if start != 0 else 0.0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Start", f"{start:,.2f}")
    k2.metric("End", f"{end:,.2f}")
    k3.metric("ROI (%)", f"{roi:.2f}")
    k4.metric("Tax paid", f"{float(eq['tax_paid'].iloc[-1] or 0.0):,.2f}" if "tax_paid" in eq.columns else "n/a")

    st.line_chart(eq.set_index("date")["equity"])

    # Drawdown quick stat
    peak = eq["equity"].cummax()
    dd = (eq["equity"] / peak) - 1.0
    max_dd = float(dd.min()) * 100.0 if not dd.empty else 0.0
    st.caption(f"Max drawdown (equity): {max_dd:.2f}%")
else:
    st.info("No equity rows for this run.")


st.divider()


st.subheader("Trades ledger")
if trades is None or trades.empty:
    st.info("No trade rows for this run.")
    st.stop()

df = trades.copy()
if ticker_filter.strip():
    df = df[df.get("ticker", "").astype(str).str.contains(ticker_filter.strip(), case=False, na=False)]
if firm_filter.strip():
    df = df[df.get("firm", "").astype(str).str.contains(firm_filter.strip(), case=False, na=False)]
if rating_filter.strip():
    df = df[df.get("rating", "").astype(str).str.upper() == rating_filter.strip().upper()]

df = df.head(int(limit))

# KPIs
t1, t2, t3, t4 = st.columns(4)
t1.metric("Trades", int(len(df)))
t2.metric("Avg net return (%)", f"{df['net_return_pct'].mean():.2f}" if "net_return_pct" in df.columns and not df.empty else "n/a")
t3.metric("Median net return (%)", f"{df['net_return_pct'].median():.2f}" if "net_return_pct" in df.columns and not df.empty else "n/a")
t4.metric("Forced exits", int(df.get("exit_is_fallback", pd.Series(dtype=bool)).sum()) if "exit_is_fallback" in df.columns else 0)

if not show_raw_cols:
    cols = [
        "signal_date",
        "buy_date",
        "sell_date",
        "ticker",
        "ticker_original",
        "firm",
        "rating",
        "exit_reason",
        "exit_is_fallback",
        "gross_return_pct",
        "cost_pct",
        "net_return_pct",
        "trade_score",
        "exec_shift_sessions",
        "exit_shift_sessions",
        "halt_reason",
    ]
    cols = [c for c in cols if c in df.columns]
    st.dataframe(df[cols], use_container_width=True)
else:
    st.dataframe(df, use_container_width=True)
