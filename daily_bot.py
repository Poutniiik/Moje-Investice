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
        print("📨 Zpráva odeslána na Telegram.")
    except Exception as e:
        print(f"❌ Chyba Telegram: {e}")

def get_data_safe(ticker):
    """Stáhne cenu a denní změnu v %."""
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="5d", auto_adjust=True)
        
        if not hist.empty and len(hist) >= 1:
            price = float(hist['Close'].iloc[-1])
            change = 0.0
            if len(hist) >= 2:
                prev_close = float(hist['Close'].iloc[-2])
                change = ((price - prev_close) / prev_close) * 100
            return price, change
    except Exception as e:
        print(f"   ⚠️ Chyba stahování u {ticker}: {e}")
    return 0.0, 0.0

def save_history(total_czk, usd_czk):
    """Zapíše dnešní hodnotu do historie pro graf."""
    try:
        # Převedeme na USD (graf v aplikaci je v USD)
        total_usd = total_czk / usd_czk if usd_czk > 0 else 0
        filename = "value_history.csv"
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # Pokud soubor neexistuje, vytvoříme hlavičku
        if not os.path.exists(filename):
            with open(filename, "w") as f:
                f.write("Date,TotalUSD,Owner\n")
        
        # Připíšeme řádek
        with open(filename, "a") as f:
            f.write(f"{today},{total_usd:.2f},admin\n")
            
        print(f"💾 ULOŽENO DO HISTORIE: {today} | ${total_usd:.2f} (kurz {usd_czk:.2f})")
        return True
    except Exception as e:
        print(f"❌ Chyba ukládání historie: {e}")
        return False

def main():
    print("🤖 ROBOT 'KOMPLET' STARTUJE...")

    # 1. NAČTENÍ A SLOUČENÍ
    try:
        df = pd.read_csv("portfolio_data.csv")
        df['Ticker'] = df['Ticker'].astype(str).str.strip().str.upper()
        df['Pocet'] = pd.to_numeric(df['Pocet'], errors='coerce').fillna(0)
        
        # Sloučení stejných tickerů (aby nebyl ve zprávě Adidas 4x)
        original_len = len(df)
        df = df.groupby('Ticker', as_index=False)['Pocet'].sum()
        print(f"📂 Načteno {original_len} řádků, sloučeno do {len(df)} unikátních firem.")
        
    except Exception as e:
        print(f"❌ Chyba CSV: {e}")
        return

    if df.empty: 
        print("⚠️ Portfolio je prázdné.")
        return

    # 2. KURZY
    print("💱 Stahuji kurzy...")
    usd_czk, _ = get_data_safe("CZK=X")
    if usd_czk == 0: usd_czk = 24.0
    
    eur_usd, _ = get_data_safe("EURUSD=X")
    if eur_usd == 0: eur_usd = 1.08
    
    print(f"   USD/CZK={usd_czk:.2f}, EUR/USD={eur_usd:.2f}")

    # 3. VÝPOČET
    portfolio_items = []
    total_val_czk = 0
    
    print("--- Start výpočtu akcií ---")
    for index, row in df.iterrows():
        ticker = row['Ticker']
        kusy = row['Pocet']
        
        price, change = get_data_safe(ticker)
        # Pauza pro Yahoo (Chameleon)
        time.sleep(0.2)
        
        if price > 0:
            val_czk = 0
            if ticker.endswith(".PR"): val_czk = price * kusy
            elif ticker.endswith(".DE"): val_czk = price * kusy * eur_usd * usd_czk
            else: val_czk = price * kusy * usd_czk
            
            total_val_czk += val_czk
            portfolio_items.append({"ticker": ticker, "value_czk": val_czk, "change": change})
            print(f"✅ {ticker}: {change:+.2f}% | {val_czk:,.0f} CZK")
        else:
            print(f"❌ {ticker}: Data nedostupná")

    print(f"💰 CELKEM: {total_val_czk:,.0f} CZK")

    # 4. ULOŽENÍ DO HISTORIE
    save_history(total_val_czk, usd_czk)

    # 5. ODESLÁNÍ REPORTU
    # Seřadíme podle změny (největší růst nahoře)
    sorted_items = sorted(portfolio_items, key=lambda x: x['change'], reverse=True)
    
    # Sestavení zprávy
    emoji_total = "🤑" if total_val_czk > 0 else "🤷‍♂️"
    msg = f"<b>📊 DENNÍ UPDATE</b>\n"
    msg += f"📅 {datetime.datetime.now().strftime('%d.%m.%Y')}\n"
    msg += f"----------------\n"
    msg += f"{emoji_total} <b>CELKEM: {total_val_czk:,.0f} Kč</b>\n"
    msg += f"💵 Kurz USD: {usd_czk:.2f} Kč\n\n"
    
    msg += "<b>📋 Detail:</b>\n"
    for item in sorted_items:
        icon = "🟢" if item['change'] >= 0 else "🔴"
        # Formát: 🟢 AAPL: +1.5%
        msg += f"{icon} <b>{item['ticker']}</b>: {item['change']:+.1f}%\n"
    
    msg += "\n<i>(Uloženo do grafu 💾)</i>"
    
    send_telegram(msg)

if __name__ == "__main__":
    main()
