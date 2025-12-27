import pandas as pd
import yfinance as yf
import requests
import os
import time
from io import StringIO
from github import Github 

# --- KONFIGURACE A TAJEMSTVÍ ---
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO_NAZEV = "Poutniiik/Moje-Investice"

# ZMĚNA: Sjednoceno na TELEGRAM_BOT_TOKEN pro celý projekt
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# --- FUNKCE PRO GITHUB (Cloud Sync) ---
def download_csv_from_github(filename):
    """Stáhne aktuální CSV data přímo z GitHubu."""
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

# --- TELEGRAM FUNKCE ---
def send_telegram_message(message):
    """Odešle zprávu na Telegram s využitím sjednoceného tokenu."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Chybí TELEGRAM_BOT_TOKEN nebo TELEGRAM_CHAT_ID.")
        return False, "Chybí token"

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    try:
        response = requests.post(url, data=payload, timeout=5)
        response.raise_for_status()
        return True, "Odesláno"
    except Exception as e:
        print(f"❌ Chyba při odesílání Telegramu: {e}")
        return False, str(e)

# --- TECHNICKÁ ANALÝZA (RSI) ---
def calculate_rsi(series, period=14):
    """Vypočítá RSI (Relative Strength Index)."""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)

    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if not rsi.empty else 50

# --- SMART DATA FETCH ---
def get_market_data_smart(ticker):
    """
    Stáhne cenu A historii pro výpočet RSI.
    Vrací: (price, currency, rsi)
    """
    try:
        t = yf.Ticker(ticker)
        
        # 1. Aktuální cena (Fast info)
        price = t.fast_info.last_price
        currency = t.fast_info.currency
        if not currency: currency = "USD"
        
        # 2. Historie pro RSI (stačí 1 měsíc)
        # Používáme period="1mo" aby bylo dost dat pro 14denní průměr
        hist = t.history(period="1mo")
        
        rsi = 50 # Default neutrální
        if not hist.empty and len(hist) > 14:
            rsi = calculate_rsi(hist['Close'])
            
        return float(price), currency, float(rsi)

    except Exception as e:
        print(f"⚠️ Chyba dat pro {ticker}: {e}")
        # Fallback - zkusíme aspoň cenu bez RSI
        try:
            d = yf.download(ticker, period="1d", progress=False)['Close'].iloc[-1]
            return float(d), "USD", 50
        except:
            return None, None, None

# --- HLAVNÍ LOGIKA ---
def run_alert_bot():
    print("🧠 Spouštím SMART Alert Bota (RSI Edition)...")
    
    WATCHLIST_FILE = "watchlist.csv"
    TARGET_OWNER = 'Attis' 
    
    # 1. Načtení Watchlistu
    df_w = download_csv_from_github(WATCHLIST_FILE)
    if df_w is None:
        print(f"❌ Chyba: {WATCHLIST_FILE} nedostupný.")
        return

    # Filtrování
    if 'Owner' in df_w.columns:
        df_targets = df_w[df_w['Owner'].astype(str) == TARGET_OWNER].copy()
    else:
        df_targets = df_w.copy()

    # Kontrola sloupců
    if 'TargetBuy' not in df_targets.columns: df_targets['TargetBuy'] = 0.0
    if 'TargetSell' not in df_targets.columns: df_targets['TargetSell'] = 0.0
    
    # Jen aktivní cíle
    df_targets = df_targets.fillna(0)
    df_targets = df_targets[(df_targets['TargetBuy'] > 0) | (df_targets['TargetSell'] > 0)]

    alerts = []
    
    print(f"🔍 Kontroluji {len(df_targets)} cílů...")

    for index, row in df_targets.iterrows():
        ticker = row['Ticker']
        t_buy = row['TargetBuy']
        t_sell = row['TargetSell']

        # Získání chytrých dat
        price, curr, rsi = get_market_data_smart(ticker)
        
        if price is None: continue
        
        # --- LOGIKA NÁKUPU (BUY) ---
        if t_buy > 0 and price <= t_buy:
            # RSI Analýza
            if rsi < 30:
                signal = "🔥 **STRONG BUY (Přeprodáno)**"
                rsi_text = f"📉 RSI: {rsi:.0f} (Extrémně levné!)"
            elif rsi < 45:
                signal = "✅ **BUY SIGNÁL**"
                rsi_text = f"RSI: {rsi:.0f} (Vhodné)"
            else:
                signal = "⚠️ **Target Hit (Ale RSI vysoko)**"
                rsi_text = f"RSI: {rsi:.0f} (Pozor, stále drahé)"

            alerts.append(
                f"{signal}\n"
                f"🎯 **{ticker}** je na ceně {price:,.2f} {curr}\n"
                f"(Cíl: {t_buy:,.2f} {curr}) | {rsi_text}"
            )
        
        # --- LOGIKA PRODEJE (SELL) ---
        if t_sell > 0 and price >= t_sell:
            # RSI Analýza
            if rsi > 70:
                signal = "💰 **PERFECT SELL (Překoupeno)**"
                rsi_text = f"📈 RSI: {rsi:.0f} (Vrchol?)"
            else:
                signal = "✅ **SELL SIGNÁL**"
                rsi_text = f"RSI: {rsi:.0f}"

            alerts.append(
                f"{signal}\n"
                f"🎯 **{ticker}** dosáhl {price:,.2f} {curr}\n"
                f"(Cíl: {t_sell:,.2f} {curr}) | {rsi_text}"
            )

    # Odeslání
    if alerts:
        header = "*🧠 SMART ALERT REPORT 🧠*\n\n"
        final_msg = header + "\n---\n".join(alerts)
        send_telegram_message(final_msg)
        print("✅ Alert odeslán.")
    else:
        print("💤 Žádné signály.")

if __name__ == "__main__":
    run_alert_bot()
