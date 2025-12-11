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

# --- NOVÉ STATICKÉ DATOVÉ STRUKTURY PRO ÚKOLY (PŘESUNUTO Z web_investice.py) ---
RPG_TASKS = [
    # 1. Watchlist research
    {"title": "První průzkum", "desc": "Přidej do Watchlistu akcii, kterou nemáš v portfoliu.", 
     "check_fn": lambda df, df_w, zustatky, vdf: not df_w.empty and any(t not in df['Ticker'].unique() for t in df_w['Ticker'].unique())},
    
    # 2. Diversification by sector
    {"title": "Diverzifikace: Sektor", "desc": "Drž akcie ve 3 různých sektorech (Zkontroluj v Portfoliu).", 
     "check_fn": lambda df, df_w, zustatky, vdf: df['Sektor'].nunique() >= 3 and df.shape[0] >= 3},
    
    # 3. Diversification by currency (cash)
    {"title": "Měnová rovnováha", "desc": "Drž hotovost alespoň ve 2 měnách (USD, CZK, EUR).", 
     "check_fn": lambda df, df_w, zustatky, vdf: sum(1 for v in zustatky.values() if v > 100) >= 2},
    
    # 4. Income investing
    {"title": "Mód Rentiera", "desc": "Drž 3 akcie s dividendovým výnosem > 1%.", 
     "check_fn": lambda df, df_w, zustatky, vdf: len([i for i in vdf.to_dict('records') if i.get('Divi', 0) is not None and i.get('Divi', 0) > 0.01]) >= 3 if isinstance(vdf, pd.DataFrame) else len([i for i in vdf if i.get('Divi', 0) is not None and i.get('Divi', 0) > 0.01]) >= 3},
      
    # 5. Risk management (Setting both types of targets)
    {"title": "Cílovací expert", "desc": "Nastav cílovou nákupní cenu u jedné akcie A cílovou prodejní cenu u jiné.", 
     "check_fn": lambda df, df_w, zustatky, vdf: (df_w['TargetBuy'] > 0).any() and (df_w['TargetSell'] > 0).any()},
    
    # 6. Liquidity (CZK cash buffer) - NOVÝ ÚKOL
    {"title": "Pohotovostní fond", "desc": "Drž alespoň 5 000 Kč v hotovosti (Měna CZK).", 
     "check_fn": lambda df, df_w, zustatky, vdf: zustatky.get('CZK', 0) >= 5000},
]

# --- Progresní funkce pro RPG úkoly (PŘESUNUTO Z web_investice.py) ---
def get_task_progress(task_id, df, df_w, zustatky, vdf):
    """Vrací tuple (current, target) pro vizuální progress bar."""
    
    # Úkoly jsou indexovány dle RPG_TASKS
    
    if task_id == 0: # První průzkum: Přidej do Watchlistu akcii, kterou nemáš v portfoliu.
        target = 1
        current = 1 if not df_w.empty and any(t not in df['Ticker'].unique() for t in df_w['Ticker'].unique()) else 0
        return current, target, f"Sledované (mimo portfolio): {current}/{target}"

    elif task_id == 1: # Diverzifikace: Sektor: Drž akcie ve 3 různých sektorech.
        target = 3
        current = df['Sektor'].nunique() if not df.empty else 0
        return current, target, f"Sektorů: {current}/{target}"

    elif task_id == 2: # Měnová rovnováha: Drž hotovost alespoň ve 2 měnách.
        target = 2
        current = sum(1 for v in zustatky.values() if v > 100)
        return current, target, f"Aktivních měn: {current}/{target}"

    elif task_id == 3: # Mód Rentiera: Drž 3 akcie s dividendovým výnosem > 1%.
        target = 3
        # Kontrola, zda vdf je DataFrame nebo list dictů
        viz_data_list_safe = vdf.to_dict('records') if isinstance(vdf, pd.DataFrame) else vdf
        current = len([i for i in viz_data_list_safe if i.get('Divi', 0) is not None and i.get('Divi', 0) > 0.01])
        return current, target, f"Dividendových akcií: {current}/{target}"
      
    elif task_id == 4: # Cílovací expert: Nastav cílovou nákupní cenu u jedné akcie A cílovou prodejní cenu u jiné.
        target = 2
        has_buy = (df_w['TargetBuy'] > 0).any()
        has_sell = (df_w['TargetSell'] > 0).any()
        current = (1 if has_buy else 0) + (1 if has_sell else 0)
        return current, target, f"Nastavené cíle (Buy + Sell): {current}/{target}"
      
    elif task_id == 5: # Pohotovostní fond: Drž alespoň 5 000 Kč v hotovosti.
        target = 5000
        current = zustatky.get('CZK', 0)
        # Progress bar by mel být limitován do 1.0, i když máme více
        current_progress = min(current, target)
        return current_progress, target, f"CZK hotovost: {current:,.0f}/{target:,.0f} Kč"

    return 0, 1, "Není kvantifikovatelné" # Výchozí hodnota

# --- HLAVNÍ FUNKCE STRÁNKY ---
def gamification_page(USER, level_name, level_progress, celk_hod_czk, AI_AVAILABLE, model, hist_vyvoje, kurzy, df, df_div, vdf, zustatky):
    """Vykreslí stránku '🎮 Gamifikace'."""

    st.title("🎮 INVESTIČNÍ ARÉNA")
   
    # --- 1. LEVEL HRÁČE (STATUS BAR) ---
    with st.container(border=True):
        c_lev1, c_lev2 = st.columns([3, 1])
        with c_lev1:
            st.subheader(f"Úroveň: {level_name}")
            # Vlastní progress bar s popiskem
            st.progress(level_progress)
           
            # Výpočet do dalšího levelu
            next_level_val = 0
            if celk_hod_czk < 10000: next_level_val = 10000
            elif celk_hod_czk < 50000: next_level_val = 50000
            elif celk_hod_czk < 100000: next_level_val = 100000
            elif celk_hod_czk < 500000: next_level_val = 500000
           
            if next_level_val > 0:
                chybi = next_level_val - celk_hod_czk
                st.caption(f"Do další úrovně chybí: **{chybi:,.0f} Kč**")
            else:
                st.success("🎉 MAX LEVEL DOSAŽEN!")
       
        with c_lev2:
            # Velký avatar nebo ikona levelu
            icon_map = {"Novic": "🧒", "Učeň": "🧑‍🎓", "Trader": "💼", "Profi": "🎩", "Velryba": "🐋"}
            # Získáme čisté jméno bez emoji pro klíč
            clean_name = level_name.split()[0]
            ikona = icon_map.get(clean_name, "👾")
            st.markdown(f"<h1 style='text-align: center; font-size: 50px;'>{ikona}</h1>", unsafe_allow_html=True)


    # --- 2. SÍŇ SLÁVY (ODZNAKY) - GRID 2x2 ---
    st.write("")
    st.subheader("🏆 SÍŇ SLÁVY (Odznaky)")
   
    # Příprava podmínek
    df_w = st.session_state.get('df_watch', pd.DataFrame())
    has_first = not df.empty
    cnt = len(df['Ticker'].unique()) if not df.empty else 0
    divi_total = 0
    if not df_div.empty:
        divi_total = df_div.apply(
            lambda r: r['Castka'] * (
                kurzy.get('CZK', 20.85) if r['Mena'] == 'USD'
                else (kurzy.get('EUR', 1.16) * kurzy.get('CZK', 20.85) if r['Mena'] == 'EUR' else 1)
            ), axis=1).sum()


    # Pomocná funkce pro render karty
    def render_badge_card(col, title, desc, cond, icon, color):
        with col:
            opacity = "1.0" if cond else "0.4"
            border_color = color if cond else "#30363D"
            bg_color = "rgba(255,255,255,0.05)" if cond else "transparent"
           
            st.markdown(f"""
            <div style="
                border: 1px solid {border_color};
                border-radius: 10px;
                padding: 15px;
                text-align: center;
                background-color: {bg_color};
                opacity: {opacity};
                margin-bottom: 10px;">
                <div style="font-size: 40px; margin-bottom: 10px;">{icon}</div>
                <div style="font-weight: bold; color: {color}; margin-bottom: 5px;">{title}</div>
                <div style="font-size: 12px; color: #8B949E;">{desc}</div>
            </div>
            """, unsafe_allow_html=True)


    # Řádek 1 (2 sloupce)
    c1, c2 = st.columns(2)
    render_badge_card(c1, "Začátečník", "Kup první akcii", has_first, "🥉", "#CD7F32") # Bronz
    render_badge_card(c2, "Stratég", "Drž 3 různé firmy", cnt >= 3, "🥈", "#C0C0C0")   # Stříbro
   
    # Řádek 2 (2 sloupce)
    c3, c4 = st.columns(2)
    render_badge_card(c3, "Boháč", "Portfolio > 100k", celk_hod_czk > 100000, "🥇", "#FFD700") # Zlato
    render_badge_card(c4, "Rentiér", "Dividendy > 500 Kč", divi_total > 500, "💎", "#00BFFF") # Diamant


    # --- 3. DYNAMICKÉ VÝZVY (QUEST LOG) ---
    st.divider()
    st.subheader("📜 QUEST LOG (Aktivní výzvy)")
   
    if 'rpg_tasks' not in st.session_state:
        st.session_state['rpg_tasks'] = []
   
    if not st.session_state['rpg_tasks']:
        try:
            for i, task in enumerate(RPG_TASKS):
                st.session_state['rpg_tasks'].append({"id": i, "title": task["title"], "desc": task["desc"], "completed": False})
        except: pass
   
    all_tasks_completed = True
   
    # Zobrazení úkolů
    for i, task_state in enumerate(st.session_state['rpg_tasks']):
        df_w_local = st.session_state.get('df_watch', pd.DataFrame()) # Používáme lokální session state
        viz_data_list_local = vdf.to_dict('records') if isinstance(vdf, pd.DataFrame) else vdf
       
        try:
            original_task = RPG_TASKS[task_state['id']]
            # Kontrola
            is_completed = original_task['check_fn'](df, df_w_local, zustatky, viz_data_list_local)
            # Progress text
            current, target, progress_text = get_task_progress(task_state['id'], df, df_w_local, zustatky, viz_data_list_local)
        except:
            is_completed = False
            current, target, progress_text = 0, 1, "Neznámý stav"


        st.session_state['rpg_tasks'][i]['completed'] = is_completed
        if not is_completed: all_tasks_completed = False
           
        # Vykreslení Questu (Kompaktní karta)
        with st.container(border=True):
            col_q1, col_q2 = st.columns([1, 5])
            with col_q1:
                st.markdown(f"<div style='font-size: 25px; text-align: center;'>{'✅' if is_completed else '📜'}</div>", unsafe_allow_html=True)
            with col_q2:
                st.markdown(f"**{task_state['title']}**")
               
                # Progress Bar
                if target > 0:
                    pct = min(current / target, 1.0)
                    st.progress(pct)
                    st.caption(f"{progress_text} ({int(pct*100)}%)")
                else:
                    st.info(progress_text)


    if all_tasks_completed and len(st.session_state['rpg_tasks']) > 0:
        st.balloons()
        st.success("VŠECHNY QUESTY SPLNĚNY! ⚔️")
        if st.button("🔄 Generovat nové RPG úkoly"):
            st.session_state['rpg_tasks'] = []
            st.rerun()


    # --- 4. AI DENNÍ LOGBOOK ---
    if AI_AVAILABLE and st.session_state.get('ai_enabled', False):
        st.divider()
        st.subheader("🎲 DENNÍ ZÁPIS (AI Narrator)")
       
        # Logika pro příběh
        denni_zmena_czk = (celk_hod_czk - (hist_vyvoje.iloc[-2]['TotalUSD'] * kurzy.get("CZK", 21))) if len(hist_vyvoje) > 1 else 0
       
        if 'rpg_story_cache' not in st.session_state:
            st.session_state['rpg_story_cache'] = None
           
        if st.button("🎲 GENEROVAT PŘÍBĚH DNE", type="secondary", use_container_width=True):
            with st.spinner("Dungeon Master hází kostkou..."):
                sc, _ = utils.cached_fear_greed()
                actual_score = sc if sc else 50
                # Voláme utilitní AI funkci
                rpg_res_text = ai_brain.generate_rpg_story(model, level_name, denni_zmena_czk, celk_hod_czk, actual_score)
                st.session_state['rpg_story_cache'] = rpg_res_text


        if st.session_state['rpg_story_cache']:
            st.markdown(f"""
            <div style="background-color: #0D1117; border-left: 4px solid #AB63FA; padding: 15px; border-radius: 5px;">
                <p style="font-style: italic; color: #E6E6E6; margin: 0;">"{st.session_state['rpg_story_cache']}"</p>
            </div>
            """, unsafe_allow_html=True)
           
    # --- 5. MOUDRO DNE ---
    st.divider()
    # Tady by normálně byla globální konstanta, ale pro modularitu použijeme lokální volání random.choice
    st.caption("💡 Moudro dne")
    st.info(f"*{random.choice(st.session_state.get('CITATY', ['Jeden krok najednou.']))}*") # Používáme fallback na CITATY
