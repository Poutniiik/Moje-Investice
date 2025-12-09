import pandas as pd
import yfinance as yf
from datetime import datetime
import data_manager as dm
import notification_engine as notify
import math
import os
import random 

# --- KONFIGURACE ROBOTA ---
TARGET_USER = "Filip"   
BOT_NAME = "Alex"

def safe_float(val, fallback=0.0):
    try:
        f = float(val)
        if math.isnan(f): return fallback
        return f
    except:
        return fallback

def run_bot():
    # 1. NAČTENÍ PARAMETRŮ Z MENU
    rezim = os.environ.get("INPUT_TYP", "Standardní Report")
    vzkaz_od_sefa = os.environ.get("INPUT_VZKAZ", "")

    print(f"🤖 {BOT_NAME}: Startuji v režimu '{rezim}'...")

    if rezim == "Jenom Vtip":
        vtipy = [
            "Víš, jak udělat na burze malé jmění? Začni s velkým.",
            "Býk vydělá, medvěd vydělá, ale prase (chamtivec) jde na porážku.",
            "Trh může zůstat iracionální déle, než ty solventní."
        ]
        notify.poslat_zpravu(f"🤡 <b>Burzovní vtip:</b>\n\n{random.choice(vtipy)}")
        return 

    if rezim == "Test Spojení":
        notify.poslat_zpravu("📡 <b>Test spojení:</b> Alex je online a připraven!")
        return

    # 2. NAČTENÍ DAT UŽIVATELE
    try:
        raw_df = dm.nacti_csv(dm.SOUBOR_DATA)
        raw_cash = dm.nacti_csv(dm.SOUBOR_CASH)
        
        df = raw_df[raw_df['Owner'] == TARGET_USER].copy()
        df_cash = raw_cash[raw_cash['Owner'] == TARGET_USER].copy()
        
        if df.empty and df_cash.empty:
            print("⚠️ Žádná data.")
            return

    except Exception as e:
        print(f"❌ Chyba načítání dat: {e}")
        return

    # 3. PŘÍPRAVA TICKERŮ (Portfolio + Benchmarky)
    my_tickers = df['Ticker'].unique().tolist()
    # Přidáme S&P 500 (^GSPC) a Bitcoin (BTC-USD) pro srovnání
    market_tickers = ["^GSPC", "BTC-USD"]
    all_tickers = list(set(my_tickers + market_tickers))

    # 4. STAŽENÍ DAT A KURZŮ
    kurz_czk = 24.0 
    kurz_eur = 1.05
    
    live_prices = {} # Cena teď
    open_prices = {} # Cena ráno (pro denní změnu)
    market_data = {} # Data pro S&P a BTC

    try:
        print(f"🌍 Stahuji data pro {len(all_tickers)} tickerů + Kurzy...")
        
        # Stáhneme vše najednou + kurzy
        download_list = all_tickers + ["CZK=X", "EURUSD=X"]
        raw_data = yf.download(download_list, period="1d", group_by='ticker', progress=False)

        # Zpracování kurzů
        if "CZK=X" in raw_data: 
            k = raw_data["CZK=X"]["Close"].iloc[-1]
            if not math.isnan(k): kurz_czk = float(k)
        if "EURUSD=X" in raw_data:
            k = raw_data["EURUSD=X"]["Close"].iloc[-1]
            if not math.isnan(k): kurz_eur = float(k)

        # Zpracování cen akcií a trhu
        for t in all_tickers:
            try:
                # Ošetření struktury yfinance (Single vs Multi index)
                if len(download_list) > 1: data = raw_data[t]
                else: data = raw_data

                if data.empty or pd.isna(data['Close'].iloc[-1]): continue
                
                price = float(data['Close'].iloc[-1])
                open_p = float(data['Open'].iloc[-1])
                
                # Uložení
                live_prices[t] = price
                open_prices[t] = open_p
                
                # Pokud je to trh, vypočítáme rovnou změnu v %
                if t in market_tickers:
                    pct_change = ((price - open_p) / open_p) * 100
                    market_data[t] = pct_change

            except: pass

    except Exception as e:
        print(f"⚠️ Chyba stahování dat: {e}")

    # 5. VÝPOČET PORTFOLIA (Majetek, Zisk celkový, Zisk denní)
    total_cash_usd = 0
    portfolio_val_usd = 0
    portfolio_cost_usd = 0
    
    daily_gain_usd = 0 # O kolik se to pohnulo dnes
    
    # A) Hotovost
    try:
        df_cash['Castka'] = pd.to_numeric(df_cash['Castka'], errors='coerce').fillna(0)
        for mena, castka in df_cash.groupby('Mena')['Castka'].sum().items():
            if castka > 1:
                if mena == 'USD': total_cash_usd += castka
                elif mena == 'CZK': total_cash_usd += castka / kurz_czk
                elif mena == 'EUR': total_cash_usd += castka * kurz_eur
    except: pass

    # B) Akcie
    movers = []
    
    for t in my_tickers:
        if t not in live_prices: continue
        
        # Měna aktiva
        curr = "USD"; koef = 1.0
        if ".PR" in t: curr = "CZK"; koef = 1.0 / kurz_czk
        elif ".DE" in t: curr = "EUR"; koef = kurz_eur
        
        row = df[df['Ticker'] == t]
        kusy = row['Pocet'].sum()
        avg_buy = row['Cena'].mean()
        
        # Hodnoty
        val_usd = kusy * live_prices[t] * koef
        cost_usd = kusy * avg_buy * koef
        
        portfolio_val_usd += val_usd
        portfolio_cost_usd += cost_usd
        
        # Denní změna tohoto aktiva ($)
        # (Cena teď - Cena ráno) * kusy * měnový kurz
        daily_diff = (live_prices[t] - open_prices[t]) * kusy * koef
        daily_gain_usd += daily_diff
        
        # Procentuální změna pro Movers
        pct = ((live_prices[t] - open_prices[t]) / open_prices[t])
        movers.append((t, pct))

    # 6. FINÁLNÍ METRIKY
    total_net_worth_czk = (portfolio_val_usd + total_cash_usd) * kurz_czk
    total_profit_czk = (portfolio_val_usd - portfolio_cost_usd) * kurz_czk
    total_profit_pct = (portfolio_val_usd - portfolio_cost_usd) / portfolio_cost_usd * 100 if portfolio_cost_usd > 0 else 0
    
    # Denní výkonnost portfolia v % (Jen akcie)
    my_daily_pct = 0.0
    if portfolio_val_usd > 0:
        my_daily_pct = (daily_gain_usd / (portfolio_val_usd - daily_gain_usd)) * 100

    # Benchmarky
    sp500_pct = market_data.get("^GSPC", 0.0)
    btc_pct = market_data.get("BTC-USD", 0.0)

    # 7. SESTAVENÍ REPORTU
    emoji_main = "🟢" if total_profit_czk >= 0 else "🔴"
    emoji_daily = "📈" if my_daily_pct >= 0 else "📉"
    
    # Porovnání s trhem
    beat_market = my_daily_pct > sp500_pct
    market_msg = "🏆 <b>Porazil jsi trh!</b>" if beat_market else "🐢 <b>Trh byl dnes rychlejší.</b>"

    msg = f"<b>🎩 CEO REPORT: {datetime.now().strftime('%d.%m.')}</b>\n"
    msg += f"<i>Souboj s trhem (Market Check)</i>\n"
    msg += "━━━━━━━━━━━━━━━━━━\n"
    
    # Hlavní čísla
    msg += f"💰 <b>JMĚNÍ: {total_net_worth_czk:,.0f} Kč</b>\n"
    msg += f"📊 Celkem: {emoji_main} {total_profit_czk:+,.0f} Kč ({total_profit_pct:+.1f}%)\n"
    msg += f"{emoji_daily} <b>Dnes: {my_daily_pct:+.2f}%</b> (S&P 500: {sp500_pct:+.2f}%)\n"
    msg += "━━━━━━━━━━━━━━━━━━\n"
    
    # Verdikt
    msg += f"{market_msg}\n"
    if btc_pct != 0:
        msg += f"🪙 Bitcoin: {btc_pct:+.2f}%\n"
    msg += "━━━━━━━━━━━━━━━━━━\n"

    # Movers
    if movers:
        movers.sort(key=lambda x: x[1], reverse=True)
        b = movers[0]; w = movers[-1]
        msg += f"🚀 {b[0]} ({b[1]*100:+.1f}%)\n"
        msg += f"💀 {w[0]} ({w[1]*100:+.1f}%)\n"
    
    msg += "━━━━━━━━━━━━━━━━━━\n"
    
    # Hotovost (kompaktnější)
    cash_str = []
    try:
        sums = df_cash.groupby('Mena')['Castka'].sum()
        if 'CZK' in sums and sums['CZK'] > 100: cash_str.append(f"{sums['CZK']:,.0f} Kč")
        if 'USD' in sums and sums['USD'] > 10: cash_str.append(f"${sums['USD']:,.0f}")
        if 'EUR' in sums and sums['EUR'] > 10: cash_str.append(f"€{sums['EUR']:,.0f}")
    except: pass
    
    if cash_str: msg += f"💳 Cash: {' | '.join(cash_str)}"

    if vzkaz_od_sefa:
        msg += f"\n\n✍️ <b>Poznámka:</b> {vzkaz_od_sefa}"

    print(f"📤 Odesílám vylepšený report...")
    notify.poslat_zpravu(msg)

if __name__ == "__main__":
    run_bot()
