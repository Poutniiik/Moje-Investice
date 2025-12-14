import pandas as pd
import yfinance as yf
import requests
import os
import datetime
import time

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ CHYBA: Chybí tokeny.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"})
    except Exception as e:
        print(f"❌ Chyba Telegram: {e}")

def get_price_safe(ticker):
    """Stáhne cenu pro jeden ticker s maskováním za prohlížeč."""
    try:
        # Trik: Vytvoříme 'Ticker' objekt
        t = yf.Ticker(ticker)
        
        # 1. Pokus: Rychlé info
        try:
            price = t.fast_info.last_price
            if price and price > 0: return float(price)
        except: pass
        
        # 2. Pokus: Historie (poslední zavírací cena)
        hist = t.history(period="5d", auto_adjust=True)
        if not hist.empty:
            return float(hist['Close'].iloc[-1])
            
    except Exception as e:
        print(f"   ⚠️ Chyba u {ticker}: {e}")
    
    return 0.0

def main():
    print("🦎 ROBOT CHAMELEON STARTUJE...")

    # 1. NAČTENÍ CSV
    try:
        df = pd.read_csv("portfolio_data.csv")
        df['Ticker'] = df['Ticker'].astype(str).str.strip().str.upper()
        df['Pocet'] = pd.to_numeric(df['Pocet'], errors='coerce').fillna(0)
    except Exception as e:
        print(f"❌ Chyba CSV: {e}")
        return

    if df.empty: return

    # 2. SEZNAM TICKERŮ
    tickers = df['Ticker'].unique().tolist()
    
    # 3. STAHOVÁNÍ PO JEDNOM (Abychom nebyli nápadní)
    print(f"📥 Stahuji ceny postupně pro: {tickers}")
    
    # Stáhneme kurzy
    usd_czk = get_price_safe("CZK=X")
    if usd_czk == 0: usd_czk = 24.0 # Fallback
    
    eur_usd = get_price_safe("EURUSD=X")
    if eur_usd == 0: eur_usd = 1.08 # Fallback
    
    print(f"💱 Kurzy: USD/CZK={usd_czk:.2f}, EUR/USD={eur_usd:.2f}")

    # 4. VÝPOČET
    total_val_czk = 0
    
    print("--- Start výpočtu ---")
    for index, row in df.iterrows():
        ticker = row['Ticker']
        kusy = row['Pocet']
        
        # Stáhneme cenu pro konkrétní akcii
        price = get_price_safe(ticker)
        
        # Debug výpis
        if price == 0:
            print(f"❌ {ticker}: Yahoo blokuje nebo data nejsou.")
        else:
            # Přepočet
            val_czk = 0
            if ticker.endswith(".PR"): val_czk = price * kusy
            elif ticker.endswith(".DE"): val_czk = price * kusy * eur_usd * usd_czk
            else: val_czk = price * kusy * usd_czk
            
            print(f"✅ {ticker}: {price:.2f} (Hodnota: {val_czk:,.0f} CZK)")
            total_val_czk += val_czk
            
        # Malá pauza, abychom nezahltili server (anti-spam)
        time.sleep(0.5)

    print(f"💰 Celkem: {total_val_czk:,.0f} CZK")

    # 5. ODESLÁNÍ
    emoji = "🤑" if total_val_czk > 0 else "🔧"
    msg = f"""
<b>🤖 DENNÍ REPORT</b>
📅 {datetime.datetime.now().strftime('%d.%m.%Y')}
-----------------------------
{emoji} <b>Celková hodnota:</b> {total_val_czk:,.0f} Kč
💵 <b>Kurz USD:</b> {usd_czk:.2f} Kč

<i>(Chameleon Mode 🦎)</i>
    """
    send_telegram(msg)

if __name__ == "__main__":
    main()
