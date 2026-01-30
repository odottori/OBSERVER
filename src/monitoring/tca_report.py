from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import duckdb


@dataclass(frozen=True)
class TcaSummary:
    run_id: str
    n_orders: int
    n_fills: int
    avg_slippage_bp: float
    avg_fee_drag_bp: float
    avg_cost_drag_bp: float
    hit_rate_1d: float
    alert: bool


def _safe_float(x) -> float:
    try:
        if x is None:
            return 0.0
        return float(x)
    except Exception:
        return 0.0


def _safe_int(x) -> int:
    try:
        if x is None:
            return 0
        return int(x)
    except Exception:
        return 0


def compute_tca_summary(
    con: duckdb.DuckDBPyConnection,
    *,
    run_id: str | None = None,
    threshold_cost_drag_bp: float = 10.0,
) -> TcaSummary:
    rid = (run_id or '').strip()
    if rid:
        filt = 'WHERE f.run_id = ?'
        params = [rid]
        run_id_expr = 'f.run_id'
    else:
        filt = ''
        params = []
        run_id_expr = "COALESCE(f.run_id, 'UNKNOWN')"

    row = con.execute(
        f"""
        WITH fills AS (
            SELECT
                {run_id_expr} AS run_id,
                f.order_id,
                f.fill_id,
                f.ticker,
                UPPER(TRIM(COALESCE(f.side, 'BUY'))) AS side,
                CAST(f.filled_at AS DATE) AS fill_date,
                f.quantity,
                f.fill_price,
                COALESCE(f.fees, 0.0) AS fees
            FROM execution_fills f
            {filt}
        ),
        ref AS (
            SELECT
                x.*,
                p.price AS ref_price,
                (
                    SELECT MIN(p2.date)
                    FROM prices p2
                    WHERE p2.ticker = x.ticker AND p2.date > x.fill_date
                ) AS next_date
            FROM fills x
            LEFT JOIN prices p
              ON p.ticker = x.ticker AND p.date = x.fill_date
        ),
        nextp AS (
            SELECT
                r.*,
                pnext.price AS next_price
            FROM ref r
            LEFT JOIN prices pnext
              ON pnext.ticker = r.ticker AND pnext.date = r.next_date
        ),
        tca AS (
            SELECT
                run_id,
                order_id,
                fill_id,
                ticker,
                side,
                quantity,
                fill_price,
                fees,
                ref_price,
                next_price,
                CASE
                    WHEN ref_price IS NULL OR ref_price = 0 THEN NULL
                    WHEN side = 'SELL' THEN (ref_price - fill_price) / ref_price * 10000.0
                    ELSE (fill_price - ref_price) / ref_price * 10000.0
                END AS slippage_bp,
                CASE
                    WHEN fill_price IS NULL OR fill_price = 0 OR quantity IS NULL OR quantity = 0 THEN NULL
                    ELSE fees / (quantity * fill_price) * 10000.0
                END AS fee_drag_bp,
                CASE
                    WHEN next_price IS NULL OR fill_price IS NULL OR fill_price = 0 THEN NULL
                    WHEN side = 'SELL' THEN (fill_price - next_price) / fill_price
                    ELSE (next_price - fill_price) / fill_price
                END AS realized_ret_1d
            FROM nextp
        ),
        agg AS (
            SELECT
                run_id,
                COUNT(DISTINCT order_id) AS n_orders,
                COUNT(*) AS n_fills,
                AVG(slippage_bp) AS avg_slippage_bp,
                AVG(fee_drag_bp) AS avg_fee_drag_bp,
                AVG(COALESCE(slippage_bp, 0.0) + COALESCE(fee_drag_bp, 0.0)) AS avg_cost_drag_bp,
                AVG(CASE WHEN realized_ret_1d IS NULL THEN NULL WHEN realized_ret_1d > 0 THEN 1.0 ELSE 0.0 END) AS hit_rate_1d
            FROM tca
            GROUP BY run_id
        )
        SELECT
            run_id,
            n_orders,
            n_fills,
            avg_slippage_bp,
            avg_fee_drag_bp,
            avg_cost_drag_bp,
            COALESCE(hit_rate_1d, 0.0) AS hit_rate_1d
        FROM agg
        ORDER BY run_id
        LIMIT 1
        """,
        params,
    ).fetchone()

    if not row:
        return TcaSummary(
            run_id=(rid or 'UNKNOWN'),
            n_orders=0,
            n_fills=0,
            avg_slippage_bp=0.0,
            avg_fee_drag_bp=0.0,
            avg_cost_drag_bp=0.0,
            hit_rate_1d=0.0,
            alert=False,
        )

    out = TcaSummary(
        run_id=str(row[0] or (rid or 'UNKNOWN')),
        n_orders=_safe_int(row[1]),
        n_fills=_safe_int(row[2]),
        avg_slippage_bp=_safe_float(row[3]),
        avg_fee_drag_bp=_safe_float(row[4]),
        avg_cost_drag_bp=_safe_float(row[5]),
        hit_rate_1d=_safe_float(row[6]),
        alert=(_safe_float(row[5]) > float(threshold_cost_drag_bp)),
    )
    return out


def build_tca_report_text(
    con: duckdb.DuckDBPyConnection,
    *,
    run_id: str | None = None,
    threshold_cost_drag_bp: float = 10.0,
) -> str:
    s = compute_tca_summary(con, run_id=run_id, threshold_cost_drag_bp=threshold_cost_drag_bp)

    lines: list[str] = []
    lines.append(f"TCA_REPORT run_id={s.run_id}")
    lines.append(f"n_orders={s.n_orders} n_fills={s.n_fills}")
    lines.append(f"avg_slippage_bp={s.avg_slippage_bp:.2f}")
    lines.append(f"avg_fee_drag_bp={s.avg_fee_drag_bp:.2f}")
    lines.append(f"avg_cost_drag_bp={s.avg_cost_drag_bp:.2f}")
    lines.append(f"hit_rate_1d={s.hit_rate_1d:.3f}")

    if s.alert:
        lines.append(f"ALERT cost_drag_bp_gt={float(threshold_cost_drag_bp):.2f}")
    else:
        lines.append("ALERT none")

    return "\n".join(lines) + "\n"
