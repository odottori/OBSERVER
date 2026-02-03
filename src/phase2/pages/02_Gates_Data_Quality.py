from __future__ import annotations

import os
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

from src.phase0.db.migrate import cli_migrate
from src.phase0.core.audit_engine import AuditEngine
from src.phase0.tools.verify_ticker_mappings import check_ticker_mappings


st.title("Gates & Data Quality")
st.caption(
    "Questa pagina mostra lo stato dei gate pre-audit (ticker_mappings, input coverage/right-censoring) "
    "senza avviare il backtest. È utile per diagnosticare problemi tipici retail (ticker sporchi, serie price mancanti)."
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
    st.header("Scope")
    db_path = st.text_input("DB path", value=DEFAULT_DB)
    universe_id = st.text_input("Universe", value="ALL")
    st.divider()
    sample_limit = st.number_input("Sample limit", min_value=0, max_value=200, value=20, step=5)
    max_chain_len_warn = st.number_input("Max chain len (warn)", min_value=1, max_value=20, value=4, step=1)
    enable_warnings = st.checkbox("Enable warnings", value=True)
    refresh = st.button("Refresh", use_container_width=True)


@st.cache_data(show_spinner=False)
def _load_gate_state(
    _db_path: str,
    _universe_id: str,
    _sample_limit: int,
    _max_chain_len_warn: int,
    _enable_warnings: bool,
) -> dict:
    cli_migrate(_db_path)
    con = duckdb.connect(_db_path, read_only=False)
    try:
        eng = AuditEngine(con=con)
        cov = eng.verify_signal_price_coverage(universe_id=_universe_id, sample_limit=int(_sample_limit))
        mp = check_ticker_mappings(
            con,
            sample_limit=int(_sample_limit),
            max_chain_len_warn=int(_max_chain_len_warn),
            enable_warnings=bool(_enable_warnings),
        )
        return {"coverage": cov, "mappings": mp}
    finally:
        try:
            con.close()
        except Exception:
            pass


if refresh:
    _load_gate_state.clear()

state = _load_gate_state(db_path, universe_id, int(sample_limit), int(max_chain_len_warn), bool(enable_warnings))
cov = state.get("coverage") or {}
mp = state.get("mappings") or {}


st.subheader("Ticker mappings gate")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("rows", int(mp.get("n_rows", 0) or 0))
c2.metric("aliases", int(mp.get("n_aliases", 0) or 0))
c3.metric("overlaps", int(mp.get("n_overlaps", 0) or 0))
c4.metric("cycles", int(mp.get("n_cycles", 0) or 0))
c5.metric("invalid", int(mp.get("n_invalid", 0) or 0))

fails = mp.get("failures") or []
if fails:
    st.error("Gate FAIL: ticker_mappings")
    st.write("Failures:")
    st.write(pd.DataFrame({"failure": list(fails)}))
else:
    st.success("Gate PASS: ticker_mappings")

with st.expander("Diagnostics: invalid / overlaps / cycles"):
    for key, title in (
        ("invalid_rows", "Invalid rows"),
        ("overlap_samples", "Overlap samples"),
        ("cycle_samples", "Cycle samples"),
    ):
        items = mp.get(key) or []
        st.markdown(f"**{title}**")
        if items:
            st.write(pd.DataFrame({"item": list(items)}))
        else:
            st.caption("(none)")

    warns = mp.get("warnings") or []
    st.markdown("**Warnings**")
    if warns:
        st.write(pd.DataFrame({"warning": list(warns)}))
    else:
        st.caption("(none)")


st.divider()


st.subheader("Input coverage gate (signals → prices)")
eligible_total = int(cov.get("eligible_signals", 0) or 0)
right_censored = int(cov.get("signals_right_censored", 0) or 0)
eligible_enterable = max(0, eligible_total - right_censored)
missing = int(cov.get("signals_missing_price_series", 0) or 0)
norm_changed = int(cov.get("signals_normalization_changed", 0) or 0)
mapped_applied = int(cov.get("signals_mapping_applied", 0) or 0)

d1, d2, d3, d4, d5 = st.columns(5)
d1.metric("eligible_enterable", eligible_enterable)
d2.metric("eligible_total", eligible_total)
d3.metric("right_censored", right_censored)
d4.metric("missing_series", missing)
d5.metric("normalized/mapped", f"{norm_changed}/{mapped_applied}")

if missing > 0:
    st.error("Gate FAIL (default policy): some eligible signals reference tickers with no price series.")
else:
    st.success("Coverage OK: no missing price series for eligible signals.")

with st.expander("Diagnostics: missing price series sample"):
    sample = cov.get("missing_price_series_sample") or []
    if sample:
        st.write(pd.DataFrame(sample))
    else:
        st.caption("(none)")
