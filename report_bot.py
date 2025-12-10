# =======================================================
# SOUBOR: report_bot.py (Standalone script)
# =======================================================
import sys
import os
from datetime import datetime
import pandas as pd
# MĚNÍME IMPORTOVANÉ FUNKCE
from data_manager import SOUBOR_CASH, SOUBOR_DATA, SOUBOR_VYVOJ, nacti_csv
import bot_utils as utils # Nyní budeme volat utility jako utils.ziskej_kurzy()
from data_manager import SOUBOR_CASH, SOUBOR_DATA, nacti_csv 
import notification_engine as notify
import ai_brain as ai
import notification_engine as notify 
# Přidáme AI pro generování deníku
import ai_brain as ai 
# ... (Zbytek hlavičky report_bot.py)

# --- KONFIGURACE PRO STANDALONE SKRIPT ---
USER_TO_REPORT = "Filip" # Změň na svého uživatele, pokud je potřeba
# ----------------------------------------

def vytvor_a_odesli_denni_report():
    
    # 0. INICIALIZACE VŠECH KLÍČOVÝCH PROMĚNNÝCH NA 0.0 (TOTO CHYBĚLO!)
    hodnota_portfolia_usd = 0.0
    hodnota_portfolia_vcer_usd = 0.0
    denni_zmena_abs = 0.0
    denni_zmena_pct = 0.0
    total_cash_usd = 0.0 # Hotovost
    celk_hod_czk = 0.0 # Celkové jmění
    rating = "N/A"
    score = 50
    kurz_czk = 22.0 # Fallback pro kurz
    
    # 1. SBĚR DAT A KALKULACE
    try:
        # 1.1 Načtení dat a filtr pro uživatele
        df_cash_all = nacti_csv(SOUBOR_CASH)
        df_portfolio_all = nacti_csv(SOUBOR_DATA)

        df_cash = df_cash_all[df_cash_all['Owner'] == USER_TO_REPORT]
        df_portfolio = df_portfolio_all[df_portfolio_all['Owner'] == USER_TO_REPORT]

        print(f"✅ Načteno Portfolio pro: {USER_TO_REPORT}")
        print(f"   Tickery v portfoliu: {df_portfolio['Ticker'].unique().tolist()}")
        
        # Získání kurzu a Fear/Greed (musí být před kalkulací CZK!)
        kurzy = utils.ziskej_kurzy()
        kurz_czk = kurzy.get("CZK", 22.0)
        score, rating = utils.ziskej_fear_greed()

        # 1.2 Kalkulace Portfolia (pouze pokud NENÍ prázdné)
        if not df_portfolio.empty:
            df_g = df_portfolio.groupby('Ticker').agg({'Pocet': 'sum', 'Cena': 'mean'}).reset_index()
            list_tickeru = df_g['Ticker'].unique().tolist()
            ceny, vcer_close = utils.ziskej_ceny_portfolia_bot(list_tickeru)

            # Projdi portfolio pro denní kalkulaci
            for index, row in df_g.iterrows(): 
                tkr = row['Ticker']
                pocet = row['Pocet']
                
                # Ceny (Fallback na průměrnou nákupní cenu)
                p_dnes = ceny.get(tkr, row['Cena'])
                p_vcer = vcer_close.get(tkr, row['Cena'])

                hodnota_portfolia_usd += pocet * p_dnes
                hodnota_portfolia_vcer_usd += pocet * p_vcer
            
            # Denní změna (Portfolia)
            if hodnota_portfolia_vcer_usd > 0:
                denni_zmena_abs = hodnota_portfolia_usd - hodnota_portfolia_vcer_usd
                denni_zmena_pct = (denni_zmena_abs / hodnota_portfolia_vcer_usd) * 100

        # 1.3 Kalkulace hotovosti (USD ekvivalent)
        cash_usd = df_cash[df_cash['Mena'] == 'USD']['Castka'].sum()
        cash_czk = df_cash[df_cash['Mena'] == 'CZK']['Castka'].sum() / kurz_czk
        cash_eur = df_cash[df_cash['Mena'] == 'EUR']['Castka'].sum() * kurzy.get("EUR", 1.16)
        
        total_cash_usd = cash_usd + cash_czk + cash_eur
        
        # 1.4 Finální součty (Nyní bezpečné, protože všechny proměnné jsou inicializovány)
        celk_hod_usd = hodnota_portfolia_usd + total_cash_usd
        celk_hod_czk = celk_hod_usd * kurz_czk
        
    except Exception as e:
        # Tady už jen chytáme neočekávané chyby (YFinance, API atd.)
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
