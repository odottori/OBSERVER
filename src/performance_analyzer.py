from __future__ import annotations

"""Performance analyzer (uses the audit engine).

This module is intentionally lightweight and avoids any nearest-price selection.
"""

import os

import matplotlib.pyplot as plt

from src.intelligence_engine import IntelligenceEngine


class SentinelBacktester:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or os.path.join("data", "sentinel_alpha.db")
        self.engine = IntelligenceEngine(db_path=self.db_path)

    def run_full_backtest(self, universe_id: str = "ALL", holding_period_sessions: int = 22):
        trades = self.engine.run_deep_audit(universe_id=universe_id, holding_period_sessions=holding_period_sessions)
        equity = self.engine.apply_money_management(trades, holding_period_sessions=holding_period_sessions)

        if equity is None or equity.empty:
            print("[!] No equity curve generated (no trades / insufficient data).")
            return trades, equity

        self._generate_performance_chart(equity)
        return trades, equity

    def _generate_performance_chart(self, equity_df):
        plt.figure(figsize=(12, 6))
        plt.plot(equity_df["date"], equity_df["equity"], linewidth=2, label="Sentinel-Alpha Strategy")
        plt.axhline(equity_df["equity"].iloc[0], linestyle="--", alpha=0.5)
        plt.title("SENTINEL-ALPHA: Equity Curve (net of costs/taxes if enabled)")
        plt.xlabel("Date")
        plt.ylabel("Equity")
        plt.grid(True, alpha=0.3)
        plt.legend()

        chart_path = os.path.join("reports", "performance_track_record.png")
        os.makedirs("reports", exist_ok=True)
        plt.savefig(chart_path)
        print(f"[+] Performance chart saved: {chart_path}")
        plt.close()


if __name__ == "__main__":
    tester = SentinelBacktester()
    tester.run_full_backtest()
