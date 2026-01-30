from __future__ import annotations

from src.risk.risk_engine import ProposedOrder, RiskConfig, apply_risk_gate


def test_risk_gate_allows_one_and_rejects_when_cash_reserve_bind():
    orders = [
        ProposedOrder(ticker="AAA", side="BUY", ref_price=100.0),
        ProposedOrder(ticker="BBB", side="BUY", ref_price=100.0),
    ]

    cfg = RiskConfig(max_positions=10, cash_reserve_pct=0.2, max_position_pct=0.6, risk_scalar=1.0)
    out = apply_risk_gate(orders, starting_cash=1000.0, cfg=cfg)

    assert len(out) == 2
    assert out[0].allowed is True
    assert out[1].allowed is False
    assert out[1].reason_code == "CASH_RESERVE"


def test_risk_gate_rejects_max_positions():
    orders = [ProposedOrder(ticker="AAA", side="BUY", ref_price=10.0)]
    cfg = RiskConfig(max_positions=0, cash_reserve_pct=0.0, max_position_pct=1.0, risk_scalar=1.0)
    out = apply_risk_gate(orders, starting_cash=1000.0, cfg=cfg)
    assert out[0].allowed is False
    assert out[0].reason_code == "MAX_POSITIONS"
