from src.phase0.core.cost_model import CostModel
from src.phase0.core.tax_model import ItalianTaxModel


def test_cost_model_round_trip():
    cm = CostModel(round_trip_cost_pct=0.01)  # 1%
    assert cm.apply_to_return_pct(10.0) == 9.0


def test_italian_tax_loss_carry_offsets_future_gains():
    tx = ItalianTaxModel(capital_gains_rate=0.26)

    pnl1, tax1 = tx.apply_to_realized_pnl(-100.0)
    assert pnl1 == -100.0
    assert tax1 == 0.0

    pnl2, tax2 = tx.apply_to_realized_pnl(200.0)
    # 100 of gain is offset; taxable = 100; tax=26; after_tax = 174
    assert abs(pnl2 - 174.0) < 1e-9
    assert abs(tax2 - 26.0) < 1e-9
