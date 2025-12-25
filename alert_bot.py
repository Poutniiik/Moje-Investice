import pandas as pd
import yfinance as yf
import requests
import os
import time
from io import StringIO
from github import Github # Přidáno pro cloudovou synchronizaci

# --- KONFIGURACE ---
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

# --- TELEGRAM FUNKCE (Zůstává beze změny) ---
def send_telegram_message(message):
    """Odešle zprávu na Telegram."""
    TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
    
    if not TOKEN or not CHAT_ID:
        print("Chybí Telegram token nebo ID chatu.")
        return False, "Chybí token"

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    try:
        response = requests.post(url, data=payload, timeout=5)
        response.raise_for_status()
        return True, "Odesláno"
    except Exception as e:
        print(f"Chyba při odesílání Telegramu: {e}")
        return False, str(e)

# --- FUNKCE PRO STAHUJÍCÍ CENY ---
def get_data_safe(ticker):
    """Bezpečně získá aktuální cenu a měnu pomocí yfinance."""
    try:
        t = yf.Ticker(ticker)
        # Používáme fast_info pro rychlé informace
        price = t.fast_info.last_price
        currency = t.fast_info.currency
        return price, currency
    except Exception:
        # Pomalý fallback pro méně standardní tickery
        try:
            data = yf.download(ticker, period="1d", interval="1m", progress=False)['Close'].iloc[-1]
            info = yf.Ticker(ticker).info
            return float(data), info.get('currency', 'USD')
        except Exception:
            return None, None

# --- HLAVNÍ LOGIKA HLÍDAČE (Upraveno pro Cloud) ---
def run_alert_bot():
    print("🔔 Spouštím Price Alert Bota pro Watchlist...")
    
    WATCHLIST_FILE = "watchlist.csv"
    TARGET_OWNER = 'Attis' 
    
    # Načtení dat (CLOUD FIRST)
    try:
        # ZMĚNA: Použití funkce pro stažení z GitHubu
        df_w = download_csv_from_github(WATCHLIST_FILE)
        
        if df_w is None:
            print(f"❌ Chyba: Nepodařilo se načíst {WATCHLIST_FILE}")
            return

        # 1. Filtrování podle Ownera
        if 'Owner' in df_w.columns:
            df_targets = df_w[df_w['Owner'].astype(str) == TARGET_OWNER].copy()
        else:
            print("⚠️ Sloupec 'Owner' chybí, používám všechna data.")
            df_targets = df_w.copy()

        # 2. Vyčištění a kontrola existence klíčových sloupců
        if 'Ticker' not in df_targets.columns or 'TargetBuy' not in df_targets.columns or 'TargetSell' not in df_targets.columns:
            print("❌ Chyba: Watchlist.csv neobsahuje sloupce Ticker, TargetBuy nebo TargetSell.")
            return

        # Převedení NaN na 0 pro bezpečné porovnání
        df_targets['TargetBuy'] = df_targets['TargetBuy'].fillna(0)
        df_targets['TargetSell'] = df_targets['TargetSell'].fillna(0)

        # Odstranění řádků, které nemají žádný cíl
        df_targets = df_targets[(df_targets['TargetBuy'] > 0) | (df_targets['TargetSell'] > 0)]

        if df_targets.empty:
            print(f"V {WATCHLIST_FILE} pro uživatele {TARGET_OWNER} nejsou žádné aktivní cíle.")
            return

    except Exception as e:
        print(f"Chyba při čtení cílů: {e}")
        return

    alerts = []
    
    # 3. Hlavní smyčka pro spouštění alarmů
    for index, row in df_targets.iterrows():
        ticker = row['Ticker']
        target_buy = row['TargetBuy']
        target_sell = row['TargetSell']

        # Získání živé ceny
        current_price, currency = get_data_safe(ticker)
        currency = currency if currency else 'USD'
        
        if current_price is None:
            print(f"⚠️ Cena pro {ticker} nedostupná, přeskočeno.")
            continue
        
        # --- BUY ALARM (Nákupní příležitost) ---
        if target_buy > 0 and current_price <= target_buy:
            alerts.append(
                f"🔴 **BUY ALERT!** {ticker} je na slevě!\n"
                f"Nyní: {current_price:,.2f} {currency} (Tvůj cíl: {target_buy:,.2f} {currency})"
            )
        
        # --- SELL ALARM (Dosažení cíle) ---
        if target_sell > 0 and current_price >= target_sell:
            alerts.append(
                f"🟢 **SELL ALERT!** {ticker} dosáhlo cíle!\n"
                f"Nyní: {current_price:,.2f} {currency} (Tvůj cíl: {target_sell:,.2f} {currency})"
            )

    # 4. Odeslání zprávy
    if alerts:
        header = "*🚨 HODINOVÝ PRICE ALARM REPORT 🚨*\n\n"
        final_message = header + "\n" + ("\n---\n".join(alerts))
        success, msg = send_telegram_message(final_message)
        
        if success:
            print("Alarmy odeslány.")
        else:
            print(f"Chyba odesílání Telegramu: {msg}")
    else:
        print("Vše v pořádku, žádné alarmy.")


if __name__ == "__main__":
    run_alert_bot()
