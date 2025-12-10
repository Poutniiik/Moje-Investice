import pandas as pd
import yfinance as yf
from datetime import datetime
import data_manager as dm
import math
import os
import matplotlib.pyplot as plt
import io
import requests
import json
from github import Github
import google.generativeai as genai

# --- KONFIGURACE ---
TARGET_USER = "Filip"
BOT_NAME = "Alex"
CACHE_FILE = "market_cache.json"

# --- TELEGRAM FUNKCE ---
def get_telegram_creds():
    token = os.environ.get("TG_BOT_TOKEN")
    chat_id = os.environ.get("TG_CHAT_ID")
    return token, chat_id

def poslat_zpravu(text):
    token, chat_id = get_telegram_creds()
    if not token or not chat_id: return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"})
    except Exception as e: print(f"Chyba TG: {e}")

def poslat_obrazek(buf, caption=""):
    token, chat_id = get_telegram_creds()
    if not token or not chat_id: return
    try:
        buf.seek(0)
        url = f"https://api.telegram.org/bot{token}/sendPhoto"
        requests.post(url, data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}, files={'photo': ('chart.png', buf, 'image/png')})
    except Exception as e: print(f"Chyba TG IMG: {e}")

# --- AI FUNKCE ---
def get_ai_comment(net_worth, daily_pct, top, flop):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key: return ""
    try:
        genai.configure(api_key=api_key)
        # Jistota: verze 1.5-flash
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = (f"Jsi sarkastický burzovní robot. Portfolio: {net_worth:,.0f} CZK. "
                  f"Změna: {daily_pct:+.2f}%. Top: {top}. Flop: {flop}. "
                  f"Napiš vtipný komentář na 1 větu.")
        response = model.generate_content(prompt)
        return f"🤖 {response.text.strip()}"
    except: return ""

# --- CACHE FUNKCE (ZÁPIS NA GITHUB) ---
def save_cache(data):
    token = os.environ.get("GH_TOKEN")
    repo_name = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo_name: return
    try:
        g = Github(token)
        repo = g.get_repo(repo_name)
        content = json.dumps(data, indent=2)
        try:
            # Update existujícího
            f = repo.get_contents(CACHE_FILE)
            repo.update_file(CACHE_FILE, "🤖 Alex: Update Cache", content, f.sha)
        except:
            # Vytvoření nového
            repo.create_file(CACHE_FILE, "🤖 Alex: Init Cache", content)
        print("✅ Cache uložena.")
    except Exception as e: print(f"❌ Chyba Cache: {e}")

# --- HLAVNÍ LOOP ---
def run():
    print("🚀 Alex startuje...")
    
    # 1. Načtení portfolia
    try:
        df = dm.nacti_csv(dm.SOUBOR_DATA).query(f"Owner=='{TARGET_USER}'")
        df_cash = dm.nacti_csv(dm.SOUBOR_CASH).query(f"Owner=='{TARGET_USER}'")
    except: return # Pokud selže DB, končíme

    my_tickers = df['Ticker'].unique().tolist() if not df.empty else []
    all_tickers = list(set(my_tickers + ["^GSPC", "BTC-USD", "CZK=X", "EURUSD=X"]))
    
    # 2. Stažení dat
    print(f"📡 Stahuji data pro {len(all_tickers)} tickerů...")
    data = yf.Tickers(" ".join(all_tickers))
    
    cache = {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "prices": {}, "fundamentals": {}, "kurzy": {}}
    
    # Kurzy
    try: cache["kurzy"]["CZK"] = data.tickers["CZK=X"].history(period="1d")['Close'].iloc[-1]
    except: cache["kurzy"]["CZK"] = 24.0
    try: cache["kurzy"]["EUR"] = data.tickers["EURUSD=X"].history(period="1d")['Close'].iloc[-1]
    except: cache["kurzy"]["EUR"] = 1.05
    
    kurz_czk = cache["kurzy"]["CZK"]
    
    # Zpracování tickerů
    port_val_czk = 0
    daily_gain_czk = 0
    movers = []
    
    for t in my_tickers:
        try:
            # Ceny
            hist = data.tickers[t].history(period="1d")
            if hist.empty: continue
            price = hist['Close'].iloc[-1]
            open_p = hist['Open'].iloc[-1]
            
            # Fundamenty (pro aplikaci)
            info = data.tickers[t].info
            cache["fundamentals"][t] = {
                "sector": info.get('sector', 'Doplnit'),
                "peRatio": info.get('trailingPE', 0),
                "dividendYield": info.get('dividendYield', 0),
                "marketCap": info.get('marketCap', 0)
            }
            cache["prices"][t] = {"price": price}
            
            # Výpočet hodnoty
            row = df[df['Ticker'] == t]
            kusy = row['Pocet'].sum()
            
            # Detekce měny
            koef = 1.0
            if ".PR" in t: koef = 1.0 
            elif ".DE" in t: koef = cache["kurzy"]["CZK"] / cache["kurzy"]["EUR"] 
            else: koef = kurz_czk 
            
            val_czk = kusy * price * koef
            port_val_czk += val_czk
            
            gain = (price - open_p) / open_p
            movers.append((t, gain))
            daily_gain_czk += (price - open_p) * kusy * koef
            
        except Exception as e: print(f"Chyba {t}: {e}")

    # Uložení cache pro aplikaci
    save_cache(cache)
    
    # Dopočítání Cash
    cash_total = 0
    try:
        sums = df_cash.groupby('Mena')['Castka'].sum()
        cash_total += sums.get('CZK', 0)
        cash_total += sums.get('USD', 0) * kurz_czk
        cash_total += sums.get('EUR', 0) * (kurz_czk / 1.05) 
    except: pass
    
    total_net_worth = port_val_czk + cash_total
    day_pct = (daily_gain_czk / port_val_czk * 100) if port_val_czk > 0 else 0
    
    # Top/Flop
    movers.sort(key=lambda x: x[1], reverse=True)
    top = f"{movers[0][0]} {movers[0][1]*100:+.1f}%" if movers else "-"
    flop = f"{movers[-1][0]} {movers[-1][1]*100:+.1f}%" if movers else "-"
    
    # AI Zpráva
    ai_text = get_ai_comment(total_net_worth, day_pct, top, flop)
    
    # Odeslání Telegramu
    msg = (f"<b>🎩 Ranní Report</b>\n"
           f"💰 <b>{total_net_worth:,.0f} Kč</b>\n"
           f"📈 Dnes: {day_pct:+.2f}%\n"
           f"----------------\n"
           f"{ai_text}")
    
    poslat_zpravu(msg)
    
    # Graf
    if total_net_worth > 0:
        fig, ax = plt.subplots(figsize=(5,5))
        plt.style.use('dark_background')
        ax.pie([port_val_czk, cash_total], labels=['Akcie', 'Cash'], autopct='%1.0f%%', colors=['#00CC96', '#636EFA'])
        ax.set_title(f"JMĚNÍ: {total_net_worth:,.0f} Kč", color="white")
        buf = io.BytesIO()
        plt.savefig(buf, format='png', facecolor='#0E1117')
        poslat_obrazek(buf)

if __name__ == "__main__":
    run()
