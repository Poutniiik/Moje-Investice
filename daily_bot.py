import pandas as pd
import yfinance as yf
import requests
import os
import datetime

# --- KONFIGURACE (Načte se z GitHub Secrets) ---
# Pokud testuješ lokálně, dosaď si sem hodnoty ručně, ale na GitHub nahrávej prázdné nebo os.environ
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Chybí Telegram Token nebo Chat ID")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        r = requests.post(url, json=payload)
        if r.status_code == 200:
            print("✅ Zpráva odeslána!")
        else:
            print(f"❌ Chyba odeslání: {r.text}")
    except Exception as e:
        print(f"❌ Chyba spojení: {e}")

def main():
    print("🤖 Robot startuje...")
    
    # 1. Načtení portfolia (lokálně, protože GitHub si repo stáhne k sobě)
    try:
        df = pd.read_csv("portfolio_data.csv")
        # Filtruj jen 'admin' nebo svého uživatele, pokud chceš
        # df = df[df['Owner'] == 'admin'] 
    except FileNotFoundError:
        print("⚠️ Soubor portfolio_data.csv nenalezen.")
        return

    if df.empty:
        print("⚠️ Portfolio je prázdné.")
        return

    # 2. Získání aktuálních cen
    tickers = df['Ticker'].unique().tolist()
    print(f"🔍 Stahuji data pro: {tickers}")
    
    # Hromadné stažení (rychlejší)
    live_data = yf.download(tickers, period="1d", progress=False)['Close']
    
    # Získání kurzů (zjednodušeně)
    kurzy = yf.download(["CZK=X", "EURUSD=X"], period="1d", progress=False)['Close']
    try:
        usd_czk = kurzy['CZK=X'].iloc[-1]
        eur_usd = kurzy['EURUSD=X'].iloc[-1]
    except:
        usd_czk = 23.50 # Fallback
        eur_usd = 1.08

    # 3. Výpočet hodnoty
    total_val_czk = 0
    total_invested_czk = 0 # Pokud máš sloupec 'Investice' nebo počítáš nákupní ceny
    
    top_mover = {"ticker": "", "change": -999}
    
    for index, row in df.iterrows():
        ticker = row['Ticker']
        kusy = row['Pocet']
        
        # Získání aktuální ceny
        try:
            if len(tickers) == 1:
                price = live_data.iloc[-1]
            else:
                price = live_data[ticker].iloc[-1]
        except:
            price = 0
            
        # Přepočet měny (zjednodušený detektor)
        if ".PR" in ticker: 
            val_czk = price * kusy
        elif ".DE" in ticker:
            val_czk = price * kusy * eur_usd * usd_czk
        else: # USD
            val_czk = price * kusy * usd_czk
            
        total_val_czk += val_czk

    # 4. Sestavení zprávy
    emoji = "🟢" if total_val_czk > 0 else "🔴" # Tady by to chtělo porovnání se včerejškem, ale pro jednoduchost stačí stav
    
    msg = f"""
<b>🤖 DENNÍ REPORT (GitHub Bot)</b>
📅 {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}
-----------------------------
💰 <b>Celková hodnota:</b> {total_val_czk:,.0f} Kč
💵 <b>Kurz USD/CZK:</b> {usd_czk:.2f}

<i>Data vygenerována automaticky z GitHub Actions.</i>
    """
    
    # 5. Odeslání
    send_telegram(msg)

if __name__ == "__main__":
    main()
