import pandas as pd
import yfinance as yf
import requests
import os
import datetime
import time
import json
import google.generativeai as genai  # <--- NOVINKA: Mozek AI

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") # Robot čeká jméno GEMINI_API_KEY

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"})
        print("📨 Telegram odeslán.")
    except Exception as e:
        print(f"❌ Chyba Telegram: {e}")

def get_ai_comment(portfolio_text, total_val, change_today):
    """Zeptá se Gemini na názor."""
    if not GEMINI_API_KEY:
        print("⚠️ Nemám AI klíč, přeskakuji analýzu.")
        return "AI klíč nenalezen."
    
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash') # Rychlý model
        
        prompt = (
            f"Jsi zkušený investiční analytik. Zhodnoť stručně (max 3 věty) dnešní stav portfolia.\n"
            f"Celková hodnota: {total_val:,.0f} CZK.\n"
            f"Dnešní pohyby akcií:\n{portfolio_text}\n"
            f"Napiš to vtipně nebo povzbudivě pro investora jménem Attis. "
            f"Nepoužívej formátování jako tučné písmo, jen čistý text."
        )
        
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"❌ Chyba AI: {e}")
        return "Dnes jsem bez nálady (chyba spojení)."

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
        
        with open(filename, "a") as f:
            f.write(f"{today},{total_usd:.2f},Attis\n")
        print("💾 Historie uložena.")
    except Exception as e:
        print(f"❌ Chyba historie: {e}")

def main():
    print("🧠 ROBOT 'AI ANALYTIK' STARTUJE...")

    try:
        df = pd.read_csv("portfolio_data.csv")
        df['Ticker'] = df['Ticker'].astype(str).str.strip().str.upper()
        df['Pocet'] = pd.to_numeric(df['Pocet'], errors='coerce').fillna(0)
        df = df.groupby('Ticker', as_index=False)['Pocet'].sum()
    except Exception: return

    if df.empty: return

    # 1. Kurzy
    usd_czk, _ = get_data_safe("CZK=X")
    if usd_czk == 0: usd_czk = 24.0
    eur_usd, _ = get_data_safe("EURUSD=X")
    if eur_usd == 0: eur_usd = 1.08

    # 2. Akcie + Cache
    portfolio_items = []
    total_val_czk = 0
    cache_data = {"updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "usd_czk": usd_czk, "eur_usd": eur_usd, "prices": {}}
    
    ai_text_input = "" # Text pro AI

    print("--- Stahuji data ---")
    for index, row in df.iterrows():
        ticker = row['Ticker']
        kusy = row['Pocet']
        price, change = get_data_safe(ticker)
        time.sleep(0.2)
        
        cache_data["prices"][ticker] = {"price": price, "change": change}

        if price > 0:
            val_czk = 0
            if ticker.endswith(".PR"): val_czk = price * kusy
            elif ticker.endswith(".DE"): val_czk = price * kusy * eur_usd * usd_czk
            else: val_czk = price * kusy * usd_czk
            
            total_val_czk += val_czk
            portfolio_items.append({"ticker": ticker, "value_czk": val_czk, "change": change})
            print(f"✅ {ticker}: {change:+.2f}%")
            
            # Přidáme do textu pro AI
            ai_text_input += f"{ticker}: {change:+.1f}%\n"

    # 3. Uložení Cache
    try:
        with open("market_cache.json", "w") as f: json.dump(cache_data, f)
    except: pass

    # 4. Historie
    save_history(total_val_czk, usd_czk)
    
    # 5. AI ANALÝZA 🧠
    print("🤖 Ptám se AI na názor...")
    ai_comment = get_ai_comment(ai_text_input, total_val_czk, 0)
    print(f"💡 AI říká: {ai_comment}")
    
    # Uložíme AI názor do souboru pro Aplikaci
    with open("ai_report.md", "w") as f:
        f.write(f"### 🧠 AI Analýza ({datetime.datetime.now().strftime('%d.%m.')})\n")
        f.write(ai_comment)

    # 6. Telegram
    sorted_items = sorted(portfolio_items, key=lambda x: x['change'], reverse=True)
    msg = f"<b>📊 DENNÍ UPDATE</b>\n📅 {datetime.datetime.now().strftime('%d.%m.%Y')}\n----------------\n🤑 <b>CELKEM: {total_val_czk:,.0f} Kč</b>\n💵 Kurz USD: {usd_czk:.2f} Kč\n\n"
    
    msg += "<b>📋 Detail:</b>\n"
    for item in sorted_items:
        icon = "🟢" if item['change'] >= 0 else "🔴"
        msg += f"{icon} <b>{item['ticker']}</b>: {item['change']:+.1f}%\n"
    
    # Přidáme AI komentář i do Telegramu
    msg += f"\n💡 <b>AI Komentář:</b>\n<i>{ai_comment}</i>"

    send_telegram(msg)

if __name__ == "__main__":
    main()
