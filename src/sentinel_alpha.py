"""Data ingestion entrypoint.

Important note (per user requirement):
- We keep the current 50-ticker universe and the existing data-coverage strategy.
- This module must NOT re-own schema logic; DDL lives in `src/phase0/db/migrate.py`.

`update_prices()` and `update_news()` remain optional. Many users will operate on
an already-populated local DuckDB.
"""

from __future__ import annotations

import os
from datetime import datetime

import duckdb
import pandas as pd

from src.phase0.db.migrate import ensure_schema, seed_default_universes
from src.phase0.core.sentiment import LocalSentimentScorer

# Optional dependencies (keep ingestion decoupled from audit)
try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None

try:
    import requests
    import urllib.parse
    from xml.etree import ElementTree
except Exception:  # pragma: no cover
    requests = None


def _infer_universe_id(ticker: str) -> str:
    return "EU" if "." in ticker else "US"


class SentinelAlpha:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or os.path.join("data", "sentinel_alpha.db")
        self.con = duckdb.connect(database=self.db_path)
        ensure_schema(self.con)
        seed_default_universes(self.con)

    def close(self) -> None:
        try:
            self.con.close()
        except Exception:
            pass

    def list_tickers(self, universe_id: str = "ALL") -> list[str]:
        """Return tickers registered in the dynamic membership table."""

        rows = self.con.execute(
            """
            SELECT DISTINCT ticker
            FROM universe_membership
            WHERE universe_id = ?
            ORDER BY ticker
            """,
            [universe_id],
        ).fetchall()
        return [r[0] for r in rows]

    def update_news(self, universe_id: str = "ALL") -> int:
        """Legacy lightweight news scanner (placeholder).

        Status:
        - DEPRECATED for operator usage.
        - This function performs network access and is **disabled by default**.

        Use instead: NEWS-ALPHA lane
          - `py scripts/news_alpha.py collect ...`
          - `py scripts/news_alpha.py run ...`

        To intentionally enable this legacy path you must set:
          - NEWS_ALPHA_ALLOW_ONLINE=1
        """

        # Hard guard: prevent accidental network use.
        if os.getenv("NEWS_ALPHA_ALLOW_ONLINE", "0") != "1":
            raise RuntimeError(
                "update_news() is legacy and online. It is disabled unless NEWS_ALPHA_ALLOW_ONLINE=1. "
                "Use scripts/news_alpha.py (NEWS-ALPHA lane) instead."
            )

        if requests is None:
            raise RuntimeError("requests is not available in this environment")

        tickers = set(self.list_tickers(universe_id=universe_id))
        if not tickers:
            return 0

        scorer = LocalSentimentScorer(self.con)

        headers = {"User-Agent": "Mozilla/5.0"}
        queries = ["analyst upgrade", "stock rating initiated", "price target increase"]
        found = []

        for q in queries:
            url = (
                "https://news.google.com/rss/search?q="
                + urllib.parse.quote(q)
                + "&hl=en-US&gl=US&ceid=US:en"
            )
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                tree = ElementTree.fromstring(resp.content)
                for item in tree.findall(".//item"):
                    title = item.find("title").text or ""
                    pub_dt = pd.to_datetime(item.find("pubDate").text)
                    pub_date = pub_dt.date()

                    # Simple ticker matching (kept intentionally conservative)
                    ticker = next((t for t in tickers if f" {t.split('.')[0]} " in f" {title} "), None)
                    if not ticker:
                        continue

                    sentiment = float(scorer.score_cached(title))
                    found.append(
                        [
                            pub_date,
                            ticker,
                            "Istituzionale",
                            "Buy",
                            sentiment,
                            title,
                            url,
                            _infer_universe_id(ticker),
                            pub_dt.to_pydatetime(),
                        ]
                    )
            except Exception:
                continue

        if not found:
            return 0

        df = pd.DataFrame(
            found,
            columns=[
                "date",
                "ticker",
                "firm",
                "rating",
                "sentiment_score",
                "headline",
                "source_url",
                "universe_id",
                "published_at",
            ],
        )
        self.con.register("df_live", df)
        self.con.execute(
            """
            INSERT INTO recs(date, ticker, firm, rating, sentiment_score, headline, source_url, universe_id, published_at)
            SELECT date, ticker, firm, rating, sentiment_score, headline, source_url, universe_id, published_at
            FROM df_live
            ON CONFLICT(date, ticker, firm) DO NOTHING
            """
        )
        return len(df)

    def update_prices(self, universe_id: str = "ALL", years: int = 10) -> int:
        """Optional price sync.

        NOTE: This function is NOT part of the audit contract.

        Price policy:
        - Uses *unadjusted* OHLC from yfinance (auto_adjust=False) to avoid hiding dividends/splits inside prices.
        - This aligns with the audit engine and the multi-provider backfiller.
        Your existing data acquisition solution can keep populating `prices`.
        """

        if yf is None:
            raise RuntimeError("yfinance is not available in this environment")

        tickers = self.list_tickers(universe_id=universe_id)
        if not tickers:
            return 0

        start_h = (datetime.now() - pd.DateOffset(years=years)).date()
        df = yf.download(tickers, start=start_h, progress=False, auto_adjust=False, threads=False)
        if df is None or df.empty:
            return 0

        cl = df["Close"].stack(future_stack=True).reset_index()
        cl.columns = [str(c).lower() for c in cl.columns]  # date, ticker, close
        op = df["Open"].stack(future_stack=True).reset_index()
        op.columns = [str(c).lower() for c in op.columns]  # date, ticker, open

        p_df = pd.merge(cl, op, on=["date", "ticker"], how="inner")
        p_df["date"] = pd.to_datetime(p_df["date"], errors="coerce").dt.date
        p_df["ticker"] = p_df["ticker"].astype(str).str.upper()
        p_df = p_df.rename(columns={"close": "price", "open": "open_price"})
        p_df["source"] = "yfinance"
        p_df["fetched_at"] = pd.Timestamp.utcnow().to_pydatetime()

        self.con.register("df_upd", p_df[["date", "ticker", "price", "open_price", "source", "fetched_at"]].dropna())
        self.con.execute(
            """
            INSERT INTO prices(date, ticker, price, open_price, source, fetched_at)
            SELECT date, ticker, price, open_price, source, fetched_at FROM df_upd
            ON CONFLICT(date, ticker)
            DO UPDATE SET
              price=excluded.price,
              open_price=excluded.open_price,
              source=excluded.source,
              fetched_at=excluded.fetched_at
            """
        )

        return len(p_df)


if __name__ == "__main__":
    s = SentinelAlpha()
    try:
        s.update_news()
        s.update_prices()
    finally:
        s.close()
