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
from io import StringIO
from github import Github

# Nastavíme backend pro servery bez monitoru
matplotlib.use('Agg')

# --- KONFIGURACE ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

# --- NASTAVENÍ VLASTNÍKA ---
TARGET_OWNER = 'Attis' 
REPO_NAZEV = "Poutniiik/Moje-Investice"

# --- FUNKCE PRO GITHUB ---
def download_csv_from_github(filename):
    """Stáhne aktuální CSV data přímo z GitHubu."""
    if not GITHUB_TOKEN:
        print("⚠️ GITHUB_TOKEN chybí. Zkouším číst lokální soubor.")
        if os.path.exists(filename): return pd.read_csv(filename)
        return None

    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAZEV)
        contents = repo.get_contents(filename)
        csv_data = contents.decoded_content.decode("utf-8")
        return pd.read_csv(StringIO(csv_data))
    except Exception as e:
        print(f"❌ Chyba stahování z GitHubu ({filename}): {e}")
        if os.path.exists(filename): return pd.read_csv(filename)
        return None

# --- TELEGRAM FUNKCE ---
def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: 
        print("❌ Chybí TELEGRAM tokeny.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"})
        print("📨 Telegram odeslán.")
    except Exception as e:
        print(f"❌ Chyba Telegram: {e}")

def send_telegram_photo(photo_path):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    try:
        with open(photo_path, 'rb') as photo:
            requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID}, files={"photo": photo})
        print("📸 Graf odeslán.")
    except Exception as e:
        print(f"❌ Chyba Telegram Foto: {e}")

# --- AI KOMENTÁŘ ---
def get_ai_comment(portfolio_text, total_val):
    if not GEMINI_API_KEY: return "AI klíč nenalezen."
    
    personas = [
        "Jsi sarkastický robot.", "Jsi nadšený fotbalový komentátor.", 
        "Jsi mistr Yoda.", "Jsi pirát.", "Jsi britský komorník."
    ]
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash') 
        prompt = (
            f"{random.choice(personas)}\n"
            f"Zhodnoť stručně (max 3 věty) dnešní stav portfolia pro investora {TARGET_OWNER}.\n"
            f"Celková hodnota: {total_val:,.0f} CZK.\n"
            f"Vývoj akcií:\n{portfolio_text}\n"
            f"Nepoužívej formátování textu."
        )
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"AI mlčí ({e})."

# --- TURBO STAHOVÁNÍ DAT (BATCH) 🚀 ---
def get_batch_data(tickers):
    """Stáhne data pro všechny tickery najednou."""
    print(f"🚀 Stahuji data pro {len(tickers)} tickerů...")
    data = {}
    
    # Přidáme měny a indexy, pokud tam nejsou
    all_tickers = list(set(tickers + ["CZK=X", "EURUSD=X", "^GSPC"]))
    
    try:
        # Hromadné stažení (To je to zrychlení!)
        batch = yf.download(all_tickers, period="2d", group_by='ticker', progress=False)
        
        for t in all_tickers:
            price = 0.0
            change = 0.0
            try:
                # Zkusíme vytáhnout data z batche
                if len(all_tickers) > 1:
                    if t in batch.columns.levels[0]:
                        hist = batch[t]['Close'].dropna()
                else:
                    hist = batch['Close'].dropna()

                if not hist.empty:
                    price = float(hist.iloc[-1])
                    if len(hist) >= 2:
                        prev = float(hist.iloc[-2])
                        change = ((price - prev) / prev) * 100
            except: pass
            
            # Fallback
            if price == 0:
                try:
                    t_obj = yf.Ticker(t)
                    price = float(t_obj.fast_info.last_price)
                    change = 0.0
                except: pass
            
            if price > 0:
                data[t] = {"price": price, "change": change}
                
    except Exception as e:
        print(f"⚠️ Chyba batch download: {e}")
        
    return data

# --- VÝPOČET A HISTORIE ---
def save_history_local(total_usd):
    """Uloží historii lokálně pro graf."""
    filename = "value_history.csv"
    df_hist = download_csv_from_github(filename)
    if df_hist is None: df_hist = pd.DataFrame(columns=["Date", "TotalUSD", "Owner"])
    
    new_row = pd.DataFrame([{"Date": datetime.datetime.now().strftime("%Y-%m-%d"), "TotalUSD": total_usd, "Owner": TARGET_OWNER}])
    df_hist = pd.concat([df_hist, new_row], ignore_index=True)
    df_hist.to_csv(filename, index=False)
    return df_hist

def create_chart(df_hist):
    try:
        if df_hist is None or df_hist.empty: return None
        df = df_hist[df_hist['Owner'] == TARGET_OWNER].copy()
        if len(df) < 2: return None
        
        df['Date'] = pd.to_datetime(df['Date'], format='mixed')
        df = df.sort_values('Date')

        plt.figure(figsize=(10, 5))
        plt.style.use('dark_background')
        plt.plot(df['Date'], df['TotalUSD'], color='#00FF99', linewidth=2)
        plt.title(f"Vývoj portfolia (USD)", color='white')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig("chart.png", facecolor='#0E1117')
        plt.close()
        return "chart.png"
    except: return None

# --- CACHE WARMER ---
def save_market_cache(market_data):
    """Uloží JSON pro rychlý start webu."""
    cache = {
        "timestamp": time.time(),
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "usd_czk": market_data.get("CZK=X", {}).get("price", 24.0),
        "eur_usd": market_data.get("EURUSD=X", {}).get("price", 1.08),
        "prices": market_data
    }
    with open("market_cache.json", "w") as f:
        json.dump(cache, f)
    print("💾 Cache uložena.")

# --- ZÁLOHOVÁNÍ (TIME MACHINE) ---
def perform_backup(df_p, df_h):
    if datetime.datetime.now().weekday() == 6: # Neděle
        if not os.path.exists("backups"): os.makedirs("backups")
        d = datetime.datetime.now().strftime("%Y-%m-%d")
        if df_p is not None: df_p.to_csv(f"backups/portfolio_{d}.csv", index=False)
        if df_h is not None: df_h.to_csv(f"backups/history_{d}.csv", index=False)
        print("📦 Záloha vytvořena.")

# --- MAIN ---
def main():
    print("🚀 TURBO BOT STARTUJE...")
    
    # 1. Načtení portfolia
    df = download_csv_from_github("portfolio_data.csv")
    if df is None or df.empty: return
    
    # Filtrování
    my_df = df[df['Owner'] == TARGET_OWNER].copy()
    if my_df.empty: return
    
    # Seznam tickerů
    my_df['Ticker'] = my_df['Ticker'].str.strip().str.upper()
    tickers = my_df['Ticker'].unique().tolist()
    
    # 2. STAHUJEME DATA (VŠE NARÁZ)
    market_data = get_batch_data(tickers)
    
    # 3. Výpočty
    total_czk = 0
    total_usd = 0
    port_text = ""
    
    usd_czk = market_data.get("CZK=X", {}).get("price", 24.0)
    eur_usd = market_data.get("EURUSD=X", {}).get("price", 1.08)
    sp500_change = market_data.get("^GSPC", {}).get("change", 0.0)
    
    # Agregace portfolia
    grouped = my_df.groupby('Ticker')['Pocet'].sum()
    
    weighted_change = 0
    portfolio_items = [] # Seznam pro detailní výpis
    
    for t, kusy in grouped.items():
        if kusy <= 0: continue
        info = market_data.get(t, {"price": 0, "change": 0})
        p = info['price']
        ch = info['change']
        
        if p > 0:
            val_usd = 0
            val_czk = 0
            
            # Měny
            if t.endswith(".PR"): # CZK
                val_czk = p * kusy
                val_usd = val_czk / usd_czk
            elif t.endswith(".DE"): # EUR
                val_usd = p * kusy * eur_usd
                val_czk = val_usd * usd_czk
            else: # USD
                val_usd = p * kusy
                val_czk = val_usd * usd_czk
                
            total_czk += val_czk
            total_usd += val_usd
            weighted_change += val_czk * ch
            
            port_text += f"{t}: {ch:+.1f}%\n"
            portfolio_items.append({"ticker": t, "change": ch})

    # Uložení cache pro web
    save_market_cache(market_data)
    
    # Výpočet výkonu
    my_perf = (weighted_change / total_czk) if total_czk > 0 else 0
    
    # 4. Uložení historie & Záloha
    df_hist_new = save_history_local(total_usd)
    perform_backup(df, df_hist_new)
    
    # 5. Report - SESTAVENÍ ZPRÁVY (OPRAVENO!)
    ai_msg = get_ai_comment(port_text, total_czk)
    
    # Souboj s trhem
    diff = my_perf - sp500_change
    if diff > 0:
        battle_result = f"🏆 <b>Porazil jsi trh o {diff:.1f}%!</b>"
    else:
        battle_result = f"🐢 <b>Trh byl dnes rychlejší o {abs(diff):.1f}%.</b>"

    icon = "🟢" if my_perf >= 0 else "🔴"
    
    # --- Zde skládáme zprávu postupně ---
    msg = f"<b>📊 DENNÍ UPDATE ({TARGET_OWNER})</b>\n"
    msg += f"📅 {datetime.datetime.now().strftime('%d.%m.')}\n"
    msg += f"----------------\n"
    msg += f"💰 <b>{total_czk:,.0f} Kč</b>\n"
    msg += f"{icon} Tvůj výkon: <b>{my_perf:+.2f}%</b>\n"
    msg += f"🌎 S&P 500: <b>{sp500_change:+.2f}%</b>\n"
    msg += f"{battle_result}\n\n"
    msg += f"💵 Kurz USD: {usd_czk:.2f} Kč\n\n"
    
    # Přidání detailů (TOP/FLOP)
    sorted_items = sorted(portfolio_items, key=lambda x: x['change'], reverse=True)
    msg += "<b>📋 Detail:</b>\n"
    
    if len(sorted_items) > 8:
        for item in sorted_items[:3]:
            msg += f"🟢 <b>{item['ticker']}</b>: {item['change']:+.1f}%\n"
        msg += "...\n"
        for item in sorted_items[-3:]:
            msg += f"🔴 <b>{item['ticker']}</b>: {item['change']:+.1f}%\n"
    else:
        for item in sorted_items:
            ic = "🟢" if item['change'] >= 0 else "🔴"
            msg += f"{ic} <b>{item['ticker']}</b>: {item['change']:+.1f}%\n"
            
    msg += f"\n💡 <b>AI Komentář:</b>\n<i>{ai_msg}</i>"
    
    # Odeslání AŽ TEĎ, když je zpráva kompletní
    send_telegram(msg)
    
    img = create_chart(df_hist_new)
    if img: send_telegram_photo(img)

if __name__ == "__main__":
    main()
