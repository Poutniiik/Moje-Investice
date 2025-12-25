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
from github import Github  # Přidáno pro cloudovou synchronizaci

# Nastavíme backend pro servery bez monitoru
matplotlib.use('Agg')

# --- KONFIGURACE A TAJEMSTVÍ ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN") # Nové: Pro stahování dat z repozitáře

# --- NASTAVENÍ VLASTNÍKA ---
TARGET_OWNER = 'Attis' 
REPO_NAZEV = "Poutniiik/Moje-Investice" # Zde doplň svůj přesný název repozitáře!

# --- FUNKCE PRO GITHUB (Cloud Sync) ---
def download_csv_from_github(filename):
    """
    Stáhne aktuální CSV data přímo z GitHubu.
    To zajistí, že bot má vždy čerstvá data, i když běží v cloudu.
    """
    if not GITHUB_TOKEN:
        print("⚠️ GITHUB_TOKEN chybí. Zkouším číst lokální soubor.")
        if os.path.exists(filename):
            return pd.read_csv(filename)
        else:
            return None

    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAZEV)
        contents = repo.get_contents(filename)
        csv_data = contents.decoded_content.decode("utf-8")
        return pd.read_csv(StringIO(csv_data))
    except Exception as e:
        print(f"❌ Chyba stahování z GitHubu ({filename}): {e}")
        # Fallback na lokální soubor
        if os.path.exists(filename):
            print("🔄 Používám lokální zálohu.")
            return pd.read_csv(filename)
        return None

# --- TELEGRAM FUNKCE ---
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

def create_chart(df_hist):
    """Vytvoří graf z historie (DataFrame)."""
    try:
        if df_hist is None or df_hist.empty: return None
        
        # Filtrujeme podle vlastníka
        if 'Owner' in df_hist.columns:
            df = df_hist[df_hist['Owner'] == TARGET_OWNER].copy()
        else:
            df = df_hist.copy()
            
        if len(df) < 2: return None

        # Formátování data
        df['Date'] = pd.to_datetime(df['Date'], format='mixed')
        df = df.sort_values(by='Date')

        plt.figure(figsize=(10, 5))
        # Stylování grafu do tmava (Cyberpunk light)
        plt.style.use('dark_background')
        plt.plot(df['Date'], df['TotalUSD'], marker='o', linestyle='-', color='#00FF99', linewidth=2)
        plt.title(f"Vývoj hodnoty portfolia (USD) - {TARGET_OWNER}", fontsize=14, color='white')
        plt.grid(True, which='both', linestyle='--', alpha=0.3)
        plt.tight_layout()
        
        filename = "chart.png"
        plt.savefig(filename, facecolor='#0E1117')
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
        # Fast info je rychlejší a méně náchylné na limity
        price = t.fast_info.last_price
        prev_close = t.fast_info.previous_close
        
        if price and prev_close:
            change = ((price - prev_close) / prev_close) * 100
            return float(price), float(change)
            
    except Exception as e:
        print(f"   ⚠️ Chyba {ticker}: {e}")
        # Fallback na historii (pomalejší)
        try:
            hist = t.history(period="2d")
            if len(hist) >= 1:
                price = float(hist['Close'].iloc[-1])
                change = 0.0
                if len(hist) >= 2:
                    prev = float(hist['Close'].iloc[-2])
                    change = ((price - prev) / prev) * 100
                return price, change
        except: pass
        
    return 0.0, 0.0

def save_history(total_usd):
    """
    Uloží historii. Pokud je GITHUB_TOKEN, měl by ideálně commitnout zpět,
    ale pro jednoduchost zatím ukládáme lokálně (pro graf v tomto běhu).
    """
    try:
        filename = "value_history.csv"
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # Načteme existující (z GitHubu nebo lokálně)
        df_hist = download_csv_from_github(filename)
        
        if df_hist is None:
            df_hist = pd.DataFrame(columns=["Date", "TotalUSD", "Owner"])
            
        # Přidáme nový řádek
        new_row = pd.DataFrame([{"Date": today, "TotalUSD": total_usd, "Owner": TARGET_OWNER}])
        df_hist = pd.concat([df_hist, new_row], ignore_index=True)
        
        # Lokální uložení pro tento běh (aby z toho šel udělat graf)
        df_hist.to_csv(filename, index=False)
        print("💾 Historie aktualizována (lokálně).")
        return df_hist
    except Exception as e:
        print(f"❌ Chyba historie: {e}")
        return None

# --- NOVINKA: CACHE WARMER 🚀 ---
def save_market_cache(prices_dict, usd_czk, eur_usd):
    """
    Uloží stažené ceny do JSON souboru, který pak využije hlavní aplikace pro bleskový start.
    """
    cache_data = {
        "timestamp": time.time(),
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "usd_czk": usd_czk,
        "eur_usd": eur_usd,
        "prices": prices_dict # Slovník {Ticker: {price: 100, change: 1.5}}
    }
    
    try:
        with open("market_cache.json", "w") as f:
            json.dump(cache_data, f)
        print("🚀 Market Cache uložena (Turbo mode enabled).")
    except Exception as e:
        print(f"⚠️ Chyba ukládání cache: {e}")

def main():
    print("🧠 ROBOT 'AI ANALYTIK' STARTUJE...")

    # 1. Načtení portfolia (z GitHubu nebo lokálně)
    df = download_csv_from_github("portfolio_data.csv")
    
    if df is None or df.empty:
        print(f"❌ Kritická chyba: Nelze načíst portfolio data.")
        return

    # Filtr vlastníka
    if 'Owner' in df.columns:
         df = df[df['Owner'] == TARGET_OWNER]
    
    if df.empty:
        print(f"Žádná data pro uživatele {TARGET_OWNER}.")
        return

    # Seskupení
    df['Ticker'] = df['Ticker'].astype(str).str.strip().str.upper()
    df['Pocet'] = pd.to_numeric(df['Pocet'], errors='coerce').fillna(0)
    df = df.groupby('Ticker', as_index=False)['Pocet'].sum()

    # 2. Kurzy měn
    usd_czk, _ = get_data_safe("CZK=X")
    if usd_czk == 0: usd_czk = 24.0 # Fallback
    eur_usd, _ = get_data_safe("EURUSD=X")
    if eur_usd == 0: eur_usd = 1.08 # Fallback

    # S&P 500
    sp500_price, sp500_change = get_data_safe("^GSPC")
    print(f"🌎 Trh (S&P 500) změna: {sp500_change:+.2f}%")

    # 3. Akcie + Výpočty + Cache Building
    portfolio_items = []
    prices_cache = {} # Data pro JSON
    
    total_val_czk = 0
    weighted_sum_change = 0 
    total_val_usd = 0 # Pro historii
    
    ai_text_input = "" 

    print("--- Stahuji data ---")
    for index, row in df.iterrows():
        ticker = row['Ticker']
        kusy = row['Pocet']
        
        if kusy <= 0: continue

        price, change = get_data_safe(ticker)
        # time.sleep(0.1) # Malé zpoždění není nutné u fast_info, ale ok pro jistotu
        
        if price > 0:
            # Uložení do cache
            prices_cache[ticker] = {"price": price, "change": change}
            
            # Konverze měn
            val_czk = 0
            val_usd = 0
            
            if ticker.endswith(".PR"): 
                val_czk = price * kusy
                val_usd = val_czk / usd_czk
            elif ticker.endswith(".DE"): 
                val_czk = price * kusy * eur_usd * usd_czk
                val_usd = price * kusy * eur_usd
            else: 
                val_czk = price * kusy * usd_czk
                val_usd = price * kusy
            
            total_val_czk += val_czk
            total_val_usd += val_usd
            weighted_sum_change += val_czk * change
            
            portfolio_items.append({"ticker": ticker, "value_czk": val_czk, "change": change})
            print(f"✅ {ticker}: {change:+.2f}%")
            ai_text_input += f"{ticker}: {change:+.1f}%\n"

    # --- ULOŽENÍ TURBO CACHE ---
    save_market_cache(prices_cache, usd_czk, eur_usd)

    # --- VÝPOČET VÝKONU ---
    my_portfolio_change = 0.0
    if total_val_czk > 0:
        my_portfolio_change = weighted_sum_change / total_val_czk

    # 4. Historie
    df_hist_new = save_history(total_val_usd)
    
    # 5. AI ANALÝZA
    print("🤖 Ptám se AI na názor...")
    ai_comment = get_ai_comment(ai_text_input, total_val_czk, 0)
    print(f"💡 AI říká: {ai_comment}")
    
    # 6. Telegram
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
    # Zobrazíme top 3 a flop 3, abychom nespamovali, pokud je toho hodně
    if len(sorted_items) > 8:
        for item in sorted_items[:3]:
            msg += f"🟢 <b>{item['ticker']}</b>: {item['change']:+.1f}%\n"
        msg += "...\n"
        for item in sorted_items[-3:]:
            msg += f"🔴 <b>{item['ticker']}</b>: {item['change']:+.1f}%\n"
    else:
        for item in sorted_items:
            icon = "🟢" if item['change'] >= 0 else "🔴"
            msg += f"{icon} <b>{item['ticker']}</b>: {item['change']:+.1f}%\n"
    
    msg += f"\n💡 <b>AI Komentář:</b>\n<i>{ai_comment}</i>"

    send_telegram(msg)

    # 7. Graf
    chart_file = create_chart(df_hist_new)
    if chart_file:
        send_telegram_photo(chart_file)
    else:
        print("⚠️ Graf nelze vytvořit.")

if __name__ == "__main__":
    main()
