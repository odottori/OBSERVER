from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import uuid4

import duckdb

from src.phase0.core.cost_model import CostModel
from src.risk.risk_engine import ProposedOrder, RiskConfig, apply_risk_gate


@dataclass(frozen=True)
class PaperExecutionResult:
    run_id: str
    asof_date: date
    orders_written: int
    fills_written: int


def determine_latest_ranking_date(con: duckdb.DuckDBPyConnection) -> date | None:
    row = con.execute("SELECT MAX(date) FROM momentum_rankings").fetchone()
    if row and row[0] is not None:
        return row[0]
    row = con.execute("SELECT MAX(date) FROM recs").fetchone()
    if row and row[0] is not None:
        return row[0]
    return None


def execute_paper_broker(
    con: duckdb.DuckDBPyConnection,
    *,
    run_id: str,
    asof_date: date | None = None,
    top_n: int = 10,
    cost_model: CostModel | None = None,
    risk_cfg: RiskConfig | None = None,
    starting_cash: float = 100000.0,
) -> PaperExecutionResult:
    cost_model = cost_model or CostModel()
    if asof_date is None:
        asof_date = determine_latest_ranking_date(con)
    if asof_date is None:
        raise RuntimeError("No momentum_rankings/recs rows found: cannot determine asof_date")

    top_n = max(0, int(top_n))
    rows = con.execute("SELECT COUNT(*) FROM momentum_rankings WHERE date = ?", [asof_date]).fetchone()
    has_momentum = bool(rows and int(rows[0] or 0) > 0)

    if has_momentum:
        ranking_rows = con.execute(
            """
            SELECT ticker, rnk
            FROM momentum_rankings
            WHERE date = ?
            ORDER BY rnk ASC
            LIMIT ?
            """,
            [asof_date, top_n],
        ).fetchall()
    else:
        ranking_rows = con.execute(
            """
            SELECT ticker, MAX(COALESCE(sentiment_score, 0.0)) AS score
            FROM recs
            WHERE date = ?
            GROUP BY ticker
            ORDER BY score DESC, ticker ASC
            LIMIT ?
            """,
            [asof_date, top_n],
        ).fetchall()

    ts = datetime.now(timezone.utc)
    orders_written = 0
    fills_written = 0

    price_by_ticker: dict[str, float] = {}
    proposals: list[ProposedOrder] = []
    for ticker, _rank in ranking_rows:
        pr = con.execute(
            "SELECT price FROM prices WHERE date = ? AND ticker = ?",
            [asof_date, ticker],
        ).fetchone()
        if not pr or pr[0] is None:
            continue
        px = float(pr[0])
        price_by_ticker[str(ticker)] = px
        proposals.append(ProposedOrder(ticker=str(ticker), side="BUY", ref_price=px))

    decisions = apply_risk_gate(
        proposals,
        starting_cash=float(starting_cash),
        cfg=(risk_cfg or RiskConfig()),
    )

    for d in decisions:
        order_id = uuid4().hex
        qty = float(d.quantity)
        px = float(d.ref_price)
        status = "FILLED" if d.allowed else "REJECTED"
        notes = "paper" if d.allowed else f"paper;risk={d.reason_code}"

        con.execute(
            """
            INSERT INTO execution_orders(
                order_id, run_id, created_at, ticker, side, quantity,
                order_type, limit_price, status, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, 'MARKET', NULL, ?, ?)
            ON CONFLICT(order_id) DO NOTHING
            """,
            [order_id, run_id, ts, str(d.ticker), str(d.side), float(qty), status, notes],
        )
        orders_written += 1

        if not d.allowed:
            continue

        notional = float(qty) * float(px)
        fees = float(cost_model.entry_cost(notional))
        fill_id = uuid4().hex
        con.execute(
            """
            INSERT INTO execution_fills(
                fill_id, order_id, run_id, filled_at, ticker, side,
                quantity, fill_price, fees, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'paper')
            ON CONFLICT(fill_id) DO NOTHING
            """,
            [fill_id, order_id, run_id, ts, str(d.ticker), str(d.side), float(qty), float(px), float(fees)],
        )
        fills_written += 1

    return PaperExecutionResult(
        run_id=str(run_id),
        asof_date=asof_date,
        orders_written=int(orders_written),
        fills_written=int(fills_written),
    )
