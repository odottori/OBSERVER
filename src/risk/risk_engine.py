from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class RiskConfig:
    max_positions: int = 10
    cash_reserve_pct: float = 0.20
    max_position_pct: float = 0.20
    risk_scalar: float = 1.0


@dataclass(frozen=True)
class ProposedOrder:
    ticker: str
    side: str
    ref_price: float


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reason_code: str
    ticker: str
    side: str
    quantity: float
    ref_price: float


def _clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return float(x)


def apply_risk_gate(
    orders: list[ProposedOrder],
    *,
    starting_cash: float = 100000.0,
    existing_positions: dict[str, float] | None = None,
    cfg: RiskConfig | None = None,
) -> list[RiskDecision]:
    cfg = cfg or RiskConfig()
    existing_positions = existing_positions or {}

    max_positions = max(0, int(cfg.max_positions))
    reserve_pct = _clamp01(float(cfg.cash_reserve_pct))
    max_pos_pct = _clamp01(float(cfg.max_position_pct))
    scalar = max(0.0, float(cfg.risk_scalar))

    starting_cash = max(0.0, float(starting_cash))
    investable_cash = starting_cash * (1.0 - reserve_pct)

    current_positions = {str(k): float(v) for k, v in existing_positions.items() if v is not None}
    current_count = len([k for k, v in current_positions.items() if abs(v) > 0.0])

    decisions: list[RiskDecision] = []

    tickers_seen: set[str] = set()
    for o in orders:
        t = str(o.ticker)
        if t in tickers_seen:
            continue
        tickers_seen.add(t)

        side = str(o.side).upper().strip() or "BUY"
        price = float(o.ref_price)
        if price <= 0.0:
            decisions.append(RiskDecision(False, "INVALID_PRICE", t, side, 0.0, price))
            continue

        if current_count >= max_positions:
            decisions.append(RiskDecision(False, "MAX_POSITIONS", t, side, 0.0, price))
            continue

        max_notional = starting_cash * max_pos_pct
        max_notional = max(0.0, float(max_notional))
        max_notional = max_notional * scalar

        qty = math.floor(max_notional / price) if max_notional > 0.0 else 0.0
        qty = float(max(0.0, qty))
        notional = qty * price

        if notional <= 0.0:
            decisions.append(RiskDecision(False, "ZERO_QTY", t, side, 0.0, price))
            continue

        if notional > investable_cash:
            decisions.append(RiskDecision(False, "CASH_RESERVE", t, side, 0.0, price))
            continue

        investable_cash -= notional
        current_count += 1
        decisions.append(RiskDecision(True, "OK", t, side, qty, price))

    return decisions
