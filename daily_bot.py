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
        # Povolíme HTML pro tučné písmo
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"})
    except Exception as e:
        print(f"❌ Chyba Telegram: {e}")

def get_data_safe(ticker):
    """
    Stáhne cenu A TAKÉ denní změnu v procentech.
    Vrací: (cena, zmena_procent)
    """
    try:
        t = yf.Ticker(ticker)
        
        # Zkusíme historii za 5 dní (abychom měli předchozí zavírací cenu)
        hist = t.history(period="5d", auto_adjust=True)
        
        if not hist.empty and len(hist) >= 1:
            price = float(hist['Close'].iloc[-1])
            
            # Výpočet změny oproti předchozímu dni (pokud máme data)
            change = 0.0
            if len(hist) >= 2:
                prev_close = float(hist['Close'].iloc[-2])
                change = ((price - prev_close) / prev_close) * 100
            
            return price, change
            
    except Exception as e:
        print(f"   ⚠️ Chyba u {ticker}: {e}")
    
    return 0.0, 0.0

def main():
    print("🦎 ROBOT REPORTÉR STARTUJE...")

    # 1. NAČTENÍ CSV
    try:
        df = pd.read_csv("portfolio_data.csv")
        df['Ticker'] = df['Ticker'].astype(str).str.strip().str.upper()
        df['Pocet'] = pd.to_numeric(df['Pocet'], errors='coerce').fillna(0)
    except Exception as e:
        print(f"❌ Chyba CSV: {e}")
        return

    if df.empty: return

    # 2. KURZY (Stáhneme bezpečně)
    print("💱 Stahuji kurzy...")
    usd_czk, _ = get_data_safe("CZK=X")
    if usd_czk == 0: usd_czk = 24.0 # Fallback
    
    eur_usd, _ = get_data_safe("EURUSD=X")
    if eur_usd == 0: eur_usd = 1.08 # Fallback
    
    print(f"   USD/CZK={usd_czk:.2f}, EUR/USD={eur_usd:.2f}")

    # 3. VÝPOČET PORTFOLIA
    portfolio_items = [] # Sem si uložíme výsledky pro seřazení
    total_val_czk = 0
    
    print("--- Start výpočtu akcií ---")
    for index, row in df.iterrows():
        ticker = row['Ticker']
        kusy = row['Pocet']
        
        # Stáhneme cenu a změnu
        price, change = get_data_safe(ticker)
        time.sleep(0.2) # Malá pauza pro Yahoo
        
        if price > 0:
            # Přepočet na CZK
            val_czk = 0
            if ticker.endswith(".PR"): val_czk = price * kusy
            elif ticker.endswith(".DE"): val_czk = price * kusy * eur_usd * usd_czk
            else: val_czk = price * kusy * usd_czk
            
            total_val_czk += val_czk
            
            # Uložíme si data pro report
            portfolio_items.append({
                "ticker": ticker,
                "value_czk": val_czk,
                "change": change
            })
            print(f"✅ {ticker}: {change:+.2f}% | {val_czk:,.0f} CZK")
        else:
            print(f"❌ {ticker}: Data nedostupná")

    # 4. SESTAVENÍ REPORTU
    # Seřadíme podle denní změny (nejlepší nahoře)
    sorted_items = sorted(portfolio_items, key=lambda x: x['change'], reverse=True)
    
    # Najdeme vítěze a poraženého
    best = sorted_items[0] if sorted_items else None
    worst = sorted_items[-1] if sorted_items else None
    
    # Hlavička zprávy
    emoji_total = "🤑" if total_val_czk > 0 else "🤷‍♂️"
    msg = f"<b>📊 DENNÍ UPDATE</b>\n"
    msg += f"📅 {datetime.datetime.now().strftime('%d.%m.%Y')}\n"
    msg += f"--------------------------------\n"
    msg += f"{emoji_total} <b>CELKEM: {total_val_czk:,.0f} Kč</b>\n"
    msg += f"💵 Kurz USD: {usd_czk:.2f} Kč\n\n"
    
    # Sekce Top/Flop (jen pokud máme aspoň 2 akcie)
    if len(sorted_items) >= 2:
        msg += f"🚀 <b>Top:</b> {best['ticker']} ({best['change']:+.2f}%)\n"
        msg += f"💀 <b>Flop:</b> {worst['ticker']} ({worst['change']:+.2f}%)\n"
        msg += f"--------------------------------\n"
    
    # Sekce Detail (Seznam)
    msg += "<b>📋 Detail portfolia:</b>\n"
    for item in sorted_items:
        # Vybereme ikonku podle změny
        icon = "🟢" if item['change'] >= 0 else "🔴"
        # Zarovnáme text, aby to vypadalo hezky
        msg += f"{icon} <b>{item['ticker']}</b>: {item['change']:+.1f}%  ({item['value_czk']/1000:.1f}k)\n"
    
    msg += f"\n<i>(Chameleon V2 🦎)</i>"

    # 5. ODESLÁNÍ
    send_telegram(msg)

if __name__ == "__main__":
    main()
