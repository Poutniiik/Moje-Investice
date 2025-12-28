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
from github import Github, Auth  # Moderní Auth

# Nastavíme backend pro servery bez monitoru (GitHub Actions)
matplotlib.use('Agg')

# --- KONFIGURACE ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO_NAZEV = "Poutniiik/Moje-Investice"
TARGET_OWNER = 'Attis'

# --- FUNKCE PRO GITHUB (Cloud Sync) ---
def download_csv_from_github(filename):
    """Stáhne aktuální CSV data přímo z GitHubu s moderní autentizací."""
    if not GITHUB_TOKEN:
        print(f"⚠️ GITHUB_TOKEN chybí. Čtu lokální {filename}")
        return pd.read_csv(filename) if os.path.exists(filename) else None

    try:
        auth = Auth.Token(GITHUB_TOKEN)
        g = Github(auth=auth)
        repo = g.get_repo(REPO_NAZEV)
        contents = repo.get_contents(filename)
        csv_data = contents.decoded_content.decode("utf-8")
        return pd.read_csv(StringIO(csv_data))
    except Exception as e:
        print(f"❌ Chyba GitHubu u {filename}: {e}")
        return pd.read_csv(filename) if os.path.exists(filename) else None

# --- TELEGRAM FUNKCE ---
def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"})
    except Exception as e: print(f"❌ Chyba Telegram: {e}")

def send_telegram_photo(photo_path):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    try:
        with open(photo_path, 'rb') as photo:
            requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID}, files={"photo": photo})
    except Exception as e: print(f"❌ Chyba Foto: {e}")

# --- ANALYTIKA A TRH ---
def get_market_data(tickers):
    """Hromadné stažení cen (Batch) s ošetřením NaN hodnot."""
    if not tickers: return {}
    all_to_download = list(set(tickers + ["^GSPC", "CZK=X", "EURUSD=X"]))
    try:
        # Používáme 3 dny, abychom o víkendu vždy našli aspoň dva validní dny
        data = yf.download(all_to_download, period="3d", progress=False)
        if data.empty: return {}
        
        close_data = data['Close']
        res = {}
        for tkr in all_to_download:
            try:
                # Odstraníme NaN pro konkrétní ticker a vezmeme poslední dvě ceny
                valid_series = close_data[tkr].dropna()
                if len(valid_series) < 2: continue
                
                curr = float(valid_series.iloc[-1])
                prev = float(valid_series.iloc[-2])
                
                if pd.isna(curr) or pd.isna(prev) or prev == 0:
                    change = 0.0
                else:
                    change = float(((curr - prev) / prev) * 100)
                
                res[tkr] = {"price": curr, "change": change}
            except: continue
        return res
    except: return {}

def get_data_safe(ticker):
    """
    KOMPATIBILITA PRO TESTY: Tato funkce tu MUSÍ zůstat, aby fungoval 'pytest'.
    Interně využívá rychlé hromadné stahování.
    """
    res = get_market_data([ticker])
    if ticker in res:
        return res[ticker]["price"], res[ticker]["change"]
    return 0.0, 0.0

def create_chart(df_hist):
    """Vytvoří graf vývoje majetku (Cyberpunk styl)."""
    try:
        if df_hist is None or len(df_hist) < 2: return None
        df = df_hist[df_hist['Owner'] == TARGET_OWNER].copy()
        df['Date'] = pd.to_datetime(df['Date'], format='mixed')
        df = df.sort_values(by='Date')

        plt.figure(figsize=(10, 5))
        plt.style.use('dark_background')
        plt.plot(df['Date'], df['TotalUSD'], marker='o', color='#00FF99', linewidth=2)
        plt.title(f"Portfolio USD - {TARGET_OWNER}", color='white')
        plt.grid(True, alpha=0.2)
        
        path = "chart.png"
        plt.savefig(path, facecolor='#0E1117')
        plt.close()
        return path
    except: return None

def get_ai_comment(portfolio_text, total_val, perf, market_perf):
    """AI analýza s výběrem persony."""
    if not GEMINI_API_KEY: return "AI spí."
    personas = [
        "sarkastický robot, co se směje lidským penězům",
        "nadšený fotbalový komentátor",
        "moudrý mistr Yoda",
        "pirát hlídající poklad",
        "britský komorník"
    ]
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        Jsi {random.choice(personas)}. Zhodnoť stav: {total_val:,.0f} Kč. 
        Tvůj výkon: {perf:+.2f}%, trh: {market_perf:+.2f}%.
        Pohyby: {portfolio_text}. Max 2-3 věty, bez formátování.
        """
        return model.generate_content(prompt).text.strip()
    except: return "Trh promluvil."

def perform_backup(df_p, df_h):
    """Time Machine - nedělní záloha dat."""
    if datetime.datetime.now().weekday() == 6:
        backup_dir = "backups"
        if not os.path.exists(backup_dir): os.makedirs(backup_dir)
        dt = datetime.datetime.now().strftime("%Y-%m-%d")
        if df_p is not None: df_p.to_csv(f"{backup_dir}/portfolio_{dt}.csv", index=False)
        if df_h is not None: df_h.to_csv(f"{backup_dir}/history_{dt}.csv", index=False)
        print("🛡️ Záloha hotova.")

def main():
    print(f"🧠 {TARGET_OWNER} ANALYTIK STARTUJE...")
    df_p_full = download_csv_from_github("portfolio_data.csv")
    df_c = download_csv_from_github("cash_data.csv")
    if df_p_full is None: return

    df = df_p_full[df_p_full['Owner'] == TARGET_OWNER].copy()
    my_tickers = df['Ticker'].unique().tolist()
    live = get_market_data(my_tickers)

    usd_czk = live.get("CZK=X", {"price": 24.0})["price"]
    eur_usd = live.get("EURUSD=X", {"price": 1.08})["price"]
    sp500_ch = live.get("^GSPC", {"change": 0})["change"]

    # Výpočty
    total_usd = 0
    weighted_ch = 0
    p_text = ""
    items = []

    for tkr, group in df.groupby('Ticker'):
        qty = group['Pocet'].sum()
        d = live.get(tkr, {"price": 0, "change": 0})
        p, ch = d["price"], d["change"]
        
        # Ochrana proti NaN hodnotám, které by zničily výpočet (nan%)
        if pd.isna(p) or p <= 0: continue

        val_usd = (qty * p)
        if tkr.endswith(".PR"): val_usd /= usd_czk
        elif tkr.endswith(".DE"): val_usd *= eur_usd

        total_usd += val_usd
        weighted_ch += val_usd * ch
        items.append({"tkr": tkr, "ch": ch})
        p_text += f"{tkr}: {ch:+.1f}% | "

    # Hotovost
    cash_czk = 0
    if df_c is not None:
        for m in ["CZK", "USD", "EUR"]:
            amt = df_c[(df_c['Owner'] == TARGET_OWNER) & (df_c['Mena'] == m)]['Castka'].sum()
            if m == "CZK": cash_czk += amt
            elif m == "USD": cash_czk += amt * usd_czk
            elif m == "EUR": cash_czk += amt * (eur_usd * usd_czk)

    final_czk = (total_usd * usd_czk) + cash_czk
    final_perf = weighted_ch / total_usd if total_usd > 0 else 0

    # Cache pro Dashboard
    with open("market_cache.json", "w") as f:
        json.dump({"prices": live, "usd_czk": usd_czk, "eur_usd": eur_usd}, f)

    # Historie a Záloha
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    df_h = download_csv_from_github("value_history.csv")
    new_h = pd.concat([df_h, pd.DataFrame([{"Date": today, "TotalUSD": total_usd, "Owner": TARGET_OWNER}])], ignore_index=True)
    new_h.to_csv("value_history.csv", index=False)
    perform_backup(df_p_full, new_h)

    # AI a Telegram
    ai_msg = get_ai_comment(p_text, final_czk, final_perf, sp500_ch)
    msg = f"<b>📊 REPORT {TARGET_OWNER}</b>\n💰 <b>{final_czk:,.0f} Kč</b>\n"
    msg += f"📈 Výkon: {final_perf:+.2f}% (S&P500: {sp500_ch:+.2f}%)\n"
    msg += f"🤖 <i>{ai_msg}</i>\n\n<b>Pohyby:</b>\n"
    
    for it in sorted(items, key=lambda x: x['ch'], reverse=True)[:3]:
        msg += f"🟢 {it['tkr']}: {it['ch']:+.1f}%\n"
    msg += "...\n"
    for it in sorted(items, key=lambda x: x['ch'])[:2]:
        msg += f"🔴 {it['tkr']}: {it['ch']:+.1f}%\n"

    send_telegram(msg)
    chart = create_chart(new_h)
    if chart: send_telegram_photo(chart)

if __name__ == "__main__": main()
