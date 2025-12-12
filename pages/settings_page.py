# =========================================================================
# SOUBOR: pages/settings_page.py
# Cíl: Obsahuje veškerou logiku pro vykreslení stránky "⚙️ Nastavení"
# =========================================================================
import streamlit as st
import pandas as pd
import hashlib
import time
import zipfile
import io
# ODSTRANĚNO: import extra_streamlit_components as stx (již nepoužíváme, způsobovalo zmatek)
from datetime import datetime

# Imports z root modulů
import data_manager
import notification_engine as notify

def settings_page(USER, df, df_hist, df_cash, df_div, df_watch, uloz_data_fn, invalidate_core_fn):
    """
    Vykreslí stránku '⚙️ Nastavení'
    """
    st.title("⚙️ KONFIGURACE SYSTÉMU")
        
    # --- 1. AI KONFIGURACE (Status bar) ---
    with st.container(border=True):
        st.subheader("🤖 AI Jádro & Osobnost")
        c_stat1, c_stat2 = st.columns([1, 3])
        with c_stat1:
            if st.session_state.get('AI_AVAILABLE', False): st.success("API: ONLINE")
            else: st.error("API: OFFLINE")
        
        with c_stat2:
             st.caption("Model: Gemini 2.5 Flash | Mood: Cyberpunk Analyst")

    st.write("")

    # --- 2. TABY PRO NASTAVENÍ ---
    t1, t2, t3, t4 = st.tabs(["👤 Profil", "🔔 Notifikace", "🛠️ Data & Zálohy", "👀 Watchlist"])
    
    # --- PROFIL ---
    with t1:
        st.subheader("Správa Profilu")
        current_user = st.text_input("Uživatel", value=USER, disabled=True)
        st.info("Změna hesla a avataru bude dostupná v příští verzi.")

    # --- NOTIFIKACE ---
    with t2:
        st.subheader("Telegram Notifikace")
        st.caption("Nastav si Telegram bota pro denní reporty.")
        
        # Testovací tlačítko
        if st.button("📨 Otestovat spojení (Telegram)", use_container_width=True):
            ok, msg = notify.poslat_zpravu(f"👋 Ahoj {USER}, test spojení z Terminal Pro!")
            if ok: st.success(msg)
            else: st.error(msg)

    # --- DATA & ZÁLOHY ---
    with t3:
        st.subheader("📦 Záloha a Export")
        
        # Příprava ZIPu
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # Mapování souborů a dataframů
            files_map = [
                (data_manager.SOUBOR_DATA, df),
                (data_manager.SOUBOR_HISTORIE, df_hist),
                (data_manager.SOUBOR_CASH, df_cash),
                (data_manager.SOUBOR_DIVIDENDY, df_div),
                (data_manager.SOUBOR_WATCHLIST, df_watch)
            ]
            
            for fname, dframe in files_map:
                if not dframe.empty:
                    zf.writestr(fname, dframe.to_csv(index=False))
                else:
                    zf.writestr(fname, "EMPTY")
        
        st.download_button(
            label="⬇️ STÁHNOUT KOMPLETNÍ ZÁLOHU (ZIP)",
            data=buf.getvalue(),
            file_name=f"backup_{USER}_{datetime.now().strftime('%Y%m%d')}.zip",
            mime="application/zip",
            use_container_width=True
        )

        st.divider()
        
        st.subheader("⚠️ Nebezpečná zóna (Editace)")
        st.warning("Přímá editace databáze. Používej opatrně!")
        
        # Editace Cash
        with st.expander("Editovat Hotovost (Cash)"):
            # PŘIDÁN KLÍČ 'key="editor_cash"' PROTI DUPLICITĚ
            edited_cash = st.data_editor(df_cash, num_rows="dynamic", use_container_width=True, key="editor_cash")
            if st.button("Uložit Hotovost", type="primary", key="save_cash"):
                uloz_data_fn(edited_cash, USER, data_manager.SOUBOR_CASH)
                invalidate_core_fn()
                st.success("✅ Hotovost uložena!") # Sjednoceno na success banner
                time.sleep(1)
                st.rerun()

    # --- WATCHLIST (Sledování) ---
    with t4:
        st.subheader("👀 Sledované akcie")
        st.caption("Přidej akcie, které chceš sledovat (zobrazí se v Analýze a na Dashboardu).")
        
        # ZDE BYLA CHYBA: Chyběl unikátní klíč 'key'
        new_watch = st.data_editor(
            df_watch, 
            num_rows="dynamic", 
            use_container_width=True,
            key="editor_watchlist" # <--- OPRAVA: Přidán unikátní klíč
        )
        
        if st.button("💾 Uložit Watchlist", key="btn_save_watch", type="primary"):
            # Používáme atomickou funkci pro uložení
            uloz_data_fn(new_watch, USER, data_manager.SOUBOR_WATCHLIST)
            invalidate_core_fn()
            st.success("✅ Watchlist aktualizován")
            time.sleep(1)
            st.rerun()
