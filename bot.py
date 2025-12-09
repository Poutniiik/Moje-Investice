import pandas as pd
import yfinance as yf
from datetime import datetime
import data_manager as dm
import notification_engine as notify
import math
import os

# --- KONFIGURACE ROBOTA ---
# ⚠️ DŮLEŽITÉ: Tady musí být PŘESNĚ to jméno, které vidíš v aplikaci vlevo nahoře
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
    print(f"🤖 {BOT_NAME}: Startuji diagnostiku pro uživatele '{TARGET_USER}'...")

    # 1. Načtení dat
    try:
        # Načteme celá data bez filtru, abychom viděli, kdo tam je
        raw_df = dm.nacti_csv(dm.SOUBOR_DATA)
        raw_cash = dm.nacti_csv(dm.SOUBOR_CASH)
        
        print(f"📊 DEBUG: V databázi je celkem {len(raw_df)} akcií a {len(raw_cash)} pohybů peněz.")
        print(f"👥 DEBUG: Nalezení uživatelé v DB: {raw_df['Owner'].unique()}")

        # Teď filtrujeme
        df = raw_df[raw_df['Owner'] == TARGET_USER].copy()
        df_cash = raw_cash[raw_cash['Owner'] == TARGET_USER].copy()
        
        print(f"✅ Pro uživatele '{TARGET_USER}' nalezeno: {len(df)} akcií, {len(df_cash)} záznamů cash.")
        
    except Exception as e:
        print(f"❌ KRITICKÁ CHYBA NAČÍTÁNÍ: {e}")
        return

    # Pokud nemáme data, nemá cenu pokračovat
    if df.empty and df_cash.empty:
        print("⚠️ VAROVÁNÍ: Žádná data pro tohoto uživatele! Kontroluji jméno...")
        notify.poslat_zpravu(f"⚠️ <b>{BOT_NAME} hlásí chybu:</b>\nNenašel jsem žádná data pro uživatele <i>{TARGET_USER}</i>.\nZkontroluj, zda máš v 'bot.py' správné jméno.")
        return

    # 2. Kurzy (S ochranou proti NaN)
    kurz_czk = 24.0 
    kurz_eur = 1.05
    
    try:
        print("🌍 Stahuji kurzy měn...")
        forex = yf.download(["CZK=X", "EURUSD=X"], period="1d", progress=False)
        if not forex.empty:
            # Zkusíme získat hodnotu a ošetřit NaN
            k_czk = forex["Close"]["CZK=X"].iloc[-1] if "CZK=X" in forex["Close"] else None
            k_eur = forex["Close"]["EURUSD=X"].iloc[-1] if "EURUSD=X" in forex["Close"] else None
            
            if k_czk and not math.isnan(k_czk): kurz_czk = float(k_czk)
            if k_eur and not math.isnan(k_eur): kurz_eur = float(k_eur)
            
        print(f"💱 Použité kurzy: USD/CZK={kurz_czk:.2f}, EUR/USD={kurz_eur:.2f}")
    except Exception as e:
        print(f"⚠️ Chyba kurzů ({e}), jedu na fallback (24.0 / 1.05).")

    # 3. Výpočet Hotovosti
    total_cash_usd = 0
    try:
        # Převedeme na čísla, kdyby tam byly stringy
        df_cash['Castka'] = pd.to_numeric(df_cash['Castka'], errors='coerce').fillna(0)
        zustatky = df_cash.groupby('Mena')['Castka'].sum().to_dict()
        
        total_cash_usd += zustatky.get('USD', 0)
        total_cash_usd += zustatky.get('CZK', 0) / kurz_czk
        total_cash_usd += zustatky.get('EUR', 0) * kurz_eur
    except Exception as e:
        print(f"❌ Chyba při počítání cash: {e}")

    # 4. Hodnota akcií
    portfolio_val_usd = 0
    movers = []
    tickers = df['Ticker'].unique().tolist()

    if tickers:
        print(f"📈 Stahuji ceny pro: {tickers}")
        try:
            live_data = yf.download(tickers, period="1d", group_by='ticker', progress=False)
            
            for t in tickers:
                try:
                    # Logika pro získání ceny (single vs multi index)
                    if len(tickers) > 1:
                        data_slice = live_data[t]
                    else:
                        data_slice = live_data
                    
                    # Ošetření prázdných dat
                    if data_slice.empty or pd.isna(data_slice['Close'].iloc[-1]):
                        print(f"⚠️ {t}: Žádná data nebo NaN.")
                        continue

                    price = float(data_slice['Close'].iloc[-1])
                    open_p = float(data_slice['Open'].iloc[-1])
                        
                    # Měna akcie (zjednodušená detekce)
                    curr = "USD"
                    if ".PR" in t: curr = "CZK"
                    elif ".DE" in t: curr = "EUR"
                    
                    kusy = df[df['Ticker'] == t]['Pocet'].sum()
                    val = kusy * price
                    
                    # Konverze
                    val_usd = val
                    if curr == "CZK": val_usd = val / kurz_czk
                    elif curr == "EUR": val_usd = val * kurz_eur
                    
                    portfolio_val_usd += val_usd
                    
                    # Změna
                    if open_p > 0:
                        change = (price - open_p) / open_p
                        movers.append((t, change))
                    
                except Exception as e:
                    print(f"⚠️ Chyba výpočtu u {t}: {e}")

        except Exception as e:
            print(f"❌ Velká chyba yfinance: {e}")

    # 5. Celkové jmění
    total_net_worth_czk = (portfolio_val_usd + total_cash_usd) * kurz_czk
    
    # 6. Top/Flop
    best_str = "N/A"
    worst_str = "N/A"
    if movers:
        movers.sort(key=lambda x: x[1], reverse=True)
        b = movers[0]
        w = movers[-1]
        best_str = f"{b[0]} ({b[1]*100:+.1f}%)"
        worst_str = f"{w[0]} ({w[1]*100:+.1f}%)"

    # 7. Sestavení zprávy
    msg = f"<b>🤖 {BOT_NAME} (v2.0):</b>\n"
    msg += f"📅 {datetime.now().strftime('%d.%m. %H:%M')}\n"
    msg += "------------------\n"
    msg += f"💰 Jmění: <b>{total_net_worth_czk:,.0f} Kč</b>\n"
    msg += f"💵 Cash: ${total_cash_usd:,.0f}\n"
    msg += "------------------\n"
    msg += f"🚀 {best_str}\n"
    msg += f"💀 {worst_str}\n"
    msg += "------------------\n"
    msg += "<i>GitHub Actions OK ✅</i>"

    print(f"📤 Odesílám: Jmění={total_net_worth_czk}, Cash={total_cash_usd}")
    notify.poslat_zpravu(msg)

if __name__ == "__main__":
    run_bot()
