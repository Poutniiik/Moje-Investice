import pandas as pd
import yfinance as yf
import requests
import os

# --- TELEGRAM FUNKCE ---
def send_telegram_message(message):
    TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
    
    if not TOKEN or not CHAT_ID:
        print("Chybí Telegram token nebo ID chatu.")
        return False

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    try:
        response = requests.post(url, data=payload, timeout=5)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Chyba při odesílání Telegramu: {e}")
        return False

# --- FUNKCE PRO STAHUJÍCÍ CENY ---
def get_data_safe(ticker):
    try:
        t = yf.Ticker(ticker)
        # Používáme fast_info, je nejrychlejší a nejspolehlivější pro aktuální cenu
        price = t.fast_info.last_price
        currency = t.fast_info.currency
        return price, currency
    except Exception:
        return None, None

# --- HLAVNÍ LOGIKA HLÍDAČE ---
def run_alert_bot():
    print("🔔 Spouštím Price Alert Bota...")
    
    # Předpoklad: portfolio_data.csv je v kořenové složce
    try:
        df = pd.read_csv("portfolio_data.csv")
    except FileNotFoundError:
        print("Chyba: Soubor portfolio_data.csv nenalezen.")
        return

    alerts = []
    
    # 1. Získáme všechny unikátní tikery, které musíme zkontrolovat
    tickers_to_check = df['TICKER'].unique().tolist()

    # 2. Iterujeme přes všechny tikery a kontrolujeme TARGET_PRICE
    for ticker in tickers_to_check:
        
        # Získáme řádek pro daný ticker (zde je target cena)
        ticker_data = df[df['TICKER'] == ticker].iloc[0]
        target_price = ticker_data.get('TARGET_PRICE', 0.0)
        
        # Ignorujeme, pokud není nastaven TARGET_PRICE
        if target_price == 0.0:
            continue
        
        # Získáme aktuální cenu
        current_price, currency = get_data_safe(ticker)
        
        if current_price is None:
            alerts.append(f"⚠️ **{ticker}**: Cena nedostupná (skip).")
            continue
        
        # Logika pro spuštění alarmu:
        # A) Cílová cena je vyšší než nákupní cena (Chceme prodat!)
        if target_price > ticker_data['AVG_PRICE']:
            # Pokud AKTUALNÍ CENA VYSTOUPLA NAD CÍL
            if current_price >= target_price:
                alerts.append(f"🟢 **SELL ALERT!** {ticker} dosáhlo cíle! {current_price:.2f} {currency} (Cíl: {target_price:.2f})")
        
        # B) Cílová cena je nižší než nákupní cena (Chceme nakoupit!)
        elif target_price < ticker_data['AVG_PRICE']:
             # Pokud AKTUALNÍ CENA KLESLA POD CÍL
             if current_price <= target_price:
                alerts.append(f"🔴 **BUY ALERT!** {ticker} je na slevě! {current_price:.2f} {currency} (Cíl: {target_price:.2f})")

    # 3. Odeslání zprávy
    if alerts:
        header = "*🚨 PRICE ALARM REPORT 🚨*\n\n"
        final_message = header + "\n\n".join(alerts)
        send_telegram_message(final_message)
        print("Alarmy odeslány.")
    else:
        print("Vše v pořádku, žádné alarmy.")


if __name__ == "__main__":
    run_alert_bot()
