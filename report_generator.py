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

    # --- A) NAČÍTÁNÍ DAT Z YAHOO FINANCE (FINÁLNÍ OPRAVA CHYBY) ---
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

    # 1. PORTFOLIO DATA (portfolio_data.csv) - Nyní s P/L analýzou
    portfolio_path = "portfolio_data.csv"
    max_zisk_pct = -1000 
    max_propad_pct = 1000
    
    try:
        df_portfolio = pd.read_csv(portfolio_path)
        
        if 'Pocet' in df_portfolio.columns and 'Cena' in df_portfolio.columns and 'Ticker' in df_portfolio.columns:
            
            df_portfolio['Pocet'] = pd.to_numeric(df_portfolio['Pocet'], errors='coerce').fillna(0)
            df_portfolio['Cena'] = pd.to_numeric(df_portfolio['Cena'], errors='coerce').fillna(0)
            
            # Agregace pro získání průměrné nákupní ceny
            df_agregovano = df_portfolio[df_portfolio['Pocet'] > 0].groupby('Ticker').agg(
                Pocet=('Pocet', 'sum'),
                Nakupni_Cena=('Cena', 'mean')
            ).reset_index()

            df_agregovano['Aktualni_Cena'] = 0.0
            
            # VÝPOČET: Iterace přes tikery pro získání aktuální ceny a P/L
            for index, row in df_agregovano.iterrows():
                ticker = row['Ticker']
                nakupni_cena = row['Nakupni_Cena']
                
                try:
                    cena_data = yf.download(ticker, period="1d", interval="1m", progress=False, show_errors=False)
                    if not cena_data.empty and 'Close' in cena_data.columns:
                        aktualni_cena = cena_data['Close'].iloc[-1]
                    else:
                        aktualni_cena = nakupni_cena # Pokud selže, nákupní cena
                    
                    vykonnost_pct = ((aktualni_cena / nakupni_cena) - 1) * 100
                    
                    # Doplňujeme Aktuální hodnotu
                    df_agregovano.loc[index, 'Aktualni_Cena'] = aktualni_cena
                    
                    # IDENTIFIKACE VÍTĚZŮ A PROPADÁKŮ
                    if vykonnost_pct > max_zisk_pct:
                        max_zisk_pct = vykonnost_pct
                        nejvetsi_vitez = f"{ticker} ({max_zisk_pct:,.2f}%)"
                    
                    if vykonnost_pct < max_propad_pct:
                        max_propad_pct = vykonnost_pct
                        nejvetsi_propadak = f"{ticker} ({max_propad_pct:,.2f}%)"

                except Exception:
                    # Chybu ignorujeme, Aktuální cena zůstane 0.0, výkonnost bude 0
                    pass 

            # FINÁLNÍ SOUHRN
            df_agregovano['Aktualni_Hodnota'] = df_agregovano['Pocet'] * df_agregovano['Aktualni_Cena']
            celkova_hodnota = df_agregovano['Aktualni_Hodnota'].sum()
            pocet_pozic = len(df_agregovano)
            
            status_portf = f"Status: Zpracováno {len(df_portfolio)} záznamů."
            
        else:
            celkova_hodnota = "CHYBA SLOUPCŮ"
            pocet_pozic = "N/A"
            status_portf = "CHYBA: Chybí klíčové sloupce Ticker/Pocet/Cena."
            
    except Exception as e:
        celkova_hodnota = "N/A"
        pocet_pozic = "N/A"
        status_portf = f"KRITICKÁ CHYBA čtení PORTFOLIA: {e}"


    # 2. HISTORY DATA (history_data.csv)
    history_path = "history_data.csv"
    try:
        df_history = pd.read_csv(history_path)
        pocet_history = len(df_history)
        status_history = f"Status: Načteno {pocet_history} historických záznamů."
        
    except Exception as e:
        pocet_history = "N/A"
        status_history = f"CHYBA čtení HISTORIE: {e}"


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
    
    # Bezpečné formátování pro celkovou hodnotu
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
