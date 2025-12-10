# =======================================================
# SOUBOR: report_bot.py (Standalone script)
# Měl by být spuštěn mimo Streamlit (Cron, AWS Lambda, atd.)
# =======================================================
import sys
import os
from datetime import datetime
import pandas as pd
# Importujeme moduly, na kterých Terminal Pro závisí:
# Ujisti se, že adresář se soubory 'data_manager.py' atd. je v PYTHONPATH.
from data_manager import SOUBOR_CASH, nacti_csv
from utils import ziskej_fear_greed
import notification_engine as notify 

# --- KONFIGURACE PRO STANDALONE SKRIPT (UPRAV DLE POTŘEBY) ---
# V reálném nasazení se tokeny musí načíst z prostředí (os.environ.get)
# Zde PŘEDPOKLÁDÁME, že tvé moduly (data_manager/notify) si klíče najdou!
USER_TO_REPORT = "Filip" # Zadej jméno uživatele, pro kterého report generuješ
CZK_USD_RATE = 22.0 # Pro jednoduchý přepočet hotovosti (cca)
# -----------------------------------------------------------

def vytvor_a_odesli_denni_report():
    
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Spouštím denní report...")
    
    # 1. SBĚR DAT (GitHub a YFinance)
    try:
        # Musí se načíst, protože data_manager automaticky nevidí Streamlit session state
        df_cash = nacti_csv(SOUBOR_CASH)
        
        # Získání živých dat (Fear/Greed)
        score, rating = ziskej_fear_greed()
        
        # 2. KALKULACE (Hotovost)
        user_cash = df_cash[df_cash['Owner'] == USER_TO_REPORT]
        
        # Zjednodušená kalkulace: Zkusíme součet CZK + USD * kurz
        cash_czk = user_cash[user_cash['Mena'] == 'CZK']['Castka'].sum()
        cash_usd_to_czk = user_cash[user_cash['Mena'] == 'USD']['Castka'].sum() * CZK_USD_RATE
        total_cash_czk = cash_czk + cash_usd_to_czk
        
        # V reálné situaci by zde následovala složitá kalkulace portfolia
        
    except Exception as e:
        # Pokud selže GitHub nebo YFinance, pošleme jen chybovou zprávu
        error_msg = f"❌ CHYBA AUTOREPORTU:\nSelhalo stažení dat: {e}"
        print(error_msg)
        # Zkusíme poslat chybu, i když by mohla selhat notifikace
        notify.poslat_zpravu(error_msg) 
        return False

    # 3. TVORBA ZPRÁVY (HTML pro Telegram)
    zprava = f"<b>🚀 RANNÍ BRIEFING</b> | {datetime.now().strftime('%d.%m. %H:%M')}\n\n"
    zprava += f"👤 Investor: {USER_TO_REPORT}\n\n"
    zprava += f"💰 Hotovost (CZK ekv.): {total_cash_czk:,.0f} Kč\n"
    
    # Fear/Greed
    if score is not None:
        zprava += f"<b>🧠 Nálada trhu:</b> {rating} ({score}/100)\n"
    else:
        zprava += "🧠 Nálada trhu: Data nejsou dostupná.\n"
        
    zprava += f"\n💡 Tip: Nezapomeň zkontrolovat své investiční cíle!"

    # 4. ODESLÁNÍ
    ok, msg = notify.poslat_zpravu(zprava)
    
    if ok:
        print(f"✅ Report odeslán: {msg}")
    else:
        print(f"❌ Chyba odeslání: {msg}")
        
    return ok

if __name__ == "__main__":
    vytvor_a_odesli_denni_report()
