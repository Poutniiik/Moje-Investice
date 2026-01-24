import pandas as pd
import yfinance as yf
import requests
import os
import time
from io import StringIO
from github import Github 

# --- KONFIGURACE ---
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO_NAZEV = "Poutniiik/Moje-Investice"
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
TARGET_OWNER = 'Attis'

# --- FUNKCE PRO GITHUB ---
def download_csv_from_github(filename):
    """Stáhne aktuální CSV data přímo z GitHubu."""
    if not GITHUB_TOKEN:
        print("⚠️ GITHUB_TOKEN chybí. Zkouším číst lokální soubor.")
        if os.path.exists(filename): return pd.read_csv(filename)
        return None

    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAZEV)
        contents = repo.get_contents(filename)
        csv_data = contents.decoded_content.decode("utf-8")
        return pd.read_csv(StringIO(csv_data))
    except Exception as e:
        print(f"❌ Chyba stahování z GitHubu ({filename}): {e}")
        if os.path.exists(filename): return pd.read_csv(filename)
        return None

# --- TELEGRAM ---
def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Chybí tokeny.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, data=payload, timeout=5)
        print("📨 Zpráva odeslána.")
    except Exception as e:
        print(f"❌ Chyba Telegram: {e}")

# --- RSI KALKULAČKA ---
def calculate_rsi_series(series, period=14):
    """Vypočítá RSI z celé časové řady."""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)
    
    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# --- TURBO SKENOVÁNÍ ---
def check_alerts_batch(df_targets):
    """
    Stáhne data pro všechny cíle naráz a vyhodnotí je.
    """
    tickers = df_targets['Ticker'].unique().tolist()
    # Přidáme měny pro jistotu
    tickers_download = list(set(tickers + ["CZK=X", "EURUSD=X"]))
    
    print(f"🚀 Turbo Sken: Stahuji data pro {len(tickers_download)} tickerů...")
    
    # Stahujeme 2 měsíce, abychom měli dost dat pro RSI
    try:
        batch = yf.download(tickers_download, period="2mo", group_by='ticker', progress=False)
    except Exception as e:
        print(f"❌ Chyba stahování: {e}")
        return []

    alerts = []

    for index, row in df_targets.iterrows():
        tk = row['Ticker']
        t_buy = row['TargetBuy']
        t_sell = row['TargetSell']
        
        # Extrakce dat z batche
        try:
            if len(tickers_download) > 1:
                if tk in batch.columns.levels[0]:
                    hist = batch[tk]['Close'].dropna()
                else:
                    print(f"⚠️ Data pro {tk} nejsou v batchi.")
                    continue
            else:
                hist = batch['Close'].dropna()

            if hist.empty: continue
            
            # Poslední cena a RSI
            price = float(hist.iloc[-1])
            
            # RSI potřebuje aspoň 14 dní
            rsi = 50.0
            if len(hist) > 14:
                rsi_series = calculate_rsi_series(hist)
                rsi = float(rsi_series.iloc[-1])

            # Měna (jednoduchý odhad)
            curr = "USD"
            if ".PR" in tk: curr = "CZK"
            elif ".DE" in tk: curr = "EUR"

            # --- VYHODNOCENÍ ---
            signal = None
            
            # Nákup?
            if t_buy > 0 and price <= t_buy:
                icon = "🔥" if rsi < 35 else "✅"
                rsi_txt = f"(RSI: {rsi:.0f} - Levné!)" if rsi < 35 else f"(RSI: {rsi:.0f})"
                signal = f"{icon} **NÁKUP: {tk}**\nCena: {price:,.2f} {curr}\nCíl: {t_buy:,.2f} {curr}\n{rsi_txt}"
            
            # Prodej?
            elif t_sell > 0 and price >= t_sell:
                icon = "💰" if rsi > 65 else "✅"
                rsi_txt = f"(RSI: {rsi:.0f} - Přehřáté!)" if rsi > 65 else f"(RSI: {rsi:.0f})"
                signal = f"{icon} **PRODEJ: {tk}**\nCena: {price:,.2f} {curr}\nCíl: {t_sell:,.2f} {curr}\n{rsi_txt}"

            if signal:
                alerts.append(signal)
                print(f"🔔 ALERT: {tk}")

        except Exception as e:
            print(f"Chyba u {tk}: {e}")
            continue

    return alerts

# --- MAIN ---
def run_alert_bot():
    print("👀 Spouštím Turbo Alert Bot...")
    
    # 1. Načtení Watchlistu
    df_w = download_csv_from_github("watchlist.csv")
    if df_w is None or df_w.empty:
        print("❌ Watchlist je prázdný nebo nedostupný.")
        return

    # Filtrování vlastníka a aktivních cílů
    if 'Owner' in df_w.columns:
        df_w = df_w[df_w['Owner'].astype(str) == TARGET_OWNER]
    
    df_targets = df_w[(df_w['TargetBuy'] > 0) | (df_w['TargetSell'] > 0)].copy()
    
    if df_targets.empty:
        print("💤 Žádné aktivní cíle.")
        return

    # 2. Kontrola
    found_alerts = check_alerts_batch(df_targets)
    
    # 3. Odeslání
    if found_alerts:
        msg = "*🚨 MARKET RADAR 🚨*\n\n" + "\n---\n".join(found_alerts)
        send_telegram_message(msg)
    else:
        print("✅ Žádné cíle zasaženy.")

if __name__ == "__main__":
    run_alert_bot()
