import pandas as pd
import yfinance as yf
import requests
import os
import datetime

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

def main():
    print("🕵️‍♂️ DETEKTIVNÍ ROBOT STARTUJE...")

    # 1. NAČTENÍ CSV
    try:
        df = pd.read_csv("portfolio_data.csv")
        # ČIŠTĚNÍ DAT: Oříznout mezery a dát na velká písmena
        df['Ticker'] = df['Ticker'].astype(str).str.strip().str.upper()
        df['Pocet'] = pd.to_numeric(df['Pocet'], errors='coerce').fillna(0)
        print(f"📂 CSV načteno. Obsahuje tickery: {df['Ticker'].unique().tolist()}")
    except Exception as e:
        print(f"❌ Chyba CSV: {e}")
        return

    if df.empty:
        print("⚠️ Portfolio je prázdné.")
        return

    # 2. STAŽENÍ DAT
    tickers = df['Ticker'].unique().tolist()
    # Přidáme měny
    if "CZK=X" not in tickers: tickers.append("CZK=X")
    if "EURUSD=X" not in tickers: tickers.append("EURUSD=X")

    print(f"📥 Stahuji data pro: {tickers}")
    
    # Stahujeme 5 dní dozadu, abychom chytili páteční cenu i v neděli
    try:
        data = yf.download(tickers, period="5d", progress=False, auto_adjust=True)['Close']
    except Exception as e:
        print(f"❌ Chyba YFinance: {e}")
        return

    # 3. PŘEVOD NA JEDNODUCHOU MAPU {Ticker: Cena}
    price_map = {}
    
    # Pokud stahujeme jen 1 věc, je to Series. Pokud víc, je to DataFrame.
    if len(tickers) == 1:
        # Většinou se nestane, protože přidáváme měny, ale pro jistotu
        last_val = data.iloc[-1]
        price_map[tickers[0]] = float(last_val)
    else:
        # Vezmeme poslední řádek (poslední známé ceny)
        last_row = data.iloc[-1]
        for col in last_row.index:
            # col může být název tickeru
            val = last_row[col]
            if pd.notna(val):
                price_map[col] = float(val)

    print(f"🗺️ Mapa cen (co jsme reálně stáhli): {list(price_map.keys())}")
    
    # Získání kurzů
    usd_czk = price_map.get("CZK=X", 24.0)
    eur_usd = price_map.get("EURUSD=X", 1.08)
    print(f"💱 Kurzy: USD/CZK={usd_czk}, EUR/USD={eur_usd}")

    # 4. VÝPOČET
    total_val_czk = 0
    
    for index, row in df.iterrows():
        ticker = row['Ticker']
        kusy = row['Pocet']
        
        # Zkusíme najít cenu
        price = price_map.get(ticker, 0)
        
        # DEBUG VÝPIS
        if price == 0:
            print(f"⚠️ PROBLÉM: Ticker '{ticker}' v mapě cen není! (Mám: {list(price_map.keys())})")
        
        # Přepočet
        val_czk = 0
        if ticker.endswith(".PR"): val_czk = price * kusy
        elif ticker.endswith(".DE"): val_czk = price * kusy * eur_usd * usd_czk
        else: val_czk = price * kusy * usd_czk
        
        total_val_czk += val_czk
        if price > 0:
            print(f"✅ {ticker}: {kusy}ks * {price:.1f} = {val_czk:.0f} CZK")

    # 5. ODESLÁNÍ
    msg = f"<b>🤖 TEST ROBOT</b>\n💰 Celkem: {total_val_czk:,.0f} CZK\n(Detailní log viz GitHub Actions)"
    send_telegram(msg)

if __name__ == "__main__":
    main()
