import pandas as pd
import yfinance as yf
import requests
import os
import datetime
from datetime import timedelta
from io import StringIO
from github import Github, Auth  # Přidán Auth pro moderní volání

# --- KONFIGURACE ---
# Používáme proměnné prostředí, které nastavuješ v GitHub Actions nebo Secrets
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO_NAZEV = "Poutniiik/Moje-Investice"  # Tvůj repozitář

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
        # Moderní způsob autentizace (opravuje DeprecationWarning)
        auth = Auth.Token(GITHUB_TOKEN)
        g = Github(auth=auth)
        repo = g.get_repo(REPO_NAZEV)
        contents = repo.get_contents(filename)
        csv_data = contents.decoded_content.decode("utf-8")
        return pd.read_csv(StringIO(csv_data))
    except Exception as e:
        print(f"❌ Chyba stahování z GitHubu ({filename}): {e}")
        # Fallback na lokální soubor
        if os.path.exists(filename):
            return pd.read_csv(filename)
        return None

def load_all_tickers():
    """
    Načte unikátní tickery z Portfolia I Watchlistu.
    """
    tickers = set()
    
    # 1. Portfolio
    df_p = download_csv_from_github("portfolio_data.csv")
    if df_p is not None and not df_p.empty and 'Ticker' in df_p.columns:
        tickers.update(df_p['Ticker'].unique())
        print(f"✅ Načteno z portfolia: {len(df_p['Ticker'].unique())} tickerů")

    # 2. Watchlist
    df_w = download_csv_from_github("watchlist.csv")
    if df_w is not None and not df_w.empty and 'Ticker' in df_w.columns:
        tickers.update(df_w['Ticker'].unique())
        print(f"✅ Načteno z watchlistu: {len(df_w['Ticker'].unique())} tickerů")

    # Čištění
    clean_tickers = [t for t in tickers if isinstance(t, str) and t.strip()]
    print(f"🔍 Celkem ke kontrole: {len(clean_tickers)} unikátních tickerů.")
    return list(clean_tickers)

def get_earnings_date(ticker, start_date, end_date):
    """
    Zjistí, zda má firma earnings v daném rozmezí.
    Vrací datum (datetime) nebo None.
    """
    try:
        # Ignorujeme komodity jako zlato (GC=F), které nemají earnings
        if "=" in ticker or "^" in ticker:
            return None

        t = yf.Ticker(ticker)
        # Získáme tabulku budoucích earnings
        earnings = t.earnings_dates
        
        if earnings is None or earnings.empty:
            return None

        # Převedeme index na datetime bez časové zóny pro snadné porovnání
        earnings.index = earnings.index.tz_localize(None)
        
        # Filtrujeme řádky, které spadají do našeho týdne
        mask = (earnings.index >= start_date) & (earnings.index <= end_date)
        upcoming = earnings[mask]

        if not upcoming.empty:
            # Vrátíme první nalezené datum v tom týdnu
            return upcoming.index[0]
            
    except Exception as e:
        # Pokud chybí lxml, vypíšeme srozumitelnou radu
        if "lxml" in str(e):
            print(f"❌ CHYBA: Pro ticker {ticker} chybí knihovna 'lxml'. Přidej ji do requirements.txt!")
        else:
            print(f"⚠️ Chyba u {ticker}: {e}")
    
    return None

def send_telegram_message(message):
    """Odešle zprávu na Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Chybí Telegram tokeny. Jen vypisuji:")
        print(message)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload, timeout=10)
        print("✅ Zpráva odeslána na Telegram.")
    except Exception as e:
        print(f"❌ Chyba při odesílání: {e}")

def run_check():
    print("🚀 Spouštím Earnings Bot...")
    
    # Nastavíme rozsah na "Příští týden" (Pondělí až Neděle)
    today = datetime.datetime.now()
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0: 
        days_until_monday = 7 # Pokud je pondělí, chceme až to příští
        
    next_monday = today + timedelta(days=days_until_monday)
    # Reset času na půlnoc pro čisté porovnání
    next_monday = next_monday.replace(hour=0, minute=0, second=0, microsecond=0)
    next_sunday = next_monday + timedelta(days=6, hours=23, minutes=59)

    print(f"📅 Hledám reporty pro týden: {next_monday.strftime('%d.%m.')} - {next_sunday.strftime('%d.%m.%Y')}")

    tickers = load_all_tickers()
    found_earnings = []

    for tkr in tickers:
        date = get_earnings_date(tkr, next_monday, next_sunday)
        if date:
            found_earnings.append((date, tkr))
            print(f"💰 NÁLEZ: {tkr} reportuje {date.strftime('%d.%m.')}")

    if found_earnings:
        # Seřadíme podle data
        found_earnings.sort(key=lambda x: x[0])
        
        msg = "<b>📢 POZOR! Earnings příští týden:</b>\n\n"
        
        for date, tkr in found_earnings:
            day_name_cz = {
                0: "Pondělí", 1: "Úterý", 2: "Středa", 3: "Čtvrtek", 
                4: "Pátek", 5: "Sobota", 6: "Neděle"
            }[date.weekday()]
            
            msg += f"🗓 <b>{day_name_cz} ({date.strftime('%d.%m.')})</b>\n"
            msg += f"👉 <b>{tkr}</b>\n\n"
            
        msg += "<i>Připrav se na volatilitu! 📉📈</i>"
        send_telegram_message(msg)
    else:
        print("📭 Žádné earnings v tvém portfoliu/watchlistu pro příští týden.")

if __name__ == "__main__":
    run_check()
