import pandas as pd
import yfinance as yf
import requests
import os
import datetime

# --- KONFIGURACE ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ CHYBA: Chybí Telegram Token nebo Chat ID v Secrets!")
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
            print("✅ Zpráva odeslána na Telegram.")
        else:
            print(f"❌ Chyba odeslání Telegramu: {r.text}")
    except Exception as e:
        print(f"❌ Chyba spojení s Telegramem: {e}")

def main():
    print("🤖 Robot startuje...")
    
    # 1. Načtení portfolia
    try:
        df = pd.read_csv("portfolio_data.csv")
        # OPRAVA NAN: Převedeme sloupce na čísla násilím, chyby nahradíme nulou
        df['Pocet'] = pd.to_numeric(df['Pocet'], errors='coerce').fillna(0)
        print(f"📂 Načteno {len(df)} pozic z CSV.")
    except FileNotFoundError:
        print("⚠️ Soubor portfolio_data.csv nenalezen. Končím.")
        send_telegram("⚠️ <b>Chyba robota:</b> Nenalezen soubor s daty.")
        return

    if df.empty:
        print("⚠️ Portfolio je prázdné.")
        return

    # 2. Získání aktuálních cen
    tickers = df['Ticker'].unique().tolist()
    # Přidáme měny pro jistotu
    tickers_all = list(set(tickers + ["CZK=X", "EURUSD=X"]))
    
    print(f"🔍 Stahuji data pro: {tickers_all}")
    
    try:
        # Přidáno auto_adjust=True pro opravu chyb YFinance
        downloaded = yf.download(tickers_all, period="1d", progress=False, auto_adjust=True)
        
        # Ošetření, zda je to MultiIndex (nový yfinance) nebo ne
        if isinstance(downloaded.columns, pd.MultiIndex):
            live_data = downloaded['Close'].iloc[-1]
        else:
            live_data = downloaded['Close'].iloc[-1]
            
    except Exception as e:
        print(f"❌ Chyba stahování dat: {e}")
        send_telegram(f"⚠️ <b>Chyba robota:</b> Selhalo stahování dat ({e})")
        return

    # Získání kurzů s fallbackem
    try:
        usd_czk = float(live_data.get("CZK=X", 24.0))
        eur_usd = float(live_data.get("EURUSD=X", 1.08))
    except:
        usd_czk = 24.0
        eur_usd = 1.08
    
    print(f"💱 Kurzy: USD/CZK={usd_czk:.2f}, EUR/USD={eur_usd:.2f}")

    # 3. Výpočet hodnoty
    total_val_czk = 0
    
    print("--- Detailní výpočet ---")
    for index, row in df.iterrows():
        ticker = row['Ticker']
        kusy = row['Pocet']
        
        # Získání ceny (ošetření NaN)
        try:
            # .get() vrátí hodnotu nebo 0, pokud ticker v datech není
            price = float(live_data.get(ticker, 0))
        except:
            price = 0
            
        if price == 0 or pd.isna(price):
            print(f"⚠️ {ticker}: Cena nenalezena nebo 0.")
            continue

        # Přepočet měny
        val_czk = 0
        ticker_str = str(ticker).upper()
        
        if ticker_str.endswith(".PR"): # CZK akcie
            val_czk = price * kusy
        elif ticker_str.endswith(".DE"): # EUR akcie
            val_czk = price * kusy * eur_usd * usd_czk
        else: # USD akcie (default)
            val_czk = price * kusy * usd_czk
            
        print(f"📈 {ticker}: {kusy} ks * {price:.2f} = {val_czk:.0f} CZK")
        total_val_czk += val_czk

    print(f"💰 Celkem: {total_val_czk:,.0f} CZK")

    # 4. Sestavení zprávy
    # Emoji podle toho, jestli tam vůbec něco je
    emoji = "🤑" if total_val_czk > 0 else "🤔"
    
    msg = f"""
<b>🤖 DENNÍ REPORT</b>
📅 {datetime.datetime.now().strftime('%d.%m.%Y')}
-----------------------------
{emoji} <b>Celková hodnota:</b> {total_val_czk:,.0f} Kč
💵 <b>Kurz USD:</b> {usd_czk:.2f} Kč

<i>(Data z GitHub Actions)</i>
    """
    
    # 5. Odeslání
    send_telegram(msg)

if __name__ == "__main__":
    main()
