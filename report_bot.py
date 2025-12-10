# =======================================================
# SOUBOR: report_bot.py (Standalone script)
# =======================================================
import sys
import os
from datetime import datetime
import pandas as pd
# MĚNÍME IMPORTOVANÉ FUNKCE
from data_manager import SOUBOR_CASH, SOUBOR_DATA, SOUBOR_VYVOJ, nacti_csv
from utils import ziskej_fear_greed, ziskej_kurzy, ziskej_ceny_portfolia_bot # Nová funkce!
import notification_engine as notify 
# Přidáme AI pro generování deníku
import ai_brain as ai 
# ... (Zbytek hlavičky report_bot.py)

# --- KONFIGURACE PRO STANDALONE SKRIPT ---
USER_TO_REPORT = "FILIP" # Změň na svého uživatele, pokud je potřeba
# ----------------------------------------

def vytvor_a_odesli_denni_report():
    
    # ÚRYVEK K ZMĚNĚ V report_bot.py
    # 1. SBĚR DAT A INICIALIZACE
    try:
        # Načtení VŠECH dat
        df_cash_all = nacti_csv(SOUBOR_CASH)
        df_portfolio_all = nacti_csv(SOUBOR_DATA)

        # FILTROVÁNÍ DAT POUZE PRO AKTIVNÍHO UŽIVATELE (Tohle chybělo!)
        df_cash = df_cash_all[df_cash_all['Owner'] == USER_TO_REPORT]
        df_portfolio = df_portfolio_all[df_portfolio_all['Owner'] == USER_TO_REPORT]

        # KONTROLA PRÁZDNOTY
        if df_portfolio.empty:
            raise ValueError(f"Portfolio pro uživatele {USER_TO_REPORT} je prázdné.")
        
        # Získání kurzu a Fear/Greed
        # ... (zbytek logiky sběru dat)
        
        # 2. KALKULACE PORTFOLIA
        # ZDE MUSÍME POUŽÍT AGREGACI DAT Z PORTFOLIA (Jako v main.py)
        # Nyní to musí být správně, protože máme data
        
        df_g = df_portfolio.groupby('Ticker').agg({'Pocet': 'sum', 'Cena': 'mean'}).reset_index()
        df_g['Investice'] = df_portfolio.groupby('Ticker').apply(lambda x: (x['Pocet'] * x['Cena']).sum()).values
        

        # 3. KALKULACE ZMĚNY
        denni_zmena_abs = hodnota_portfolia_usd - hodnota_portfolia_vcer_usd
        # Aby se zabránilo dělení nulou při nulové hodnotě portfolia:
        if hodnota_portfolia_vcer_usd > 0:
            denni_zmena_pct = (denni_zmena_abs / hodnota_portfolia_vcer_usd) * 100
        else:
            denni_zmena_pct = 0.0
            
        # 4. CELKOVÁ HOTOVOST (stejná logika jako dříve, jen robustnější)
        cash_usd_to_czk = df_cash[df_cash['Mena'] == 'USD']['Castka'].sum()
        total_cash_usd = cash_usd_to_czk / kurzy.get("CZK", 22.0)
        
        celk_hod_usd = hodnota_portfolia_usd + total_cash_usd
        celk_hod_czk = celk_hod_usd * kurzy.get("CZK", 22.0)

    except Exception as e:
        error_msg = f"❌ CHYBA AUTOREPORTU:\nSelhalo stažení/kalkulace dat: {e}"
        return notify.poslat_zpravu(error_msg)

   # ÚRYVEK K ZMĚNĚ V report_bot.py

    # 5. GENERACE AI DENÍKU
    # AI potřebuje data v CZK, takže přepočítáme
    ai_model, ai_ok = ai.init_ai()
    denik = "AI modul není k dispozici."
    if ai_ok:
        # ZDE JE OPRAVA: POUŽÍVÁME SKUTEČNÝ NÁZEV Z ai_brain.py
        denik = ai.generate_rpg_story(
            ai_model, 
            level_name="BETA TESTER", 
            denni_zmena=denni_zmena_abs * kurzy.get("CZK", 22.0),
            celk_hod=celk_hod_czk,
            score=score if score else 50
        )
    
    # 6. TVORBA ZPRÁVY (HTML pro Telegram)
    # Zbarvíme změnu podle výsledku
    barva = "🟢" if denni_zmena_abs >= 0 else "🔴"
    
    zprava = f"<b>🚀 RANNÍ BRIEFING</b> | {datetime.now().strftime('%d.%m. %H:%M')}\n\n"
    zprava += f"👤 Investor: {USER_TO_REPORT}\n\n"
    zprava += f"💎 **Celkové jmění:** {celk_hod_czk:,.0f} Kč\n"
    zprava += f"📈 **Hodnota Portfolia:** {hodnota_portfolia_usd:,.0f} $\n"
    zprava += f"{barva} **Denní změna:** {denni_zmena_abs:+.0f} $ ({denni_zmena_pct:+.2f}%)\n"
    zprava += f"💰 Hotovost (USD): {total_cash_usd:,.0f} $\n\n"
    
    zprava += f"<b>🧠 Nálada trhu:</b> {rating} ({score}/100)\n"
    zprava += f"--- KAPITÁNSKÝ DENÍK ---\n"
    zprava += f"<i>{denik}</i>\n"

    # 7. ODESLÁNÍ
    return notify.poslat_zpravu(zprava)

if __name__ == "__main__":
    vytvor_a_odesli_denni_report()
