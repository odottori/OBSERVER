from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ItalianTaxModel:
    """Simplified Italian resident tax model for backtesting.

    This is a *simulation* model (not tax advice).

    - Capital gains tax rate (CGT): default 26%
    - Loss carry ("zainetto fiscale"): losses offset future gains

    Tobin/FTT is modeled separately as a transaction cost when applicable.
    """

    capital_gains_rate: float = 0.26

    # Loss carryforward bucket (EUR).
    loss_carry: float = 0.0

    def apply_to_realized_pnl(self, realized_pnl: float) -> tuple[float, float]:
        """Return (after_tax_pnl, tax_paid)."""

        pnl = float(realized_pnl)
        if pnl <= 0:
            self.loss_carry += abs(pnl)
            return pnl, 0.0

        # Offset gains with existing loss carry.
        offset = min(self.loss_carry, pnl)
        taxable = pnl - offset
        self.loss_carry -= offset

        tax = taxable * max(0.0, float(self.capital_gains_rate))
        after_tax = pnl - tax
        return after_tax, tax
