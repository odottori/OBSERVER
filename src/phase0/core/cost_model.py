from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    """Simple, conservative round-trip cost model.

    Parameters are expressed as fractions of notional, e.g. 0.0075 = 0.75%.
    """

    round_trip_cost_pct: float = 0.0075

    def cost_pct(self) -> float:
        return max(0.0, float(self.round_trip_cost_pct))

    def entry_cost_pct(self) -> float:
        """Entry-side costs as fraction of notional.

        We split the round-trip penalty symmetrically.
        """

        return self.cost_pct() / 2.0

    def exit_cost_pct(self) -> float:
        """Exit-side costs as fraction of notional."""

        return self.cost_pct() / 2.0

    def entry_cost(self, notional: float) -> float:
        return float(notional) * self.entry_cost_pct()

    def exit_cost(self, notional: float) -> float:
        return float(notional) * self.exit_cost_pct()

    def apply_to_return_pct(self, gross_return_pct: float) -> float:
        """Apply costs to a gross return expressed in percent."""
        return float(gross_return_pct) - (self.cost_pct() * 100.0)
