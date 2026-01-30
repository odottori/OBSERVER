from __future__ import annotations

"""Generate a simple execution bulletin from the most recent recommendations.

This is intentionally *not* a look-ahead optimizer.
It prints recent signals and their associated universe/market metadata.

If you want a ranked bulletin, add a forward-looking scoring model (e.g., firm
reliability computed only on history strictly prior to the signal date) and
apply it here.
"""

import os
from datetime import datetime, timedelta

import duckdb

from src.db.migrate import ensure_schema


def generate_bulletin(days: int = 1, out_dir: str = "reports") -> str:
    db_path = os.path.join("data", "sentinel_alpha.db")
    con = duckdb.connect(database=db_path)
    ensure_schema(con)

    cutoff = (datetime.now() - timedelta(days=days)).date()
    df = con.execute(
        """
        SELECT r.date, r.ticker, r.firm, r.rating, m.market, m.sector, r.headline
        FROM recs r
        LEFT JOIN metadata m ON m.ticker = r.ticker
        WHERE r.date >= ?
        ORDER BY r.date DESC, r.ticker ASC
        """,
        [cutoff],
    ).df()
    con.close()

    os.makedirs(out_dir, exist_ok=True)
    filename = os.path.join(out_dir, f"MORNING_BULLETIN_{datetime.now().strftime('%Y%m%d_%H%M')}.txt")

    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"SENTINEL-ALPHA: RECENT SIGNALS (last {days} day(s))\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write("=" * 72 + "\n\n")

        if df.empty:
            f.write("No recent signals.\n")
        else:
            for _, row in df.iterrows():
                f.write(f"DATE: {row['date']} | TICKER: {row['ticker']} | FIRM: {row['firm']} | RATING: {row['rating']}\n")
                f.write(f"MARKET: {row.get('market', '')} | SECTOR: {row.get('sector', '')}\n")
                if row.get("headline"):
                    f.write(f"HEADLINE: {row['headline']}\n")
                f.write("-" * 72 + "\n")

    return filename


if __name__ == "__main__":
    path = generate_bulletin(days=1)
    print(f"[+] Bulletin written: {path}")
