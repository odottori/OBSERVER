import pandas as pd
import pandas_market_calendars as mcal
from datetime import datetime

def get_market_closures(exchange_code, start_year, end_year):
    """Estrae le chiusure (festive e straordinarie) per una borsa specifica."""
    try:
        # Carica il calendario specifico
        calendar = mcal.get_calendar(exchange_code)
        
        # Definiamo il range temporale
        start_date = f"{start_year}-01-01"
        end_date = f"{end_year}-12-31"
        
        # Otteniamo tutti i giorni (inclusi weekend) nel range
        all_days = pd.date_range(start=start_date, end=end_date, freq='D')
        
        # Otteniamo i giorni in cui il mercato era effettivamente APERTO
        schedule = calendar.schedule(start_date=start_date, end_date=end_date)
        open_days = schedule.index
        
        # I giorni di chiusura sono i giorni feriali (Lun-Ven) non presenti in open_days
        # Escludiamo i weekend per isolare le chiusure 'business'
        potential_business_days = all_days[all_days.weekday < 5]
        closures = potential_business_days.difference(open_days)
        
        df = pd.DataFrame({'date': closures})
        df['exchange'] = exchange_code
        df['year'] = df['date'].dt.year
        return df
    except Exception as e:
        print(f"Errore per {exchange_code}: {e}")
        return pd.DataFrame()

# Configurazione
exchanges = ['NYSE', 'LSE', 'XSWX', 'XMIL', 'XPAR', 'XMAD', 'XTKS', 'XHKG', 'XETR', 'EUREX'] # NYSE, Londra, Borsa Italiana (Euronext), Francoforte
start_y, end_y = 2000, 2024

# Loop di estrazione
all_closures = pd.concat([get_market_closures(ex, start_y, end_y) for ex in exchanges])

# Normalizzazione finale
all_closures['date'] = all_closures['date'].dt.strftime('%Y-%m-%d')
all_closures.to_csv('borse_chiusure_storiche.csv', index=False)
print("File CSV creato con successo: borse_chiusure_storiche.csv")