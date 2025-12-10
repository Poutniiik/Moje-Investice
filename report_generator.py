import os
import requests
from datetime import datetime
import traceback
from typing import Tuple, Optional 

# --- 1. Nastavení a klíče ---

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# --- 2. Funkce pro odeslání zprávy (Nejbezpečnější verze) ---

def send_telegram_message(message: str) -> bool: # Odstranili jsme parse_mode z argumentů
    """Odešle textovou zprávu na Telegram jako PLAIN TEXT."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("CHYBA: Klíče nejsou nastaveny.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    # Payload, který posílá pouze text a chat ID (NEJBEZPEČNĚJŠÍ)
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message
    }
    
    # Všimni si, že parse_mode se neposílá vůbec!

    try:
        response = requests.post(url, data=payload)
        response.raise_for_status() 

        response_json = response.json()
        if response_json.get("ok"):
            print("Zpráva úspěšně odeslána na Telegram.")
            return True
        else:
            # Tohle nám napoví, co je špatně, pokud to selže
            print(f"Chyba z Telegram API: {response_json.get('description', 'Neznámá chyba')}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"Kritická chyba při komunikaci s Telegram API: {e}")
        return False


# --- 3. Funkce pro generování obsahu reportu ---

def generate_report_content() -> Tuple[str, Optional[str]]:
    """Generuje obsah reportu ve formátu HTML, kombinuje data z Yahoo a lokálních CSV."""
    
    current_time = datetime.now().strftime("%d.%m.%Y v %H:%M:%S")
    
    # --- A) NAČÍTÁNÍ DAT Z YAHOO FINANCE ---
    ticker_symbol = "MSFT" # Příklad: Můžeš si zvolit jiný symbol
    try:
        data = yf.download(ticker_symbol, period="5d", interval="1d")
        
        # Získání metrik z Yahoo dat
        posledni_cena = data['Close'].iloc[-1]
        zmena_za_den = (data['Close'].iloc[-1] - data['Close'].iloc[-2]) / data['Close'].iloc[-2] * 100
        
        yahoo_status = f"Poslední cena {ticker_symbol}: {posledni_cena:.2f} USD ({zmena_za_den:.2f}%)"
        
    except Exception as e:
        yahoo_status = f"CHYBA načítání Yahoo dat pro {ticker_symbol}: {e}"
        posledni_cena = "N/A"
        zmena_za_den = "N/A"


   # --- B) NAČÍTÁNÍ LOKÁLNÍCH CSV SOUBORŮ ---

# 1. PORTFOLIO DATA (portfolio_data.csv)
portfolio_path = "portfolio_data.csv"
try:
    df_portfolio = pd.read_csv(portfolio_path)
    # Získání metrik z PORTFOLIA
    celkem_zaznamu_portf = len(df_portfolio)
    status_portf = f"Úspěšně načteno {celkem_zaznamu_portf} záznamů."
    
except Exception as e:
    celkem_zaznamu_portf = "N/A"
    status_portf = f"CHYBA čtení PORTFOLIA: {e}"


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


# --- C) TVORBA HTML REPORTU ---

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
\u2022 Celkem záznamů: <b>{celkem_zaznamu_portf}</b>
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

# Vrátíme HTML text a specifikujeme mód 'HTML'
return html_report_text, 'HTML'


# --- 4. Hlavní spouštěcí blok ---

if __name__ == '__main__':
    print(f"Spouštím Telegram report generator v {datetime.now().strftime('%H:%M:%S')}...")
    
    try:
        # Nyní generujeme POUZE text
        report_content = generate_report_content()
        
        # Odeslání zprávy. parse_mode neposíláme.
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
# --- Zbytek kódu (Sekce 4) ---
# ...
