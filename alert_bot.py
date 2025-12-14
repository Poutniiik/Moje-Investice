import pandas as pd
import yfinance as yf
import requests
import os

# --- TELEGRAM FUNKCE ---
def send_telegram_message(message):
    # ... (tahle funkce je stejná, nech ji beze změny) ...
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
        price = t.fast_info.last_price
        currency = t.fast_info.currency
        return price, currency
    except Exception:
        return None, None

# --- HLAVNÍ LOGIKA HLÍDAČE ---
def run_alert_bot():
    print("🔔 Spouštím Price Alert Bota z targets.csv...")
    
    # NOVÉ: Čteme POUZE price_targets.csv
    TARGETS_FILE = "price_targets.csv"
    try:
        df_targets = pd.read_csv(TARGETS_FILE)
        # Odstraníme řádky, kde chybí TARGET_PRICE nebo je 0
        df_targets = df_targets.dropna(subset=['TARGET_PRICE'])
        df_targets = df_targets[df_targets['TARGET_PRICE'] > 0]
        if df_targets.empty:
            print("V price_targets.csv nejsou žádné aktivní cíle.")
            return

    except FileNotFoundError:
        print(f"Chyba: Soubor {TARGETS_FILE} nenalezen. Vytvořte ho.")
        return
    except Exception as e:
        print(f"Chyba při čtení cílů: {e}")
        return

    alerts = []
    
    # Používáme iteraci přes řádky nového DataFrame s cíli
    for index, row in df_targets.iterrows():
        ticker = row['TICKER']
        target_price = row['TARGET_PRICE']
        direction = str(row.get('DIRECTION', 'BUY')).upper() # default BUY

        current_price, currency = get_data_safe(ticker)
        
        if current_price is None:
            print(f"⚠️ Cena pro {ticker} nedostupná.")
            continue
        
        # Logika pro spuštění alarmu:
        
        # BUY ALARM: Cíl je NÍŽE než aktuální cena
        if direction == 'BUY':
            if current_price <= target_price:
                alerts.append(f"🔴 **BUY ALERT!** {ticker} je na slevě! Nyní {current_price:.2f} {currency} (Cíl: {target_price:.2f})")
        
        # SELL ALARM: Cíl je VÝŠE než aktuální cena
        elif direction == 'SELL':
            if current_price >= target_price:
                alerts.append(f"🟢 **SELL ALERT!** {ticker} dosáhlo cíle! Nyní {current_price:.2f} {currency} (Cíl: {target_price:.2f})")

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
