import pandas as pd
import yfinance as yf
import requests
import os
import datetime
from datetime import timedelta
from io import StringIO
from github import Github # Přidáno pro cloudovou synchronizaci

# --- KONFIGURACE ---
TARGET_OWNER = 'Attis'

# ZMĚNA: Sjednoceno na TELEGRAM_BOT_TOKEN
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO_NAZEV = "Poutniiik/Moje-Investice" # Zde doplň svůj přesný název repozitáře!

# --- FUNKCE PRO GITHUB (Cloud Sync) ---
def download_csv_from_github(filename):
    """
    Stáhne aktuální CSV data přímo z GitHubu.
    """
    if not GITHUB_TOKEN:
        print("⚠️ GITHUB_TOKEN chybí. Zkouším číst lokální soubor.")
        if os.path.exists(filename):
            return pd.read_csv(filename)
        else:
            return None

    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAZEV)
        contents = repo.get_contents(filename)
        csv_data = contents.decoded_content.decode("utf-8")
        return pd.read_csv(StringIO(csv_data))
    except Exception as e:
        print(f"❌ Chyba stahování z GitHubu ({filename}): {e}")
        if os.path.exists(filename):
            print("🔄 Používám lokální zálohu.")
            return pd.read_csv(filename)
        return None

def send_telegram(message):
    # ZMĚNA: Používáme sjednocený TELEGRAM_BOT_TOKEN
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Chybí Telegram Token nebo ID.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload)
        print("📨 Telegram odeslán.")
    except Exception as e:
        print(f"❌ Chyba při odesílání: {e}")

def get_earnings_in_range(ticker, start_date, end_date):
    """Zjistí, zda má firma earnings v daném rozmezí."""
    try:
        t = yf.Ticker(ticker)
        cal = t.calendar
        
        # Pokud yfinance vrátí prázdný kalendář
        if cal is None:
            return None

        dates = []
        
        # Varianta 1: Dictionary
        if isinstance(cal, dict) and 'Earnings Date' in cal:
            dates = cal['Earnings Date']
        # Varianta 2: DataFrame
        elif isinstance(cal, pd.DataFrame) and 'Earnings Date' in cal.index:
            dates = cal.loc['Earnings Date'].tolist()
            
        # Projdeme data a hledáme shodu s příštím týdnem
        for d in dates:
            try:
                # Univerzální převod: Ať je to cokoliv, pandas z toho udělá Timestamp
                # a my si z něj vezmeme .date()
                d_date = pd.to_datetime(d).date()
                
                if start_date <= d_date <= end_date:
                    return d_date 
            except Exception:
                continue # Kdyby bylo jedno datum vadné, zkusíme další
                
    except Exception as e:
        print(f"⚠️ Chyba u {ticker}: {e}")
        
    return None

def load_tickers():
    """Načte unikátní tickery z portfolia i watchlistu pro Attise (z Cloudu!)."""
    tickers = set()
    
    # 1. Portfolio (CLOUD)
    try:
        df = download_csv_from_github("portfolio_data.csv")
        if df is not None and 'Owner' in df.columns:
            df = df[df['Owner'] == TARGET_OWNER]
            tickers.update(df['Ticker'].dropna().unique())
    except Exception as e:
        print(f"Chyba portfolio: {e}")

    # 2. Watchlist (CLOUD)
    try:
        df = download_csv_from_github("watchlist.csv")
        if df is not None and 'Owner' in df.columns:
            df = df[df['Owner'] == TARGET_OWNER]
            tickers.update(df['Ticker'].dropna().unique())
    except Exception as e:
        print(f"Chyba watchlist: {e}")
            
    # Očista tickerů (velká písmena, strip)
    return {str(t).strip().upper() for t in tickers}

def main():
    print("🗓️ EARNINGS BOT STARTUJE...")
    
    # 1. Definice příštího týdne (Pondělí - Neděle)
    today = datetime.date.today()
    # Najdeme nejbližší pondělí (pokud je dnes neděle, zítra je pondělí)
    days_ahead = 0 - today.weekday() 
    if days_ahead <= 0: # Pokud už je pondělí nebo později, chceme AŽ TO PŘÍŠTÍ pondělí
        days_ahead += 7
        
    next_monday = today + timedelta(days=days_ahead)
    next_sunday = next_monday + timedelta(days=6)
    
    print(f"🔍 Hledám earnings pro týden: {next_monday} až {next_sunday}")
    
    tickers = load_tickers()
    if not tickers:
        print("❌ Žádné tickery k prohledání.")
        return

    upcoming_earnings = []

    # 2. Kontrola tickerů
    for ticker in tickers:
        print(f"Kontroluji: {ticker}...")
        date = get_earnings_in_range(ticker, next_monday, next_sunday)
        if date:
            print(f"✅ NÁLEZ! {ticker} má earnings {date}")
            upcoming_earnings.append((date, ticker))

    # 3. Odeslání zprávy
    if upcoming_earnings:
        # Seřadíme podle data
        upcoming_earnings.sort()
        
        msg = "<b>📢 POZOR! Earnings příští týden:</b>\n\n"
        for date, ticker in upcoming_earnings:
            day_name = date.strftime("%A") # Den anglicky
            # Překlad dne
            days_cz = {"Monday": "Pondělí", "Tuesday": "Úterý", "Wednesday": "Středa", 
                       "Thursday": "Čtvrtek", "Friday": "Pátek", "Saturday": "Sobota", "Sunday": "Neděle"}
            day_cz = days_cz.get(day_name, day_name)
            
            msg += f"🗓️ <b>{day_cz} ({date.day}.{date.month}.)</b>: {ticker}\n"
        
        msg += "\n<i>Připrav se na volatilitu!</i> 🎢"
        send_telegram(msg)
    else:
        print("Žádné earnings v příštím týdnu.")

if __name__ == "__main__":
    main()
