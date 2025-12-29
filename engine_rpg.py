import pandas as pd
from datetime import datetime

# --- KONFIGURACE LEVELŮ ---
def ziskej_hodnost_a_ikonu(level):
    """Převede číslo levelu na ikonu a název (sjednoceno s LEVELS)."""
    # Použijeme tvé názvy z LEVELS a přidáme k nim ikony
    rank_icons = {
        1: "🧒 Burzovní Elév",
        2: "🧑‍🎓 Asistent Makléře",
        3: "💼 Junior Trader",
        4: "🎩 Portfolio Manažer",
        5: "🐋 Vankéř (Vlk z Wall Street)",
        10: "🚀 Investiční Matador"
    }
    # Najde nejbližší nižší nebo rovný level v seznamu
    dostupne_levely = sorted(rank_icons.keys(), reverse=True)
    for l in dostupne_levely:
        if level >= l:
            return rank_icons[l]
    return "🧒 Burzovní Elév"

def vypocitej_detail_levelu(total_xp):
    """Vypočítá přesná čísla pro progress bar a popisky."""
    xp_za_level = 500
    level = int(total_xp // xp_za_level) + 1
    xp_v_levelu = total_xp % xp_za_level
    progress_pct = xp_v_levelu / xp_za_level
    xp_do_dalsiho = xp_za_level - xp_v_levelu
    return level, xp_v_levelu, progress_pct, xp_do_dalsiho


def pridej_xp_engine(user, xp_amount, df_stats, uloz_funkce, soubor_stats):
    """
    Super-robustní logika: Pokud sloupce chybí, vytvoří je.
    """
    # 1. Pokud nám přišlo něco, co není DataFrame, nebo je to prázdné
    if df_stats is None or (isinstance(df_stats, pd.DataFrame) and df_stats.empty and 'Owner' not in df_stats.columns):
        df_new = pd.DataFrame(columns=['Owner', 'XP', 'LastLogin', 'Level', 'CompletedQuests'])
    else:
        df_new = df_stats.copy()

    user_str = str(user)
    
    # 2. POJISTKA: Pokud sloupec 'Owner' stále chybí (např. načten prázdný soubor bez hlavičky)
    if 'Owner' not in df_new.columns:
        # Pokud tam nejsou sloupce, ale jsou tam data, zkusíme je pojmenovat
        if not df_new.empty and len(df_new.columns) >= 2:
             df_new.columns = ['Owner', 'XP', 'LastLogin', 'Level', 'CompletedQuests'][:len(df_new.columns)]
        else:
             # Raději vytvoříme novou strukturu
             df_new = pd.DataFrame(columns=['Owner', 'XP', 'LastLogin', 'Level', 'CompletedQuests'])

    # 3. Teď už je hledání bezpečné
    mask = df_new['Owner'] == user_str
    
    if df_new[mask].empty:
        old_level = 1
        new_row = pd.DataFrame([{
            "Owner": user_str, "XP": xp_amount, "Level": 1, "LastLogin": datetime.now()
        }])
        df_new = pd.concat([df_new, new_row], ignore_index=True)
        new_level = 1
    else:
        idx = df_new[mask].index[0]
        old_level = int(df_new.at[idx, 'XP'] // 500) + 1
        df_new.at[idx, 'XP'] += xp_amount
        new_level = int(df_new.at[idx, 'XP'] // 500) + 1
        df_new.at[idx, 'Level'] = new_level
        df_new.at[idx, 'LastLogin'] = datetime.now()

    level_up = new_level > old_level
    
    try:
        uloz_funkce(df_new, user, soubor_stats)
        return True, new_level, level_up, df_new
    except:
        return False, 1, False, df_stats
