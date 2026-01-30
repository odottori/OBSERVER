"""Alert lifecycle (TTL=0, AS-OF navigation).

Questo modulo fornisce una vista deterministica, offline-by-default, sul ciclo di vita
(degli alert / recs / signals) con supporto alla navigazione temporale (AS-OF).

Semantica chiave
----------------
- TTL = 0: un alert e' tradabile solo nel primo giorno di borsa utile dopo il giorno
  del segnale ("intended_entry_date").

- AS-OF / no-future-leak: tutte le computazioni sono vincolate a `now_date`. In
  particolare, la intended_entry_date e' calcolata come:

      intended_entry_date = MIN(prices.date)
                           WHERE prices.date > signal_date
                             AND prices.date <= now_date

  Se non esiste, l'alert e' in WAITLIST a questo `now_date`.

- Postcast / exit horizon: NON viene calcolato qui. L'uscita deve essere derivata
  (exit policy), non inventata.

Modalita'
---------
Questa vista puo' essere usata in due contesti:

- Trading Room (decisionale): considerare solo TRADABLE / WAITLIST / EXPIRED.
  In questa modalita' e' opportuno ignorare completamente `audit_trades`.

- Backtest / simulazione (storico): includere `audit_trades` e rappresentare lo
  stato della simulazione *as-of* (posizione "aperta" se sell_date > now_date).

Lo switch e' controllato da `LifecycleParams.include_audit_trades`.

Nota su provenienza
-------------------
`provenance_ok` e' un gate stretto: un alert e' OK solo se ha headline + source_url
+ published_at (non vuoti). Se NON OK, non deve mai essere operabile.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import duckdb
import pandas as pd

from src.core.ticker_normalize import normalize_ticker_sql


@dataclass(frozen=True)
class LifecycleParams:
    """Parametri per la vista lifecycle."""

    universe_id: str = "ALL"
    now_date: date = date.today()
    lookback_days: int = 14
    only_signal_date_equals_now: bool = False

    # Se False, la query NON legge audit_trades (Trading Room).
    include_audit_trades: bool = True


def _safe_universe_id(x: str | None) -> str:
    uid = (x or "ALL").strip() or "ALL"
    return uid.upper() if uid.upper() == "ALL" else uid


def compute_alert_lifecycle(con: duckdb.DuckDBPyConnection, params: LifecycleParams) -> pd.DataFrame:
    """Materializza la vista lifecycle per la finestra lookback.

    Restituisce un pandas.DataFrame (possibilmente vuoto) con ordinamento
    deterministico.
    """

    uid = _safe_universe_id(params.universe_id)
    now = params.now_date
    lookback = int(max(1, min(365, params.lookback_days)))

    # Finestra inclusiva: lookback_days=14 = oggi + 13 giorni precedenti (calendario).
    start = now - timedelta(days=lookback - 1)

    # Canonicalizzazione coerente con la lane ranking.
    r_norm = normalize_ticker_sql("rt.ticker")
    um_norm = normalize_ticker_sql("um.ticker")
    tmr_alias_norm = normalize_ticker_sql("tmr.alias_ticker")
    tmr_can_norm = normalize_ticker_sql("tmr.canonical_ticker")

    only_today = 1 if params.only_signal_date_equals_now else 0

    ctes = f"""
    WITH recs_window AS (
        SELECT
            rt.date AS signal_date,
            rt.ticker AS ticker_original,
            {r_norm} AS ticker_normalized,
            COALESCE({tmr_can_norm}, {r_norm}) AS ticker,
            rt.firm,
            rt.rating,
            rt.sentiment_score,
            rt.headline,
            rt.source_url,
            rt.published_at,
            rt.universe_id
        FROM recs rt
        LEFT JOIN ticker_mappings tmr
          ON {tmr_alias_norm} = {r_norm}
         AND (tmr.start_date IS NULL OR rt.date >= tmr.start_date)
         AND (tmr.end_date IS NULL OR rt.date <= tmr.end_date)
        WHERE rt.date BETWEEN ? AND ?
          AND ({only_today} = 0 OR rt.date = ?)
          AND (? = 'ALL' OR rt.universe_id = ?)
    ),
    eligible AS (
        SELECT rw.*
        FROM recs_window rw
        JOIN universe_membership um
          ON um.universe_id = ?
         AND {um_norm} = {normalize_ticker_sql('rw.ticker')}
         AND (um.start_date IS NULL OR rw.signal_date >= um.start_date)
         AND (um.end_date IS NULL OR rw.signal_date <= um.end_date)
    ),
    enriched AS (
        SELECT
            e.*,
            (
              SELECT MIN(p.date)
              FROM prices p
              WHERE p.ticker = e.ticker
                AND p.date > e.signal_date
                AND p.date <= ?
            ) AS intended_entry_date,
            CASE
              WHEN e.headline IS NOT NULL AND length(trim(e.headline)) > 0
               AND e.source_url IS NOT NULL AND length(trim(e.source_url)) > 0
               AND e.published_at IS NOT NULL
              THEN 1 ELSE 0
            END AS provenance_ok
        FROM eligible e
    )
    """

    if params.include_audit_trades:
        sql = ctes + """
    ,
    trades_visible AS (
        SELECT
            t.trade_id,
            t.signal_date,
            t.ticker,
            t.firm,
            t.buy_date,
            t.sell_date,
            t.gross_return_pct,
            t.net_return_pct,
            t.trade_score,
            t.exit_reason
        FROM audit_trades t
        WHERE t.buy_date IS NOT NULL
          AND t.buy_date <= ?
    )
    SELECT
        en.signal_date,
        en.ticker_original,
        en.ticker,
        en.firm,
        en.rating,
        en.sentiment_score,
        en.headline,
        en.source_url,
        en.published_at,
        en.universe_id,
        en.intended_entry_date,
        en.intended_entry_date AS entry_deadline_date,
        en.provenance_ok,
        tv.trade_id,
        tv.buy_date,
        tv.sell_date,
        tv.gross_return_pct,
        tv.net_return_pct,
        tv.trade_score,
        tv.exit_reason,
        CASE
          WHEN tv.trade_id IS NOT NULL AND (tv.sell_date IS NULL OR tv.sell_date > ?) THEN 'TRADED_OPEN'
          WHEN tv.trade_id IS NOT NULL AND tv.sell_date <= ? THEN 'TRADED_CLOSED'
          WHEN en.intended_entry_date IS NULL THEN 'WAITLIST'
          WHEN en.intended_entry_date = ? THEN 'TRADABLE'
          ELSE 'EXPIRED'
        END AS status,
        CASE
          WHEN tv.trade_id IS NOT NULL AND (tv.sell_date IS NULL OR tv.sell_date > ?) THEN 'TRADE_OPEN'
          WHEN tv.trade_id IS NOT NULL AND tv.sell_date <= ? THEN 'TRADE_CLOSED'
          WHEN en.intended_entry_date IS NULL THEN 'MISSING_PRICE_T1_ASOF'
          WHEN en.intended_entry_date = ? AND en.provenance_ok = 0 THEN 'BLOCKED_PROVENANCE'
          WHEN en.intended_entry_date = ? THEN 'ENTRY_WINDOW_OPEN'
          ELSE 'TTL_EXPIRED'
        END AS reason_code
    FROM enriched en
    LEFT JOIN trades_visible tv
      ON tv.ticker = en.ticker
     AND tv.signal_date = en.signal_date
     AND (tv.firm = en.firm OR (tv.firm IS NULL AND en.firm IS NULL))
    ORDER BY en.signal_date DESC, en.ticker ASC, en.firm ASC
        """

        args = [
            start,
            now,
            now,
            uid,
            uid,
            uid,
            now,  # prices <= now
            now,  # trades visible buy_date <= now
            now,  # status open if sell_date > now
            now,  # status closed if sell_date <= now
            now,  # status tradable if intended_entry_date == now
            now,  # reason open
            now,  # reason closed
            now,  # reason blocked
            now,  # reason entry open
        ]

    else:
        sql = ctes + """
    SELECT
        en.signal_date,
        en.ticker_original,
        en.ticker,
        en.firm,
        en.rating,
        en.sentiment_score,
        en.headline,
        en.source_url,
        en.published_at,
        en.universe_id,
        en.intended_entry_date,
        en.intended_entry_date AS entry_deadline_date,
        en.provenance_ok,
        CAST(NULL AS VARCHAR) AS trade_id,
        CAST(NULL AS DATE) AS buy_date,
        CAST(NULL AS DATE) AS sell_date,
        CAST(NULL AS DOUBLE) AS gross_return_pct,
        CAST(NULL AS DOUBLE) AS net_return_pct,
        CAST(NULL AS DOUBLE) AS trade_score,
        CAST(NULL AS VARCHAR) AS exit_reason,
        CASE
          WHEN en.intended_entry_date IS NULL THEN 'WAITLIST'
          WHEN en.intended_entry_date = ? THEN 'TRADABLE'
          ELSE 'EXPIRED'
        END AS status,
        CASE
          WHEN en.intended_entry_date IS NULL THEN 'MISSING_PRICE_T1_ASOF'
          WHEN en.intended_entry_date = ? AND en.provenance_ok = 0 THEN 'BLOCKED_PROVENANCE'
          WHEN en.intended_entry_date = ? THEN 'ENTRY_WINDOW_OPEN'
          ELSE 'TTL_EXPIRED'
        END AS reason_code
    FROM enriched en
    ORDER BY en.signal_date DESC, en.ticker ASC, en.firm ASC
        """

        args = [
            start,
            now,
            now,
            uid,
            uid,
            uid,
            now,  # prices <= now
            now,  # status tradable
            now,  # reason blocked
            now,  # reason entry open
        ]

    df = con.execute(sql, args).df()
    if df is None or df.empty:
        return pd.DataFrame()

    # Post-processing: date columns to python date for stable rendering.
    for c in (
        "signal_date",
        "intended_entry_date",
        "entry_deadline_date",
        "buy_date",
        "sell_date",
    ):
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce").dt.date

    # Coerce flags.
    if "provenance_ok" in df.columns:
        df["provenance_ok"] = df["provenance_ok"].astype(int)

    df["entry_window"] = (df["intended_entry_date"] == now).astype(int)
    df["tradable_ok"] = ((df["status"] == "TRADABLE") & (df["provenance_ok"] == 1)).astype(int)
    df["tradable_blocked"] = ((df["status"] == "TRADABLE") & (df["provenance_ok"] == 0)).astype(int)
    df["operabile_oggi"] = df["tradable_ok"].astype(int)

    return df
