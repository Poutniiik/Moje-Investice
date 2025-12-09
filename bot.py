import pandas as pd
import yfinance as yf
from datetime import datetime
import data_manager as dm
import notification_engine as notify
import math
import os
import random # Přidej pro vtipy

# --- KONFIGURACE ROBOTA ---
TARGET_USER = "Filip"  
BOT_NAME = "Alex"

def safe_float(val, fallback=0.0):
    """Pomocná funkce: Pokud je hodnota NaN nebo None, vrátí fallback."""
    try:
        f = float(val)
        if math.isnan(f): return fallback
        return f
    except:
        return fallback

def run_bot():
    # 1. NAČTENÍ PARAMETRŮ Z GITHUB MENU
    # Pokud běží automat, 'INPUT_TYP' nebude existovat, tak použijeme 'Standardní Report'
    rezim = os.environ.get("INPUT_TYP", "Standardní Report")
    vzkaz_od_sefa = os.environ.get("INPUT_VZKAZ", "")

    print(f"🤖 {BOT_NAME}: Startuji v režimu '{rezim}'...")

    if rezim == "Jenom Vtip":
        vtipy = [
            "Proč se investoři neopalují? Protože se bojí spálení (burn rate).",
            "Jaký je rozdíl mezi dluhopisem a chlapem? Dluhopis nakonec dospěje.",
            "Investování je jako mýdlo. Čím víc na to saháš, tím méně toho máš."
        ]
        notify.poslat_zpravu(f"🤡 <b>Burzovní vtip:</b>\n\n{random.choice(vtipy)}")
        return  # Konec, dál nepočítej

    if rezim == "Test Spojení":
        notify.poslat_zpravu("📡 <b>Test spojení:</b> Alex slyší a vidí! Vše OK.")
        return
    # 1. Načtení dat
    try:
        raw_df = dm.nacti_csv(dm.SOUBOR_DATA)
        raw_cash = dm.nacti_csv(dm.SOUBOR_CASH)
        
        # Filtrace uživatele
        df = raw_df[raw_df['Owner'] == TARGET_USER].copy()
        df_cash = raw_cash[raw_cash['Owner'] == TARGET_USER].copy()
        
        if df.empty and df_cash.empty:
            print("⚠️ Žádná data.")
            return

    except Exception as e:
        print(f"❌ Chyba načítání dat: {e}")
        return

    # 2. Kurzy (S ochranou proti NaN)
    kurz_czk = 24.0 
    kurz_eur = 1.05
    
    try:
        print("🌍 Stahuji kurzy měn...")
        forex = yf.download(["CZK=X", "EURUSD=X"], period="1d", progress=False)
        if not forex.empty:
            k_czk = forex["Close"]["CZK=X"].iloc[-1] if "CZK=X" in forex["Close"] else None
            k_eur = forex["Close"]["EURUSD=X"].iloc[-1] if "EURUSD=X" in forex["Close"] else None
            
            if k_czk and not math.isnan(k_czk): kurz_czk = float(k_czk)
            if k_eur and not math.isnan(k_eur): kurz_eur = float(k_eur)
            
    except Exception as e:
        print(f"⚠️ Chyba kurzů, jedu na fallback: {e}")

    # 3. Výpočet Hotovosti (Detailní rozpad)
    total_cash_usd = 0
    cash_details = {} # Slovník pro výpis po měnách
    
    try:
        df_cash['Castka'] = pd.to_numeric(df_cash['Castka'], errors='coerce').fillna(0)
        zustatky = df_cash.groupby('Mena')['Castka'].sum().to_dict()
        
        for mena, castka in zustatky.items():
            if castka > 1: # Ignorujeme drobné
                cash_details[mena] = castka
                
                # Převod na USD pro celkový součet
                if mena == 'USD': total_cash_usd += castka
                elif mena == 'CZK': total_cash_usd += castka / kurz_czk
                elif mena == 'EUR': total_cash_usd += castka * kurz_eur

    except Exception as e:
        print(f"❌ Chyba cash: {e}")

    # 4. Hodnota akcií a ZISK (Profit/Loss)
    portfolio_val_usd = 0
    portfolio_cost_usd = 0 # Kolik nás to stálo
    movers = []
    tickers = df['Ticker'].unique().tolist()

    if tickers:
        print(f"📈 Stahuji ceny pro: {tickers}")
        try:
            live_data = yf.download(tickers, period="1d", group_by='ticker', progress=False)
            
            for t in tickers:
                try:
                    # Data slice logic
                    if len(tickers) > 1: data_slice = live_data[t]
                    else: data_slice = live_data
                    
                    if data_slice.empty or pd.isna(data_slice['Close'].iloc[-1]): continue

                    price = float(data_slice['Close'].iloc[-1])
                    open_p = float(data_slice['Open'].iloc[-1])
                        
                    # Měna a konverzní poměr
                    curr = "USD"
                    koef_to_usd = 1.0
                    
                    if ".PR" in t: 
                        curr = "CZK"
                        koef_to_usd = 1.0 / kurz_czk
                    elif ".DE" in t: 
                        curr = "EUR"
                        koef_to_usd = kurz_eur
                    
                    # Data z portfolia
                    row = df[df['Ticker'] == t]
                    kusy = row['Pocet'].sum()
                    avg_buy_price = row['Cena'].mean() # Průměrná nákupka z CSV
                    
                    # 1. Aktuální hodnota
                    val_usd = kusy * price * koef_to_usd
                    portfolio_val_usd += val_usd
                    
                    # 2. Nákupní cena (Investice)
                    cost_usd = kusy * avg_buy_price * koef_to_usd
                    portfolio_cost_usd += cost_usd

                    # 3. Denní změna
                    if open_p > 0:
                        change = (price - open_p) / open_p
                        movers.append((t, change))
                    
                except Exception as e:
                    print(f"⚠️ Chyba u {t}: {e}")

        except Exception as e:
            print(f"❌ Chyba yfinance: {e}")

    # 5. Finální Finanční Matematika
    total_net_worth_czk = (portfolio_val_usd + total_cash_usd) * kurz_czk
    invested_czk = portfolio_cost_usd * kurz_czk
    profit_czk = (portfolio_val_usd - portfolio_cost_usd) * kurz_czk
    
    # Výpočet procentuálního zisku (ošetření dělení nulou)
    profit_pct = 0.0
    if portfolio_cost_usd > 0:
        profit_pct = ((portfolio_val_usd - portfolio_cost_usd) / portfolio_cost_usd) * 100

    # 6. Top/Flop formátování
    best_str = "---"
    worst_str = "---"
    if movers:
        movers.sort(key=lambda x: x[1], reverse=True)
        b = movers[0]
        w = movers[-1]
        best_str = f"🚀 <b>{b[0]}</b> ({b[1]*100:+.2f}%)"
        worst_str = f"💀 <b>{w[0]}</b> ({w[1]*100:+.2f}%)"

    # 7. Sestavení HTML zprávy (Vylepšený design)
    emoji_status = "🟢" if profit_czk >= 0 else "🔴"
    
    msg = f"<b>🎩 CEO REPORT: {datetime.now().strftime('%d.%m.')}</b>\n"
    msg += f"<i>Denní svodka od Alexe</i>\n"
    msg += "━━━━━━━━━━━━━━━━━━\n"
    
    # Sekce 1: Hlavní čísla
    msg += f"💰 <b>JMĚNÍ: {total_net_worth_czk:,.0f} Kč</b>\n"
    msg += f"📊 Zisk: {emoji_status} <b>{profit_czk:+,.0f} Kč</b> ({profit_pct:+.2f}%)\n"
    msg += "━━━━━━━━━━━━━━━━━━\n"
    
    # Sekce 2: Trh (Movers)
    msg += f"{best_str}\n"
    msg += f"{worst_str}\n"
    msg += "━━━━━━━━━━━━━━━━━━\n"
    
    # Sekce 3: Hotovost
    msg += "💳 <b>Stav hotovosti:</b>\n"
    if cash_details:
        for m, c in cash_details.items():
            msg += f"• {m}: {c:,.0f}\n"
    else:
        msg += "• <i>Žádná hotovost</i>\n"
        
    msg += "━━━━━━━━━━━━━━━━━━\n"
   msg += f"<i>Kurz USD: {kurz_czk:.2f} Kč</i>"

    # --- PŘIDÁNÍ POZNÁMKY (Pokud jsi ji napsal ručně) ---
    if vzkaz_od_sefa:
    msg += f"\n\n✍️ <b>Poznámka:</b>\n{vzkaz_od_sefa}"

    print(f"📤 Odesílám report...")
    notify.poslat_zpravu(msg)

if __name__ == "__main__":
    run_bot()
