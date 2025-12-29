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
    Čistá logika: Přičte XP a zjistí, zda došlo k Level Upu.
    """
    df_new = df_stats.copy()
    user_str = str(user)
    
    # Inicializace uživatele
    if df_new[df_new['Owner'] == user_str].empty:
        old_level = 1
        new_row = pd.DataFrame([{
            "Owner": user_str, "XP": xp_amount, "Level": 1, "LastLogin": datetime.now()
        }])
        df_new = pd.concat([df_new, new_row], ignore_index=True)
        idx = df_new[df_new['Owner'] == user_str].index[0]
    else:
        idx = df_new[df_new['Owner'] == user_str].index[0]
        old_level = int(df_new.at[idx, 'XP'] // 500) + 1
        df_new.at[idx, 'XP'] += xp_amount

    # Výpočet nového levelu
    new_level = int(df_new.at[idx, 'XP'] // 500) + 1
    df_new.at[idx, 'Level'] = new_level
    
    level_up = new_level > old_level
    
    try:
        uloz_funkce(df_new, user, soubor_stats)
        return True, new_level, level_up, df_new
    except:
        return False, old_level, False, df_stats
