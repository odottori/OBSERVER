from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

from src.db.migrate import cli_migrate


st.title("Execution Log")
st.caption("Ordini/fill di execution layer + risk flags (paper broker).")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = os.environ.get("SENTINEL_ALPHA_DB_PATH", str(ROOT / "data" / "sentinel_alpha.db"))


def _extract_risk_code(notes: object) -> str:
    if notes is None:
        return ""
    s = str(notes)
    k = "risk="
    if k not in s:
        return ""
    try:
        tail = s.split(k, 1)[1]
        return tail.split(";", 1)[0].strip()
    except Exception:
        return ""


with st.sidebar:
    st.header("Scope")
    db_path = st.text_input("DB path", value=DEFAULT_DB)
    cli_migrate(db_path)

    con = duckdb.connect(db_path, read_only=False)
    try:
        run_ids = (
            con.execute(
                "SELECT DISTINCT run_id FROM execution_orders WHERE run_id IS NOT NULL ORDER BY run_id DESC LIMIT 500"
            )
            .fetchdf()["run_id"]
            .astype(str)
            .tolist()
        )
    except Exception:
        run_ids = []
    finally:
        try:
            con.close()
        except Exception:
            pass

    run_id = st.selectbox("run_id (optional)", options=["(any)"] + run_ids, index=0)
    ticker_filter = st.text_input("Filter ticker (contains)", value="")
    status_filter = st.selectbox("Order status", options=["(any)", "FILLED", "REJECTED", "NEW", "CANCELLED"], index=0)
    date_from = st.text_input("From date (YYYY-MM-DD)", value="")
    date_to = st.text_input("To date (YYYY-MM-DD)", value="")
    limit = st.number_input("Max rows", min_value=50, max_value=20000, value=2000, step=50)


def _parse_iso(s: str) -> date | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except Exception:
        return None


cli_migrate(db_path)
con = duckdb.connect(db_path, read_only=False)
try:
    wh = []
    params: list = []

    if run_id and run_id != "(any)":
        wh.append("o.run_id = ?")
        params.append(run_id)

    tf = ticker_filter.strip()
    if tf:
        wh.append("upper(o.ticker) LIKE ?")
        params.append(f"%{tf.upper()}%")

    if status_filter and status_filter != "(any)":
        wh.append("upper(o.status) = ?")
        params.append(status_filter.upper())

    d0 = _parse_iso(date_from)
    if d0 is not None:
        wh.append("CAST(o.created_at AS DATE) >= ?")
        params.append(d0)

    d1 = _parse_iso(date_to)
    if d1 is not None:
        wh.append("CAST(o.created_at AS DATE) <= ?")
        params.append(d1)

    where_sql = ("WHERE " + " AND ".join(wh)) if wh else ""

    orders = con.execute(
        f"""
        SELECT
            o.order_id,
            o.run_id,
            o.created_at,
            o.ticker,
            o.side,
            o.quantity,
            o.order_type,
            o.limit_price,
            o.status,
            o.notes
        FROM execution_orders o
        {where_sql}
        ORDER BY COALESCE(o.created_at, now()) DESC
        LIMIT {int(limit)}
        """,
        params,
    ).df()

    fills = con.execute(
        f"""
        SELECT
            f.fill_id,
            f.order_id,
            f.run_id,
            f.filled_at,
            f.ticker,
            f.side,
            f.quantity,
            f.fill_price,
            f.fees,
            f.notes
        FROM execution_fills f
        ORDER BY COALESCE(f.filled_at, now()) DESC
        LIMIT {int(limit)}
        """
    ).df()
finally:
    try:
        con.close()
    except Exception:
        pass


st.subheader("Orders")
if orders is None or orders.empty:
    st.info("No execution_orders rows.")
else:
    df = orders.copy()
    df["risk_code"] = df.get("notes", pd.Series(dtype=str)).apply(_extract_risk_code)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("orders", int(len(df)))
    k2.metric("rejected", int((df.get("status", "").astype(str).str.upper() == "REJECTED").sum()))
    k3.metric("filled", int((df.get("status", "").astype(str).str.upper() == "FILLED").sum()))
    k4.metric("unique tickers", int(df.get("ticker", pd.Series(dtype=str)).astype(str).nunique()))

    show_cols = [
        "created_at",
        "run_id",
        "ticker",
        "side",
        "quantity",
        "status",
        "risk_code",
        "order_id",
    ]
    show_cols = [c for c in show_cols if c in df.columns]
    st.dataframe(df[show_cols], use_container_width=True)


st.divider()


st.subheader("Fills")
if fills is None or fills.empty:
    st.info("No execution_fills rows.")
else:
    df = fills.copy()
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("fills", int(len(df)))
    k2.metric("unique orders", int(df.get("order_id", pd.Series(dtype=str)).astype(str).nunique()))
    k3.metric("avg fees", f"{df.get('fees', pd.Series(dtype=float)).astype(float).mean():.4f}" if "fees" in df.columns else "n/a")
    k4.metric("avg fill_px", f"{df.get('fill_price', pd.Series(dtype=float)).astype(float).mean():.4f}" if "fill_price" in df.columns else "n/a")

    show_cols = [
        "filled_at",
        "run_id",
        "ticker",
        "side",
        "quantity",
        "fill_price",
        "fees",
        "order_id",
        "fill_id",
    ]
    show_cols = [c for c in show_cols if c in df.columns]
    st.dataframe(df[show_cols], use_container_width=True)
