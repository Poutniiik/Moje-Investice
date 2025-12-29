import pandas as pd
from datetime import datetime

# --- KONFIGURACE LEVELŮ ---
# Tady si můžeš definovat názvy levelů, jak chceš
LEVELS = {
    1: "Burzovní Elév",
    2: "Asistent Makléře",
    3: "Junior Trader",
    4: "Portfolio Manažer",
    5: "Vlk z Wall Street",
    10: "Investiční Legenda"
}

def vypocitej_level(celkove_xp):
    """Vrátí číslo levelu, název a progres k dalšímu levelu."""
    # Každý level vyžaduje např. 500 XP
    xp_za_level = 500
    level = int(celkove_xp // xp_za_level) + 1
    progress = (celkove_xp % xp_za_level) / xp_za_level
    
    # Získání názvu levelu (nebo default)
    level_name = LEVELS.get(level, LEVELS[max(LEVELS.keys())] if level > max(LEVELS.keys()) else "Finanční Magnát")
    
    return level, level_name, progress

def pridej_xp_engine(user, xp_amount, df_stats, uloz_funkce, soubor_stats):
    """
    Logika pro přidání zkušeností a uložení do statistik.
    """
    df_new = df_stats.copy()
    
    # Najdeme řádek uživatele, nebo vytvoříme nový
    if user not in df_new['Owner'].values:
        new_user = pd.DataFrame([{
            "Owner": user, "XP": 0, "Level": 1, "Trades": 0, "LastUpdate": datetime.now()
        }])
        df_new = pd.concat([df_new, new_user], ignore_index=True)
    
    # Přidáme XP
    idx = df_new[df_new['Owner'] == user].index[0]
    stare_xp = df_new.at[idx, 'XP']
    nove_xp = stare_xp + xp_amount
    df_new.at[idx, 'XP'] = nove_xp
    df_new.at[idx, 'LastUpdate'] = datetime.now()
    
    # Zjistíme, jestli postoupil na nový level pro hlášku
    stary_lvl, _, _ = vypocitej_level(stare_xp)
    novy_lvl, lvl_name, _ = vypocitej_level(nove_xp)
    
    level_up = novy_lvl > stary_lvl
    
    try:
        uloz_funkce(df_new, user, soubor_stats)
        return True, nove_xp, level_up, lvl_name, df_new
    except Exception as e:
        return False, stare_xp, False, "", None
