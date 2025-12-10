import os
import requests
from datetime import datetime
import traceback
from typing import Tuple, Optional
import pandas as pd # Nově přidáno
import yfinance as yf # Nově přidáno

# --- 1. Nastavení a klíče ---

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# --- 2. Funkce pro odeslání zprávy (Nejbezpečnější verze) ---

def send_telegram_message(message: str, parse_mode: Optional[str] = None) -> bool:
    """Odešle textovou zprávu na Telegram. Přidáno parse_mode pro budoucí HTML."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("CHYBA: Klíče nejsou nastaveny.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message
    }
    
    # Podpora HTML/Markdown pro sekci 3
    if parse_mode:
        payload['parse_mode'] = parse_mode

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


# --- 3. Funkce pro generování obsahu reportu (LOGIKA ZAPOUZDŘENA A OPRAVENA) ---

def generate_report_content() -> Tuple[str, Optional[str]]:
    """Generuje obsah reportu ve formátu HTML, kombinuje data z Yahoo a lokálních CSV."""
    
    # ----------------------------------------------------
    # --- PROJDI TYTO PROMĚNNÉ, KTERÉ MUSÍŠ DEFINOVAT ---
    # ----------------------------------------------------
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
    # ----------------------------------------------------
    
    current_time = datetime.now().strftime("%d.%m.%Y v %H:%M:%S")
    
    # --- A) NAČÍTÁNÍ DAT Z YAHOO FINANCE ---
    ticker_symbol = "MSFT" 
    try:
        data = yf.download(ticker_symbol, period="5d", interval="1d")
        
        posledni_cena = data['Close'].iloc[-1]
        zmena_za_den = (data['Close'].iloc[-1] - data['Close'].iloc[-2]) / data['Close'].iloc[-2] * 100
        
        yahoo_status = f"Poslední cena {ticker_symbol}: {posledni_cena:.2f} USD ({zmena_za_den:.2f}%)"
        
    except Exception as e:
        yahoo_status = f"CHYBA načítání Yahoo dat pro {ticker_symbol}: {e}"
        posledni_cena = "N/A"
        zmena_za_den = "N/A"


    # --- B) NAČÍTÁNÍ LOKÁLNÍCH CSV SOUBORŮ (OPRAVENO ODSZENÍ A LOGIKA) ---

    # 1. PORTFOLIO DATA (portfolio_data.csv)
    portfolio_path = "portfolio_data.csv"
    try:
        df_portfolio = pd.read_csv(portfolio_path)
        
        if 'Pocet' in df_portfolio.columns and 'Cena' in df_portfolio.columns:
            
            df_portfolio['Pocet'] = pd.to_numeric(df_portfolio['Pocet'], errors='coerce').fillna(0)
            df_portfolio['Cena'] = pd.to_numeric(df_portfolio['Cena'], errors='coerce').fillna(0)
            
            # VÝPOČET: Vytvoření sloupce 'Hodnota' = Pocet * Cena
            df_portfolio['Hodnota'] = df_portfolio['Pocet'] * df_portfolio['Cena']
            
            # Získání výsledné metriky: CELKOVÁ HODNOTA PORTFOLIA
            celkova_hodnota = df_portfolio['Hodnota'].sum()
            pocet_pozic = len(df_portfolio[df_portfolio['Pocet'] > 0])
            
            status_portf = f"Úspěšně zpracováno {len(df_portfolio)} záznamů."
            
        else:
            celkova_hodnota = "CHYBA SLOUPCŮ"
            pocet_pozic = "N/A"
            status_portf = "CHYBA: Chybí sloupce 'Pocet' nebo 'Cena'."
            
    except Exception as e:
        celkova_hodnota = "N/A"
        pocet_pozic = "N/A"
        status_portf = f"KRITICKÁ CHYBA čtení PORTFOLIA: {e}"

    # 2. HISTORY DATA (history_data.csv)
    history_path = "history_data.csv"
    try:
        df_history = pd.read_csv(history_path)
        # Získání metrik z HISTORIE
        pocet_history = len(df_history)
        status_history = f"Načteno {pocet_history} historických záznamů."
        
    except Exception as e:
        pocet_history = "N/A"
        status_history = f"CHYBA čtení HISTORIE: {e}"


    # 3. CASH DATA (cash_data.csv)
    cash_path = "cash_data.csv"
    try:
        df_cash = pd.read_csv(cash_path)
        # Získání metrik z CASH
        pocet_cash = len(df_cash)
        status_cash = f"Načteno {pocet_cash} cash záznamů."
        
    except Exception as e:
        pocet_cash = "N/A"
        status_cash = f"CHYBA čtení CASH: {e}"


    # --- C) TVORBA HTML REPORTU (OPRAVENO ODSZENÍ A VLOŽENÍ HODNOT) ---

    html_report_text = f"""
    <b>🚀 Denní Report: Finance a Data</b>
    <pre>Datum: {current_time}</pre>

    <b>📊 Yahoo Finance Metriky ({ticker_symbol})</b>
    \u2022 Poslední cena: <b>{posledni_cena}</b>
    \u2022 Změna za den: <b>{zmena_za_den}%</b>
    \u2022 Stav Yahoo: <i>{yahoo_status}</i>

    <b>📁 Lokální CSV Souhrn</b>
    <hr>
    <b>PORTFOLIO DATA ({portfolio_path})</b>
    \u2022 Celkem pozic: <b>{pocet_pozic}</b>
    \u2022 **CELKOVÁ HODNOTA:** <b>{celkova_hodnota:,.2f} CZK</b>
    \u2022 Stav: <i>{status_portf}</i>

    <b>HISTORY DATA ({history_path})</b>
    \u2022 Celkem záznamů: <b>{pocet_history}</b>
    \u2022 Stav: <i>{status_history}</i>

    <b>CASH DATA ({cash_path})</b>
    \u2022 Celkem záznamů: <b>{pocet_cash}</b>
    \u2022 Stav: <i>{status_cash}</i>
    <hr>

    <a href="https://moje-investice-pesalikcistokrevnimamlas.streamlit.app/">Odkaz na tvou Streamlit aplikaci</a>
    """

    # TENTO ŘÁDEK ZPŮSOBIL CHYBU A JE Nyní SPRÁVNĚ ODSZEN
    return html_report_text, 'HTML' 


# --- 4. Hlavní spouštěcí blok ---

if __name__ == '__main__':
    print(f"Spouštím Telegram report generator v {datetime.now().strftime('%H:%M:%S')}...")
    
    try:
        # Nyní generujeme HTML a mód je 'HTML'
        report_content, parse_mode = generate_report_content()
        
        # Odeslání zprávy. Nyní posíláme parse_mode!
        success = send_telegram_message(report_content, parse_mode=parse_mode)
        
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
