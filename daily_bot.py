import pandas as pd
import yfinance as yf
import requests
import os
import random
import datetime
import time
import json
import google.generativeai as genai
import matplotlib
import matplotlib.pyplot as plt

# Nastavíme backend pro servery bez monitoru
matplotlib.use('Agg')

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# --- NASTAVENÍ VLASTNÍKA ---
TARGET_OWNER = 'Attis' 

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"})
        print("📨 Telegram odeslán.")
    except Exception as e:
        print(f"❌ Chyba Telegram: {e}")

def send_telegram_photo(photo_path):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    try:
        with open(photo_path, 'rb') as photo:
            requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID}, files={"photo": photo})
        print("📸 Telegram (graf) odeslán.")
    except Exception as e:
        print(f"❌ Chyba Telegram Foto: {e}")

def create_chart():
    try:
        if not os.path.exists("value_history.csv"): return None
        df = pd.read_csv("value_history.csv")
        
        # 1. Filtrujeme podle vlastníka (pokud tam sloupec je)
        if 'Owner' in df.columns:
            df = df[df['Owner'] == TARGET_OWNER]
            
        if len(df) < 2: return None

        # 2. OPRAVA DATA: Použijeme format='mixed' pro různé styly zápisu
        df['Date'] = pd.to_datetime(df['Date'], format='mixed')
        
        # Seřadíme podle data, aby čára neksákala sem a tam
        df = df.sort_values(by='Date')

        plt.figure(figsize=(10, 5))
        plt.plot(df['Date'], df['TotalUSD'], marker='o', linestyle='-', color='#007acc', linewidth=2)
        plt.title(f"Vývoj hodnoty portfolia (USD) - {TARGET_OWNER}", fontsize=14)
        plt.grid(True, which='both', linestyle='--', alpha=0.5)
        plt.tight_layout()
        
        filename = "chart.png"
        plt.savefig(filename)
        plt.close()
        print("🎨 Graf vytvořen.")
        return filename
    except Exception as e:
        print(f"⚠️ Chyba při tvorbě grafu: {e}")
        return None

def get_ai_comment(portfolio_text, total_val, change_today):
    if not GEMINI_API_KEY: return "AI klíč nenalezen."
    
    personas = [
        "Jsi sarkastický robot, který si dělá legraci z lidských peněz.",
        "Jsi nadšený fotbalový komentátor, který komentuje vývoj akcií jako napínavý zápas.",
        "Jsi moudrý mistr Yoda. Mluvíš v hádankách a obracíš slovosled.",
        "Jsi pirát, který hlídá svůj poklad. Používej pirátský slang.",
        "Jsi velmi formální britský komorník."
    ]
    selected_persona = random.choice(personas)

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # Použijeme model, který máš dostupný (1.5 nebo 2.0)
        model = genai.GenerativeModel('gemini-2.5-flash') 
        prompt = (
            f"{selected_persona}\n"
            f"Zhodnoť stručně (max 3 věty) dnešní stav portfolia pro investora jménem {TARGET_OWNER}.\n"
            f"Celková hodnota: {total_val:,.0f} CZK.\n"
            f"Dnešní pohyby akcií:\n{portfolio_text}\n"
            f"Nepoužívej formátování textu."
        )
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"❌ Chyba AI: {e}")
        return "Dnes nemám slov."

def get_data_safe(ticker):
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
        print(f"   ⚠️ Chyba {ticker}: {e}")
    return 0.0, 0.0

def save_history(total_czk, usd_czk):
    try:
        total_usd = total_czk / usd_czk if usd_czk > 0 else 0
        filename = "value_history.csv"
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        if not os.path.exists(filename):
            with open(filename, "w") as f: f.write("Date,TotalUSD,Owner\n")
        
        # Zapíšeme data se správným Ownerem
        with open(filename, "a") as f:
            f.write(f"{today},{total_usd:.2f},{TARGET_OWNER}\n")
        print("💾 Historie uložena.")
    except Exception as e:
        print(f"❌ Chyba historie: {e}")

def main():
    print("🧠 ROBOT 'AI ANALYTIK' STARTUJE...")

    try:
        df = pd.read_csv("portfolio_data.csv")
        
        # --- FILTR PRO KONKRÉTNÍHO UŽIVATELE ---
        if 'Owner' in df.columns:
             df = df[df['Owner'] == TARGET_OWNER]
        
        if df.empty:
            print(f"Žádná data pro uživatele {TARGET_OWNER}.")
            return

        df['Ticker'] = df['Ticker'].astype(str).str.strip().str.upper()
        df['Pocet'] = pd.to_numeric(df['Pocet'], errors='coerce').fillna(0)
        df = df.groupby('Ticker', as_index=False)['Pocet'].sum()
    except Exception as e: 
        print(f"Chyba při načítání portfolia: {e}")
        return

    # 1. Kurzy měn
    usd_czk, _ = get_data_safe("CZK=X")
    if usd_czk == 0: usd_czk = 24.0
    eur_usd, _ = get_data_safe("EURUSD=X")
    if eur_usd == 0: eur_usd = 1.08

    # S&P 500 pro porovnání
    sp500_price, sp500_change = get_data_safe("^GSPC")
    print(f"🌎 Trh (S&P 500) změna: {sp500_change:+.2f}%")

    # 2. Akcie + Výpočty
    portfolio_items = []
    total_val_czk = 0
    weighted_sum_change = 0 
    
    ai_text_input = "" 

    print("--- Stahuji data ---")
    for index, row in df.iterrows():
        ticker = row['Ticker']
        kusy = row['Pocet']
        
        if kusy <= 0: continue # Přeskočíme prázdné pozice

        price, change = get_data_safe(ticker)
        time.sleep(0.2)
        
        if price > 0:
            val_czk = 0
            if ticker.endswith(".PR"): val_czk = price * kusy
            elif ticker.endswith(".DE"): val_czk = price * kusy * eur_usd * usd_czk
            else: val_czk = price * kusy * usd_czk
            
            total_val_czk += val_czk
            weighted_sum_change += val_czk * change
            
            portfolio_items.append({"ticker": ticker, "value_czk": val_czk, "change": change})
            print(f"✅ {ticker}: {change:+.2f}%")
            ai_text_input += f"{ticker}: {change:+.1f}%\n"

    # --- VÝPOČET: O kolik % se pohlo tvé portfolio celkem ---
    my_portfolio_change = 0.0
    if total_val_czk > 0:
        my_portfolio_change = weighted_sum_change / total_val_czk

    # 3. Uložení historie
    save_history(total_val_czk, usd_czk)
    
    # 4. AI ANALÝZA 🧠
    print("🤖 Ptám se AI na názor...")
    ai_comment = get_ai_comment(ai_text_input, total_val_czk, 0)
    print(f"💡 AI říká: {ai_comment}")
    
    # Uložení reportu lokálně (volitelné)
    try:
        with open("ai_report.md", "w") as f:
            f.write(f"### 🧠 AI Analýza ({datetime.datetime.now().strftime('%d.%m.')})\n")
            f.write(ai_comment)
    except: pass

    # 5. Telegram
    market_icon = "🟢" if sp500_change >= 0 else "🔴"
    my_icon = "🟢" if my_portfolio_change >= 0 else "🔴"
    
    diff = my_portfolio_change - sp500_change
    if diff > 0:
        battle_result = f"🏆 <b>Porazil jsi trh o {diff:.1f}%!</b>"
    else:
        battle_result = f"🐢 <b>Trh byl dnes rychlejší o {abs(diff):.1f}%.</b>"

    sorted_items = sorted(portfolio_items, key=lambda x: x['change'], reverse=True)
    
    msg = f"<b>📊 DENNÍ UPDATE ({TARGET_OWNER})</b>\n📅 {datetime.datetime.now().strftime('%d.%m.%Y')}\n"
    msg += f"----------------\n"
    msg += f"🤑 <b>CELKEM: {total_val_czk:,.0f} Kč</b>\n"
    msg += f"{my_icon} Tvůj výkon: <b>{my_portfolio_change:+.2f}%</b>\n"
    msg += f"{market_icon} S&P 500: <b>{sp500_change:+.2f}%</b>\n"
    msg += f"{battle_result}\n\n"
    msg += f"💵 Kurz USD: {usd_czk:.2f} Kč\n\n"
    
    msg += "<b>📋 Detail:</b>\n"
    for item in sorted_items:
        icon = "🟢" if item['change'] >= 0 else "🔴"
        msg += f"{icon} <b>{item['ticker']}</b>: {item['change']:+.1f}%\n"
    
    msg += f"\n💡 <b>AI Komentář:</b>\n<i>{ai_comment}</i>"

    send_telegram(msg)

    # 6. Graf
    chart_file = create_chart()
    if chart_file:
        send_telegram_photo(chart_file)
    else:
        print("⚠️ Graf zatím nelze vytvořit (asi málo dat v historii).")

if __name__ == "__main__":
    main()
