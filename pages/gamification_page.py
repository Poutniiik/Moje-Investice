# =========================================================================
# SOUBOR: pages/gamification_page.py
# Cíl: Obsahuje veškerou logiku pro vykreslení stránky "🎮 Gamifikace"
# =========================================================================
import streamlit as st
import pandas as pd
import random
import time
import numpy as np

# Imports z root modulů
import utils
import ai_brain

# --- NOVÉ STATICKÉ DATOVÉ STRUKTURY PRO ÚKOLY ---
RPG_TASKS = [
    # 1. Watchlist research
    {"title": "První průzkum", "desc": "Přidej do Watchlistu akcii, kterou nemáš v portfoliu.", 
     "check_fn": lambda df, df_w, zustatky, vdf: not df_w.empty and any(t not in df['Ticker'].unique() for t in df_w['Ticker'].unique())},
    
    # 2. Diversification by sector
    {"title": "Diverzifikace: Sektor", "desc": "Drž akcie ve 3 různých sektorech (Zkontroluj v Portfoliu).", 
     "check_fn": lambda df, df_w, zustatky, vdf: df['Sektor'].nunique() >= 3 and df.shape[0] >= 3},
    
    # 3. Diversification by currency (cash)
    {"title": "Měnová rovnováha", "desc": "Drž hotovost alespoň ve 2 měnách (USD, CZK, EUR).", 
     "check_fn": lambda df, df_w, zustatky, vdf: len([k for k,v in zustatky.items() if v > 10]) >= 2},

    # 4. First Dividend
    {"title": "Rentier", "desc": "Získej první dividendu (Yield > 0 u nějaké akcie).", 
     "check_fn": lambda df, df_w, zustatky, vdf: not vdf.empty and any(vdf['Divi'] > 0)},
     
    # 5. HODLer
    {"title": "Diamond Hands", "desc": "Hodnota portfolia > 100 000 CZK.", 
     "check_fn": lambda df, df_w, zustatky, vdf: (vdf['HodnotaUSD'].sum() * 24) > 100000} # Hrubý odhad kurzu
]

def gamification_page(USER, celk_hod_czk, hist_vyvoje, kurzy, df, df_watch, zustatky, vdf, model, AI_AVAILABLE):
    """
    Hlavní stránka Gamifikace.
    Nyní přijímá 'hist_vyvoje' pro výpočet denní změny.
    """
    st.title(f"🎮 RPG PROFIL: {USER}")

    # 1. Level System
    xp = int(celk_hod_czk / 1000)
    level = int(np.sqrt(xp)) if xp > 0 else 1
    
    level_names = ["Novic", "Učeň", "Obchodník", "Investořík", "Vlk z Wall Street", "Finanční Magnát", "Pán Vesmíru"]
    level_name = level_names[min(level, len(level_names)-1)]

    # Progress bar to next level
    next_level_xp = (level + 1)**2 * 1000
    current_level_base_xp = level**2 * 1000
    
    # Ošetření dělení nulou
    denom = next_level_xp - current_level_base_xp
    if denom == 0: denom = 1
        
    progress = (celk_hod_czk - current_level_base_xp) / denom
    progress = max(0.0, min(1.0, progress))

    c1, c2 = st.columns([1, 3])
    with c1:
        st.image("https://api.dicebear.com/7.x/avataaars/svg?seed=" + str(USER), width=150)
    with c2:
        st.subheader(f"Level {level}: {level_name}")
        st.progress(progress)
        st.caption(f"XP: {celk_hod_czk:,.0f} / {next_level_xp:,.0f} (Další level: {next_level_xp - celk_hod_czk:,.0f} Kč)")

    st.divider()

    # 2. Daily Quest (AI Story)
    st.subheader("📜 DENNÍ ZÁPIS (AI Narrator)")
    
    # Výpočet denní změny z historie
    denni_zmena_czk = 0
    if hist_vyvoje is not None and not hist_vyvoje.empty and len(hist_vyvoje) > 1:
        # Poslední záznam je dnešek (pokud byl aktualizován), předposlední je včerejšek
        # Řadíme pro jistotu podle data
        hist_sorted = hist_vyvoje.sort_values('Date')
        last_val = hist_sorted.iloc[-1]['TotalUSD']
        prev_val = hist_sorted.iloc[-2]['TotalUSD']
        denni_zmena_usd = last_val - prev_val
        denni_zmena_czk = denni_zmena_usd * kurzy.get("CZK", 24.5)

    if 'rpg_story_cache' not in st.session_state:
        st.session_state['rpg_story_cache'] = None
    
    col_gen, col_story = st.columns([1, 4])
    with col_gen:
        if st.button("🎲 GENEROVAT PŘÍBĚH", type="primary", use_container_width=True):
            if AI_AVAILABLE and model:
                with st.spinner("Dungeon Master hází kostkou..."):
                    sc, _ = utils.cached_fear_greed()
                    actual_score = sc if sc else 50
                    # Voláme utilitní AI funkci (předpokládáme, že je v ai_brain)
                    try:
                        rpg_res_text = ai_brain.generate_rpg_story(model, level_name, denni_zmena_czk, celk_hod_czk, actual_score)
                        st.session_state['rpg_story_cache'] = rpg_res_text
                    except AttributeError:
                        st.warning("Funkce generate_rpg_story nenalezena v ai_brain. (Je modul aktualizován?)")
                    except Exception as e:
                        st.error(f"Chyba: {e}")
            else:
                st.error("AI není dostupné.")

    with col_story:
        if st.session_state['rpg_story_cache']:
            st.markdown(f"""
            <div style="background-color: #0D1117; border-left: 4px solid #AB63FA; padding: 15px; border-radius: 5px;">
                <p style="font-style: italic; color: #E6E6E6; margin: 0;">"{st.session_state['rpg_story_cache']}"</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("Klikni na tlačítko pro vygenerování dnešního příběhu na základě tvého zisku/ztráty.")

    st.divider()

    # 3. Achievements / Quests
    st.subheader("🏆 ÚKOLY A ODZNAKY")
    
    cols = st.columns(len(RPG_TASKS))
    for i, task in enumerate(RPG_TASKS):
        # Vyhodnocení splnění
        is_done = False
        try:
            is_done = task["check_fn"](df, df_watch, zustatky, vdf)
        except Exception:
            is_done = False
            
        with cols[i]:
            with st.container(border=True):
                if is_done:
                    st.markdown("### ✅")
                    st.markdown(f"**{task['title']}**")
                    st.caption("Splněno!")
                else:
                    st.markdown("### 🔒")
                    st.markdown(f"**{task['title']}**")
                    st.caption(task['desc'])
