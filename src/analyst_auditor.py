import duckdb
import pandas as pd
import matplotlib.pyplot as plt
import os

class AnalystAuditor:
    def __init__(self):
        self.db_path = os.path.join("data", "sentinel_alpha.db")
        self.con = duckdb.connect(database=self.db_path)

    def generate_audit_map(self):
        print("[*] Generazione Mappa Strategica Analisti...")
        
        # Query che aggrega i dati di performance per banca e settore
        query = """
        SELECT 
            firm, sector, 
            AVG(pre_ret) as avg_pre, 
            AVG(post_ret) as avg_post, 
            COUNT(*) as calls
        FROM (
            SELECT r.firm, m.sector,
            (SELECT (p1.price-p0.price)/p0.price*100 FROM prices p0, prices p1 WHERE p0.ticker=r.ticker AND p0.date=(SELECT MAX(date) FROM prices WHERE ticker=r.ticker AND date<=r.date-30) AND p1.ticker=r.ticker AND p1.date=(SELECT MIN(date) FROM prices WHERE ticker=r.ticker AND date>=r.date)) as pre_ret,
            (SELECT (p1.price-p0.price)/p0.price*100 FROM prices p0, prices p1 WHERE p0.ticker=r.ticker AND p0.date=(SELECT MIN(date) FROM prices WHERE ticker=r.ticker AND date>=r.date) AND p1.ticker=r.ticker AND p1.date=(SELECT MIN(date) FROM prices WHERE ticker=r.ticker AND date>=r.date+30)) as post_ret
            FROM recs r JOIN metadata m ON r.ticker = m.ticker
        ) 
        GROUP BY firm, sector 
        HAVING avg_pre IS NOT NULL AND avg_post IS NOT NULL
        """
        df = self.con.execute(query).df()
        
        if df.empty:
            print("[!] Dati insufficienti per generare la mappa.")
            return

        plt.figure(figsize=(12, 8))
        for sector in df['sector'].unique():
            sub = df[df['sector'] == sector]
            plt.scatter(sub['avg_pre'], sub['avg_post'], s=sub['calls']*150, alpha=0.6, label=sector)
            for _, row in sub.iterrows():
                plt.annotate(row['firm'], (row['avg_pre'], row['avg_post']), fontsize=8, alpha=0.7)

        plt.axhline(0, color='black', lw=1, alpha=0.5)
        plt.axvline(0, color='black', lw=1, alpha=0.5)
        plt.title('SENTINEL-ALPHA: Mappa DNA (Visionari vs Followers)', fontsize=14)
        plt.xlabel('Rendimento 30gg PRIMA del segnale (Momentum)')
        plt.ylabel('Alpha 30gg DOPO il segnale (Performance)')
        plt.legend(title="Settore Specializzazione")
        plt.grid(True, alpha=0.2)
        
        path = os.path.join("reports", "analyst_dna_map.png")
        os.makedirs("reports", exist_ok=True)
        plt.savefig(path)
        plt.close()
        print(f"[+] Mappa DNA salvata in: {path}")

if __name__ == "__main__":
    auditor = AnalystAuditor()
    auditor.generate_audit_map()