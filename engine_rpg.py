import pandas as pd
from datetime import datetime
import streamlit as st

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

RPG_TASKS = [
    {"title": "První průzkum", "desc": "Přidej do Watchlistu akcii, kterou nemáš v portfoliu.", 
     "check_fn": lambda df, df_w, zustatky, vdf: not df_w.empty and any(t not in df['Ticker'].unique() for t in df_w['Ticker'].unique())},
    
    {"title": "Diverzifikace: Sektor", "desc": "Drž akcie ve 3 různých sektorech (Zkontroluj v Portfoliu).", 
     "check_fn": lambda df, df_w, zustatky, vdf: df['Sektor'].nunique() >= 3 and df.shape[0] >= 3},
    
    {"title": "Měnová rovnováha", "desc": "Drž hotovost alespoň ve 2 měnách (USD, CZK, EUR).", 
     "check_fn": lambda df, df_w, zustatky, vdf: sum(1 for v in zustatky.values() if v > 100) >= 2},
    
    {"title": "Mód Rentiera", "desc": "Drž 3 akcie s dividendovým výnosem > 1%.", 
     "check_fn": lambda df, df_w, zustatky, vdf: len([i for i in vdf.to_dict('records') if i.get('Divi', 0) is not None and i.get('Divi', 0) > 0.01]) >= 3 if isinstance(vdf, pd.DataFrame) else len([i for i in vdf if i.get('Divi', 0) is not None and i.get('Divi', 0) > 0.01]) >= 3},
      
    {"title": "Cílovací expert", "desc": "Nastav cílovou nákupní cenu u jedné akcie A cílovou prodejní cenu u jiné.", 
     "check_fn": lambda df, df_w, zustatky, vdf: (df_w['TargetBuy'] > 0).any() and (df_w['TargetSell'] > 0).any()},
    
    {"title": "Pohotovostní fond", "desc": "Drž alespoň 5 000 Kč v hotovosti (Měna CZK).", 
     "check_fn": lambda df, df_w, zustatky, vdf: zustatky.get('CZK', 0) >= 5000},
]

def get_task_progress(task_id, df, df_w, zustatky, vdf):
    """Vrací tuple (current, target, text) pro vizuální progress bar."""
    
    if task_id == 0: # První průzkum
        target = 1
        current = 1 if not df_w.empty and any(t not in df['Ticker'].unique() for t in df_w['Ticker'].unique()) else 0
        return current, target, f"Sledované (mimo portfolio): {current}/{target}"

    elif task_id == 1: # Diverzifikace
        target = 3
        current = df['Sektor'].nunique() if not df.empty else 0
        return current, target, f"Sektorů: {current}/{target}"

    elif task_id == 2: # Měny
        target = 2
        current = sum(1 for v in zustatky.values() if v > 100)
        return current, target, f"Aktivních měn: {current}/{target}"

    elif task_id == 3: # Rentier
        target = 3
        viz_data_list_safe = vdf.to_dict('records') if isinstance(vdf, pd.DataFrame) else vdf
        current = len([i for i in viz_data_list_safe if i.get('Divi', 0) is not None and i.get('Divi', 0) > 0.01])
        return current, target, f"Dividendových akcií: {current}/{target}"
      
    elif task_id == 4: # Cíle
        target = 2
        has_buy = (df_w['TargetBuy'] > 0).any()
        has_sell = (df_w['TargetSell'] > 0).any()
        current = (1 if has_buy else 0) + (1 if has_sell else 0)
        return current, target, f"Nastavené cíle (Buy + Sell): {current}/{target}"
      
    elif task_id == 5: # Fond
        target = 5000
        current = zustatky.get('CZK', 0)
        current_progress = min(current, target)
        return current_progress, target, f"CZK hotovost: {current:,.0f}/{target:,.0f} Kč"

    return 0, 1, "Není kvantifikovatelné"
