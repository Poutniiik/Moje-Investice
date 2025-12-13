import streamlit as st
import pandas as pd
import zipfile
import io
import time
from datetime import datetime
from src.data_manager import (
    uloz_data_uzivatele, uloz_csv, nacti_uzivatele, zasifruj,
    SOUBOR_DATA, SOUBOR_HISTORIE, SOUBOR_CASH, SOUBOR_DIVIDENDY, SOUBOR_WATCHLIST, SOUBOR_UZIVATELE
)
from src.services.portfolio_service import invalidate_data_core
import src.notification_engine as notify

def render_nastaveni_page(USER, df, AI_AVAILABLE):
    st.title("⚙️ KONFIGURACE SYSTÉMU")

    # --- 1. AI KONFIGURACE ---
    with st.container(border=True):
        st.subheader("🤖 AI Jádro & Osobnost")
        c_stat1, c_stat2 = st.columns([1, 3])
        with c_stat1:
            if AI_AVAILABLE: st.success("API: ONLINE")
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
    t1, t2 = st.tabs(["PORTFOLIO", "HISTORIE"])
    with t1:
        new_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
        if st.button("Uložit Portfolio"):
            st.session_state['df'] = new_df
            uloz_data_uzivatele(new_df, USER, SOUBOR_DATA)
            invalidate_data_core()
            st.success("Uloženo"); time.sleep(1); st.rerun()
    with t2:
        new_h = st.data_editor(st.session_state['df_hist'], num_rows="dynamic", use_container_width=True)
        if st.button("Uložit Historii"):
            st.session_state['df_hist'] = new_h
            uloz_data_uzivatele(new_h, USER, SOUBOR_HISTORIE)
            invalidate_data_core()
            st.success("Uloženo"); time.sleep(1); st.rerun()

    st.divider(); st.subheader("📦 ZÁLOHA")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for n, d in [(SOUBOR_DATA, 'df'), (SOUBOR_HISTORIE, 'df_hist'), (SOUBOR_CASH, 'df_cash'), (SOUBOR_DIVIDENDY, 'df_div'), (SOUBOR_WATCHLIST, 'df_watch')]:
            if d in st.session_state: zf.writestr(n, st.session_state[d].to_csv(index=False))
    st.download_button("Stáhnout Data", buf.getvalue(), f"backup_{datetime.now().strftime('%Y%m%d')}.zip", "application/zip")
    st.divider()
    st.subheader("📲 NOTIFIKACE(Telegram)")
    st.caption("Otestuj spojení s tvým mobilem.")

    #TADY JE TA MAGIE
    notify.otestovat_tlacitko()

    # Změna hesla
    with st.expander("🔐 Změna hesla"):
        with st.form("pass_change"):
            old = st.text_input("Staré", type="password"); new = st.text_input("Nové", type="password"); conf = st.text_input("Potvrdit", type="password")
            if st.form_submit_button("Změnit heslo"):
                df_u = nacti_uzivatele(); row = df_u[df_u['username'] == USER]
                if not row.empty and row.iloc[0]['password'] == zasifruj(old):
                    if new == conf and len(new) > 0:
                        df_u.at[row.index[0], 'password'] = zasifruj(new); uloz_csv(df_u, SOUBOR_UZIVATELE, f"Pass change {USER}"); st.success("Hotovo!")
                    else: st.error("Chyba")
                else: st.error("Staré heslo nesedí.")
