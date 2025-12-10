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
    # 1. NAČTENÍ PARAMETRŮ
    rezim = os.environ.get("INPUT_TYP", "Standardní Report")
    vzkaz_od_sefa = os.environ.get("INPUT_VZKAZ", "")

    print(f"🤖 {BOT_NAME}: Startuji v režimu '{rezim}'...")

    if rezim == "Jenom Vtip":
        vtipy = [
            "Víš, jak udělat na burze malé jmění? Začni s velkým.",
            "Dividendový investor není lakomý. Jen má rád, když mu peníze říkají 'pane'.",
            "Trh může zůstat iracionální déle, než ty solventní."
        ]
        notify.poslat_zpravu(f"🤡 <b>Burzovní vtip:</b>\n\n{random.choice(vtipy)}")
        return 

    if rezim == "Test Spojení":
        notify.poslat_zpravu("📡 <b>Test spojení:</b> Alex je online a připraven!")
        return

    # 2. NAČTENÍ DAT
    try:
        raw_df = dm.nacti_csv(dm.SOUBOR_DATA)
        raw_cash = dm.nacti_csv(dm.SOUBOR_CASH)
        
        df = raw_df[raw_df['Owner'] == TARGET_USER].copy()
        df_cash = raw_cash[raw_cash['Owner'] == TARGET_USER].copy()
        
        if df.empty and df_cash.empty:
            notify.poslat_zpravu("⚠️ <b>Alex:</b> Nemám data. Nahraj CSV na GitHub.")
            return

    except Exception as e:
        print(f"❌ Chyba dat: {e}")
        return

    # 3. PŘÍPRAVA TICKERŮ
    my_tickers = df['Ticker'].unique().tolist()
    market_tickers = ["^GSPC", "BTC-USD"]
    all_tickers = list(set(my_tickers + market_tickers))

    # 4. STAŽENÍ DAT
    kurz_czk = 24.0 
    kurz_eur = 1.05
    
    live_prices = {} 
    open_prices = {} 
    market_data = {} 
    divi_yields = {} # Ukládáme výnosy pro výpočet renty

    try:
        print(f"🌍 Stahuji data pro {len(all_tickers)} tickerů...")
        # Stáhneme data
        data_obj = yf.Tickers(" ".join(all_tickers + ["CZK=X", "EURUSD=X"]))
        
        # A) Kurzy (bezpečnější přístup přes Ticker objekt)
        try:
            h_czk = data_obj.tickers["CZK=X"].history(period="1d")
            if not h_czk.empty: kurz_czk = float(h_czk['Close'].iloc[-1])
            
            h_eur = data_obj.tickers["EURUSD=X"].history(period="1d")
            if not h_eur.empty: kurz_eur = float(h_eur['Close'].iloc[-1])
        except: pass

        # B) Ceny a Dividendy
        for t in all_tickers:
            try:
                ticker_obj = data_obj.tickers[t]
                hist = ticker_obj.history(period="1d")
                
                if hist.empty: continue
                
                price = float(hist['Close'].iloc[-1])
                open_p = float(hist['Open'].iloc[-1])
                
                live_prices[t] = price
                open_prices[t] = open_p
                
                # Získání dividendy (jen pro moje akcie)
                if t in my_tickers:
                    info = ticker_obj.info
                    # DividendYield je desetinné číslo (např. 0.05 pro 5%)
                    dy = info.get('dividendYield', 0)
                    divi_yields[t] = safe_float(dy)

                if t in market_tickers:
                    pct_change = ((price - open_p) / open_p) * 100 if open_p > 0 else 0
                    market_data[t] = pct_change
            except: pass

    except Exception as e:
        print(f"⚠️ Chyba stahování: {e}")

    # 5. VÝPOČTY
    total_cash_usd = 0
    portfolio_val_usd = 0
    portfolio_cost_usd = 0
    daily_gain_usd = 0
    
    # Novinka: Roční dividenda
    annual_divi_usd = 0
    
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
        
        curr = "USD"; koef = 1.0
        if ".PR" in t: curr = "CZK"; koef = 1.0 / kurz_czk
        elif ".DE" in t: curr = "EUR"; koef = kurz_eur
        
        row = df[df['Ticker'] == t]
        kusy = row['Pocet'].sum()
        avg_buy = row['Cena'].mean()
        
        val_usd = kusy * live_prices[t] * koef
        cost_usd = kusy * avg_buy * koef
        
        portfolio_val_usd += val_usd
        portfolio_cost_usd += cost_usd
        
        daily_diff = (live_prices[t] - open_prices[t]) * kusy * koef
        daily_gain_usd += daily_diff
        
        if open_prices[t] > 0:
            pct = ((live_prices[t] - open_prices[t]) / open_prices[t])
            movers.append((t, pct))
            
        # Výpočet dividendy: Hodnota * Yield
        yield_val = divi_yields.get(t, 0)
        if yield_val > 0:
            # Roční výnos v USD = Hodnota v USD * Procento
            annual_divi_usd += (val_usd * yield_val)

    # 6. FINÁLNÍ ČÍSLA
    total_net_worth_czk = (portfolio_val_usd + total_cash_usd) * kurz_czk
    total_profit_czk = (portfolio_val_usd - portfolio_cost_usd) * kurz_czk
    total_profit_pct = (portfolio_val_usd - portfolio_cost_usd) / portfolio_cost_usd * 100 if portfolio_cost_usd > 0 else 0
    
    # Přepočet dividendy na CZK
    annual_divi_czk = annual_divi_usd * kurz_czk
    
    my_daily_pct = 0.0
    if portfolio_val_usd > 0:
        my_daily_pct = (daily_gain_usd / (portfolio_val_usd - daily_gain_usd)) * 100

    sp500_pct = market_data.get("^GSPC", 0.0)
    btc_pct = market_data.get("BTC-USD", 0.0)

    # 7. REPORT
    emoji_main = "🟢" if total_profit_czk >= 0 else "🔴"
    emoji_daily = "📈" if my_daily_pct >= 0 else "📉"
    
    beat_market = my_daily_pct > sp500_pct
    market_msg = "🏆 <b>Porazil jsi trh!</b>" if beat_market else "🐢 <b>Trh byl dnes rychlejší.</b>"

    msg = f"<b>🎩 CEO REPORT: {datetime.now().strftime('%d.%m.')}</b>\n"
    msg += f"<i>Rentier Edition ❄️</i>\n"
    msg += "━━━━━━━━━━━━━━━━━━\n"
    
    msg += f"💰 <b>JMĚNÍ: {total_net_worth_czk:,.0f} Kč</b>\n"
    msg += f"📊 Zisk: {emoji_main} {total_profit_czk:+,.0f} Kč ({total_profit_pct:+.1f}%)\n"
    
    # --- NOVINKA: DIVIDENDY ---
    if annual_divi_czk > 10:
        msg += f"❄️ <b>Dividenda (rok): {annual_divi_czk:,.0f} Kč</b>\n"
    # --------------------------
    
    msg += f"{emoji_daily} Dnes: {my_daily_pct:+.2f}% (S&P: {sp500_pct:+.2f}%)\n"
    msg += "━━━━━━━━━━━━━━━━━━\n"
    
    msg += f"{market_msg}\n"
    if btc_pct != 0:
        msg += f"🪙 Bitcoin: {btc_pct:+.2f}%\n"
    msg += "━━━━━━━━━━━━━━━━━━\n"

    if movers:
        movers.sort(key=lambda x: x[1], reverse=True)
        b = movers[0]; w = movers[-1]
        msg += f"🚀 {b[0]} ({b[1]*100:+.1f}%)\n"
        msg += f"💀 {w[0]} ({w[1]*100:+.1f}%)\n"
    
    msg += "━━━━━━━━━━━━━━━━━━\n"
    
    msg += "💳 <b>Stav hotovosti:</b>\n"
    found_cash = False
    try:
        sums = df_cash.groupby('Mena')['Castka'].sum()
        for mena in ['CZK', 'USD', 'EUR']:
            if mena in sums and sums[mena] > 1:
                amount = sums[mena]
                if mena == 'CZK': txt = f"{amount:,.0f} Kč"
                elif mena == 'USD': txt = f"${amount:,.0f}"
                elif mena == 'EUR': txt = f"€{amount:,.0f}"
                else: txt = f"{amount:,.0f} {mena}"
                msg += f"• {txt}\n"
                found_cash = True
    except: pass
    
    if not found_cash: msg += "• <i>Prázdno</i>\n"
    msg += "━━━━━━━━━━━━━━━━━━\n"

    if vzkaz_od_sefa:
        msg += f"\n✍️ <b>Poznámka:</b> {vzkaz_od_sefa}"

    print(f"📤 Odesílám report...")
    notify.poslat_zpravu(msg)

if __name__ == "__main__":
    run_bot()
