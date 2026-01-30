import duckdb
import pandas as pd
from datetime import datetime, timedelta
import os

class SentinelReporter:
    def __init__(self):
        self.db_path = os.path.join("data", "sentinel_alpha.db")
        self.con = duckdb.connect(database=self.db_path)

    def get_today_alerts(self):
        """Estrae i segnali recenti ad alto punteggio (Elite)"""
        print("[*] Selezione segnali Elite per il report finale...")
        
        query = """
        WITH performance_audit AS (
            SELECT r.date, r.ticker, r.firm, r.rating, m.sector,
            (SELECT (p1.price-p0.price)/p0.price*100 FROM prices p0, prices p1 WHERE p0.ticker=r.ticker AND p0.date=(SELECT MAX(date) FROM prices WHERE ticker=r.ticker AND date<=r.date-30) AND p1.ticker=r.ticker AND p1.date=(SELECT MIN(date) FROM prices WHERE ticker=r.ticker AND date>=r.date)) as pre_ret,
            (SELECT (p1.price-p0.price)/p0.price*100 FROM prices p0, prices p1 WHERE p0.ticker=r.ticker AND p0.date=(SELECT MIN(date) FROM prices WHERE ticker=r.ticker AND date>=r.date) AND p1.ticker=r.ticker AND p1.date=(SELECT MIN(date) FROM prices WHERE ticker=r.ticker AND date>=r.date+30)) as post_ret
            FROM recs r JOIN metadata m ON r.ticker = m.ticker
        )
        SELECT *,
            CASE 
                WHEN post_ret > 5 AND pre_ret < 0 THEN 5
                WHEN post_ret > 5 AND pre_ret > 0 THEN 4
                WHEN post_ret BETWEEN 0 AND 5 THEN 3
                ELSE 1
            END as stars_score
        FROM performance_audit
        WHERE date >= CURRENT_DATE - INTERVAL 3 DAY
        AND stars_score >= 4
        ORDER BY stars_score DESC, post_ret DESC
        """
        return self.con.execute(query).df()

    def generate_markdown_report(self, df):
        """Genera il report finale degli alert attivi"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        path = os.path.join("reports", f"ALERTS_{timestamp}.md")
        
        with open(path, "w", encoding="utf-8") as f:
            f.write("# 🛡️ SENTINEL-ALPHA: Elite Intelligence Report\n\n")
            f.write(f"Generato il: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
            
            if df.empty:
                f.write("⚠️ Nessun segnale ad alta probabilità rilevato nelle ultime 72 ore.\n")
            else:
                f.write("| Score | Ticker | Banca | Settore | Anticipazione | Alpha Storico |\n")
                f.write("| :--- | :--- | :--- | :--- | :--- | :--- |\n")
                for _, row in df.iterrows():
                    stars = "⭐" * int(row['stars_score'])
                    f.write(f"| {stars} | **{row['ticker']}** | {row['firm']} | {row['sector']} | {row['pre_ret']:.1f}% | {row['post_ret']:.1f}% |\n")
        
        return path

if __name__ == "__main__":
    reporter = SentinelReporter()
    alerts = reporter.get_today_alerts()
    if not alerts.empty:
        reporter.generate_markdown_report(alerts)