import pandas as pd
import yfinance as yf
import requests
import os
from datetime import datetime, timedelta

# --- TELEGRAM FUNKCE (Stejná jako v jiných botech) ---
def send_telegram_message(message):
    """Odešle zprávu na Telegram."""
    TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
    
    if not TOKEN or not CHAT_ID:
        print("Chybí Telegram token nebo ID chatu.")
        return False, "Chybí token"

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    # Důležité: Tady používáme HTML, abychom mohli snadno formátovat datum a čas
    payload = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'HTML'
    }
    try:
        response = requests.post(url, data=payload, timeout=5)
        response.raise_for_status()
        return True, "Odesláno"
    except Exception as e:
        print(f"Chyba při odesílání Telegramu: {e}")
        return False, str(e)

# --- FUNKCE PRO ZÍSKÁNÍ DATUMU VÝSLEDKŮ ---
def get_earnings_date(ticker):
    """Získá datum reportování výsledků pro daný ticker."""
    try:
        # yfinance bohužel nedává budoucí datum v 'info', musíme parsovat stránku
        # nebo použít pokročilejší API. Pro zjednodušení použijeme 'Calendar'
        # který je spolehlivější pro budoucí datum, pokud se k němu dá dostat
        
        t = yf.Ticker(ticker)
        # Hledáme budoucí datum, pokud existuje
        # Může to trvat déle než fast_info!
        earnings_date = t.calendar.loc['Earnings Date'][0]
        
        # Ošetření, že je to datum a není prázdné
        if pd.isna(earnings_date):
             return None
             
        # Převod na jednoduchý formát
        return earnings_date.strftime('%Y-%m-%d')
        
    except Exception:
        # Pokud se nezdaří, zkusíme najít alespoň poslední datum
        try:
             # Použití info pro zjištění posledních výsledků, pokud budoucí nejsou
             return t.info.get('lastFiscalYearEnd') 
        except:
             return None

# --- HLAVNÍ LOGIKA BOTa ---
def run_earnings_bot():
    print("🗓️ Spouštím Earnings Calendar Bota...")
    
    # 1. Definujeme časový rámec (Příští týden)
    today = datetime.now().date()
    # Bot běží v neděli. Chceme data od zítřka (pondělí) do příští neděle.
    start_date = today + timedelta(days=(7 - today.weekday()))
    end_date = start_date + timedelta(days=6)

    print(f"Hledám výsledky od {start_date} do {end_date}.")
    
    # Kde jsou uloženy tikety (Portfólio i Watchlist)
    PORTFOLIO_FILE = "data.csv"
    WATCHLIST_FILE = "watchlist.csv"
    TARGET_OWNER = 'Attis' # Stejný OWNER jako v Alert Botovi
    
    # Společný seznam Tickerů k ověření
    unique_tickers = set()

    # Načtení Portfolia (abychom věděli, co reportuje)
    try:
        df_p = pd.read_csv(PORTFOLIO_FILE)
        df_p = df_p[df_p['Owner'].astype(str) == TARGET_OWNER]
        unique_tickers.update(df_p['Ticker'].unique())
    except Exception:
        print(f"Chyba: Soubor {PORTFOLIO_FILE} nenalezen.")
    
    # Načtení Watchlistu (abychom věděli, co sledovat)
    try:
        df_w = pd.read_csv(WATCHLIST_FILE)
        df_w = df_w[df_w['Owner'].astype(str) == TARGET_OWNER]
        unique_tickers.update(df_w['Ticker'].unique())
    except Exception:
        print(f"Chyba: Soubor {WATCHLIST_FILE} nenalezen.")
        
    if not unique_tickers:
        print("Nenašel jsem žádné tickery v Portfoliu ani Watchlistu.")
        return

    earnings_list = []

    # 2. Iterace a získávání dat
    for ticker in unique_tickers:
        print(f"Kontroluji {ticker}...")
        date_str = get_earnings_date(ticker)
        
        if date_str:
            try:
                # Převedeme string na datum
                earnings_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                
                # Kontrola, zda datum spadá do příštího týdne
                if start_date <= earnings_date <= end_date:
                    earnings_list.append({
                        'Ticker': ticker,
                        'Date': earnings_date,
                        # Den v týdnu pro lepší čitelnost
                        'Day': earnings_date.strftime('%A')
                    })
            except ValueError:
                print(f"Nelze parsovat datum výsledků pro {ticker}: {date_str}")


    # 3. Sestavení zprávy
    if earnings_list:
        
        # Setřídíme podle data pro lepší přehlednost
        df_earnings = pd.DataFrame(earnings_list).sort_values(by='Date')
        
        report_parts = []
        for index, row in df_earnings.iterrows():
            # Převod anglického dne na český
            day_cz = {
                'Monday': 'Pondělí', 'Tuesday': 'Úterý', 'Wednesday': 'Středa', 
                'Thursday': 'Čtvrtek', 'Friday': 'Pátek'
            }.get(row['Day'], row['Day'])
            
            report_parts.append(
                f"<b>{row['Ticker']}</b>: {row['Date']} ({day_cz})"
            )

        header = f"<b>🗓️ EARNINGS KALENDÁŘ - PŘÍŠTÍ TÝDEN 🗓️</b>\n"
        body = "\n".join(report_parts)
        footer = "\n\n<i>Připravte se na volatilitu.</i>"

        final_message = header + "\n\n" + body + footer
        
        send_telegram_message(final_message)
        print("Earnings report odeslán.")
        
    else:
        send_telegram_message(f"<b>🗓️ EARNINGS KALENDÁŘ</b>\n\nPříští týden ({start_date} - {end_date}) nereportuje žádná sledovaná firma.")
        print("Žádné výsledky na obzoru.")

if __name__ == "__main__":
    run_earnings_bot()
