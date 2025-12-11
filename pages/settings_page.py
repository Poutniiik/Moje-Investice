# =========================================================================
# SOUBOR: pages/settings_page.py
# Cíl: Obsahuje veškerou logiku pro vykreslení stránky "⚙️ Nastavení"
# OPRAVA: Import celého modulu data_manager pro přístup ke konstantám SOUBOR_...
# =========================================================================
import streamlit as st
import pandas as pd
import hashlib
import time
import zipfile
import io
import extra_streamlit_components as stx
from datetime import datetime

# Imports z root modulů - klíčové závislosti
import data_manager # KLÍČOVÁ ZMĚNA
import notification_engine as notify

# --- HLAVNÍ FUNKCE STRÁNKY ---
# Uloz_data_fn je nyní atomická funkce (uloz_data_uzivatele)
def settings_page(USER, df, df_hist, df_cash, df_div, df_watch, uloz_data_fn, invalidate_core_fn):
    """
    Vykreslí stránku '⚙️ Nastavení'
    """
    st.title("⚙️ KONFIGURACE SYSTÉMU")
        
    # --- 1. AI KONFIGURACE ---
    with st.container(border=True):
        st.subheader("🤖 AI Jádro & Osobnost")
        c_stat1, c_stat2 = st.columns([1, 3])
        with c_stat1:
            if st.session_state.get('AI_AVAILABLE', False): st.success("API: ONLINE")
            else: st.error("API: OFFLINE")
        
        with c_stat2:
            is_on = st.toggle("Povolit AI funkce", value=st.session_state.get('ai_enabled', False))
            if is_on != st.session_state.get('ai_enabled', False):
                st.session_state['ai_enabled'] = is_on
                st.rerun()

        st.divider()
        st.caption("🎭 Nastavení chování (System Prompts)")
        
        if 'ai_prompts' not in st.session_state:
            st.session_state['ai_prompts'] = {
                "Ranní report": "Jsi cynický burzovní makléř z Wall Street. Používej finanční slang.",
                "Analýza akcií": "Jsi konzervativní Warren Buffett. Hledej hodnotu a bezpečí.",
                "Chatbot": "Jsi stručný a efektivní asistent Terminalu Pro."
            }

        prompts_df = pd.DataFrame(list(st.session_state['ai_prompts'].items()), columns=["Funkce", "Instrukce (Prompt)"])
        edited_prompts = st.data_editor(prompts_df, use_container_width=True, num_rows="dynamic", key="prompt_editor")

        if st.button("💾 Uložit nastavení AI"):
            new_prompts = dict(zip(edited_prompts["Funkce"], edited_prompts["Instrukce (Prompt)"]))
            st.session_state['ai_prompts'] = new_prompts
            st.toast("Osobnost AI aktualizována!", icon="🧠")

    # --- 2. DATA EDITORY ---
    st.write("")
    st.subheader("💾 DATA & SPRÁVA")
    t1, t2, t3, t4 = st.tabs(["PORTFOLIO", "HISTORIE", "HOTOVOST", "SLEDOVÁNÍ"])

    # --- PORTFOLIO ---
    with t1:
        new_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
        if st.button("Uložit Portfolio", key="btn_save_df"): 
            st.session_state['df'] = new_df
            # Používáme data_manager.SOUBOR_DATA
            uloz_data_fn(new_df, USER, data_manager.SOUBOR_DATA)
            invalidate_core_fn()
            st.success("Uloženo"); time.sleep(1); st.rerun()
            
    # --- HISTORIE ---
    with t2:
        new_h = st.data_editor(df_hist, num_rows="dynamic", use_container_width=True)
        if st.button("Uložit Historii", key="btn_save_hist"): 
            st.session_state['df_hist'] = new_h
            # Používáme data_manager.SOUBOR_HISTORIE
            uloz_data_fn(new_h, USER, data_manager.SOUBOR_HISTORIE)
            invalidate_core_fn()
            st.success("Uloženo"); time.sleep(1); st.rerun()
            
    # --- HOTOVOST (CASH) ---
    with t3:
        new_cash = st.data_editor(df_cash, num_rows="dynamic", use_container_width=True)
        if st.button("Uložit Hotovost", key="btn_save_cash"):
            st.session_state['df_cash'] = new_cash
            # Používáme data_manager.SOUBOR_CASH
            uloz_data_fn(new_cash, USER, data_manager.SOUBOR_CASH)
            invalidate_core_fn()
            st.success("Uloženo"); time.sleep(1); st.rerun()
            
    # --- SLEDOVÁNÍ (WATCHLIST) ---
    with t4:
        new_watch = st.data_editor(df_watch, num_rows="dynamic", use_container_width=True)
        if st.button("Uložit Sledování", key="btn_save_watch"):
            st.session_state['df_watch'] = new_watch
            # Používáme data_manager.SOUBOR_WATCHLIST
            uloz_data_fn(new_watch, USER, data_manager.SOUBOR_WATCHLIST)
            invalidate_core_fn()
            st.success("Uloženo"); time.sleep(1); st.rerun()

    # --- 3. ZÁLOHA ---
    st.divider(); st.subheader("📦 ZÁLOHA")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Zde používáme všechny Session State dataframes
        for n, d in [(data_manager.SOUBOR_DATA, df), (data_manager.SOUBOR_HISTORIE, df_hist), (data_manager.SOUBOR_CASH, df_cash), (data_manager.SOUBOR_DIVIDENDY, df_div), (data_manager.SOUBOR_WATCHLIST, df_watch)]:
            if not d.empty: zf.writestr(n, d.to_csv(index=False))
    
    st.download_button("Stáhnout Data", buf.getvalue(), f"backup_{datetime.now().strftime('%Y%m%d')}.zip", "application/zip")
    st.divider()
    st.subheader("📲 NOTIFIKACE (Telegram)")
    st.caption("Otestuj spojení s tvým mobilem.")

    # Voláme funkci z notifikačního modulu
    notify.otestovat_tlacitko()
