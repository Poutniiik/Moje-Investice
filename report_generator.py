import os
import requests
from datetime import datetime
import traceback
from typing import Tuple, Optional 
import pandas as pd 
import yfinance as yf 

# --- 1. Nastavení a klíče ---

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# --- 2. Funkce pro odeslání zprávy (Nejbezpečnější verze) ---

def send_telegram_message(message: str) -> bool:
    """Odešle textovou zprávu na Telegram jako PLAIN TEXT."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("CHYBA: Klíče nejsou nastaveny.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    # Payload, který posílá pouze text a chat ID
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message
    }
    
    try:
        response = requests.post(url, data=payload)
        response.raise_for_status() 

        response_json = response.json()
        if response_json.get("ok"):
            print("Zpráva úspěšně odeslána na Telegram.")
            return True
        else:
            print(f"Chyba z Telegram API: {response_json.get('description', 'Neznámá chyba')}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"Kritická chyba při komunikaci s Telegram API: {e}")
        return False


# --- 3. Funkce pro generování obsahu reportu (KONEČNÁ VERZE S ANALÝZOU) ---

def generate_report_content() -> Tuple[str, Optional[str]]:
    """Generuje obsah reportu jako strukturovaný čistý text (Plain Text)."""
    
    # Nastavení výchozích hodnot pro případ chyby
    posledni_cena = "N/A"
    zmena_za_den = "N/A"
    yahoo_status = "Data zatím nenačtena"
    celkova_hodnota = "N/A"
    pocet_pozic = "N/A"
    status_portf = "N/A"
    pocet_history = "N/A"
    status_history = "N/A"
    pocet_cash = "N/A"
    status_cash = "N/A"
    nejvetsi_vitez = "N/A"
    nejvetsi_propadak = "N/A"
    
    current_time = datetime.now().strftime("%d.%m.%Y v %H:%M:%S")

    # --- A) NAČÍTÁNÍ DAT Z YAHOO FINANCE (MSFT) ---
    ticker_symbol = "MSFT" 
    cena_str = "N/A"
    zmena_str = "N/A"

    try:
        data = yf.download(ticker_symbol, period="5d", interval="1d")
        
        if len(data) >= 2:
            posledni_cena = data['Close'].iloc[-1]
            zmena_za_den = (data['Close'].iloc[-1] - data['Close'].iloc[-2]) / data['Close'].iloc[-2] * 100
            
            cena_str = f"{posledni_cena:,.2f} USD"
            zmena_str = f"{zmena_za_den:,.2f}%"
            yahoo_status = "Status: OK"
        else:
            yahoo_status = "CHYBA: Staženo málo dat pro výpočet změny."
        
    except Exception as e:
        yahoo_status = f"CHYBA načítání Yahoo dat: {e}"

    # --- B) NAČÍTÁNÍ LOKÁLNÍCH CSV SOUBORŮ ---

    # 1. PORTFOLIO DATA (portfolio_data.csv) - DEBUG VERZE
portfolio_path = "portfolio_data.csv"
max_zisk_pct = -1000 
max_propad_pct = 1000

try:
    print("DEBUG: Zacinam cteni Portfolio CSV.")
    df_portfolio = pd.read_csv(portfolio_path)
    print(f"DEBUG: Nacteno {len(df_portfolio)} radku.")
    
    # KONTROLA KLÍČOVÝCH SLOUPCŮ
    required_cols = ['Pocet', 'Cena', 'Ticker']
    if not all(col in df_portfolio.columns for col in required_cols):
        raise ValueError(f"Chybí klíčové sloupce: {list(set(required_cols) - set(df_portfolio.columns))}")
        
    df_portfolio['Pocet'] = pd.to_numeric(df_portfolio['Pocet'], errors='coerce').fillna(0)
    df_portfolio['Cena'] = pd.to_numeric(df_portfolio['Cena'], errors='coerce').fillna(0)
    
    # AGREGACE:
    df_agregovano = df_portfolio[df_portfolio['Pocet'] > 0].groupby('Ticker').agg(
        Pocet=('Pocet', 'sum'),
        Nakupni_Cena=('Cena', 'mean')
    ).reset_index()
    print(f"DEBUG: Agregovano {len(df_agregovano)} unikatnich tickeru.")

    df_agregovano['Aktualni_Hodnota'] = 0.0
    df_agregovano['Vykonnost_PCT'] = 0.0
    
    # VÝPOČET: Iterace přes tikery pro získání aktuální ceny (IZOLOVANÝ TRY/EXCEPT)
    for index, row in df_agregovano.iterrows():
        ticker = row['Ticker']
        nakupni_cena = row['Nakupni_Cena']
        
        try:
            print(f"DEBUG: Stahuji cenu pro {ticker}...")
            # Načtení aktuální ceny z Yahoo
            cena_data = yf.download(ticker, period="1d", interval="1m", progress=False, show_errors=False)
            
            if not cena_data.empty and 'Close' in cena_data.columns:
                aktualni_cena = cena_data['Close'].iloc[-1]
                vykonnost_pct = ((aktualni_cena / nakupni_cena) - 1) * 100
                
                df_agregovano.loc[index, 'Aktualni_Hodnota'] = row['Pocet'] * aktualni_cena
                df_agregovano.loc[index, 'Vykonnost_PCT'] = vykonnost_pct
                
                # IDENTIFIKACE VÍTĚZŮ A PROPADÁKŮ
                if vykonnost_pct > max_zisk_pct:
                    max_zisk_pct = vykonnost_pct
                    nejvetsi_vitez = f"{ticker} ({max_zisk_pct:,.2f}%)"
                
                if vykonnost_pct < max_propad_pct:
                    max_propad_pct = vykonnost_pct
                    nejvetsi_propadak = f"{ticker} ({max_propad_pct:,.2f}%)"
            
            else:
                print(f"DEBUG: Selhalo stahovani, pouzivam nakupni cenu pro {ticker}.")
                df_agregovano.loc[index, 'Aktualni_Hodnota'] = row['Pocet'] * nakupni_cena
                # Výkonnost bude 0% (pouze lokální cena)

        except Exception as e:
            print(f"DEBUG: KRITICKÁ CHYBA analýzy pro {ticker}: {e}")
            df_agregovano.loc[index, 'Aktualni_Hodnota'] = row['Pocet'] * nakupni_cena # Fallback
        
    # FINÁLNÍ SOUHRN: Celková hodnota portfolia
    celkova_hodnota = df_agregovano['Aktualni_Hodnota'].sum()
    pocet_pozic = len(df_agregovano)
    
    status_portf = f"Status: Zpracováno {len(df_portfolio)} záznamů. P/L OK."

except Exception as e:
    # Tady se ocitneme, pokud padlo celé CSV
    celkova_hodnota = "N/A"
    pocet_pozic = "N/A"
    status_portf = f"KRITICKÁ CHYBA čtení PORTFOLIA: {e}"
    # Zde se také musí nastavit Vítěz a Propadák na N/A
    nejvetsi_vitez = "N/A"
    nejvetsi_propadak = "N/A"


    # 3. CASH DATA (cash_data.csv)
    cash_path = "cash_data.csv"
    try:
        df_cash = pd.read_csv(cash_path)
        pocet_cash = len(df_cash)
        status_cash = f"Status: Načteno {pocet_cash} cash záznamů."
        
    except Exception as e:
        pocet_cash = "N/A"
        status_cash = f"CHYBA čtení CASH: {e}"


    # --- C) TVORBA STRUKTUROVANÉHO TEXTOVÉHO REPORTU ---
    
    if isinstance(celkova_hodnota, (int, float)):
        hodnota_str = f"{celkova_hodnota:,.2f} CZK"
    else:
        hodnota_str = str(celkova_hodnota) 

    report_text = f"""
======================================
🚀 DENNÍ REPORT: FINANCE A DATA
Datum: {current_time}
======================================

📊 YAHOO FINANCE METRIKY ({ticker_symbol})
- Poslední cena: {cena_str}
- Změna za den: {zmena_str}
- Status: {yahoo_status}

======================================

📈 ANALÝZA PORTFOLIA
| NEJVĚTŠÍ VÍTĚZ: {nejvetsi_vitez}
| NEJVĚTŠÍ PROPADÁK: {nejvetsi_propadak}

======================================

📁 LOKÁLNÍ DATA SOUHRN

| PORTFOLIO DATA (portfolio_data.csv)
| Celkem pozic: {pocet_pozic}
| CELKOVÁ HODNOTA: {hodnota_str}
| Stav: {status_portf}

| HISTORY DATA (history_data.csv)
| Celkem záznamů: {pocet_history}
| Stav: {status_history}

| CASH DATA (cash_data.csv)
| Celkem záznamů: {pocet_cash}
| Stav: {status_cash}

======================================
Odkaz na aplikaci: https://moje-investice-pesalikcistokrevnimamlas.streamlit.app/
"""

    return report_text, None 


# --- 4. Hlavní spouštěcí blok ---

if __name__ == '__main__':
    print(f"Spouštím Telegram report generator v {datetime.now().strftime('%H:%M:%S')}...")
    
    try:
        report_content, parse_mode_unused = generate_report_content()
        
        success = send_telegram_message(report_content)
        
        if success:
            print("Skript dokončen úspěšně.")
        else:
            print("Skript dokončen, ale zpráva se nepodařila odeslat.")
            exit(1)
            
    except Exception as e:
        print(f"Kritická chyba v report_generator.py: {e}")
        print("-" * 30)
        traceback.print_exc()
        print("-" * 30)
        exit(1)
