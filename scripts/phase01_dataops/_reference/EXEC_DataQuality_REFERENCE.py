import pandas as pd

def run_data_quality_checks(csv_path):
    try:
        # Carica il file
        df = pd.read_csv(csv_path)
        df['date'] = pd.to_datetime(df['date'])
    except Exception as e:
        print(f"Errore durante l'apertura del file: {e}")
        return

    issues = []
    print("\n" + "="*40)
    print("   REPORT DI DATA QUALITY")
    print("="*40)

    # 1. Controllo Duplicati
    duplicates = df.duplicated().sum()
    if duplicates > 0:
        issues.append(f"Trovati {duplicates} record duplicati.")

    # 2. Controllo Range Temporale
    actual_min = df['date'].min()
    actual_max = df['date'].max()
    print(f"[*] Copertura dati: da {actual_min.date()} a {actual_max.date()}")

    # 3. Analisi Chiusure Annuali (Outlier)
    closure_counts = df.groupby(['exchange', 'year']).size().reset_index(name='count')
    for _, row in closure_counts.iterrows():
        # Segnala se ci sono più di 25 chiusure (molto insolito) o meno di 5
        if row['count'] > 25:
            issues.append(f"ALERT: {row['exchange']} ha {row['count']} chiusure nel {row['year']} (Elevate).")
        if row['count'] < 3:
            issues.append(f"ALERT: {row['exchange']} ha {row['count']} chiusure nel {row['year']} (Troppo poche).")

    # 4. Verifica date nel weekend (Fondamentale!)
    # weekday 5 = Sabato, 6 = Domenica
    weekend_check = df[df['date'].dt.weekday >= 5]
    if not weekend_check.empty:
        issues.append(f"ERRORE: Trovate {len(weekend_check)} date che cadono di Sabato o Domenica!")

    # 5. Statistiche medie
    print("\n[*] Media giorni di chiusura annui per borsa:")
    summary = df.groupby('exchange').size() / (df['year'].max() - df['year'].min() + 1)
    print(summary.round(2))

    # Report finale
    print("\n" + "-"*40)
    if not issues:
        print("✅ Esito: QUALITÀ OTTIMA. Nessuna anomalia rilevata.")
    else:
        print("❌ Esito: PROBLEMI RILEVATI:")
        for issue in issues:
            print(f"  - {issue}")
    print("-"*40 + "\n")

if __name__ == "__main__":
    run_data_quality_checks('borse_chiusure_storiche.csv')