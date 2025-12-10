import pandas as pd
import yfinance as yf
from datetime import datetime
import data_manager as dm
import math
import os
import random
import matplotlib.pyplot as plt
import io
import requests
import google.generativeai as genai  # 🧠 Mozek

# --- KONFIGURACE ROBOTA ---
TARGET_USER = "Filip"
BOT_NAME = "Alex"

# --- POMOCNÉ FUNKCE ---
def get_telegram_creds():
    token = os.environ.get("TG_BOT_TOKEN")
    chat_id = os.environ.get("TG_CHAT_ID")
    if not token or not chat_id: return None, None
    return token, chat_id

def poslat_zpravu_telegram(text):
    token, chat_id = get_telegram_creds()
    if not token: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try: requests.post(url, data=data)
    except Exception as e: print(f"❌ Chyba text: {e}")

def poslat_obrazek_telegram(img_buffer, caption=""):
    token, chat_id = get_telegram_creds()
    if not token: return
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    img_buffer.seek(0)
    files = {'photo': ('chart.png', img_buffer, 'image/png')}
    data = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'HTML'}
    try: requests.post(url, files=files, data=data)
    except Exception as e: print(f"❌ Chyba obrazek: {e}")

def generate_portfolio_chart(stocks, cash, total):
    if total <= 0: return None
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(aspect="equal"))
    fig.patch.set_facecolor('#161B22')
    ax.set_facecolor('#161B22')
    
    wedges, texts, autotexts = ax.pie([stocks, cash], labels=['Akcie', 'Hotovost'], autopct='%1.0f%%',
                                      startangle=90, colors=['#00CC96', '#636EFA'],
                                      textprops=dict(color="white", fontsize=12, weight='bold'),
                                      wedgeprops=dict(width=0.4, edgecolor='#161B22'), pctdistance=0.80)
    
    ax.text(0, 0, f"JMĚNÍ\n{total:,.0f} Kč", ha='center', va='center', fontsize=14, weight='bold', color='white')
    ax.set_title("Rozložení Portfolia", fontsize=16, color='white', pad=20, weight='bold')
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor='#161B22')
    buf.seek(0); plt.close(fig)
    return buf

# --- NOVINKA: FUNKCE PRO AI MOZEK 🧠 ---
def get_ai_commentary(total_val, daily_pct, sp500_pct, top_mover, flop_mover):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "<i>(AI klíč nenalezen, Alex mlčí)</i>"

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Sestavíme prompt pro AI
        prompt = (
            f"Jsi sarkastický ale profesionální burzovní robot Alex. Mluvíš k uživateli 'Šéf'. "
            f"Zde je dnešní výsledek portfolia: "
            f"Celková hodnota: {total_val:,.0f} CZK. "
            f"Dnešní změna portfolia: {daily_pct:+.2f}%. "
            f"Změna trhu S&P 500: {sp500_pct:+.2f}%. "
            f"Nejlepší akcie dne: {top_mover}. "
            f"Nejhorší akcie dne: {flop_mover}. "
            f"Úkol: Napiši velmi krátký (max 2 věty), úderný komentář k tomuto výsledku. "
            f"Pokud portfolio porazilo trh, pochval ho. Pokud prohrálo, rýpni si. Buď vtipný."
        )
        
        response = model.generate_content(prompt)
        return f"🤖 <b>AI Insight:</b> {response.text.strip()}"
    except Exception as e:
        print(f"Chyba AI: {e}")
        return ""

# --- HLAVNÍ LOGIKA ---
def safe_float(val, fallback=0.0):
    try: f = float(val); return fallback if math.isnan(f) else f
    except: return fallback

def run_bot():
    rezim = os.environ.get("INPUT_TYP", "Standardní Report")
    vzkaz_od_sefa = os.environ.get("INPUT_VZKAZ", "")
    print(f"🤖 {BOT_NAME}: Startuji v6.0 AI Edition ({rezim})...")

    if rezim == "Jenom Vtip":
        poslat_zpravu_telegram(f"🤡 <b>Vtip:</b> AI dnes stávkuje, chce dovolenou na serverech Googlu.")
        return

    # NAČTENÍ DAT
    try:
        df = dm.nacti_csv(dm.SOUBOR_DATA).query(f"Owner=='{TARGET_USER}'")
        df_cash = dm.nacti_csv(dm.SOUBOR_CASH).query(f"Owner=='{TARGET_USER}'")
        if df.empty and df_cash.empty: return
    except: return

    # TICKERY & DATA
    my_tickers = df['Ticker'].unique().tolist()
    market_tickers = ["^GSPC", "BTC-USD"]
    all_tickers = list(set(my_tickers + market_tickers))
    
    kurz_czk = 24.0; kurz_eur = 1.05
    live_prices = {}; open_prices = {}; market_data = {}; divi_yields = {}

    try:
        data_obj = yf.Tickers(" ".join(all_tickers + ["CZK=X", "EURUSD=X"]))
        try: kurz_czk = data_obj.tickers["CZK=X"].history(period="1d")['Close'].iloc[-1]
        except: pass
        
        for t in all_tickers:
            try:
                hist = data_obj.tickers[t].history(period="1d")
                if hist.empty: continue
                live_prices[t] = hist['Close'].iloc[-1]
                open_prices[t] = hist['Open'].iloc[-1]
                if t in my_tickers: divi_yields[t] = safe_float(data_obj.tickers[t].info.get('dividendYield', 0))
                if t in market_tickers: market_data[t] = ((live_prices[t] - open_prices[t])/open_prices[t])*100
            except: pass
    except: pass

    # VÝPOČTY
    total_cash_usd = 0; port_val_usd = 0; port_cost_usd = 0; daily_gain_usd = 0; annual_divi_usd = 0
    movers = []

    try:
        for m, c in df_cash.groupby('Mena')['Castka'].sum().items():
            if c > 1:
                if m == 'USD': total_cash_usd += c
                elif m == 'CZK': total_cash_usd += c/kurz_czk
                elif m == 'EUR': total_cash_usd += c*kurz_eur
    except: pass

    for t in my_tickers:
        if t not in live_prices: continue
        curr = "USD"; koef = 1.0
        if ".PR" in t: curr="CZK"; koef=1.0/kurz_czk
        elif ".DE" in t: curr="EUR"; koef=kurz_eur
        
        row = df[df['Ticker']==t]
        kusy = row['Pocet'].sum(); avg = row['Cena'].mean()
        
        val = kusy*live_prices[t]*koef
        port_val_usd += val
        port_cost_usd += kusy*avg*koef
        daily_gain_usd += (live_prices[t]-open_prices[t])*kusy*koef
        
        if open_prices[t]>0: movers.append((t, ((live_prices[t]-open_prices[t])/open_prices[t])))
        if divi_yields.get(t,0)>0: annual_divi_usd += val * divi_yields[t]

    # FINÁLNÍ METRIKY (CZK)
    net_worth = (port_val_usd + total_cash_usd) * kurz_czk
    port_czk = port_val_usd * kurz_czk
    cash_czk = total_cash_usd * kurz_czk
    profit_czk = (port_val_usd - port_cost_usd) * kurz_czk
    profit_pct = (port_val_usd - port_cost_usd)/port_cost_usd*100 if port_cost_usd>0 else 0
    divi_czk = annual_divi_usd * kurz_czk
    
    daily_pct = (daily_gain_usd/(port_val_usd-daily_gain_usd))*100 if port_val_usd>0 else 0
    sp500_pct = market_data.get("^GSPC", 0.0)
    btc_pct = market_data.get("BTC-USD", 0.0)

    # MOVERS STRINGS
    top_m = "Nikdo"
    flop_m = "Nikdo"
    if movers:
        movers.sort(key=lambda x: x[1], reverse=True)
        top_m = f"{movers[0][0]} ({movers[0][1]*100:+.1f}%)"
        flop_m = f"{movers[-1][0]} ({movers[-1][1]*100:+.1f}%)"

    # 🧠 VOLÁNÍ AI MOZKU
    ai_msg = get_ai_commentary(net_worth, daily_pct, sp500_pct, top_m, flop_m)

    # SESTAVENÍ REPORTU
    emoji_main = "🟢" if profit_czk>=0 else "🔴"
    msg = f"<b>🎩 CEO REPORT: {datetime.now().strftime('%d.%m.')}</b>\n"
    msg += f"<i>AI Ultimate Edition 🧠</i>\n"
    msg += "━━━━━━━━━━━━━━━━━━\n"
    msg += f"💰 <b>JMĚNÍ: {net_worth:,.0f} Kč</b>\n"
    msg += f"📊 Zisk: {emoji_main} {profit_czk:+,.0f} Kč ({profit_pct:+.1f}%)\n"
    if divi_czk > 10: msg += f"❄️ Dividenda: {divi_czk:,.0f} Kč/rok\n"
    msg += f"📈 Dnes: {daily_pct:+.2f}% (S&P: {sp500_pct:+.2f}%)\n"
    msg += "━━━━━━━━━━━━━━━━━━\n"
    
    # Vložení AI komentáře
    if ai_msg:
        msg += f"{ai_msg}\n"
        msg += "━━━━━━━━━━━━━━━━━━\n"

    # Zbytek reportu (Movers, Cash...)
    if movers:
        msg += f"🚀 {top_m}\n💀 {flop_m}\n"
        msg += "━━━━━━━━━━━━━━━━━━\n"

    # Cash (zkrácený výpis)
    cash_txt = []
    try:
        sums = df_cash.groupby('Mena')['Castka'].sum()
        if 'CZK' in sums: cash_txt.append(f"{sums['CZK']:,.0f} Kč")
        if 'USD' in sums: cash_txt.append(f"${sums['USD']:,.0f}")
        if 'EUR' in sums: cash_txt.append(f"€{sums['EUR']:,.0f}")
    except: pass
    if cash_txt: msg += f"💳 Cash: {' | '.join(cash_txt)}\n"

    if vzkaz_od_sefa: msg += f"\n✍️ {vzkaz_od_sefa}"

    # ODESLÁNÍ
    print("📤 Odesílám report...")
    poslat_zpravu_telegram(msg)
    
    chart = generate_portfolio_chart(port_czk, cash_czk, net_worth)
    if chart: poslat_obrazek_telegram(chart, "📊 Vizuální přehled")

if __name__ == "__main__":
    run_bot()
