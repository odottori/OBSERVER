from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

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


def _find_latest_transcript() -> str | None:
    rep = ROOT / "reports"
    if not rep.exists():
        return None
    files = list(rep.glob("*_TRANSCRIPT_*.txt"))
    if not files:
        return None
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return str(files[0].resolve())


def _run(cmd: list[str], env_overrides: dict[str, str]) -> tuple[int, str]:
    env = os.environ.copy()
    env.update(env_overrides)
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, env=env)
    out = (proc.stdout or "") + (proc.stderr or "")
    return int(proc.returncode), out


st.title("Pipeline Control")
st.caption("Esecuzione reale, end-to-end: migrate → tests → gates → audit → report. Output e transcript sono catturati.")

with st.sidebar:
    st.header("Runtime")
    db_path = st.text_input("DB path", value=DEFAULT_DB)

    universe_id = st.text_input("Universe", value="ALL")

    offline = st.checkbox("Offline (default consigliato)", value=True)
    provider_order = st.text_input("Provider order", value=os.environ.get("SENTINEL_PRICE_PROVIDER_ORDER", "stooq"))
    enable_yfinance = st.checkbox("Enable yfinance", value=False)

    st.divider()
    run_id = st.text_input("Run ID (opzionale)", value="")
    confirm = st.checkbox("Confermo: esegui comandi", value=False)

env_overrides = {
    "SENTINEL_ALPHA_DB_PATH": db_path,
    "SENTINEL_PRICE_PROVIDER_ORDER": provider_order,
    "SENTINEL_DISABLE_YFINANCE": "0" if enable_yfinance else "1",
    "SENTINEL_OFFLINE": "1" if offline else "0",
    "SENTINEL_ALLOW_ONLINE_BACKFILL": "0" if offline else "1",
}
if run_id.strip():
    env_overrides["SENTINEL_RUN_ID"] = run_id.strip()

py = sys.executable

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("migrate", disabled=not confirm, use_container_width=True):
        rc, out = _run([py, "scripts/sentinel.py", "migrate", "--db", db_path], env_overrides)
        st.session_state["last_cmd"] = "migrate"
        st.session_state["last_rc"] = rc
        st.session_state["last_out"] = out

with col2:
    if st.button("tests", disabled=not confirm, use_container_width=True):
        rc, out = _run([py, "scripts/sentinel.py", "test", "--db", db_path], env_overrides)
        st.session_state["last_cmd"] = "tests"
        st.session_state["last_rc"] = rc
        st.session_state["last_out"] = out

with col3:
    if st.button("status", disabled=not confirm, use_container_width=True):
        rc, out = _run([py, "scripts/sentinel.py", "status", "--db", db_path], env_overrides)
        st.session_state["last_cmd"] = "status"
        st.session_state["last_rc"] = rc
        st.session_state["last_out"] = out

st.divider()

col4, col5, col6 = st.columns(3)
with col4:
    if st.button("gate: ticker_mappings", disabled=not confirm, use_container_width=True):
        rc, out = _run([py, "-m", "src.tools.verify_ticker_mappings", "--db", db_path], env_overrides)
        st.session_state["last_cmd"] = "gate ticker_mappings"
        st.session_state["last_rc"] = rc
        st.session_state["last_out"] = out

with col5:
    if st.button("gate: verify_inputs", disabled=not confirm, use_container_width=True):
        rc, out = _run([py, "-m", "src.tools.verify_inputs", "--db", db_path, "--universe-id", universe_id], env_overrides)
        st.session_state["last_cmd"] = "gate verify_inputs"
        st.session_state["last_rc"] = rc
        st.session_state["last_out"] = out

with col6:
    if st.button("verify_run", disabled=not confirm, use_container_width=True):
        cmd = [py, "-m", "src.tools.verify_run", "--db", db_path]
        if run_id.strip():
            cmd += ["--run-id", run_id.strip()]
        rc, out = _run(cmd, env_overrides)
        st.session_state["last_cmd"] = "verify_run"
        st.session_state["last_rc"] = rc
        st.session_state["last_out"] = out

st.divider()

col7, col8 = st.columns(2)
with col7:
    if st.button("RUN audit", disabled=not confirm, use_container_width=True):
        cmd = [py, "scripts/sentinel.py", "run", "--db", db_path]
        cmd += ["--offline"] if offline else ["--online"]
        if enable_yfinance:
            cmd += ["--enable-yfinance"]
        if provider_order.strip():
            cmd += ["--provider-order", provider_order.strip()]
        rc, out = _run(cmd, env_overrides)
        st.session_state["last_cmd"] = "run"
        st.session_state["last_rc"] = rc
        st.session_state["last_out"] = out

with col8:
    if st.button("CERTIFY (tests+gates+audit)", disabled=not confirm, use_container_width=True):
        cmd = [py, "scripts/sentinel.py", "certify", "--db", db_path]
        cmd += ["--offline"] if offline else ["--online"]
        if enable_yfinance:
            cmd += ["--enable-yfinance"]
        if provider_order.strip():
            cmd += ["--provider-order", provider_order.strip()]
        rc, out = _run(cmd, env_overrides)
        st.session_state["last_cmd"] = "certify"
        st.session_state["last_rc"] = rc
        st.session_state["last_out"] = out

# Output panel
last_cmd = st.session_state.get("last_cmd")
last_rc = st.session_state.get("last_rc")
last_out = st.session_state.get("last_out")

if last_cmd:
    st.subheader("Last execution")
    st.write(f"**command:** {last_cmd}  ")
    st.write(f"**exit code:** {last_rc}")
    st.code(last_out or "(no output)")

st.subheader("Transcript")
latest = _find_latest_transcript()
if latest:
    st.write(f"Latest transcript: `{latest}`")
else:
    st.info("Nessun transcript trovato in reports/. Esegui RUN o CERTIFY.")
