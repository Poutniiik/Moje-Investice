import pandas as pd
import yfinance as yf
from datetime import datetime
import data_manager as dm
import notification_engine as notify
import os

# --- KONFIGURACE ROBOTA ---
# Jméno uživatele, pro kterého report generujeme (musí sedět s tvým loginem)
TARGET_USER = "Beith"  # <--- ZDE SI ZMĚŇ SVÉ UŽIVATELSKÉ JMÉNO, POKUD JE JINÉ

def run_bot():
    print(f"🤖 ROBOT: Startuji denní report pro uživatele '{TARGET_USER}'...")

    # 1. Načtení dat z GitHubu
    try:
        df = dm.nacti_csv(dm.SOUBOR_DATA).query(f"Owner=='{TARGET_USER}'")
        df_cash = dm.nacti_csv(dm.SOUBOR_CASH).query(f"Owner=='{TARGET_USER}'")
        print("✅ Data načtena.")
    except Exception as e:
        print(f"❌ Chyba načítání dat: {e}")
        return

    # 2. Výpočet Hotovosti
    # Zjednodušený výpočet hotovosti (bez kurzů, vše v nominálu, nebo fixní kurz pro odhad)
    # Pro jednoduchost robota budeme předpokládat fixní kurzy, pokud nemáme live feed
    kurz_czk = 24.0 # Fallback
    kurz_eur = 1.05 # Fallback
    
    # Zkusíme stáhnout aktuální kurzy
    try:
        forex = yf.download(["CZK=X", "EURUSD=X"], period="1d", progress=False)
        if not forex.empty:
            kurz_czk = float(forex["Close"]["CZK=X"].iloc[-1])
            kurz_eur = float(forex["Close"]["EURUSD=X"].iloc[-1])
            print(f"💱 Kurzy staženy: USD/CZK={kurz_czk:.2f}, EUR/USD={kurz_eur:.2f}")
    except:
        print("⚠️ Nepodařilo se stáhnout kurzy, používám fallback.")

    # Hotovost total v USD
    total_cash_usd = 0
    zustatky = df_cash.groupby('Mena')['Castka'].sum().to_dict()
    total_cash_usd += zustatky.get('USD', 0)
    total_cash_usd += zustatky.get('CZK', 0) / kurz_czk
    total_cash_usd += zustatky.get('EUR', 0) * kurz_eur

    # 3. Hodnota akcií
    portfolio_val_usd = 0
    tickers = df['Ticker'].unique().tolist()
    movers = []

    if tickers:
        print(f"📈 Stahuji ceny pro {len(tickers)} akcií...")
        try:
            live_data = yf.download(tickers, period="1d", group_by='ticker', progress=False)
            
            for t in tickers:
                try:
                    # Bezpečné získání ceny z MultiIndexu
                    if len(tickers) > 1:
                        price = float(live_data[t]['Close'].iloc[-1])
                        open_p = float(live_data[t]['Open'].iloc[-1])
                    else:
                        price = float(live_data['Close'].iloc[-1])
                        open_p = float(live_data['Open'].iloc[-1])
                        
                    # Přepočet měny
                    curr = "USD"
                    if ".PR" in t: curr = "CZK"
                    elif ".DE" in t: curr = "EUR"
                    
                    kusy = df[df['Ticker'] == t]['Pocet'].sum()
                    val = kusy * price
                    
                    # Konverze na USD pro součet
                    if curr == "CZK": val_usd = val / kurz_czk
                    elif curr == "EUR": val_usd = val * kurz_eur
                    else: val_usd = val
                    
                    portfolio_val_usd += val_usd
                    
                    # Změna v %
                    change = (price - open_p) / open_p
                    movers.append((t, change))
                    
                except Exception as e:
                    print(f"Chyba u {t}: {e}")
        except Exception as e:
            print(f"❌ Chyba yfinance: {e}")

    # 4. Celkové jmění
    total_net_worth_czk = (portfolio_val_usd + total_cash_usd) * kurz_czk
    
    # 5. Top Movers
    movers.sort(key=lambda x: x[1], reverse=True)
    best = movers[0] if movers else ("N/A", 0)
    worst = movers[-1] if movers else ("N/A", 0)

    # 6. Sestavení zprávy
    msg = f"<b>🤖 AUTOMATICKÝ REPORT</b>\n"
    msg += f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
    msg += "-----------------------------\n"
    msg += f"💰 Jmění: <b>{total_net_worth_czk:,.0f} Kč</b>\n"
    msg += f"💵 Cash: ${total_cash_usd:,.0f}\n"
    msg += "-----------------------------\n"
    msg += f"🚀 Top: {best[0]} ({best[1]*100:+.1f}%)\n"
    msg += f"💀 Flop: {worst[0]} ({worst[1]*100:+.1f}%)\n"
    msg += "-----------------------------\n"
    msg += "<i>Odesláno z GitHub Actions</i>"

    # 7. Odeslání
    print("📤 Odesílám na Telegram...")
    ok, err = notify.poslat_zpravu(msg)
    if ok:
        print("✅ HOTOVO.")
    else:
        print(f"❌ CHYBA ODESLÁNÍ: {err}")

if __name__ == "__main__":
    # Fallback pro manuální spuštění bez ENV
    # if "TG_BOT_TOKEN" not in os.environ:
    #     os.environ["TG_BOT_TOKEN"] = "TVUJ_TOKEN_ZDE"
    #     os.environ["TG_CHAT_ID"] = "TVUJ_CHAT_ID_ZDE"
    #     os.environ["GH_TOKEN"] = "TVUJ_GITHUB_TOKEN_ZDE"
    
    run_bot()
