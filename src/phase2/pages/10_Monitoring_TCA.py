from __future__ import annotations

import os
from pathlib import Path

import duckdb
import streamlit as st

from src.phase0.db.migrate import cli_migrate
from src.monitoring.tca_report import build_tca_report_text


st.title("Monitoring / TCA")
st.caption("Report TCA v0: slippage/fees/cost-drag + hit-rate (best-effort).")

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
    st.header("Scope")
    db_path = st.text_input("DB path", value=DEFAULT_DB)
    cli_migrate(db_path)

    con = duckdb.connect(db_path, read_only=False)
    try:
        run_ids = (
            con.execute(
                "SELECT DISTINCT run_id FROM execution_fills WHERE run_id IS NOT NULL ORDER BY run_id DESC LIMIT 500"
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
    threshold_bp = st.number_input("Alert threshold (bp)", min_value=0.0, max_value=1000.0, value=10.0, step=1.0)

cli_migrate(db_path)
con = duckdb.connect(db_path, read_only=False)
try:
    txt = build_tca_report_text(
        con,
        run_id=None if run_id == "(any)" else run_id,
        threshold_cost_drag_bp=float(threshold_bp),
    )
finally:
    try:
        con.close()
    except Exception:
        pass

st.subheader("TCA report")
st.code(txt, language="text")
