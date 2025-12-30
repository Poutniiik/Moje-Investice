import pandas as pd
from datetime import datetime

# --- KONFIGURACE ---
XP_PER_LEVEL = 500

RANKS = {
    1: {"name": "Burzovní Elév", "icon": "🧒"},
    2: {"name": "Asistent Makléře", "icon": "🧑‍🎓"},
    3: {"name": "Junior Trader", "icon": "💼"},
    4: {"name": "Portfolio Manažer", "icon": "🎩"},
    5: {"name": "Bankéř (Vlk z Wall Street)", "icon": "🐋"},
    10: {"name": "Investiční Matador", "icon": "🚀"}
}

def get_player_profile(user, df_stats):
    """Kompletní balíček dat pro UI profilu."""
    if df_stats.empty:
        return None
        
    user_row = df_stats[df_stats['Owner'] == str(user)]
    if user_row.empty:
        return None
        
    total_xp = user_row['XP'].iloc[0]
    
    # Výpočty levelu
    level = int(total_xp // XP_PER_LEVEL) + 1
    xp_in_level = total_xp % XP_PER_LEVEL
    progress_pct = min(xp_in_level / XP_PER_LEVEL, 1.0)
    xp_to_next = XP_PER_LEVEL - xp_in_level
    
    # Získání hodnosti
    rank_info = RANKS[1] # fallback
    for l in sorted(RANKS.keys(), reverse=True):
        if level >= l:
            rank_info = RANKS[l]
            break
            
    # Načtení hotových questů
    saved_raw = str(user_row['CompletedQuests'].iloc[0])
    completed_ids = [q.strip() for q in saved_raw.split(",") if q.strip()]
    
    return {
        "level": level,
        "xp_total": total_xp,
        "xp_current": xp_in_level,
        "xp_needed": XP_PER_LEVEL,
        "progress": progress_pct,
        "xp_to_next": xp_to_next,
        "rank_name": rank_info["name"],
        "rank_icon": rank_info["icon"],
        "completed_ids": completed_ids
    }

def pridej_xp_engine(user, xp_amount, df_stats, uloz_funkce, soubor_stats):
    """Zpracuje přidání XP a vrátí aktualizovaná data."""
    df_new = df_stats.copy()
    user_str = str(user)
    
    # Pokud uživatel neexistuje, vytvoříme ho
    if df_new.empty or user_str not in df_new['Owner'].values:
        new_row = pd.DataFrame([{
            "Owner": user_str, "XP": xp_amount, "Level": 1, "LastLogin": datetime.now(), "CompletedQuests": ""
        }])
        df_new = pd.concat([df_new, new_row], ignore_index=True)
    else:
        idx = df_new[df_new['Owner'] == user_str].index[0]
        old_xp = df_new.at[idx, 'XP']
        new_xp = old_xp + xp_amount
        df_new.at[idx, 'XP'] = new_xp
        df_new.at[idx, 'Level'] = int(new_xp // XP_PER_LEVEL) + 1
        df_new.at[idx, 'LastLogin'] = datetime.now()

    try:
        uloz_funkce(df_new, user, soubor_stats)
        return True, int(df_new[df_new['Owner'] == user_str]['Level'].iloc[0]), df_new
    except:
        return False, 1, df_stats
