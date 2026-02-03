from __future__ import annotations

"""Streamlit page: Lifecycle Monitor (TTL=0, AS-OF navigation).

Obiettivo
---------
Vista operativa (decisionale/di controllo) per rispondere in modo deterministico:
  - Quali alert esistono nella finestra recente?
  - Quali erano operabili *oggi* (TTL=0)?
  - Quali sono in WAITLIST per mancanza del prezzo t+1 as-of?
  - Quali sono EXPIRED (finestra d'ingresso persa)?

Separazione concettuale
----------------------
Questa pagina supporta due modalita' distinte:
  - Trading Room (decisionale): ignora completamente il backtest/audit.
  - Backtest (simulazione): visualizza le simulazioni *as-of* usando audit_trades.

Nota importante
---------------
Questa pagina NON calcola postcast/exit/outcome; la exit policy deve essere derivata,
non inventata.

Vincoli
-------
- Offline-by-default: legge solo DuckDB locale
- Deterministica e AS-OF safe (no future leak)
"""

import os
from datetime import date
from pathlib import Path

import pandas as pd

try:
    import altair as alt  # type: ignore
except Exception:  # pragma: no cover
    alt = None

try:
    import streamlit as st  # type: ignore
except Exception:  # pragma: no cover
    st = None

try:
    import duckdb  # type: ignore
except Exception:  # pragma: no cover
    duckdb = None

from src.phase0.core.alert_lifecycle import LifecycleParams, compute_alert_lifecycle

def _repo_root() -> Path:
    """Best-effort repo root discovery (works from /pages and /src/*)."""
    p = Path(__file__).resolve()
    for parent in p.parents:
        if (parent / 'src').is_dir() and (parent / '.doc').is_dir():
            return parent
    # Fallback: historical assumption (file lives under repo/pages/)
    return p.parents[1]

ROOT = _repo_root()
DEFAULT_DB = ROOT / os.environ.get("SENTINEL_ALPHA_DB_PATH", "data/sentinel_alpha.db")


def _status_it(mode: str) -> dict[str, str]:
    if mode == "backtest":
        return {
            "TRADABLE": "Tradabile (TTL=0, as-of)",
            "EXPIRED": "Scaduto (TTL=0)",
            "WAITLIST": "In attesa dati (manca t+1 as-of)",
            "TRADED_OPEN": "Simulazione: aperta (uscita futura vs AS-OF)",
            "TRADED_CLOSED": "Simulazione: chiusa (uscita <= AS-OF)",
        }
    # trading
    return {
        "TRADABLE": "Tradabile oggi (TTL=0)",
        "EXPIRED": "Scaduto (finestra ingresso persa)",
        "WAITLIST": "In attesa dati (manca t+1 as-of)",
        # non dovrebbero comparire in modalita' trading (audit ignorato)
        "TRADED_OPEN": "(simulazione) aperta",
        "TRADED_CLOSED": "(simulazione) chiusa",
    }


def _reason_it() -> dict[str, str]:
    return {
        "MISSING_PRICE_T1_ASOF": "Manca il prezzo del primo giorno utile dopo il segnale entro l’AS-OF",
        "TTL_EXPIRED": "Finestra di ingresso scaduta (TTL=0)",
        "TRADE_OPEN": "Simulazione presente: posizione ancora aperta a questa data AS-OF",
        "TRADE_CLOSED": "Simulazione presente: posizione gia' chiusa a questa data AS-OF",
        "ENTRY_WINDOW_OPEN": "Finestra di ingresso aperta oggi (TTL=0)",
        "BLOCKED_PROVENANCE": "NON OK: provenienza incompleta (mai operabile)",
    }


def _db_exists(p: Path) -> bool:
    try:
        return p.exists() and p.stat().st_size > 0
    except Exception:
        return False


def _infer_default_now_date(db_path: Path, universe_id: str) -> date:
    """Default now_date = max(recs.date) (best-effort)."""
    if duckdb is None or not _db_exists(db_path):
        return date.today()

    uid = (universe_id or "ALL").strip() or "ALL"
    try:
        con = duckdb.connect(database=str(db_path), read_only=True)
        try:
            if uid.upper() == "ALL":
                row = con.execute("SELECT MAX(date) FROM recs").fetchone()
            else:
                row = con.execute("SELECT MAX(date) FROM recs WHERE universe_id = ?", [uid]).fetchone()
            if row and row[0]:
                return row[0]
        finally:
            con.close()
    except Exception:
        return date.today()
    return date.today()


def _normalize_rating(raw: object) -> str:
    """Normalizza il campo rating (grezzo) in categorie piu' leggibili.

    Nota: manteniamo anche il grezzo (opzionale). Questa normalizzazione e' solo per UI.
    """
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s:
        return ""

    lo = s.lower()

    # Varianti "live" (es. "Live-Buy")
    if ("live" in lo) and ("buy" in lo):
        return "Buy"

    # Fonti che troncono: "Upgrad" ecc.
    if lo.startswith("upgrad"):
        return "Upgrade"
    if lo.startswith("downgrad"):
        return "Downgrade"

    if "initi" in lo:
        return "Inizio copertura"  # initiated coverage

    # Rating comuni
    if lo in {"buy", "strong buy", "outperform", "overweight"}:
        return "Buy"
    if lo in {"hold", "neutral"}:
        return "Hold"
    if lo in {"sell", "underperform", "underweight"}:
        return "Sell"

    return s


def _rating_score(norm: str) -> int:
    """Punteggio di priorita' per dedup decisionale.

    Obiettivo: 1 riga per ticker/giorno (Trading Room), scegliendo l'alert piu'
    informativo e coerente.

    Scala (indicativa): Buy/Upgrade > Hold > Downgrade/Sell.
    """

    s = (norm or "").strip().lower()
    if not s:
        return 0
    if s == "buy":
        return 30
    if s == "upgrade":
        return 20
    if s == "inizio copertura":
        return 15
    if s == "hold":
        return 5
    if s == "downgrade":
        return -10
    if s == "sell":
        return -20
    return 0


def _status_score(code: str) -> int:
    """Priorita' di stato per dedup."""
    c = (code or "").strip().upper()
    if c == "TRADABLE":
        return 100
    if c == "WAITLIST":
        return 50
    if c == "EXPIRED":
        return 10
    if c == "TRADED_CLOSED":
        return 80
    if c == "TRADED_OPEN":
        return 70
    return 0


def _dedup_trading_room(df_raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Dedup per Trading Room: 1 riga per (signal_date, ticker).

    Ritorna:
      - df_view: tabella deduplicata (una riga per ticker/giorno)
      - df_map:  mappa righe originali con chiave `_dedup_key` (per drill-down)
    """

    df = df_raw.copy()
    if df.empty:
        return df, df

    # Normalizzazioni per ranking
    df["_rating_norm"] = df.get("rating", "").apply(_normalize_rating)
    df["_rating_score"] = df["_rating_norm"].apply(_rating_score)
    df["_status_score"] = df.get("status", "").apply(_status_score)
    df["_prov"] = df.get("provenance_ok", 0).fillna(0).astype(int)
    df["_pub"] = pd.to_datetime(df.get("published_at"), errors="coerce")

    df["_dedup_key"] = df["signal_date"].astype(str) + "|" + df["ticker"].astype(str)

    # Aggregati utili
    grp = df.groupby("_dedup_key", dropna=False)
    agg = grp.agg(
        signal_date=("signal_date", "first"),
        ticker=("ticker", "first"),
        n_alert=("ticker", "size"),
        sources=("firm", lambda x: ", ".join(sorted({str(v) for v in x if pd.notna(v)}))),
        any_provenance_ok=("_prov", "max"),
        intended_entry_date=("intended_entry_date", "max"),
        status=("status", lambda x: max(x, key=_status_score)),
    ).reset_index(drop=True)

    # Scegli riga "migliore" per mostrare headline/url/valutazione
    df_sorted = df.sort_values(
        by=["_dedup_key", "_prov", "_status_score", "_rating_score", "_pub"],
        ascending=[True, False, False, False, False],
        kind="mergesort",
    )
    best = df_sorted.drop_duplicates(subset=["_dedup_key"], keep="first")
    keep_cols = [
        "_dedup_key",
        "signal_date",
        "ticker",
        "firm",
        "rating",
        "sentiment_score",
        "headline",
        "source_url",
        "published_at",
        "ticker_original",
        "universe_id",
        "provenance_ok",
        "reason_code",
    ]

    best_keep = best[[c for c in keep_cols if c in best.columns]].copy()

    # Merge best-fields nel dedup
    out = agg.merge(
        best_keep,
        left_on=["signal_date", "ticker"],
        right_on=["signal_date", "ticker"],
        how="left",
        suffixes=("", "_best"),
    )

    # Override: provenance_ok = any_provenance_ok (Trading Room: basta una fonte tracciabile)
    out["provenance_ok"] = out["any_provenance_ok"].fillna(0).astype(int)

    # Operabile oggi per ticker/giorno
    out["operabile_oggi"] = ((out["status"] == "TRADABLE") & (out["provenance_ok"] == 1)).astype(int)
    out["tradable_ok"] = out["operabile_oggi"].astype(int)
    out["tradable_blocked"] = ((out["status"] == "TRADABLE") & (out["provenance_ok"] == 0)).astype(int)

    # Reason_code coerente a livello ticker/giorno
    def _reason_row(r):
        if r["status"] == "WAITLIST":
            return "MISSING_PRICE_T1_ASOF"
        if r["status"] == "EXPIRED":
            return "TTL_EXPIRED"
        if r["status"] == "TRADABLE" and int(r["provenance_ok"] or 0) == 0:
            return "BLOCKED_PROVENANCE"
        if r["status"] == "TRADABLE":
            return "ENTRY_WINDOW_OPEN"
        return str(r.get("reason_code") or "")

    out["reason_code"] = out.apply(_reason_row, axis=1)

    # Firm visualizzata: se piu' sorgenti, mostra la lista; altrimenti la singola
    out["firm"] = out["sources"].where(out["sources"].astype(str).str.len() > 0, out.get("firm"))

    # Ordinamento
    out = out.sort_values(by=["signal_date", "ticker"], ascending=[False, True], kind="mergesort")

    # df_map per drill-down (mantiene tutte le righe originali con _dedup_key)
    df_map = df_raw.copy()
    df_map["_dedup_key"] = df_raw["signal_date"].astype(str) + "|" + df_raw["ticker"].astype(str)
    return out, df_map


def _plot_timeline(view_df: pd.DataFrame, mode: str, status_it: dict[str, str]) -> None:
    """Grafico timeline (14gg): conteggi per giorno e stato."""
    assert st is not None

    if alt is None:
        st.info("Altair non disponibile: grafico timeline disabilitato.")
        return

    if view_df is None or view_df.empty:
        return

    # Conteggi
    tmp = view_df.copy()
    tmp["signal_date"] = pd.to_datetime(tmp["signal_date"], errors="coerce")
    tmp = tmp.dropna(subset=["signal_date", "status"])
    if tmp.empty:
        return

    cts = (
        tmp.groupby(["signal_date", "status"], dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values(["signal_date", "status"], kind="mergesort")
    )
    cts["stato"] = cts["status"].map(status_it).fillna(cts["status"].astype(str))

    title = "Timeline (conteggi per giorno e stato)"
    subtitle = "Trading Room" if mode == "trading" else "Backtest (simulazione as-of)"

    chart = (
        alt.Chart(cts)
        .mark_bar()
        .encode(
            x=alt.X("yearmonthdate(signal_date):T", title="Data segnale"),
            y=alt.Y("count:Q", title="Numero"),
            color=alt.Color("stato:N", title="Stato"),
            tooltip=[
                alt.Tooltip("yearmonthdate(signal_date):T", title="Data"),
                alt.Tooltip("stato:N", title="Stato"),
                alt.Tooltip("count:Q", title="Conteggio"),
            ],
        )
        .properties(height=260, title={"text": title, "subtitle": subtitle})
    )

    st.altair_chart(chart, use_container_width=True)


def _render_legend(mode: str) -> None:
    """Legenda testuale (solo Markdown, no HTML) per evitare ambiguita'."""
    assert st is not None

    if mode == "trading":
        bullets = [
            "**Tradabile oggi**: oggi e' il primo giorno utile dopo il segnale (TTL=0)",
            "**Scaduto**: finestra di ingresso persa (oggi > intended_entry_date)",
            "**In attesa dati**: manca il prezzo t+1 entro l'AS-OF (intended_entry_date non determinabile)",
        ]
        extra = "Backtest: ignorato in questa modalita'. La Trading Room mostra solo opportunita' e qualita' dati."
    else:
        bullets = [
            "**Tradabile (TTL=0, as-of)**: finestra di ingresso aperta alla data AS-OF",
            "**Scaduto**: finestra di ingresso persa (TTL=0)",
            "**In attesa dati**: manca il prezzo t+1 entro l'AS-OF",
            "**Simulazione: aperta**: esiste un trade ma l'uscita (sell_date) e' futura rispetto all'AS-OF",
            "**Simulazione: chiusa**: uscita (sell_date) <= AS-OF",
        ]
        extra = "Nota: 'Simulazione aperta' non e' un trade live; indica solo che sell_date e' successiva alla data AS-OF."

    st.markdown("**Legenda (TTL=0 / AS-OF)**")
    for b in bullets:
        st.markdown(f"- {b}")

    st.caption(
        "Provenienza: un alert e' OK solo se ha headline + source_url + published_at. "
        "Se e' NON OK, non deve mai diventare operabile."
    )
    st.caption(
        "Sorgente: NEWS-ALPHA indica un segnale generato dal lane news (RSS/GDELT). "
        "Altrimenti e' un'istituzione (es. Citi, JPMorgan...)."
    )
    st.caption(extra)



def main() -> None:
    assert st is not None
    st.set_page_config(page_title="Monitor Lifecycle", layout="wide")

    st.title("Monitor Lifecycle (AS-OF / TTL=0)")
    st.caption(
        "Vista deterministica per Trading Room (opportunita') o Backtest (simulazioni as-of). "
        "Postcast/exit policy non inclusi in questa fase."
    )

    # --- Sidebar controls ---
    st.sidebar.header("Parametri")

    mode_label = st.sidebar.radio(
        "Modalita'",
        options=["Trading Room (decisionale)", "Backtest (simulazione)"],
        index=0,
        help=(
            "Trading Room: ignora audit_trades e mostra solo TRADABLE/WAITLIST/EXPIRED. "
            "Backtest: include audit_trades e mostra Simulazione aperta/chiusa as-of."
        ),
    )
    mode = "backtest" if mode_label.startswith("Backtest") else "trading"

    db_path_str = st.sidebar.text_input("Percorso DB", value=str(DEFAULT_DB))
    universe_id = st.sidebar.text_input("Universo", value="ALL")

    db_path = Path(db_path_str).expanduser()

    default_now = _infer_default_now_date(db_path, universe_id)
    now_date = st.sidebar.date_input(
        "Data AS-OF (oggi simulato)",
        value=default_now,
        help=(
            "Data osservata per la classificazione deterministica (AS-OF). "
            "La tradabilita' e' TTL=0: un segnale e' tradabile solo su intended_entry_date (T+1)."
        ),
    )
    lookback_days = st.sidebar.slider("Finestra (giorni)", min_value=1, max_value=60, value=14, step=1)
    only_today = st.sidebar.checkbox(
        "Solo segnali con signal_date == AS-OF",
        value=False,
        help="Mostra solo i segnali registrati esattamente nella data AS-OF selezionata.",
    )

    show_raw_rating = st.sidebar.checkbox(
        "Mostra 'Valutazione (grezza)'",
        value=False,
        help="Utile per audit/debug (es. stringhe tronche). In Trading Room spesso e' rumore.",
    )

    # Dedup decisionale
    dedup_ticker_day = False
    timeline_basis = "Per ticker (aggregato)"
    if mode == "trading":
        dedup_ticker_day = st.sidebar.checkbox(
            "Aggrega per ticker/giorno (consigliato)",
            value=True,
            help=(
                "Riduce rumore: 1 riga per (data segnale, ticker). "
                "La riga mostra anche quante notizie/alert sono stati aggregati. "
                "Il dettaglio resta consultabile." 
            ),
        )
        timeline_basis = st.sidebar.selectbox(
            "Timeline: conteggi",
            options=["Per ticker (aggregato)", "Per alert (grezzo)"],
            index=0,
            help="In Trading Room, 'Per ticker' evita di gonfiare i volumi quando ci sono piu' news sullo stesso titolo.",
        )
    else:
        timeline_basis = st.sidebar.selectbox(
            "Timeline: conteggi",
            options=["Per alert (grezzo)", "Per ticker (aggregato)"],
            index=0,
            help="In Backtest, per default mostriamo i record grezzi; puoi aggregare per ticker/giorno per una vista sintetica.",
        )

    st.sidebar.divider()
    st.sidebar.header("Navigazione")
    try:
        st.sidebar.page_link("pages/00_Decision_Briefing.py", label="Decision Briefing")
        st.sidebar.page_link("pages/06_Forecasts_Ranking.py", label="Forecast & Ranking")
        st.sidebar.page_link("pages/02_Gates_Data_Quality.py", label="Gate / Qualita' dati")
        st.sidebar.page_link("pages/04_Trades_Equity.py", label="Backtest: Trades & Equity")
    except Exception:
        pass

    if duckdb is None:
        st.error("DuckDB non disponibile nell'ambiente. Installa le dipendenze per usare questa pagina.")
        return
    if not _db_exists(db_path):
        st.error(f"DB non trovato o vuoto: {db_path}")
        return

    # --- Load lifecycle ---
    con = duckdb.connect(database=str(db_path), read_only=True)
    try:
        params = LifecycleParams(
            universe_id=universe_id,
            now_date=now_date,
            lookback_days=int(lookback_days),
            only_signal_date_equals_now=bool(only_today),
            include_audit_trades=(mode == "backtest"),
        )
        df = compute_alert_lifecycle(con, params)
    finally:
        try:
            con.close()
        except Exception:
            pass

    if df is None or df.empty:
        st.warning("Nessun alert nel periodo selezionato (o nessun ticker eleggibile nell'universo).")
        return

    df_raw = df

    # --- Dedup / aggregazioni (senza cambiare i dati sottostanti) ---
    # - df_table: guida tabella e metriche
    # - df_timeline: guida il grafico timeline
    df_dedup: pd.DataFrame | None = None
    df_map = df_raw

    need_dedup = (mode == "trading" and dedup_ticker_day) or timeline_basis.startswith("Per ticker")
    if need_dedup:
        df_dedup, df_map = _dedup_trading_room(df_raw)

    df_table = df_dedup if (mode == "trading" and dedup_ticker_day and df_dedup is not None) else df_raw
    df_timeline = df_dedup if (timeline_basis.startswith("Per ticker") and df_dedup is not None) else df_raw

    status_it = _status_it(mode)
    reason_it = _reason_it()

    # --- Layout: progressive disclosure (Executive → Operativo → Tecnico) ---
    tab_exec, tab_ops, tab_tech = st.tabs(["Executive", "Operativo", "Tecnico"])

    # ===== Executive =====
    with tab_exec:
        st.subheader("Sintesi (decisionale)")
        st.caption(
            "La Trading Room e' decisionale (non consulta audit_trades). "
            "La modalita' Backtest e' simulazione esplicita (DR-5). "
            "Entry TTL=0: tradabile solo su intended_entry_date (T+1) rispetto al segnale (DR-4)."
        )

        with st.expander("Glossario e legenda (AS-OF / TTL=0 / Provenienza)", expanded=False):
            _render_legend(mode)
            st.markdown(
                """
**Definizioni operative (deterministiche)**
- **AS-OF (data osservata)**: la data su cui si calcola lo stato. Nessun utilizzo di informazioni future.
- **TTL=0 (Entry)**: la finestra di ingresso dura 1 solo giorno di borsa: **intended_entry_date** (T+1).
- **intended_entry_date**: primo giorno di mercato utile dopo **signal_date** (calcolato su prezzi, AS-OF safe).
- **Provenienza OK**: headline + source_url + published_at presenti. Se NON OK: record non operabile (vincolo "zero dati di prova").
"""
            )

        # KPI
        total = int(len(df_table))
        operabili = int(df_table.get("operable_today", df_table.get("operabile_oggi", 0)).sum())
        tradable_blocked = int(df_table.get("tradable_blocked", 0).sum())
        waitlist = int((df_table["status"] == "WAITLIST").sum())
        expired = int((df_table["status"] == "EXPIRED").sum())

        if mode == "backtest":
            sim_open = int((df_table["status"] == "TRADED_OPEN").sum())
            sim_closed = int((df_table["status"] == "TRADED_CLOSED").sum())
            c1, c2, c3, c4, c5, c6 = st.columns(6)
            c1.metric("Totale", total)
            c2.metric("Operabili oggi (OK)", operabili)
            c3.metric("In attesa dati", waitlist)
            c4.metric("Scaduti", expired)
            c5.metric("Simulazione: aperti", sim_open)
            c6.metric("Simulazione: chiusi", sim_closed)
            st.info(
                "Backtest: 'Simulazione aperta' significa sell_date > AS-OF. "
                "Non e' un trade live, e non deve essere usato come suggerimento operativo."
            )
        else:
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Totale", total)
            c2.metric("Operabili oggi (OK)", operabili)
            c3.metric("Bloccati (provenienza)", tradable_blocked)
            c4.metric("In attesa dati", waitlist)
            c5.metric("Scaduti", expired)

        if mode == "trading" and dedup_ticker_day:
            st.caption(
                f"Vista aggregata: 1 riga per ticker/giorno. Alert grezzi nel periodo: {len(df_raw)}. "
                f"Righe aggregate: {len(df_table)}."
            )

        st.subheader(f"Timeline (ultimi {int(lookback_days)} giorni)")
        st.caption(
            "Conteggi per giorno e stato. In Trading Room e' consigliato aggregare per ticker/giorno "
            "per evitare duplicazioni dovute a piu' news sullo stesso titolo."
        )
        _plot_timeline(df_timeline, mode=mode, status_it=status_it)

    # ===== Operativo =====
    with tab_ops:
        st.subheader("Operativo (filtri + tabella)")
        st.caption(
            "Obiettivo: identificare rapidamente i segnali operabili oggi (TTL=0) e distinguere blocchi dati "
            "(provenienza NON OK) da right-censoring (WAITLIST: manca prezzo T+1 as-of)."
        )

        preset = st.radio(
            "Vista operativa",
            options=[
                "Tutti",
                "Operabili oggi (OK)",
                "Tradabili ma bloccati (provenienza NON OK)",
                "In attesa dati (WAITLIST)",
                "Scaduti (EXPIRED)",
            ],
            index=0,
            horizontal=True,
            help="Filtro aggiuntivo deterministico per triage rapido. Non modifica i dati; restringe solo la vista.",
        )

        fcols = st.columns(4)

        # Stato (dinamico)
        if mode == "backtest":
            status_label_to_code = {
                "(tutti)": "(all)",
                "Tradabile (TTL=0, as-of)": "TRADABLE",
                "Scaduto": "EXPIRED",
                "In attesa dati": "WAITLIST",
                "Simulazione: aperta": "TRADED_OPEN",
                "Simulazione: chiusa": "TRADED_CLOSED",
            }
        else:
            status_label_to_code = {
                "(tutti)": "(all)",
                "Tradabile oggi": "TRADABLE",
                "Scaduto": "EXPIRED",
                "In attesa dati": "WAITLIST",
            }

        status_opts = list(status_label_to_code.keys())
        status_sel_label = fcols[0].selectbox(
            "Stato",
            options=status_opts,
            index=0,
            help="Filtra per stato lifecycle calcolato AS-OF e coerente con TTL=0.",
        )
        status_sel = status_label_to_code.get(status_sel_label, "(all)")

        # Provenienza
        prov_sel = fcols[1].selectbox(
            "Provenienza",
            options=["(tutte)", "Solo OK", "Solo NON OK"],
            index=0,
            help="Provenienza OK richiede headline+source_url+published_at. NON OK = mai operabile.",
        )

        # Filtri rapidi (robusti) — multiselect con ricerca
        tickers = sorted([x for x in df_table["ticker"].dropna().unique().tolist()])
        sources = sorted([x for x in df_table["firm"].dropna().unique().tolist()])
        ticker_sel = fcols[2].multiselect(
            "Filtro ticker",
            options=tickers,
            default=[],
            help="Selezione multipla (ricerca inclusa).",
        )
        source_sel = fcols[3].multiselect(
            "Filtro sorgente",
            options=sources,
            default=[],
            help="Origine: 'NEWS-ALPHA' = lane news; altrimenti istituzione (Citi, JPMorgan...).",
        )

        # --- Apply filters ---
        view = df_table.copy()
        if status_sel != "(all)":
            view = view[view["status"] == status_sel]

        if prov_sel == "Solo OK":
            view = view[view["provenance_ok"] == 1]
        elif prov_sel == "Solo NON OK":
            view = view[view["provenance_ok"] == 0]

        if ticker_sel:
            view = view[view["ticker"].isin(ticker_sel)]
        if source_sel:
            view = view[view["firm"].isin(source_sel)]

        # Preset operativo (post-filtri manuali)
        if preset != "Tutti":
            prov_ok = view.get("provenance_ok", 0).fillna(0).astype(int)
            is_tradable = (view["status"] == "TRADABLE")
            is_waitlist = (view["status"] == "WAITLIST")
            is_expired = (view["status"] == "EXPIRED")
            oper_col = (
                "operable_today" if "operable_today" in view.columns else ("operabile_oggi" if "operabile_oggi" in view.columns else "")
            )
            if preset == "Operabili oggi (OK)":
                if oper_col:
                    view = view[view[oper_col].fillna(0).astype(int) == 1]
                else:
                    view = view[is_tradable & (prov_ok == 1)]
            elif preset == "Tradabili ma bloccati (provenienza NON OK)":
                view = view[is_tradable & (prov_ok == 0)]
            elif preset == "In attesa dati (WAITLIST)":
                view = view[is_waitlist]
            elif preset == "Scaduti (EXPIRED)":
                view = view[is_expired]

        # --- Display: translate headers and values ---
        disp = view.copy()
        disp["stato"] = disp["status"].map(status_it).fillna(disp["status"].astype(str))
        disp["provenienza"] = disp["provenance_ok"].apply(lambda x: "OK" if int(x or 0) == 1 else "NON OK")
        disp["motivo"] = disp["reason_code"].map(reason_it).fillna(disp["reason_code"].astype(str))
        disp["rating_grezzo"] = disp.get("rating", "").astype(str)
        disp["valutazione"] = disp["rating_grezzo"].apply(_normalize_rating)
        disp["operabile_oggi"] = disp.get("operable_today", disp.get("operabile_oggi", 0)).apply(
            lambda x: "SI" if int(x or 0) == 1 else "NO"
        )

        # Columns (Italian) - dinamiche per modalita'
        show_cols: list[tuple[str, str]] = [
            ("signal_date", "Data segnale"),
            ("ticker", "Ticker"),
            ("n_alert", "N notizie"),
            ("firm", "Sorgente"),
            ("valutazione", "Valutazione"),
        ]
        if show_raw_rating:
            show_cols.append(("rating_grezzo", "Valutazione (grezza)"))

        show_cols += [
            ("operabile_oggi", "Operabile oggi"),
            ("stato", "Stato"),
            ("provenienza", "Provenienza"),
            ("intended_entry_date", "Data ingresso prevista"),
        ]

        if mode == "backtest":
            # Informazioni di simulazione
            for src, dst in [
                ("buy_date", "Data acquisto"),
                ("sell_date", "Data vendita"),
                ("net_return_pct", "Rendimento netto %"),
            ]:
                if src in disp.columns:
                    show_cols.append((src, dst))

        show_cols.append(("motivo", "Motivo"))

        # Build final table
        table = pd.DataFrame()
        for src, dst in show_cols:
            if src in disp.columns:
                table[dst] = disp[src]

        # Column tooltips (Streamlit column_config)
        colcfg_all = {
            "N notizie": st.column_config.NumberColumn(help="Numero di alert/news aggregati in questa riga (solo in vista aggregata)."),
            "Data segnale": st.column_config.DateColumn(help="Data (giorno) in cui il segnale e' stato registrato."),
            "Sorgente": st.column_config.TextColumn(help="Origine del segnale. 'NEWS-ALPHA' = lane news; altrimenti istituzione (Citi, JPMorgan...)."),
            "Valutazione": st.column_config.TextColumn(help="Valutazione normalizzata per leggibilita' (es. Upgrad -> Upgrade, Initiated -> Inizio copertura)."),
            "Valutazione (grezza)": st.column_config.TextColumn(help="Valutazione originale dalla sorgente (audit). Può essere tronca (es. 'Upgrad')."),
            "Operabile oggi": st.column_config.TextColumn(help="SI solo se: Stato tradabile oggi (TTL=0) e Provenienza OK."),
            "Stato": st.column_config.TextColumn(help="Lifecycle con TTL=0, calcolato in modo AS-OF safe (no future leak)."),
            "Provenienza": st.column_config.TextColumn(help="OK solo se headline+source_url+published_at sono presenti. NON OK = mai operabile."),
            "Data ingresso prevista": st.column_config.DateColumn(help="Primo giorno di trading utile dopo il segnale (as-of safe)."),
            "Data acquisto": st.column_config.DateColumn(help="(Backtest) Data buy in audit_trades."),
            "Data vendita": st.column_config.DateColumn(help="(Backtest) Data sell in audit_trades. Se > AS-OF, la simulazione risulta 'aperta' as-of."),
            "Rendimento netto %": st.column_config.NumberColumn(help="(Backtest) Net return % (dopo costi)."),
            "Motivo": st.column_config.TextColumn(help="Spiegazione sintetica (es. manca prezzo t+1 as-of, TTL scaduto, simulazione presente...)."),
        }
        colcfg = {k: v for k, v in colcfg_all.items() if k in table.columns}

        st.caption(f"Righe mostrate: {len(table)} su {len(df_table)} (dopo filtri).")
        st.dataframe(table, use_container_width=True, height=520, hide_index=True, column_config=colcfg)

    # ===== Tecnico =====
    with tab_tech:
        st.subheader("Tecnico (drill-down + glossari)")
        st.caption(
            "Contenuti di audit/diagnostica. "
            "In Trading Room non si consultano audit_trades (DR-5): le informazioni backtest sono visibili solo in modalita' Backtest."
        )

        with st.expander("Legenda valutazioni (rating)"):
            st.markdown(
                """
Valori normalizzati (colonna **Valutazione**)
-------------------------------------------
- **Hold**: raccomandazione neutrale / mantenere
- **Buy**: raccomandazione positiva
- **Sell**: raccomandazione negativa
- **Upgrade / Downgrade**: cambio di giudizio (miglioramento/peggioramento)
- **Inizio copertura**: avvio della copertura da parte della fonte

Varianti frequenti (colonna **Valutazione (grezza)**)
----------------------------------------------------
- **Live-Buy**: variante di *Buy* (alcune fonti indicano un giudizio "live"). In UI viene normalizzato a **Buy**.
- **Upgrad**: stringa tronca di *Upgrade* (normalizzata a **Upgrade**).

Nota: alcune sorgenti producono stringhe tronche (es. **Upgrad**) che qui normalizziamo.
"""
            )

        # --- Detail (single row) ---
        with st.expander("Dettaglio (drill-down)"):
            # Chiave stabile per drill-down
            disp2 = disp.copy()
            disp2["_key"] = disp2["signal_date"].astype(str) + " | " + disp2["ticker"].astype(str)

            keys = disp2["_key"].dropna().unique().tolist()
            if not keys:
                st.info("Nessuna riga da dettagliare con i filtri attuali.")
            else:
                sel = st.selectbox("Seleziona ticker/giorno", options=keys, index=0)
                sig_date_str, ticker = [x.strip() for x in sel.split("|")[:2]]

                r = disp2[disp2["_key"] == sel].iloc[0].to_dict()

                st.markdown(
                    f"**{ticker}** — Data segnale: **{sig_date_str}** — Stato: **{status_it.get(r.get('status'), r.get('status'))}**"
                )

                st.write(
                    {
                        "Modalita'": "Backtest (simulazione)" if mode == "backtest" else "Trading Room (decisionale)",
                        "Sorgente": r.get("firm"),
                        "N notizie": r.get("n_alert"),
                        "Valutazione": r.get("valutazione"),
                        "Valutazione (grezza)": r.get("rating_grezzo"),
                        "Operabile oggi": r.get("operabile_oggi"),
                        "Ingresso previsto": r.get("intended_entry_date"),
                        "Provenienza": r.get("provenienza"),
                        "Motivo": r.get("motivo"),
                        "Data acquisto (backtest)": r.get("buy_date"),
                        "Data vendita (backtest)": r.get("sell_date"),
                        "Rendimento netto % (backtest)": r.get("net_return_pct"),
                        "Headline": r.get("headline"),
                        "URL sorgente": r.get("source_url"),
                        "Pubblicato il": r.get("published_at"),
                    }
                )

                # Se abbiamo una mappa (dedup), mostra tutte le righe originali per quel ticker/giorno
                try:
                    raw_key = sig_date_str + "|" + ticker
                    if "_dedup_key" in df_map.columns:
                        raw_rows = df_map[df_map["_dedup_key"] == raw_key].copy()
                    else:
                        raw_rows = df_raw[(df_raw["signal_date"].astype(str) == sig_date_str) & (df_raw["ticker"] == ticker)].copy()

                    if not raw_rows.empty and (dedup_ticker_day or timeline_basis.startswith("Per ticker")):
                        st.markdown("**Dettaglio notizie/alert aggregati**")
                        raw_rows = raw_rows.sort_values(by=["published_at"], ascending=False, kind="mergesort")
                        raw_disp = raw_rows.copy()
                        raw_disp["Valutazione"] = raw_disp.get("rating", "").apply(_normalize_rating)
                        raw_disp["Provenienza"] = raw_disp.get("provenance_ok", 0).apply(
                            lambda x: "OK" if int(x or 0) == 1 else "NON OK"
                        )
                        raw_disp = raw_disp[
                            [
                                c
                                for c in [
                                    "signal_date",
                                    "ticker",
                                    "firm",
                                    "Valutazione",
                                    "published_at",
                                    "headline",
                                    "source_url",
                                    "Provenienza",
                                ]
                                if c in raw_disp.columns
                            ]
                        ]
                        st.dataframe(raw_disp, use_container_width=True, hide_index=True, height=240)
                except Exception:
                    pass


if __name__ == "__main__":
    if st is None:  # pragma: no cover
        raise SystemExit("streamlit is required to run this page")
    main()
